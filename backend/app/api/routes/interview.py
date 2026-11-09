from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_current_user, get_session_repo
from app.db.repositories.session_repo import SessionRepository
from app.models.session import SessionStatus
from app.models.user import User
from app.schemas.interview import InterviewStateResponse

router = APIRouter(prefix="/interview", tags=["interview"])


@router.get("/{session_id}/state", response_model=InterviewStateResponse)
async def get_interview_state(
    session_id: str,
    current_user: User = Depends(get_current_user),
    repo: SessionRepository = Depends(get_session_repo),
):
    session = await repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.investigator_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    return InterviewStateResponse(
        session_id=session_id,
        current_phase=session.current_phase,
        total_questions=session.total_questions,
        phase_question_count=session.phase_question_count,
        overall_stress_score=session.overall_stress_score,
        is_complete=session.session_status == SessionStatus.COMPLETED,
    )