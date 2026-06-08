"""FastAPI application for EduTeacher Workbench."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import session, interact, compose, artifacts, events, health

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
