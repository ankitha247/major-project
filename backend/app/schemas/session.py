from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.models.session import SessionStatus, SessionPhase


class SessionCreateRequest(BaseModel):
    witness_name: str = Field(..., min_length=2, max_length=100)
    case_number: str = Field(..., min_length=1, max_length=50)
    incident_type: str = Field(..., min_length=2, max_length=100)
    incident_date: Optional[datetime] = None
    notes: Optional[str] = None
    tags: list[str] = []


class SessionUpdateRequest(BaseModel):
    session_status: Optional[SessionStatus] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None


class SessionResponse(BaseModel):
    id: str
    investigator_id: str
    witness_name: str
    case_number: str
    incident_type: str
    incident_date: Optional[datetime]
    session_status: SessionStatus
    current_phase: SessionPhase
    total_questions: int
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime
    overall_stress_score: float
    overall_credibility_score: float
    flag_count: int
    notes: Optional[str]
    tags: list[str]


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int
    page: int
    page_size: int


class PhaseAdvanceRequest(BaseModel):
    reason: Optional[str] = None