---
title: Graph Query Semantics
status: normative
version: 3.0
---
# 07b — Graph Query Semantics

## 1. Scope
Tài liệu này định nghĩa semantics cho graph-native tools để coding agents reason trên memory graph thay vì chỉ search keyword.

## 2. Required graph tools
- `viberecall_get_neighbors`
- `viberecall_find_paths`
- `viberecall_explain_fact`
- `viberecall_search_entities`
- `viberecall_resolve_reference` (optional but recommended)

## 3. `get_neighbors`
Purpose:
- cho một anchor entity, lấy neighborhood có kiểm soát

Inputs:
- `entity_id`
- `direction = OUT | IN | BOTH`
- `relation_types[]` optional
- `depth` default 1, hard max 2 or 3
- `current_only`
- `valid_at` / `as_of_system_time`
- `limit`

Output:
- anchor entity
- neighbor entities
- connecting facts/edges
- truncation info

## 4. `find_paths`
Purpose:
- tìm path ngắn/nghĩa giữa 2 entities

Inputs:
- `src_entity_id`
- `dst_entity_id`
- `relation_types[]` optional allowlist
- `max_depth` hard bounded
- `current_only`
- temporal filters

Output:
- top K paths
- each path = ordered entity/fact steps
- path score
- explanation of pruning/truncation

Path scoring SHOULD prefer:
- higher-confidence edges
- fewer hops
- code/architecture relations over weak mention links
- current facts over archived history

## 5. `explain_fact`
Purpose:
- trả lời “vì sao fact này tồn tại / current / superseded?”

Output SHOULD include:
- fact version body
- fact group lineage
- prior/next versions if any
- supporting episode summaries
- extraction and resolution provenance
- conflicts and confidence

## 6. `resolve_reference`
Useful for agents khi gặp text span mơ hồ.
Input: text mention + optional scope.
Output:
- candidate entities
- confidence
- reason signals
- suggestion whether follow-up disambiguation is needed

## 7. Canonical vs projected execution
Graph query MAY run on:
- recursive SQL / canonical tables
- optional graph projection backend

Nhưng kết quả exposed cho client MUST obey canonical semantics:
- respect current_only / temporal filters
- no edges that do not correspond to canonical facts or code index edges
- no phantom entities from stale projection

## 8. Boundedness
Graph queries MUST have hard guards:
- max depth
- max nodes
- max edges
- max execution time
- relation allowlist defaults

Nếu truncated, response MUST say truncated.

## 9. Graph trust
Response SHOULD label each edge/fact with:
- source class
- confidence
- trust class

Agent không nên nhận một path rồi tưởng mọi edge đều equally reliable.

## 10. Coding-agent usage patterns
Typical patterns:
- “what depends on this service?”
- “which tests cover this module?”
- “why do we think file X owns behavior Y?”
- “what path links incident I to service S?”
- “what changed between old and current fact?”

## 11. Anti-patterns
- unlimited k-hop traversals
- using `mentioned_in` as default relation in path finding
- hiding supersede/conflict lineage
- returning giant subgraphs without prioritization
