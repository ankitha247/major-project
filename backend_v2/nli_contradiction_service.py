"""
NLI-based contradiction detection.
Uses cross-encoder/nli-deberta-v3-base from HuggingFace.
More accurate and explainable than LLM-based detection.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_model = None
_model_error = None


def _get_model():
    global _model, _model_error
    if _model is not None:
        return _model
    if _model_error is not None:
        return None
    try:
        from sentence_transformers import CrossEncoder
        _model = CrossEncoder(
                "cross-encoder/nli-MiniLM2-L6-H768",
                max_length=256,
        )
        logger.info("[NLI] cross-encoder/nli-deberta-v3-base loaded successfully")
        return _model
    except Exception as e:
        logger.warning(f"[NLI] Model load failed: {e} — falling back to Groq")
        _model_error = str(e)
        return None


def detect_contradictions_nli(
    scene_analysis: dict,
    conversation: list,
    confidence_threshold: float = 0.75,
) -> list[dict]:
    """
    Check all witness statements against all evidence findings using NLI.
    Returns contradictions with confidence scores above threshold.

    NLI labels: ENTAILMENT=0, NEUTRAL=1, CONTRADICTION=2
    """
    model = _get_model()

    # Build evidence premises
    evidence_premises = _build_evidence_premises(scene_analysis)
    if not evidence_premises:
        return []

    # Get all witness statements with timestamps
    clean_conv = [
        {"role": m["role"], "content": m["content"],
         "timestamp": m.get("timestamp", "")}
        for m in conversation
    ]
    witness_statements = [
        m for m in clean_conv if m["role"] == "user"
    ]
    if not witness_statements:
        return []

    contradictions = []

    if model:
        # NLI-based detection
        pairs = []
        pair_meta = []

        for stmt in witness_statements:
            for premise in evidence_premises:
                pairs.append([premise["text"], stmt["content"]])
                pair_meta.append({
                    "evidence": premise["text"],
                    "evidence_type": premise["type"],
                    "witness_statement": stmt["content"],
                    "timestamp": stmt.get("timestamp", ""),
                })

        if not pairs:
            return []

        try:
            scores = model.predict(pairs, apply_softmax=True)
            # scores shape: (N, 3) — [entailment, neutral, contradiction]

            for i, (score, meta) in enumerate(zip(scores, pair_meta)):
                contradiction_conf = float(score[2])
                if contradiction_conf >= confidence_threshold:
                    contradictions.append({
                        "type":              "nli_detected",
                        "severity":          _severity_from_confidence(contradiction_conf),
                        "evidence_says":     meta["evidence"],
                        "witness_says":      meta["witness_statement"][:150],
                        "description":       _build_description(meta, contradiction_conf),
                        "confidence":        round(contradiction_conf, 3),
                        "confidence_pct":    f"{contradiction_conf * 100:.1f}%",
                        "evidence_type":     meta["evidence_type"],
                        "timestamp":         meta["timestamp"],
                        "detection_method":  "NLI (cross-encoder/nli-deberta-v3-base)",
                    })

        except Exception as e:
            logger.warning(f"[NLI] Prediction failed: {e} — falling back to Groq")
            return _groq_fallback(scene_analysis, conversation)

    else:
        # Groq fallback when NLI model not available
        return _groq_fallback(scene_analysis, conversation)

    # Sort by confidence descending
    contradictions.sort(key=lambda x: x["confidence"], reverse=True)
    logger.info(f"[NLI] Found {len(contradictions)} contradictions above {confidence_threshold} threshold")
    return contradictions


def check_single_response_nli(
    scene_analysis: dict,
    witness_response: str,
    timestamp: str = "",
    confidence_threshold: float = 0.75,
) -> list[dict]:
    """
    Real-time check of a single witness response against all evidence.
    Called after every witness answer during the interview.
    """
    model = _get_model()
    evidence_premises = _build_evidence_premises(scene_analysis)
    if not evidence_premises:
        return []

    contradictions = []

    if model:
        pairs = [[p["text"], witness_response] for p in evidence_premises]
        try:
            scores = model.predict(pairs, apply_softmax=True)
            for i, (score, premise) in enumerate(zip(scores, evidence_premises)):
                contradiction_conf = float(score[2])
                if contradiction_conf >= confidence_threshold:
                    contradictions.append({
                        "type":              "nli_realtime",
                        "severity":          _severity_from_confidence(contradiction_conf),
                        "evidence_says":     premise["text"],
                        "witness_says":      witness_response[:150],
                        "description":       (
                            f"Witness statement contradicts evidence "
                            f"({contradiction_conf * 100:.1f}% confidence): "
                            f"{premise['text']}"
                        ),
                        "confidence":        round(contradiction_conf, 3),
                        "confidence_pct":    f"{contradiction_conf * 100:.1f}%",
                        "evidence_type":     premise["type"],
                        "timestamp":         timestamp,
                        "detection_method":  "NLI",
                    })
        except Exception as e:
            logger.warning(f"[NLI] Real-time check failed: {e}")
            return _groq_single_fallback(scene_analysis, witness_response)
    else:
        return _groq_single_fallback(scene_analysis, witness_response)

    contradictions.sort(key=lambda x: x["confidence"], reverse=True)
    return contradictions


def _build_evidence_premises(scene_analysis: dict) -> list[dict]:
    """Build a list of evidence premise strings from scene analysis."""
    premises = []

    # YOLO detections
    yolo_detections = scene_analysis.get("yolo_detections", [])
    if yolo_detections:
        labels = [d["label"] for d in yolo_detections]
        label_counts = {}
        for l in labels:
            label_counts[l] = label_counts.get(l, 0) + 1
        for label, count in label_counts.items():
            premises.append({
                "text": f"The crime scene evidence shows {count} {label}(s) present.",
                "type": "yolo_detection",
            })

    # Scene summary
    scene_summary = scene_analysis.get("scene_summary", "")
    if scene_summary:
        premises.append({
            "text": scene_summary,
            "type": "scene_description",
        })

    # Key observations
    for obs in scene_analysis.get("observations", [])[:3]:
        if obs and len(obs) > 10:
            premises.append({
                "text": obs,
                "type": "observation",
            })

    return premises


def _severity_from_confidence(confidence: float) -> str:
    if confidence >= 0.90:
        return "high"
    elif confidence >= 0.80:
        return "medium"
    else:
        return "low"


def _build_description(meta: dict, confidence: float) -> str:
    return (
        f"Evidence ({meta['evidence_type']}) states: \"{meta['evidence'][:80]}\" — "
        f"Witness said: \"{meta['witness_statement'][:80]}\" "
        f"[{confidence * 100:.1f}% contradiction confidence]"
    )


def _groq_fallback(scene_analysis: dict, conversation: list) -> list[dict]:
    """Groq-based contradiction detection as fallback."""
    try:
        import os
        from groq import Groq
        import json
        import re
        from dotenv import load_dotenv
        load_dotenv()

        client    = Groq(api_key=os.getenv("GROQ_API_KEY", ""), timeout=60.0)
        clean_conv = [
            {"role": m["role"], "content": m["content"]}
            for m in conversation
        ]
        witness_text = " ".join(
            m["content"] for m in clean_conv if m["role"] == "user"
        )
        evidence = (
            f"{scene_analysis.get('yolo_summary', '')}. "
            f"{scene_analysis.get('scene_summary', '')}"
        ).strip(". ")

        prompt = f"""Evidence: {evidence}
