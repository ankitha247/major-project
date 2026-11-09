from datetime import datetime
from enum import Enum
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, Field


class FlagSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FlagType(str, Enum):
    HIGH_STRESS = "high_stress"
    LONG_PAUSE = "long_pause"
    CONTRADICTION = "contradiction"
    MICRO_EXPRESSION = "micro_expression"
    DECEPTION_INDICATOR = "deception_indicator"
    TOPIC_AVOIDANCE = "topic_avoidance"
    VOICE_TREMOR = "voice_tremor"
    GAZE_AVERSION = "gaze_aversion"


class Flag(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    session_id: str
    transcript_entry_id: Optional[str] = None
    frame_id: Optional[str] = None
    flag_type: FlagType
    severity: FlagSeverity
    description: str
    confidence: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    context_text: Optional[str] = None
    reviewed: bool = False
    reviewer_notes: Optional[str] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}