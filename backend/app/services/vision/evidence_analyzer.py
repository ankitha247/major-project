"""
Evidence analyzer using OpenCV.
Analyzes images and video frames without needing a vision model.
Extracts scene context to inject into Groq during the interview.
"""

import cv2
import base64
import logging
import numpy as np
import tempfile
import os
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Image Analysis ─────────────────────────────────────────────────────────

def analyze_image_bytes(image_bytes: bytes, filename: str = "image.jpg") -> dict:
    """
    Analyze a single image using OpenCV.
    Returns scene context dict.
    """
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return _empty_image_result("Could not decode image")
        return _analyze_frame(img, filename)
    except Exception as e:
        logger.warning("Image analysis failed: %s", e)
        return _empty_image_result(str(e))


def _analyze_frame(img: np.ndarray, label: str = "frame") -> dict:
    """Run full OpenCV analysis on a single frame."""
    h, w = img.shape[:2]

    # ── Face detection ──────────────────────────────────────────────────
    face_count = _detect_faces(img)

    # ── Scene brightness ────────────────────────────────────────────────
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray))
    if brightness < 50:
        lighting = "very dark / night scene"
    elif brightness < 100:
        lighting = "dimly lit"
    elif brightness < 180:
        lighting = "moderately lit"
    else:
        lighting = "well lit / bright"

    # ── Dominant colors ─────────────────────────────────────────────────
    dominant_colors = _get_dominant_colors(img, k=3)

    # ── Edge density (complexity of scene) ──────────────────────────────
    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.sum(edges > 0)) / (h * w)
    if edge_density > 0.15:
        scene_complexity = "complex scene with many objects"
    elif edge_density > 0.05:
        scene_complexity = "moderate scene complexity"
    else:
        scene_complexity = "simple or empty scene"

    # ── Indoor / outdoor estimate ────────────────────────────────────────
    scene_type = _estimate_scene_type(img, brightness)

    # ── Motion blur detection ────────────────────────────────────────────
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    is_blurry = laplacian_var < 100
    image_quality = "blurry / motion blur detected" if is_blurry else "clear image"

    # ── Build context string for Groq ────────────────────────────────────
    context_parts = []
    if face_count > 0:
        context_parts.append(
            f"{face_count} {'person' if face_count == 1 else 'people'} visible in footage"
        )
    context_parts.append(f"Lighting: {lighting}")
    context_parts.append(f"Scene type: {scene_type}")
    context_parts.append(f"Scene complexity: {scene_complexity}")
    context_parts.append(f"Image quality: {image_quality}")
    if dominant_colors:
        context_parts.append(f"Dominant colors in scene: {', '.join(dominant_colors)}")

    return {
        "label": label,
        "face_count": face_count,
        "lighting": lighting,
        "scene_type": scene_type,
        "scene_complexity": scene_complexity,
        "image_quality": image_quality,
        "dominant_colors": dominant_colors,
        "brightness": round(brightness, 1),
        "edge_density": round(edge_density, 4),
        "resolution": f"{w}x{h}",
        "context_string": ". ".join(context_parts),
        "error": None,
    }


def _detect_faces(img: np.ndarray) -> int:
    """Count faces using OpenCV Haar cascade."""
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        return len(faces)
    except Exception:
        return 0


def _get_dominant_colors(img: np.ndarray, k: int = 3) -> list[str]:
    """Get dominant color names from image using k-means clustering."""
    try:
        small = cv2.resize(img, (50, 50))
        data = small.reshape((-1, 3)).astype(np.float32)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, _, centers = cv2.kmeans(
            data, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
        )

        color_names = []
        for center in centers:
            b, g, r = int(center[0]), int(center[1]), int(center[2])
            color_names.append(_bgr_to_name(b, g, r))

        return list(dict.fromkeys(color_names))  # deduplicate preserving order
    except Exception:
        return []


def _bgr_to_name(b: int, g: int, r: int) -> str:
    """Convert BGR values to a rough color name."""
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    brightness = (max_c + min_c) / 2

    if brightness < 40:
        return "black"
    if brightness > 215:
        return "white"
    if max_c - min_c < 30:
        if brightness < 100:
            return "dark gray"
        return "gray"

    if r > g and r > b:
        return "dark red" if r < 120 else "red"
    if g > r and g > b:
        return "dark green" if g < 120 else "green"
    if b > r and b > g:
        return "dark blue" if b < 120 else "blue"
    if r > 150 and g > 150 and b < 100:
        return "yellow"
    if r > 150 and b > 150 and g < 100:
        return "purple"
    if r > 150 and g > 100 and b < 80:
        return "orange"

    return "mixed"


def _estimate_scene_type(img: np.ndarray, brightness: float) -> str:
    """Rough indoor/outdoor estimate based on color distribution."""
    try:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # Green channel — high green saturation suggests outdoor
        green_mask = cv2.inRange(hsv, (35, 40, 40), (85, 255, 255))
        green_ratio = float(np.sum(green_mask > 0)) / (img.shape[0] * img.shape[1])
        # Blue sky detection
        sky_mask = cv2.inRange(hsv, (90, 50, 150), (130, 255, 255))
        sky_ratio = float(np.sum(sky_mask > 0)) / (img.shape[0] * img.shape[1])

        if green_ratio > 0.2 or sky_ratio > 0.15:
            return "outdoor / open area"
        if brightness < 60:
            return "indoor / low light environment"
        return "indoor"
    except Exception:
        return "unknown"


