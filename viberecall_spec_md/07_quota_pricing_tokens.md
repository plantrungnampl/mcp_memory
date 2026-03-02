# 07 — Pricing & Usage (Token-based)

> Pricing theo **token** như yêu cầu. Để tránh tranh cãi/cost blow-up, cần định nghĩa rõ “token” và cơ chế metering.

## 1) Định nghĩa VibeTokens
**VibeTokens** = tổng tokens hệ thống tiêu thụ cho project, gồm:
- LLM tokens cho extraction/summarization (nếu có)
- Embedding tokens (nếu có)
- Optional rerank tokens (nếu có)

Nguồn số liệu:
- Lấy usage tokens từ provider (OpenAI/Groq/…) rồi normalize → VibeTokens.

## 2) Metering events
Mỗi tool/job sinh `usage_event`:
- `project_id`, `token_id`, `tool_name`
- `provider`, `model`
- `input_tokens`, `output_tokens`, `vibe_tokens`
- `timestamp`, `status`

Counters:
- Redis: realtime monthly counters
- Postgres: daily/monthly rollups (billing + dashboard)

## 3) Quota enforcement
- Pre-check quota ở Gateway (Redis counter).
- Hard stop khi vượt (tool isError + 429/403).
- Optional: grace/overage (paid plans).

## 4) Pricing (v0.1)
### Free
- 100k VibeTokens / tháng
- 5 projects
- MCP basic tools (save/search/timeline) + limit rate

### Pro ($9/mo)
- Token cap lớn hoặc “Unlimited* (fair use)”
- MCP full tools
- Priority queue + higher limits
- Team sharing basic

### Team ($29/mo)
- Seat-based + token pool
- Shared projects + RBAC + audit log
- Admin controls

## 5) Fair use
(v0.1 không dùng “Unlimited*”, giữ mục này để tham khảo nếu sau này muốn đổi model pricing.)


## 6) Normalize formula (chốt cứng v0.1)

### 6.1 VibeTokens formula
Mỗi provider call tạo `provider_tokens`:
- `in_tokens`, `out_tokens`
Tính VibeTokens:
- `raw = in_tokens * in_mul + out_tokens * out_mul`
- `vibe_tokens = ceil(raw * model_factor)`

Defaults (v0.1):
- `in_mul = 1.0`
- `out_mul = 1.0`
- `model_factor` lấy từ config theo (provider, model). Base factor = 1.0.

> Lý do: cùng “token” nhưng cost khác nhau giữa models; `model_factor` cho phép pricing thống nhất.

### 6.2 Charge timing (async jobs)
- Charge **khi provider call complete** (không charge lúc enqueue).
- Nếu job fail trước provider call → 0 token.
- Nếu job retry và gọi provider nhiều lần → charge theo tokens *thực tế* (không double-count cùng request).
- Pre-check quota:
  - dùng `estimated_tokens` (heuristic) với safety factor 1.2 để tránh runaway.
  - reconcile khi complete.

## 7) Pricing (chốt cứng v0.1 — token caps, không “Unlimited”)
- **Free**: 100k VibeTokens/mo
- **Pro ($9/mo)**: 5,000,000 VibeTokens/mo
- **Team ($29/mo)**: 20,000,000 VibeTokens/mo + seat-based

> “Unlimited*” bị loại khỏi v0.1 để tránh ambiguity và cost risk.

