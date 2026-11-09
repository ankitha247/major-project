"""
Flag engine — automatically detects and raises flags during an interview.

Flag types:
- high_stress: stress indicator crosses 0.75
- long_pause: witness takes too long to respond
- contradiction: witness says something inconsistent (keyword based for now)
- micro_expression: stress detected while face shows neutral/happy
- voice_tremor: high pitch variance detected
- topic_avoidance: witness deflects or gives very short answers
"""

import logging
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class FlagType(str, Enum):
    HIGH_STRESS = "high_stress"
    LONG_PAUSE = "long_pause"
    CONTRADICTION = "contradiction"
    MICRO_EXPRESSION = "micro_expression"
    VOICE_TREMOR = "voice_tremor"
    TOPIC_AVOIDANCE = "topic_avoidance"
    GAZE_AVERSION = "gaze_aversion"


class FlagSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Flag:
    def __init__(
        self,
        flag_type: FlagType,
        severity: FlagSeverity,
        description: str,
        confidence: float,
        context: str = "",
    ):
        self.flag_type = flag_type
        self.severity = severity
        self.description = description
        self.confidence = confidence
        self.context = context
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            "type": "flag",
            "flag_type": self.flag_type,
            "severity": self.severity,
            "description": self.description,
            "confidence": round(self.confidence, 3),
            "context": self.context,
            "ts": self.timestamp,
        }


class FlagEngine:
    """
    Detects flags from emotion scores, voice analysis,
    and transcript text.
    """

    # Thresholds
    HIGH_STRESS_THRESHOLD = 0.75
    MODERATE_STRESS_THRESHOLD = 0.5
    VOICE_TREMOR_VARIANCE_THRESHOLD = 3000
    SHORT_ANSWER_WORD_COUNT = 5
    LONG_PAUSE_SECONDS = 8

    # Contradiction keywords — words that signal reversal
    CONTRADICTION_SIGNALS = [
        "actually", "wait", "no i mean", "i meant", "correction",
        "i was wrong", "that's not right", "let me correct",
        "i didn't say", "i never said", "that's not what i said",
    ]

    # Topic avoidance signals
    AVOIDANCE_SIGNALS = [
        "i don't know", "i can't remember", "i don't recall",
        "i'm not sure", "maybe", "i think", "possibly",
        "i don't want to", "can we skip", "i'd rather not",
    ]

    def __init__(self):
        self._flags: list[Flag] = []
        self._last_response_time: datetime = datetime.utcnow()

    def check_vision_frame(self, emotion_result: dict) -> list[Flag]:
        """Check a video frame result for flags."""
        flags = []

        stress = emotion_result.get("stress_indicator", 0.0)
        micro = emotion_result.get("micro_expression_detected", False)
        dominant = emotion_result.get("dominant_emotion", "neutral")
        face_detected = emotion_result.get("face_detected", False)

        # High stress flag
        if stress >= self.HIGH_STRESS_THRESHOLD:
            flag = Flag(
                flag_type=FlagType.HIGH_STRESS,
                severity=FlagSeverity.HIGH,
                description=f"High stress detected (score={stress:.2f})",
                confidence=stress,
            )
            flags.append(flag)
            self._flags.append(flag)

        # Micro expression flag
        if micro and face_detected:
            flag = Flag(
                flag_type=FlagType.MICRO_EXPRESSION,
                severity=FlagSeverity.MEDIUM,
                description=(
                    f"Micro expression detected — stress present "
                    f"while dominant emotion is {dominant}"
                ),
                confidence=stress,
            )
            flags.append(flag)
            self._flags.append(flag)

        return flags

    def check_voice_chunk(self, voice_result: dict) -> list[Flag]:
        """Check a voice analysis result for flags."""
        flags = []

        pitch_variance = voice_result.get("pitch_variance", 0.0)
        stress_score = voice_result.get("stress_score", 0.0)

        # Voice tremor flag
        if pitch_variance >= self.VOICE_TREMOR_VARIANCE_THRESHOLD:
            flag = Flag(
                flag_type=FlagType.VOICE_TREMOR,
                severity=FlagSeverity.MEDIUM,
                description=(
                    f"Voice tremor detected — high pitch variance "
                    f"({pitch_variance:.0f})"
                ),
                confidence=min(pitch_variance / 10000, 1.0),
            )
            flags.append(flag)
            self._flags.append(flag)

        return flags

    def check_witness_response(self, text: str) -> list[Flag]:
        """Check a witness response text for flags."""
        flags = []
        text_lower = text.lower().strip()
        word_count = len(text_lower.split())

        # Update last response time
        self._last_response_time = datetime.utcnow()

        # Topic avoidance — very short answer
        if word_count <= self.SHORT_ANSWER_WORD_COUNT:
            flag = Flag(
                flag_type=FlagType.TOPIC_AVOIDANCE,
                severity=FlagSeverity.LOW,
                description=f"Very short response detected ({word_count} words)",
                confidence=0.5,
                context=text[:100],
            )
            flags.append(flag)
            self._flags.append(flag)

        # Topic avoidance — evasive language
        for signal in self.AVOIDANCE_SIGNALS:
            if signal in text_lower:
                flag = Flag(
                    flag_type=FlagType.TOPIC_AVOIDANCE,
                    severity=FlagSeverity.MEDIUM,
                    description=f"Evasive language detected: '{signal}'",
                    confidence=0.65,
                    context=text[:100],
                )
                flags.append(flag)
                self._flags.append(flag)
                break  # One flag per response

        # Contradiction signals
        for signal in self.CONTRADICTION_SIGNALS:
            if signal in text_lower:
                flag = Flag(
                    flag_type=FlagType.CONTRADICTION,
                    severity=FlagSeverity.HIGH,
                    description=f"Possible contradiction detected: '{signal}'",
                    confidence=0.7,
                    context=text[:100],
                )
                flags.append(flag)
                self._flags.append(flag)
                break

        return flags

    def check_pause(self, seconds_since_last_response: float) -> list[Flag]:
        """Check if witness has paused too long before responding."""
        flags = []
        if seconds_since_last_response >= self.LONG_PAUSE_SECONDS:
            flag = Flag(
                flag_type=FlagType.LONG_PAUSE,
                severity=FlagSeverity.MEDIUM,
                description=(
                    f"Long pause detected — "
                    f"{seconds_since_last_response:.0f}s since last response"
                ),
                confidence=min(seconds_since_last_response / 30, 1.0),
            )
            flags.append(flag)
            self._flags.append(flag)
        return flags

    @property
    def total_flags(self) -> int:
        return len(self._flags)

    def get_flag_summary(self) -> dict:
        summary: dict[str, int] = {}
        for flag in self._flags:
            summary[flag.flag_type] = summary.get(flag.flag_type, 0) + 1
        return summary

    def get_all_flags(self) -> list[dict]:
        return [f.to_dict() for f in self._flags]


# Session-level store — one FlagEngine per active session
_session_engines: dict[str, FlagEngine] = {}


def get_flag_engine(session_id: str) -> FlagEngine:
    """Get or create a FlagEngine for a session."""
    if session_id not in _session_engines:
        _session_engines[session_id] = FlagEngine()
    return _session_engines[session_id]


def remove_flag_engine(session_id: str) -> None:
    """Clean up when session ends."""
    _session_engines.pop(session_id, None)