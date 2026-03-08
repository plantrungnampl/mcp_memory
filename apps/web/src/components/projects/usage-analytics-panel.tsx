"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Activity, Calendar, Download, Loader2, ShieldCheck, Timer, Zap } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import type {
  UsageAnalyticsMetric,
  UsageAnalyticsPayload,
  UsageAnalyticsToolDistributionItem,
  UsageRange,
} from "@/lib/api/types";
import { normalizeUsageRange, USAGE_RANGE_OPTIONS } from "@/lib/api/usage-range";
import { fetchQueryJson, normalizeQueryError } from "@/lib/query/fetch";
import { projectQueryKeys } from "@/lib/query/keys";

type UsageAnalyticsPanelProps = {
  projectId: string;
  initialRange: UsageRange;
  initialAnalytics: UsageAnalyticsPayload;
};

const RANGE_TABS: Array<{ key: UsageRange; label: string }> = USAGE_RANGE_OPTIONS.map((key) => ({
  key,
  label: key === "all" ? "All time" : key,
}));

const TOOL_COLORS = ["#A855F7", "#00F5FF", "#EAB308"];
const USAGE_ANALYTICS_STALE_TIME_MS = 60_000;

function formatMetric(metric: UsageAnalyticsMetric, options?: { suffix?: string; precision?: number }): string {
  if (metric.value === null) {
    return "—";
  }
  const suffix = options?.suffix ?? "";
  const precision = options?.precision ?? 0;
  if (precision > 0) {
    return `${metric.value.toFixed(precision)}${suffix}`;
  }
  return `${Math.round(metric.value).toLocaleString()}${suffix}`;
}

function metricDelta(metric: UsageAnalyticsMetric, options?: { inverse?: boolean }): { text: string; className: string } {
  if (metric.changePct === null) {
    return { text: "No previous window", className: "text-[var(--vr-text-dim)]" };
  }
  if (metric.changePct === 0) {
    return { text: "No change", className: "text-[var(--vr-text-dim)]" };
  }
  const inverse = options?.inverse ?? false;
  const isPositive = metric.changePct > 0;
  const good = inverse ? !isPositive : isPositive;
  const arrow = isPositive ? "↑" : "↓";
  return {
    text: `${arrow} ${Math.abs(metric.changePct).toFixed(1)}% vs prev period`,
    className: good ? "text-emerald-400" : "text-rose-400",
  };
}

function toolFillColor(index: number): string {
  return TOOL_COLORS[index] ?? "#A855F7";
}

function toolFillStyle(index: number): string {
  const color = toolFillColor(index);
  if (color === "#A855F7") {
    return "bg-gradient-to-r from-[var(--vr-accent)] to-[var(--vr-accent-2)]";
  }
  if (color === "#00F5FF") {
    return "bg-[#00F5FF66]";
  }
  return "bg-[#EAB30866]";
}

async function fetchUsageAnalytics(projectId: string, range: UsageRange): Promise<UsageAnalyticsPayload> {
  return fetchQueryJson<UsageAnalyticsPayload>(
    `/api/projects/${projectId}/usage/analytics?range=${range}`,
  );
}

function exportHref(projectId: string, range: UsageRange): string {
  return `/projects/${projectId}/usage/export?range=${range}`;
}

function dateRangeLabel(value: string): string {
  return value.trim() || "Date range unavailable";
}

function shareWidth(sharePct: number): number {
  if (Number.isNaN(sharePct)) {
    return 0;
  }
  return Math.max(0, Math.min(100, sharePct));
}

function chartHeight(value: number, max: number): number {
  if (max <= 0) {
    return 8;
  }
  return Math.max(8, Math.round((value / max) * 100));
}

function trendMaxValue(analytics: UsageAnalyticsPayload): number {
  if (analytics.trend.length === 0) {
    return 1;
  }
  return Math.max(
    1,
    ...analytics.trend.map((point) => point.apiCalls),
  );
}

function topTools(tools: UsageAnalyticsToolDistributionItem[]): UsageAnalyticsToolDistributionItem[] {
  return tools.slice(0, 3);
}

