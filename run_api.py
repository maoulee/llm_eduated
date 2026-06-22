#!/usr/bin/env python3
"""Run the EduTeacher Workbench API server."""

import os
import sys
import uvicorn

# Ensure project root in path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "3001"))

    print(f"Starting EduTeacher Workbench API on {host}:{port}")
    print(f"Project root: {project_root}")

    uvicorn.run(
        "api.app:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )
