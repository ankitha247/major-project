"""
spaCy NLP enrichment for interview context.
Extracts entities, action verbs, and negations from witness answers
to inject into Groq prompts for better follow-up questions.
"""

from __future__ import annotations

_nlp = None
_nlp_error = None


def _get_nlp():
    global _nlp, _nlp_error
    if _nlp is not None:
        return _nlp
    if _nlp_error is not None:
        return None
    try:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            import subprocess, sys
            subprocess.run(
                [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
                check=True, capture_output=True,
            )
            _nlp = spacy.load("en_core_web_sm")
        return _nlp
    except Exception as e:
        _nlp_error = str(e)
        return None


FORENSIC_ENTITIES = {
    "PERSON":  "Person mentioned",
    "GPE":     "Location (city/country)",
    "LOC":     "Location (physical)",
    "FAC":     "Facility/building",
    "ORG":     "Organisation",
    "TIME":    "Time reference",
    "DATE":    "Date reference",
    "EVENT":   "Event",
    "PRODUCT": "Product/item",
    "NORP":    "Nationality/group",
}


def analyze_text(text: str) -> dict:
    nlp = _get_nlp()
    if nlp is None or not text.strip():
        return {
            "entities": [], "entity_summary": "", "noun_phrases": [],
            "action_verbs": [], "negations": [], "context_enrichment": "",
            "spacy_available": False,
        }

    doc = nlp(text)

    # Named entities
    entities = []
    seen = set()
    for ent in doc.ents:
        if ent.label_ in FORENSIC_ENTITIES and ent.text.lower() not in seen:
            seen.add(ent.text.lower())
            entities.append({
                "text": ent.text,
                "label": ent.label_,
                "description": FORENSIC_ENTITIES[ent.label_],
            })

    # Key noun phrases
    noun_phrases = []
    seen_np = set()
    for chunk in doc.noun_chunks:
        np_text = chunk.text.strip().lower()
        if len(np_text) > 2 and np_text not in seen_np:
            seen_np.add(np_text)
            noun_phrases.append(chunk.text.strip())

    # Action verbs
    action_verbs = []
    for token in doc:
        if token.pos_ == "VERB" and token.dep_ in ("ROOT", "conj", "advcl", "relcl"):
            lemma = token.lemma_.lower()
            if lemma not in action_verbs and len(lemma) > 2:
                action_verbs.append(lemma)

    # Negations
    negations = []
    for token in doc:
        if token.dep_ == "neg":
            neg_phrase = f"not {token.head.lemma_}"
            if neg_phrase not in negations:
                negations.append(neg_phrase)

    # Build entity summary
    entity_parts = []
    for label, desc in FORENSIC_ENTITIES.items():
        group = [e["text"] for e in entities if e["label"] == label]
        if group:
            entity_parts.append(f"{desc}: {', '.join(group)}")
    entity_summary = "; ".join(entity_parts) if entity_parts else ""

    # Build enrichment string for Groq prompt injection
    enrichment_parts = []
    if entities:
        enrichment_parts.append(f"Named entities — {entity_summary}")
    if noun_phrases[:5]:
        enrichment_parts.append(f"Key phrases: {', '.join(noun_phrases[:5])}")
    if action_verbs[:5]:
        enrichment_parts.append(f"Actions described: {', '.join(action_verbs[:5])}")
    if negations:
        enrichment_parts.append(
            f"Negations (witness said they did NOT): {', '.join(negations)}"
        )

    context_enrichment = "\n".join(enrichment_parts)

    return {
        "entities": entities,
        "entity_summary": entity_summary,
        "noun_phrases": noun_phrases,
        "action_verbs": action_verbs,
        "negations": negations,
        "context_enrichment": context_enrichment,
        "spacy_available": True,
    }


def enrich_conversation_context(transcript: list[dict]) -> str:
    """
    Run spaCy over all witness answers in the transcript.
    Returns a formatted string to inject into the Groq system prompt.
    """
    witness_texts = [
        entry["text"] for entry in transcript if entry["speaker"] == "witness"
    ]
    if not witness_texts:
        return ""

    combined = " ".join(witness_texts)
    result = analyze_text(combined)

    if not result["spacy_available"] or not result["context_enrichment"]:
        return ""

    return f"\n[NLP Analysis of witness answers so far]\n{result['context_enrichment']}"