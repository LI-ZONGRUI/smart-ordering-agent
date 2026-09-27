# Framework Agent Service

## Purpose

This directory is the V7.1A local foundation for an independent Python AI service. It uses
FastAPI and LangChain while leaving the existing WeChat and uniCloud business core unchanged.
It is a local framework foundation, not a deployed production service.

LangChain was moved outside uniCloud because the measured JavaScript production dependency
package exceeded the current single cloud function size limit. The Python service is therefore
an adjacent framework layer, not a replacement for menu, order, payment, or transaction logic.

## Architecture

```text
POST /v1/agent/run
 → validate query
 → project-owned LangGraph StateGraph
 → route_request
    ├─ menu_query → existing LangChain create_agent → read-only Structured Tools
    ├─ knowledge_query → rag_node → authenticated Gateway → existing uniCloud RAG
    ├─ action_query → native_action_node → authenticated Gateway → existing Native Agent proposal
    ├─ smalltalk → deterministic response
    └─ unsupported_action → deterministic read-only boundary
 → normalize_result
 → unchanged public response
```

V7.2A directly depends on and imports LangGraph 1.2.12. The project now defines its own
`StateGraph`, typed state, nodes, edges and conditional routing. LangGraph owns the top-level
workflow; the accepted LangChain `create_agent` loop still owns Qwen Tool selection, Tool Result
observation and replanning inside `menu_agent`.

**V7.2A Explicit LangGraph StateGraph Foundation is complete and has passed controlled local
FastAPI acceptance through the formal endpoint.**

V7.2B adds the fourth `knowledge_query` route and `rag_node`. The node uses the same authenticated
Gateway adapter to call the existing uniCloud RAG and receives only its safe server-rendered
answer. Python does not copy knowledge, embeddings, retrieval, grounding, or rendering logic.
**V7.2B has completed controlled real acceptance through the formal FastAPI endpoint.**

V7.2C adds a narrowly classified `action_query` route. It calls the existing Native Agent through
the same HMAC-authenticated Gateway and accepts only its validated add-to-cart `pendingAction`.
The graph does not execute that proposal. User confirmation, frontend cart mutation, order
preview, confirmed order creation, price revalidation, request fingerprinting and idempotency all
remain in their existing deterministic boundaries. **V7.2C is fully offline-tested and has
completed real action-proposal and payment-boundary acceptance.**

## Local setup

Python 3.11 is required. Keep the virtual environment inside this directory:

```bash
cd services/framework-agent
python3.11 -m venv .venv
.venv/bin/python -m pip install uv==0.12.15
.venv/bin/uv sync --frozen
```

The repository uses `uv.lock` and exact versions in `pyproject.toml`. No Python dependency is
installed into the JavaScript project or the system Python environment.

## Environment variables

Copy `.env.example` to an ignored local `.env` only when preparing a production model adapter:

```text
DASHSCOPE_API_KEY=
LLM_BASE_URL=
FRAMEWORK_AGENT_LLM_MODEL=qwen3.8-flash
FRAMEWORK_GATEWAY_URL=
FRAMEWORK_GATEWAY_SECRET=
```

The app and `/health` import without these variables. They are checked only when the production
runner is requested. Missing or invalid configuration returns `FRAMEWORK_CONFIG_MISSING` without
identifying or printing a secret. V7.1A never sends a real Qwen request.

## Run

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

`POST /v1/agent/run` accepts only `{ "query": "..." }`. The query is trimmed and must contain
1–200 Unicode characters. Clients cannot select models, prompts, tools, temperature, base URLs,
keys, or limits.

V7.1B-2 adds the production `UniCloudHttpMenuGateway`. It requires an HTTPS URL whose exact path
is `/framework-gateway` and a separate 32–256 character Gateway secret. It rejects URL
credentials, query strings, fragments, other schemes and other paths. Production configuration
never falls back to `InMemoryMenuGateway`.

The adapter serializes each `{operation, arguments}` payload once as compact UTF-8 JSON, signs and
sends those exact bytes, and validates the response envelope and operation-specific data. One
logical Tool invocation makes one HTTP request; there is no automatic retry. A fresh signed nonce
is generated for every request. Explicit connect/read/write/pool timeouts are all below the
FastAPI Agent's 20-second overall limit.

## HTTP contract

Successful response:

```json
{
  "errCode": 0,
  "query": "有柠檬茶吗？",
  "answer": "...",
  "completed": true
}
```

An action proposal may add one backward-compatible optional field:

```json
{
  "pendingAction": {
    "type": "add_to_cart",
    "dishId": "dish-4",
    "name": "柠檬茶",
    "quantity": 2,
    "unitPrice": 12,
    "totalPrice": 24,
    "requiresConfirmation": true
  }
}
```

