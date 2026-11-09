from datetime import datetime
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, Field


class EmotionFrame(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    session_id: str
    frame_timestamp: datetime = Field(default_factory=datetime.utcnow)
    frame_number: int
    dominant_emotion: Optional[str] = None
    emotion_scores: dict[str, float] = {}
    face_detected: bool = False
    action_units: dict[str, float] = {}
    gaze_direction: Optional[str] = None
    micro_expression_detected: bool = False
    stress_indicator: float = 0.0
    voice_stress_score: Optional[float] = None
    pitch_mean: Optional[float] = None
    pitch_variance: Optional[float] = None
    speaking_rate: Optional[float] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}