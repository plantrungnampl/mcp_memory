# 04 — Tools Contract (Public API của MCP)

> VibeRecall giữ **tool names stable**. Nội bộ có thể map sang Graphiti tool set/upstream.

## 1) Tool list (v0.1)
1. `viberecall_save`
2. `viberecall_search`
3. `viberecall_get_facts`
4. `viberecall_update_fact`
5. `viberecall_timeline`

## 2) Conventions
- Output trả dạng: `content: [{type:"text", text:"<JSON string>"}]`
- Pagination: `cursor` + `next_cursor`
- Thời gian: ISO-8601 UTC

## 3) JSON Schemas

### 3.1 viberecall_save
- Purpose: lưu episode (fast-ack; enrich async)

**Input**
- `content` (required)
- `reference_time` (optional)
- `metadata` (type/repo/branch/files/tags/importance + custom)
- `idempotency_key` (optional)

**Output**
- `status`: `ACCEPTED`
- `episode_id`
- `ingested_at`
- `job_id`

### 3.2 viberecall_search
- Purpose: hybrid search + temporal filtering

**Input**
- `query` (required)
- `limit` (1..50)
- `filters`:
  - `reference_time_from/to`
  - `valid_at`
  - `as_of_ingest`
  - `tags`, `files`, `entity_types`
- `sort`: `RELEVANCE|RECENCY|TIME`
- `cursor`

**Output**
- list `results[]`:
  - `fact {id, text, valid_at, invalid_at}`
  - `entities[]`
  - `provenance {episode_ids, reference_time, ingested_at}`
  - `score`
- `next_cursor`

### 3.3 viberecall_get_facts
- Purpose: list facts (filters + pagination)

**Input**
- `filters {entity_type?, tag?, valid_at?}`
- `limit` (1..200)
- `cursor`

**Output**
- `facts[]` + `next_cursor`

### 3.4 viberecall_update_fact
- Purpose: temporal update (no overwrite history)

**Input**
- `fact_id` (required)
- `new_text` (required)
- `effective_time` (required)
- `reason` (optional)

**Output**
- `old_fact {id, invalid_at}`
- `new_fact {id, valid_at}`
- `job_id`

### 3.5 viberecall_timeline
- Purpose: list episodes timeline

**Input**
- `from?`, `to?`
- `limit` (1..200)
- `cursor`

**Output**
- `episodes[]`: `{episode_id, reference_time, ingested_at, summary?, metadata}`
- `next_cursor`

## 4) Plan gating
- Free: save/search/timeline (limits)
- Pro/Team: all tools + higher limits
- Khi plan đổi → server gửi `tools/list_changed`


## 5) Machine-tight schemas (JSON Schema — v0.1)

> Các schema dưới đây là **nguồn sự thật** (single source of truth).  
> Tool output luôn là JSON string trong MCP `content[].text`, theo **Output Envelope** cố định.

### 5.1 Output Envelope (mọi tool)
```json
{
  "output_version": "1.0",
  "ok": true,
  "result": {},
  "error": null,
  "request_id": "req_..."
}
```

- Khi lỗi: `ok=false`, `result=null`, `error` != null.
- `output_version` chỉ thay khi có breaking change; minor additions không tăng version.

### 5.2 Error object (khi ok=false)
```json
{
  "code": "RATE_LIMITED",
  "message": "Too many requests",
  "details": { "reset_at": "2026-02-28T10:32:00Z" }
}
```

**Enum `code` (v0.1):**
- `UNAUTHENTICATED`, `FORBIDDEN`, `INVALID_ARGUMENT`, `PAYLOAD_TOO_LARGE`
- `CONFLICT`, `RATE_LIMITED`, `QUOTA_EXCEEDED`
- `UPSTREAM_ERROR`, `GRAPH_DB_ERROR`, `INTERNAL`

