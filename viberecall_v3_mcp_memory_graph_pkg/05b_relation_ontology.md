---
title: Relation Ontology
status: normative
version: 3.0
---
# 05b — Relation Ontology

## 1. Purpose
Memory graph chết nhanh nếu relation types bị nổ thành free-form strings.
Tài liệu này định nghĩa catalog relation đủ giàu cho coding agents nhưng vẫn kiểm soát được.

## 2. Design rules
1. Relation names MUST ngắn, rõ chiều.
2. Relation semantics MUST không chồng lấn quá nhiều.
3. Relation mới SHOULD qua ADR nếu ảnh hưởng ranking/query semantics.
4. Polarity/conflict là thuộc tính của fact version, không encode bằng relation name mới lung tung.
5. Graph projection và search ranking phải hiểu relation class.

## 3. Core relation catalog
| Relation | Inverse | Typical subject -> object | Notes |
|---|---|---|---|
| `contains` | `contained_by` | repo/dir/module -> dir/file/module | cấu trúc |
| `defines` | `defined_in` | file/module -> class/function | code structure |
| `declares` | `declared_in` | class/interface -> method/field | code structure |
| `calls` | `called_by` | function/method -> function/method | code flow |
| `imports` | `imported_by` | file/module -> module/package | code dependency |
| `implements` | `implemented_by` | class/service -> interface/spec | architecture |
| `extends` | `extended_by` | class -> class | inheritance |
| `depends_on` | `dependency_of` | service/module -> service/lib | architecture |
| `uses_api_of` | `api_used_by` | service/client -> api/service | runtime linkage |
| `reads_from` | `read_by` | service/job -> db/topic/cache | data flow |
| `writes_to` | `written_by` | service/job -> db/topic/cache | data flow |
| `emits_event_to` | `event_received_from` | service -> queue/topic | async flow |
| `consumes_event_from` | `event_consumed_by` | service -> queue/topic | async flow |
| `tests` | `tested_by` | test_case -> function/module/service | validation |
| `fixes` | `fixed_by` | PR/commit/change -> bug/incidents/tickets | workflow |
| `blocked_by` | `blocks` | task/ticket/change -> task/ticket/dependency | workflow |
| `owned_by` | `owns` | service/module/repo -> person/team | ownership |
| `reviewed_by` | `reviews` | PR/change -> person | workflow |
| `mentioned_in` | `mentions` | entity/fact -> episode/ticket/pr | provenance-ish |
| `same_as` | `same_as` | entity -> entity | resolution only |
| `renamed_to` | `renamed_from` | entity -> entity/alias target | identity evolution |
| `supersedes` | `superseded_by` | fact/change/decision -> fact/change/decision | temporal/logical |
| `introduced_in` | `introduces` | entity/bug/behavior -> commit/release | time/version |
| `removed_in` | `removes` | entity/behavior -> commit/release | time/version |
| `generated_from` | `generated` | summary/index artifact -> episode/bundle | derivation |
| `summarizes` | `summarized_by` | summary -> episode/fact group | compaction |

## 4. Relation classes
- `CODE_STRUCTURE`
- `ARCHITECTURE`
- `RUNTIME_FLOW`
- `WORKFLOW`
- `IDENTITY`
- `TEMPORAL`
- `DERIVATION`

Ranking/query logic SHOULD hiểu class này.

## 5. Constraints
Một số relation có subject/object kind constraints.
Ví dụ:
- `calls`: subject/object phải là callable-like entities
- `implements`: subject = class/service; object = interface/spec
- `owned_by`: object = person/team
- `same_as`: subject/object = same high-level kind family

## 6. Transitivity
Chỉ một số relation được coi là transitive trong path reasoning:
- `contains`
- `depends_on` (có điều kiện, thường chỉ cho limited depth)
- `same_as`

`calls` không nên coi là transitive cho retrieval vì dễ làm graph explosion.

## 7. Confidence policy
Relation có source classes:
- `DETERMINISTIC_CODE_INDEX`
- `HEURISTIC_CODE_INDEX`
- `LLM_EXTRACTED`
- `USER_ASSERTED`
- `OPERATOR_ASSERTED`

Query result phải expose source/confidence để agent không nhầm hard truth với heuristic.

## 8. Conflict policy
Hai fact versions có thể conflict nếu cùng subject + relation + object/value domain nhưng statement ngược nhau.
Conflict không được giải bằng cách overwrite âm thầm; phải:
- create superseding version
- hoặc lưu current conflicting candidates với conflict flag nếu domain cho phép
- hoặc require operator resolution

## 9. Ontology evolution
Relation mới cần:
- migration cho `relation_types`
- ranking and query semantics review
- examples
- backward compatibility story

## 10. Anti-patterns
Không dùng:
- `related_to`
- `associated_with`
- `connected_to`
- `references` nếu có relation cụ thể hơn
- relation name encode time/confidence, ví dụ `maybe_calls`, `old_depends_on`
