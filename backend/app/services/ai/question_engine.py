"""
Question engine — adaptive interview questions using Groq.
Based on the proven approach from the reference implementation:
passes full conversation history directly to Groq so it naturally
avoids repeating questions and builds on previous answers.
"""

import logging
from app.services.ai.groq_client import chat_completion
from app.services.ai.cognitive_phases import get_phase_config
from app.services.nlp.nlp_services import enrich_conversation_context

logger = logging.getLogger(__name__)

INTERVIEW_COMPLETE_SIGNAL = "[INTERVIEW_COMPLETE]"

FALLBACK_QUESTIONS = {
    "rapport": "Thank you for coming in. How long have you lived in this area?",
    "free_recall": "Please continue — what happened next?",
    "probing": "You mentioned some specific details — can you describe the person involved?",
    "clarification": "Can you help me understand the timeline a little better?",
    "closure": "Is there anything else you would like to add?",
}


async def generate_next_question(
    phase: str,
    witness_name: str,
    crime_type: str,
    case_number: str,
    transcript: list[dict],
    latest_witness_response: str,
    evidence_context: str = "",
) -> str | None:
    """
    Generate the next interview question.

    Passes the FULL conversation history to Groq as actual messages
    so Groq naturally avoids repeating questions and builds on context.
    Returns None when Groq signals the interview is complete.
    """
    config = get_phase_config(phase)

    # Run spaCy NLP over all witness answers so far
    nlp_enrichment = enrich_conversation_context(transcript)

    # Build scene context string
    scene_context = ""
    if evidence_context:
        scene_context = f"Evidence from crime scene:\n{evidence_context}\n"

    # Build system prompt
    system_prompt = _build_system_prompt(
        witness_name=witness_name,
        crime_type=crime_type,
        case_number=case_number,
        phase=phase,
        config=config,
        scene_context=scene_context,
        nlp_enrichment=nlp_enrichment,
    )

    # Convert transcript to Groq message format
    # Pass the FULL conversation history — this is the key
    conversation_messages = []
    for entry in transcript:
        role = "assistant" if entry["speaker"] == "ai" else "user"
        conversation_messages.append({
            "role": role,
            "content": entry["text"],
        })

    # Full message list: system + full history
    groq_messages = [
        {"role": "system", "content": system_prompt},
        *conversation_messages,
    ]

    try:
        response = await chat_completion(
            messages=groq_messages,
            temperature=config.temperature,
            max_tokens=256,
        )
        result = response.strip()

        if INTERVIEW_COMPLETE_SIGNAL in result:
            logger.info("Groq signalled interview complete")
            return None

        result = result.strip('"').strip("'")
        logger.info("Generated question: %s", result[:80])
        return result

    except Exception as exc:
        logger.warning("Groq failed, using fallback: %s", exc)
        return FALLBACK_QUESTIONS.get(phase, "Can you tell me more about that?")


def _build_system_prompt(
    witness_name: str,
    crime_type: str,
    case_number: str,
    phase: str,
    config,
    scene_context: str,
    nlp_enrichment: str,
) -> str:
    tactics_text = "\n".join(f"- {t}" for t in config.tactics)

    return f"""You are a professional forensic interviewer trained in the \
Cognitive Interview technique.
You are interviewing {witness_name} for a {crime_type} case (Case: {case_number}).
Current phase: {config.name} — {config.goal}

{scene_context}
{nlp_enrichment}

Rules:
1. Ask exactly ONE focused open-ended question per turn.
2. Build directly on what the witness just said — reference specific details they mentioned.
3. Use NLP-identified entities (people, places, times, objects) as specific follow-up targets.
4. Cover progressively: people seen, physical descriptions, timeline, \
sounds/smells, exact location.
5. Use probing follow-ups for vague answers — never accept "I don't know" without probing.
6. Never lead the witness or suggest answers.
7. Keep tone calm, neutral, professional, and sensitive.
8. NEVER repeat a question already asked in this conversation.
9. NEVER ask "How are you feeling" more than once.
10. NEVER ask generic questions — always be specific to what the witness said.
11. After covering all major areas (roughly 8-12 exchanges), output ONLY: \
{INTERVIEW_COMPLETE_SIGNAL}
    Do NOT output this prematurely — ensure all key details are covered first."""


async def generate_phase_opening(
    phase: str,
    witness_name: str,
    crime_type: str,
    case_number: str,
) -> str:
    phase_openings = {
        "rapport": (
            f"Hello {witness_name}. Thank you for coming in today. "
            "I want you to know this is a safe space and you can speak freely. "
            "How are you feeling?"
        ),
        "free_recall": (
            "Thank you. I'd now like you to tell me, in your own words and "
            "in as much detail as you can remember, everything that happened. "
            "Please don't leave anything out, even if it seems small or unimportant."
        ),
        "probing": (
            "Thank you for sharing that. I'd like to ask you some more specific "
            "questions about what you've described. Take your time with each one."
        ),
        "clarification": (
            "We are nearly done. I just want to make sure I have understood "
            "everything correctly. I may refer back to some things you said earlier."
        ),
        "closure": (
            f"Thank you so much {witness_name}. You have been very helpful. "
            "Before we finish, is there anything else you would like to add "
            "that you feel is important?"
        ),
    }
    return phase_openings.get(phase, "Please continue.")