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
 → LangChain create_agent
 → Qwen ChatOpenAI adapter (production only)
 → read-only Structured Tools
 → MenuGateway port
 → future UniCloudHttpMenuGateway (V7.1B)
```

`create_agent` brings LangGraph in as a transitive runtime dependency. V7.1A does not import or
implement `StateGraph`, custom state, nodes, edges, conditional routing, or any other explicit
LangGraph workflow. That work belongs to V7.2.

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

V7.1A intentionally has no production `MenuGateway`. Therefore a production run first validates
the Qwen configuration, then safely reports that the menu tool layer is unavailable. It never
falls back to the in-memory fixture. V7.1B will add the real authenticated read-only gateway.

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

The public endpoint does not return LangChain state, raw messages, prompts, tool call IDs, hidden
reasoning, raw model output, traces, keys, base URLs, or stack traces.

| Error code | HTTP | Meaning |
| --- | ---: | --- |
| `FRAMEWORK_QUERY_INVALID` | 400 | Query contract failed |
| `FRAMEWORK_CONFIG_MISSING` | 503 | Server model configuration is unavailable |
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
RAG routing, and all write operations are absent.

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

## Docker

The Dockerfile is a static Python 3.11 deployment starting point. `.dockerignore` excludes `.env`,
`.venv`, caches, tests, and Git metadata. Docker was unavailable during V7.1A, so no image build or
container deployment is claimed.

## Current boundary and next steps

- **V7.1A complete locally:** Python service, adapter, gateway port, read-only tools, real
  LangChain loop with an offline model, HTTP and safety tests.
- **Not complete:** real Qwen acceptance, real uniCloud menu integration, service authentication,
  remote deployment, frontend integration, and custom LangGraph orchestration.
- **V7.1B:** authenticated `UniCloudHttpMenuGateway` and real read-only acceptance.
- **V7.2:** explicit LangGraph orchestration after the service boundary is stable.
