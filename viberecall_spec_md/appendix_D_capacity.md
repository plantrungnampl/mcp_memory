# Appendix D — Capacity assumptions & SLO sizing

## 1) Target load
- Projects: 1,000+
- Daily active projects: vài trăm
- Peak concurrent MCP sessions: vài trăm
- Peak short-burst tool traffic: hàng chục RPS

## 2) Dataset assumptions
- Episodes per project: median vài nghìn, p95 hàng chục nghìn
- Facts per project: cao hơn episodes nhiều lần tùy enrichment
- Code index snapshot: hàng trăm đến hàng nghìn files, hàng nghìn symbols/entities/chunks

## 3) SLO interpretation
- `save` ACK p95 < 200ms khi queue path khỏe
- `search` p95 < 1.5s phụ thuộc canonical search-doc reads, filters, và runtime dependency health
- ingest completion p95 < 10s phụ thuộc queue depth và backend dependencies
- index completion phụ thuộc repo size và current public `FULL_SNAPSHOT` indexing path

## 4) What to track
- p50/p95 initialize latency
- p50/p95 tool latency theo tool
- queue depth theo lane
- worker job duration
- FalkorDB dependency health / graph latency
- index run duration và READY snapshot freshness
- token burn / usage growth per project
