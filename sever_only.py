# server_only.py - 一个独立的、仅用于API服务的推理服务器

import uvicorn
import asyncio
import json
import re
import subprocess
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from typing import Dict, Any, List
from rich.console import Console

# ======================== 1. 导入可复用的底层组件 ========================
# 我们从您的项目中导入构建块，而不是整个 main_api.py
from core.prompts import (
    FRAMEWORK_GENERATION_PROMPT,
    DIVERSE_CODE_GENERATION_PROMPT,
    CODE_SELF_REFLECTION_PROMPT,
    FALLBACK_DECISION_PROMPT,
    FINAL_SYNTHESIS_PROMPT,
    DIRECT_ANSWER_PROMPT,
    QUESTION_CLASSIFICATION_PROMPT
)
from core.retrieval_api_client import RetrievalAPIClient
from llm_providers import get_llm_provider
from core.workflow_components import (find_majority_result, 
                                      format_divergent_codes_for_reflection)

# ======================== 2. 复制/重新定义必要的配置和辅助函数 ========================
# 将 main_api.py 中的配置和辅助函数复制到这里，使此文件独立。

# --- 配置 ---
# 注意：我们去掉了与批量文件相关的配置
CONFIG = {
    "base": {
        "retrieval_api_url": "http://localhost:8001"
    },
    "providers": {
        "local": {"provider_type": "local", "model_path": "/zhaoshu/llm/qwen3-32b/"},
        "api": {"provider_type": "api", "model_path": "/zhaoshu/llm/qwen3-32b/", "api_url": "http://localhost:8000/v1"},
        "glm4.5": {"provider_type": "api", "model_path": "glm-4.5", "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",'api_key':'aa6c598ff745960ef447bf4f55ad1f2a.ZYtqw25sXCBOkw5h'},

        
    }
}

# --- 辅助函数 ---
# 这些函数是通用的，直接从 main_api.py 复制过来是安全的
def _parse_code(text: str) -> str:
    if not isinstance(text, str): return ""
    try:
        outer_match = re.search(r'<execute_code>(.*?)</execute_code>', text, re.DOTALL)
        content_to_search = outer_match.group(1) if outer_match else text
        inner_match = re.search(r'```python\n(.*?)\n```', content_to_search, re.DOTALL)
        if inner_match: return inner_match.group(1).strip()
        if outer_match: return content_to_search.strip()
        fallback_match = re.search(r'```(.*?)```', text, re.DOTALL)
        if fallback_match:
            code = fallback_match.group(1).strip()
            if code.lower().startswith('python'):
                re.sub(r'^[pP][yY][tT][hH][oO][nN]\s*', '', code, count=1)
            return code
        return text.strip()
    except Exception: return ""

def _execute_code(code: str, context: str = "") -> Dict:
    full_code = context + "\n" + code
    if not code: return {'code': code, 'output': None, 'error': 'Generated code was empty.'}
    try:
        process = subprocess.run(['python', '-c', full_code], capture_output=True, text=True, timeout=20, check=False)
        return {'code': code, 'output': process.stdout, 'error': process.stderr if process.returncode != 0 else None}
    except Exception as e: return {'code': code, 'output': None, 'error': str(e)}

def _parse_json_from_llm_output(text: str) -> Dict:
    if not isinstance(text, str): return None
    try:
        match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
        if match: return json.loads(match.group(1).strip())
        start_index = text.find('{'); end_index = text.rfind('}')
        if start_index != -1 and end_index != -1 and end_index > start_index:
            return json.loads(text[start_index : end_index + 1])
        return json.loads(text)
    except (json.JSONDecodeError, AttributeError): return None

# ======================== 3. 构建面向API的核心工作流引擎 ========================
# 这是从 main_api.py 的逻辑改编而来的，专门用于处理单个请求。

