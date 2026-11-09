from datetime import datetime
from enum import Enum
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FLAGGED = "flagged"


class SessionPhase(str, Enum):
    RAPPORT = "rapport"
    FREE_RECALL = "free_recall"
    PROBING = "probing"
    CLARIFICATION = "clarification"
    CLOSURE = "closure"


class Session(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    investigator_id: str
    witness_name: str
    case_number: str
    incident_type: str
    incident_date: Optional[datetime] = None
    session_status: SessionStatus = SessionStatus.PENDING
    current_phase: SessionPhase = SessionPhase.RAPPORT
    phase_question_count: int = 0
    total_questions: int = 0
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    video_path: Optional[str] = None
    transcript_path: Optional[str] = None
    overall_stress_score: float = 0.0
    overall_credibility_score: float = 0.0
    flag_count: int = 0
    notes: Optional[str] = None
    tags: list[str] = []

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}