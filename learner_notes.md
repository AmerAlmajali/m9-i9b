# Integration 9B — Learner Notes

Document your design choices and what you learned. The TA rubric
references this file directly — incomplete or perfunctory answers reduce
your score.

## 1. Intents you handled and how you classified them

Describe your `detect_shape` rules. Which question shapes were easy to
discriminate, which were ambiguous, and how did you handle the
ambiguities? Cite at least one specific question from
`data/eval_questions.jsonl` where two shapes were plausible candidates.


> I implemented `detect_shape` as a priority-ordered set of keyword and
> regex rules over the lowercased question text. Shapes with unique
> surface markers were straightforward: Q10 fires on `r"under \d+
> minutes"`, Q11 on the literal phrase "ingredients used in", Q13 on
> "or any subtype", and Q15 on "optionally tagged". These have no
> plausible overlap with other shapes.
>
> The trickiest ambiguity was between Q1, Q8, and Q14. All three can
> contain "use ginger" in the question text. I resolved it with strict
> priority ordering: Q14 ("but not") is tested first, then Q8 ("by
> author … that use"), and Q1 last. Without that ordering,
> "Find recipes that use ginger but not garlic" would mis-fire as Q1
> because "use ginger" matches the ingredient pattern.
>
> A second ambiguity is Q3 vs Q4 (and Q5 vs Q6). Both involve a cuisine
> name, but Q4/Q6 apply hierarchical `[:SUBCLASS_OF*0..]` traversal for
> broad categories like Asian or Chinese. I maintain a
> `HIERARCHICAL_CUISINES` set and check membership after finding the
> cuisine name — if it is in the set the classifier promotes to Q4/Q6,
> otherwise it stays at Q3/Q5. The concrete eval question
> "Find Asian recipes" is the case where both Q3 and Q4 are plausible:
> Q3 would do a direct `OF_CUISINE` match and silently miss all
> Sichuan, Japanese, and Thai descendants; Q4's `*0..` traversal is
> the correct choice.

## 2. A question that worked end-to-end

Pick one of the 15 canonical questions, walk through the pipeline:
what `detect_shape` returned, what `extract_slots` returned, the
compiled Cypher (with $param placeholders), the bound params dict, and
the rows the driver returned. Paste the actual CLI output.

> **Question:** "Find Italian recipes ranked by popularity"
>
> 1. `detect_shape` matched the "ranked by popularity" keyword and
>    found "Italian" in the cuisine vocabulary → returned `ShapeId.Q9`.
> 2. `extract_slots` scanned for a cuisine name → `{'cuisine': 'Italian'}`.
> 3. `compile_to_cypher` looked up `CANONICAL_CYPHER[Q9]` and returned
>    the template unchanged with the slots as params:
>
>    ```cypher
>    MATCH (r:Recipe)-[:OF_CUISINE]->(:Cuisine {name: $cuisine})
>    RETURN r.name AS recipe, r.popularityScore AS popularity
>    ORDER BY r.popularityScore DESC, r.name ASC
>    LIMIT 10
>    ```
>    Params: `{'cuisine': 'Italian'}`
>
> 4. The Neo4j driver bound `$cuisine` at execution time and returned:
>
>    ```
>    {'recipe': 'Risotto', 'popularity': 94}
>    {'recipe': 'Margherita Pizza', 'popularity': 83}
>    {'recipe': 'Carbonara #2', 'popularity': 82}
>    {'recipe': 'Carbonara', 'popularity': 78}
>    {'recipe': 'Lasagna #2', 'popularity': 72}
>    {'recipe': 'Margherita Pizza #2', 'popularity': 49}
>    {'recipe': 'Lasagna', 'popularity': 22}
>    {'recipe': 'Tiramisu', 'popularity': 21}
>    ```

## 3. A failure mode you diagnosed

Either a question that you initially mis-classified (and why), or an
adversarial / off-template question and what your `UnsupportedQueryError`
message told the caller. If you implemented Tier 3, you may also use a
case where the LLM emitted unsafe Cypher and your allowlist rejected it
— describe the prompt, the Cypher returned, and the clause that
triggered the rejection.

> **Off-template question:** "Tell me about pasta dishes from Rome"
>
> This question mentions a food concept ("pasta") and a place ("Rome")
> but neither matches the KG vocabulary — "pasta" is an ingredient name
> but appears without the required "use" or "with" cue, and "Rome" is
> not a Cuisine node. `detect_shape` returned `None` for both tests and
> the pipeline raised `UnsupportedQueryError`. The CLI printed to
> stderr:
>
> ```
> Question shape not supported: 'Tell me about pasta dishes from Rome'
> Supported shapes:
>   - q1: Find recipes that use <ingredient>
>   - q2: Find recipes by author <name>
>   ...
>   - q15: Find recipes optionally tagged with <technique>
> ```
>
> This is the correct fail-loud behavior: the caller sees exactly which
> 15 shapes are supported, the exit code is 1, and no empty result list
> is silently returned. The diagnostic signal is preserved — an
> integrator reading the error immediately knows whether to extend the
> mapper with a 16th shape or to rephrase the question.
>
> An earlier draft of the classifier used a bare ingredient-name scan
> (`any(ing in q for ing in INGREDIENTS)`), which would have
> mis-classified this question as Q1 because "pasta" is in the
> ingredient list. Adding the "use"/"with" cue requirement fixed the
> silent false-positive.

## 4. A design tradeoff between the deterministic mapper and the Tier 3 chain

When would you prefer the deterministic mapper over the LLM chain in
production, and vice versa? Cite a concrete dimension (latency,
auditability, schema-coverage cost, distribution-shift robustness,
operational risk) for each side. Both implementations are first-class —
your answer should reflect that, not pick a winner.

> **Prefer the deterministic mapper** when auditability is a hard
> requirement. Every Cypher string it emits is a static template stored
> in `shapes.py` — a compliance reviewer can read the file and confirm
> exactly what database paths are reachable from each question shape,
> without running anything. Latency is also deterministic: the mapper
> adds microseconds of Python overhead, not the 100–500 ms a local LLM
> inference call costs per token. For a bounded, well-understood question
> distribution (internal tooling, a kiosk, a regulated reporting
> surface), the mapper's schema-coverage cost — writing and testing one
> template per shape — is a one-time investment that pays off in
> predictability and zero operational dependency on an inference runtime.
>
> **Prefer the Tier 3 LLM chain** when the input distribution is open
> and genuinely unpredictable. A user who types "which authors tend to
> cook with both ginger and coconut milk?" is outside the 15-shape
> surface; the mapper raises `UnsupportedQueryError` and the user is
> stuck. A well-prompted LLM can synthesize a novel multi-hop Cypher
> query for that case without a new template being authored. The
> tradeoff is distribution-shift robustness: the LLM generalizes, but
> at the cost of requiring the allowlist as a safety layer, accepting
> non-deterministic outputs, and incurring inference latency on every
> call. Both are legitimate production choices — the deciding factor is
> whether the question distribution is bounded enough for templating to
> scale.