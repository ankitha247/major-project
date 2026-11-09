"""
Interview WebSocket endpoint.

CLIENT -> SERVER messages (JSON):
  { "type": "witness_response", "text": "..." }
  { "type": "end_interview" }
  { "type": "pong" }

SERVER -> CLIENT messages (JSON):
  { "type": "connected", "session_id": "...", "phase": "rapport" }
  { "type": "ai_question", "question": "...", "phase": "...", "question_number": N }
  { "type": "phase_advanced", "new_phase": "..." }
  { "type": "interview_complete", "summary": { ... } }
  { "type": "stress_alert", "stress_indicator": 0.85 }
  { "type": "error", "message": "..." }
  { "type": "ping", "ts": "..." }
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError

from app.core.security import decode_token
from app.db.repositories.session_repo import SessionRepository
from app.services.ai.question_engine import generate_next_question, generate_phase_opening
from app.services.analysis.flag_engine import get_flag_engine
from app.services.analysis.credibility_scorer import get_credibility_scorer, remove_credibility_scorer
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()

PHASE_QUESTION_LIMITS = {
    "rapport": 2,
    "free_recall": 2,
    "probing": 6,
    "clarification": 4,
    "closure": 2,
}

PHASE_ORDER = [
    "rapport",
    "free_recall",
    "probing",
    "clarification",
    "closure",
]


async def _get_user_id_from_token(token: str) -> str | None:
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except (JWTError, Exception):
        return None


def _build_evidence_context(session: dict) -> str:
    """Build evidence context string from session data for Groq."""
    # Use pre-built context string from OpenCV analysis if available
    if session.get("evidence_context_string"):
        return session["evidence_context_string"]

    # Fall back to NLP-based context (text evidence)
    evidence_context = ""
    if session.get("evidence_nlp"):
        nlp = session["evidence_nlp"]
        parts = []
        if nlp.get("entity_summary"):
            parts.append(f"Entities: {nlp['entity_summary']}")
        if nlp.get("action_verbs"):
            parts.append(f"Actions: {', '.join(nlp['action_verbs'][:5])}")
        if nlp.get("negations"):
            parts.append(f"Negations: {', '.join(nlp['negations'])}")
        if session.get("evidence_description"):
            parts.append(
                f"Scene description: {session['evidence_description'][:300]}"
            )
        evidence_context = "\n".join(parts)
    return evidence_context


@router.websocket("/ws/interview/{session_id}")
async def interview_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
):
    # 1. Authenticate
    user_id = await _get_user_id_from_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # 2. Load and validate session
    repo = SessionRepository()
    session = await repo.get_by_id(session_id)

    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return
    if session["investigator_id"] != user_id:
        await websocket.close(code=4003, reason="Forbidden")
        return
    if session["status"] not in ("pending", "active"):
        await websocket.close(code=4000, reason="Session not available")
        return

    # 3. Build evidence context from session data
    evidence_context = _build_evidence_context(session)

    # 4. Accept and register connection
    await ws_manager.connect_interview(websocket, user_id, session_id)

    # 5. Auto-start if pending
    if session["status"] == "pending":
        session = await repo.update_status(session_id, "active")

    # 6. In-memory transcript for Groq context
    transcript_history: list[dict] = []

    # 7. Send connected message
    await ws_manager.send_to_interview(
        session_id,
        {
            "type": "connected",
            "session_id": session_id,
            "witness_name": session["witness_name"],
            "phase": session["phase"],
            "case_number": session["case_number"],
            "has_evidence": bool(evidence_context),
            "ts": datetime.utcnow().isoformat(),
        },
    )

    # 8. Send opening question using Groq
    opening = await generate_phase_opening(
        phase=session["phase"],
        witness_name=session["witness_name"],
        crime_type=session["crime_type"],
        case_number=session["case_number"],
    )
    transcript_history.append({"speaker": "ai", "text": opening})
    await repo.increment_question_count(session_id)
    await ws_manager.send_to_interview(
        session_id,
        {
            "type": "ai_question",
            "question": opening,
            "phase": session["phase"],
            "question_number": 1,
            "ts": datetime.utcnow().isoformat(),
        },
    )

    # 9. Main loop
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws_manager.send_to_interview(
                    session_id, {"type": "error", "message": "Invalid JSON"}
                )
                continue

            msg_type = msg.get("type")

            if msg_type == "pong":
                continue

            # ---- End interview ----
            if msg_type == "end_interview":
                session = await repo.update_status(session_id, "completed")
                await ws_manager.send_to_interview(
                    session_id,
                    {
                        "type": "interview_complete",
                        "summary": {
                            "total_questions": session["total_questions"],
                            "overall_stress_score": session["overall_stress_score"],
                            "flag_count": session["flags_count"],
                        },
                        "ts": datetime.utcnow().isoformat(),
                    },
                )
                break

            # ---- Witness response ----
            if msg_type == "witness_response":
                witness_text: str = msg.get("text", "").strip()

                # Check empty FIRST
                if not witness_text:
                    await ws_manager.send_to_interview(
                        session_id, {"type": "error", "message": "Empty response"}
                    )
                    continue

                # Check response for flags
                engine = get_flag_engine(session_id)
                response_flags = engine.check_witness_response(witness_text)
                for flag in response_flags:
                    await ws_manager.send_to_interview(session_id, flag.to_dict())

                # Update credibility scorer
                credibility = get_credibility_scorer(session_id)
                has_contradiction = any(
                    f.flag_type == "contradiction" for f in response_flags
                )
                has_avoidance = any(
                    f.flag_type == "topic_avoidance" for f in response_flags
                )
                credibility.add_response(witness_text, has_contradiction, has_avoidance)

                # Save witness response to transcript history
                transcript_history.append({"speaker": "witness", "text": witness_text})

                # Reload session for fresh counts
                session = await repo.get_by_id(session_id)
                current_phase = session["phase"]
                phase_limit = PHASE_QUESTION_LIMITS.get(current_phase, 5)

                # Check if phase limit reached — advance phase
                if session["phase_question_count"] >= phase_limit:
                    current_idx = PHASE_ORDER.index(current_phase)

                    if current_idx < len(PHASE_ORDER) - 1:
                        next_phase = PHASE_ORDER[current_idx + 1]
                        session = await repo.update_phase(session_id, next_phase)

                        await ws_manager.send_to_interview(
                            session_id,
                            {
                                "type": "phase_advanced",
                                "new_phase": next_phase,
                                "message": f"Moving to {next_phase.replace('_', ' ')} phase.",
                                "ts": datetime.utcnow().isoformat(),
                            },
                        )

                        opening = await generate_phase_opening(
                            phase=next_phase,
                            witness_name=session["witness_name"],
                            crime_type=session["crime_type"],
                            case_number=session["case_number"],
                        )
                        transcript_history.append({"speaker": "ai", "text": opening})
                        await repo.increment_question_count(session_id)
                        session = await repo.get_by_id(session_id)

                        await ws_manager.send_to_interview(
                            session_id,
                            {
                                "type": "ai_question",
                                "question": opening,
                                "phase": next_phase,
                                "question_number": session["total_questions"],
                                "ts": datetime.utcnow().isoformat(),
                            },
                        )
                        continue

                    else:
                        # Final phase exhausted — complete interview
                        session = await repo.update_status(session_id, "completed")
                        await ws_manager.send_to_interview(
                            session_id,
                            {
                                "type": "interview_complete",
                                "summary": {
                                    "total_questions": session["total_questions"],
                                    "overall_stress_score": session["overall_stress_score"],
                                    "flag_count": session["flags_count"],
                                },
                                "ts": datetime.utcnow().isoformat(),
                            },
                        )
                        break

                # Normal flow — generate next question with Groq + spaCy NLP
                next_q = await generate_next_question(
                    phase=current_phase,
                    witness_name=session["witness_name"],
                    crime_type=session["crime_type"],
                    case_number=session["case_number"],
                    transcript=transcript_history,
                    latest_witness_response=witness_text,
                    evidence_context=evidence_context,
                )

                # Groq signalled interview is complete
                if next_q is None:
                    session = await repo.update_status(session_id, "completed")
                    await ws_manager.send_to_interview(
                        session_id,
                        {
                            "type": "interview_complete",
                            "summary": {
                                "total_questions": session["total_questions"],
                                "overall_stress_score": session["overall_stress_score"],
                                "flag_count": session["flags_count"],
                            },
                            "ts": datetime.utcnow().isoformat(),
                        },
                    )
                    break

                transcript_history.append({"speaker": "ai", "text": next_q})
                await repo.increment_question_count(session_id)
                session = await repo.get_by_id(session_id)

                await ws_manager.send_to_interview(
                    session_id,
                    {
                        "type": "ai_question",
                        "question": next_q,
                        "phase": current_phase,
                        "question_number": session["total_questions"],
                        "ts": datetime.utcnow().isoformat(),
                    },
                )

    except WebSocketDisconnect:
        logger.info("Interview WS disconnected: session=%s", session_id)
    except Exception as exc:
        logger.exception("Interview WS error: session=%s error=%s", session_id, exc)
        try:
            await ws_manager.send_to_interview(
                session_id, {"type": "error", "message": "Internal server error"}
            )
        except Exception:
            pass
    finally:
        remove_credibility_scorer(session_id)
        await ws_manager.disconnect_interview(session_id)