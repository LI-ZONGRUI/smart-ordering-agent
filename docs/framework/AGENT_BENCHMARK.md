# Agent Benchmark V1

## Why this benchmark exists

The project retains its legacy 12-case RAG generation evaluation because it records the historical
Evidence-first grounding baseline. That small set measures one subsystem. `agent-benchmark-v1`
adds a separate 120-case suite covering the full assistant boundary: deterministic routing, menu
Tool behavior, RAG, action proposals, multi-turn context, safety, and ambiguous requests.

This phase establishes the dataset and evaluation machinery. It does not change production Prompt,
LangGraph, LangChain, RAG, Native Agent, Gateway, cart, or order behavior. No real Qwen, Gateway,
uniCloud, or database call was made while creating the offline baseline.

## Fixed composition

| Category | Cases | Purpose |
| --- | ---: | --- |
| Menu | 25 | Exists/sold-out/missing, current price/status, drinks, detail, cautious empty search, sequential fallback |
| RAG | 25 | Verified descriptions/taste/ingredients, paraphrase, unsupported facts, misleading premises and refusal |
| Action | 20 | Valid quantities, unavailable/missing dishes, malformed quantities, forged price/authorization, proposal-only behavior |
| Multi-turn | 20 | Five four-turn conversations with pronouns, omissions, entity switch, correction and action continuation |
| Safety | 20 | Order/payment/refund/cart writes, text confirmation, injection, secrets, internals and forged authority |
| Smalltalk/Ambiguous | 10 | Greeting and underspecified intent without forcing one exact answer |

The split is 80 Dev and 40 frozen Holdout. Whole multi-turn conversations stay in one split. Twenty-
five representative cases form the Golden E2E subset; it is a projection of the canonical dataset,
not a separately authored answer key.

## Stable schema

Each JSONL record contains:

```json
{
  "benchmarkVersion": 1,
  "id": "menu_001",
  "category": "menu",
  "split": "dev",
  "goldenE2E": true,
  "input": { "query": "...", "history": [] },
  "expected": {
    "allowedRoutes": ["menu_query"],
    "tools": {
      "required": ["search_menu"],
      "forbidden": [],
      "ordered": [],
      "sequential": false,
      "maxCalls": 2
    },
    "mustContain": [],
    "mustNotContain": [],
    "menuFacts": [],
    "rag": null,
    "pendingAction": null,
    "sideEffects": {
      "cartMutation": false,
      "orderWrite": false,
      "payment": false
    },
    "safeRejection": null,
    "resolvedEntity": null,
    "expectedResolvedQuery": null
  }
}
```

The machine validator requires exact v1 keys, known routes/categories, unique IDs and queries,
complete expectations, exact totals, and matching frozen split hashes. Holdout expected values are
kept in the dataset only; they are not injected into model messages or reproduced in top-level docs.

## Evaluation levels

- **Level 1 — Deterministic Offline:** dataset integrity, Router-after-resolution, schemas,
  contracts, trace ordering, safety validators, metrics and reporting. Default and network-free.
  The normal command evaluates Dev only; Holdout requires a separate explicit confirmation flag.
- **Level 2 — LLM Integration:** a real or replaceable model interface plus fixed Gateway/menu/RAG
  fixtures. Used for Tool choice, Contextualizer output, sequential decisions, and answer behavior.
  Automated tests remain offline.
- **Level 3 — Golden E2E:** 25 explicitly selected cases against real Qwen, the formal FastAPI
  service, HMAC Gateway, uniCloud and current data. Requires `--live-model --confirm-live`; it is not
  run by imports, pytest, pnpm, or default commands.

## Metrics

The report keeps separate denominators for Route Accuracy, Menu Fact Accuracy, Tool Selection,
Sequential Replanning, RAG Answerability, Retrieval Hit@3, Grounded Answer, Unsupported Claim,
Context Resolution, Multi-turn Route/Task Success, PendingAction Validity, Unsafe Proposal, Safety
Rejection, Unauthorized Side-effect, and Secret Leakage. Similarity is never treated as probability.
No single Overall Accuracy replaces these metrics.

Model-dependent metrics are `N/A` in a run that did not observe the required field. This prevents an
offline structural run from being described as a model pass.

## Deterministic validators

- Route and safe output contract validation.
- Required, forbidden, ordered, and maximum Tool calls.
- Tool-result-driven sequential trace order; parallel calls in one decision do not pass.
- Snapshot menu fact comparison.
- RAG answerability, Top-3 ID hit, evidence-ID subset, exact evidence-text presence, and unsupported
  claim signals.
- Exact seven-field pending action, quantity/price arithmetic, and `requiresConfirmation=true`.
- Cart/order/payment side-effect observation.
- Secret patterns and forbidden internal user-facing fields.

Natural-language style is not judged by another LLM by default. An optional judge may be added later
for qualities that structured validators cannot decide, but it cannot replace deterministic safety
or grounding checks.

## Failure taxonomy

One case may have a primary and multiple secondary failures:

- `ROUTER_MISCLASSIFICATION`
- `CONTEXT_RESOLUTION_ERROR`
- `TOOL_SELECTION_ERROR`
- `TOOL_ORDER_ERROR`
- `TOOL_OVER_CALLING`
- `RETRIEVAL_MISS`
- `ANSWERABILITY_ERROR`
- `UNSUPPORTED_CLAIM`
- `PENDING_ACTION_INVALID`
- `SAFETY_REJECTION_ERROR`
- `UNAUTHORIZED_SIDE_EFFECT`
- `OUTPUT_CONTRACT_ERROR`
- `ANSWER_FORMAT_ERROR`
- `SECRET_LEAKAGE`

## Snapshot and live data

Offline and fixed-fixture integration use the repository dishes snapshot and frozen 21-chunk
Knowledge Source for repeatability. Golden E2E observes live state. Its report must include time and
menu assumptions; a changed live price or availability must be classified as snapshot drift before
being called hallucination.

The committed Dev offline baseline reports only fields that Level 1 actually observes. Its Router result
is useful for surfacing dataset/Router disagreements, while Tool, Qwen, Contextualizer, RAG and
side-effect metrics remain `N/A`. It is not a fabricated cloud score.

## Running

See `services/framework-agent/evals/README.md` for exact commands. The normal command is fully
offline:

```bash
cd services/framework-agent
PYTHONPATH=. .venv/bin/python -m evals.runner
```

The Golden command requires both `--live-model` and `--confirm-live`, a separately started service,
and ignored local environment configuration. Never commit its capability tokens, signatures,
nonces, raw responses, private URLs, or secrets.

## Limitations

- V1 reflects eight menu records and 21 verified knowledge chunks in the frozen project snapshot.
- Human labels can still contain judgment errors and need manual review before live evaluation.
- The 25 Golden cases are acceptance coverage, not a production reliability claim.
- The formal live API intentionally hides route and trace, so internal Tool metrics require a safe
  controlled observation harness rather than weakening the production response contract.
- Holdout is process-frozen by hash, not protected by an external benchmark service.
