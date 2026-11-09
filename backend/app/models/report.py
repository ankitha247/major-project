from datetime import datetime
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, Field


class Report(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    session_id: str
    investigator_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    witness_name: str
    case_number: str
    incident_type: str
    duration_seconds: int = 0
    total_questions: int = 0
    overall_stress_score: float = 0.0
    overall_credibility_score: float = 0.0
    emotion_summary: dict[str, float] = {}
    flag_summary: dict[str, int] = {}
    key_entities: dict[str, list[str]] = {}
    transcript_highlights: list[dict] = []
    ai_assessment: Optional[str] = None
    pdf_path: Optional[str] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}