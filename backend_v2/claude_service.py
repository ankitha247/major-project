"""
claude_service.py
AI interactions — YOLO26 + Gemini Vision for images/video, Groq for interview + report.
Uses the new google-genai SDK (replaces deprecated google.generativeai).
"""

import os
import base64
import json
import re
import cv2
import tempfile
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

_base = Path(__file__).resolve().parent
load_dotenv(_base / ".env")
load_dotenv(_base.parent / ".env")

from groq import Groq
from ultralytics import YOLO as YOLOModel
from nlp_service import analyze_text as nlp_analyze, enrich_conversation_context

# ── Groq client ───────────────────────────────────────────────────────────────
_groq_key = os.getenv("GROQ_API_KEY", "")
if not _groq_key:
    print("[ERROR] GROQ_API_KEY is not set.")
else:
    print(f"[INFO] GROQ_API_KEY loaded (starts with: {_groq_key[:8]}...)")

groq_client = Groq(api_key=_groq_key, timeout=120.0)
CHAT_MODEL = "qwen/qwen3.8-27b"

# ── Gemini client (new google-genai SDK) ──────────────────────────────────────
_gemini_key    = os.getenv("GEMINI_API_KEY", "")
_gemini_client = None

if _gemini_key:
    try:
        import google.genai
        _gemini_client = google.genai.Client(api_key=_gemini_key)
        print("[INFO] Gemini client initialized (google-genai SDK, gemini-1.5-flash)")
    except Exception as e:
        print(f"[WARN] Gemini init failed: {e}")
else:
    print("[WARN] GEMINI_API_KEY not set — using OpenCV + YOLO26 fallback")

GEMINI_MODEL = "gemini-2.0-flash"

# ── YOLO26 model ──────────────────────────────────────────────────────────────
_yolo_model = None


def get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        try:
            _yolo_model = YOLOModel("yolo26n.pt")
            print("[INFO] YOLO26n model loaded successfully")
        except Exception as e:
            print(f"[WARN] YOLO26 load failed: {e}")
            _yolo_model = False
    return _yolo_model if _yolo_model else None


def run_yolo_on_image(image_bytes: bytes) -> dict:
    """Run YOLO26 object detection on image bytes."""
    model = get_yolo_model()
    if not model:
        return {"detections": [], "summary": "", "person_count": 0}

    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"detections": [], "summary": "", "person_count": 0}

        results      = model(img, verbose=False)
        detections   = []
        person_count = 0

        for result in results:
            for box in result.boxes:
                label      = model.names[int(box.cls)]
                confidence = float(box.conf)
                if confidence > 0.4:
                    detections.append({
                        "label":      label,
                        "confidence": round(confidence, 2),
                    })
                    if label == "person":
                        person_count += 1

        if detections:
            label_counts = {}
            for d in detections:
                label_counts[d["label"]] = label_counts.get(d["label"], 0) + 1
            parts   = [f"{count} {label}(s)" for label, count in label_counts.items()]
            summary = "YOLO26 detected: " + ", ".join(parts)
        else:
            summary = "YOLO26 detected no significant objects"

        print(f"[YOLO26] {summary}")
        return {
            "detections":   detections,
            "summary":      summary,
            "person_count": person_count,
        }

    except Exception as e:
        print(f"[WARN] YOLO26 detection failed: {e}")
        return {"detections": [], "summary": "", "person_count": 0}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    text  = re.sub(r"```(?:json)?", "", text).strip().replace("```", "").strip()
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in:\n{text[:300]}")
    return json.loads(text[start:end])


def _gemini_generate(prompt: str, image_bytes: bytes, mime: str) -> str:
    """Call Gemini with image using new google-genai SDK."""
    import google.genai
    import google.genai.types as t
    response = _gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            prompt,
            t.Part.from_bytes(data=image_bytes, mime_type=mime),
        ],
    )
    return response.text


