"""
report_pdf.py
Generates a professional PDF investigation report using ReportLab.
Embeds the actual evidence input:
  - Image  → full-width crime scene photo
  - Video  → grid of annotated frames (YOLO bounding boxes) + descriptions
  - Text   → styled text block of the original description
Also includes NLP entity table when available.
"""

import io
import base64
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Table, TableStyle, Image as RLImage, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

PAGE_W, PAGE_H = A4
MARGIN        = 2.2 * cm
USABLE_W      = PAGE_W - 2 * MARGIN


# ── Styles ────────────────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()
    def s(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    return {
        "title":    s("T", fontSize=20, leading=24, textColor=colors.HexColor("#1a1a2e"),
                      alignment=TA_CENTER, spaceAfter=4, fontName="Helvetica-Bold"),
        "subtitle": s("ST", fontSize=9, textColor=colors.HexColor("#666"),
                      alignment=TA_CENTER, spaceAfter=10),
        "h1":       s("H1", fontSize=13, leading=17, textColor=colors.HexColor("#1a1a2e"),
                      spaceBefore=14, spaceAfter=4, fontName="Helvetica-Bold"),
        "h2":       s("H2", fontSize=11, leading=14, textColor=colors.HexColor("#374151"),
                      spaceBefore=10, spaceAfter=3, fontName="Helvetica-Bold"),
        "body":     s("B", fontSize=9.5, leading=14, textColor=colors.HexColor("#2c2c2c"),
                      spaceAfter=5, alignment=TA_JUSTIFY),
        "caption":  s("C", fontSize=8, textColor=colors.HexColor("#6b7280"),
                      alignment=TA_CENTER, spaceAfter=4),
        "bullet":   s("BU", fontSize=9.5, leading=14, textColor=colors.HexColor("#2c2c2c"),
                      leftIndent=12, spaceAfter=3),
        "label":    s("L", fontSize=8.5, textColor=colors.HexColor("#7c3aed"),
                      fontName="Helvetica-Bold"),
        "textbox":  s("TB", fontSize=9, leading=13, textColor=colors.HexColor("#14532d"),
                      backColor=colors.HexColor("#f0fdf4"), borderPad=8,
                      borderWidth=1, borderColor=colors.HexColor("#bbf7d0"),
                      spaceAfter=8),
    }


def _hr(color="#cccccc", thickness=0.5):
    return HRFlowable(width="100%", thickness=thickness,
                      color=colors.HexColor(color), spaceAfter=6)


def _section_header(text, st):
    return [
        Paragraph(text, st["h1"]),
        _hr("#1a1a2e", 1.0),
    ]


def _bytes_to_rl_image(jpeg_bytes: bytes, max_w: float, max_h: float) -> RLImage:
    """Wrap JPEG bytes as a ReportLab Image, scaled to fit max_w × max_h."""
    buf = io.BytesIO(jpeg_bytes)
    img = RLImage(buf)
    img_w, img_h = img.imageWidth, img.imageHeight
    scale = min(max_w / img_w, max_h / img_h, 1.0)
    img.drawWidth  = img_w * scale
    img.drawHeight = img_h * scale
    return img


# ── Evidence sections ─────────────────────────────────────────────────────────

def _evidence_image(image_bytes: bytes, filename: str, st_) -> list:
    """Embed crime scene image."""
    story = _section_header("📥 Evidence Input — Crime Scene Image", st_)

    if image_bytes:
        try:
            img = _bytes_to_rl_image(image_bytes, USABLE_W, 10 * cm)
            story += [
                img,
                Paragraph(filename or "Crime scene image", st_["caption"]),
                Spacer(1, 0.3 * cm),
            ]
        except Exception as e:
            story.append(Paragraph(f"[Image could not be embedded: {e}]", st_["body"]))

    return story


def _evidence_video(frame_results: list, frames_n: int, st_) -> list:
    """Embed each annotated frame in a 2-column grid with its description."""
    story = _section_header(f"📥 Evidence Input — Video Footage ({frames_n} Frames)", st_)

    if not frame_results:
        story.append(Paragraph("No frame data available.", st_["body"]))
        return story

    # Build 2-column frame grid
    for i in range(0, len(frame_results), 2):
        row_cells = []
        for fr in frame_results[i:i+2]:
            frame_num  = fr.get("frame_num", "?")
            timestamp  = fr.get("timestamp_sec", 0)
            orig_b64    = fr.get("jpeg_b64", "")
            description = fr.get("description", "No description.")
            nlp_entities = fr.get("nlp_entities", [])

            cell_story = []

            # Frame image
            disp_b64 = orig_b64
            if disp_b64:
                try:
                    img = _bytes_to_rl_image(base64.b64decode(disp_b64),
                                             (USABLE_W / 2) - 0.5 * cm, 6 * cm)
                    cell_story.append(img)
                except Exception:
                    pass

            cell_story.append(
                Paragraph(f"<b>Frame {frame_num}</b>  ·  ⏱ {timestamp}s", st_["label"])
            )

            # NLP entities
            if nlp_entities:
                ent_str = "  ".join(e["label"] + ": " + e["text"] for e in nlp_entities[:4])
                cell_story.append(Paragraph("🔤 NLP: " + ent_str, st_["caption"]))

            # AI description
            cell_story.append(Paragraph(description, st_["body"]))
            row_cells.append(cell_story)

        # Pad to 2 columns
        while len(row_cells) < 2:
            row_cells.append([Spacer(1, 1)])

        col_w = (USABLE_W - 0.4 * cm) / 2
        tbl = Table([row_cells], colWidths=[col_w, col_w])
        tbl.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
            ("BOX",          (0, 0), (0, 0),  0.5, colors.HexColor("#ddd6fe")),
            ("BOX",          (1, 0), (1, 0),  0.5, colors.HexColor("#ddd6fe")),
            ("BACKGROUND",   (0, 0), (-1, -1), colors.HexColor("#faf5ff")),
        ]))
        story.append(KeepTogether([tbl, Spacer(1, 0.3 * cm)]))

    return story


