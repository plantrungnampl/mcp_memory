---
title: Ingest and Extraction Pipeline
status: normative
version: 3.0
---
# 06b — Ingest and Extraction Pipeline

## 1. Objective
Biến raw episodes thành memory graph có ích mà không bịa.
Pipeline phải ưu tiên:
- provenance
- deterministic extraction when possible
- conservative linking under ambiguity
- measurable quality

## 2. Pipeline stages
### Stage 0 — admission
- validate size/schema
- assign trust class
- secret scan / policy scan
- store raw episode

### Stage 1 — normalization
- canonicalize timestamps
- normalize whitespace/markup
- split into chunks/spans
- detect language/source modality

### Stage 2 — candidate entity extraction
Sources:
- explicit IDs (`PROJ-123`, PR numbers, paths, symbols)
- code snippets
- stack traces
- structured metadata
- user notes

### Stage 3 — candidate fact extraction
Extract candidates in normalized form:
- `service A depends_on service B`
- `file X defines class Y`
- `ticket T blocked_by issue U`
- `test Z fails_on module M`

Use rule-based extractors where possible before LLM extraction.

### Stage 4 — entity resolution
Resolve candidate references to canonical entities.
Ambiguous cases become unresolved mentions, not forced links.

### Stage 5 — fact upsert / versioning
For each candidate:
- map to fact group if equivalent current/history exists
- create new version or attach as corroborating provenance
- detect conflicts
- compute confidence and salience seed

### Stage 6 — projection updates
- update `memory_search_docs`
- update optional graph projection
- update entity profiles
- update conflict counters

### Stage 7 — metrics/evaluation
Emit:
- extracted_fact_count
- resolved_entity_rate
- ambiguity_rate
- conflict_rate
- secret_redaction_count
- projection_latency

## 3. Rule-first philosophy
Coding-agent memory có rất nhiều deterministic signals:
- paths
- symbols
- stack traces
- issue IDs
- commit hashes
- PR URLs

Dùng rule-based extraction trước sẽ:
- rẻ hơn
- ít hallucination hơn
- dễ debug hơn

LLM extraction chỉ nên dùng cho:
- architecture notes
- incident summaries
- free-form task handoffs
- implicit relationships khó parse bằng rule

## 4. Trust classes and confidence
Confidence SHOULD phụ thuộc:
- extraction source class
- resolver certainty
- number of corroborating episodes
- contradiction history
- deterministic parser signal

Code-derived deterministic facts SHOULD mặc định có trust cao hơn free-form LLM-inferred facts.

## 5. Conflict handling
Pipeline MUST không silently overwrite conflicts.
Khi thấy candidate trái current fact:
- create conflict signal
- maybe create new version if source is authoritative
- else keep candidate as supporting evidence pending correction

## 6. Secret and unsafe content handling
Nếu episode chứa secret-like substrings:
- redact or hash in derived searchable fields
- preserve minimal necessary audit trail
- never echo raw secret into search docs/context packs

## 7. Derivation lineage
Mỗi derived fact SHOULD ghi:
- extraction pipeline version
- model/parser version
- source chunk ids
- rule names or prompt template id

## 8. Failure behavior
Nếu extraction fail:
- raw episode vẫn tồn tại
- observation doc vẫn searchable
- operation marked failed/retryable appropriately
- system không được làm như episode chưa từng được lưu

## 9. Implementation advice
Bắt đầu với 3 extractors mạnh:
1. code entity extractor
2. ticket/PR/commit extractor
3. architecture/incident LLM extractor

Chỉ thêm extractors mới khi có evaluation coverage.
