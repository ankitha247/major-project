"""
Contradiction detection service.
Compares witness statements against YOLO26 + Gemini evidence findings.
Uses Groq to identify conflicts between what was seen and what was said.
"""

import os
from groq import Groq
from dotenv import load_dotenv
from pathlib import Path

_base = Path(__file__).resolve().parent
load_dotenv(_base / ".env")

_groq_key = os.getenv("GROQ_API_KEY", "")
groq_client = Groq(api_key=_groq_key, timeout=120.0)
CHAT_MODEL = "qwen/qwen3.8-27b"


def detect_contradictions(
    scene_analysis: dict,
    conversation: list,
) -> list[dict]:

    clean_conversation = [
        {"role": m["role"], "content": m["content"]}
        for m in conversation
    ]

    """
    Compare witness statements against evidence findings.
    Returns list of detected contradictions.
    """
    scene_summary   = scene_analysis.get("scene_summary", "")
    yolo_summary    = scene_analysis.get("yolo_summary", "")
    yolo_detections = scene_analysis.get("yolo_detections", [])
    key_objects     = scene_analysis.get("key_objects", [])
    observations    = scene_analysis.get("observations", [])

    if not scene_summary and not yolo_summary:
        return []

    # Get all witness statements
    witness_statements = [
        m["content"] for m in conversation if m["role"] == "user"
    ]
    if not witness_statements:
        return []

    full_testimony = " ".join(witness_statements)

    # Build evidence summary
    yolo_objects = ", ".join([d["label"] for d in yolo_detections])
    evidence_summary = f"""
YOLO26 detected objects: {yolo_objects if yolo_objects else "none"}
Scene description: {scene_summary}
Key observations: {"; ".join(observations[:5]) if observations else "none"}
"""

    prompt = f"""You are a forensic analyst checking for contradictions between 
physical evidence and witness testimony.

PHYSICAL EVIDENCE (from YOLO26 object detection and Gemini scene analysis):
{evidence_summary}

WITNESS TESTIMONY (everything the witness said):
\"\"\"{full_testimony}\"\"\"

Identify any contradictions between the physical evidence and witness testimony.
A contradiction is when the witness claims something that directly conflicts with 
what was objectively detected in the evidence.

Examples of contradictions:
- Evidence shows 2 people, witness says only 1 person was present
- Evidence shows a knife, witness says no weapons were used
- Evidence shows outdoor scene, witness says it happened indoors
- Evidence shows daytime lighting, witness says it was nighttime

Respond with ONLY a valid JSON array. If no contradictions found, return empty array [].
Format:
[
  {{
    "type": "person_count" | "weapon" | "location" | "lighting" | "object" | "other",
    "severity": "low" | "medium" | "high",
    "evidence_says": "what the evidence shows",
    "witness_says": "what the witness claimed",
    "description": "clear one sentence description of the contradiction",
    "confidence": 0.0 to 1.0
  }}
]

Only include genuine factual contradictions, not minor differences or assumptions.
Return [] if testimony is consistent with evidence."""

    try:
        response = groq_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()

        # Extract JSON array
        import json
        import re
        raw = re.sub(r"```(?:json)?", "", raw).strip().replace("```", "").strip()
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []

        contradictions = json.loads(raw[start:end])
        print(f"[Contradiction] Found {len(contradictions)} contradictions")
        return contradictions

    except Exception as e:
        print(f"[WARN] Contradiction detection failed: {e}")
        return []


def check_single_response(
    scene_analysis: dict,
    witness_response: str,
    conversation_so_far: list,
) -> list[dict]:

    clean_conversation = [
        {"role": m["role"], "content": m["content"]}
        for m in conversation_so_far
    ]


    """
    Check a single witness response for contradictions in real time.
    Faster and lighter than full detection.
    """
    scene_summary = scene_analysis.get("scene_summary", "")
    yolo_summary  = scene_analysis.get("yolo_summary", "")

    if not scene_summary and not yolo_summary:
        return []

    evidence = f"{yolo_summary}. {scene_summary}"

    prompt = f"""Evidence shows: {evidence}

Witness just said: "{witness_response}"

Does this statement directly contradict the physical evidence?
If yes, respond with JSON: {{"contradiction": true, "description": "one sentence", "severity": "low/medium/high"}}
If no contradiction, respond with: {{"contradiction": false}}
Respond with ONLY the JSON object."""

    try:
        response = groq_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
        )
        raw = response.choices[0].message.content.strip()

        import json
        import re
        raw   = re.sub(r"```(?:json)?", "", raw).strip().replace("```", "").strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1:
            return []

        result = json.loads(raw[start:end])
        if result.get("contradiction"):
            return [{
                "type":         "real_time",
                "severity":     result.get("severity", "medium"),
                "description":  result.get("description", "Possible contradiction detected"),
                "evidence_says": evidence[:100],
                "witness_says":  witness_response[:100],
                "confidence":    0.7,
            }]
        return []

    except Exception as e:
        print(f"[WARN] Real-time contradiction check failed: {e}")
        return []