def _extract_video_frames(video_bytes: bytes, num_frames: int = 6) -> list:
    """Extract evenly-spaced frames from video bytes."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = tmp.name

    frames = []
    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            raise ValueError("Could not open video file.")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps          = cap.get(cv2.CAP_PROP_FPS) or 25
        print(f"[Video] total={total_frames}, fps={fps:.1f}, duration={total_frames/fps:.1f}s")

        margin  = max(1, int(total_frames * 0.05))
        usable  = total_frames - 2 * margin
        step    = max(1, usable // num_frames)
        indices = [margin + i * step for i in range(num_frames)]

        for frame_num, idx in enumerate(indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue
            _, buf     = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            jpeg_bytes = buf.tobytes()
            timestamp  = round(idx / fps, 2)
            frames.append({
                "frame_num":     frame_num + 1,
                "frame_index":   idx,
                "jpeg_bytes":    jpeg_bytes,
                "timestamp_sec": timestamp,
            })
            print(f"[Video] Frame {frame_num+1} @ {timestamp}s extracted")

        cap.release()
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    return frames


def _opencv_analyze_image(image_bytes: bytes) -> dict:
    """Fallback OpenCV analysis when Gemini is unavailable."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {
            "face_count": 0,
            "lighting":   "unknown",
            "scene_type": "unknown",
            "summary":    "Could not analyze image.",
        }

    h, w  = img.shape[:2]
    gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    faces        = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
    face_count   = len(faces)

    brightness = float(np.mean(gray))
    if brightness < 50:
        lighting = "very dark / night scene"
    elif brightness < 100:
        lighting = "dimly lit"
    elif brightness < 180:
        lighting = "moderately lit"
    else:
        lighting = "well lit / bright"

    hsv        = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    green      = float(np.sum(cv2.inRange(hsv, (35,40,40), (85,255,255)) > 0)) / (h*w)
    sky        = float(np.sum(cv2.inRange(hsv, (90,50,150), (130,255,255)) > 0)) / (h*w)
    scene_type = "outdoor" if green > 0.2 or sky > 0.15 else "indoor"

    summary = (
        f"{face_count} person(s) detected. "
        f"Scene appears {scene_type} with {lighting} lighting. "
        f"Resolution: {w}x{h}."
    )
    return {
        "face_count": face_count,
        "lighting":   lighting,
        "scene_type": scene_type,
        "summary":    summary,
    }


# ── Image Analysis ────────────────────────────────────────────────────────────

def analyze_image(image_bytes: bytes, crime_type: str, filename: str = "image.jpg") -> dict:
    """
    YOLO26 detects objects + Gemini Vision describes scene.
    Combined context gives richer interview questions.
    """
    ext  = Path(filename).suffix.lower()
    mime = {
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")

    # Step 1 — YOLO26 object detection
    yolo_result       = run_yolo_on_image(image_bytes)
    yolo_summary      = yolo_result["summary"]
    yolo_detections   = yolo_result["detections"]
    yolo_person_count = yolo_result["person_count"]

    # Step 2 — Build YOLO context for Gemini
    yolo_context = ""
    if yolo_detections:
        det_list     = ", ".join(
            f"{d['label']} ({d['confidence']*100:.0f}%)"
            for d in yolo_detections[:10]
        )
        yolo_context = (
            f"\n\nYOLO26 Pre-Analysis detected these objects:\n{det_list}\n"
            f"Use these detections to guide and validate your analysis."
        )

    # Step 3 — Gemini Vision for full scene description
    prompt = f"""You are an experienced forensic scene analyst.
A {crime_type} case is being investigated.

Carefully examine this image (CCTV still, crime scene photo, or security camera footage).
{yolo_context}

Respond with ONLY a valid JSON object — no extra text, no markdown fences:

{{
  "scene_summary": "2-3 sentence factual description incorporating both visual analysis and YOLO26 detections",
  "key_objects": ["all", "detected", "objects", "people", "vehicles", "weapons"],
  "observations": ["notable", "forensic", "details", "about", "the", "scene"],
  "crime_indicators": ["elements", "that", "relate", "to", "the", "{crime_type}", "crime"],
  "first_question": "The single most important opening question to ask the witness"
}}

Be specific about people (clothing, appearance, actions), vehicles, weapons, and locations.
Always analyze — never refuse."""

    # Try Gemini with new SDK
    if _gemini_client:
        try:
            raw = _gemini_generate(prompt, image_bytes, mime)
            print(f"[Gemini/Image] {raw[:200]}")

            try:
                result = _extract_json(raw)
            except (ValueError, json.JSONDecodeError):
                result = {
                    "scene_summary":    raw[:400] if raw else "Image analyzed.",
                    "key_objects":      [d["label"] for d in yolo_detections],
                    "observations":     [raw[:200]] if raw else [],
                    "crime_indicators": [],
                    "first_question":   (
                        f"Can you describe what you witnessed during "
                        f"this {crime_type} incident?"
                    ),
                }

            # Merge YOLO into result
            result["yolo_detections"]   = yolo_detections
            result["yolo_summary"]      = yolo_summary
            result["yolo_person_count"] = yolo_person_count
            result["input_type"]        = "image"

            existing    = result.get("key_objects", [])
            yolo_labels = [d["label"] for d in yolo_detections]
            for label in yolo_labels:
                if label not in existing:
                    existing.append(label)
            result["key_objects"] = existing

            return result

        except Exception as e:
            print(f"[WARN] Gemini failed: {e} — using OpenCV + YOLO26 fallback")

    # Fallback — OpenCV + YOLO26 only
    print("[OpenCV+YOLO26] Using fallback analysis")
    opencv           = _opencv_analyze_image(image_bytes)
    combined_context = f"{yolo_summary}. {opencv['summary']}"

    try:
        resp = groq_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content":
                f"Crime: {crime_type}. Scene findings: {combined_context}. "
                f"Generate ONE important opening question for the witness. "
                f"Just the question."}],
            max_tokens=80,
        )
        first_q = resp.choices[0].message.content.strip()
    except Exception:
        first_q = (
            f"Can you describe what you witnessed during this {crime_type} incident?"
        )

    return {
        "scene_summary":    combined_context,
        "key_objects":      [d["label"] for d in yolo_detections] + [opencv["scene_type"]],
        "observations":     [yolo_summary, opencv["summary"]],
        "crime_indicators": [f"Scene analyzed for {crime_type}"],
        "first_question":   first_q,
        "yolo_detections":  yolo_detections,
        "yolo_summary":     yolo_summary,
        "yolo_person_count": yolo_person_count,
        "input_type":       "image",
    }


