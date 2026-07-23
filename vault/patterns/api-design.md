---
id: api-design
title: API Design — REST, GraphQL, gRPC
type: pattern
tags: [api, rest, graphql, grpc, http, versioning, pagination, idempotency, contracts]
summary: Principles and tradeoffs for designing REST, GraphQL, and gRPC APIs — covering protocol selection, resource modeling, versioning, pagination, idempotency, error modeling, and schema contracts.
related:
  - {slug: owasp-top-10-quickref, rel: relates-to}
  - {slug: database-design-and-indexing, rel: relates-to}
created: 2026-06-20
---

# API Design — REST, GraphQL, gRPC

Choosing the right API style and applying consistent conventions to it determines how maintainable and
evolvable a system is. REST, GraphQL, and gRPC each solve a different problem; misapplying them
produces unnecessary complexity. The principles below apply once you have chosen a style.

## Protocol Selection

**REST** (HTTP + JSON or XML) is the default for public-facing, resource-oriented APIs. Its uniform
interface (URLs, verbs, status codes) needs no tooling to consume and maps naturally to CRUD
operations. The cost is over- and under-fetching for complex data needs.

**GraphQL** is preferable when clients with different data appetites (mobile vs. web vs. third-party)
query the same graph. A single schema-typed endpoint replaces N resource endpoints; clients request
exactly the fields they need. The cost is query complexity and the N+1 problem, which requires
deliberate data-loader design server-side.

**gRPC** is preferable for internal service-to-service calls where performance matters: it uses HTTP/2
multiplexing, binary Protocol Buffers encoding, and generated client stubs, yielding lower latency and
payload size than JSON. It is unsuitable for browser-native consumption without a proxy layer.

Rule of thumb: public web APIs → REST; heterogeneous client data needs → GraphQL; internal microservice mesh → gRPC.

## REST Resource and URL Modeling

Design around **resources** (nouns), not actions (verbs). URLs identify resources; HTTP methods express the action.

- Collections: `GET /orders`, `POST /orders`
- Individual items: `GET /orders/{id}`, `PUT /orders/{id}`, `DELETE /orders/{id}`
- Sub-resources: `GET /orders/{id}/items` (prefer shallow nesting; maximum two levels)
- Non-CRUD actions: use a verb sub-resource sparingly — `POST /orders/{id}/cancel`

**HTTP method semantics** (per RFC 9110):

| Method | Semantics | Safe | Idempotent |
|--------|-----------|------|------------|
| GET | Retrieve representation | Yes | Yes |
| HEAD | Retrieve headers only | Yes | Yes |
| PUT | Replace resource | No | Yes |
| PATCH | Partial update | No | No* |
| POST | Create or non-idempotent action | No | No |
| DELETE | Remove resource | No | Yes |

Use `PUT` only when the client supplies the complete replacement; use `PATCH` for partial updates. Never use `GET` with a body to perform queries.

**HTTP status codes** must be accurate. Key codes:

- `200 OK`
- `201 Created` (include `Location` header)
- `204 No Content`
- `400 Bad Request` (client error, fixable)
- `401 Unauthorized` (missing/invalid auth)
- `403 Forbidden` (authenticated but not allowed)
- `404 Not Found`
- `409 Conflict`
- `422 Unprocessable Entity` (validation failed)
- `429 Too Many Requests`
- `500 Internal Server Error`

## Versioning

APIs change; clients cannot always update in lockstep. Common strategies:

- **URI versioning** (`/v1/orders`): explicit, cacheable, easy to route. Preferred for major breaking changes.
- **Header versioning** (`Accept: application/vnd.api+json; version=2`): keeps URLs clean; harder to discover and test.
- **Query parameter** (`?version=2`): simple but pollutes caches.

Avoid breaking changes within a version. Additive changes (new fields, new optional parameters) are
safe. Removing or renaming fields requires a new major version. Sunset deprecated versions with an HTTP
`Sunset` or `Deprecation` header and communicate timelines explicitly.

## Pagination

**Offset pagination** (`?offset=0&limit=20`) is simple but degrades on large datasets: deep offsets
require the database to scan and discard rows, and concurrent inserts/deletes make results
inconsistent. Use it for small, stable datasets or admin UIs.

**Cursor pagination** encodes a stable pointer into the result set, such as an opaque base-64-encoded
`{created_at, id}` tuple. The server returns `next_cursor`; the client passes `?after={cursor}`. It is
O(1) per page at the database, consistent under mutation, and the preferred approach for feeds and
large collections.

Return pagination metadata in a consistent envelope — e.g., `{ data: [...], pagination: { next_cursor, total_count } }` — or use Link headers (`Link: <url>; rel="next"`).

## Idempotency

**Idempotent** operations can be retried safely (same result regardless of how many times the call succeeds). GET, PUT, and DELETE are inherently idempotent. POST is not.

For non-idempotent POST operations that must be retried safely (payments, order creation), require an
**idempotency key**: a client-generated UUID supplied in a header, e.g.,
`Idempotency-Key: <uuid>`. The server stores the key and, on replay, returns the cached response rather
than processing again. Keys should be scoped to the operation type and expire after a reasonable window
(24–48 hours).

## Consistent Error Modeling

Error responses must be machine-readable, not just human-readable. Adopt a single shape across all endpoints. A practical structure:

```
{
  "error": {
    "code": "VALIDATION_ERROR",        // stable machine code
    "message": "...",                  // human-readable
    "details": [                       // optional per-field breakdown
      { "field": "email", "issue": "must be a valid email address" }
    ],
    "request_id": "req_abc123"         // for log correlation
  }
}
```

Never expose stack traces or internal implementation details in production error responses (see [[owasp-top-10-quickref]]).

## API Contracts and Schemas

A machine-readable schema is the contract between producer and consumer. Define it before writing code; generate stubs and docs from it.

- **REST**: OpenAPI (formerly Swagger) is the standard. Version the spec alongside the API; use it to generate server stubs, client SDKs, and validation middleware.
- **GraphQL**: the schema definition language (SDL) is the contract. Enforce backwards compatibility with schema-change linting tools (e.g., no field removal without deprecation).
- **gRPC**: `.proto` files are the contract. Treat them as first-class source artifacts. Follow Protobuf field-numbering rules to maintain wire compatibility: never reuse a field number, use `reserved` for removed fields.

Schema-first design catches integration mismatches at definition time rather than at runtime and enables
parallel client/server development. See also [[database-design-and-indexing]] for how schema discipline
applies at the persistence layer.

> Source: https://docs.cloud.google.com/apis/design · curated · 2026-06-20
