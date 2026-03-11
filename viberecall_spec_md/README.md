# VibeRecall System Design

Bộ tài liệu này mô tả **trạng thái triển khai hiện tại** của VibeRecall trong repository này, không còn giữ vai trò là spec Neo4j/Fly/MVP kiểu ban đầu.

## Current stack
- Backend: **Python + FastAPI + FastMCP**
- Web control plane: **Next.js 16 App Router**
- Relational state: **Postgres**
- Graph memory runtime: **FalkorDB** với adapter layer `local | falkordb | graphiti`
- Queue / broker / result backend: **Redis + Celery** trong production-shaped runtime
- Deployment target: **Vercel** cho web, **Render** cho API/worker/FalkorDB

## Current public MCP tool surface
Current runtime exposes **25** public tools:
- `viberecall_save_episode`
- `viberecall_save`
- `viberecall_search_memory`
- `viberecall_search`
- `viberecall_get_fact`
- `viberecall_get_facts`
- `viberecall_update_fact`
- `viberecall_pin_memory`
- `viberecall_timeline`
- `viberecall_get_status`
- `viberecall_delete_episode`
- `viberecall_get_operation`
- `viberecall_index_repo`
- `viberecall_get_index_status`
- `viberecall_index_status`
- `viberecall_search_entities`
- `viberecall_get_neighbors`
- `viberecall_find_paths`
- `viberecall_explain_fact`
- `viberecall_resolve_reference`
- `viberecall_merge_entities`
- `viberecall_split_entity`
- `viberecall_get_context_pack`
- `viberecall_working_memory_get`
- `viberecall_working_memory_patch`

## Tài liệu trong thư mục này
1. [00_overview.md](00_overview.md)
2. [01_architecture.md](01_architecture.md)
3. [02_mcp_protocol.md](02_mcp_protocol.md)
4. [03_auth_tenancy.md](03_auth_tenancy.md)
5. [04_tools_contract.md](04_tools_contract.md)
6. [05_data_model_temporal.md](05_data_model_temporal.md)
7. [06_pipelines_latency.md](06_pipelines_latency.md)
8. [07_quota_pricing_tokens.md](07_quota_pricing_tokens.md)
9. [08_observability_security.md](08_observability_security.md)
10. [09_deployment_roadmap.md](09_deployment_roadmap.md)
11. [10_current_state_alignment.md](10_current_state_alignment.md)
12. [appendix_A_mcp_examples.md](appendix_A_mcp_examples.md)
13. [appendix_B_error_catalog.md](appendix_B_error_catalog.md)
14. [appendix_C_export_format.md](appendix_C_export_format.md)
15. [appendix_D_capacity.md](appendix_D_capacity.md)

## Reading order
- Bắt đầu với `00_overview.md` nếu cần hiểu product surface và hard decisions.
- Đọc `01_architecture.md` + `03_auth_tenancy.md` để nắm trust boundaries, scope model, và topology thật sự đang chạy.
- Đọc `04_tools_contract.md` + `05_data_model_temporal.md` + `06_pipelines_latency.md` khi làm việc với MCP/runtime/indexing/canonical memory.
- Đọc `09_deployment_roadmap.md` + `10_current_state_alignment.md` khi chuẩn bị release, docs refresh, hoặc kiểm tra spec drift.
