"""Slot extraction — fill the named slots a shape's Cypher template needs.

Each shape in `shapes.CANONICAL_CYPHER` carries `$param` placeholders.
Your `extract_slots(question, shape)` returns a dict whose keys are the
parameter names the template expects, e.g.:

  ShapeId.Q1 → {"ingredient": "ginger"}
  ShapeId.Q5 → {"cuisine": "Sichuan", "ingredient": "ginger"}
  ShapeId.Q9 → {"cuisine": "Italian"}
  ShapeId.Q10 → {"max_minutes": 30}
  ShapeId.Q14 → {"ingredient": "ginger", "exclude_ingredient": "garlic"}

See `data/eval_questions.jsonl` for the gold (question_text, shape, slots)
triples used by the autograder.
"""

from .shapes import ShapeId
import re

CUISINES = [
    "Sichuan",
    "Italian",
    "Chinese",
    "Asian",
    "Mexican",
    "French",
    "Indian",
    "Japanese",
    "Thai",
    "Mediterranean",
    "Spanish",
    "Greek",
    "American",
    "Middle Eastern",
    "World",
]

INGREDIENTS = [
    "ginger",
    "garlic",
    "basil",
    "peppercorn",
    "tomato",
    "onion",
    "olive oil",
    "lemon",
    "salt",
    "pepper",
    "cumin",
    "coriander",
    "turmeric",
    "chili",
    "soy sauce",
    "sesame oil",
    "rice",
    "pasta",
    "flour",
    "egg",
    "butter",
    "cream",
    "cheese",
    "chicken",
    "beef",
    "pork",
    "fish",
    "shrimp",
    "mushroom",
    "spinach",
    "broccoli",
    "carrot",
    "potato",
    "tofu",
    "coconut milk",
    "vinegar",
    "honey",
    "sugar",
    "thyme",
    "rosemary",
]

TECHNIQUES = [
    "wok",
    "grilling",
    "baking",
    "steaming",
    "frying",
    "braising",
    "roasting",
    "sautéing",
    "sauteing",
    "poaching",
    "smoking",
]


def _find_cuisine(text: str) -> str | None:
    tl = text.lower()
    for c in CUISINES:
        if c.lower() in tl:
            return c
    return None


def _find_ingredient(text: str) -> str | None:
    tl = text.lower()
    for ing in sorted(INGREDIENTS, key=len, reverse=True):
        if ing.lower() in tl:
            return ing
    return None


def _find_technique(text: str) -> str | None:
    tl = text.lower()
    for t in TECHNIQUES:
        if t.lower() in tl:
            return t
    return None


def _find_author(text: str) -> str | None:
    """Extract PERSON name after 'by author' or 'by <Name>'."""
    m = re.search(r"\bby\s+author\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", text)
    if m:
        return m.group(1)
    m = re.search(r"\bby\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", text)
    if m:
        return m.group(1)
    # Fallback: try spaCy
    try:
        import spacy

        nlp = spacy.load("en_core_web_sm")
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                return ent.text
    except Exception:
        pass
    return None


def extract_slots(question: str, shape: ShapeId) -> dict:
    """Extract slot values for the given shape from the question text.

    Suggested approach:
      - spaCy NER for PERSON entities (q2, q8 author slot).
      - A short hand-authored vocabulary list of the cuisines and
        ingredients in the recipe KG — string-match the question against
        it case-insensitively. The lists are small (16 cuisines, 40
        ingredients) so a literal-match approach is fine.
      - For q10: a regex like `under (\\d+)\\s*minutes` to pull the
        integer threshold.
      - For q14: split the question on "but not" / "without" to get the
        positive and negative ingredient slots.

    Return a dict whose keys EXACTLY match the `$param` names in
    shapes.CANONICAL_CYPHER[shape]. Returning a slot dict missing a
    required parameter will surface as a Neo4j ParameterMissing error
    at query time — that is fail-loud and desired.

    Values must be the canonical form the KG uses (e.g., 'Italian' not
    'italian'; 'ginger' not 'Ginger'). Match against the schema vocabulary
    rather than echoing the surface form of the question.
    """
    # TODO (slot extraction):
    # 1. For the given shape, list the parameter names you need to fill.
    # 2. For each parameter, use a vocabulary list or a regex over the
    #    question text to extract the value in canonical form.
    # 3. Return the dict.
    q = question

    if shape == ShapeId.Q1:
        return {"ingredient": _find_ingredient(q)}

    if shape == ShapeId.Q2:
        return {"author": _find_author(q)}

    if shape in (ShapeId.Q3, ShapeId.Q4, ShapeId.Q9, ShapeId.Q11):
        return {"cuisine": _find_cuisine(q)}

    if shape in (ShapeId.Q5, ShapeId.Q6):
        return {"cuisine": _find_cuisine(q), "ingredient": _find_ingredient(q)}

    if shape == ShapeId.Q7:
        return {"technique": _find_technique(q)}

    if shape == ShapeId.Q8:
        return {"author": _find_author(q), "ingredient": _find_ingredient(q)}

    if shape == ShapeId.Q10:
        m = re.search(r"under\s+(\d+)\s*minutes", q.lower())
        return {"max_minutes": int(m.group(1)) if m else None}

    if shape == ShapeId.Q12:
        return {"cuisine": _find_cuisine(q)}

    if shape == ShapeId.Q13:
        return {"ingredient": _find_ingredient(q)}

    if shape == ShapeId.Q14:
        # Split on "but not" or "without"
        parts = re.split(r"\bbut not\b|\bwithout\b", q.lower(), maxsplit=1)
        pos_ing = _find_ingredient(parts[0]) if parts else None
        neg_ing = _find_ingredient(parts[1]) if len(parts) > 1 else None
        return {"ingredient": pos_ing, "exclude_ingredient": neg_ing}

    if shape == ShapeId.Q15:
        return {"technique": _find_technique(q)}

    raise ValueError(f"Unknown shape: {shape}")


# q
