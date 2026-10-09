# Tool Selection + Sequential Replanning Benchmark v1 Report

- Mode: `live-model-local-fixture`
- Split: `holdout`
- Validator version: `3`
- Production Agent source fingerprint: `718284d53e2f3f40b6bfd3ab8a7b261b150b0fb9b336918d95710ad97931c698`
- Dataset Manifest SHA-256: `5300badec340c6cf74dc193e8c7a690f7d43173f2995e062b25accf2cc574603`
- Generated at: `2026-10-09T05:30:00.320213+00:00`
- Cases in scope: 10
- Cases evaluated: 10
- Allowed production Tools: search_menu, list_available_drinks, get_dish_detail
- Side-effect Tools: forbidden

> N/A means this run did not observe the data required for the metric. It is not a pass.
> Validation-only mode checks frozen artifacts and performs no model or network call.

## Category counts

| Category | Cases |
| --- | ---: |
| no_premature_parallelism | 1 |
| no_tool_needed | 1 |
| sequential_replanning | 2 |
| single_tool_selection | 3 |
| tool_argument_accuracy | 2 |
| tool_empty_or_failure | 1 |

## Metrics

| Metric | Result |
| --- | ---: |
| Tool Selection Accuracy | 100.00% (9/9) |
| Tool Argument Accuracy | 100.00% (9/9) |
| Required Tool Call Accuracy | 100.00% (10/10) |
| Sequential Replanning Accuracy | 100.00% (3/3) |
| Tool Result Utilization Accuracy | 77.78% (7/9) |
| Final Answer Consistency | 80.00% (8/10) |
| Trace Contract Accuracy | 100.00% (10/10) |
| Unnecessary Tool Call Rate | 0.00% (0/10) |
| Premature Parallel Call Rate | 0.00% (0/4) |
| Unauthorized Tool Call Rate | 0.00% (0/10) |

## Failures

- Failed case IDs: tool_tool_argument_accuracy_008, tool_no_premature_parallelism_004
- Failure distribution: FINAL_ANSWER_CONTRADICTS_TOOL=2, TOOL_RESULT_IGNORED=2

No prompt, raw provider response, reasoning, credential, or full Tool payload is included.

## Validator v3: conservative scoring and review

- Cases requiring human review: 2/10
- Trigger reasons: INDETERMINATE_SEMANTIC_CHECK=2
- Safe branch codes: EMPTY_SEARCH_RECOGNIZED=2, ENTITY_ATTRIBUTION_UNRESOLVED=2, PRICE_FORMAT_RECOGNIZED=8, REVIEW_REQUIRED=2, STATUS_SYNONYM_RECOGNIZED=10
- REVIEW is not PASS and remains in every original applicable denominator.
- Machine-detected failure is not a human-verified semantic error. PASS is bounded rule acceptance.
- Validator changes are scoring-contract changes, not Agent capability improvements.
- UNNECESSARY_TOOL_CALL measures frozen strict budget excess, not necessarily product uselessness.

| Answer metric | Applicable | PASS | Machine-Detected Failure Count | Requires Human Review Count | Conservative Automatic Pass Rate | Determinate Check Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| tool_result_utilization_accuracy | 9 | 7 | 0 | 2 | 77.78% | 77.78% |
| final_answer_consistency | 10 | 8 | 0 | 2 | 80.00% | 80.00% |