This is a proposal for explicit user confirmation. It is not proof that the cart changed and it
cannot represent order creation or payment.

The public endpoint does not return LangChain state, raw messages, prompts, tool call IDs, hidden
reasoning, raw model output, traces, keys, base URLs, or stack traces.

| Error code | HTTP | Meaning |
| --- | ---: | --- |
| `FRAMEWORK_QUERY_INVALID` | 400 | Query contract failed |
| `FRAMEWORK_CONFIG_MISSING` | 503 | Required model or Gateway configuration is unavailable |
| `FRAMEWORK_GATEWAY_REQUEST_FAILED` | 502 | Gateway transport or HTTP request failed |
| `FRAMEWORK_GATEWAY_TIMEOUT` | 504 | Gateway request timed out |
| `FRAMEWORK_GATEWAY_RESPONSE_INVALID` | 502 | Gateway response contract was invalid |
| `FRAMEWORK_GATEWAY_REMOTE_ERROR` | 502 | Gateway safely rejected the operation |
| `FRAMEWORK_MODEL_REQUEST_FAILED` | 502 | Upstream model request failed |
| `FRAMEWORK_MODEL_RESPONSE_INVALID` | 502 | No valid final model answer |
| `FRAMEWORK_TOOL_EXECUTION_FAILED` | 502 | Read-only menu tool failed |
| `FRAMEWORK_MAX_STEPS_EXCEEDED` | 422 | Finite graph recursion limit reached |
| `FRAMEWORK_EXECUTION_TIMEOUT` | 504 | Overall service timeout reached |
| `FRAMEWORK_INTERNAL_ERROR` | 500 | Unknown internal failure, safely generalized |

## Read-only tools

Only these three tools are registered:

- `search_menu(query: str)`
- `list_available_drinks()`
- `get_dish_detail(dish_id: str)`

Their Pydantic schemas reject unknown fields. They depend only on `MenuGateway`; they contain no
database code and expose only small menu result shapes. Cart mutation, order creation, payment,
and all write operations are absent. RAG is a separate graph route and is not registered as a
LangChain Tool.

`InMemoryMenuGateway` contains two deterministic fixtures for offline tests: an available lemon
tea priced at 12 and a sold-out sour plum drink priced at 14. These are not live menu facts and
the production dependency path never substitutes this adapter.

## Agent loop and limits

The service calls the current `langchain.agents.create_agent` API. Tests inject a small
tool-calling `BaseChatModel`, but still execute the real LangChain agent graph and real tools.
The key test proves:

```text
search_menu("可乐")
 → ToolMessage count=0
 → next fake-model decision
 → list_available_drinks()
 → final answer
```

There is no `if count == 0` fallback in production Python code. The second call comes from the
next model decision after observing the first ToolMessage.

## Explicit LangGraph workflow

The project-owned workflow is defined under `app/graph/`:

```text
START
 → route_request
 → menu_query → menu_agent ───────────────┐
 → knowledge_query → rag_node ────────────┤
 → action_query → native_action_node ─────┤
 → smalltalk → smalltalk_response ────────┤→ normalize_result → END
 → unsupported_action → readonly_boundary ┘
```

`FrameworkGraphState` contains `query`, `route`, `answer`, `completed` and an optional strict
`pendingAction`. It does not store keys, Gateway secrets, prompts, model reasoning, raw model
responses or Tool messages. The deterministic router sends a small set of add-to-cart proposal
phrases to `action_query`; order, payment, refund, confirmation and destructive cart requests stay
in `unsupported_action`. This is an orchestration foundation, not a complete NLU classifier.

For a validated add-to-cart proposal, `native_action_node` does not expose the Native Agent's free
answer. It deterministically renders the dish name, quantity, unit price and total from
`pendingAction`, then asks the user to confirm in the ordering UI. This avoids promising a text
“确认” continuation when the service has no `thread_id`, memory or multi-turn execution.

There is no checkpointer, `thread_id`, conversation memory or multi-turn history. The public
FastAPI contract does not expose the selected route or graph state. Inspect the compiled graph
offline without executing Qwen or Gateway calls:

```bash
.venv/bin/python -m scripts.check_graph
```

Execution uses a finite LangChain graph recursion limit of 13. This bounds model/tool cycles; it
is not described as exactly five decisions or eight tool calls. FastAPI also applies a 20-second
overall timeout.

## Tests and lint

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

All tests are offline. The fake chat model lives under `tests/`, never production code, and no
test calls Model Studio, uniCloud, a database, or the WeChat backend.

The V7.1B-2 integration test combines the real LangChain `create_agent`, real Structured Tools,
real `UniCloudHttpMenuGateway`, and `httpx.MockTransport`. It verifies the two-request cola flow,
HMAC headers and a different nonce per request without contacting the deployed Gateway.

