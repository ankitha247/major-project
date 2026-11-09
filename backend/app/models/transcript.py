from datetime import datetime
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, Field


class TranscriptEntry(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    session_id: str
    sequence_number: int
    speaker: str  # "ai" or "witness"
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    audio_start_ms: Optional[int] = None
    audio_end_ms: Optional[int] = None
    emotion_snapshot: Optional[dict] = None
    stress_score: Optional[float] = None
    hesitation_detected: bool = False
    keywords_extracted: list[str] = []

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}