Witness testimony: {witness_text}

List contradictions as JSON array. Return [] if none.
[{{"type":"...", "severity":"high/medium/low", "evidence_says":"...",
   "witness_says":"...", "description":"...", "confidence":0.8,
   "confidence_pct":"80.0%", "evidence_type":"scene", "timestamp":""}}]"""

        resp = client.chat.completions.create(
            model    = "qwen/qwen3.8-27b",
            messages = [{"role": "user", "content": prompt}],
            max_tokens = 400,
        )
        raw   = resp.choices[0].message.content.strip()
        raw   = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start == -1:
            return []
        result = json.loads(raw[start:end])
        for r in result:
            r["detection_method"] = "Groq LLM (fallback)"
        return result
    except Exception as e:
        logger.warning(f"[Groq fallback] Failed: {e}")
        return []


def _groq_single_fallback(scene_analysis: dict, witness_response: str) -> list[dict]:
    """Groq fallback for single response check."""
    try:
        import os, json, re
        from groq import Groq
        from dotenv import load_dotenv
        load_dotenv()

        client   = Groq(api_key=os.getenv("GROQ_API_KEY", ""), timeout=30.0)
        evidence = (
            f"{scene_analysis.get('yolo_summary', '')}. "
            f"{scene_analysis.get('scene_summary', '')}"
        ).strip(". ")

        prompt = (
            f'Evidence: {evidence}\n'
            f'Witness just said: "{witness_response}"\n'
            f'Does this contradict the evidence? Respond ONLY with JSON:\n'
            f'{{"contradiction":true/false,"description":"...","severity":"high/medium/low","confidence":0.8}}'
        )

        resp = client.chat.completions.create(
            model    = "qwen/qwen3.8-27b",
            messages = [{"role": "user", "content": prompt}],
            max_tokens = 100,
        )
        raw   = resp.choices[0].message.content.strip()
        raw   = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1:
            return []
        result = json.loads(raw[start:end])
        if result.get("contradiction"):
            conf = result.get("confidence", 0.7)
            return [{
                "type":             "groq_realtime",
                "severity":         result.get("severity", "medium"),
                "evidence_says":    evidence[:100],
                "witness_says":     witness_response[:100],
                "description":      result.get("description", "Possible contradiction"),
                "confidence":       conf,
                "confidence_pct":   f"{conf * 100:.1f}%",
                "evidence_type":    "scene",
                "timestamp":        "",
                "detection_method": "Groq LLM (fallback)",
            }]
        return []
    except Exception as e:
        logger.warning(f"[Groq single fallback] Failed: {e}")
        return []