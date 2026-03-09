---
title: VibeRecall v3 MCP Memory Graph Design Package
status: proposed
version: 3.0
audience: ai-agent, implementation-team, staff-engineer
---
# VibeRecall v3 — MCP Memory Graph for Coding Agents

Đây là bộ thiết kế mục tiêu cho một **MCP memory graph** dành cho coding agents như **Codex CLI / IDE** và **Claude Code**.

Triết lý cốt lõi:

1. **Core capability phải chạy được chỉ với MCP tools** để tương thích rộng nhất.
2. **Resources và Prompts là optional enhancement**, không phải dependency của correctness.
3. **Postgres là source of truth** cho knowledge canonical; graph backend chỉ là projection/accelerator.
4. **Không bao giờ giả định server có local filesystem của repo người dùng**.
5. **Mọi async workflow phải đi qua operation ledger + transactional outbox**.
6. **Memory graph phải ưu tiên correctness under failure**, không phải demo traversal đẹp.

## Package này sửa các khoảng trống trước đó
Bản này bổ sung đầy đủ các phần còn thiếu để thật sự làm được memory graph cho coding agents:
- relation ontology
- entity resolution / merge / split
- salience / decay / retention / compaction
- graph query semantics
- code indexing cho local dirty workspace qua workspace bundle
- MCP resources/prompts contract
- extraction pipeline và evaluation loop
- client integration notes cho Codex CLI / Claude Code
- implementation backlog để AI agent có thể code theo phase

## Đọc theo thứ tự
1. `00_agent_guide.md`
2. `01_goals_non_goals.md`
3. `02_architecture_overview.md`
4. `03_mcp_runtime_protocol.md`
5. `04_authn_authz_policy.md`
6. `05_data_model_source_of_truth.md`
7. `05b_relation_ontology.md`
8. `05c_entity_resolution.md`
9. `05d_memory_salience_retention.md`
10. `06_async_operations_outbox.md`
11. `06b_ingest_extraction_pipeline.md`
12. `07_search_memory_semantics.md`
13. `07b_graph_query_semantics.md`
14. `08_code_indexing_design.md`
15. `09_tools_contract.md`
16. `09b_resources_prompts_contract.md`
17. `10_reliability_failure_modes.md`
18. `11_observability_security.md`
19. `11b_extraction_quality_evaluation.md`
20. `12_deployment_and_operability.md`
21. `13_cost_capacity_quotas.md`
22. `14_migration_plan.md`
23. `15_open_questions_and_adrs.md`
24. `16_agent_integration_codex_claude.md`
25. `17_implementation_backlog.md`

## Cấu trúc package
- `00_*` đến `17_*`: tài liệu normative / working cho implementation
- `appendix_*`: examples, error catalog, schema, test matrix, bundle format

## Tóm tắt một câu
VibeRecall v3 là một **project-scoped remote MCP server** + **optional local workspace bridge**, cho phép coding agents ghi nhận observation, chuẩn hóa thành facts/entities/edges có provenance, truy vấn memory graph ổn định theo thời gian, và index code an toàn mà không cần raw server filesystem access.

## Nguyên tắc ưu tiên khi implementation
1. Làm đúng **source of truth**, **outbox**, **idempotency**, **tool contract** trước.
2. Sau đó mới làm **graph projection**, **advanced path finding**, **resources/prompts**.
3. Không ship auto-extraction nếu chưa có evaluation loop và conflict handling.
