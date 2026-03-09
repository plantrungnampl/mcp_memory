---
title: Architecture Overview
status: normative
version: 3.0
---
# 02 — Architecture Overview

## 1. High-level topology

```text
                     +------------------------------+
                     |        Browser / Owner UI    |
                     +---------------+--------------+
                                     |
                                     v
                     +------------------------------+
                     |      Web Control Plane       |
                     +---------------+--------------+
                                     |
                                     v
                     +------------------------------+
                     |       Control-plane API      |
                     +---------------+--------------+
                                     |
                    +----------------+-------------------+
                    |                                    |
                    v                                    v
           +-------------------+                +-------------------+
           |     Postgres      |                |       Redis       |
           | canonical truth   |                | session/rl/queue  |
           +---------+---------+                +---------+---------+
                     ^                                    ^
                     |                                    |
      +--------------+---------------+      +-------------+-----------+
      |                              |      |                         |
      v                              |      v                         |
+---------------------+              | +---------------------+        |
|   MCP Runtime HTTP  |--------------+ |   Worker Lanes      |--------+
| tools/resources/... |                | ingest/index/...    |
+----------+----------+                +----------+----------+
           |                                      |
           v                                      v
+---------------------+                +-----------------------+
|   Object Storage    |                | Optional Graph        |
| blobs/bundles       |                | Projection Backend    |
+---------------------+                +-----------------------+

Optional for local dirty workspaces:

+---------------------+          uploads bundle / manifests
| Local Workspace     |------------------------------------>
| Bridge (STDIO/CLI)  |
+---------------------+
```

## 2. Architectural split
### A. Web control plane
Dùng cho owner / operator:
- project settings
- token lifecycle
- budget/quota visibility
- uploads, exports, graph UI
- audit and operations views

### B. Control-plane API
Chịu trách nhiệm:
- owner auth/session
- issuing PATs
- workspace bundle upload initiation
- export orchestration
- admin / maintenance endpoints

### C. MCP runtime
Chịu trách nhiệm:
- remote MCP endpoint per project
- tool/resources/prompts discovery theo token scope
- authn/authz, rate limit, budgets
- synchronous canonical reads/writes
- operation row + outbox row creation

### D. Local workspace bridge (optional nhưng rất hữu ích)
Đây là thành phần local để coding agent chạy cạnh repo hiện tại.
Nó KHÔNG giữ source of truth; nó chỉ:
- snapshot hoặc diff repo local
- upload bundle an toàn
- có thể expose helper resources về workspace local nếu muốn
- tránh anti-pattern “cloud server đọc local repo path”

### E. Workers
Tách tối thiểu 5 lane:
- `ingest-high`
- `projection-medium`
- `index-low`
- `export-low`
- `maintenance-low`

### F. Data stores
- Postgres: canonical truth
- Redis: session, counters, queue broker, short-lived coordination
- Object storage: bundles, big blobs, exports
- Graph projection backend: optional accelerator / UI backend

## 3. Criticality classes
### Tier-0
- Postgres
- Redis cho session/rate limits/broker

### Tier-1
- Object storage (large payloads, bundles, exports)

### Tier-2
- graph projection backend
- graph UI
- optional resources/prompts caching

## 4. Core flows
### 4.1 Save memory
1. agent gọi `viberecall_save_episode`
2. runtime authz + rate limit + size guard
3. optional blob handoff nếu payload lớn
4. trong 1 transaction:
   - insert `episodes`
   - insert immediate observation docs
   - insert `operations`
   - insert `outbox_events`
5. return `ACCEPTED`
6. worker enrich thành entities/facts/provenance/search projection/graph projection

### 4.2 Search + context
1. agent gọi `search_memory` hoặc `get_context_pack`
2. runtime đọc từ Postgres canonical/projection tables
3. optionally use graph projection as accelerator
4. return grouped results + `snapshot_token`

### 4.3 Fact correction
1. agent gọi `update_fact`
2. runtime validate CAS precondition
3. trong 1 transaction:
   - supersede old fact version
   - insert new current version
   - update current head
   - audit + outbox
4. return committed ids

### 4.4 Code indexing
Hai mode hợp lệ:
- `git`: worker clone vào sandbox
- `workspace_bundle`: local bridge hoặc owner workflow upload bundle trước

Read path chỉ đọc `latest READY` snapshot.

### 4.5 Graph querying
`get_neighbors` / `find_paths` / `explain_fact` đọc canonical graph-shaped tables; nếu graph projection tồn tại, runtime MAY dùng nó làm accelerator nhưng phải giữ semantics như canonical store.

## 5. Invariants
1. Không có domain truth chỉ tồn tại trong graph backend.
2. Không có public read path phụ thuộc duy nhất vào graph backend.
3. Không service nào assume repo của user tồn tại ở local filesystem của cloud worker.
4. Tool discovery phải phụ thuộc token scope; không lộ full admin surface cho read-only token.
5. Derived projections phải rebuild được từ canonical data.
6. Local workspace bridge là optional companion, không phải canonical service.