async def solve_prompt_for_api(
    prompt: str,
    workflow: str,
    provider: str,
    llm_service: Any, # 传递已初始化的服务
    retriever: RetrievalAPIClient # 传递已初始化的服务
) -> Dict:
    """
    一个自包含的函数，用于处理单个API请求的完整工作流。
    """
    is_async = (provider == 'api')
    console = Console()
    console.print(f"[bold blue]  -> Solving API request with workflow '{workflow}'...[/bold blue]")

    # --- 阶段 1: 检索 ---
    # `search`方法接收一个prompts列表，所以我们把单个prompt放进去
    retrieved_results = retriever.search([prompt], k=3)
    retrieved_info = {'knowledge_points': [], 'common_pitfalls': []}
    if retrieved_results and retrieved_results[0]:
        for res in retrieved_results[0]:
            retrieved_info['knowledge_points'].extend(res.get('knowledge_points', []))
            retrieved_info['common_pitfalls'].extend(res.get('common_pitfalls', []))
        retrieved_info['knowledge_points'] = [dict(t) for t in {tuple(d.items()) for d in retrieved_info['knowledge_points']}]
        retrieved_info['common_pitfalls'] = list(set(retrieved_info['common_pitfalls']))

    knowledge_and_pitfalls_str = (
        f"知识点:\n" + "\n".join([f"- {p['point']}: {p['description']}" for p in retrieved_info.get('knowledge_points', [])]) +
        "\n\n常见陷阱:\n" + "\n".join([f"- {p}" for p in retrieved_info.get('common_pitfalls', [])])
    )

    # --- 阶段 2: 根据工作流执行 ---
    
    # ---- 'direct' 工作流 ----
    if workflow == 'direct':
        content = DIRECT_ANSWER_PROMPT.format(new_question_prompt=prompt, knowledge_and_pitfalls=knowledge_and_pitfalls_str)
        messages = [[{"role": "user", "content": content}]]
        if is_async: outputs = await llm_service.generate_with_think_and_parse_batch(messages, enable_thinking=False)
        else: outputs = llm_service.generate_with_think_and_parse_batch(messages, enable_thinking=False)
        return {"response": outputs[0]['answer'], "metadata": {"workflow": f"direct_{provider}"}}

    # ---- 'full' 工作流 (智能路由) ----
    if workflow == 'full':
        # 1. 分类问题
        messages = [[{"role": "user", "content": QUESTION_CLASSIFICATION_PROMPT.format(question_prompt=prompt)}]]
        if is_async: json_outputs = await llm_service.generate_json_batch(messages)
        else: json_outputs = llm_service.generate_json_batch(messages)
        question_type = json_outputs[0].get("question_type", "procedural") if isinstance(json_outputs[0], dict) else "procedural"

        # 2. 如果是直接问题，路由到直接回答
        if question_type == 'direct':
            console.print("  -> Routed to: Direct Answer")
            content = DIRECT_ANSWER_PROMPT.format(new_question_prompt=prompt, knowledge_and_pitfalls=knowledge_and_pitfalls_str)
            messages = [[{"role": "user", "content": content}]]
            if is_async: outputs = await llm_service.generate_with_think_and_parse_batch(messages, enable_thinking=False)
            else: outputs = llm_service.generate_with_think_and_parse_batch(messages, enable_thinking=False)
            return {"response": outputs[0]['answer'], "metadata": {"workflow": f"full_routed_direct_{provider}"}}

        # 3. 如果是程序性问题，执行完整迭代流程
        else:
            console.print("  -> Routed to: Procedural Iterative Solving")
            # --- 以下是完整的迭代求解逻辑，直接从 main_api.py 中适配而来 ---
            content = FRAMEWORK_GENERATION_PROMPT.format(question=prompt, knowledge_and_pitfalls=knowledge_and_pitfalls_str)
            messages = [[{"role": "user", "content": content}]]
            if is_async: framework_outputs = await llm_service.generate_with_think_and_parse_batch(messages, enable_thinking=True, max_token=6000)
            else: framework_outputs = llm_service.generate_with_think_and_parse_batch(messages, enable_thinking=True, max_token=6000)
            solving_plan_str = framework_outputs[0]['answer']
            solving_plan = _parse_json_from_llm_output(solving_plan_str)

            if solving_plan is None:
                return {"response": "Error: Failed to generate a valid solving plan.", "metadata": {"raw_plan_output": solving_plan_str}}

            execution_context, full_trace, all_steps_succeeded = "# Execution context starts here.\n", "", True
            
            for subquestion_key, steps in solving_plan.items():
                console.rule(f"Solving {subquestion_key}", style="cyan")
                subproblem_framework = f"Instructions for {subquestion_key}:\n" + "\n".join([f"- {s['step']}: {s['core_operation']}" for s in steps])
                
                content = DIVERSE_CODE_GENERATION_PROMPT.format(original_question=prompt, execution_context=execution_context, subproblem_framework=subproblem_framework)
                messages_batch = [[{"role": "user", "content": content}] for _ in range(3)]
                if is_async: code_gen_outputs = await llm_service.generate_with_think_and_parse_batch(messages_batch, enable_thinking=False)
                else: code_gen_outputs = llm_service.generate_with_think_and_parse_batch(messages_batch, enable_thinking=False)
                code_candidates = [_parse_code(out['answer']) for out in code_gen_outputs]

                step_exec_results = [_execute_code(code, execution_context) for code in code_candidates]
                majority_result, _ = find_majority_result(step_exec_results)
                
                best_code_for_step, best_result_for_step = None, None
                if majority_result:
                    best_code_for_step, best_result_for_step = majority_result['code'], majority_result
                else:
                    successful_results = [r for r in step_exec_results if r['error'] is None and r['output']]
                    if successful_results:
                        analysis_str = format_divergent_codes_for_reflection(successful_results)
                        content = CODE_SELF_REFLECTION_PROMPT.format(original_question=prompt, subproblem_framework=subproblem_framework, execution_context=execution_context, divergent_codes_analysis=analysis_str)
                        reflection_messages = [[{"role": "user", "content": content}] for _ in range(3)]
                        if is_async: reflection_outputs = await llm_service.generate_with_think_and_parse_batch(reflection_messages, enable_thinking=False)
                        else: reflection_outputs = llm_service.generate_with_think_and_parse_batch(reflection_messages, enable_thinking=False)
                        revised_code_candidates = [_parse_code(out['answer']) for out in reflection_outputs]
                        
                        for revised_code in revised_code_candidates:
                            if not revised_code: continue
                            revised_result = _execute_code(revised_code, execution_context)
                            if revised_result['error'] is None:
                                best_code_for_step, best_result_for_step = revised_code, revised_result; break
                        
                        if best_code_for_step is None:
                            content = FALLBACK_DECISION_PROMPT.format(original_question=prompt, subproblem_framework=subproblem_framework, successful_solutions_analysis=analysis_str)
                            if is_async: decision_json_list = await llm_service.generate_json_batch([[{"role": "user", "content": content}]])
                            else: decision_json_list = llm_service.generate_json_batch([[{"role": "user", "content": content}]])
                            decision = decision_json_list[0]
                            best_index = int(decision.get("best_fallback_index", 1)) - 1 if decision else 0
                            best_code_for_step, best_result_for_step = successful_results[best_index]['code'], successful_results[best_index]

                if best_code_for_step is None:
                    console.print(f"[red]❌ Failed to solve {subquestion_key}. Aborting workflow for this question.[/red]")
                    all_steps_succeeded = False; break

                execution_context += f"\n# --- Code for {subquestion_key} ---\n{best_code_for_step}\n"
                full_trace += f"--- {subquestion_key} ---\n[Code]:\n{best_code_for_step}\n[Result]:\n{best_result_for_step['output']}\n\n"
            
            if all_steps_succeeded:
                console.print("\n[bold blue]Synthesizing final answer...[/bold blue]")
                content = FINAL_SYNTHESIS_PROMPT.format(original_question=prompt, full_execution_trace=full_trace)
                if is_async: final_answer_output = await llm_service.generate_with_think_and_parse_batch([[{"role": "user", "content": content}]], enable_thinking=False)
                else: final_answer_output = llm_service.generate_with_think_and_parse_batch([[{"role": "user", "content": content}]], enable_thinking=False)
                return {"response": final_answer_output[0]['answer'], "metadata": {"workflow": f"full_iterative_{provider}", "trace": full_trace}}
            else:
                return {"response": "Error: Failed during iterative solving process.", "metadata": {"workflow": f"full_iterative_failed_{provider}", "trace": full_trace}}

    # 如果工作流名称不匹配，返回错误
    raise ValueError(f"Unknown workflow: {workflow}")