V7.1C has completed controlled real Qwen end-to-end acceptance. The production path combines
`ChatOpenAI`, LangChain `create_agent`, the same three read-only Structured Tools and
`UniCloudHttpMenuGateway`. `scripts.check_real_agent` runs six bounded single-turn cases and prints
only sanitized Tool calls, minimal Tool result summaries and final answers. It does not run on
import and is never called by pytest or the formal FastAPI endpoint.

After manually supplying all five ignored environment settings, run it explicitly from this
directory with:

```bash
.venv/bin/python -m scripts.check_real_agent
```

The final Case A trace was:

```text
search_menu("可乐")
 → Tool Result: count=0
 → later Qwen decision: list_available_drinks()
 → Tool Result: acceptance-time 柠檬茶, ¥12, on_sale
 → grounded final answer
```

An earlier real run emitted both Tool Calls in one `AIMessage`, producing
`call → call → result → result`; it was not counted as sequential replanning. The final rerun
produced `call → result → call → result` after a general Prompt rule required the model to wait for
the first result. No program fallback was added.

The remaining cases verified a one-Tool lemon-tea lookup, a zero-Tool greeting, sold-out sour-plum
drink wording, refusal to modify the cart, and one basic prompt-injection check. These controlled
results do not constitute a general autonomous-planning or complete security guarantee.

## V7.2A real FastAPI acceptance

The formal `POST /v1/agent/run` endpoint was run locally with the production graph wiring and
ignored local environment settings:

- `你好` followed `smalltalk → smalltalk_response → normalize_result → END` and returned the fixed
  menu-assistant introduction without a menu Tool or database read.
- `有可乐吗？没有的话推荐点别的喝的。` followed `menu_query → menu_agent`; the existing
  LangChain/Qwen Agent used the authenticated Gateway and current uniCloud menu facts, then
  returned the cautious zero-search wording and the acceptance-time available lemon tea at ¥12.
- `把柠檬茶加两杯到购物车` followed
  `unsupported_action → readonly_boundary → normalize_result → END` and returned the fixed
  read-only refusal without a cart, order, payment Tool or write side effect.

All three successful responses retained the narrow public contract: `errCode`, `query`, `answer`
and `completed`. They exposed no route, graph state, node history, trace, Tool calls, reasoning or
raw messages. This acceptance establishes the observed routes and menu path; it is not a claim of
multi-turn memory or general autonomous workflow behavior.

During setup, `FRAMEWORK_CONFIG_MISSING` was traced to locally present but invalid model and
Gateway URL values: neither parsed as HTTPS with a host. Correcting the ignored local environment
values made `FrameworkSettings` validation and the formal endpoint succeed. This was local
acceptance environment misconfiguration, not a LangGraph, FastAPI or Pydantic defect. No real URL
or secret is recorded here.

Acceptance details:

- **Case B:** `search_menu("柠檬茶")` returned the real ¥12 in-stock item, followed by a grounded
  final answer with one Tool Call.
- **Case C:** a greeting completed with zero Tool Calls.
- **Case D:** the real sour-plum drink result was ¥14 and `sold_out`; the final answer used the
  user-facing Chinese wording “已售罄” rather than the internal status code.
- **Case E:** the assistant searched the real lemon-tea item but refused to add it to a cart or
  place an order. It exposed neither `dish-4` nor `on_sale` and performed no write side effect.
- **Case F:** one controlled prompt-injection request produced zero Tool Calls and did not reveal
  the system prompt, secrets, raw database data or Tool internals.

Grounding remains explicit: every menu fact in a final answer must appear in a Tool Result from the
same execution. The Prompt forbids unsupported taste, food-pairing, health, sugar, popularity and
sales-rank claims. A zero-result literal search must be phrased as “当前菜单搜索没有查到 X”, not as
proof that the restaurant has no such item.

Internal IDs and codes may remain in the local sanitized acceptance trace, but the user-facing
answer must hide dish IDs, Tool names, field names, Gateway/HMAC details and internal status codes;
`on_sale` and `sold_out` are rendered as “在售” and “已售罄”. The formal `/v1/agent/run` response
remains narrow and may include only the optional validated `pendingAction` for action proposals,
with no trace, messages, Tool calls, prompt, reasoning or raw provider response.

## V7.2B real RAG route acceptance

The same formal endpoint was manually verified with all four closed routes:

- `有柠檬茶吗？` followed `menu_query → menu_agent` and returned the real acceptance-time price
  of 12 yuan and on-sale status through the existing Qwen and menu Tool path.
- `柠檬茶是什么味道？` followed `knowledge_query → rag_node → RagGateway → authenticated
  Framework Gateway → rag_answer → existing uniCloud RAG`. The grounded answer stated the lemon
  aroma and the recorded red-tea/lemon ingredients.
