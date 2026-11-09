"""
Evidence route — accepts image or video file upload.
OpenCV analyzes the evidence and builds context for Groq.
"""

import os
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from app.core.dependencies import get_current_user
from app.db.repositories.session_repo import SessionRepository
from app.services.vision.evidence_analyzer import (
    analyze_image_bytes,
    analyze_video_bytes,
    build_evidence_context_string,
)

router = APIRouter(prefix="/evidence", tags=["evidence"])

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


class EvidenceResponse(BaseModel):
    session_id: str
    evidence_type: str
    summary: str
    face_count: int
    scene_type: str
    motion_detected: bool
    dominant_colors: list[str]
    frame_count: int
    duration_sec: float
    context_string: str
    error: str | None


@router.post("/upload", response_model=EvidenceResponse)
async def upload_evidence(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    repo = SessionRepository()
    session = await repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["investigator_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Read file
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in IMAGE_EXTENSIONS and ext not in VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Upload jpg, png, mp4, mov, avi, mkv, or webm."
        )

    # ── Analyze ──────────────────────────────────────────────────────────
    if ext in IMAGE_EXTENSIONS:
        result = analyze_image_bytes(file_bytes, filename)
        evidence_type = "image"
        context_string = build_evidence_context_string("image", image_result=result)
        face_count = result.get("face_count", 0)
        scene_type = result.get("scene_type", "unknown")
        dominant_colors = result.get("dominant_colors", [])
        motion_detected = False
        frame_count = 1
        duration_sec = 0.0
        summary = result.get("context_string", "Image analyzed")
        error = result.get("error")

    else:
        result = analyze_video_bytes(file_bytes, num_frames=6)
        evidence_type = "video"
        context_string = build_evidence_context_string("video", video_result=result)
        face_count = result.get("max_faces_in_frame", 0)
        scene_type = result.get("scene_type", "unknown")
        dominant_colors = result.get("dominant_colors", [])
        motion_detected = result.get("motion_frames", 0) > 0
        frame_count = result.get("total_frames_analyzed", 0)
        duration_sec = result.get("duration_sec", 0.0)
        summary = result.get("aggregate_context", "Video analyzed")
        error = result.get("error")

    # ── Save context to session ───────────────────────────────────────────
    await repo.save_evidence_context(
        session_id=session_id,
        evidence_description=summary,
        nlp_result={},
        scene_summary=summary,
        evidence_type=evidence_type,
        opencv_result=result,
        context_string=context_string,
    )

    return EvidenceResponse(
        session_id=session_id,
        evidence_type=evidence_type,
        summary=summary,
        face_count=face_count,
        scene_type=scene_type,
        motion_detected=motion_detected,
        dominant_colors=dominant_colors,
        frame_count=frame_count,
        duration_sec=duration_sec,
        context_string=context_string,
        error=error,
    )