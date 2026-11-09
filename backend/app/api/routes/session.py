from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import get_current_user, get_session_repo
from app.db.repositories.session_repo import SessionRepository, SessionStatus, SessionPhase

router = APIRouter(prefix="/sessions", tags=["sessions"])

PHASE_ORDER = [
    SessionPhase.RAPPORT,
    SessionPhase.FREE_RECALL,
    SessionPhase.PROBING,
    SessionPhase.CLARIFICATION,
    SessionPhase.CLOSURE,
]


def _session_to_response(session: dict) -> dict:
    return {
        "id": session.get("_id"),
        "investigator_id": session.get("investigator_id"),
        "witness_name": session.get("witness_name"),
        "case_number": session.get("case_number"),
        "incident_type": session.get("crime_type"),
        "incident_date": session.get("incident_date"),
        "session_status": session.get("status"),
        "current_phase": session.get("phase"),
        "total_questions": session.get("total_questions", 0),
        "started_at": session.get("start_time"),
        "ended_at": session.get("end_time"),
        "created_at": session.get("created_at"),
        "overall_stress_score": session.get("overall_stress_score", 0.0),
        "overall_credibility_score": session.get("overall_credibility_score", 0.0),
        "flag_count": session.get("flags_count", 0),
        "notes": session.get("notes"),
        "tags": session.get("tags", []),
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: dict,
    current_user=Depends(get_current_user),
    repo: SessionRepository = Depends(get_session_repo),
):
    created = await repo.create(
        witness_id="",
        investigator_id=str(current_user.id),
        crime_type=payload.get("incident_type", ""),
        witness_name=payload.get("witness_name", ""),
        case_number=payload.get("case_number", ""),
        notes=payload.get("notes"),
    )
    return _session_to_response(created)


@router.get("/")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    repo: SessionRepository = Depends(get_session_repo),
):
    sessions, total = await repo.get_by_investigator(
        str(current_user.id), page=page, page_size=page_size
    )
    return {
        "sessions": [_session_to_response(s) for s in sessions],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    current_user=Depends(get_current_user),
    repo: SessionRepository = Depends(get_session_repo),
):
    session = await repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["investigator_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    return _session_to_response(session)


@router.patch("/{session_id}")
async def update_session(
    session_id: str,
    payload: dict,
    current_user=Depends(get_current_user),
    repo: SessionRepository = Depends(get_session_repo),
):
    session = await repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["investigator_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    if payload.get("session_status"):
        session = await repo.update_status(session_id, payload["session_status"])
    if payload.get("notes") is not None:
        await repo.update_notes(session_id, payload["notes"])
        session = await repo.get_by_id(session_id)
    return _session_to_response(session)


@router.post("/{session_id}/start")
async def start_session(
    session_id: str,
    current_user=Depends(get_current_user),
    repo: SessionRepository = Depends(get_session_repo),
):
    session = await repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["investigator_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    if session["status"] != SessionStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Session is already {session['status']}")
    updated = await repo.update_status(session_id, SessionStatus.ACTIVE)
    return _session_to_response(updated)


@router.post("/{session_id}/end")
async def end_session(
    session_id: str,
    current_user=Depends(get_current_user),
    repo: SessionRepository = Depends(get_session_repo),
):
    session = await repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["investigator_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    if session["status"] not in (SessionStatus.ACTIVE, SessionStatus.PAUSED):
        raise HTTPException(status_code=400, detail="Session is not active")
    updated = await repo.update_status(session_id, SessionStatus.COMPLETED)
    return _session_to_response(updated)


@router.post("/{session_id}/advance-phase")
async def advance_phase(
    session_id: str,
    current_user=Depends(get_current_user),
    repo: SessionRepository = Depends(get_session_repo),
):
    session = await repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["investigator_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    if session["status"] != SessionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Session must be active")

    current_index = PHASE_ORDER.index(session["phase"])
    if current_index >= len(PHASE_ORDER) - 1:
        raise HTTPException(status_code=400, detail="Already in final phase")

    updated = await repo.advance_phase(session_id)
    return _session_to_response(updated)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user=Depends(get_current_user),
    repo: SessionRepository = Depends(get_session_repo),
):
    session = await repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["investigator_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    await repo.delete(session_id)