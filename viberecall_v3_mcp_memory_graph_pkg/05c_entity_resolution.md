---
title: Entity Resolution
status: normative
version: 3.0
---
# 05c — Entity Resolution

## 1. Why this matters
Memory graph không đáng tin nếu entity identity trôi dạt:
- cùng một service bị thành 3 nodes
- file rename thành entity mới mất history
- hai classes khác nhau bị merge nhầm
- PR/ticket/incident links bám vào wrong object

## 2. Canonical identity rule
`entity_id` MUST là stable opaque id, không encode trực tiếp path/name/fqn.
Path, name, FQN, external IDs đều chỉ là aliases / observed identifiers.

## 3. Resolution inputs
Resolver nhận:
- extracted name/text span
- observed kind
- surrounding repo/module/path scope
- source episode or code snapshot
- external IDs if any
- code fingerprints if any

## 4. Resolution pipeline
1. deterministic candidate generation
2. fuzzy candidate generation
3. score candidates
4. threshold decision:
   - match existing canonical
   - create new canonical
   - emit ambiguity for manual/privileged follow-up

## 5. Deterministic rules for code entities
### Files
Strong signals:
- repo logical identity
- path alias history
- content hash lineage
- git rename metadata if available

### Symbols
Strong signals:
- repo + snapshot lineage
- symbol kind
- declaring container
- canonical signature
- parser fingerprint

### Services/modules
Strong signals:
- config names
- repo/service directories
- deployment manifests
- stable ids in code or infra definitions

## 6. Thresholds
Recommended decisions:
- score >= high threshold: auto-resolve
- medium band: keep candidates but require privileged resolution or future evidence
- low score: create new canonical

Thresholds SHOULD khác nhau theo entity kind.
Ví dụ file rename resolution có thể aggressive hơn person/team resolution.

## 7. Merge semantics
Merge entities là privileged operation.
Merge phải:
- create `entity_resolution_events`
- redirect old ids to canonical target
- move or rebind aliases
- not destroy provenance
- preserve audit trail

Graph/search/index projections phải rebuild hoặc update theo redirect map.

## 8. Split semantics
Split còn nguy hiểm hơn merge.
Split phải:
- create new canonical entities
- rebind affected facts/aliases/provenance carefully
- record exact reason and affected ranges
- reproject search docs and graph views

## 9. Rename handling
Rename KHÔNG đồng nghĩa entity mới.
Quy tắc:
- file path change -> add alias + optional `renamed_to` lineage
- symbol rename -> add alias, maybe keep same canonical entity if continuity high
- service rename -> may require canonical continuity if deployment/artifact lineage proves sameness

## 10. Ambiguity policy
Nếu resolver không đủ chắc:
- store `UNRESOLVED_MENTION`
- avoid hallucinating a hard link
- allow later background resolution from more evidence

## 11. Entity resolution tables
Canonical schema SHOULD có:
- `entity_aliases`
- `entity_redirects`
- `entity_resolution_events`
- `unresolved_mentions`

## 12. Concurrency
Merge/split must use optimistic locking on involved entities.
Không cho 2 resolution operations chạy chồng trên cùng entity set mà không serialization.

## 13. Invariants
1. redirect graph must be acyclic
2. entity points to at most one active canonical target
3. provenance không mất sau merge/split
4. query by old alias vẫn resolve tới canonical current entity nếu policy cho phép

## 14. Practical rule for v1
V1 nên auto-resolve tốt cho:
- files
- modules
- symbols
- tickets/PRs/commits với external ids

V1 nên conservative cho:
- people
- teams
- incidents
- architectural concepts trừ khi user/operator assert rõ
