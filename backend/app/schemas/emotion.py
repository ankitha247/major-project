from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class EmotionFrameRequest(BaseModel):
    session_id: str
    frame_number: int
    image_base64: Optional[str] = None


class EmotionFrameResponse(BaseModel):
    frame_id: str
    dominant_emotion: Optional[str]
    emotion_scores: dict[str, float]
    face_detected: bool
    stress_indicator: float
    micro_expression_detected: bool
    timestamp: datetime


class EmotionTimelineResponse(BaseModel):
    session_id: str
    frames: list[EmotionFrameResponse]
    average_stress: float
    peak_stress_timestamp: Optional[datetime]
    dominant_emotions: dict[str, float]