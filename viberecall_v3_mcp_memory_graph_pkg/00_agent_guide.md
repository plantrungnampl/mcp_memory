---
title: Agent Implementation Guide
status: normative
version: 3.0
---
# 00 — Agent Implementation Guide

Tài liệu này nói cho **AI implementation agent** cách đọc package và cách biến spec thành code.

## 1. Mục tiêu của gói spec
Mục tiêu không phải tạo một “graph demo”. Mục tiêu là tạo một **production-capable MCP memory graph** cho coding agents, nơi:
- write path không mất dữ liệu khi partial failure
- correction không làm hỏng history
- graph projection có thể rebuild
- search / context pack ổn định đủ để agent tin dùng
- code indexing xử lý được cả repo remote và dirty local workspace

## 2. Thứ tự ưu tiên nếu phải cắt scope
### P0 — correctness foundations
- Postgres canonical schema
- tool authz/scopes
- operation ledger + transactional outbox
- `save_episode`, `search_memory`, `get_context_pack`, `get_operation`
- `update_fact` transactional compare-and-swap

### P1 — graph-capable memory
- entities, relation catalog, provenance
- entity resolution
- `search_entities`, `get_neighbors`, `explain_fact`
- salience scoring v1

### P2 — code intelligence
- secure indexing flow
- `index_repo`, `get_index_status`
- code-derived entity extraction
- relation extraction from code index

### P3 — advanced graph + ergonomics
- `find_paths`
- resources/prompts
- graph projection backend
- compaction / summarization
- merge/split entities

## 3. Precedence khi docs xung đột
Nếu có xung đột, ưu tiên:
1. `02_architecture_overview.md`
2. `05_data_model_source_of_truth.md`
3. `09_tools_contract.md`
4. `06_async_operations_outbox.md`
5. appendices

`README.md` là summary, không override normative docs.

## 4. Assumptions cho implementation đầu
- single-region deployment
- Python/FastAPI hoặc tương đương là chấp nhận được
- Postgres, Redis, object storage, worker queue
- graph projection backend có thể feature-flagged và vắng mặt ở phase đầu
- no Kafka unless measurement proves need
- no global cross-project memory in v1

## 5. Những điều AI agent KHÔNG được làm
- không tạo design phụ thuộc vào raw `repo_path` server-local
- không để graph DB giữ truth duy nhất
- không dùng eventual consistency mơ hồ cho `update_fact`
- không merge runtime giữa nhiều stores cho search nếu có thể tránh
- không expose destructive/admin tools cho mọi token
- không thêm quá nhiều tools nếu chưa có plan token-scoped discovery

## 6. Definition of done ở mức hệ thống
Hệ thống chỉ được xem là “đủ dùng” khi:
- có test cho duplicate delivery / outbox publish fail / concurrent fact update
- can rebuild search docs và graph projection từ canonical data
- search pagination có `snapshot_token`
- local dirty workspace có flow index an toàn qua bundle
- tool outputs có `structuredContent` tương ứng `outputSchema`
- metrics/audit đủ để on-call dò một operation từ request tới worker

## 7. Suggested implementation order theo repo
1. schema + migrations
2. authz middleware
3. operation/outbox framework
4. MCP tool registry + schemas
5. canonical repositories/services
6. workers
7. search/context pack
8. indexing
9. graph projection
10. resources/prompts
11. evaluation harness
