# Contextualizer Benchmark v1 Report

- Mode: `live-model`
- Split: `dev`
- Generated at: `2026-10-07T16:33:59.507802+00:00`
- Cases in scope: 30
- Cases evaluated: 30
- Input boundary: recent user/assistant history plus the current query
- Output boundary: standaloneQuery only; no Router, Gateway, RAG, Tool, or database

> N/A means the run did not observe the data needed for that metric. It is not a pass.
> Normalized String Match is auxiliary and never decides Context Resolution Accuracy.

## Category counts

| Category | Cases |
| --- | ---: |
| action_continuation | 4 |
| already_standalone | 3 |
| entity_ellipsis | 4 |
| entity_switch | 4 |
| multi_entity_ambiguity | 3 |
| no_history_ambiguity | 3 |
| pronoun_reference | 5 |
| user_correction | 4 |

## Metrics

| Metric | Result |
| --- | ---: |
| Context Resolution Accuracy | 86.67% (26/30) |
| Entity Resolution Accuracy | 90.00% (27/30) |
| Intent Preservation Accuracy | 93.33% (28/30) |
| Quantity Preservation Accuracy | 100.00% (8/8) |
| Clarification Accuracy | 90.00% (27/30) |
| Normalized String Match (auxiliary) | 75.86% (22/29) |
| Hallucinated Entity Rate | 0.00% (0/29) |
| Unsupported Fact Injection Rate | 0.00% (0/29) |

## Failures

- Failed case IDs: ctx_entity_ellipsis_001, ctx_entity_ellipsis_002, ctx_multi_entity_ambiguity_002, ctx_multi_entity_ambiguity_003
- Failure distribution: CLARIFICATION_MISSED=2, ENTITY_RESOLUTION_ERROR=2, INTENT_CHANGED=1, MODEL_OUTPUT_INVALID=1

No query, history, prompt, raw provider response, or expected answer is copied here.
