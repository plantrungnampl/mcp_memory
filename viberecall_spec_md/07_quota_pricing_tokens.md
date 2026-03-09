# 07 — Pricing, Quota & Usage

## 1) VibeTokens
VibeTokens là đơn vị metering nội bộ cho usage analytics và billing surfaces.

Nguồn usage có thể gồm:
- input/output tokens từ provider calls
- embedding / enrichment / rerank usage nếu pipeline sử dụng
- lightweight heuristic estimates cho một số tool paths

## 2) Current runtime policy
- MCP runtime hiện là **all-users-free** cho mọi bearer token hợp lệ
- `plan` vẫn được lưu ở project/token metadata
- usage vẫn được ghi nhận để hiển thị dashboard và phục vụ pricing/billing về sau
- quota hiện **không hard-block** public MCP tools

## 3) Quota numbers đang tồn tại trong config
- Free: `100_000` VibeTokens / tháng
- Pro: `5_000_000` VibeTokens / tháng
- Team: `20_000_000` VibeTokens / tháng

Các ngưỡng này hiện được dùng làm planning/analytics baseline, không phải runtime gate.

## 4) Usage events
Mỗi event có thể gắn:
- `project_id`
- `token_id`
- `tool`
- provider / model metadata nếu có
- `vibe_tokens`
- status / timestamp

Dashboard reads hiện lấy từ Postgres-backed usage data và rollups.

## 5) Normalize formula
Current config giữ:
- `vibe_in_mul`
- `vibe_out_mul`

Heuristic examples:
- `save` và `update_fact` có estimate dựa trên payload length
- các tool nhẹ mặc định charge rất thấp hoặc 1-unit placeholder cho analytics

## 6) Future pricing note
Nếu sau này khôi phục quota enforcement hoặc paid gating:
- không được phá public MCP tool contract
- phải coi đó là policy-layer change, không phải transport/schema breaking change
