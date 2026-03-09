---
title: Extraction Quality and Evaluation
status: normative
version: 3.0
---
# 11b — Extraction Quality and Evaluation

## 1. Why this exists
Một memory graph có thể đúng về transaction nhưng sai về knowledge.
Vậy nên extraction/resolution phải có evaluation loop riêng.

## 2. Quality dimensions
- fact extraction precision
- fact extraction recall
- entity resolution accuracy
- false merge rate
- conflict detection accuracy
- provenance completeness
- context pack relevance
- stale/noise rate in retrieval

## 3. Gold datasets
Build ít nhất 4 gold sets:
1. architecture notes -> facts/entities
2. incident/debug traces -> entities/causal facts
3. code index outputs -> deterministic relationships
4. handoff/task notes -> useful retrieval context

## 4. Offline evaluation
Mỗi pipeline version SHOULD được replay trên gold sets.
Store:
- expected entities
- expected relations
- expected conflicts
- expected retrieval anchors

## 5. Online evaluation
Collect signals:
- user/agent corrections after retrieval
- fact supersede rate shortly after extraction
- context pack acceptance/use rate
- unresolved mention backlog
- graph query follow-up success

## 6. Launch thresholds
Suggested stop-ship thresholds:
- false merge rate too high
- secret redaction misses
- context pack noise causing repeated wrong edits
- extraction hallucination above tolerated threshold on key datasets

## 7. Canary strategy
- run new extractors in shadow mode first
- compare projected facts against current pipeline
- do not auto-promote extractor versions without diff review on sampled projects

## 8. Evaluation artifacts
Each run SHOULD record:
- pipeline version
- dataset version
- metric summary
- error buckets
- sample false positives / false negatives

## 9. Coding-agent-specific metrics
- “did retrieved memory reduce follow-up search churn?”
- “did context pack include the right code entities?”
- “did path queries explain a failure/root cause correctly?”
- “how often did agent need to overwrite wrong fact?”

## 10. Practical rule
New extractor or relation type SHOULD ship behind flag until:
- offline metrics acceptable
- shadow traffic stable
- sampled manual review passes