# ======================== 4. FastAPI 应用设置 ========================

# --- API 数据模型定义 ---
class SolveRequest(BaseModel):
    prompt: str = Field(..., description="用户输入的完整问题文本。")
    workflow: str = Field("full", enum=["full", "direct"], description="选择 'full' (智能) 或 'direct' (直接) 工作流。")
    provider: str = Field("api", enum=["api", "local"], description="选择 'api' (异步) 或 'local' (同步) LLM提供者。")

class SolveResponse(BaseModel):
    response: str
    metadata: Dict[str, Any]

# --- 资源管理: 在应用启动时加载模型 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 API服务启动中，开始加载资源...")
    # 这里我们允许通过请求来选择 provider，但默认启动时加载一个
    # 你可以根据常用场景硬编码 'api' 或 'local'
    default_provider = "api" 
    print(f"Pre-loading default provider: '{default_provider}'")
    provider_config = CONFIG['providers'][default_provider]
    # 将模型实例存储在 app.state 中，以便在请求之间共享
    app.state.llm_service = get_llm_provider(provider_config)
    print(f"✅ LLM Service ('{default_provider}') 加载完成.")

    app.state.retriever = RetrievalAPIClient(base_url=CONFIG['base']["retrieval_api_url"])
    print(f"✅ Retrieval Client 连接到 {CONFIG['base']['retrieval_api_url']} 完成.")

    print("🎉 API服务已就绪，可以接收请求!")
    yield
    print("🔌 API服务正在关闭...")

