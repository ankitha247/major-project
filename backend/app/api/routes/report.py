"""
Report generation route.
Generates a full PDF report for a completed session.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
import os

from app.core.dependencies import get_current_user
from app.db.repositories.session_repo import SessionRepository
from app.services.analysis.stress_scorer import get_session_stress_summary
from app.services.analysis.flag_engine import get_flag_engine

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{session_id}")
async def get_report(
    session_id: str,
    current_user=Depends(get_current_user),
):
    repo = SessionRepository()
    session = await repo.get_by_id(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["investigator_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "session_id": session_id,
        "witness_name": session["witness_name"],
        "case_number": session["case_number"],
        "crime_type": session["crime_type"],
        "status": session["status"],
        "phase": session["phase"],
        "total_questions": session["total_questions"],
        "overall_stress_score": session["overall_stress_score"],
        "overall_credibility_score": session["overall_credibility_score"],
        "flags_count": session["flags_count"],
        "start_time": session["start_time"],
        "end_time": session["end_time"],
        "notes": session["notes"],
    }


@router.post("/{session_id}/generate-pdf")
async def generate_pdf_report(
    session_id: str,
    current_user=Depends(get_current_user),
):
    repo = SessionRepository()
    session = await repo.get_by_id(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["investigator_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    from scripts.export_report import generate_pdf
    pdf_path = await generate_pdf(session)

    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail="PDF generation failed")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"report_{session['case_number']}_{session_id}.pdf",
    )