"""FastAPI application for EduTeacher Workbench."""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import session, interact, compose, artifacts, events, health, interact_v2

app = FastAPI(title="EduTeacher Workbench", version="0.1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(session.router, prefix="/api")
app.include_router(interact.router, prefix="/api")
app.include_router(compose.router, prefix="/api")
app.include_router(artifacts.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(interact_v2.router, prefix="/api")


@app.get("/teacher-interact")
@app.get("/teacher-interact-lite-v7.html")
async def teacher_interact_lite():
    """Serve the standalone teacher interaction frontend."""
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "teacher-interact-lite-v7.html",
    )
    if not os.path.exists(path):
        raise HTTPException(404, "teacher-interact-lite-v7.html not found")
    return FileResponse(path, media_type="text/html; charset=utf-8")


# Serve static frontend files (built Vue app) if available
static_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "static"
)
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "EduTeacher Workbench API", "version": "0.1.0"}
