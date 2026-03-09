---
title: Memory Salience, Retention and Compaction
status: normative
version: 3.0
---
# 05d — Memory Salience, Retention and Compaction

## 1. Problem
Nếu chỉ lưu thêm memory mãi mãi, retrieval sẽ xuống cấp:
- context pack đầy noise
- stale facts lấn current facts
- repeated observations chèn nhau
- storage và cost tăng không kiểm soát

## 2. Salience model
Mỗi fact/episode/entity SHOULD có `salience_score` và `salience_class`.

Suggested classes:
- `PINNED`
- `HOT`
- `WARM`
- `COLD`
- `ARCHIVED`
- `TOMBSTONED`

## 3. Salience factors
Score nên kết hợp:
- recency
- frequency / repeated corroboration
- provenance quality
- trust class
- code relevance to current repo/task
- user pin/manual importance
- conflict penalty
- retrieval click/use feedback
- type prior (architecture decisions > transient log lines)

## 4. Pinning policy
Có 2 loại pin:
- explicit user/operator pin
- policy pin (ví dụ current architecture decisions, repo conventions)

Pin MUST override decay trừ khi deleted or superseded.

## 5. Retention classes by object type
### Episodes
- raw logs/debug snippets: short-medium TTL unless referenced by facts
- architecture/task handoff notes: longer TTL
- user preferences: long TTL, high salience

### Facts
- current facts: retain
- superseded facts: retain for audit and temporal queries
- invalidated low-value facts: archive/compact later

### Index artifacts
- latest READY always keep
- keep one rollback snapshot
- older snapshots GC by policy

## 6. Compaction
Compaction SHOULD tạo summary facts/episodes thay vì hard-delete bừa.
Ví dụ:
- 50 repeated error observations -> 1 summary fact + top supporting episodes
- 20 similar debugging notes -> 1 compacted summary with provenance links

Rule:
- compaction MUST preserve provenance chain
- original objects MAY go archived/hidden, không xóa nếu còn audit value

## 7. Decay policy
- salience decay chạy background
- decay rate khác nhau theo object class
- retrieval hit / recent edits có thể boost salience
- superseded or contradicted facts decay nhanh hơn current pinned facts

## 8. Forgetting vs deletion
- **Forgetting** = giảm ranking/visibility
- **Archival** = giữ nhưng rời hot path
- **Deletion** = remove/tombstone due policy or explicit request

Hệ thống MUST phân biệt 3 thứ này.

## 9. Retrieval usage feedback
Context pack pipeline SHOULD record:
- item surfaced
- item used/quoted by agent if inferable
- subsequent correction or user dissatisfaction

Signals này dùng để tune salience nhưng không được silently rewrite truth.

## 10. Cost-aware policy
Khi project vượt storage budget:
- compact summaries first
- archive low-trust repetitive episodes
- reduce vector/embedding retention if enabled
- keep canonical facts and audit-critical history

## 11. Guardrails
Không decay mạnh các memory loại:
- long-lived architectural decisions
- repo conventions
- entity aliases for active code entities
- current ownership and service boundaries
