"""Intent classifier — map NL question to a canonical ShapeId.

This file is your responsibility. Read the 15 supported shapes in
`shapes.ShapeId` and `shapes.CANONICAL_CYPHER`, then implement
`detect_shape` so that each of the 15 canonical eval questions in
`data/eval_questions.jsonl` is classified to the gold shape, and
adversarial / off-template questions return None.

The deterministic mapper is the production-discipline arm of M9B; a
classifier that returns the wrong shape on a supported question is a
real bug, and a classifier that returns a confident answer on an
off-template question is the silent-failure mode the Reading warns
against. Prefer None over a false positive.
"""

from .shapes import ShapeId
import re

# Cuisines in the KG — ordered longest-first to avoid partial matches
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

# Broad/hierarchical cuisines that get q4/q6/q12 traversal treatment
HIERARCHICAL_CUISINES = {"Asian", "Chinese", "World", "Middle Eastern"}

# Ingredients in the KG
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

# Techniques in the KG
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


def _find_cuisine(q: str) -> str | None:
    for c in CUISINES:
        if c.lower() in q:
            return c
    return None


def _find_ingredient(q: str) -> str | None:
    # longest match first to avoid partial hits
    for ing in sorted(INGREDIENTS, key=len, reverse=True):
        if ing.lower() in q:
            return ing
    return None


def _find_technique(q: str) -> str | None:
    for t in TECHNIQUES:
        if t.lower() in q:
            return t
    return None


def _is_hierarchical(cuisine: str) -> bool:
    return cuisine in HIERARCHICAL_CUISINES


def detect_shape(question: str) -> ShapeId | None:
    """Classify the question into one of the 15 ShapeId values, or None.

    Suggested approach: a small set of keyword / regex rules over the
    question text that match the shape vocabulary used by the recipe
    KG. Look for cues such as:
      - "by author <name>", "by <Name>"   → author shapes
      - "<cuisine name>"                  → cuisine shapes
      - "use <ingredient>", "with <ingredient>" → ingredient shapes
      - "but not <ingredient>"            → q14 (negation)
      - "ranked by popularity" / "most popular" → q9
      - "under <N> minutes"               → q10
      - "ingredients used in"             → q11 (inverse)
      - "authors of"                      → q12
      - "or any subtype" / "or any kind"  → q13
      - "optionally tagged"               → q15
      - "require <technique>"             → q7

    For cuisines and ingredients, you can use the schema label vocabulary
    (Cuisine.name values, Ingredient.name values) to disambiguate which
    slot type the question is naming. A spaCy NER pass on PERSON entities
    helps for q2 / q8.

    Returns None when no rule fires — the orchestrator raises
    UnsupportedQueryError in that case, which is the correct behaviour
    for an out-of-scope question.
    """
    # TODO (intent classifier):
    # 1. Lowercase the question for pattern matching.
    # 2. Apply rules in priority order — more-specific shapes (q14
    #    "but not", q8 "by ... that use") before less-specific (q1, q3).
    # 3. Return the matching ShapeId, or None if nothing matches.
    q = question.lower()

    # --- Q15: optionally tagged
    if "optionally tagged" in q:
        return ShapeId.Q15

    # --- Q13: ingredient or any subtype
    if "or any subtype" in q or "or any kind" in q:
        return ShapeId.Q13

    # --- Q14: negation (but not / without) — must precede Q1
    if "but not" in q or " without " in q:
        return ShapeId.Q14

    # --- Q10: prep time under N minutes
    if re.search(r"under\s+\d+\s*minutes", q) or "prep time" in q:
        return ShapeId.Q10

    # --- Q11: ingredients used in ...
    if "ingredients used in" in q:
        return ShapeId.Q11

    # --- Q12: authors of ...
    if "authors of" in q:
        return ShapeId.Q12

    # --- Q9: ranked by popularity / most popular
    if "ranked by popularity" in q or "most popular" in q:
        return ShapeId.Q9

    # --- Q7: require <technique>
    if "require" in q and _find_technique(q):
        return ShapeId.Q7

    # --- Q8: by author ... that use <ingredient> — must precede Q2 and Q1
    has_author_cue = bool(re.search(r"\bby\s+author\b|\bby\s+[A-Z]", question))
    has_ingredient_cue = (
        bool(re.search(r"\buse\b|\bwith\b", q)) and _find_ingredient(q) is not None
    )
    if has_author_cue and has_ingredient_cue:
        return ShapeId.Q8

    # --- Q2: by author (no ingredient)
    if has_author_cue:
        return ShapeId.Q2

    cuisine = _find_cuisine(q)
    ingredient = _find_ingredient(q) if re.search(r"\buse\b|\bwith\b", q) else None

    # --- Q6: hierarchical cuisine + ingredient
    if cuisine and ingredient and _is_hierarchical(cuisine):
        return ShapeId.Q6

    # --- Q5: direct cuisine + ingredient
    if cuisine and ingredient:
        return ShapeId.Q5

    # --- Q4: hierarchical cuisine, no ingredient
    if cuisine and _is_hierarchical(cuisine):
        return ShapeId.Q4

    # --- Q3: direct cuisine, no ingredient
    if cuisine:
        return ShapeId.Q3

    # --- Q1: use <ingredient> (no cuisine, no negation)
    if re.search(r"\buse\b|\bwith\b", q) and _find_ingredient(q):
        return ShapeId.Q1

    return None
