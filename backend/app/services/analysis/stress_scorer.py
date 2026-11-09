"""
Stress scorer — aggregates emotion frames and voice chunks
into a rolling stress score for the session.
"""

import logging
from collections import deque

logger = logging.getLogger(__name__)

# How many recent frames to keep for rolling average
ROLLING_WINDOW = 10


class StressScorer:
    """
    Maintains a rolling window of stress scores from both
    vision (DeepFace) and audio (librosa) sources.
    Combines them into a single unified stress score.
    """

    def __init__(self, window_size: int = ROLLING_WINDOW):
        self.window_size = window_size
        self._vision_scores: deque[float] = deque(maxlen=window_size)
        self._audio_scores: deque[float] = deque(maxlen=window_size)
        self._combined_scores: deque[float] = deque(maxlen=window_size)
        self.peak_stress: float = 0.0
        self.total_frames: int = 0

    def add_vision_score(self, stress_indicator: float) -> float:
        """
        Add a stress score from a video frame.
        Returns the current combined stress score.
        """
        self._vision_scores.append(stress_indicator)
        self.total_frames += 1
        return self._update_combined()

    def add_audio_score(self, stress_score: float) -> float:
        """
        Add a stress score from a voice chunk.
        Returns the current combined stress score.
        """
        self._audio_scores.append(stress_score)
        return self._update_combined()

    def _update_combined(self) -> float:
        """
        Combines vision and audio stress scores.
        Vision weighted at 60%, audio at 40%.
        """
        vision_avg = (
            sum(self._vision_scores) / len(self._vision_scores)
            if self._vision_scores else 0.0
        )
        audio_avg = (
            sum(self._audio_scores) / len(self._audio_scores)
            if self._audio_scores else 0.0
        )

        # If only one source available use it fully
        if not self._vision_scores:
            combined = audio_avg
        elif not self._audio_scores:
            combined = vision_avg
        else:
            combined = vision_avg * 0.6 + audio_avg * 0.4

        combined = round(combined, 4)
        self._combined_scores.append(combined)

        # Track peak
        if combined > self.peak_stress:
            self.peak_stress = combined

        return combined

    @property
    def current_score(self) -> float:
        """Most recent combined stress score."""
        if not self._combined_scores:
            return 0.0
        return self._combined_scores[-1]

    @property
    def rolling_average(self) -> float:
        """Rolling average over the window."""
        if not self._combined_scores:
            return 0.0
        return round(sum(self._combined_scores) / len(self._combined_scores), 4)

    @property
    def is_high_stress(self) -> bool:
        return self.current_score >= 0.75

    @property
    def is_moderate_stress(self) -> bool:
        return 0.4 <= self.current_score < 0.75

    def get_summary(self) -> dict:
        return {
            "current_score": self.current_score,
            "rolling_average": self.rolling_average,
            "peak_stress": round(self.peak_stress, 4),
            "total_frames_analyzed": self.total_frames,
            "is_high_stress": self.is_high_stress,
        }


# Session-level store — one StressScorer per active session
_session_scorers: dict[str, StressScorer] = {}


def get_scorer(session_id: str) -> StressScorer:
    """Get or create a StressScorer for a session."""
    if session_id not in _session_scorers:
        _session_scorers[session_id] = StressScorer()
    return _session_scorers[session_id]


def remove_scorer(session_id: str) -> None:
    """Clean up when session ends."""
    _session_scorers.pop(session_id, None)


def get_session_stress_summary(session_id: str) -> dict:
    """Get the full stress summary for a session."""
    scorer = get_scorer(session_id)
    return scorer.get_summary()