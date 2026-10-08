# Contextualizer Benchmark v1 Report

- Mode: `live-model`
- Split: `holdout`
- Generated at: `2026-10-08T06:56:00.357155+00:00`
- Cases in scope: 10
- Cases evaluated: 10
- Input boundary: recent user/assistant history plus the current query
- Output boundary: standaloneQuery only; no Router, Gateway, RAG, Tool, or database

> N/A means the run did not observe the data needed for that metric. It is not a pass.
> Normalized String Match is auxiliary and never decides Context Resolution Accuracy.

## Category counts

| Category | Cases |
| --- | ---: |
| action_continuation | 1 |
| already_standalone | 1 |
| entity_ellipsis | 2 |
| entity_switch | 1 |
| multi_entity_ambiguity | 1 |
| no_history_ambiguity | 2 |
| pronoun_reference | 1 |
| user_correction | 1 |

## Metrics

| Metric | Result |
| --- | ---: |
| Context Resolution Accuracy | 90.00% (9/10) |
| Entity Resolution Accuracy | 90.00% (9/10) |
| Intent Preservation Accuracy | 100.00% (10/10) |
| Quantity Preservation Accuracy | 100.00% (1/1) |
| Clarification Accuracy | 100.00% (10/10) |
| Normalized String Match (auxiliary) | 80.00% (8/10) |
| Hallucinated Entity Rate | 0.00% (0/10) |
| Unsupported Fact Injection Rate | 0.00% (0/10) |

## Failures

- Failed case IDs: ctx_entity_ellipsis_005
- Failure distribution: ENTITY_RESOLUTION_ERROR=1

No query, history, prompt, raw provider response, or expected answer is copied here.
