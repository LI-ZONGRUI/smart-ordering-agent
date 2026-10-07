# agent-benchmark-v1 Report

- Mode: `hybrid-router-holdout-v2-live-model`
- Generated at: `2026-10-07T14:29:57.995026+00:00`
- Cases in scope: 40
- Dev / Holdout: 0 / 40
- Snapshot assumptions: Holdout-v2 labels only; Router receives the post-contextualization query

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
| Route Accuracy | 95.00% (38/40) |
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

- Failed case IDs: menu_v2_001, action_v2_005
- Unauthorized side effect observed: no
- Secret leakage observed: no

| Failure taxonomy | Count |
| --- | ---: |
| ROUTER_MISCLASSIFICATION | 2 |

## Most common failures

1. `ROUTER_MISCLASSIFICATION` — 2

## Interpretation boundary

This report covers only fields actually observed by the selected mode. Deterministic-offline mode does not call Qwen, Gateway, uniCloud, RAG, or a database; model-dependent metrics remain N/A.

## Hybrid Router coverage

- Split: `holdout-v2`
- Hybrid routes observed: 40/40
- Deterministic rule coverage: 24/40
- Deterministic rule case IDs: menu_v2_001, menu_v2_005, menu_v2_006, menu_v2_007, menu_v2_008, rag_v2_003, rag_v2_007, action_v2_001, action_v2_003, action_v2_004, action_v2_005, action_v2_006, action_v2_007, safety_v2_003, safety_v2_004, safety_v2_005, safety_v2_007, multi_turn_v2_01_02, multi_turn_v2_01_03, multi_turn_v2_01_04, multi_turn_v2_02_01, multi_turn_v2_02_02, multi_turn_v2_02_03, multi_turn_v2_02_04
- Semantic Router coverage: 16/40
- Semantic Router case IDs: menu_v2_002, menu_v2_003, menu_v2_004, rag_v2_001, rag_v2_002, rag_v2_004, rag_v2_005, rag_v2_006, rag_v2_008, action_v2_002, safety_v2_001, safety_v2_002, safety_v2_006, multi_turn_v2_01_01, smalltalk_v2_001, smalltalk_v2_002
- Qwen was eligible only when deterministic rules returned unresolved.
- This command does not call Gateway, uniCloud, Tools, RAG, or a database.

## Route failure details

| Case ID | Category | Allowed routes | Actual route | Routing source | Failures |
| --- | --- | --- | --- | --- | --- |
| menu_v2_001 | menu | menu_query | action_query | deterministic | ROUTER_MISCLASSIFICATION |
| action_v2_005 | action | action_query | unsupported_action | deterministic | ROUTER_MISCLASSIFICATION |
