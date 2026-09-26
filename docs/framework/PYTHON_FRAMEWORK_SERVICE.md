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

V7.1B-1 now provides the server-side shared read-only menu domain and authenticated uniCloud
`framework-gateway`, and that server-side boundary has passed real uniCloud URLized HTTP, HMAC,
allowlist, and live-menu acceptance. The Python `UniCloudHttpMenuGateway` client is still not
implemented, so no real Python-to-uniCloud HTTP integration or acceptance is claimed. When
V7.1B-2 adds that client, the Python service will not access uniCloud collections or copy database
rules directly.

## MenuGateway port

`MenuGateway` defines only three semantic operations:

1. `search_menu(query)`
2. `list_available_drinks()`
3. `get_dish_detail(dish_id)`

LangChain tools depend on this interface. They do not import database clients, uniCloud code, or
the existing Native Agent. This keeps Tool schemas stable while adapters change.

`InMemoryMenuGateway` is a deterministic offline fixture for local tests and demos. Its two menu
records are not production data. The production dependency path has no fixture fallback.

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

V7.1A implements but does not call the production adapter. Automated orchestration tests use a
test-only `BaseChatModel` and make no network requests.

## LangGraph boundary

The installed LangChain version includes LangGraph as a transitive agent runtime dependency.
This repository has no explicit LangGraph implementation in V7.1A: no `StateGraph`, custom graph
state, nodes, edges, conditional edges, router, or graph persistence is defined. Explicit
LangGraph orchestration is reserved for V7.2.

## Failure and execution controls

The service maps query, configuration, model request, model response, tool, recursion, timeout,
and unknown failures to stable safe codes. Unknown details are never returned. A finite graph
recursion limit bounds the agent cycle and FastAPI applies an overall 20-second timeout.

## Evolution path

### V7.1B

- **V7.1B-1 accepted on real uniCloud:** shared menu domain and authenticated read-only server Gateway.
- **V7.1B-2 pending:** add `UniCloudHttpMenuGateway` without changing LangChain Tool contracts.
- Later validate Qwen and real menu reads in a controlled environment.

### V7.2

- Introduce explicit LangGraph state and routing only after the gateway boundary is stable.
- Preserve uniCloud ownership of facts and transactions.
- Keep write effects behind deterministic validation and explicit user confirmation.
