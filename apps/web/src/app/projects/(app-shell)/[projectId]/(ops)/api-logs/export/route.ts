import { NextResponse } from "next/server";

import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { getProjectApiLogsAnalytics } from "@/lib/api/control-plane";
import type { ApiLogsRange, ApiLogsStatusFilter, ProjectApiLogsAnalyticsRow } from "@/lib/api/types";

const VALID_RANGES: ApiLogsRange[] = ["24h", "7d", "30d", "90d", "all"];
const VALID_STATUS: ApiLogsStatusFilter[] = ["all", "success", "error"];

function normalizeRange(value: string | null): ApiLogsRange {
  if (value && VALID_RANGES.includes(value as ApiLogsRange)) {
    return value as ApiLogsRange;
  }
  return "30d";
}

function normalizeStatus(value: string | null): ApiLogsStatusFilter {
  if (value && VALID_STATUS.includes(value as ApiLogsStatusFilter)) {
    return value as ApiLogsStatusFilter;
  }
  return "all";
}

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

function rowsToCsv(rows: Array<Array<string | number | null>>): string {
  return rows.map((row) => row.map((cell) => csvEscape(cell)).join(",")).join("\n");
}

function latencyText(latencyMs: number | null): string | null {
  if (latencyMs === null) {
    return null;
  }
  return `${Math.round(latencyMs)}ms`;
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
  const range = normalizeRange(url.searchParams.get("range"));
  const statusFilter = normalizeStatus(url.searchParams.get("status_filter"));
  const tool = url.searchParams.get("tool")?.trim() || null;
  const query = url.searchParams.get("q")?.trim() || null;

  const collectedRows: ProjectApiLogsAnalyticsRow[] = [];
  let cursor: string | null = null;
  let summary:
    | Awaited<ReturnType<typeof getProjectApiLogsAnalytics>>["summary"]
    | null = null;
  let safetyCounter = 0;

  while (safetyCounter < 100) {
    safetyCounter += 1;
    const payload = await getProjectApiLogsAnalytics(user, projectId, {
      range,
      statusFilter,
      tool,
      query,
      limit: 200,
      cursor,
    });
    summary = summary ?? payload.summary;
    collectedRows.push(...payload.table.rows);
    cursor = payload.table.pagination.nextCursor;
    if (!cursor) {
      break;
    }
  }

  const rows: Array<Array<string | number | null>> = [];
  rows.push(["Section", "Metric", "Value", "ChangePct"]);
  rows.push(["summary", "total_requests", summary?.totalRequests.value ?? null, summary?.totalRequests.changePct ?? null]);
  rows.push(["summary", "success_rate_pct", summary?.successRatePct.value ?? null, summary?.successRatePct.changePct ?? null]);
  rows.push(["summary", "error_count", summary?.errorCount.value ?? null, summary?.errorCount.changePct ?? null]);
  rows.push(["summary", "p95_latency_ms", summary?.p95LatencyMs.value ?? null, summary?.p95LatencyMs.changePct ?? null]);
  rows.push([]);
  rows.push(["logs"]);
  rows.push(["time", "tool", "status", "latency", "token_prefix", "request_id", "action"]);
  for (const row of collectedRows) {
    rows.push([
      row.time,
      row.tool,
      row.status,
      latencyText(row.latencyMs),
      row.tokenPrefix,
      row.requestId,
      row.action,
    ]);
  }

  const csv = rowsToCsv(rows);
  const filename = `api-logs-${projectId}-${range}-${statusFilter}.csv`;

  return new Response(csv, {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store",
    },
  });
}