- `你好` followed `smalltalk → smalltalk_response` without entering either remote branch.
- Before V7.2C, `把柠檬茶加入购物车` followed `unsupported_action → readonly_boundary`, performed
  no write, and did not delegate to the Native Agent. V7.2C intentionally supersedes only this
  add-to-cart proposal classification while preserving the no-write boundary.

Every branch then passed through `normalize_result → END`. The public response remained only
`errCode`, `query`, `answer`, and `completed`; route, graph state, chunks, scores, evidence IDs,
trace, Tool calls, and reasoning were not exposed.

LangGraph does not reimplement RAG. Embedding, Exact Retrieval, Top-3, evidence-first grounding,
and deterministic server rendering remain in the existing uniCloud RAG. The Python service has no
knowledge-source copy, vectors, cosine implementation, RAG prompt, or second generation pipeline.

## V7.2C real action-proposal acceptance

The fifth closed route was then verified through the same formal endpoint:

- `把柠檬茶加两杯到购物车` followed `action_query → native_action_node → ActionGateway →
  authenticated Framework Gateway → agent_propose_action → existing Native Agent →
  prepare_add_to_cart` and returned the validated seven-field proposal for 柠檬茶 ×2, unit price
  12, total 24, and `requiresConfirmation=true`.
- `native_action_node` rendered the final user answer deterministically from those fields and asks
  for confirmation in the ordering UI. It does not promise a later text-confirmation execution.
- `直接帮我付款` remained an `unsupported_action`, returned no `pendingAction`, and did not enter
  Native Agent proposal execution.
- Existing real `menu_query`, `knowledge_query`, and `smalltalk` cases continued to work.

The Native Agent Registry still contains three read-only menu Tools plus proposal-only
`prepare_add_to_cart`. It contains no `createConfirmedOrder`, payment, or confirmed transaction
execution Tool. Automated no-side-effect coverage runs the real Native Runner with database
`add`, `update`, and `remove` methods configured to fail immediately; the proposal path performs
only dishes reads and produces no cart mutation, order insert, confirmed execution, or executed flag.

## Real Gateway acceptance

Real Python-to-Gateway acceptance is complete. The accepted run used the production
`UniCloudHttpMenuGateway` through the existing script after manually exporting
`FRAMEWORK_GATEWAY_URL` and `FRAMEWORK_GATEWAY_SECRET` in an ignored local environment:

```bash
cd services/framework-agent
.venv/bin/python -m scripts.check_gateway
```

The script calls only `search_menu("柠檬茶")`, `list_available_drinks()` and
`get_dish_detail("dish-4")`. It does not start LangChain or call Qwen. Do not paste its secret,
signature or nonce into logs or documentation.

At acceptance time, search returned one `dish-4` 柠檬茶 at price 12 with `on_sale`; the available
drinks call returned the same single item; detail returned `found=true`, category `drink`, spicy
level 0, description “清爽柠檬香气，适合搭配正餐。” and ingredients 红茶、柠檬. These values
record the menu state observed during acceptance and are not permanent menu guarantees.

## Docker

The Dockerfile is a static Python 3.11 deployment starting point. `.dockerignore` excludes `.env`,
`.venv`, caches, tests, and Git metadata. Docker was unavailable during V7.1A, so no image build or
container deployment is claimed.

## Current boundary and next steps

- **V7.1A complete locally:** Python service, adapter, gateway port, read-only tools, real
  LangChain loop with an offline model, HTTP and safety tests.
- **Not complete:** Python service remote deployment, frontend framework integration, multi-turn
  memory, `thread_id`, checkpointer, conversation history, multi-turn confirmation and long-term state.
- **V7.1B-1 accepted on real uniCloud:** shared domain and authenticated server-side Gateway. The
  Python service did not participate in that acceptance.
- **V7.1B-2 accepted against real uniCloud:** Python `UniCloudHttpMenuGateway`, HMAC v1 client,
  response validation, safe errors, offline LangChain integration, and all three read-only
  operations through the deployed Gateway and Shared Menu Domain.
- **V7.1C accepted end to end:** real Qwen + LangChain `create_agent` + Structured Tools + real
  authenticated Gateway/menu data, including one Tool-result-driven sequential replanning case.
- **V7.2A accepted through the local formal FastAPI endpoint:** explicit project-owned
  `StateGraph`, minimal typed state, conditional routing, normalized output, offline tests and the
  three controlled route cases described above.
- **V7.2B accepted through the same endpoint:** the knowledge route reuses the existing
  evidence-first RAG through the authenticated Gateway without copying retrieval or grounding
  into Python.
- **V7.2C accepted:** the proposal-only action route returned a real validated 柠檬茶 ×2 action,
  while a direct payment request remained unsupported with no `pendingAction`. The final action
  answer is deterministically rendered from the proposal and no side effect is executed.
