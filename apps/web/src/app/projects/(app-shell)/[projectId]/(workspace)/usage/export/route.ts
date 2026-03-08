import { NextResponse } from "next/server";

import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { getUsageAnalytics } from "@/lib/api/control-plane";
import { normalizeUsageRange } from "@/lib/api/usage-range";

function csvEscape(value: string | number | null): string {
  if (value === null) {
    return "";
  }
  const raw = String(value);
  if (raw.includes(",") || raw.includes("\"") || raw.includes("\n")) {
    return `"${raw.replace(/"/g, "\"\"")}"`;
  }
  return raw;
}

function toCsv(rows: Array<Array<string | number | null>>): string {
  return rows
    .map((row) => row.map((cell) => csvEscape(cell)).join(","))
    .join("\n");
}

export async function GET(
  request: Request,
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;
  const user = await getAuthenticatedProjectUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const url = new URL(request.url);
  const range = normalizeUsageRange(url.searchParams.get("range"));
  const analytics = await getUsageAnalytics(user, projectId, range);

  const rows: Array<Array<string | number | null>> = [];
  rows.push(["Section", "Metric", "Value", "ChangePct"]);
  rows.push(["summary", "api_calls", analytics.summary.apiCalls.value, analytics.summary.apiCalls.changePct]);
  rows.push([
    "summary",
    "tokens_consumed",
    analytics.summary.tokensConsumed.value,
    analytics.summary.tokensConsumed.changePct,
  ]);
  rows.push([
    "summary",
    "avg_response_time_ms",
    analytics.summary.avgResponseTimeMs.value,
    analytics.summary.avgResponseTimeMs.changePct,
  ]);
  rows.push([
    "summary",
    "error_rate_pct",
    analytics.summary.errorRatePct.value,
    analytics.summary.errorRatePct.changePct,
  ]);
  rows.push([]);

  rows.push(["daily_trend"]);
  rows.push(["bucket_start", "day_label", "api_calls", "vibe_tokens"]);
  for (const point of analytics.trend) {
    rows.push([point.bucketStart, point.dayLabel, point.apiCalls, point.vibeTokens]);
  }
  rows.push([]);

  rows.push(["tool_distribution"]);
  rows.push(["tool", "api_calls", "share_pct"]);
  for (const item of analytics.toolDistribution) {
    rows.push([item.tool, item.apiCalls, item.sharePct]);
  }
  rows.push([]);

  rows.push(["token_breakdown"]);
  rows.push(["token_id", "prefix", "status", "api_calls", "vibe_tokens", "avg_latency_ms", "share_pct"]);
  for (const item of analytics.tokenBreakdown) {
    rows.push([
      item.tokenId,
      item.prefix,
      item.status,
      item.apiCalls,
      item.vibeTokens,
      item.avgLatencyMs,
      item.sharePct,
    ]);
  }

  const csv = toCsv(rows);
  const filename = `usage-analytics-${projectId}-${range}.csv`;

  return new Response(csv, {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store",
    },
  });
}
