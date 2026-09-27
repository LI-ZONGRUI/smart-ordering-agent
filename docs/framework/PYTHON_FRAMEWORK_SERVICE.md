# Python Framework Service Architecture

## Decision

V7 introduces an independent Python 3.11 service beside the existing WeChat and uniCloud system.
The reason is operational: the measured JavaScript LangChain package cannot fit the current
uniCloud single-function package limit. The existing business core remains the system of record.

FastAPI provides a narrow HTTP boundary and explicit request/error contracts. LangChain provides
the model and structured tool loop using the current `create_agent` API. The service does not own
menu persistence, pricing, carts, orders, idempotency, or payment.

## Component boundary

```text
WeChat / uniCloud business core (unchanged)
  menu facts, prices, status, orders, side effects, idempotency

Independent Python framework service (V7.1A local only)
  FastAPI contract
  LangChain create_agent orchestration
  Qwen ChatOpenAI adapter
  three read-only tool contracts
  MenuGateway port
```

V7.1B-1 provides the server-side shared read-only menu domain and authenticated uniCloud
`framework-gateway`, and that server-side boundary passed real cloud acceptance. V7.1B-2 now
implements `UniCloudHttpMenuGateway` without accessing collections or copying database rules.
Its signing and HTTP path are fully offline-tested and have completed real Python-to-uniCloud
acceptance for all three read-only operations.

## MenuGateway port

`MenuGateway` defines only three semantic operations:

1. `search_menu(query)`
2. `list_available_drinks()`
3. `get_dish_detail(dish_id)`

LangChain tools depend on this interface. They do not import database clients, uniCloud code, or
the existing Native Agent. This keeps Tool schemas stable while adapters change.

`InMemoryMenuGateway` is a deterministic offline fixture for local tests and demos. Its two menu
records are not production data. The production dependency path has no fixture fallback.

`UniCloudHttpMenuGateway` is the production adapter. It validates an exact HTTPS
`/framework-gateway` URL, signs compact raw JSON bytes with HMAC v1, sends one request per Tool
invocation, and reduces the remote response to the existing `MenuGateway` result types. HTTP
headers, signatures, remote bodies and transport details do not enter LangChain Tool results.

Gateway failures map to stable framework errors: request/HTTP failures, timeout, invalid response
and safe remote rejection. Raw URL, secret, signature, cookies and upstream error content are not
included. Automatic retry is intentionally absent; a future retry would require a new timestamp,
nonce and signature for every attempt.

## Trust and transaction boundaries

- The server owns model, base URL, prompt, tool registry, and execution limits.
- Users can submit only one trimmed query of 1–200 Unicode characters.
- Tools are read-only and reject extra arguments.
- Tool results expose small public menu shapes rather than raw documents.
- The public API omits trace, messages, prompts, tool IDs, hidden reasoning, configuration, and
  raw exceptions.
- The service never writes a cart, creates an order, processes payment, or accesses a database.
- Existing uniCloud validation, pricing, confirmation, and idempotency remain authoritative.

## Qwen adapter

`langchain_openai.ChatOpenAI` is configured at construction time from `DASHSCOPE_API_KEY`,
`LLM_BASE_URL`, and `FRAMEWORK_AGENT_LLM_MODEL`. It is non-streaming, uses zero retries in the
adapter, and has a finite request timeout. Configuration is lazy so app import and health checks
remain available without secrets.

V7.1A implemented but did not call the production adapter. Automated orchestration tests still use
a test-only `BaseChatModel` and make no network requests. V7.1C separately completed controlled
real Qwen acceptance through the production adapter; those calls are manual acceptance, never
pytest behavior.

## LangGraph boundary

V7.1 used LangGraph only through LangChain's agent runtime. V7.2A now declares LangGraph 1.2.12 as
a direct dependency and defines a project-owned `StateGraph` under `app/graph/`. Its minimal typed
state contains `query`, `route`, `answer` and `completed`; conditional edges route requests to the
existing menu Agent, deterministic smalltalk, or a deterministic read-only boundary. Every branch
passes through `normalize_result` before `END`.

The menu node delegates to the accepted `FrameworkAgent`; it does not call the Gateway directly
or replace the inner LangChain Tool loop. There is no checkpointer, thread ID, conversation memory,
multi-turn history, RAG routing or Native Agent delegation. The formal HTTP response still omits
route, graph state, trace and messages.

**V7.2A is complete and has passed controlled local acceptance through the formal FastAPI
endpoint, including smalltalk, the real Qwen menu path and the deterministic read-only boundary.**

## Failure and execution controls

The service maps query, configuration, model request, model response, tool, recursion, timeout,
and unknown failures to stable safe codes. Unknown details are never returned. A finite graph
recursion limit bounds the agent cycle and FastAPI applies an overall 20-second timeout.

## Evolution path

### V7.1B

- **V7.1B-1 accepted on real uniCloud:** shared menu domain and authenticated read-only server Gateway.
- **V7.1B-2 accepted against real uniCloud:** `UniCloudHttpMenuGateway`, HMAC v1, strict response
  validation, safe errors, MockTransport LangChain integration, and real reads through the
  deployed Gateway for all three operations.
- Keep the accepted Gateway contract frozen while the framework layer evolves.

### V7.1C

- **Accepted end to end:** real Qwen3.8-Flash, LangChain `create_agent`, three read-only Tools,
  `UniCloudHttpMenuGateway`, authenticated Gateway, Shared Menu Domain and real uniCloud menu data.
- In the final Case A trace, Qwen first called `search_menu("可乐")`, observed `count=0`, then made
  a second model decision to call `list_available_drinks()`. No Python fallback branch or script
  call supplied the second Tool invocation.
- The other controlled cases covered one-Tool lookup, zero-Tool greeting, sold-out status,
  read-only refusal and a basic prompt-injection check.
- This proves the observed single-turn cases, not a general autonomous-planning or production
  security guarantee. Automated tests remain fully offline.

### V7.2A

- Explicit LangGraph state and conditional top-level routing are implemented and accepted through
  the formal local FastAPI endpoint.
- Keep the accepted LangChain menu Tool loop inside the `menu_agent` node.
- The controlled menu case reached real Qwen, the authenticated Gateway and current uniCloud menu
  data. This is local integration acceptance, not remote service deployment or a production-grade
  autonomous workflow claim.
- Preserve uniCloud ownership of facts and transactions.
- Keep write effects behind deterministic validation and explicit user confirmation.
