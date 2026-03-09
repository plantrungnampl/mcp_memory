# Appendix B — Error Catalog

## 1) Tool error envelope
Tool errors trả trong output envelope chuẩn:

```json
{
  "output_version": "1.0",
  "ok": false,
  "result": null,
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests",
    "details": {}
  },
  "request_id": "req_..."
}
```

## 2) Common tool error codes

### Auth / access
- `UNAUTHENTICATED`
- `FORBIDDEN`

### Validation
- `INVALID_ARGUMENT`
- `PAYLOAD_TOO_LARGE`

### State / idempotency
- `CONFLICT`

### Runtime / dependency
- `RATE_LIMITED`
- `UPSTREAM_ERROR`
- `INTERNAL`

## 3) Transport-level conditions đáng chú ý
- `404 Session not found`: stale hoặc unknown `mcp-session-id`
- `406 Not Acceptable`: client không advertise media types mong đợi
- `401 Missing control-plane assertion`: web -> backend contract bị lỗi ở control-plane path

## 4) Retry guidance
- Retry hợp lý: `RATE_LIMITED`, `UPSTREAM_ERROR`, stale session sau khi reconnect
- Không retry nguyên trạng: `INVALID_ARGUMENT`, `FORBIDDEN`, `CONFLICT`
