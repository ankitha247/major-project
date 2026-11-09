"""
Defines the goals, tactics, and constraints for each cognitive interview phase.
This is the forensic psychology knowledge that guides the AI.
"""

from dataclasses import dataclass


@dataclass
class PhaseConfig:
    name: str
    goal: str
    tactics: list[str]
    forbidden: list[str]
    max_questions: int
    temperature: float


PHASE_CONFIGS = {
    "rapport": PhaseConfig(
        name="Rapport Building",
        goal=(
            "Build trust and make the witness comfortable. "
            "Establish a safe, non-threatening environment. "
            "Do not ask about the incident yet.",
            "Do not ask 'How are you feeling today?' more than once — it has already been asked as the opening question",
"Do not ask any variation of 'how are you feeling' again",
        ),
        tactics=[
            "Ask about neutral, comfortable topics like their day or how they are feeling",
            "Use the witness's name naturally",
            "Acknowledge their courage in coming forward",
            "Keep questions open-ended and easy to answer",
            "Show empathy and patience",
        ],
        forbidden=[
            "Do not ask about the crime or incident yet",
            "Do not ask leading questions",
            "Do not express surprise or judgment at any answer",
            "Do not rush the witness",
        ],
        max_questions=3,
        temperature=0.6,
    ),

    "free_recall": PhaseConfig(
        name="Free Recall",
        goal=(
            "Let the witness narrate everything they remember in their own words "
            "without interruption or guidance. Capture the full unfiltered account."
        ),
        tactics=[
            "Ask the witness to tell you everything they remember from start to finish",
            "Encourage them to include even small details that seem unimportant",
            "Do not interrupt — let them speak freely",
            "Ask open-ended follow-ups like 'what happened next?' or 'please continue'",
            "Mentally note topics to probe later but do not probe yet",
        ],
        forbidden=[
            "Do not ask specific questions about details yet",
            "Do not suggest possible answers",
            "Do not correct the witness if something seems inconsistent — note it for later",
            "Do not ask yes/no questions",
        ],
        max_questions=2,
        temperature=0.5,
    ),

    "probing": PhaseConfig(
        name="Probing",
        goal=(
            "Ask targeted questions about specific details from the free recall. "
            "Explore who, what, when, where, and how. Extract maximum detail."
        ),
        tactics=[
            "Focus on one detail at a time",
            "Ask about sensory details — what they saw, heard, smelled, felt",
            "Ask about people involved — appearance, clothing, behaviour, voice",
            "Ask about the environment — lighting, weather, surroundings",
            "Ask about the sequence of events carefully",
            "Use the witness's own words when referencing what they said earlier",
        ],
        forbidden=[
            "Do not suggest answers or lead the witness",
            "Do not ask multiple questions at once",
            "Do not express disbelief",
            "Do not ask why questions — they feel accusatory",
        ],
        max_questions=6,
        temperature=0.7,
    ),

    "clarification": PhaseConfig(
        name="Clarification",
        goal=(
            "Resolve any inconsistencies, gaps, or unclear details from earlier. "
            "Confirm key facts without pressuring the witness."
        ),
        tactics=[
            "Gently reference specific things the witness said earlier",
            "Ask them to help you understand something better",
            "Confirm important details like times, locations, and descriptions",
            "Allow the witness to correct or add to what they said before",
            "Keep tone calm and non-accusatory",
        ],
        forbidden=[
            "Do not confront the witness aggressively about inconsistencies",
            "Do not imply they are lying",
            "Do not repeat a question if they have already answered it clearly",
        ],
        max_questions=4,
        temperature=0.6,
    ),

    "closure": PhaseConfig(
        name="Closure",
        goal=(
            "End the interview professionally. Give the witness a chance to add "
            "anything else. Thank them and explain next steps."
        ),
        tactics=[
            "Ask if there is anything else they want to add",
            "Summarise what you have understood briefly",
            "Thank the witness genuinely for their time and courage",
            "Explain that investigators may follow up if needed",
            "Leave the witness feeling respected and heard",
        ],
        forbidden=[
            "Do not introduce new topics",
            "Do not ask probing questions at this stage",
            "Do not make promises about the investigation outcome",
        ],
        max_questions=2,
        temperature=0.5,
    ),
}


def get_phase_config(phase: str) -> PhaseConfig:
    config = PHASE_CONFIGS.get(phase)
    if not config:
        raise ValueError(f"Unknown phase: {phase}")
    return config