#!/bin/bash

# ==============================================================================
#                 MCTS-Reason 多功能服务管理器 (v3.5 - 完整最终版)
# ==============================================================================
#
# 新特性:
# - [新增] 支持为 retrieval 服务指定GPU
# - [新增] 支持通过 `start llm <config_name>` 启动指定的本地模型作为API服务
# - [新增] 支持通过 `--quant <method>` 命令行标志覆盖量化配置
# - 更健壮的 Conda 环境激活逻辑
# - 增加服务启动后的健康检查
# - 使用进程组(PGID)进行清理，更彻底
# - 统一的 PYTHONPATH 管理
#
# ==============================================================================

# --- 脚本设置 ---
set -e

# --- 1. 项目根目录和工作目录 ---
PROJECT_ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"

# --- 2. 颜色定义 ---
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

# --- 3. Conda环境激活 ---
CONDA_ENV_NAME="llm"
echo -e "${YELLOW}>>> Activating Conda environment: ${CONDA_ENV_NAME}...${NC}"
if command -v conda &>/dev/null && conda run -n "$CONDA_ENV_NAME" python -c "" &>/dev/null; then
    PYTHON_CMD="conda run --no-capture-output -n $CONDA_ENV_NAME python"
else
    CONDA_BASE=$(conda info --base)
    if [ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]; then
        # shellcheck disable=SC1091
        source "$CONDA_BASE/etc/profile.d/conda.sh"
        conda activate "$CONDA_ENV_NAME"
        PYTHON_CMD="python"
    else
        echo -e "${RED}Error: Conda initialization script not found.${NC}"; exit 1
    fi
fi
echo -e "  - Python executable: $(eval "$PYTHON_CMD -c 'import sys; print(sys.executable)'")"


# --- 4. 日志和PID目录 ---
LOG_DIR="$PROJECT_ROOT/log"; mkdir -p "$LOG_DIR"

# --- 5. 配置加载函数 ---
get_config_value() {
    $PYTHON_CMD -c "from config import settings; value = settings.$1; print(value if value is not None else '')"
}

# 加载通用配置
RETRIEVAL_PORT=$(get_config_value "servers.retrieval_api_port")
LLM_PORT=$(get_config_value "servers.vllm_api_port")
SOLVER_PORT=$(get_config_value "servers.solver_api_port")
LLM_MODEL_PATH=$(get_config_value "providers['local'].model_path")
LLM_TP_SIZE=$(get_config_value "providers['local'].tensor_parallel_size")
LLM_GPU_MEM=$(get_config_value "providers['local'].gpu_memory_utilization")
LLM_QUANT=$(get_config_value "providers['local'].quantization")

# --- PID 和 日志文件路径 ---
RETRIEVAL_PID_FILE="$LOG_DIR/retrieval.pid"; RETRIEVAL_LOG_FILE="$LOG_DIR/retrieval_server.log"
LLM_PID_FILE="$LOG_DIR/llm.pid"; LLM_LOG_FILE="$LOG_DIR/llm_server.log"

# ============================= 函数定义 =============================

# -- 辅助函数: 停止单个服务 (通过进程组PGID) --
stop_service() {
    local service_name=$1
    local pid_file=$2
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        # 检查PID是否存在，防止文件残留但进程已死
        if ! ps -p "$pid" > /dev/null; then
            echo -e "$service_name is not running (stale PID file found). Cleaning up."
            rm -f "$pid_file"
            return
        fi

        local pgid
        pgid=$(ps -o pgid= -p "$pid" | tr -d ' ')
        
        # --- [关键修复] ---
        # 使用标准的多行 if-then-fi 结构
        if [ -n "$pgid" ]; then
            echo -e "Stopping $service_name (PGID: $pgid)..."
            # 使用 kill -- -PGID 来杀死整个进程组
            kill -- -"$pgid" &>/dev/null || true
        else
             # 如果无法获取PGID，作为后备方案，只杀死主进程
            echo -e "Could not get PGID for PID $pid. Killing PID directly..."
            kill "$pid" &>/dev/null || true
        fi
        
        rm -f "$pid_file"
    else
        echo -e "$service_name is not running (no PID file)."
    fi
}

