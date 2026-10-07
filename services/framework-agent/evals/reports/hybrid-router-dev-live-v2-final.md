# agent-benchmark-v1 Report

- Mode: `hybrid-router-live-model`
- Generated at: `2026-10-07T14:01:32.210254+00:00`
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

- Split: `dev`
- Hybrid routes observed: 80/80
- Deterministic rule coverage: 74/80
- Deterministic rule case IDs: menu_001, menu_002, menu_003, menu_004, menu_005, menu_006, menu_007, menu_008, menu_009, menu_010, menu_013, menu_014, menu_015, menu_016, menu_017, rag_001, rag_002, rag_003, rag_004, rag_005, rag_006, rag_007, rag_008, rag_009, rag_010, rag_011, rag_012, rag_013, rag_014, rag_015, rag_016, rag_017, action_001, action_002, action_003, action_004, action_005, action_006, action_007, action_008, action_009, action_010, action_011, action_012, action_013, multi_turn_01_01, multi_turn_01_02, multi_turn_01_03, multi_turn_01_04, multi_turn_02_01, multi_turn_02_02, multi_turn_02_03, multi_turn_02_04, multi_turn_03_01, multi_turn_03_02, multi_turn_03_03, multi_turn_03_04, safety_001, safety_002, safety_003, safety_004, safety_005, safety_006, safety_007, safety_008, safety_009, safety_010, safety_011, safety_012, safety_013, smalltalk_001, smalltalk_002, smalltalk_003, smalltalk_005
- Semantic Router coverage: 6/80
- Semantic Router case IDs: menu_011, menu_012, smalltalk_004, smalltalk_006, smalltalk_007, smalltalk_008
- Qwen was eligible only when deterministic rules returned unresolved.
- This command does not call Gateway, uniCloud, Tools, RAG, or a database.

## Route failure details

| Case ID | Category | Allowed routes | Actual route | Routing source | Failures |
| --- | --- | --- | --- | --- | --- |
| none | — | — | — | — | — |
