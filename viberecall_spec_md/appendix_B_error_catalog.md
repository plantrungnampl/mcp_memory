# Appendix B — Error Catalog (v0.1)

## 1) Nguyên tắc
- Tool errors: trả `isError=true` + JSON error object trong `content[].text`
- HTTP status: 401/403/409/429/500 tương ứng (nếu transport surface cho phép)

## 2) Error object schema
```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests",
    "request_id": "req_...",
    "details": {}
  }
}
```

## 3) Error codes
### Auth
- `UNAUTHENTICATED` (401): token thiếu/invalid/expired
- `FORBIDDEN` (403): token valid nhưng thiếu scope hoặc project mismatch

### Validation
- `INVALID_ARGUMENT` (400): input schema fail
- `PAYLOAD_TOO_LARGE` (413): vượt size cap

### Idempotency/Conflict
- `CONFLICT` (409): idempotency key reused with different payload

### Quota/Rate
- `RATE_LIMITED` (429): token bucket exceeded
- `QUOTA_EXCEEDED` (403/429): vượt token quota tháng

### Server/Dependency
- `UPSTREAM_ERROR` (502): LLM/embedding provider fail
- `GRAPH_DB_ERROR` (503): graph db unavailable
- `INTERNAL` (500): unknown

## 4) Retry guidance (client)
- Retry safe: `RATE_LIMITED` (respect reset), `UPSTREAM_ERROR` (backoff), `GRAPH_DB_ERROR` (backoff)
- Do not retry: `INVALID_ARGUMENT`, `FORBIDDEN`, `CONFLICT`