def _evidence_text(original_text: str, nlp_data: dict, st_) -> list:
    """Embed original text description + spaCy NLP findings."""
    story = _section_header("📥 Evidence Input — Text Description", st_)

    story.append(Paragraph("<b>Original description provided:</b>", st_["h2"]))
    # Split into paragraphs
    for para in (original_text or "").split("\n"):
        para = para.strip()
        if para:
            story.append(Paragraph(para, st_["textbox"]))

    # NLP entity table
    if nlp_data.get("spacy_available") and nlp_data.get("entities"):
        story += _nlp_table(nlp_data, st_)

    return story



def _nlp_table(nlp_data: dict, st_) -> list:
    """Render a spaCy NLP entity table."""
    entities = nlp_data.get("entities", [])
    if not entities:
        return []

    story = [Paragraph("<b>spaCy NLP — Named Entities</b>", st_["h2"])]
    rows  = [["Entity", "Type", "Meaning"]]
    for e in entities:
        rows.append([e.get("text", ""), e.get("label", ""), e.get("description", "")])

    col_w = [USABLE_W * r for r in [0.35, 0.2, 0.45]]
    tbl   = Table(rows, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#7c3aed")),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#faf5ff")]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#e5e7eb")),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    if nlp_data.get("action_verbs"):
        story.append(Paragraph(
            "<b>Actions:</b> " + ", ".join(nlp_data["action_verbs"][:8]), st_["body"]
        ))
    if nlp_data.get("negations"):
        story.append(Paragraph(
            "<b>⚠ Negations (witness said did NOT see):</b> " +
            ", ".join(nlp_data["negations"]), st_["body"]
        ))
    story += [tbl, Spacer(1, 0.3 * cm)]
    return story


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_pdf(
    report_text:   str,
    session_id:    str,
    crime_type:    str,
    # evidence data (all optional — gracefully skipped if absent)
    image_bytes:   bytes = None,
    image_filename: str  = None,
    frame_results: list  = None,
    frames_n:      int   = 0,
    nlp_data:      dict  = None,
    original_text: str   = None,
    input_type:    str   = "image",
) -> bytes:
    """
    Build a complete PDF investigation report including:
      - Cover page with case metadata
      - Evidence Input section (embedded image / frames / text)
      - NLP entity table
      - Full AI-generated report text
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
    )
    st_ = _styles()
    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("FORENSIC INTERVIEW REPORT", st_["title"]))
    story.append(Paragraph(
        f"Case ID: <b>{session_id}</b> &nbsp;|&nbsp; "
        f"Crime Type: <b>{crime_type}</b> &nbsp;|&nbsp; "
        f"Input: <b>{input_type.capitalize()}</b> &nbsp;|&nbsp; "
        f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}",
        st_["subtitle"],
    ))
    story.append(_hr("#1a1a2e", 1.5))
    story.append(Spacer(1, 0.4 * cm))

    # ── Evidence Input section ────────────────────────────────────────────────
    if input_type == "image" and image_bytes:
        story += _evidence_image(image_bytes, image_filename or "image", st_)

    elif input_type == "video" and frame_results:
        story += _evidence_video(frame_results, frames_n, st_)

    elif input_type == "text" and original_text:
        story += _evidence_text(original_text, nlp_data or {}, st_)

    story.append(Spacer(1, 0.3 * cm))

    # ── AI Report text ────────────────────────────────────────────────────────
    story += _section_header("📋 Full Investigation Report", st_)

    for line in report_text.splitlines():
        line = line.strip()
        if not line:
            story.append(Spacer(1, 0.15 * cm))
            continue
        if line.startswith("## "):
            story.append(Paragraph(line[3:].strip(), st_["h1"]))
            story.append(_hr())
        elif line.startswith("# "):
            story.append(Paragraph(line[2:].strip(), st_["title"]))
        elif line.startswith(("- ", "* ")):
            story.append(Paragraph("• " + line[2:].strip(), st_["bullet"]))
        elif line.startswith("**") and line.endswith("**"):
            story.append(Paragraph("<b>" + line[2:-2] + "</b>", st_["body"]))
        else:
            fmt = line.replace("**", "<b>", 1)
            while "**" in fmt:
                fmt = fmt.replace("**", "</b>", 1)
            story.append(Paragraph(fmt, st_["body"]))

    doc.build(story)
    return buf.getvalue()

def _add_transcript_section(story, conversation, styles_dict):
    """Add timestamped transcript to report."""
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib import colors

    story.append(Paragraph("Interview Transcript", styles_dict["section"]))

    for msg in conversation:
        role      = msg.get("role", "")
        content   = msg.get("content", "")
        timestamp = msg.get("timestamp", "")

        if role == "assistant":
            speaker = "AI Interviewer"
            color   = "#7c6af7"
        elif role == "user":
            speaker = "Witness"
            color   = "#22c55e"
        else:
            continue

        time_str = f" [{timestamp}]" if timestamp else ""
        label    = f'<font color="{color}"><b>{speaker}{time_str}:</b></font>'
        story.append(Paragraph(label, styles_dict["body"]))
        story.append(Paragraph(content, styles_dict["body"]))
        story.append(Spacer(1, 4))