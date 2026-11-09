"""
Real-time emotion analysis endpoint.
Uses DeepFace with VGG-Face backend for better accuracy.
Stores full 7-emotion probability vector per frame.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from deepface import DeepFace
import base64
import numpy as np
import cv2
from datetime import datetime

router = APIRouter(prefix="/emotion", tags=["emotion"])


class FrameRequest(BaseModel):
    image_base64: str
    frame_number: int = 0
    question_context: str = ""  # current AI question being asked


class EmotionResponse(BaseModel):
    face_detected:    bool
    dominant_emotion: str
    emotion_scores:   dict   # full 7-channel vector
    stress_indicator: float
    frame_number:     int
    timestamp:        str
    question_context: str


def _calculate_stress(emotion_scores: dict) -> float:
    fear    = emotion_scores.get("fear",    0) / 100
    angry   = emotion_scores.get("angry",   0) / 100
    disgust = emotion_scores.get("disgust", 0) / 100
    sad     = emotion_scores.get("sad",     0) / 100
    stress  = (fear * 0.4) + (angry * 0.3) + (disgust * 0.15) + (sad * 0.15)
    return round(min(stress, 1.0), 4)


@router.post("/analyze-frame", response_model=EmotionResponse)
async def analyze_frame(payload: FrameRequest):
    timestamp = datetime.utcnow().isoformat()
    try:
        image_bytes = base64.b64decode(payload.image_base64)
        nparr       = np.frombuffer(image_bytes, np.uint8)
        img         = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise HTTPException(status_code=400, detail="Could not decode image")

        # Upscale for better detection
        h, w = img.shape[:2]
        if w < 480:
            scale = 480 / w
            img   = cv2.resize(img, (int(w * scale), int(h * scale)))

        # Use VGG-Face backend for better accuracy
        results = DeepFace.analyze(
            img_path          = img,
            actions           = ["emotion"],
            enforce_detection = False,
            silent            = True,
            detector_backend  = "opencv",
        )

        result = results[0] if isinstance(results, list) else results

        face_confidence = result.get("face_confidence", 0)
        if face_confidence < 0.1:
            return EmotionResponse(
                face_detected    = False,
                dominant_emotion = "none",
                emotion_scores   = {},
                stress_indicator = 0.0,
                frame_number     = payload.frame_number,
                timestamp        = timestamp,
                question_context = payload.question_context,
            )

        emotion_scores   = result.get("emotion", {})
        dominant_emotion = result.get("dominant_emotion", "neutral")
        stress_indicator = _calculate_stress(emotion_scores)

        return EmotionResponse(
            face_detected    = True,
            dominant_emotion = dominant_emotion,
            emotion_scores   = emotion_scores,
            stress_indicator = stress_indicator,
            frame_number     = payload.frame_number,
            timestamp        = timestamp,
            question_context = payload.question_context,
        )

    except Exception as e:
        return EmotionResponse(
            face_detected    = False,
            dominant_emotion = "none",
            emotion_scores   = {},
            stress_indicator = 0.0,
            frame_number     = payload.frame_number,
            timestamp        = timestamp,
            question_context = payload.question_context,
        )


@router.post("/session-stats")
async def compute_session_stats(payload: dict):
    """
    Compute statistical measures from stored emotion log.
    Input: {"frames": [{emotion_scores, stress_indicator, timestamp, question_context}]}
    """
    frames = payload.get("frames", [])
    if not frames:
        return {"error": "No frames provided"}

    stress_values = [f["stress_indicator"] for f in frames if f.get("face_detected")]
    if not stress_values:
        return {"mean_stress": 0, "peak_stress": 0, "variance": 0}

    mean_stress  = round(sum(stress_values) / len(stress_values), 4)
    peak_stress  = round(max(stress_values), 4)
    variance     = round(
        sum((s - mean_stress) ** 2 for s in stress_values) / len(stress_values), 4
    )
    peak_index   = stress_values.index(peak_stress)
    peak_frame   = frames[peak_index]

    # Group stress by question context
    question_stress = {}
    for f in frames:
        ctx = f.get("question_context", "unknown")
        if ctx not in question_stress:
            question_stress[ctx] = []
        if f.get("face_detected"):
            question_stress[ctx].append(f["stress_indicator"])

    question_avg_stress = {
        q: round(sum(v) / len(v), 4)
        for q, v in question_stress.items()
        if v
    }

    return {
        "mean_stress":          mean_stress,
        "peak_stress":          peak_stress,
        "variance":             variance,
        "peak_at_question":     peak_frame.get("question_context", ""),
        "peak_timestamp":       peak_frame.get("timestamp", ""),
        "total_frames":         len(frames),
        "frames_with_face":     len(stress_values),
        "question_avg_stress":  question_avg_stress,
    }