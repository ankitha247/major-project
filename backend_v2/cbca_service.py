"""
CBCA-inspired Content Analysis Score.
Based on Criteria-Based Content Analysis (Steller & Koehnken, 1989).
Uses LLM to evaluate 19 criteria — each scored 0 or 1.
Called "CBCA-inspired content analysis score" not "credibility score"
to avoid legal and ethical issues.
"""

import os
import json
import re
import logging
from groq import Groq
from dotenv import load_dotenv
from pathlib import Path

_base = Path(__file__).resolve().parent
load_dotenv(_base / ".env")

logger     = logging.getLogger(__name__)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", ""), timeout=120.0)
CHAT_MODEL  = "qwen/qwen3.8-27b"


# ── CBCA Criteria ─────────────────────────────────────────────────────────────
# Based on Steller & Koehnken (1989) and Vrij (2008)

CBCA_CRITERIA = [
    # General characteristics
    {
        "id":          1,
        "category":    "General Characteristics",
        "name":        "Logical Structure",
        "description": "The statement is coherent and logically consistent. Events are described in a way that makes sense.",
    },
    {
        "id":          2,
        "category":    "General Characteristics",
        "name":        "Unstructured Production",
        "description": "The account is not overly organised or rehearsed. Information is provided in a non-scripted, somewhat disorganised way that suggests genuine recall.",
    },
    {
        "id":          3,
        "category":    "General Characteristics",
        "name":        "Quantity of Details",
        "description": "The statement contains a large number of specific details about people, objects, events, times, and places.",
    },
    # Specific contents
    {
        "id":          4,
        "category":    "Specific Contents",
        "name":        "Contextual Embedding",
        "description": "Events are placed in time and space. The witness describes where things happened and when, linking events to a broader context.",
    },
    {
        "id":          5,
        "category":    "Specific Contents",
        "name":        "Descriptions of Interactions",
        "description": "The statement includes descriptions of interactions between people — conversations, physical contact, or exchanges.",
    },
    {
        "id":          6,
        "category":    "Specific Contents",
        "name":        "Reproduction of Conversation",
        "description": "The witness reproduces conversations verbatim or near-verbatim, including what specific people said.",
    },
    {
        "id":          7,
        "category":    "Specific Contents",
        "name":        "Unexpected Complications",
        "description": "The statement includes unexpected elements or complications that arose during the event — things that were not planned or anticipated.",
    },
    {
        "id":          8,
        "category":    "Specific Contents",
        "name":        "Unusual Details",
        "description": "The account contains unusual or unique details that are unlikely to be fabricated because they are too specific or odd.",
    },
    {
        "id":          9,
        "category":    "Specific Contents",
        "name":        "Superfluous Details",
        "description": "The witness includes peripheral details not central to the main event — details that would not typically be invented.",
    },
    {
        "id":          10,
        "category":    "Specific Contents",
        "name":        "Accurately Reported Details Misunderstood",
        "description": "The witness describes details they experienced but did not fully understand at the time — suggesting genuine recall rather than fabrication.",
    },
    {
        "id":          11,
        "category":    "Specific Contents",
        "name":        "Related External Associations",
        "description": "The statement contains references to related events or themes outside the core incident — natural associations a genuine witness would make.",
    },
    {
        "id":          12,
        "category":    "Specific Contents",
        "name":        "Accounts of Subjective Mental State",
        "description": "The witness describes their own feelings, thoughts, or emotions during the event.",
    },
    {
        "id":          13,
        "category":    "Specific Contents",
        "name":        "Attribution of Perpetrator Mental State",
        "description": "The witness attributes thoughts, feelings, or intentions to the perpetrator based on observed behaviour.",
    },
    # Peculiarities of content
    {
        "id":          14,
        "category":    "Peculiarities of Content",
        "name":        "Spontaneous Corrections",
        "description": "The witness spontaneously corrects or clarifies their own statements without being prompted.",
    },
    {
        "id":          15,
        "category":    "Peculiarities of Content",
        "name":        "Admitting Lack of Memory",
        "description": "The witness admits they cannot remember certain details — suggesting honesty rather than fabrication of a complete account.",
    },
    {
        "id":          16,
        "category":    "Peculiarities of Content",
        "name":        "Raising Doubts About Own Testimony",
        "description": "The witness expresses uncertainty about whether their account is accurate — a sign of genuine rather than rehearsed testimony.",
    },
    {
        "id":          17,
        "category":    "Peculiarities of Content",
        "name":        "Self-Deprecation",
        "description": "The witness says something that reflects poorly on themselves but is included anyway — suggesting honesty over fabrication.",
    },
    {
        "id":          18,
        "category":    "Peculiarities of Content",
        "name":        "Pardoning the Perpetrator",
        "description": "The witness makes excuses for or shows understanding toward the perpetrator — atypical for a fabricated account.",
    },
    # Offence-specific elements
    {
        "id":          19,
        "category":    "Offence-Specific Elements",
        "name":        "Details Characteristic of the Offence",
        "description": "The statement includes details that are specific and characteristic of this type of crime — details that a witness who did not experience the event would be unlikely to know.",
    },
]


