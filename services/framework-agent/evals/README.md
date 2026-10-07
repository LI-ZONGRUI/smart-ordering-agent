# Agent Benchmark Evaluation Framework

`agent-benchmark-v1` is an offline-first, versioned benchmark for the complete ordering assistant.
It does not replace the legacy 12-case RAG evaluation and does not change production prompts,
routing, Tools, RAG, actions, or transactions.

## Layout

```text
evals/
  datasets/
    agent-benchmark-v1.jsonl   # canonical 120-case source
    dev.jsonl                  # 80-case development projection
    holdout.jsonl              # frozen 40-case projection
    golden-e2e.jsonl           # 25-case explicit live subset
    benchmark-manifest-v1.json # counts and SHA-256 freeze manifest
  reports/
    offline-dev-baseline-v1.md
  schema.py
  validators.py
  metrics.py
  report.py
  runner.py
```

The canonical source contains 25 Menu, 25 RAG, 20 Action, 20 Multi-turn, 20 Safety, and 10
Smalltalk/Ambiguous cases. Multi-turn contains five complete conversations of four turns; a
conversation never crosses the Dev/Holdout boundary. Holdout content is frozen by SHA-256 and must
not be used for Prompt, Router, or Tool-description tuning.

## Case and observation contracts

Every case has `benchmarkVersion`, unique `id`, `category`, `split`, `goldenE2E`, an input
`query/history`, and machine-checkable expectations. Expectations cover allowed routes, Tool
selection/order, sequential behavior, required/forbidden answer text, snapshot menu facts, RAG
answerability and relevant knowledge IDs, strict pending action, side effects, safety rejection,
resolved entity, and expected standalone query.

An evaluation observation may provide only measured fields such as route, resolved query, sanitized
trace, answer, menu facts, answerability, retrieval/evidence IDs, evidence texts, unsupported claims,
pending action, side effects, and safety rejection. Full vectors and unknown internal fields fail
the output contract. Expected values are never sent to a model.

## Three levels

1. **Deterministic Offline** validates the dataset, frozen files, production Router contract,
   schemas, trace order, pending actions, metrics, reports, and safety validators. It performs no
   network request. Metrics without observations are `N/A`, never implicit passes.
2. **LLM Integration** accepts captured observations from a replaceable model interface and fixed
   Gateway fixtures. Model-dependent Tool selection, contextualization, replanning, and answer
   behavior can then be scored without changing the dataset.
3. **Golden E2E** contains 25 representative cases for real Qwen → LangChain/LangGraph → HMAC
   Gateway → uniCloud acceptance. It requires two explicit CLI flags and a separately configured
   service. Importing modules, pytest, Node tests, and the default runner cannot activate it.

## Commands

From `services/framework-agent`:

```bash
# Default: deterministic and fully offline
PYTHONPATH=. .venv/bin/python -m evals.runner

# Holdout is never run implicitly
PYTHONPATH=. .venv/bin/python -m evals.runner \
  --split holdout --confirm-holdout \
  --report /tmp/agent-benchmark-holdout.md

# Score previously captured safe observations
PYTHONPATH=. .venv/bin/python -m evals.runner \
  --observations /path/to/safe-observations.jsonl \
  --report evals/reports/observation-report.md

# Explicit real Golden E2E only; starts no server and never persists conversation tokens
FRAMEWORK_AGENT_EVAL_BASE_URL=http://127.0.0.1:8000 \
PYTHONPATH=. .venv/bin/python -m evals.runner \
  --live-model --confirm-live \
  --report evals/reports/golden-live-report.md
```

Before Golden E2E, the operator must deliberately start the Framework Agent with its ignored local
model/Gateway configuration. A live report must record run time and current menu assumptions because
price and availability can differ from the frozen snapshot. Do not commit raw live responses,
tokens, signatures, nonces, secrets, or private URLs.

## Metrics and failures

Metrics are reported separately: Route Accuracy, Menu Fact Accuracy, Tool Selection Accuracy,
Sequential Replanning Success, RAG Answerability, Retrieval Hit@3, Grounded Answer, Unsupported
Claim, Context Resolution, Multi-turn Route/Task Success, PendingAction Validity, Safety Rejection,
Unsafe Proposal, Unauthorized Side-effect, and Secret Leakage. There is no primary “Overall
Accuracy”. Zero denominators render as `N/A`.

Failure taxonomy supports primary plus secondary failures: router, context, Tool selection/order/
over-calling, retrieval, answerability, unsupported claim, pending action, safety rejection,
unauthorized side effect, output contract, answer format, and secret leakage.

Sequential replanning requires:

```text
tool_call A → tool_result A → later tool_call B → tool_result B
```

`tool_call A → tool_call B → result A → result B` is explicitly rejected as same-decision parallel
calling. Grounding validation uses structured retrieval/evidence IDs, server evidence text and
explicit unsupported-claim observations; another LLM is not the default judge.

## Versioning

V1 is frozen by `benchmark-manifest-v1.json`. Do not silently edit Dev or Holdout. A factual
correction requires an explicit manifest revision and changelog entry; semantic expansion should
create V2. The full Holdout answer key must not be copied into README, prompts, or Tool descriptions.
The default Runner selects only Dev; Holdout or all-case evaluation requires `--confirm-holdout`.

## Hybrid Router Dev comparison and Router v2

The historical `offline-dev-baseline-v1.md` remains the pre-change Rule Router result: 68/80. The
new Hybrid Router uses a separate runner and report so the baseline cannot be overwritten:

```bash
# Rules only; unresolved semantic cases remain N/A
PYTHONPATH=. .venv/bin/python -m evals.hybrid_router_runner

# Explicit real Qwen classification on Dev
PYTHONPATH=. .venv/bin/python -m evals.hybrid_router_runner \
  --live-model --confirm-live

# Frozen Holdout: both Holdout access and the real model require separate confirmation
PYTHONPATH=. .venv/bin/python -m evals.hybrid_router_runner \
  --split holdout --confirm-holdout \
  --live-model --confirm-live \
  --report evals/reports/hybrid-router-holdout-live-v1.md
```

The default remains the 80-case Dev split. The frozen 40-case Holdout cannot run without
`--confirm-holdout`; live Qwen classification independently requires `--live-model --confirm-live`.
Dev and Holdout share the same Hybrid Router, validators, metrics, and report implementation. Live
mode calls Qwen only for queries unresolved by deterministic rules; it does not call Gateway,
uniCloud, Tools, RAG, or a database.

Router v2 preserves that runner and strict five-route output contract. Its deterministic layer first
keeps genuinely unsupported transaction/destructive/internal operations on `unsupported_action`, then
routes supported main intent without treating future-action language or unsafe authorization modifiers
as route ownership. Live menu facts and exploration belong to `menu_query`; stable knowledge belongs
to `knowledge_query` independently of answerability; supported cart proposals belong to `action_query`
without gaining execution authority. Independently authored unit regressions cover these boundaries and
entity-keyword collisions.

Holdout v1 has already been evaluated and analyzed; it is now a regression/failure-analysis set.
Any future report from it must be named `holdout-v1-regression`, not an unseen/generalization result.
The independent `holdout-v2.jsonl` is a 40-case route-only set frozen by
`holdout-v2-manifest.json` before Router v2 implementation. The current runner does not select v2,
and v2 must not be inspected or run during Router development; only metadata freeze tests may run.
New Hybrid reports include a failure
table containing only case ID, category, allowed routes, actual route, routing source
(`deterministic`, `semantic` or `fallback`) and failure taxonomy. Neither raw model output nor
user query/history is written to that table.
