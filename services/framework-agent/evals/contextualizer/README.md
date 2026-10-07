# Contextualizer Benchmark v1

This benchmark is independent from the Router benchmark. It supplies recent user/assistant history
plus the current user query and measures whether the Contextualizer boundary returns a safe,
semantically standalone query. It does not classify a route, answer the user, call a Tool, create a
`pendingAction`, or contact Gateway, uniCloud, RAG, or a database.

The Router benchmark instead receives a post-contextualization query and measures route
classification. Its Multi-turn Route Accuracy is therefore not Context Resolution Accuracy.

## Layout and frozen data

```text
evals/contextualizer/
  datasets/
    contextualizer-benchmark-v1.jsonl
    dev.jsonl
    holdout.jsonl
    manifest.json
    CHANGELOG.md
  runner.py
  metrics.py
  validators.py
  report.py
  schema.py
```

V1 contains 40 cases: 30 Dev and 10 frozen Holdout. The category totals are 6 pronoun references,
6 entity ellipses, 5 action continuations, 5 entity switches, 5 user corrections, 4 multi-entity
ambiguities, 5 no-history ambiguities, and 4 already-standalone queries. Cases test distinct
language phenomena rather than dish-name substitution.

`manifest.json` SHA-256-freezes the canonical dataset and both projections. Holdout was created and
frozen before any production Contextualizer change. After freezing, its content must not be
manually reviewed, copied into prompts, used to change parsing, or run for development tuning.
Automated metadata, schema, projection, mutation, and hash integrity checks are allowed.

## Contract and deterministic scoring

Each case contains `id`, `category`, `split`, `history`, `query`, and expectations for resolved
entity, intent, applicable quantity, clarification, allowed semantic examples, forbidden entities,
facts that must survive, and facts that must not be invented. Expected standalone examples never
enter model input.

The production output remains one `standalone_query` string. The evaluator derives entity, intent,
quantity, and clarification signals deterministically. Because the production contract has no
clarification boolean, a required clarification passes either when the output explicitly asks which
entity the user means or when it safely keeps the original unresolved reference without choosing an
entity. Normalized String Match is auxiliary only. It never decides semantic correctness.

The metrics are Context Resolution Accuracy, Entity Resolution Accuracy, Intent Preservation
Accuracy, Quantity Preservation Accuracy, Clarification Accuracy, Hallucinated Entity Rate,
Unsupported Fact Injection Rate, and auxiliary Normalized String Match. Separate denominators are
reported and unavailable observations remain N/A. No second LLM is used as a judge.

Deterministic validation is intentionally conservative. It recognizes the entities, intent phrases,
quantities, ambiguity patterns, and fact classes represented by v1. A novel paraphrase outside that
lexicon can require manual review; the runner does not fabricate a score for an invalid or missing
model output.

## Runner boundaries

From `services/framework-agent`:

```bash
# Default: validate the frozen Dev dataset and emit an N/A report; no model is constructed
PYTHONPATH=. .venv/bin/python -m evals.contextualizer.runner

# Score previously captured, sanitized observations without a model call
PYTHONPATH=. .venv/bin/python -m evals.contextualizer.runner \
  --observations /path/to/contextualizer-observations.jsonl \
  --report /tmp/contextualizer-observations.md

# Future first real Dev baseline: Qwen Contextualizer only
PYTHONPATH=. .venv/bin/python -m evals.contextualizer.runner \
  --live-model --confirm-live \
  --report evals/contextualizer/reports/dev-live-v1.md

# Future Holdout evaluation requires an independent gate as well
PYTHONPATH=. .venv/bin/python -m evals.contextualizer.runner \
  --split holdout --confirm-holdout \
  --live-model --confirm-live \
  --report evals/contextualizer/reports/holdout-live-v1.md
```

Live mode exercises the production `needs_contextualization` gate and the production resolver. A
query bypassed by the gate is observed unchanged; an eligible query receives only its own history
and current query. The runner never supplies expected values and never invokes Router, LangGraph,
Gateway, uniCloud, RAG, Tools, or a database. Imports, pytest, and the default command cannot call
Qwen. A real Dev run is not included in this phase, so no current-model baseline is claimed.

## Failure taxonomy

- `ENTITY_RESOLUTION_ERROR`
- `ENTITY_HALLUCINATION`
- `ENTITY_SWITCH_ERROR`
- `CORRECTION_IGNORED`
- `INTENT_CHANGED`
- `QUANTITY_CHANGED`
- `CLARIFICATION_MISSED`
- `FACT_PRESERVATION_ERROR`
- `UNSUPPORTED_FACT_INJECTION`
- `OUTPUT_CONTRACT_ERROR`
- `MODEL_OUTPUT_INVALID`
