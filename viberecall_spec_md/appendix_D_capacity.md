# Appendix D — Capacity assumptions & SLO sizing (v0.1)

## 1) Target load (MVP)
- Projects: 1,000
- Daily active projects: 200
- Peak concurrent IDE sessions: 300
- Average tool calls: 1 rps overall
- Peak burst: 30 rps overall (short bursts)
- Save/search ratio: 40% save / 60% search

## 2) Dataset size
- Episodes per project: median 2,000 (MVP), p95 20,000
- Facts per project: ~ 5–20x episodes (tuỳ extraction)
- Storage:
  - median raw text per episode: 2–8KB

## 3) SLO interpretation
- `save` ACK p95 < 200ms: achievable vì không đợi LLM/embeddings.
- `search` p95 < 1.5s: với BM25 + (optional vector) + cache; p95 phụ thuộc Neo4j index + cold starts.
- Ingest completion p95 < 10s: phụ thuộc queue depth và provider latency.

## 4) Benchmark plan
- Synthetic workload theo target load
- Track: p50/p95 tool latency, queue depth, ingest duration, Neo4j query time, token burn rate.
