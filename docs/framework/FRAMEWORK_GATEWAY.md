# V7.1B-1 Authenticated Framework Gateway

## Purpose

V7.1B-1 adds a small authenticated HTTP boundary through which the future Python framework
service can read current menu facts. It does not connect the Python service yet and it does not
call Qwen.

The implementation has two parts:

```text
cloudfunctions/common/menu-read-domain
  ├─ existing Native Agent
  └─ framework-gateway (URLized HTTP function)
```

The shared module is the only implementation of menu pagination, field validation, literal
search, drinks-category lookup, on-sale filtering, and response normalization. The Gateway does
not query a collection itself and does not call an admin function.

## Shared Menu Domain

Public functions:

- `searchMenu({ query }, options?)`
- `listAvailableDrinks({}, options?)`
- `getDishDetail({ dishId }, options?)`

The Native Agent supplies its existing server-owned `db` dependency through `options`. In the
deployed Gateway path the common module resolves `uniCloud.database()` internally. This preserves
the existing test seam while keeping database ownership out of the HTTP boundary.

`agent/tools/menu-tools.js` is now only a compatibility loader. HBuilderX uses the declared
`menu-read-domain` public-module dependency; local Node tests use the same source directory as a
fallback. Registry, Executor, Prompt, Agent Loop, Trace, and `prepare_add_to_cart` are unchanged.

## Trust Boundary

The Gateway is a normal uniCloud cloud function intended to be URLized at one exact route. It:

- accepts only URLized HTTP requests with `context.SOURCE === "http"`;
- accepts only `POST` at the function root path;
- limits the decoded body to 4096 bytes;
- authenticates the exact raw body bytes before JSON parsing;
- validates a strict top-level and per-operation schema;
- dispatches through a static three-operation map;
- returns small normalized data from the shared domain;
- converts database and implementation failures to fixed safe errors.

It has no cart, order, payment, RAG admin, arbitrary collection, or database-write capability.

## Allowed Operations

### `search_menu`

```json
{
  "operation": "search_menu",
  "arguments": { "query": "可乐" }
}
```

`query` is trimmed and must contain 1–200 Unicode characters. Search remains the existing literal
substring search over dish name, description, and ingredients, including sold-out matches.

### `list_available_drinks`

```json
{
  "operation": "list_available_drinks",
  "arguments": {}
}
```

The shared domain resolves the category whose current name is `饮料` and returns only `on_sale`
records. The category ID is not hardcoded.

### `get_dish_detail`

```json
{
  "operation": "get_dish_detail",
  "arguments": { "dishId": "dish-4" }
}
```

`dishId` is trimmed and limited to 128 Unicode characters. A missing dish remains the normal
`found: false` result; sold-out detail remains visible with its real status.

All other operation names, including prototype-property names and write operations, are rejected.
Extra top-level and argument fields are rejected.

## Response Contract

Success:

```json
{
  "errCode": 0,
  "operation": "search_menu",
  "data": {
    "tool": "search_menu",
    "query": "可乐",
    "count": 0,
    "items": []
  }
}
```

Error:

```json
{
  "errCode": "FRAMEWORK_GATEWAY_AUTH_INVALID",
  "message": "请求认证失败"
}
```

Errors never contain the secret, signature, headers, request body, database exception, stack,
collection metadata, or local path.

## HMAC-SHA256 Authentication

The only Gateway secret is the server environment variable:

```text
FRAMEWORK_GATEWAY_SECRET
```

It is separate from `DASHSCOPE_API_KEY`. There is no default or open development mode. Missing,
too-short, or invalid server configuration fails closed with
`FRAMEWORK_GATEWAY_CONFIG_MISSING`. The current implementation accepts a 32–256 character secret;
the real value must never be committed.

Required HTTP headers:

```text
X-Framework-Signature-Version: v1
X-Framework-Timestamp: <Unix seconds>
X-Framework-Nonce: 16–64 characters matching [A-Za-z0-9_-]
X-Framework-Signature: <lowercase HMAC-SHA256 hex>
```

The signed body hash is calculated from the **exact decoded HTTP body bytes** received by
uniCloud. JSON is not parsed and reserialized for signing, so object key iteration is irrelevant.
The future Python client must sign exactly the bytes it sends.

Canonical signing string v1:

```text
v1
POST
/framework-gateway
<timestamp>
<nonce>
<sha256(rawBodyBytes) lowercase hex>
```

The signature is:

```text
hex(HMAC-SHA256(FRAMEWORK_GATEWAY_SECRET, canonicalString))
```

The server validates the lowercase 64-character signature and uses
`crypto.timingSafeEqual`. Signature version `v1` leaves room for a future protocol revision.

## Freshness and Replay Boundary

Timestamp freshness is limited to server time ±300 seconds. Requests older than the window or too
far in the future return `FRAMEWORK_GATEWAY_AUTH_EXPIRED`.

The nonce is included in the signed material and its format is validated. V7.1B-1 does **not**
persist used nonces. Therefore it provides body integrity, sender-secret authentication, and a
bounded replay window, but it is not a complete one-time replay guarantee. No collection or write
path was added for nonce storage. Persistent replay prevention is future hardening.

## Error Contract

