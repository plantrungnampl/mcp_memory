"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Loader2,
  Search,
  Timer,
  Waves,
} from "lucide-react";
import { useMemo, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import type {
  ApiLogsMetric,
  ProjectApiLogsAnalyticsPayload,
} from "@/lib/api/types";
import {
  API_LOGS_RANGE_OPTIONS,
  type ApiLogsSearchState,
  buildApiLogsSearchParams,
  normalizeApiLogsSearchState,
} from "@/lib/api/api-logs-search";
import { fetchQueryJson, normalizeQueryError } from "@/lib/query/fetch";
import { projectQueryKeys } from "@/lib/query/keys";

type ProjectApiLogsPanelProps = {
  projectId: string;
  initialAnalytics: ProjectApiLogsAnalyticsPayload;
  initialSearchState: ApiLogsSearchState;
};

const STATUS_OPTIONS = [
  { key: "all", label: "All" },
  { key: "success", label: "Success" },
  { key: "error", label: "Error" },
] as const;

function formatUtc(value: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatMetricValue(metric: ApiLogsMetric, suffix = "", precision = 0): string {
  if (metric.value === null) {
    return "—";
  }
  if (precision > 0) {
    return `${metric.value.toFixed(precision)}${suffix}`;
  }
  return `${Math.round(metric.value).toLocaleString()}${suffix}`;
}

function formatDelta(
  metric: ApiLogsMetric,
  options?: { inverse?: boolean },
): { text: string; className: string } {
  const inverse = options?.inverse ?? false;
  if (metric.changePct === null) {
    return { text: "No previous window", className: "text-[var(--vr-text-dim)]" };
  }
  if (metric.changePct === 0) {
    return { text: "No change", className: "text-[var(--vr-text-dim)]" };
  }
  const isPositive = metric.changePct > 0;
  const good = inverse ? !isPositive : isPositive;
  const arrow = isPositive ? "↑" : "↓";
  return {
    text: `${arrow} ${Math.abs(metric.changePct).toFixed(1)}% vs prev window`,
    className: good ? "text-emerald-400" : "text-rose-400",
  };
}

function formatRangeLabel(range: ProjectApiLogsAnalyticsPayload["range"]): string {
  if (range === "all") {
    return "All Time";
  }
  return range.toUpperCase();
}

function statusBadgeClass(value: string | null): string {
  if (value === "ok") {
    return "bg-emerald-500/15 text-emerald-400";
  }
  return "bg-rose-500/15 text-rose-400";
}

export function ProjectApiLogsPanel({
  projectId,
  initialAnalytics,
  initialSearchState,
}: ProjectApiLogsPanelProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const filters = useMemo(
    () =>
      normalizeApiLogsSearchState({
        range: searchParams.get("range"),
        statusFilter: searchParams.get("status_filter"),
        tool: searchParams.get("tool"),
        query: searchParams.get("q"),
        cursor: searchParams.get("cursor"),
        limit: searchParams.get("limit"),
      }),
    [searchParams],
  );
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const toolInputRef = useRef<HTMLSelectElement | null>(null);

  const initialFiltersMatch =
    filters.range === initialSearchState.range &&
    filters.statusFilter === initialSearchState.statusFilter &&
    filters.tool === initialSearchState.tool &&
    filters.query === initialSearchState.query &&
    filters.cursor === initialSearchState.cursor &&
    filters.limit === initialSearchState.limit;

  const analyticsQuery = useQuery({
    queryKey: projectQueryKeys.apiLogsAnalytics(projectId, filters),
    queryFn: () =>
      fetchQueryJson<ProjectApiLogsAnalyticsPayload>(
        `/api/projects/${projectId}/api-logs/analytics?${buildApiLogsSearchParams(filters).toString()}`,
      ),
    initialData: initialFiltersMatch ? initialAnalytics : undefined,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  const analytics = analyticsQuery.data ?? initialAnalytics;
  const pagination = analytics.table.pagination;
  const analyticsError = analyticsQuery.isError
    ? normalizeQueryError(analyticsQuery.error)
    : null;

  function updateUrl(
    patch: Partial<{
      range: ProjectApiLogsAnalyticsPayload["range"];
      statusFilter: ProjectApiLogsAnalyticsPayload["filters"]["statusFilter"];
      tool: string | null;
      query: string | null;
      cursor: string | null;
      limit: number;
    }>,
    options?: { replace?: boolean },
  ): void {
    const nextState = normalizeApiLogsSearchState({
      range: patch.range ?? filters.range,
      statusFilter: patch.statusFilter ?? filters.statusFilter,
      tool: patch.tool ?? filters.tool,
      query: patch.query ?? filters.query,
      cursor:
        patch.cursor !== undefined
          ? patch.cursor
          : filters.cursor,
      limit: patch.limit ?? filters.limit,
    });
    const nextUrl = `${pathname}?${buildApiLogsSearchParams(nextState).toString()}`;
    if (options?.replace) {
      window.history.replaceState(null, "", nextUrl);
      return;
    }
    window.history.pushState(null, "", nextUrl);
  }

  function handleSearchSubmit(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    updateUrl({ query: searchInputRef.current?.value.trim() || null, cursor: null });
  }

  function handleToolApply(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    updateUrl({ tool: toolInputRef.current?.value || null, cursor: null });
  }

  const exportHref = `${pathname}/export?${buildApiLogsSearchParams({
    ...filters,
    cursor: null,
  }).toString()}`;

  return (
    <div className="mx-auto max-w-[1240px] space-y-5">
      <section className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--vr-border)] pb-4">
        <div className="space-y-0.5">
          <p className="text-xs font-medium text-[var(--vr-text-dim)]">{projectId} / API Logs</p>
          <div className="flex items-center gap-3">
            <h1 className="text-[28px] font-bold leading-none text-[var(--vr-text-strong)]">
              API Logs
            </h1>
            {analyticsQuery.isFetching ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-[var(--vr-divider)] px-2 py-1 text-[11px] text-[var(--vr-text-dim)]">
                <Loader2 className="size-3 animate-spin" />
                Updating
              </span>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <form className="flex items-center gap-2" onSubmit={handleSearchSubmit}>
            <div className="flex items-center gap-2 rounded-md border border-[var(--vr-divider)] bg-[var(--vr-bg-card)] px-3 py-2">
              <Search className="size-3.5 text-[var(--vr-text-dim)]" />
              <input
                className="w-[220px] bg-transparent text-xs text-[var(--vr-text-main)] outline-none placeholder:text-[var(--vr-text-faint)]"
                defaultValue={filters.query ?? ""}
                key={`api-logs-search-${filters.query ?? ""}`}
                placeholder="Search request ID, tool..."
                ref={searchInputRef}
              />
            </div>
          </form>
          <a
            className="inline-flex items-center gap-2 rounded-md border border-[var(--vr-divider)] px-3 py-2 text-xs font-medium text-[var(--vr-text-main)] transition hover:bg-[var(--vr-bg-elevated)]"
            href={exportHref}
          >
            <Download className="size-3.5" />
            Export
          </a>
        </div>
      </section>

      {analyticsError ? (
        <div className="rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          API logs data may be stale. {analyticsError.message}
        </div>
      ) : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
          <div className="mb-2 flex items-center gap-2 text-xs text-[var(--vr-text-muted)]">
            <Waves className="size-3.5 text-[var(--vr-accent-2)]" />
            Total MCP Requests ({formatRangeLabel(filters.range)})
          </div>
          <p className="font-mono text-[30px] font-semibold text-[var(--vr-text-strong)]">
            {formatMetricValue(analytics.summary.totalRequests)}
          </p>
          {(() => {
            const delta = formatDelta(analytics.summary.totalRequests);
            return <p className={`text-[11px] ${delta.className}`}>{delta.text}</p>;
          })()}
        </article>

        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
          <div className="mb-2 flex items-center gap-2 text-xs text-[var(--vr-text-muted)]">
            <CheckCircle2 className="size-3.5 text-emerald-400" />
            Success Rate
          </div>
          <p className="font-mono text-[30px] font-semibold text-[var(--vr-text-strong)]">
            {formatMetricValue(analytics.summary.successRatePct, "%", 1)}
          </p>
          {(() => {
            const delta = formatDelta(analytics.summary.successRatePct);
            return <p className={`text-[11px] ${delta.className}`}>{delta.text}</p>;
          })()}
        </article>

        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
          <div className="mb-2 flex items-center gap-2 text-xs text-[var(--vr-text-muted)]">
            <AlertTriangle className="size-3.5 text-rose-400" />
            MCP Errors ({formatRangeLabel(filters.range)})
          </div>
          <p className="font-mono text-[30px] font-semibold text-[var(--vr-text-strong)]">
            {formatMetricValue(analytics.summary.errorCount)}
          </p>
          {(() => {
            const delta = formatDelta(analytics.summary.errorCount, { inverse: true });
            return <p className={`text-[11px] ${delta.className}`}>{delta.text}</p>;
          })()}
        </article>

        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
          <div className="mb-2 flex items-center gap-2 text-xs text-[var(--vr-text-muted)]">
            <Timer className="size-3.5 text-[var(--vr-accent-2)]" />
            p95 Latency
          </div>
          <p className="font-mono text-[30px] font-semibold text-[var(--vr-text-strong)]">
            {formatMetricValue(analytics.summary.p95LatencyMs, "ms")}
          </p>
          {(() => {
            const delta = formatDelta(analytics.summary.p95LatencyMs, { inverse: true });
            return <p className={`text-[11px] ${delta.className}`}>{delta.text}</p>;
          })()}
        </article>
      </section>

      <section className="space-y-4 rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-xs font-medium text-[var(--vr-text-dim)]">Range:</p>
          {API_LOGS_RANGE_OPTIONS.map((rangeOption) => {
            const active = rangeOption === filters.range;
            return (
              <button
                className={
                  active
                    ? "rounded-md bg-[var(--vr-accent)] px-3 py-1.5 text-xs font-semibold text-white"
                    : "rounded-md border border-[var(--vr-divider)] px-3 py-1.5 text-xs font-medium text-[var(--vr-text-muted)] transition hover:bg-[var(--vr-bg-elevated)]"
                }
                key={rangeOption}
                onClick={() => updateUrl({ range: rangeOption, cursor: null })}
                type="button"
              >
                {formatRangeLabel(rangeOption)}
              </button>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <p className="text-xs font-medium text-[var(--vr-text-dim)]">Status:</p>
          {STATUS_OPTIONS.map((option) => {
            const active = option.key === filters.statusFilter;
            return (
              <button
                className={
                  active
                    ? "rounded-md bg-[var(--vr-accent)] px-3 py-1.5 text-xs font-semibold text-white"
                    : "rounded-md border border-[var(--vr-divider)] px-3 py-1.5 text-xs font-medium text-[var(--vr-text-muted)] transition hover:bg-[var(--vr-bg-elevated)]"
                }
                key={option.key}
                onClick={() => updateUrl({ statusFilter: option.key, cursor: null })}
                type="button"
              >
                {option.label}
              </button>
            );
          })}

          <form className="ml-1 flex items-center gap-2" onSubmit={handleToolApply}>
            <select
              className="rounded-md border border-[var(--vr-divider)] bg-[var(--vr-bg-card)] px-3 py-1.5 text-xs text-[var(--vr-text-main)] outline-none"
              defaultValue={filters.tool ?? ""}
              key={`api-logs-tool-${filters.tool ?? ""}`}
              ref={toolInputRef}
            >
              <option value="">All tools</option>
              {analytics.table.toolOptions.map((toolOption) => (
                <option key={toolOption} value={toolOption}>
                  {toolOption}
                </option>
              ))}
            </select>
            <button
              className="rounded-md border border-[var(--vr-divider)] px-3 py-1.5 text-xs font-medium text-[var(--vr-text-main)] transition hover:bg-[var(--vr-bg-elevated)]"
              type="submit"
            >
              Apply
            </button>
          </form>
        </div>

        <div className="overflow-x-auto rounded-xl border border-[var(--vr-border)]">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-[var(--vr-bg-input)] text-[11px] uppercase tracking-[0.08em] text-[var(--vr-text-dim)]">
              <tr>
                <th className="px-4 py-2.5">Time</th>
                <th className="px-4 py-2.5">Tool</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Latency</th>
                <th className="px-4 py-2.5">Token</th>
                <th className="px-4 py-2.5">Request ID</th>
              </tr>
            </thead>
            <tbody>
              {analytics.table.rows.length > 0 ? (
                analytics.table.rows.map((row) => (
                  <tr className="border-t border-[var(--vr-border)]" key={row.id}>
                    <td className="px-4 py-3 font-mono text-xs text-[var(--vr-text-main)]">
                      {formatUtc(row.time)}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-[var(--vr-text-main)]">
                      {row.tool ?? "-"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${statusBadgeClass(row.status)}`}
                      >
                        {row.status ?? "-"}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-[var(--vr-text-main)]">
                      {row.latencyMs === null ? "-" : `${Math.round(row.latencyMs)}ms`}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-[var(--vr-text-muted)]">
                      {row.tokenPrefix ?? "-"}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-[var(--vr-text-faint)]">
                      {row.requestId ?? "-"}
                    </td>
                  </tr>
                ))
              ) : (
                <tr className="border-t border-[var(--vr-border)]">
                  <td
                    className="px-4 py-8 text-center text-xs text-[var(--vr-text-dim)]"
                    colSpan={6}
                  >
                    No logs found for the current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
          <p className="text-[var(--vr-text-dim)]">
            Showing {pagination.showingTo === 0 ? "0" : `${pagination.showingFrom}-${pagination.showingTo}`}{" "}
            of {pagination.totalRows.toLocaleString()} MCP requests
          </p>
          <div className="flex items-center gap-2">
            {pagination.prevCursor ? (
              <button
                className="rounded-md border border-[var(--vr-divider)] px-3 py-1.5 text-[11px] font-medium text-[var(--vr-text-main)] transition hover:bg-[var(--vr-bg-elevated)]"
                onClick={() => updateUrl({ cursor: pagination.prevCursor })}
                type="button"
              >
                Prev
              </button>
            ) : (
              <span className="rounded-md border border-[var(--vr-divider)] px-3 py-1.5 text-[11px] text-[var(--vr-text-faint)]">
                Prev
              </span>
            )}
            {pagination.nextCursor ? (
              <button
                className="rounded-md bg-gradient-to-r from-[var(--vr-accent)] to-[var(--vr-accent-2)] px-3 py-1.5 text-[11px] font-semibold text-white"
                onClick={() => updateUrl({ cursor: pagination.nextCursor })}
                type="button"
              >
                Next
              </button>
            ) : (
              <span className="rounded-md border border-[var(--vr-divider)] px-3 py-1.5 text-[11px] text-[var(--vr-text-faint)]">
                Next
              </span>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