# -- 启动单个服务 --
start_single_service() {
    local service_name=$1
    local command_str=$2
    local log_file=$3
    local pid_file=$4
    local health_check_url=$5

    echo "Starting $service_name..."
    
    # --- [关键修复] ---
    # 使用 setsid bash -c "..." 的方式来执行包含环境变量的完整命令字符串
    # 1. setsid 启动一个新的 bash 进程
    # 2. bash -c "..." 让这个新的 bash 进程执行我们想要的命令
    # 3. 最后的 & 将整个 (setsid bash ...) 放入后台
    (setsid bash -c "$command_str") > "$log_file" 2>&1 &
    
    local pid=$!
    # $! 仍然是 setsid 进程的PID
    echo "$pid" > "$pid_file"
    echo -e "  -> Service starting with PID: ${GREEN}$pid${NC}, Log: $log_file"

    # 健康检查部分保持不变
    echo -n "  -> Waiting for service to be ready..."
    for _ in {1..30}; do
        if curl -s -f "$health_check_url" &>/dev/null; then
            echo -e " ${GREEN}Online!${NC}"
            return 0
        fi
        sleep 1; echo -n "."
    done
    echo -e " ${RED}Failed!${NC} Service did not become ready in time. Check logs."
    return 1
}

# -- 启动所有服务 --
start_services() {
    local service_to_start=$1
    shift # 移除第一个参数，方便后续处理
    
    local llm_config_name="qwen3local_api"
    local retrieval_gpu_ids="0"
    local llm_gpu_ids="0"
    local quant_override=""

    # --- [关键修改] 解析更灵活的参数 ---
    if [[ "$service_to_start" == "retrieval" ]]; then
        retrieval_gpu_ids=${1:-0}
    elif [[ "$service_to_start" == "llm" ]]; then
        llm_config_name=${1:-qwen3local_api}
        llm_gpu_ids=${2:-0}
        # 查找 --quant 参数
        for arg in "$@"; do
            if [[ $arg == --quant=* ]]; then quant_override="${arg#*=}"; fi
        done
    else # all
        # 默认: retrieval 在 GPU 0, llm 在 GPU 1
        retrieval_gpu_ids=${1:-0}
        llm_gpu_ids=${2:-1}
    fi


    if [[ "$service_to_start" == "all" || "$service_to_start" == "retrieval" ]]; then
        echo -e "${YELLOW}>>> Starting Retrieval Service on GPU(s): ${retrieval_gpu_ids}...${NC}"
        local cmd="CUDA_VISIBLE_DEVICES=$retrieval_gpu_ids $ENV_PREFIX $PYTHON_CMD -m uvicorn llm_providers_new.retrieval_api_server:app --host 0.0.0.0 --port $RETRIEVAL_PORT"
        start_single_service "Retrieval Service" "$cmd" "$RETRIEVAL_LOG_FILE" "$RETRIEVAL_PID_FILE" "http://localhost:$RETRIEVAL_PORT/health"
    fi

    if [[ "$service_to_start" == "all" || "$service_to_start" == "llm" ]]; then
        echo -e "${YELLOW}>>> Preparing to start LLM service using config: '${llm_config_name}' on GPU(s): ${llm_gpu_ids}...${NC}"
        
        local provider_type; provider_type=$(get_config_value "providers['$llm_config_name'].provider_type")
        local serve_as_api; serve_as_api=$(get_config_value "providers['$llm_config_name'].serve_as_api")

        if [[ "$provider_type" != "local" || "$serve_as_api" != "True" ]]; then
            echo -e "${RED}Error: Config '${llm_config_name}' is not a local model configured to be served as an API.${NC}"
            exit 1
        fi

        local llm_model_path; llm_model_path=$(get_config_value "providers['$llm_config_name'].model_path")
        local llm_gpu_mem; llm_gpu_mem=$(get_config_value "providers['$llm_config_name'].gpu_memory_utilization")
        
        local llm_quant
        if [ -n "$quant_override" ]; then
            llm_quant="$quant_override"
            echo "  - Using quantization from command line: $llm_quant"
        else
            llm_quant=$(get_config_value "providers['$llm_config_name'].quantization")
            if [ -n "$llm_quant" ]; then echo "  - Using quantization from config file: $llm_quant"; fi
        fi
        
        local quant_arg=""
        if [ -n "$llm_quant" ] && [ "$llm_quant" != "None" ]; then
            quant_arg="--quantization $llm_quant"
        fi
        
        local tp_size; tp_size=$(echo "${llm_gpu_ids//,/ }" | wc -w)
        
        local cmd="CUDA_VISIBLE_DEVICES=$llm_gpu_ids $PYTHON_CMD -m vllm.entrypoints.openai.api_server \
            --model \"$llm_model_path\" \
            --tensor-parallel-size \"$tp_size\" \
            $quant_arg \
            --gpu-memory-utilization \"$llm_gpu_mem\" \
            --trust-remote-code \
            --port \"$LLM_PORT\""
        
        start_single_service "vLLM Service ($llm_config_name)" "$cmd" "$LLM_LOG_FILE" "$LLM_PID_FILE" "http://localhost:$LLM_PORT/health"
    fi
}

