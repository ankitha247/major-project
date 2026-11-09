"""
Credibility scoring service.
Analyzes the full witness transcript and generates:
1. A credibility score 0-100
2. An automatic case summary for investigators
"""

import os
import json
import re
from groq import Groq
from dotenv import load_dotenv
from pathlib import Path

_base = Path(__file__).resolve().parent
load_dotenv(_base / ".env")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", ""), timeout=120.0)
CHAT_MODEL  = "qwen/qwen3.8-27b"


# ── Credibility Score ─────────────────────────────────────────────────────────

def calculate_credibility_score(
    conversation: list,
    scene_analysis: dict,
    contradictions: list,
    crime_type: str,
) -> dict:
    """
    Calculate credibility score 0-100 based on:
    - Consistency of responses
    - Detail level
    - Contradiction count
    - Hedging language
    - Evidence alignment
    """

    # Strip timestamps
    clean_conv = [
        {"role": m["role"], "content": m["content"]}
        for m in conversation
    ]

    witness_responses = [
        m["content"] for m in clean_conv if m["role"] == "user"
    ]

    if not witness_responses:
        return {
            "score":      0,
            "grade":      "N/A",
            "breakdown":  {},
            "summary":    "No witness responses to analyze.",
        }

    full_testimony    = " ".join(witness_responses)
    total_words       = len(full_testimony.split())
    total_responses   = len(witness_responses)

    # ── Rule-based scoring components ────────────────────────────────────────

    # 1. Detail score — longer more detailed responses = more credible
    avg_words = total_words / total_responses if total_responses > 0 else 0
    if avg_words >= 40:
        detail_score = 25
    elif avg_words >= 20:
        detail_score = 18
    elif avg_words >= 10:
        detail_score = 10
    else:
        detail_score = 4

    # 2. Consistency score — penalize contradictions
    contradiction_penalty = min(len(contradictions) * 10, 30)
    consistency_score     = max(0, 25 - contradiction_penalty)

    # 3. Hedging score — penalize vague/evasive language
    hedging_phrases = [
        "i don't know", "i can't remember", "i'm not sure",
        "maybe", "possibly", "i think", "i guess", "kind of",
        "i don't recall", "i forget", "not really sure",
    ]
    hedging_count = sum(
        full_testimony.lower().count(phrase)
        for phrase in hedging_phrases
    )
    if hedging_count == 0:
        hedging_score = 20
    elif hedging_count <= 2:
        hedging_score = 15
    elif hedging_count <= 5:
        hedging_score = 8
    else:
        hedging_score = 2

    # 4. Specificity score — specific details like names, times, locations
    specificity_indicators = [
        "at", "near", "behind", "between", "wearing", "holding",
        "said", "heard", "saw", "felt", "smelled", "o'clock",
        "pm", "am", "street", "road", "floor", "door", "window",
    ]
    specificity_count = sum(
        full_testimony.lower().count(word)
        for word in specificity_indicators
    )
    if specificity_count >= 15:
        specificity_score = 20
    elif specificity_count >= 8:
        specificity_score = 14
    elif specificity_count >= 4:
        specificity_score = 8
    else:
        specificity_score = 3

    # 5. Evidence alignment — does testimony mention things in evidence
    yolo_objects = [d["label"] for d in scene_analysis.get("yolo_detections", [])]
    alignment_count = sum(
        1 for obj in yolo_objects
        if obj.lower() in full_testimony.lower()
    )
    if alignment_count >= 3:
        alignment_score = 10
    elif alignment_count >= 1:
        alignment_score = 6
    else:
        alignment_score = 2

    # ── Total score ───────────────────────────────────────────────────────────
    total = (
        detail_score
        + consistency_score
        + hedging_score
        + specificity_score
        + alignment_score
    )
    total = min(100, max(0, total))

    # ── Grade ─────────────────────────────────────────────────────────────────
    if total >= 80:
        grade = "HIGH"
        grade_color = "green"
    elif total >= 60:
        grade = "MODERATE"
        grade_color = "yellow"
    elif total >= 40:
        grade = "LOW"
        grade_color = "orange"
    else:
        grade = "VERY LOW"
        grade_color = "red"

    return {
        "score": total,
        "grade": grade,
        "grade_color": grade_color,
        "breakdown": {
            "detail_level":        detail_score,
            "consistency":         consistency_score,
            "language_clarity":    hedging_score,
            "specificity":         specificity_score,
            "evidence_alignment":  alignment_score,
        },
        "max_scores": {
            "detail_level":       25,
            "consistency":        25,
            "language_clarity":   20,
            "specificity":        20,
            "evidence_alignment": 10,
        },
        "contradiction_count": len(contradictions),
        "total_responses":     total_responses,
        "avg_response_words":  round(avg_words, 1),
    }


# ── Automatic Case Summary ────────────────────────────────────────────────────

def generate_case_summary(
    conversation: list,
    scene_analysis: dict,
    contradictions: list,
    crime_type: str,
    session_id: str,
    credibility: dict,
) -> str:
    """
    Generate a plain English 1-page case summary for investigators.
    """

    # Strip timestamps
    clean_conv = [
        {"role": m["role"], "content": m["content"]}
        for m in conversation
    ]

    transcript = "\n".join([
        f"{'Q' if m['role'] == 'assistant' else 'A'}: {m['content']}"
        for m in clean_conv
    ])

    scene_summary   = scene_analysis.get("scene_summary", "No scene analysis available.")
    yolo_summary    = scene_analysis.get("yolo_summary", "")
    contradiction_text = "\n".join([
        f"- [{c.get('severity','').upper()}] {c.get('description','')}"
        for c in contradictions
    ]) if contradictions else "None detected."

    prompt = f"""You are a senior forensic investigator writing a case summary report.

CASE ID: {session_id}
CRIME TYPE: {crime_type}
WITNESS CREDIBILITY SCORE: {credibility['score']}/100 ({credibility['grade']})

PHYSICAL EVIDENCE:
{yolo_summary}
{scene_summary}

CONTRADICTIONS DETECTED:
{contradiction_text}

FULL INTERVIEW TRANSCRIPT:
{transcript}

Write a professional 1-page case summary with these exact sections:

## INCIDENT OVERVIEW
2-3 sentences summarizing what happened based on the witness account.

## WITNESS ACCOUNT
Key facts the witness provided — who, what, when, where, how.

## PHYSICAL EVIDENCE FINDINGS
What was detected in the CCTV/crime scene evidence.

## CONTRADICTIONS & CONCERNS
Any inconsistencies between testimony and evidence, or concerning patterns.

## CREDIBILITY ASSESSMENT
Brief assessment of witness credibility based on score of {credibility['score']}/100.

## RECOMMENDED NEXT STEPS
3-5 specific investigative actions the team should take next.

Write in professional forensic language. Be concise and factual."""

    try:
        response = groq_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[WARN] Case summary generation failed: {e}")
        return "Case summary could not be generated."