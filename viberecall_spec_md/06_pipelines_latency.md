# 06 — Pipelines & Latency

## 1) Save pipeline

### Phase A — sync ACK
1. auth + project binding + scope check
2. rate limit + payload validation
3. persist raw episode vào Postgres hoặc object storage
4. enqueue ingest job
5. trả `{ status: "ACCEPTED", episode_id, enrichment: { mode: "ASYNC", job_id } }`

Mục tiêu:
- `save` ACK nhanh vì không chờ graph enrichment

### Phase B — async ingest
1. load raw episode
2. ingest vào memory core / graph backend
3. materialize facts/entities/provenance
4. update episode enrichment status + summary
5. ghi usage event và audit log

## 2) Search pipeline
1. query graph-backed facts trong project scope
2. apply temporal/file/tag/entity filters
3. query recent raw episodes chưa enrich từ Postgres
4. merge hai nguồn kết quả
5. paginate bằng merged opaque cursor

## 3) Update fact pipeline
1. validate `effective_time`
2. enqueue update job
3. worker invalidate old fact + create new fact
4. ghi audit / usage

## 4) Delete episode pipeline
1. validate episode ownership trong project
2. cleanup graph memory first
3. delete Postgres row và object-storage artifact nếu có
4. trả trạng thái chi tiết theo từng subsystem

Delete phải fail với runtime error chuẩn nếu graph cleanup không hoàn tất; không được giả vờ `DELETED`.

## 5) Export pipeline
Export hiện là **control-plane** flow:
1. owner tạo export qua control-plane route
2. backend tạo `exports` record + enqueue export job
3. worker collect episodes + facts + entities + relationships
4. build JSON v1 artifact
5. sign download URL và expose qua export endpoints

## 6) Inline migration / retention / purge
- `migrate-inline-to-object`: chuyển large historical inline episodes sang object storage
- `retention`: dọn dữ liệu cũ theo project policy
- `purge`: xóa toàn bộ project artifacts ở relational/object/graph layers

## 7) Code indexing pipeline
1. `index_repo` tạo `code_index_runs` row ở trạng thái `QUEUED`
2. queue backend chạy indexing job
3. job scan repo, materialize files/entities/chunks
4. mark run `READY` hoặc `FAILED`
5. read-paths chỉ đọc latest `READY`

`diff` mode hiện:
- fail fast nếu thiếu refs
- không silently fallback sang full snapshot khi git diff lỗi
- zero-change diff giữ nguyên previous READY snapshot

## 8) Context-pack pipeline
1. lấy latest `READY` index snapshot
2. rank entities/chunks theo query
3. build `architecture_map`, `relevant_symbols`, `citations`
4. merge thêm timeline evidence có liên quan
5. trả về một pack tối ưu cho agent reasoning
