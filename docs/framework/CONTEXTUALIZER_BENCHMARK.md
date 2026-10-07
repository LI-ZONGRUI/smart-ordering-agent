# Contextualizer Benchmark v1

## Responsibility and current workflow

The Contextualizer has one narrow responsibility: use bounded recent user/assistant text to rewrite
a context-dependent current user message into a concise standalone query in the user's language. It
must not answer, perform menu/RAG/action work, create a `pendingAction`, or execute a transaction.

`FrameworkWorkflow.run` adds the current `HumanMessage` to graph state. The state reducer keeps the
latest eight top-level user/assistant messages. `contextualize_query` removes that current message
before calling the resolver, so the production model receives at most seven historical messages
plus the current query. Stateless calls have no history. Confirmations such as `确认` bypass
contextualization, and `needs_contextualization` currently limits model use to recognized ambiguous
follow-up forms with history. Bypassed queries become `resolved_query` unchanged.

The Qwen resolver sends a system prompt, the supplied history, and the current query. Its unchanged
structured output contract requires exactly one `standalone_query` string of 1–200 characters and
no extra fields. The compatibility parser accepts exactly three shapes under that same schema:

1. One normalized LangChain Tool Call named `return_standalone_query`.
2. One raw OpenAI-compatible function call with JSON arguments and the same function name.
3. Strict JSON string content containing only `standalone_query`.

Malformed arguments, multiple/wrong Tool Calls, free text, empty output, extra fields, invalid
message types, transport failures, and provider failures fail closed. The public resolver maps them
to `FRAMEWORK_CONTEXT_FAILED` without returning prompts, history, raw model content, or provider
details.

After successful rewriting, Router receives `resolved_query` and selects one of the graph's routes.
That is a separate responsibility. Router Benchmark Multi-turn Route Accuracy measures route
classification on a query that has already been contextualized; it cannot establish whether the
entity, intent, quantity, correction, or ambiguity was resolved correctly. Therefore:

```text
Multi-turn Route Accuracy != Context Resolution Accuracy
```

## Dataset and split

The standalone suite lives in `services/framework-agent/evals/contextualizer/`. It contains 40
business-language cases with distinct phenomena:

| Category | Cases | Purpose |
| --- | ---: | --- |
| `pronoun_reference` | 6 | Resolve 它 / 这个 / 那个 / 这杯 / 这道菜 to the unique prior entity |
| `entity_ellipsis` | 6 | Restore the sole entity omitted from price, status, taste, or ingredient questions |
| `action_continuation` | 5 | Preserve prior entity and requested quantity without executing anything |
| `entity_switch` | 5 | Prefer an explicit new/current entity over the previously discussed entity |
| `user_correction` | 5 | Give the current correction priority, including quantity corrections |
| `multi_entity_ambiguity` | 4 | Avoid selecting one of multiple plausible historical entities |
| `no_history_ambiguity` | 5 | Keep an entityless request unresolved instead of inventing a dish |
| `already_standalone` | 4 | Preserve entity, intent, quantity, and modifiers in an independent query |

The fixed split is 30 Dev and 10 Holdout. Holdout was authored and SHA-256-frozen before any
production Contextualizer work in this phase. Its content was not reviewed after freezing and was
not evaluated. Development must use Dev only. Automated Holdout integrity tests may verify schema,
counts, projection equality, immutability, and hash without printing cases.

## Case schema

Every JSONL case contains:

```json
{
  "id": "ctx_entity_ellipsis_001",
  "category": "entity_ellipsis",
  "split": "dev",
  "history": [{"role": "user", "content": "..."}],
  "query": "...",
  "expected": {
    "resolvedEntity": "...",
    "intent": "price",
    "quantity": null,
    "requiresClarification": false,
    "allowedStandaloneMeaning": ["..."],
    "forbiddenEntities": [],
    "mustPreserveFacts": [],
    "mustNotInventFacts": []
  }
}
```

`allowedStandaloneMeaning` provides examples for an auxiliary normalized comparison. It is never
sent to Qwen and exact string equality is not the primary judge.

## Metrics and deterministic validators

The report keeps separate denominators for:

- Context Resolution Accuracy
- Entity Resolution Accuracy
- Intent Preservation Accuracy
- Quantity Preservation Accuracy
- Clarification Accuracy
- Hallucinated Entity Rate
- Unsupported Fact Injection Rate
- Normalized String Match (auxiliary)

The primary context metric combines deterministic entity, intent, applicable quantity,
clarification, required-fact preservation, entity hallucination, and unsupported-fact checks.
Because production outputs only a string, required clarification accepts either an explicit request
to disambiguate or a safe unchanged unresolved expression that does not choose an entity. This does
not alter the production contract.

The validator uses case expectations, a fixed entity lexicon, intent/quantity patterns, forbidden
entities, required facts, and prohibited/new fact markers. It does not use a second LLM. A language
phenomenon outside the deterministic lexicon may be N/A or require human review; the system must not
invent accuracy. Normalized String Match is diagnostic only and cannot turn a semantic failure into
a pass or reject a valid paraphrase.

Failures are classified as `ENTITY_RESOLUTION_ERROR`, `ENTITY_HALLUCINATION`,
`ENTITY_SWITCH_ERROR`, `CORRECTION_IGNORED`, `INTENT_CHANGED`, `QUANTITY_CHANGED`,
`CLARIFICATION_MISSED`, `FACT_PRESERVATION_ERROR`, `UNSUPPORTED_FACT_INJECTION`,
`OUTPUT_CONTRACT_ERROR`, or `MODEL_OUTPUT_INVALID`. One case may have one primary and multiple
secondary failures.

## Live boundary and commands

Imports and pytest are offline. The default runner validates Dev and renders N/A for unobserved
model metrics. A live run constructs Qwen only when both `--live-model` and `--confirm-live` are
present. Selecting Holdout independently requires `--confirm-holdout`. The runner calls neither
Router nor LangGraph and has no Gateway, uniCloud, RAG, Tool, or database path.

The future first real Dev baseline command is:

```bash
cd services/framework-agent
PYTHONPATH=. .venv/bin/python -m evals.contextualizer.runner \
  --live-model --confirm-live \
  --report evals/contextualizer/reports/dev-live-v1.md
```

No real Dev or Holdout model run occurred while building v1. Production Contextualizer Prompt,
parsing, routing, and graph behavior remain unchanged.

## Limitations

- V1 is a focused 40-case Chinese ordering-language benchmark, not a general discourse benchmark.
- Deterministic intent and entity recognition can miss valid novel paraphrases and should then be
  extended through a new benchmark version using Dev evidence, never frozen Holdout tuning.
- The production output has no explicit clarification field, so clarification must be inferred from
  language or safely retained ambiguity.
- The hash freeze is repository/process governance rather than an external secret benchmark
  service.
