# Tool Selection + Sequential Replanning Benchmark v1 Report

- Mode: `live-model-local-fixture`
- Split: `dev`
- Validator version: `3`
- Production Agent source fingerprint: `718284d53e2f3f40b6bfd3ab8a7b261b150b0fb9b336918d95710ad97931c698`
- Dataset Manifest SHA-256: `5300badec340c6cf74dc193e8c7a690f7d43173f2995e062b25accf2cc574603`
- Generated at: `2026-10-09T05:03:43.889452+00:00`
- Cases in scope: 30
- Cases evaluated: 30
- Allowed production Tools: search_menu, list_available_drinks, get_dish_detail
- Side-effect Tools: forbidden

> N/A means this run did not observe the data required for the metric. It is not a pass.
> Validation-only mode checks frozen artifacts and performs no model or network call.

## Category counts

| Category | Cases |
| --- | ---: |
| no_premature_parallelism | 3 |
| no_tool_needed | 4 |
| sequential_replanning | 6 |
| single_tool_selection | 9 |
| tool_argument_accuracy | 6 |
| tool_empty_or_failure | 2 |

## Metrics

| Metric | Result |
| --- | ---: |
| Tool Selection Accuracy | 100.00% (26/26) |
| Tool Argument Accuracy | 100.00% (26/26) |
| Required Tool Call Accuracy | 100.00% (30/30) |
| Sequential Replanning Accuracy | 100.00% (8/8) |
| Tool Result Utilization Accuracy | 56.00% (14/25) |
| Final Answer Consistency | 62.07% (18/29) |
| Trace Contract Accuracy | 100.00% (30/30) |
| Unnecessary Tool Call Rate | 3.33% (1/30) |
| Premature Parallel Call Rate | 0.00% (0/11) |
| Unauthorized Tool Call Rate | 0.00% (0/30) |

## Failures

- Failed case IDs: tool_single_tool_selection_002, tool_single_tool_selection_004, tool_single_tool_selection_006, tool_single_tool_selection_007, tool_single_tool_selection_008, tool_single_tool_selection_009, tool_tool_argument_accuracy_002, tool_tool_argument_accuracy_005, tool_tool_argument_accuracy_006, tool_no_premature_parallelism_001, tool_no_premature_parallelism_002, tool_no_premature_parallelism_003
- Failure distribution: FINAL_ANSWER_CONTRADICTS_TOOL=11, TOOL_RESULT_IGNORED=11, UNNECESSARY_TOOL_CALL=1

No prompt, raw provider response, reasoning, credential, or full Tool payload is included.

## Validator v3: conservative scoring and review

- Cases requiring human review: 12/30
- Trigger reasons: ENTITY_REFERENCE_MISSING=1, INDETERMINATE_SEMANTIC_CHECK=11
- Safe branch codes: CONDITIONAL_SCOPE_UNRESOLVED=1, EMPTY_SEARCH_RECOGNIZED=6, ENTITY_ATTRIBUTION_UNRESOLVED=8, ENTITY_REFERENCE_MISSING=1, KEY_FACT_UNRECOGNIZED=1, NEGATION_SCOPE_RESOLVED=1, PRICE_FORMAT_RECOGNIZED=23, REVIEW_REQUIRED=11, STATUS_SYNONYM_RECOGNIZED=26, UNCERTAIN_ASSERTION=1
- REVIEW is not PASS and remains in every original applicable denominator.
- Machine-detected failure is not a human-verified semantic error. PASS is bounded rule acceptance.
- Validator changes are scoring-contract changes, not Agent capability improvements.
- UNNECESSARY_TOOL_CALL measures frozen strict budget excess, not necessarily product uselessness.

| Answer metric | Applicable | PASS | Machine-Detected Failure Count | Requires Human Review Count | Conservative Automatic Pass Rate | Determinate Check Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| tool_result_utilization_accuracy | 25 | 14 | 0 | 11 | 56.00% | 56.00% |
| final_answer_consistency | 29 | 18 | 0 | 11 | 62.07% | 62.07% |

## Dev same-output shadow scoring

- Primary Validator: 3; Shadow Validator: 2
- Both scorers consume the identical in-memory observations from one model execution per case.
- No raw answer is persisted. Separate applicable denominators are retained.

| Shadow metric | Result |
| --- | ---: |
| Tool Selection Accuracy | 100.00% (26/26) |
| Tool Argument Accuracy | 100.00% (26/26) |
| Required Tool Call Accuracy | 100.00% (30/30) |
| Sequential Replanning Accuracy | 100.00% (8/8) |
| Tool Result Utilization Accuracy | 32.00% (8/25) |
| Final Answer Consistency | 41.38% (12/29) |
| Trace Contract Accuracy | 100.00% (30/30) |
| Unnecessary Tool Call Rate | 3.33% (1/30) |
| Premature Parallel Call Rate | 0.00% (0/11) |
| Unauthorized Tool Call Rate | 0.00% (0/30) |

| Answer metric | Same-output transitions |
| --- | --- |
| tool_result_utilization_accuracy | both_na=5, both_pass=8, both_review=9, primary_new_review=2, shadow_review_to_primary_pass=6 |
| final_answer_consistency | both_na=1, both_pass=12, both_review=9, primary_new_review=2, shadow_review_to_primary_pass=6 |
