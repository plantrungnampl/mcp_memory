# Appendix C — Export Format (Canonical JSON v1)

## 1) Scope (v0.1)
- **Export only** (Import out-of-scope v0.1)
- Format canonical: **JSON v1**
- GraphML: out-of-scope v0.1
- IDs: **preserve** (no remap trong v0.1)

## 2) Delivery
- Tool call tạo `export_job`
- Khi complete, trả **signed URL** (expires) trong tool result.
- Resource URI: phase sau (khi bật Resources capability).

## 3) File schema (JSON v1)
Top-level:
```json
{
  "format": "viberecall-export",
  "version": "1.0",
  "exported_at": "2026-02-28T12:00:00Z",
  "project_id": "proj_...",
  "episodes": [],
  "entities": [],
  "facts": [],
  "relationships": []
}
```

Constraints:
- `episode_id`, `entity_id`, `fact_id` phải stable và unique.
- Facts phải có `valid_at` và có thể có `invalid_at=null`.

## 4) Import semantics (future)
- v0.2: thêm import với modes `PRESERVE_IDS` hoặc `FORK_WITH_PREFIX`.
