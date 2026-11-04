#!/usr/bin/env python3
"""Run the EduTeacher Workbench API server."""

import os
import sys
import uvicorn

# Ensure project root in path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Default VLLM model (can be overridden by env)
os.environ.setdefault("VLLM_MODEL", "/zhaoshu/llm/Qwen3.6-27B-FP8")
os.environ.setdefault("VLLM_API_BASE", "http://127.0.0.1:8000/v1")

# Load operational env (GLM key for glm5.2_anthropic etc.) — sibling repo shares it.
# Must run before uvicorn imports api.app (which imports config.py → reads GLM_* env).
from dotenv import load_dotenv
for _env in ("/zhaoshu/llm_eduated/.env", os.path.join(project_root, ".env")):
    if os.path.exists(_env):
        load_dotenv(_env)

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "3001"))

    print(f"Starting EduTeacher Workbench API on {host}:{port}")
    print(f"VLLM_MODEL: {os.getenv('VLLM_MODEL')}")
    print(f"Project root: {project_root}")

    uvicorn.run(
        "api.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
