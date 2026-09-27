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
a direct dependency and defines a project-owned `StateGraph` under `app/graph/`. Its typed state
contains `query`, `route`, `answer`, `completed` and an optional strict `pendingAction`. V7.2B adds the closed
`knowledge_query` route, which delegates through `rag_node` and the authenticated Gateway to the
existing uniCloud RAG. Conditional edges route requests to the existing menu Agent, the RAG,
the existing Native Agent proposal path, deterministic smalltalk, or a deterministic read-only
boundary. Every branch passes through
`normalize_result` before `END`.

The menu node delegates to the accepted `FrameworkAgent`; it does not call the Gateway directly
or replace the inner LangChain Tool loop. The RAG node accepts only the graph query and returns the
existing server-rendered answer; it does not implement Embedding, Retrieval, Grounding, or
evidence rendering in Python. There is no checkpointer, thread ID, conversation memory or
multi-turn history. The formal HTTP response still omits route, graph state, trace, messages,
evidence IDs, chunks, scores, and embeddings. It may include a validated optional `pendingAction`;
this never means the proposal has executed.

**V7.2A is complete and has passed controlled local acceptance through the formal FastAPI
endpoint, including smalltalk, the real Qwen menu path and the deterministic read-only boundary.**

**V7.2B has completed controlled real acceptance through the formal FastAPI endpoint.** The four
accepted cases covered a real-time lemon-tea lookup, a grounded lemon-tea taste/ingredients
knowledge answer, deterministic smalltalk, and deterministic refusal of a cart write request.
Automated tests remain offline and do not call the remote Gateway or Qwen.

The router remains intentionally small and deterministic. Write-action and exact greeting rules
run first; a compact set of taste, ingredient, description, and texture markers selects
`knowledge_query`; other read-only questions default to `menu_query`. Ambiguous phrasing can be
misclassified, and V7.2B does not add a router model or a large item-specific keyword table.

## V7.2C proposal boundary

The action branch supports only add-to-cart proposal intent. Python does not copy the Native
Function Calling loop or tools. `UniCloudHttpMenuGateway.propose_action()` signs the narrow
`agent_propose_action` operation; the server adapter statically calls `agent.run(query)` and
projects only `query`, `answer`, `completed`, and the existing seven-field `pendingAction`.

The Native Agent may read menu facts and call its existing `prepare_add_to_cart` Tool. That Tool
revalidates current dish identity, state, quantity, and price, then returns a proposal requiring
confirmation. It does not write a cart. LangGraph never calls frontend Pinia, `previewOrder`,
`createConfirmedOrder`, an orders collection, or a payment operation. Those transaction controls,
server revalidation, request fingerprint, idempotency, unique constraint and explicit user
confirmation remain outside the model workflow.

V7.2C is implemented, offline-tested, and accepted through the real FastAPI → LangGraph → HMAC
Gateway → Native Agent path. “把柠檬茶加两杯到购物车” returned a validated proposal for 柠檬茶 ×2,
unit price 12, total 24, and `requiresConfirmation=true`. “直接帮我付款” remained an
`unsupported_action` and returned no proposal.

The proposal answer is rendered deterministically by `native_action_node` from the validated
`pendingAction`. This replaced Native Agent free text that could imply “reply confirm and I will
execute”, although no `thread_id`, conversation memory, multi-turn confirmation, or text-confirmed
execution exists. The resulting user flow is proposal-only:

```text
User intent → Native Agent → pendingAction → frontend UI
            → explicit user confirmation → deterministic execution
```

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

### V7.2B

- Add deterministic `knowledge_query` routing and `rag_node` while keeping graph state minimal.
- Reuse HMAC v1 and the existing authenticated HTTP adapter through a narrow `RagGateway` port.
- Keep `rag.answer(query)` as the sole RAG implementation and expose only its safe rendered answer.
- Keep the formal API shape unchanged and continue rejecting write actions.
- Real `menu_query`, `knowledge_query`, `smalltalk`, and `unsupported_action` paths are accepted
  through the unchanged formal API.

### V7.2C

- Add deterministic `action_query` routing for add-to-cart proposal phrases only.
- Delegate through `native_action_node` and the HMAC Gateway to the existing Native Agent.
- Return the existing strict `pendingAction` as an optional backward-compatible API field.
- Keep order, payment, refund, confirmed execution and destructive cart requests unsupported.
- Keep every side effect behind explicit user confirmation and deterministic transaction code.
- Real action-proposal and payment-boundary acceptance is complete. The action answer is rendered
  deterministically from validated proposal fields; no graph node executes it.
