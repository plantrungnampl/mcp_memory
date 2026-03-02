# VibeRecall Pro (Native MCP) — System Design Spec v0.1

Bộ tài liệu thiết kế hệ thống *MCP-first* cho **VibeRecall** (Memory-as-a-Service cho coding agents).  
Tài liệu tập trung vào **MCP Remote Server**, **auth/tenancy**, **tool contract**, **temporal memory**, **pipeline latency**, và **pricing theo token**.


## Tech decisions (v0.1)
- Backend: **Python (FastMCP + FastAPI)**
- Graph DB: **Neo4j**


## Mục lục
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
11. [appendix_A_mcp_examples.md](appendix_A_mcp_examples.md)
12. [appendix_B_error_catalog.md](appendix_B_error_catalog.md)
13. [appendix_C_export_format.md](appendix_C_export_format.md)
14. [appendix_D_capacity.md](appendix_D_capacity.md)

## Quick start (triển khai)
- Bắt đầu từ **00_overview.md** để chốt scope và quyết định nền tảng.
- Sau đó đọc **02_mcp_protocol.md** + **03_auth_tenancy.md** để xây Gateway đúng chuẩn.
- Cuối cùng implement theo **04_tools_contract.md** và **06_pipelines_latency.md**.
