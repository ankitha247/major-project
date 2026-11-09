"""
Real-time deception indicator detection.
Analyzes witness responses for linguistic patterns associated with deception.
"""

HEDGING_PHRASES = [
    "i think", "i believe", "i guess", "maybe", "possibly",
    "i'm not sure", "i don't know", "i can't remember",
    "i'm not certain", "i forget", "i don't recall",
    "something like that", "more or less", "kind of", "sort of",
]

DISTANCING_PHRASES = [
    "that person", "the individual", "whoever it was",
    "they", "someone", "a person", "somebody",
]

OVERLY_SPECIFIC_PHRASES = [
    "i remember exactly", "i clearly remember", "i know for sure",
    "absolutely", "definitely", "without a doubt", "i'm 100%",
    "i can tell you exactly",
]

AVOIDANCE_PHRASES = [
    "i'd rather not", "can we move on", "do we have to",
    "i already told you", "i said that already", "why do you keep asking",
    "i don't want to talk about", "can you ask something else",
]

CONTRADICTION_SIGNALS = [
    "actually", "wait no", "i mean", "let me correct",
    "that's not what i said", "i didn't say that",
    "i never said", "what i meant was",
]

SCRIPT_SIGNALS = [
    "as i said", "like i said", "as i mentioned",
    "i already explained", "i told you", "i said before",
]


def analyze_response_for_deception(
    witness_response: str,
    response_number: int,
    previous_responses: list,
) -> list:
    """
    Analyze a single witness response for deception indicators.
    Returns list of detected indicators.
    """
    text       = witness_response.lower().strip()
    word_count = len(text.split())
    indicators = []

    # 1. Hedging language
    hedging_found = [p for p in HEDGING_PHRASES if p in text]
    if len(hedging_found) >= 2:
        indicators.append({
            "type":        "hedging",
            "severity":    "medium",
            "title":       "Excessive Hedging",
            "description": f"Multiple uncertain phrases detected: {', '.join(hedging_found[:3])}",
            "emoji":       "🟡",
        })
    elif len(hedging_found) == 1 and response_number > 3:
        indicators.append({
            "type":        "hedging",
            "severity":    "low",
            "title":       "Hedging Language",
            "description": f"Uncertain language detected: '{hedging_found[0]}'",
            "emoji":       "🟡",
        })

    # 2. Distancing language
    distancing_found = [p for p in DISTANCING_PHRASES if p in text]
    if len(distancing_found) >= 2:
        indicators.append({
            "type":        "distancing",
            "severity":    "medium",
            "title":       "Distancing Language",
            "description": "Witness avoids naming or personalizing people involved",
            "emoji":       "🔵",
        })

    # 3. Too short answer
    if word_count <= 4 and response_number > 2:
        indicators.append({
            "type":        "short_answer",
            "severity":    "medium",
            "title":       "Unusually Short Answer",
            "description": f"Only {word_count} words — possible topic avoidance",
            "emoji":       "🔴",
        })

    # 4. Avoidance signals
    avoidance_found = [p for p in AVOIDANCE_PHRASES if p in text]
    if avoidance_found:
        indicators.append({
            "type":        "avoidance",
            "severity":    "high",
            "title":       "Topic Avoidance",
            "description": f"Witness may be avoiding the question: '{avoidance_found[0]}'",
            "emoji":       "🔴",
        })

    # 5. Contradiction signals
    contradiction_found = [p for p in CONTRADICTION_SIGNALS if p in text]
    if contradiction_found:
        indicators.append({
            "type":        "self_contradiction",
            "severity":    "high",
            "title":       "Self Correction Signal",
            "description": f"Witness correcting previous statement: '{contradiction_found[0]}'",
            "emoji":       "🔴",
        })

    # 6. Scripted response
    script_found = [p for p in SCRIPT_SIGNALS if p in text]
    if script_found:
        indicators.append({
            "type":        "scripted",
            "severity":    "medium",
            "title":       "Rehearsed Response",
            "description": f"Response sounds scripted: '{script_found[0]}'",
            "emoji":       "🟠",
        })

    # 7. Overly specific early on
    specific_found = [p for p in OVERLY_SPECIFIC_PHRASES if p in text]
    if specific_found and response_number <= 3:
        indicators.append({
            "type":        "over_specific",
            "severity":    "low",
            "title":       "Overly Certain",
            "description": "Very early certainty can sometimes indicate a prepared story",
            "emoji":       "🟡",
        })

    # 8. Repetition of previous answers
    if previous_responses:
        for prev in previous_responses[-3:]:
            prev_words = set(prev.lower().split())
            curr_words = set(text.split())
            if len(prev_words) > 3 and len(curr_words) > 3:
                overlap = len(prev_words & curr_words) / max(len(curr_words), 1)
                if overlap > 0.7 and word_count > 8:
                    indicators.append({
                        "type":        "repetition",
                        "severity":    "medium",
                        "title":       "Repeated Answer",
                        "description": "This response closely mirrors a previous answer",
                        "emoji":       "🟠",
                    })
                    break

    return indicators