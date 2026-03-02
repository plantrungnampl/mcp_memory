# 06 — Pipelines & Latency (Fast ACK + Async Enrich)

## 1) Save pipeline (2-phase write)
### Phase A — Fast ACK (sync)
1. Auth + scope check
2. Rate limit + quota pre-check
3. Persist raw episode (Postgres/object storage)
4. Enqueue `ingest_job`
5. Return tool result `{status:ACCEPTED, episode_id, job_id}`

Target: p95 < 200ms

### Phase B — Enrichment (async worker)
1. Load episode
2. Graphiti `add_episode(...)` vào project graph
3. Extract entities/facts (LLM/embeddings as needed)
4. Apply temporal updates (invalidate old facts nếu mâu thuẫn)
5. Update usage counters + audit
6. Optional: push notifications / webhook

## 2) Search pipeline (hybrid + fresh visibility)
1. Query graph facts (Graphiti search) trong project graph
2. Apply filters (`valid_at`, `reference_time_range`, tags/files/entity_types)
3. Merge thêm “recent raw episodes chưa enrich” (window 1–5 phút)
4. Rank + return

## 3) Update fact pipeline
- Input bắt buộc `effective_time`
- Worker:
  - set old `invalid_at = effective_time`
  - create new fact `valid_at = effective_time`
  - audit log

## 4) Export pipeline
1. Tool call tạo `export_job`
2. Worker stream graph → JSON/GraphML → object storage (chunked)
3. Ghi `exports` record + signed URL + expiry
4. Tool result trả export_id + link (hoặc resource URI)

## 5) Idempotency rules
- Save/update/export: support Idempotency-Key
- De-dup job enqueue theo `(project_id, idempotency_key)`


## 6) Search algorithm (chốt cứng v0.1)

### 6.1 Candidate generation (hybrid cố định)
Tạo candidate set bằng **union** của:
1) **FULLTEXT/BM25** trên `Fact.text` (topK=50)  
2) **VECTOR similarity** trên `Fact.embedding` (topK=100) *(nếu bật vector; nếu chưa bật → skip)*  
3) **Graph expansion**: với entities match mạnh, traverse 1-hop `(Entity)<-[:ABOUT]-(Fact)` (cap 50)

### 6.2 Scoring (deterministic)
Normalize các score về [0,1] rồi tính:
- `score = 0.55 * vec + 0.25 * bm25 + 0.10 * graph_boost + 0.10 * time_boost`

Trong đó:
- `graph_boost`: +0.1 nếu fact share entity với top entity hit; +0.05 nếu từ episode gần đây
- `time_boost`: decay theo `reference_time` (ưu tiên mới) và boost facts `invalid_at=null`

Tie-break:
1) higher `score`
2) newer `ingested_at`
3) stable sort by `fact_id`

### 6.3 Dedupe & freshness merge
- Dedupe theo `fact.id`: giữ record có score cao nhất.
- Merge “recent raw episodes chưa enrich” trong window **5 phút**:
  - chỉ include nếu vector sim ≥ 0.35 (hoặc bm25 hit) để tránh spam.
  - Kết quả raw episodes có `kind="episode"` và cap tối đa 5 items.
  - Raw episodes **không** được gắn `Fact.id`.

### 6.4 Consistency guarantees (v0.1)
- **Read-your-writes**: episode vừa `save` sẽ xuất hiện trong search dưới dạng `kind="episode"` trong ≤ 5s.
- Facts enriched xuất hiện trong search khi ingest job complete (p95 mục tiêu < 10s).
- Temporal correctness: nếu query có `valid_at`, server lọc facts theo validity interval trước khi rank.

