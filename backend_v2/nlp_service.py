"""
nlp_service.py
spaCy-based NLP enrichment for the Crime Witness Interview Assistant.

Used in two places:
  1. analyze_witness_answer()  — extracts entities + key phrases from each
                                 witness answer to enrich the Groq interview context
  2. analyze_text_description() — enriches free-text scene descriptions before
                                  they are passed to Groq

Extracted information:
  - Named entities: PERSON, GPE (location), ORG, TIME, DATE, EVENT, FAC (facility)
  - Key noun phrases (noun chunks) relevant to the scene
  - Action verbs (root verbs) describing what happened
  - Negations (e.g. "didn't see", "no one") — forensically important
"""

from __future__ import annotations

# ── lazy-load spaCy ───────────────────────────────────────────────────────────
_nlp = None
_nlp_available = None

def _get_nlp():
    global _nlp, _nlp_available

    # Already checked — return cached result
    if _nlp_available is True:
        return _nlp
    if _nlp_available is False:
        return None

    try:
        import spacy
        _nlp = spacy.load("en_core_web_sm")
        _nlp_available = True
        print("[spaCy] en_core_web_sm loaded successfully")
        return _nlp
    except OSError:
        print("[spaCy] en_core_web_sm not found — NLP enrichment disabled. Run: pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl")
        _nlp_available = False
        return None
    except Exception as e:
        print(f"[spaCy] Failed to load: {e}")
        _nlp_available = False
        return None

# Entity labels we care about forensically
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


def _empty_result(text: str) -> dict:
    return {
        "entities": [],
        "entity_summary": "",
        "noun_phrases": [],
        "action_verbs": [],
        "negations": [],
        "context_enrichment": "",
        "spacy_available": False,
        "original_text": text,
    }


def analyze_text(text: str) -> dict:
    """
    Run spaCy NLP on any text (witness answer or scene description).

    Returns a dict with extracted entities, phrases, verbs, negations,
    and a pre-formatted context_enrichment string ready to inject into Groq prompts.
    """
    nlp = _get_nlp()
    if nlp is None or not text.strip():
        return _empty_result(text)

    doc = nlp(text)

    # ── Named entities ────────────────────────────────────────────────────────
    entities = []
    seen     = set()
    for ent in doc.ents:
        if ent.label_ in FORENSIC_ENTITIES and ent.text.lower() not in seen:
            seen.add(ent.text.lower())
            entities.append({
                "text":        ent.text,
                "label":       ent.label_,
                "description": FORENSIC_ENTITIES[ent.label_],
            })

    # ── Key noun phrases ──────────────────────────────────────────────────────
    noun_phrases = []
    seen_np      = set()
    for chunk in doc.noun_chunks:
        np_text = chunk.text.strip().lower()
        if len(np_text) > 2 and np_text not in seen_np:
            seen_np.add(np_text)
            noun_phrases.append(chunk.text.strip())

    # ── Action verbs (root + other main verbs) ────────────────────────────────
    action_verbs = []
    for token in doc:
        if token.pos_ == "VERB" and token.dep_ in ("ROOT", "conj", "advcl", "relcl"):
            lemma = token.lemma_.lower()
            if lemma not in action_verbs and len(lemma) > 2:
                action_verbs.append(lemma)

    # ── Negations ─────────────────────────────────────────────────────────────
    negations = []
    for token in doc:
        if token.dep_ == "neg":
            # Grab the verb being negated
            head = token.head
            neg_phrase = f"not {head.lemma_}"
            if neg_phrase not in negations:
                negations.append(neg_phrase)

    # ── Summaries for Groq prompt injection ───────────────────────────────────
    entity_parts = []
    for label, desc in FORENSIC_ENTITIES.items():
        group = [e["text"] for e in entities if e["label"] == label]
        if group:
            entity_parts.append(f"{desc}: {', '.join(group)}")
    entity_summary = "; ".join(entity_parts) if entity_parts else "No named entities found."

    enrichment_parts = []
    if entities:
        enrichment_parts.append(f"NLP Entities — {entity_summary}")
    if noun_phrases[:5]:
        enrichment_parts.append(f"Key phrases: {', '.join(noun_phrases[:5])}")
    if action_verbs[:5]:
        enrichment_parts.append(f"Actions described: {', '.join(action_verbs[:5])}")
    if negations:
        enrichment_parts.append(f"Negations (important gaps): {', '.join(negations)}")

    context_enrichment = "\n".join(enrichment_parts) if enrichment_parts else ""

    print(f"[spaCy] Entities={len(entities)}, NPs={len(noun_phrases)}, "
          f"Verbs={len(action_verbs)}, Negations={len(negations)}")

    return {
        "entities":           entities,
        "entity_summary":     entity_summary,
        "noun_phrases":       noun_phrases,
        "action_verbs":       action_verbs,
        "negations":          negations,
        "context_enrichment": context_enrichment,
        "spacy_available":    True,
        "original_text":      text,
    }


def enrich_conversation_context(conversation: list[dict]) -> str:
    """
    Run spaCy over all witness answers in a conversation and return a
    combined NLP context string to inject into the Groq interviewer prompt.
    """
    nlp = _get_nlp()
    if nlp is None:
        return ""

    witness_texts = [m["content"] for m in conversation if m["role"] == "user"]
    if not witness_texts:
        return ""

    combined = " ".join(witness_texts)
    result   = analyze_text(combined)

    if not result["spacy_available"] or not result["context_enrichment"]:
        return ""

    return f"\n[NLP Analysis of witness answers so far]\n{result['context_enrichment']}"