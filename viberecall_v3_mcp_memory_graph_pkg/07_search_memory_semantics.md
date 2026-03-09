---
title: Search and Context Retrieval Semantics
status: normative
version: 3.0
---
# 07 — Search and Context Retrieval Semantics

## 1. Design goals
Search cho coding agents phải:
- ổn định khi phân trang
- phân biệt facts/entities/episodes
- hỗ trợ temporal queries
- biết giới hạn context size
- trả đủ provenance để agent đánh giá độ tin cậy

## 2. Search surfaces
### `viberecall_search_memory`
General retrieval surface.

### `viberecall_get_context_pack`
Opinionated retrieval cho current task.

### `viberecall_search_entities`
Entity-centric discovery.

### `timeline` behavior
Có thể folded vào `search_memory` hoặc tool riêng; semantics phải nhất quán với temporal model.

## 3. Result grouping
Search SHOULD trả grouped results, không trả một flat mixed list vô nghĩa.
Nhóm chuẩn:
- `facts`
- `entities`
- `episodes`
- `summaries`

## 4. Query filters
Recommended filters:
- `query`
- `entity_kinds[]`
- `relation_types[]`
- `current_only`
- `repo_scope`
- `trust_classes[]`
- `salience_classes[]`
- `as_of_system_time`
- `valid_at`
- `source_kinds[]`
- `limit`

## 5. Snapshot token
Search response MUST include `snapshot_token` or equivalent watermark handle.
Pagination requests MUST echo token to pin semantic view.

Điều này tránh:
- missing/duplicate items giữa pages
- enrich job làm page 2 nhìn thế giới khác page 1
- supersede fact giữa lúc client đang browse

## 6. Ranking
Ranking SHOULD kết hợp:
- lexical/structured match
- entity overlap
- relation relevance
- salience
- freshness
- provenance quality
- current-task repo scope

Nhưng ranking MUST NOT hide explicit exact matches hoàn toàn chỉ vì salience thấp.

## 7. Episode vs fact semantics
Episodes là observations.
Facts là normalized assertions.
Agent cần biết sự khác nhau:
- episodes tốt cho recent debugging breadcrumbs
- facts tốt cho stable working memory

Search result MUST expose `kind` và provenance/trust để model biết item nào đáng tin hơn.

## 8. Context pack algorithm
`get_context_pack(task_prompt, repo_scope, budget)` SHOULD:
1. derive anchor terms/entities from task prompt
2. retrieve top facts
3. retrieve supporting entities
4. retrieve limited recent episodes
5. optionally expand 1-hop graph neighborhood
6. remove redundant items
7. shape output into sections with budget caps

Suggested sections:
- `current_facts`
- `key_entities`
- `recent_observations`
- `open_conflicts_or_unknowns`
- `suggested_followups`

## 9. Budgeting
Context pack MUST honor hard byte/token budget.
If over budget:
- drop low-salience episodes first
- keep pinned/current facts
- compress verbose bodies
- keep ids for follow-up fetches

## 10. Temporal queries
Two useful views:
- `as_of_system_time`: what system knew at time T
- `valid_at`: what was believed to be true in domain at time T

Both MUST be explicit; không được dùng một field mơ hồ đại diện cho cả hai.

## 11. Search and graph interaction
Search MAY use graph expansion signals, but graph traversal must not explode result set.
Default expansion:
- max depth 1 for context pack
- max 3 anchor entities
- relation allowlist

## 12. Output explanation
Each result SHOULD include:
- why matched
- trust/confidence
- last updated
- supporting episode ids or counts
- whether current or superseded

## 13. Anti-patterns
- merge runtime giữa graph DB và SQL raw rows không pin snapshot
- flat result list lẫn lộn entity/fact/episode
- context pack nhồi full raw blobs