export function UsageAnalyticsPanel({
  projectId,
  initialRange,
  initialAnalytics,
}: UsageAnalyticsPanelProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const activeRange = normalizeUsageRange(searchParams.get("range"));
  const analyticsQuery = useQuery({
    queryKey: projectQueryKeys.usageAnalytics(projectId, activeRange),
    queryFn: () => fetchUsageAnalytics(projectId, activeRange),
    initialData: activeRange === initialRange ? initialAnalytics : undefined,
    placeholderData: keepPreviousData,
    staleTime: USAGE_ANALYTICS_STALE_TIME_MS,
  });
  const analytics = analyticsQuery.data ?? initialAnalytics;
  const analyticsError = analyticsQuery.isError
    ? normalizeQueryError(analyticsQuery.error)
    : null;
  const maxTrend = trendMaxValue(analytics);
  const toolRows = topTools(analytics.toolDistribution);
  const trend = analytics.trend;
  const firstLabel = trend[0]?.dayLabel ?? "-";
  const middleLabel = trend[Math.floor(trend.length / 2)]?.dayLabel ?? "-";
  const lastLabel = trend[trend.length - 1]?.dayLabel ?? "-";

  function updateRange(nextRange: UsageRange): void {
    if (nextRange === activeRange) {
      return;
    }

    const nextSearchParams = new URLSearchParams(searchParams.toString());
    nextSearchParams.set("range", nextRange);
    window.history.pushState(null, "", `${pathname}?${nextSearchParams.toString()}`);
  }

  return (
    <div className="mx-auto max-w-[1240px] space-y-5">
      <section className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--vr-border)] pb-4">
        <div className="space-y-0.5">
          <p className="text-xs font-medium text-[var(--vr-text-dim)]">{projectId} / Usage Analytics</p>
          <div className="flex items-center gap-3">
            <h1 className="text-[28px] font-bold leading-none text-[var(--vr-text-strong)]">
              Usage Analytics
            </h1>
            {analyticsQuery.isFetching ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-[var(--vr-divider)] px-2 py-1 text-[11px] text-[var(--vr-text-dim)]">
                <Loader2 className="size-3 animate-spin" />
                Updating
              </span>
            ) : null}
          </div>
        </div>
        <Link
          className="inline-flex items-center gap-2 rounded-md border border-[var(--vr-divider)] px-3 py-2 text-xs font-medium text-[var(--vr-text-main)] transition hover:bg-[var(--vr-bg-elevated)]"
          href={exportHref(projectId, activeRange)}
        >
          <Download className="size-3.5 text-[var(--vr-text-dim)]" />
          Export CSV
        </Link>
      </section>

      {analyticsError ? (
        <div className="rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          Usage analytics data may be stale. {analyticsError.message}
        </div>
      ) : null}

      <section className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center rounded-[10px] border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-1">
          {RANGE_TABS.map((tab) => {
            const active = tab.key === activeRange;
            return (
              <button
                className={
                  active
                    ? "rounded-[7px] bg-[var(--vr-accent)] px-3 py-1.5 text-xs font-semibold text-white"
                    : "rounded-[7px] px-3 py-1.5 text-xs font-medium text-[var(--vr-text-dim)] transition hover:bg-[var(--vr-bg-elevated)]"
                }
                key={tab.key}
                onClick={() => updateRange(tab.key)}
                type="button"
              >
                {tab.label}
              </button>
            );
          })}
        </div>
        <div className="inline-flex items-center gap-2 rounded-md border border-[var(--vr-divider)] px-3 py-1.5 text-xs text-[var(--vr-text-muted)]">
          <Calendar className="size-3.5" />
          {dateRangeLabel(analytics.dateRangeLabel)}
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
          <div className="mb-2 flex items-center gap-2 text-xs text-[var(--vr-text-muted)]">
            <Activity className="size-3.5 text-[var(--vr-accent-2)]" />
            API Calls ({activeRange})
          </div>
          <p className="font-mono text-[30px] font-semibold leading-none text-[var(--vr-text-strong)]">
            {formatMetric(analytics.summary.apiCalls)}
          </p>
          {(() => {
            const delta = metricDelta(analytics.summary.apiCalls);
            return <p className={`mt-2 text-[11px] ${delta.className}`}>{delta.text}</p>;
          })()}
        </article>

        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
          <div className="mb-2 flex items-center gap-2 text-xs text-[var(--vr-text-muted)]">
            <Zap className="size-3.5 text-[var(--vr-accent-2)]" />
            Tokens Consumed ({activeRange})
          </div>
          <p className="font-mono text-[30px] font-semibold leading-none text-[var(--vr-text-strong)]">
            {formatMetric(analytics.summary.tokensConsumed)}
          </p>
          {(() => {
            const delta = metricDelta(analytics.summary.tokensConsumed);
            return <p className={`mt-2 text-[11px] ${delta.className}`}>{delta.text}</p>;
          })()}
        </article>

        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
          <div className="mb-2 flex items-center gap-2 text-xs text-[var(--vr-text-muted)]">
            <Timer className="size-3.5 text-[#00F5FF]" />
            Avg Response Time
          </div>
          <p className="font-mono text-[30px] font-semibold leading-none text-[var(--vr-text-strong)]">
            {formatMetric(analytics.summary.avgResponseTimeMs, { suffix: "ms" })}
          </p>
          {(() => {
            const delta = metricDelta(analytics.summary.avgResponseTimeMs, { inverse: true });
            return <p className={`mt-2 text-[11px] ${delta.className}`}>{delta.text}</p>;
          })()}
        </article>

        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
          <div className="mb-2 flex items-center gap-2 text-xs text-[var(--vr-text-muted)]">
            <ShieldCheck className="size-3.5 text-emerald-400" />
            Error Rate
          </div>
          <p className="font-mono text-[30px] font-semibold leading-none text-[var(--vr-text-strong)]">
            {formatMetric(analytics.summary.errorRatePct, { suffix: "%", precision: 1 })}
          </p>
          {(() => {
            const delta = metricDelta(analytics.summary.errorRatePct, { inverse: true });
            return <p className={`mt-2 text-[11px] ${delta.className}`}>{delta.text}</p>;
          })()}
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-[15px] font-semibold text-[var(--vr-text-strong)]">API Calls Over Time</h2>
            <div className="flex items-center gap-3 text-[11px]">
              <span className="text-[var(--vr-accent-2)]">● calls</span>
              <span className="text-[#00F5FF]">● tokens</span>
            </div>
          </div>
          {trend.length > 0 ? (
            <>
              <div className="flex h-[180px] items-end gap-1">
                {trend.map((point, index) => (
                  <div
                    className={
                      index === trend.length - 1
                        ? "w-full rounded-t-[3px] bg-gradient-to-b from-[var(--vr-accent-2)] to-[var(--vr-accent)] shadow-[0_0_18px_rgba(122,45,190,0.45)]"
                        : "w-full rounded-t-[3px] bg-[var(--vr-accent)]/35"
                    }
                    key={`${point.bucketStart}-${index}`}
                    style={{ height: `${chartHeight(point.apiCalls, maxTrend)}%` }}
                    title={`${point.dayLabel}: ${point.apiCalls.toLocaleString()} calls`}
                  />
                ))}
              </div>
              <div className="mt-3 flex items-center justify-between text-[10px] text-[var(--vr-text-faint)]">
                <span>{firstLabel}</span>
                <span>{middleLabel}</span>
                <span>{lastLabel}</span>
              </div>
            </>
          ) : (
            <div className="flex h-[180px] items-center justify-center rounded-lg border border-dashed border-[var(--vr-divider)] text-sm text-[var(--vr-text-dim)]">
              No usage events for this range.
            </div>
          )}
        </article>

        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6">
          <h2 className="text-[15px] font-semibold text-[var(--vr-text-strong)]">Tool Distribution</h2>
          <p className="mt-1 text-xs text-[var(--vr-text-dim)]">
            {(analytics.summary.apiCalls.value ?? 0).toLocaleString()} total calls this period
          </p>

          <div className="mt-4 space-y-4">
            {toolRows.length > 0 ? (
              toolRows.map((tool, index) => (
                <div className="space-y-1.5" key={`${tool.tool}-${index}`}>
                  <div className="flex items-center justify-between gap-3 text-xs">
                    <span className="truncate font-mono text-[var(--vr-text-main)]">{tool.tool}</span>
                    <span className="font-mono font-semibold" style={{ color: toolFillColor(index) }}>
                      {tool.sharePct.toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-[var(--vr-divider)]">
                    <div className={`h-full rounded-full ${toolFillStyle(index)}`} style={{ width: `${shareWidth(tool.sharePct)}%` }} />
                  </div>
                </div>
              ))
            ) : (
              <p className="text-xs text-[var(--vr-text-dim)]">No tool distribution data.</p>
            )}
          </div>

          <div className="my-4 h-px bg-[var(--vr-border)]" />
          <div className="space-y-2 text-xs">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--vr-text-faint)]">Highlights</p>
            <div className="flex items-center justify-between gap-3">
              <span className="text-[var(--vr-text-dim)]">Peak Hour</span>
              <span className="font-mono text-[var(--vr-text-main)]">{analytics.highlights.peakHour || "—"}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-[var(--vr-text-dim)]">Most Active Token</span>
              <span className="max-w-[180px] truncate font-mono text-[var(--vr-text-main)]">
                {analytics.highlights.mostActiveToken || "—"}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-[var(--vr-text-dim)]">Busiest Day</span>
              <span className="font-medium text-[var(--vr-accent-2)]">{analytics.highlights.busiestDay || "—"}</span>
            </div>
          </div>
        </article>
      </section>

      <section className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-[15px] font-semibold text-[var(--vr-text-strong)]">Token Usage Breakdown</h2>
          <Link className="text-xs font-medium text-[var(--vr-accent-2)] transition hover:text-[var(--vr-accent-2)]" href={`/projects/${projectId}/tokens`}>
            View all →
          </Link>
        </div>

        <div className="overflow-x-auto rounded-lg border border-[var(--vr-border)]">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-[var(--vr-bg-input)] text-[11px] uppercase tracking-[0.04em] text-[var(--vr-text-dim)]">
              <tr>
                <th className="px-4 py-2.5">Token</th>
                <th className="px-4 py-2.5">API Calls</th>
                <th className="px-4 py-2.5">Tokens Used</th>
                <th className="px-4 py-2.5">Avg Latency</th>
                <th className="px-4 py-2.5">Share</th>
              </tr>
            </thead>
            <tbody>
              {analytics.tokenBreakdown.length > 0 ? (
                analytics.tokenBreakdown.map((row) => (
                  <tr className="border-t border-[var(--vr-border)]" key={row.tokenId}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs text-[var(--vr-text-main)]">{row.prefix}</span>
                        {row.status === "revoked" ? (
                          <span className="rounded-full bg-rose-500/15 px-2 py-0.5 text-[10px] font-medium text-rose-400">
                            revoked
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-[var(--vr-text-main)]">{row.apiCalls.toLocaleString()}</td>
                    <td className="px-4 py-3 font-mono text-xs text-[var(--vr-text-main)]">{row.vibeTokens.toLocaleString()}</td>
                    <td className="px-4 py-3 font-mono text-xs text-[var(--vr-text-muted)]">
                      {row.avgLatencyMs === null ? "—" : `${Math.round(row.avgLatencyMs)}ms`}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs font-semibold text-[var(--vr-accent-2)]">
                      {row.sharePct.toFixed(1)}%
                    </td>
                  </tr>
                ))
              ) : (
                <tr className="border-t border-[var(--vr-border)]">
                  <td className="px-4 py-7 text-center text-xs text-[var(--vr-text-dim)]" colSpan={5}>
                    No token usage data for this range.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