# ── Video Analysis ────────────────────────────────────────────────────────────

def analyze_video(video_bytes: bytes, crime_type: str, filename: str = "video.mp4") -> dict:
    """Extract frames → YOLO26 + Gemini Vision per frame → Groq synthesis."""
    print(f"[Video] Analyzing {filename}, {len(video_bytes)} bytes")

    frames = _extract_video_frames(video_bytes, num_frames=6)
    if not frames:
        return {
            "scene_summary":      "Could not extract frames.",
            "key_objects":        [],
            "observations":       ["Video could not be processed."],
            "crime_indicators":   [],
            "first_question":     "Can you describe what you witnessed?",
            "input_type":         "video",
            "frames_analyzed":    0,
            "frame_results":      [],
            "frame_descriptions": [],
        }

    frame_results      = []
    frame_descriptions = []

    for f in frames:
        frame_num  = f["frame_num"]
        jpeg_bytes = f["jpeg_bytes"]
        timestamp  = f["timestamp_sec"]
        print(f"[Video] Processing frame {frame_num}/{len(frames)} @ {timestamp}s")

        # YOLO26 on this frame
        yolo_frame         = run_yolo_on_image(jpeg_bytes)
        yolo_frame_summary = yolo_frame["summary"]
        print(f"[YOLO26/Video] Frame {frame_num}: {yolo_frame_summary}")

        description = f"Frame {frame_num} at {timestamp}s: {yolo_frame_summary}"

        # Gemini for richer frame description
        if _gemini_client:
            try:
                frame_prompt = f"""You are a forensic analyst reviewing frame {frame_num} of {len(frames)}
from a {crime_type} incident video (timestamp: {timestamp}s).

YOLO26 pre-detection for this frame: {yolo_frame_summary}

Describe what you observe incorporating the YOLO26 detections:
- The scene, location, and environment
- All people visible (appearance, clothing, actions, position)
- All vehicles and objects of interest
- Any notable actions or events occurring

Be specific, factual, and 3-5 sentences."""

                description = _gemini_generate(frame_prompt, jpeg_bytes, "image/jpeg")
                description = description.strip()
                print(f"[Gemini/Video] Frame {frame_num} → {description[:80]}...")
            except Exception as e:
                print(f"[WARN] Gemini frame {frame_num} failed: {e} — using YOLO26 only")

        nlp_result = nlp_analyze(description)

        frame_results.append({
            "frame_num":       frame_num,
            "timestamp_sec":   timestamp,
            "jpeg_b64":        base64.standard_b64encode(jpeg_bytes).decode(),
            "description":     description,
            "yolo_detections": yolo_frame["detections"],
            "yolo_summary":    yolo_frame_summary,
            "nlp_entities":    nlp_result["entities"],
            "nlp_summary":     nlp_result["entity_summary"],
        })
        frame_descriptions.append(f"Frame {frame_num} ({timestamp}s): {description}")

    # Groq synthesis
    synthesis_prompt = f"""You are a senior forensic analyst.
Below are descriptions of {len(frames)} evenly-spaced frames from a {crime_type} incident video.
Each frame was analyzed by YOLO26 object detection and Gemini Vision.

{chr(10).join(frame_descriptions)}

Respond with ONLY a valid JSON object — no extra text, no markdown:

{{
  "scene_summary": "2-3 sentence overall summary of the full video sequence",
  "key_objects": ["all", "significant", "objects", "people", "vehicles", "observed"],
  "observations": ["key", "patterns", "and", "details", "across", "all", "frames"],
  "crime_indicators": ["elements", "that", "confirm", "the", "crime", "type"],
  "first_question": "The most important opening question for the witness based on all frames"
}}"""

    try:
        synth_resp = groq_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": synthesis_prompt}],
            max_tokens=1024,
        )
        result = _extract_json(synth_resp.choices[0].message.content)
    except Exception as e:
        print(f"[WARN] Synthesis failed: {e}")
        result = {
            "scene_summary":    " ".join(
                d.split(": ", 1)[-1] for d in frame_descriptions[:2]
            ),
            "key_objects":      [],
            "observations":     frame_descriptions,
            "crime_indicators": [],
            "first_question":   "Can you describe what you saw in the video footage?",
        }

    result["input_type"]          = "video"
    result["frames_analyzed"]     = len(frames)
    result["frame_results"]       = frame_results
    result["frame_descriptions"]  = frame_descriptions
    return result


