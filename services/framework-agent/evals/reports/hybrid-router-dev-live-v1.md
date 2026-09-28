# agent-benchmark-v1 Report

- Mode: `hybrid-router-live-model`
- Generated at: `2026-09-28T09:17:35.426238+00:00`
- Cases in scope: 80
- Dev / Holdout: 80 / 0
- Snapshot assumptions: Dev labels only; Router receives the post-contextualization query

> N/A means this run did not observe the data required for that metric. It is not a pass.
> No single Overall Accuracy is reported; metrics keep their separate denominators.

## Category counts

| Category | Cases |
| --- | ---: |
| action | 13 |
| menu | 17 |
| multi_turn | 12 |
| rag | 17 |
| safety | 13 |
| smalltalk | 8 |

## Metrics

| Metric | Result |
| --- | ---: |
| Route Accuracy | 100.00% (80/80) |
| Menu Fact Accuracy | N/A |
| Tool Selection Accuracy | N/A |
| Sequential Replanning Success Rate | N/A |
| RAG Answerability Accuracy | N/A |
| RAG Retrieval Hit@3 | N/A |
| Grounded Answer Rate | N/A |
| Context Resolution Accuracy | N/A |
| Multi-turn Route Accuracy | 100.00% (12/12) |
| Multi-turn Task Success Rate | N/A |
| PendingAction Validity Rate | N/A |
| Safety Rejection Rate | N/A |
| Unsupported Claim Rate | N/A |
| Unauthorized Side-effect Rate | N/A |
| Secret Leakage Rate | N/A |
| Unsafe Proposal Rate | N/A |

## Failures

- Failed case IDs: none
- Unauthorized side effect observed: no
- Secret leakage observed: no

| Failure taxonomy | Count |
| --- | ---: |
| none | 0 |

## Most common failures

No failures were observed in the fields evaluated by this run.

## Interpretation boundary

This report covers only fields actually observed by the selected mode. Deterministic-offline mode does not call Qwen, Gateway, uniCloud, RAG, or a database; model-dependent metrics remain N/A.

## Hybrid Router coverage

- Hybrid routes observed: 80/80
- Qwen was eligible only when deterministic rules returned unresolved.
- This command does not call Gateway, uniCloud, Tools, RAG, or a database.
