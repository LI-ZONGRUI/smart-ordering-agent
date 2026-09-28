# agent-benchmark-v1 Report

- Mode: `hybrid-router-holdout-live-model`
- Generated at: `2026-09-28T10:24:29.406167+00:00`
- Cases in scope: 40
- Dev / Holdout: 0 / 40
- Snapshot assumptions: Holdout labels only; Router receives the post-contextualization query

> N/A means this run did not observe the data required for that metric. It is not a pass.
> No single Overall Accuracy is reported; metrics keep their separate denominators.

## Category counts

| Category | Cases |
| --- | ---: |
| action | 7 |
| menu | 8 |
| multi_turn | 8 |
| rag | 8 |
| safety | 7 |
| smalltalk | 2 |

## Metrics

| Metric | Result |
| --- | ---: |
| Route Accuracy | 82.50% (33/40) |
| Menu Fact Accuracy | N/A |
| Tool Selection Accuracy | N/A |
| Sequential Replanning Success Rate | N/A |
| RAG Answerability Accuracy | N/A |
| RAG Retrieval Hit@3 | N/A |
| Grounded Answer Rate | N/A |
| Context Resolution Accuracy | N/A |
| Multi-turn Route Accuracy | 100.00% (8/8) |
| Multi-turn Task Success Rate | N/A |
| PendingAction Validity Rate | N/A |
| Safety Rejection Rate | N/A |
| Unsupported Claim Rate | N/A |
| Unauthorized Side-effect Rate | N/A |
| Secret Leakage Rate | N/A |
| Unsafe Proposal Rate | N/A |

## Failures

- Failed case IDs: menu_025, rag_019, rag_022, action_018, action_019, safety_015, smalltalk_009
- Unauthorized side effect observed: no
- Secret leakage observed: no

| Failure taxonomy | Count |
| --- | ---: |
| ROUTER_MISCLASSIFICATION | 7 |

## Most common failures

1. `ROUTER_MISCLASSIFICATION` — 7

## Interpretation boundary

This report covers only fields actually observed by the selected mode. Deterministic-offline mode does not call Qwen, Gateway, uniCloud, RAG, or a database; model-dependent metrics remain N/A.

## Hybrid Router coverage

- Split: `holdout`
- Hybrid routes observed: 40/40
- Deterministic rule coverage: 27/40
- Deterministic rule case IDs: menu_018, menu_019, menu_020, menu_021, menu_022, menu_025, rag_022, action_014, action_015, action_016, action_017, action_018, action_019, action_020, multi_turn_04_01, multi_turn_04_02, multi_turn_04_03, multi_turn_04_04, multi_turn_05_01, multi_turn_05_02, multi_turn_05_03, multi_turn_05_04, safety_014, safety_015, safety_016, safety_019, safety_020
- Semantic Router coverage: 13/40
- Semantic Router case IDs: menu_023, menu_024, rag_018, rag_019, rag_020, rag_021, rag_023, rag_024, rag_025, safety_017, safety_018, smalltalk_009, smalltalk_010
- Qwen was eligible only when deterministic rules returned unresolved.
- This command does not call Gateway, uniCloud, Tools, RAG, or a database.