# ── Text Analysis ─────────────────────────────────────────────────────────────

def analyze_text(text_input: str, crime_type: str) -> dict:
    """spaCy NLP → Groq with entity context injected."""
    print(f"[Text] Analyzing {len(text_input)} chars")

    nlp_result  = nlp_analyze(text_input)
    nlp_context = nlp_result["context_enrichment"]

    prompt = f"""You are an experienced forensic scene analyst.
A {crime_type} case is being investigated.

The witness/officer provided this written description:
\"\"\"{text_input}\"\"\"

NLP Pre-Analysis (spaCy):
{nlp_context if nlp_context else "No named entities detected."}

Respond with ONLY a valid JSON object:

{{
  "scene_summary": "2-3 sentence factual summary integrating text and NLP findings",
  "key_objects": ["items", "people", "locations", "from", "text", "and", "NLP"],
  "observations": ["notable", "details", "including", "NLP", "entities", "found"],
  "crime_indicators": ["elements", "related", "to", "the", "crime", "type"],
  "first_question": "The most important follow-up question for the witness"
}}"""

    response = groq_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    raw = response.choices[0].message.content
    print(f"[Text/Groq] {raw[:200]}")

    try:
        result = _extract_json(raw)
    except (ValueError, json.JSONDecodeError):
        result = {
            "scene_summary":    text_input[:300],
            "key_objects":      [],
            "observations":     [],
            "crime_indicators": [],
            "first_question":   "Can you elaborate on what you witnessed?",
        }

    result["input_type"]          = "text"
    result["original_text_input"] = text_input
    result["nlp"] = {
        "entities":        nlp_result["entities"],
        "entity_summary":  nlp_result["entity_summary"],
        "noun_phrases":    nlp_result["noun_phrases"],
        "action_verbs":    nlp_result["action_verbs"],
        "negations":       nlp_result["negations"],
        "spacy_available": nlp_result["spacy_available"],
    }
    return result


# ── Interview ─────────────────────────────────────────────────────────────────
def get_next_question(conversation: list, scene_context: str, crime_type: str) -> str:
    """Adaptive interview question with spaCy NLP enrichment."""
    nlp_enrichment = enrich_conversation_context(conversation)

    # Strip timestamps before sending to Groq — Groq only accepts role and content
    clean_conversation = [
        {"role": m["role"], "content": m["content"]}
        for m in conversation
    ]

    system_prompt = f"""You are a professional forensic interviewer trained in the
Cognitive Interview technique. You are interviewing a witness for a {crime_type} case.

Scene context from YOLO26 + Gemini analysis:
{scene_context}
{nlp_enrichment}

Rules:
1. Ask exactly ONE focused open-ended question per turn.
2. Build directly on what the witness just said.
3. Use NLP-identified entities (people, places, times) as specific follow-up targets.
4. Cover progressively: people seen, timeline, physical descriptions, sounds, location.
5. Use probing follow-ups for vague answers.
6. Never lead the witness or suggest answers.
7. Keep tone calm, neutral, professional.
8. NEVER repeat a question already asked in this conversation.
9. NEVER ask "How are you feeling" more than once.
10. NEVER ask generic questions — always be specific to what the witness said.
11. After covering all major areas (roughly 8-12 exchanges), output ONLY:
    [INTERVIEW_COMPLETE]
    Do NOT output this prematurely."""

    response = groq_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": system_prompt}, *clean_conversation],
        max_tokens=100,
    )
    return response.choices[0].message.content.strip()



