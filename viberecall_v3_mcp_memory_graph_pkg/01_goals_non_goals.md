---
title: Goals and Non-Goals
status: normative
version: 3.0
---
# 01 — Goals and Non-Goals

## 1. Product goal
Xây một **project-scoped MCP memory graph** giúp coding agents:
- ghi nhận phát hiện trong quá trình làm việc
- truy xuất context đáng tin cậy cho task hiện tại
- sửa facts sai mà vẫn giữ lịch sử
- hiểu mối quan hệ giữa code entities, tickets, incidents, decisions
- truy vấn memory theo graph, theo thời gian, theo provenance
- đồng bộ code understanding từ repo snapshot an toàn

## 2. Functional goals
Hệ thống MUST hỗ trợ:
1. lưu raw episodes có provenance
2. chuẩn hóa entities, facts, edges
3. temporal fact history
4. context pack retrieval ổn định
5. graph neighborhood/path queries với giới hạn rõ
6. code index snapshots với `latest READY`
7. strong authz theo tool scope
8. budget/quota enforcement
9. rebuild projections từ canonical state
10. operation polling cho async tasks

## 3. Non-functional goals
- `save_episode` ACK p95 dưới ngưỡng interactive
- search/context pack trong mức chấp nhận được cho coding workflow
- partial dependency failure phải degrade có kiểm soát
- operators có thể audit vì sao một fact tồn tại / bị sửa / bị supersede
- noisy-neighbor được giới hạn bằng quotas và queue lanes

## 4. Coding-agent-specific goals
Thiết kế này tối ưu cho agent làm code, nên memory cần lưu được:
- kiến trúc hệ thống
- service boundaries
- file/module/class/function identities
- ownership / review / PR / ticket linkage
- recurring failures, fixes, root causes
- repo-local conventions và developer preferences
- current task handoff / intent / constraints

## 5. Hard constraints
- remote MCP server không được giả định nhìn thấy local repo của user
- graph backend không được là single source of truth
- admin/destructive capabilities không được mặc định lộ cho mọi token
- client capability khác nhau giữa Codex / Claude / API connectors, nên core path phải tool-first
- bundle upload phải sandboxed và bounded

## 6. Non-goals
- consumer chatbot memory chung cho mọi project
- world knowledge graph không provenance
- autonomous self-editing memory không guardrails
- real-time collaborative graph editor trong v1
- multi-region active-active replication trong v1
- cross-project global recommendations trong v1
- full semantic code search cluster riêng trong v1 nếu Postgres projection còn đủ

## 7. Success criteria
Một implementation đạt spec này nếu:
- coding agent dùng được memory server hằng ngày mà không gây hành vi kỳ quặc vì stale/duplicate context
- fact corrections không bị race dẫn đến hai current versions
- code index không phá correctness khi run fail giữa chừng
- graph queries trả về subgraph vừa đủ, không thổi phồng context window
