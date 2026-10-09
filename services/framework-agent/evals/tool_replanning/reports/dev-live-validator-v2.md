# Tool Selection + Sequential Replanning Benchmark v1 Report

- Mode: `live-model-local-fixture`
- Split: `dev`
- Validator version: `2`
- Production Agent source fingerprint: `718284d53e2f3f40b6bfd3ab8a7b261b150b0fb9b336918d95710ad97931c698`
- Generated at: `2026-10-09T03:46:42.329182+00:00`
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
| Tool Result Utilization Accuracy | 40.00% (10/25) |
| Final Answer Consistency | 48.28% (14/29) |
| Trace Contract Accuracy | 100.00% (30/30) |
| Unnecessary Tool Call Rate | 3.33% (1/30) |
| Premature Parallel Call Rate | 0.00% (0/11) |
| Unauthorized Tool Call Rate | 0.00% (0/30) |

## Failures

- Failed case IDs: tool_single_tool_selection_002, tool_single_tool_selection_004, tool_single_tool_selection_005, tool_single_tool_selection_006, tool_single_tool_selection_007, tool_single_tool_selection_008, tool_single_tool_selection_009, tool_tool_argument_accuracy_001, tool_tool_argument_accuracy_002, tool_tool_argument_accuracy_003, tool_sequential_replanning_001, tool_sequential_replanning_005, tool_no_premature_parallelism_001, tool_no_premature_parallelism_002, tool_no_premature_parallelism_003
- Failure distribution: FINAL_ANSWER_CONTRADICTS_TOOL=15, TOOL_RESULT_IGNORED=15, UNNECESSARY_TOOL_CALL=1

No prompt, raw provider response, reasoning, credential, or full Tool payload is included.

## Validator v2 review diagnostics

- Cases requiring human review: 14/30
- Trigger reasons: INDETERMINATE_SEMANTIC_CHECK=14, STATUS_MISMATCH=2
- Indeterminate eligible answer checks count as failed, not N/A; denominators are unchanged.
- Utilization and final consistency share fact checks; overlapping failures are not independent Agent faults.
- Extra Tool calls still fail the frozen strict budget, including plausible detail calls flagged for review.
- Changes from Validator v1 are scoring-contract corrections, not proof of improved Agent capability.
