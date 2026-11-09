"""
Credibility scorer — rule-based scoring for now.
DistilBERT fine-tuned model will replace this in the Colab training step.

Scores the witness's credibility based on:
- Consistency of responses
- Detail level
- Emotional congruence
- Avoidance patterns
- Contradiction count
"""

import logging
import re

logger = logging.getLogger(__name__)


class CredibilityScorer:
    """
    Rule-based credibility scorer.
    Analyzes the full transcript to produce a credibility score 0.0 to 1.0.

    Higher score = more credible.
    """

    def __init__(self):
        self._response_lengths: list[int] = []
        self._total_responses: int = 0
        self._contradiction_count: int = 0
        self._avoidance_count: int = 0
        self._detail_score: float = 0.0

    def add_response(self, text: str, has_contradiction: bool = False,
                     has_avoidance: bool = False) -> float:
        """
        Process a witness response and update credibility score.
        Returns the current credibility score.
        """
        self._total_responses += 1
        word_count = len(text.split())
        self._response_lengths.append(word_count)

        if has_contradiction:
            self._contradiction_count += 1
        if has_avoidance:
            self._avoidance_count += 1

        # Update detail score based on response length
        # Longer, more detailed responses score higher
        if word_count >= 50:
            self._detail_score += 1.0
        elif word_count >= 20:
            self._detail_score += 0.6
        elif word_count >= 10:
            self._detail_score += 0.3
        else:
            self._detail_score += 0.0

        return self.current_score

    @property
    def current_score(self) -> float:
        """
        Calculate credibility score from 0.0 to 1.0.
        """
        if self._total_responses == 0:
            return 0.5

        # Base score from detail level
        detail_ratio = self._detail_score / self._total_responses
        base_score = detail_ratio * 0.6

        # Penalty for contradictions
        contradiction_penalty = min(self._contradiction_count * 0.15, 0.4)

        # Penalty for avoidance
        avoidance_ratio = self._avoidance_count / self._total_responses
        avoidance_penalty = avoidance_ratio * 0.3

        # Consistency bonus — if response lengths are consistent
        if len(self._response_lengths) > 2:
            avg_length = sum(self._response_lengths) / len(self._response_lengths)
            variance = sum(
                (l - avg_length) ** 2 for l in self._response_lengths
            ) / len(self._response_lengths)
            consistency_bonus = 0.1 if variance < 500 else 0.0
        else:
            consistency_bonus = 0.0

        score = base_score - contradiction_penalty - avoidance_penalty + consistency_bonus
        return round(max(0.0, min(score, 1.0)), 4)

    def get_summary(self) -> dict:
        avg_length = (
            sum(self._response_lengths) / len(self._response_lengths)
            if self._response_lengths else 0
        )
        return {
            "credibility_score": self.current_score,
            "total_responses": self._total_responses,
            "contradiction_count": self._contradiction_count,
            "avoidance_count": self._avoidance_count,
            "average_response_length_words": round(avg_length, 1),
        }


# Session-level store
_session_scorers: dict[str, CredibilityScorer] = {}


def get_credibility_scorer(session_id: str) -> CredibilityScorer:
    """Get or create a CredibilityScorer for a session."""
    if session_id not in _session_scorers:
        _session_scorers[session_id] = CredibilityScorer()
    return _session_scorers[session_id]


def remove_credibility_scorer(session_id: str) -> None:
    """Clean up when session ends."""
    _session_scorers.pop(session_id, None)