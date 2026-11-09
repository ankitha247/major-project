"""
yolo_service.py
YOLO-based object detection for crime scene images and video frames.

Uses YOLOv8n (nano) from ultralytics — small, fast, no GPU needed.
Detects objects in images/frames and returns:
  - List of detected objects with labels, confidence scores, bounding boxes
  - Annotated image (JPEG bytes) with bounding boxes drawn
  - Summary string for feeding into Groq prompts
"""

import io
import numpy as np
import cv2
from pathlib import Path
from ultralytics import YOLO

model = YOLO("yolov8n.pt")
# ── lazy-load YOLO so import errors don't crash the whole app ─────────────────
_yolo_model = None
_yolo_error = None


def _get_model():
    global _yolo_model, _yolo_error
    if _yolo_model is not None:
        return _yolo_model
    if _yolo_error is not None:
        return None
    try:
        from ultralytics import YOLO
        model_path = Path(__file__).parent / "yolov8n.pt"
        # Downloads automatically on first run if not present
        _yolo_model = YOLO(str(model_path) if model_path.exists() else "yolov8n.pt")
        print("[YOLO] Model loaded successfully.")
        return _yolo_model
    except Exception as e:
        _yolo_error = str(e)
        print(f"[YOLO] Failed to load model: {e}")
        return None


# Crime-relevant YOLO COCO classes (class index → label)
# Full COCO has 80 classes; we highlight forensically relevant ones
FORENSIC_CLASSES = {
    0:  "person",
    1:  "bicycle",
    2:  "car",
    3:  "motorcycle",
    5:  "bus",
    6:  "train",
    7:  "truck",
    14: "bird",        # may indicate outdoor scene
    24: "backpack",
    25: "umbrella",
    26: "handbag",
    27: "tie",
    28: "suitcase",
    39: "bottle",
    41: "cup",
    42: "fork",
    43: "knife",
    44: "spoon",
    45: "bowl",
    56: "chair",
    57: "couch",
    58: "potted plant",
    59: "bed",
    60: "dining table",
    62: "tv",
    63: "laptop",
    64: "mouse",
    65: "remote",
    66: "keyboard",
    67: "cell phone",
    73: "book",
    74: "clock",
    76: "scissors",
    77: "teddy bear",
    78: "hair drier",
    79: "toothbrush",
}

# Color map for bounding boxes (BGR for OpenCV)
COLORS = [
    (0,   255,   0),   # green
    (0,   0,   255),   # red
    (255, 165,   0),   # orange
    (0,   255, 255),   # yellow
    (255,   0, 255),   # magenta
    (0,   128, 255),   # blue
]


def detect_objects(image_bytes: bytes, conf_threshold: float = 0.35) -> dict:
    """
    Run YOLO detection on image bytes.

    Returns:
    {
      "detections": [
          {"label": str, "confidence": float, "bbox": [x1,y1,x2,y2], "forensic": bool},
          ...
      ],
      "annotated_jpeg": bytes,   # image with bounding boxes drawn
      "summary": str,            # human-readable summary for Groq prompt
      "counts": {"person": 2, "car": 1, ...},
      "yolo_available": bool,
    }
    """
    model = _get_model()
    if model is None:
        return {
            "detections": [], "annotated_jpeg": image_bytes,
            "summary": "YOLO detection unavailable.",
            "counts": {}, "yolo_available": False,
        }

    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {
            "detections": [], "annotated_jpeg": image_bytes,
            "summary": "Could not decode image for YOLO.",
            "counts": {}, "yolo_available": True,
        }

    # Run inference
    results = model(img, conf=conf_threshold, verbose=False)

    detections = []
    counts     = {}
    annotated  = img.copy()

    for result in results:
        boxes = result.boxes
        for i, box in enumerate(boxes):
            cls_id     = int(box.cls[0])
            label      = result.names[cls_id]
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            is_forensic = cls_id in FORENSIC_CLASSES

            detections.append({
                "label":      label,
                "confidence": round(confidence, 3),
                "bbox":       [x1, y1, x2, y2],
                "forensic":   is_forensic,
            })

            counts[label] = counts.get(label, 0) + 1

            # Draw bounding box
            color     = COLORS[i % len(COLORS)]
            thickness = 3 if is_forensic else 1
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)

            # Label with confidence
            text = f"{label} {confidence:.0%}"
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            # Background rectangle for text
            cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
            cv2.putText(annotated, text, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

    # Encode annotated image to JPEG bytes
    _, buf          = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
    annotated_jpeg  = buf.tobytes()

    # Build human-readable summary for Groq
    if counts:
        parts = [f"{v}x {k}" for k, v in sorted(counts.items(), key=lambda x: -x[1])]
        summary = f"YOLO detected: {', '.join(parts)}."
        # Highlight forensically important ones
        forensic_found = [d["label"] for d in detections if d["forensic"]]
        if forensic_found:
            unique_f = list(dict.fromkeys(forensic_found))
            summary += f" Forensically relevant: {', '.join(unique_f)}."
    else:
        summary = "YOLO found no objects above the confidence threshold."

    print(f"[YOLO] {summary}")
    return {
        "detections":     detections,
        "annotated_jpeg": annotated_jpeg,
        "summary":        summary,
        "counts":         counts,
        "yolo_available": True,
    }