# -- 停止所有服务 --
stop_all_services() {
    echo -e "${YELLOW}>>> Stopping all services...${NC}"
    stop_service "LLM Service" "$LLM_PID_FILE"
    stop_service "Retrieval Service" "$RETRIEVAL_PID_FILE"
}

# -- 强大的清理函数 --
force_clean() {
    stop_all_services
    echo -e "${YELLOW}>>> Force cleaning processes on ports...${NC}"
    for port in $RETRIEVAL_PORT $LLM_PORT; do
        lsof -t -i:"$port" | xargs -r kill -9 &>/dev/null && echo "  - Port $port cleaned." || true
    done
    echo -e "${GREEN}>>> Cleanup complete.${NC}"
}

# -- 检查状态 --
check_status() {
    echo -e "${YELLOW}>>> Checking service status...${NC}"
    check_single_status() {
        local name=$1; local pid_file=$2; local port=$3
        if [ -f "$pid_file" ] && ps -p "$(cat "$pid_file")" &>/dev/null; then
            echo -e "$name: ${GREEN}RUNNING${NC} (PID: $(cat "$pid_file"), Port: $port)"
        else
            echo -e "$name: ${RED}STOPPED${NC}"
        fi
    }
    check_single_status "Retrieval Service" "$RETRIEVAL_PID_FILE" "$RETRIEVAL_PORT"
    check_single_status "LLM Service      " "$LLM_PID_FILE" "$LLM_PORT"
}

# -- 查看日志 --
view_logs() {
    local target=${1:-retrieval}
    local log_file
    case "$target" in
        llm) log_file="$LLM_LOG_FILE";;
        retrieval|*) log_file="$RETRIEVAL_LOG_FILE";;
    esac

    if [ -f "$log_file" ]; then
        echo "Tailing log file: $log_file (Press Ctrl+C to exit)"
        tail -f "$log_file"
    else
        echo -e "${RED}Error: Log file not found: $log_file${NC}"
    fi
}

# ============================= 主逻辑入口 =============================

COMMAND=$1
shift # 移除第一个参数，方便后续函数处理

case "$COMMAND" in
    start)
        # ./service.sh start retrieval [gpu_ids]
        # ./service.sh start llm [model_config_name] [gpu_ids] [--quant=awq]
        # ./service.sh start all [retrieval_gpu_ids] [llm_gpu_ids]
        start_services "$@"
        echo && check_status
        ;;
    stop)
        stop_all_services
        ;;
    restart)
        force_clean
        echo "Waiting for ports to free up..."
        sleep 3
        start_services "$@"
        echo && check_status
        ;;
    clean)
        force_clean
        ;;
    status)
        check_status
        ;;
    logs)
        view_logs "$1"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|clean|status|logs} [service_name] [options]"
        echo ""
        echo "START COMMANDS:"
        echo "  ./service.sh start all [retrieval_gpus] [llm_gpus]"
        echo "    - Example: ./service.sh start all 0 1,2   (Retrieval on GPU 0, LLM on GPUs 1 and 2)"
        echo "    - Default: ./service.sh start all         (Retrieval on GPU 0, LLM on GPU 1)"
        echo ""
        echo "  ./service.sh start retrieval [gpu_ids]"
        echo "    - Example: ./service.sh start retrieval 0"
        echo ""
        echo "  ./service.sh start llm [model_config] [gpu_ids] [--quant=<method>]"
        echo "    - Example: ./service.sh start llm qwen3local_api 1 --quant=awq"
        echo ""
        echo "OTHER COMMANDS:"
        echo "  ./service.sh stop"
        echo "  ./service.sh logs llm"
        exit 1
        ;;
esac