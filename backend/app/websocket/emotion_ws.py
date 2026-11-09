"""
Emotion stream WebSocket endpoint.

CLIENT -> SERVER messages (JSON):
  { "type": "frame", "frame_number": N, "image_base64": "<base64 JPEG>" }
  { "type": "voice_chunk", "chunk_base64": "<base64 PCM>", "sample_rate": 16000 }
  { "type": "pong" }

SERVER -> CLIENT messages (JSON):
  { "type": "connected", "session_id": "..." }
  { "type": "emotion_result", "frame_number": N, "dominant_emotion": "...",
    "emotion_scores": {...}, "face_detected": true, "stress_indicator": 0.4 }
  { "type": "voice_stress_result", "stress_score": 0.3, "pitch_mean": 220.5 }
  { "type": "flag", "flag_type": "high_stress", "severity": "high" }
  { "type": "error", "message": "..." }
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError

from app.core.security import decode_token
from app.db.repositories.session_repo import SessionRepository
from app.services.vision.emotion_detector import analyze_frame
from app.services.audio.voice_stress import analyze_voice_chunk
from app.services.analysis.stress_scorer import get_scorer, remove_scorer
from app.services.analysis.flag_engine import get_flag_engine, remove_flag_engine
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()

STRESS_FLAG_THRESHOLD = 0.75


async def _get_user_id_from_token(token: str) -> str | None:
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except (JWTError, Exception):
        return None


@router.websocket("/ws/emotion/{session_id}")
async def emotion_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
):
    user_id = await _get_user_id_from_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    repo = SessionRepository()
    session = await repo.get_by_id(session_id)

    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return
    if session["investigator_id"] != user_id:
        await websocket.close(code=4003, reason="Forbidden")
        return
    if session["status"] != "active":
        await websocket.close(code=4000, reason="Session not active")
        return

    await ws_manager.connect_emotion(websocket, user_id, session_id)
    await ws_manager.send_to_emotion(
        session_id,
        {
            "type": "connected",
            "session_id": session_id,
            "ts": datetime.utcnow().isoformat(),
        },
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws_manager.send_to_emotion(
                    session_id, {"type": "error", "message": "Invalid JSON"}
                )
                continue

            msg_type = msg.get("type")

            if msg_type == "pong":
                continue

            # ---- Video frame ----
            if msg_type == "frame":
                image_b64: str = msg.get("image_base64", "")
                frame_number: int = msg.get("frame_number", 0)

                if not image_b64:
                    await ws_manager.send_to_emotion(
                        session_id,
                        {"type": "error", "message": "Missing image_base64"},
                    )
                    continue

                # Real DeepFace analysis
                result = analyze_frame(image_b64)

                # Update stress scorer
                scorer = get_scorer(session_id)
                scorer.add_vision_score(result["stress_indicator"])

                # Check flags
                engine = get_flag_engine(session_id)
                flags = engine.check_vision_frame(result)
                for flag in flags:
                    await ws_manager.send_to_emotion(session_id, flag.to_dict())

                # Send emotion result to client
                await ws_manager.send_to_emotion(
                    session_id,
                    {
                        "type": "emotion_result",
                        "frame_number": frame_number,
                        "ts": datetime.utcnow().isoformat(),
                        **result,
                    },
                )

                # Alert interview channel if stress is critical
                if result["stress_indicator"] >= STRESS_FLAG_THRESHOLD:
                    await ws_manager.send_to_interview(
                        session_id,
                        {
                            "type": "stress_alert",
                            "stress_indicator": result["stress_indicator"],
                            "frame_number": frame_number,
                            "ts": datetime.utcnow().isoformat(),
                        },
                    )

            # ---- Voice chunk ----
            elif msg_type == "voice_chunk":
                chunk_b64: str = msg.get("chunk_base64", "")
                sample_rate: int = msg.get("sample_rate", 16000)

                if not chunk_b64:
                    continue

                # Real librosa analysis
                result = analyze_voice_chunk(chunk_b64, sample_rate)

                # Update stress scorer with audio
                scorer = get_scorer(session_id)
                scorer.add_audio_score(result["stress_score"])

                # Check voice flags
                engine = get_flag_engine(session_id)
                flags = engine.check_voice_chunk(result)
                for flag in flags:
                    await ws_manager.send_to_emotion(session_id, flag.to_dict())

                # Send voice result to client
                await ws_manager.send_to_emotion(
                    session_id,
                    {
                        "type": "voice_stress_result",
                        "ts": datetime.utcnow().isoformat(),
                        **result,
                    },
                )

    except WebSocketDisconnect:
        logger.info("Emotion WS disconnected: session=%s", session_id)
    except Exception as exc:
        logger.exception("Emotion WS error: session=%s error=%s", session_id, exc)
    finally:
        # Clean up session-level scorers and engines
        remove_scorer(session_id)
        remove_flag_engine(session_id)
        await ws_manager.disconnect_emotion(session_id)