# --- 创建 FastAPI 应用实例 ---
app = FastAPI(
    title="独立推理框架 API",
    description="一个接收文本输入，通过多Agent协作流程返回问题解答的API (不依赖main_api.py)。",
    version="2.0.0",
    lifespan=lifespan
)

# --- 定义 API 端点 ---
@app.post("/solve", response_model=SolveResponse)
async def solve_endpoint(req: Request, solve_request: SolveRequest):
    """
    接收问题并启动推理工作流。
    """
    try:
        # 从 app.state 获取已初始化的服务
        llm_service = req.app.state.llm_service
        retriever = req.app.state.retriever

        # 注意：这里的实现假设请求中的provider与启动时加载的provider一致。
        # 如果需要动态切换，需要更复杂的逻辑来管理多个llm_service实例。
        # 目前的设计是最简单高效的。
        if solve_request.provider != llm_service.provider_type:
             raise HTTPException(
                status_code=400, 
                detail=f"Requested provider ('{solve_request.provider}') does not match the running server's provider ('{llm_service.provider_type}')."
            )

        print(f"\n🚀 收到新请求: prompt='{solve_request.prompt[:50]}...', workflow='{solve_request.workflow}'")
        
        # 调用核心逻辑处理请求
        result = await solve_prompt_for_api(
            prompt=solve_request.prompt,
            workflow=solve_request.workflow,
            provider=solve_request.provider,
            llm_service=llm_service,
            retriever=retriever
        )
        
        print("✅ 请求处理完成.")
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/", summary="健康检查")
def read_root():
    return {"status": "ok", "message": "独立推理API正在运行。"}

# --- 运行服务器的入口点 ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)