from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest


tool_call_latency_ms = Histogram(
    "tool_call_latency_ms",
    "Latency of MCP tool calls in milliseconds",
    labelnames=("tool",),
)
mcp_initialize_latency_ms = Histogram(
    "mcp_initialize_latency_ms",
    "Latency of MCP initialize calls in milliseconds",
)
rate_limited_count = Counter(
    "rate_limited_count",
    "Number of rate-limit rejections",
)
quota_exceeded_count = Counter(
    "quota_exceeded_count",
    "Number of quota exceeded rejections",
)
queue_depth = Gauge(
    "queue_depth",
    "Approximate queue depth by queue name",
    labelnames=("queue",),
)
job_duration_ms = Histogram(
    "job_duration_ms",
    "Worker job duration in milliseconds",
    labelnames=("job",),
)
graph_db_latency_ms = Histogram(
    "graph_db_latency_ms",
    "Latency for graph database operations in milliseconds",
    labelnames=("operation",),
)
tokens_burn_rate = Gauge(
    "tokens_burn_rate",
    "Monthly vibe token burn per project",
    labelnames=("project",),
)


def metrics_response() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
