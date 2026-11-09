"""
Builds the full prompt sent to Groq for each question generation.
Includes session context, phase instructions, and conversation history.
"""

from app.services.ai.cognitive_phases import get_phase_config


def build_system_prompt(
    phase: str,
    witness_name: str,
    crime_type: str,
    case_number: str,
) -> str:
    config = get_phase_config(phase)

    tactics_text = "\n".join(f"- {t}" for t in config.tactics)
    forbidden_text = "\n".join(f"- {f}" for f in config.forbidden)

    return f"""You are an expert AI forensic interviewer conducting a cognitive interview with a crime witness.

CASE INFORMATION:
- Witness name: {witness_name}
- Crime type: {crime_type}
- Case number: {case_number}

CURRENT PHASE: {config.name}
PHASE GOAL: {config.goal}

YOUR TACTICS FOR THIS PHASE:
{tactics_text}

STRICT RULES — NEVER VIOLATE THESE:
{forbidden_text}

GENERAL RULES:
- Ask exactly ONE question per response. Never ask two questions at once.
- Keep your question concise and clear — one or two sentences maximum.
- Never repeat a question already asked in this conversation.
- Never suggest possible answers to the witness.
- Never express shock, disbelief, or judgment.
- Respond ONLY with the question itself — no preamble, no explanation, no "certainly" or "of course".
- Do not label your question or explain what phase you are in.
- Sound natural and human, not robotic.
- If the witness seems distressed, acknowledge briefly before asking.
"""


def build_conversation_history(transcript: list[dict]) -> list[dict]:
    """
    Converts stored transcript entries into Groq message format.
    transcript is a list of dicts with keys: speaker, text
    speaker is either 'ai' or 'witness'
    """
    messages = []
    for entry in transcript:
        if entry["speaker"] == "ai":
            messages.append({
                "role": "assistant",
                "content": entry["text"],
            })
        elif entry["speaker"] == "witness":
            messages.append({
                "role": "user",
                "content": entry["text"],
            })
    return messages


def build_full_prompt(
    phase: str,
    witness_name: str,
    crime_type: str,
    case_number: str,
    transcript: list[dict],
    latest_witness_response: str,
) -> list[dict]:
    """
    Builds the complete message list to send to Groq.
    Returns list of messages in OpenAI/Groq format.
    """
    system_prompt = build_system_prompt(
        phase=phase,
        witness_name=witness_name,
        crime_type=crime_type,
        case_number=case_number,
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history so AI knows what was already asked
    history = build_conversation_history(transcript)
    messages.extend(history)

    # Add the latest witness response if not already in history
    if latest_witness_response:
        messages.append({
            "role": "user",
            "content": latest_witness_response,
        })

    return messages