| Error | Meaning |
| --- | --- |
| `FRAMEWORK_GATEWAY_REQUEST_INVALID` | HTTP, payload, JSON, size, or argument contract failed |
| `FRAMEWORK_GATEWAY_OPERATION_NOT_ALLOWED` | Operation is outside the three-item allowlist |
| `FRAMEWORK_GATEWAY_AUTH_MISSING` | Required authentication metadata is absent |
| `FRAMEWORK_GATEWAY_AUTH_INVALID` | Signature or authentication metadata is malformed/invalid |
| `FRAMEWORK_GATEWAY_AUTH_EXPIRED` | Timestamp is outside ±300 seconds |
| `FRAMEWORK_GATEWAY_AUTH_VERSION_UNSUPPORTED` | Signature version is not `v1` |
| `FRAMEWORK_GATEWAY_CONFIG_MISSING` | Server secret is unavailable or invalid |
| `FRAMEWORK_GATEWAY_TOOL_FAILED` | Shared menu read failed safely |
| `FRAMEWORK_GATEWAY_INTERNAL_ERROR` | Unexpected Gateway failure |

## Real uniCloud Acceptance

V7.1B-1 completed real acceptance against the deployed uniCloud environment.

### Native Agent regression after extraction

The existing WeChat Agent path was rechecked against real cloud data after moving the read-only
handlers into the Shared Menu Domain:

- `有柠檬茶吗？` returned lemon tea as on sale at ¥12.
- `有酸梅汤吗？` returned sour plum drink at ¥14 with its current sold-out status.
- `有可乐吗？没有的话推荐点别的喝的。` returned the currently available lemon tea at ¥12.
- `把柠檬茶加两杯到购物车` produced a Pending Action for two lemon teas, unit price ¥12 and
  total ¥24, still requiring explicit user confirmation.

These results show that the extraction preserved the existing Native Agent path. They do not
claim that an admin trace was re-inspected during this acceptance.

### URLized HTTP and authentication

The first real URLized request exposed a platform compatibility issue: the entry checked
`context.source`, while a DCloud normal cloud function supplies `context.SOURCE`. As a result, an
unsigned request initially returned `FRAMEWORK_GATEWAY_REQUEST_INVALID` before reaching HMAC
validation. The entry was minimally corrected to require `context.SOURCE === "http"` and still
rejects client, function, server, timing, and missing-source calls.

After redeployment, a real unsigned `POST /framework-gateway` request for
`search_menu("柠檬茶")` returned `FRAMEWORK_GATEWAY_AUTH_MISSING`. This confirms that the deployed
Gateway fails closed before executing the Shared Menu Domain.

A local signing client then used canonical signing v1 and sent valid HMAC-authenticated HTTPS
requests. At acceptance time:

- `search_menu("柠檬茶")` returned `dish-4`, name `柠檬茶`, category `drink`, price ¥12,
  `on_sale`, and spicy level 0.
- `list_available_drinks({})` returned one available item: the same `dish-4` lemon tea facts.
- `get_dish_detail({ dishId: "dish-4" })` returned `found: true`, description
  `清爽柠檬香，适合搭配正餐。`, and ingredients `红茶`、`柠檬` from the real dishes collection.

No secret, signature, or actual nonce value is recorded here. Menu facts above describe the
acceptance-time database state and are not permanent assertions.

### Read-only allowlist acceptance

A validly authenticated request for `createConfirmedOrder` returned
`FRAMEWORK_GATEWAY_OPERATION_NOT_ALLOWED`. Authentication therefore does not grant access outside
the explicit allowlist of `search_menu`, `list_available_drinks`, and `get_dish_detail`. This is
evidence for the current operation boundary, not a claim that every possible attack has been
proven safe.

The replay boundary remains unchanged: the signature covers a validated nonce and a timestamp
within ±300 seconds, but no persistent nonce replay cache exists and no one-time nonce guarantee
is claimed.

## Deployment in HBuilderX

The accepted deployment used the following sequence:

1. Under `cloudfunctions/common/menu-read-domain`, choose **上传公共模块**.
2. For `agent`, use **管理公共模块依赖** and confirm `menu-read-domain` is selected.
3. For `framework-gateway`, use **管理公共模块依赖** and confirm the same module is selected.
4. Upload/deploy the updated `agent` cloud object and run its existing regression acceptance.
5. Configure only the environment variable name `FRAMEWORK_GATEWAY_SECRET` on
   `framework-gateway`; enter a new strong value in the remote environment, never in Git.
6. Upload/deploy `framework-gateway` as a normal cloud function.
7. In the uniCloud console, configure the URLized path as `/framework-gateway`. A request to that
   exact public path reaches the function with the root event path `/`, which is the only path the
   function accepts.

Do not reinitialize categories, dishes, orders, or knowledge collections. Do not deploy an admin
or unauthenticated debug function.

## Current Status

Implemented, locally tested, and accepted on real uniCloud:

- shared read-only menu domain;
- Native Agent reuse;
- authenticated URLized Gateway boundary;
- HMAC v1, timestamp freshness, nonce validation, constant-time comparison;
- operation and argument allowlists;
- safe normalized results and errors;
- real Native Agent regression after Shared Domain extraction;
- real URLized fail-closed authentication and valid HMAC requests;
- real reads for all three allowed operations;
- authenticated rejection of a non-allowlisted write operation.

Not yet implemented or accepted:

- Python `UniCloudHttpMenuGateway`;
- real Python-to-uniCloud HTTP request;
- real Qwen + Gateway end-to-end LangChain run;
- persistent nonce replay cache;
- custom LangGraph workflow.

## Platform References

- uniCloud public modules: <https://doc.dcloud.net.cn/uniCloud/cf-common.html>
- uniCloud URLized HTTP event/body/headers: <https://doc.dcloud.net.cn/uniCloud/http>