### 5.3 viberecall_save — inputSchema (strict)
```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "content": { "type": "string", "minLength": 1, "maxLength": 200000 },
    "reference_time": { "type": ["string", "null"], "default": null, "description": "ISO-8601 UTC" },
    "metadata": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "type": { "type": "string", "enum": ["decision","bugfix","requirement","style","note"] },
        "repo": { "type": "string", "maxLength": 200 },
        "branch": { "type": "string", "maxLength": 200 },
        "files": { "type": "array", "items": { "type": "string", "maxLength": 400 }, "maxItems": 200 },
        "tags": { "type": "array", "items": { "type": "string", "maxLength": 64 }, "maxItems": 50 },
        "importance": { "type": "string", "enum": ["low","medium","high"], "default": "medium" }
      }
    },
    "idempotency_key": { "type": ["string","null"], "default": null, "maxLength": 128 }
  },
  "required": ["content"]
}
```

**viberecall_save — result schema**
```json
{
  "episode_id": "ep_...",
  "status": "ACCEPTED",
  "ingested_at": "2026-02-28T10:05:12Z",
  "enrichment": { "mode": "ASYNC", "job_id": "job_ingest_..." }
}
```

### 5.4 viberecall_search — inputSchema (strict)
```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "query": { "type": "string", "minLength": 1, "maxLength": 2000 },
    "limit": { "type": "integer", "minimum": 1, "maximum": 50, "default": 10 },
    "filters": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "reference_time_from": { "type": ["string","null"], "default": null },
        "reference_time_to": { "type": ["string","null"], "default": null },
        "valid_at": { "type": ["string","null"], "default": null },
        "as_of_ingest": { "type": ["string","null"], "default": null },
        "tags": { "type": "array", "items": { "type": "string", "maxLength": 64 }, "maxItems": 50, "default": [] },
        "files": { "type": "array", "items": { "type": "string", "maxLength": 400 }, "maxItems": 200, "default": [] },
        "entity_types": { "type": "array", "items": { "type": "string", "maxLength": 64 }, "maxItems": 20, "default": [] }
      }
    },
    "sort": { "type": "string", "enum": ["RELEVANCE","RECENCY","TIME"], "default": "RELEVANCE" },
    "cursor": { "type": ["string","null"], "default": null, "maxLength": 2048 }
  },
  "required": ["query"]
}
```

**Cursor format (v0.1):**
- Base64URL(JSON) gồm `{ "offset": <int>, "seed": <string> }`
- Không lộ internals DB.

**viberecall_search — result schema**
```json
{
  "results": [
    {
      "kind": "fact",
      "fact": { "id": "fact_...", "text": "...", "valid_at": "2026-02-27T09:20:00Z", "invalid_at": null },
      "entities": [{ "id": "ent_...", "type": "Module", "name": "auth" }],
      "provenance": { "episode_ids": ["ep_..."], "reference_time": "2026-02-27T09:20:00Z", "ingested_at": "2026-02-28T10:05:12Z" },
      "score": 0.83
    }
  ],
  "next_cursor": null
}
```

### 5.5 viberecall_get_facts — input/result schema
```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "filters": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "entity_type": { "type": ["string","null"], "default": null, "maxLength": 64 },
        "tag": { "type": ["string","null"], "default": null, "maxLength": 64 },
        "valid_at": { "type": ["string","null"], "default": null }
      }
    },
    "limit": { "type": "integer", "minimum": 1, "maximum": 200, "default": 50 },
    "cursor": { "type": ["string","null"], "default": null, "maxLength": 2048 }
  }
}
```

### 5.6 viberecall_update_fact — input/result schema
```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "fact_id": { "type": "string", "minLength": 1, "maxLength": 128 },
    "new_text": { "type": "string", "minLength": 1, "maxLength": 20000 },
    "effective_time": { "type": "string", "description": "ISO-8601 UTC" },
    "reason": { "type": ["string","null"], "default": null, "maxLength": 2000 }
  },
  "required": ["fact_id","new_text","effective_time"]
}
```

### 5.7 viberecall_timeline — input/result schema
```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "from": { "type": ["string","null"], "default": null },
    "to": { "type": ["string","null"], "default": null },
    "limit": { "type": "integer", "minimum": 1, "maximum": 200, "default": 50 },
    "cursor": { "type": ["string","null"], "default": null, "maxLength": 2048 }
  }
}
```

**Timeline item**
```json
{
  "episode_id": "ep_...",
  "reference_time": "2026-02-27T09:20:00Z",
  "ingested_at": "2026-02-28T10:05:12Z",
  "summary": "optional short summary",
  "metadata": { "type": "decision", "tags": ["auth"] }
}
```