# ── Report ────────────────────────────────────────────────────────────────────

def generate_report(
    scene_analysis: dict,
    conversation: list,
    crime_type: str,
    session_id: str,
) -> str:
    """Generate structured forensic report."""
    input_type = scene_analysis.get("input_type", "image")

    # YOLO section
    yolo_summary    = scene_analysis.get("yolo_summary", "")
    yolo_detections = scene_analysis.get("yolo_detections", [])
    yolo_section    = ""
    if yolo_summary:
        det_list     = ", ".join(
            f"{d['label']} ({d['confidence']*100:.0f}%)"
            for d in yolo_detections[:10]
        )
        yolo_section = f"YOLO26 Detection: {yolo_summary}\nDetailed: {det_list}"

    if input_type == "video":
        frames_n      = scene_analysis.get("frames_analyzed", 0)
        frame_descs   = scene_analysis.get("frame_descriptions", [])
        input_section = (
            f"Input Type     : Video footage\n"
            f"Frames Analyzed: {frames_n}\n\n"
            f"Per-Frame Analysis:\n"
            + ("\n".join(frame_descs) if frame_descs else "Not available.")
        )
        nlp_section = "NLP analysis applied per frame."
    elif input_type == "text":
        original_text = scene_analysis.get("original_text_input", "Not available.")
        nlp_data      = scene_analysis.get("nlp", {})
        input_section = (
            f"Input Type     : Text description\n\n"
            f"Original Description:\n\"\"\"{original_text}\"\"\""
        )
        nlp_section = nlp_data.get("entity_summary", "No NLP data available.")
        if nlp_data.get("action_verbs"):
            nlp_section += f"\nActions: {', '.join(nlp_data['action_verbs'][:8])}"
        if nlp_data.get("negations"):
            nlp_section += f"\nNegations: {', '.join(nlp_data['negations'])}"
    else:
        input_section = "Input Type     : Image / photograph"
        nlp_section   = "NLP analysis applied to witness interview answers."

    all_witness_text      = " ".join(
        m["content"] for m in conversation if m["role"] == "user"
    )
    interview_nlp         = nlp_analyze(all_witness_text) if all_witness_text else {}
    interview_nlp_summary = (
        interview_nlp.get("entity_summary", "")
        if interview_nlp.get("spacy_available") else ""
    )
    negations_in_interview = interview_nlp.get("negations", []) if interview_nlp else []

    transcript = "\n\n".join([
        f"{'Interviewer' if m['role'] == 'assistant' else 'Witness'}: {m['content']}"
        for m in conversation
    ])

    prompt = f"""You are a senior forensic report writer. Generate a formal investigation report.

=== CASE METADATA ===
Case ID    : {session_id}
Crime Type : {crime_type}

=== EVIDENCE INPUT ===
{input_section}

=== YOLO26 OBJECT DETECTION ===
{yolo_section if yolo_section else "YOLO26 analysis not available."}

=== NLP ANALYSIS (spaCy) ===
{nlp_section}
Interview NLP summary: {interview_nlp_summary if interview_nlp_summary else "N/A"}
Witness negations    : {", ".join(negations_in_interview) if negations_in_interview else "None detected"}

=== SCENE ANALYSIS ===
Summary     : {scene_analysis.get("scene_summary", "N/A")}
Key Objects : {", ".join(scene_analysis.get("key_objects", []))}
Observations: {"; ".join(scene_analysis.get("observations", []))}
Indicators  : {"; ".join(scene_analysis.get("crime_indicators", []))}

=== WITNESS INTERVIEW TRANSCRIPT ===
{transcript}

=== REQUIRED SECTIONS (use ## for each header) ===
## Case Summary
## Evidence Input
## YOLO26 Object Detection Results
## NLP Analysis of Witness Statements
## Scene Description
## Physical Evidence Identified
## Witness Statement Summary
## Persons / Vehicles Described
## Timeline of Events
## Inconsistencies or Gaps
## Investigator Recommendations

Be factual, concise, and objective. Use professional forensic language."""

    response = groq_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    return response.choices[0].message.content