def compute_cbca_score(
    conversation: list,
    crime_type: str,
    session_id: str,
) -> dict:
    """
    Evaluate full witness testimony against all 19 CBCA criteria.
    Returns scores, breakdown, and interpretation.
    """

    # Strip timestamps, keep only witness responses
    clean_conv = [
        {"role": m["role"], "content": m["content"]}
        for m in conversation
    ]
    witness_responses = [m["content"] for m in clean_conv if m["role"] == "user"]

    if not witness_responses:
        return _empty_cbca_result()

    full_testimony = "\n".join(
        f"Response {i+1}: {r}" for i, r in enumerate(witness_responses)
    )

    # Build criteria list for prompt
    criteria_text = "\n".join([
        f"{c['id']}. [{c['category']}] {c['name']}: {c['description']}"
        for c in CBCA_CRITERIA
    ])

    prompt = f"""You are a forensic psychologist trained in Criteria-Based Content Analysis (CBCA).
Evaluate the following witness testimony for a {crime_type} case against all 19 CBCA criteria.

WITNESS TESTIMONY:
{full_testimony}

CBCA CRITERIA TO EVALUATE:
{criteria_text}

For each criterion, score 1 if present/satisfied, 0 if absent/not satisfied.
Base your evaluation ONLY on what is actually in the testimony — do not infer or assume.

Respond with ONLY a valid JSON object:
{{
  "scores": {{
    "1": 0 or 1,
    "2": 0 or 1,
    "3": 0 or 1,
    "4": 0 or 1,
    "5": 0 or 1,
    "6": 0 or 1,
    "7": 0 or 1,
    "8": 0 or 1,
    "9": 0 or 1,
    "10": 0 or 1,
    "11": 0 or 1,
    "12": 0 or 1,
    "13": 0 or 1,
    "14": 0 or 1,
    "15": 0 or 1,
    "16": 0 or 1,
    "17": 0 or 1,
    "18": 0 or 1,
    "19": 0 or 1
  }},
  "reasoning": {{
    "1": "one sentence explaining why 0 or 1",
    "2": "...",
    "3": "...",
    "4": "...",
    "5": "...",
    "6": "...",
    "7": "...",
    "8": "...",
    "9": "...",
    "10": "...",
    "11": "...",
    "12": "...",
    "13": "...",
    "14": "...",
    "15": "...",
    "16": "...",
    "17": "...",
    "18": "...",
    "19": "..."
  }}
}}"""

    try:
        response = groq_client.chat.completions.create(
            model      = CHAT_MODEL,
            messages   = [{"role": "user", "content": prompt}],
            max_tokens = 2000,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1:
            return _empty_cbca_result()

        result    = json.loads(raw[start:end])
        scores    = result.get("scores", {})
        reasoning = result.get("reasoning", {})

        # Calculate totals by category
        total_score   = sum(int(v) for v in scores.values())
        max_score     = len(CBCA_CRITERIA)
        percentage    = round((total_score / max_score) * 100, 1)

        category_scores = {}
        for c in CBCA_CRITERIA:
            cat  = c["category"]
            cid  = str(c["id"])
            if cat not in category_scores:
                category_scores[cat] = {"score": 0, "max": 0}
            category_scores[cat]["max"]   += 1
            category_scores[cat]["score"] += int(scores.get(cid, 0))

        # Build detailed breakdown
        breakdown = []
        for c in CBCA_CRITERIA:
            cid = str(c["id"])
            breakdown.append({
                "id":          c["id"],
                "category":    c["category"],
                "name":        c["name"],
                "score":       int(scores.get(cid, 0)),
                "reasoning":   reasoning.get(cid, ""),
            })

        # Interpretation
        if percentage >= 70:
            interpretation = "HIGH"
            interpretation_text = (
                "The testimony satisfies a substantial proportion of CBCA criteria, "
                "consistent with genuine witnessed events."
            )
        elif percentage >= 45:
            interpretation = "MODERATE"
            interpretation_text = (
                "The testimony satisfies a moderate proportion of CBCA criteria. "
                "Some indicators of genuine recall are present but the account lacks detail in several areas."
            )
        else:
            interpretation = "LOW"
            interpretation_text = (
                "The testimony satisfies few CBCA criteria. "
                "The account may lack detail or structure consistent with genuine recall. "
                "Further investigation is recommended."
            )

        return {
            "total_score":        total_score,
            "max_score":          max_score,
            "percentage":         percentage,
            "interpretation":     interpretation,
            "interpretation_text": interpretation_text,
            "category_scores":    category_scores,
            "breakdown":          breakdown,
            "method":             "CBCA-inspired Content Analysis (Steller & Koehnken, 1989)",
            "disclaimer":         (
                "This score is a research tool and must not be used as evidence "
                "of truthfulness or deception in legal proceedings."
            ),
        }

    except Exception as e:
        logger.warning(f"[CBCA] Scoring failed: {e}")
        return _empty_cbca_result()


def _empty_cbca_result() -> dict:
    return {
        "total_score":        0,
        "max_score":          19,
        "percentage":         0,
        "interpretation":     "N/A",
        "interpretation_text": "Insufficient testimony to evaluate.",
        "category_scores":    {},
        "breakdown":          [],
        "method":             "CBCA-inspired Content Analysis",
        "disclaimer":         "This score is a research tool only.",
    }