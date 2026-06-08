"""Artifact access endpoints for generated content."""

import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["artifacts"])


@router.get("/runs/{run_id}/artifacts/{artifact_type}")
async def get_artifact(run_id: str, artifact_type: str, slot_id: str = None):
    """Read artifacts from disk.

    Args:
        run_id: The run identifier (workspace directory name).
        artifact_type: Type of artifact (outline, final, review, solution, revision_report, manifest).
        slot_id: Optional slot ID for per-slot artifacts like final.md.

    Returns:
        PlainTextResponse with the artifact content.
    """
    # Search in common locations
    search_dirs = [
        os.path.join("docs", "compose"),
        os.path.join("docs", "workspace", run_id),
        os.path.join("docs"),
    ]

    if artifact_type == "outline":
        filename = "outline.md"
    elif artifact_type == "revision_report":
        filename = "revision_report.md"
    elif artifact_type == "final" and slot_id:
        # Per-slot final.md
        for d in search_dirs:
            path = os.path.join(d, slot_id, "final.md")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return PlainTextResponse(f.read())
        raise HTTPException(404, f"final.md not found for slot {slot_id}")
    elif artifact_type == "manifest":
        filename = "manifest.md"
    else:
        raise HTTPException(400, f"Unknown artifact type: {artifact_type}")

    for d in search_dirs:
        path = os.path.join(d, filename)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return PlainTextResponse(f.read())

    raise HTTPException(404, f"{artifact_type} not found")
