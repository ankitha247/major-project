"""
Emotion detector using DeepFace.
Takes a base64 encoded JPEG frame from the browser webcam
and returns emotion scores + dominant emotion.
"""

import base64
import logging
import tempfile
import os
import numpy as np
from deepface import DeepFace

logger = logging.getLogger(__name__)


def _base64_to_image_array(image_b64: str) -> np.ndarray:
    """Convert base64 JPEG string to numpy array for DeepFace."""
    import cv2

    # Decode base64 to bytes
    image_bytes = base64.b64decode(image_b64)

    # Convert bytes to numpy array
    nparr = np.frombuffer(image_bytes, np.uint8)

    # Decode image
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img


def analyze_frame(image_b64: str) -> dict:
    """
    Analyzes a single webcam frame for emotions.
    Returns emotion scores, dominant emotion, and stress indicator.

    Returns dict with keys:
        face_detected: bool
        dominant_emotion: str
        emotion_scores: dict[str, float]
        stress_indicator: float  (0.0 to 1.0)
        micro_expression_detected: bool
    """
    try:
        img = _base64_to_image_array(image_b64)

        if img is None:
            logger.warning("Could not decode image from base64")
            return _no_face_result()

        # Run DeepFace analysis
        results = DeepFace.analyze(
            img_path=img,
            actions=["emotion"],
            enforce_detection=False,  # Don't crash if no face found
            silent=True,
        )

        # DeepFace returns a list — take the first face
        if not results:
            return _no_face_result()

        result = results[0] if isinstance(results, list) else results

        # Check if face was actually detected
        face_confidence = result.get("face_confidence", 0)
        if face_confidence < 0.5:
            return _no_face_result()

        # Extract emotion scores
        raw_emotions: dict = result.get("emotion", {})

        # Normalize to 0.0-1.0 range (DeepFace returns percentages)
        total = sum(raw_emotions.values()) or 1
        emotion_scores = {
            emotion: round(score / total, 4)
            for emotion, score in raw_emotions.items()
        }

        dominant_emotion: str = result.get("dominant_emotion", "neutral")

        # Calculate stress indicator
        # Fear + anger + disgust are stress indicators
        # Weighted combination
        stress_indicator = round(
            emotion_scores.get("fear", 0) * 0.5
            + emotion_scores.get("angry", 0) * 0.3
            + emotion_scores.get("disgust", 0) * 0.2,
            4,
        )
        stress_indicator = min(stress_indicator, 1.0)

        # Micro expression detected if stress is high but not dominant
        micro_expression_detected = (
            stress_indicator > 0.3
            and dominant_emotion in ("neutral", "happy")
        )

        return {
            "face_detected": True,
            "dominant_emotion": dominant_emotion,
            "emotion_scores": emotion_scores,
            "stress_indicator": stress_indicator,
            "micro_expression_detected": micro_expression_detected,
        }

    except Exception as exc:
        logger.warning("DeepFace analysis failed: %s", exc)
        return _no_face_result()


def _no_face_result() -> dict:
    """Returns a safe default when no face is detected."""
    return {
        "face_detected": False,
        "dominant_emotion": None,
        "emotion_scores": {},
        "stress_indicator": 0.0,
        "micro_expression_detected": False,
    }