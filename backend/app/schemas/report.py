from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ReportGenerateRequest(BaseModel):
    session_id: str
    include_transcript: bool = True
    include_emotion_timeline: bool = True
    include_flags: bool = True


class ReportResponse(BaseModel):
    id: str
    session_id: str
    witness_name: str
    case_number: str
    incident_type: str
    generated_at: datetime
    duration_seconds: int
    total_questions: int
    overall_stress_score: float
    overall_credibility_score: float
    emotion_summary: dict[str, float]
    flag_summary: dict[str, int]
    key_entities: dict[str, list[str]]
    ai_assessment: Optional[str]
    pdf_url: Optional[str]