def _empty_image_result(error: str) -> dict:
    return {
        "label": "unknown",
        "face_count": 0,
        "lighting": "unknown",
        "scene_type": "unknown",
        "scene_complexity": "unknown",
        "image_quality": "unknown",
        "dominant_colors": [],
        "brightness": 0.0,
        "edge_density": 0.0,
        "resolution": "unknown",
        "context_string": "",
        "error": error,
    }


# ── Video Analysis ──────────────────────────────────────────────────────────

def analyze_video_bytes(video_bytes: bytes, num_frames: int = 6) -> dict:
    """
    Analyze a video by extracting evenly spaced frames and running
    OpenCV analysis on each frame.
    Returns aggregated scene context dict.
    """
    tmp_path = None
    try:
        # Write to temp file — OpenCV needs a file path for video
        suffix = ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            return _empty_video_result("Could not open video file")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        duration_sec = total_frames / fps

        logger.info(
            "Video: total_frames=%d fps=%.1f duration=%.1fs",
            total_frames, fps, duration_sec
        )

        if total_frames < 1:
            return _empty_video_result("Video has no frames")

        # Pick evenly spaced frame indices
        margin = max(1, int(total_frames * 0.05))
        usable = max(1, total_frames - 2 * margin)
        step = max(1, usable // num_frames)
        indices = [margin + i * step for i in range(min(num_frames, total_frames))]

        frame_results = []
        prev_gray = None

        for i, idx in enumerate(indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue

            timestamp = round(idx / fps, 2)
            label = f"Frame {i+1} at {timestamp}s"

            result = _analyze_frame(frame, label)
            result["timestamp_sec"] = timestamp
            result["frame_number"] = i + 1

            # Motion detection between consecutive frames
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                motion_score = float(np.mean(diff))
                result["motion_score"] = round(motion_score, 2)
                if motion_score > 15:
                    result["motion_detected"] = True
                    result["context_string"] += ". Significant motion detected between frames"
                else:
                    result["motion_detected"] = False
            else:
                result["motion_score"] = 0.0
                result["motion_detected"] = False

            prev_gray = gray
            frame_results.append(result)

        cap.release()

        if not frame_results:
            return _empty_video_result("No frames could be extracted")

        # ── Aggregate across all frames ──────────────────────────────────
        total_faces = sum(f["face_count"] for f in frame_results)
        max_faces = max(f["face_count"] for f in frame_results)
        motion_frames = sum(1 for f in frame_results if f.get("motion_detected"))
        avg_brightness = np.mean([f["brightness"] for f in frame_results])

        # Most common scene type
        scene_types = [f["scene_type"] for f in frame_results]
        scene_type = max(set(scene_types), key=scene_types.count)

        # All dominant colors across frames
        all_colors = []
        for f in frame_results:
            all_colors.extend(f["dominant_colors"])
        unique_colors = list(dict.fromkeys(all_colors))[:5]

        # Build aggregate context string
        agg_parts = []
        if max_faces > 0:
            agg_parts.append(
                f"Up to {max_faces} {'person' if max_faces == 1 else 'people'} "
                f"visible across {len(frame_results)} frames"
            )
        agg_parts.append(f"Scene type: {scene_type}")
        agg_parts.append(
            f"Average lighting: {'dark' if avg_brightness < 80 else 'moderate' if avg_brightness < 160 else 'bright'}"
        )
        if motion_frames > 0:
            agg_parts.append(
                f"Motion detected in {motion_frames} of {len(frame_results)} frame intervals"
            )
        if unique_colors:
            agg_parts.append(f"Colors observed: {', '.join(unique_colors)}")
        agg_parts.append(f"Video duration: approximately {duration_sec:.1f} seconds")

        return {
            "frame_results": frame_results,
            "total_frames_analyzed": len(frame_results),
            "duration_sec": round(duration_sec, 1),
            "fps": round(fps, 1),
            "max_faces_in_frame": max_faces,
            "motion_frames": motion_frames,
            "scene_type": scene_type,
            "avg_brightness": round(float(avg_brightness), 1),
            "dominant_colors": unique_colors,
            "aggregate_context": ". ".join(agg_parts),
            "error": None,
        }

    except Exception as e:
        logger.exception("Video analysis failed: %s", e)
        return _empty_video_result(str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _empty_video_result(error: str) -> dict:
    return {
        "frame_results": [],
        "total_frames_analyzed": 0,
        "duration_sec": 0.0,
        "fps": 0.0,
        "max_faces_in_frame": 0,
        "motion_frames": 0,
        "scene_type": "unknown",
        "avg_brightness": 0.0,
        "dominant_colors": [],
        "aggregate_context": "",
        "error": error,
    }


# ── Context Builder for Groq ────────────────────────────────────────────────

def build_evidence_context_string(
    evidence_type: str,
    image_result: dict = None,
    video_result: dict = None,
) -> str:
    """
    Build a context string to inject into Groq system prompt.
    """
    if evidence_type == "image" and image_result:
        ctx = image_result.get("context_string", "")
        if not ctx:
            return ""
        return f"CCTV/Photo Evidence Analysis:\n{ctx}"

    if evidence_type == "video" and video_result:
        ctx = video_result.get("aggregate_context", "")
        frame_details = []
        for fr in video_result.get("frame_results", []):
            fc = fr.get("face_count", 0)
            motion = "motion detected" if fr.get("motion_detected") else "no motion"
            ts = fr.get("timestamp_sec", 0)
            if fc > 0 or fr.get("motion_detected"):
                frame_details.append(
                    f"  At {ts}s: {fc} person(s) visible, {motion}"
                )
        full_ctx = f"Video Evidence Analysis:\n{ctx}"
        if frame_details:
            full_ctx += "\nFrame-by-frame:\n" + "\n".join(frame_details)
        return full_ctx

    return ""