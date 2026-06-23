# 假设您想将 retrieval 服务放在 GPU 0, qwen3local_api 服务放在 GPU 1

# 1. 在后台启动 retrieval 服务 (注意命令末尾的 &)
echo "--- Starting Retrieval Service on GPU 0 ---"
bash /data/amax/home/E22101006/mcts_reason/service.sh start retrieval 1 &

# 等待几秒钟，让第一个服务有时间初始化，避免日志混杂
sleep 30
# 2. 在后台启动 qwen3local_api 服务 (注意命令末尾的 &)
echo "--- Starting LLM Service (qwen3local_api) on GPU 1 ---"
bash /data/amax/home/E22101006/mcts_reason/service.sh start llm qwen3local_api 0,1 &

# 3. (可选) 等待服务启动后，检查状态
echo "--- Waiting for services to start up... ---"
sleep 120 # 等待时间可以根据您的机器性能调整
bash /data/amax/home/E22101006/mcts_reason/service.sh status