from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class WitnessMessageRequest(BaseModel):
    text: str
    audio_duration_ms: Optional[int] = None
    has_hesitation: bool = False


class AIQuestionResponse(BaseModel):
    question: str
    phase: str
    question_number: int
    reasoning: Optional[str] = None


class TranscriptEntryResponse(BaseModel):
    id: str
    speaker: str
    text: str
    timestamp: datetime
    stress_score: Optional[float]
    hesitation_detected: bool
    keywords_extracted: list[str]


class InterviewStateResponse(BaseModel):
    session_id: str
    current_phase: str
    total_questions: int
    phase_question_count: int
    overall_stress_score: float
    is_complete: bool