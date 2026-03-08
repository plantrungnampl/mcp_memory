import Link from "next/link";
import {
  Activity,
  HeartPulse,
  KeyRound,
  Plus,
  RefreshCw,
  Zap,
} from "lucide-react";

import type {
  McpConnectionInfo,
  ProjectApiLogRow,
  ProjectOverviewRow,
  ProjectSummary,
  ProjectToken,
  UsageSeries,
  UsageSummary,
} from "@/lib/api/types";
import { QuickIntegrationCredentials } from "@/components/projects/quick-integration-credentials";

type ProjectsDashboardPenProps = {
  activeProject: ProjectSummary | null;
  connection: McpConnectionInfo | null;
  logs: ProjectApiLogRow[];
  overviewRow: ProjectOverviewRow | null;
  tokens: ProjectToken[];
  usageDaily: UsageSummary | null;
  usageMonthly: UsageSummary | null;
  usageSeries: UsageSeries | null;
};

type ChartBar = {
  dayLabel: string;
  height: number;
  vibeTokens: number;
};

const FALLBACK_SERIES = [45, 62, 38, 85, 55, 72, 48, 92, 110, 78, 95, 120, 68, 140];

function formatRelativeTime(value: string | null): string {
  if (!value) {
    return "No activity yet";
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return value;
  }
  const diffSeconds = Math.floor((Date.now() - timestamp) / 1000);
  if (diffSeconds < 60) {
    return "Just now";
  }
  if (diffSeconds < 3600) {
    return `${Math.floor(diffSeconds / 60)} min ago`;
  }
  if (diffSeconds < 86400) {
    return `${Math.floor(diffSeconds / 3600)}h ago`;
  }
  return `${Math.floor(diffSeconds / 86400)}d ago`;
}

function formatLogTime(value: string | null): string {
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

function statusClassName(status: string): string {
  const lower = status.toLowerCase();
  if (lower.includes("success") || lower.includes("ok")) {
    return "bg-emerald-500/15 text-emerald-400";
  }
  if (lower.includes("error") || lower.includes("fail")) {
    return "bg-rose-500/15 text-rose-400";
  }
  return "bg-amber-500/15 text-amber-300";
}

function tokenBadgeClassName(status: ProjectToken["status"]): string {
  if (status === "active") {
    return "bg-emerald-500/15 text-emerald-400";
  }
  if (status === "grace") {
    return "bg-amber-500/15 text-amber-300";
  }
  return "bg-rose-500/15 text-rose-400";
}

function toBars(series: UsageSeries | null): ChartBar[] {
  if (!series || series.series.length === 0) {
    const max = Math.max(...FALLBACK_SERIES);
    return FALLBACK_SERIES.map((value, index) => ({
      dayLabel: index === 0 ? "Feb 1" : index === 7 ? "Feb 15" : index === FALLBACK_SERIES.length - 1 ? "Mar 1" : "",
      height: Math.max(8, Math.round((value / max) * 100)),
      vibeTokens: value,
    }));
  }

  const source = series.series.slice(-14);
  const max = Math.max(1, ...source.map((entry) => entry.vibeTokens));
  return source.map((entry, index) => {
    const date = new Date(entry.bucketStart);
    const shortLabel = Number.isNaN(date.getTime())
      ? entry.bucketStart
      : date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    return {
      dayLabel:
        index === 0 || index === Math.floor(source.length / 2) || index === source.length - 1
          ? shortLabel
          : "",
      height: Math.max(8, Math.round((entry.vibeTokens / max) * 100)),
      vibeTokens: entry.vibeTokens,
    };
  });
}

export function ProjectsDashboardPen({
  activeProject,
  connection,
  logs,
  overviewRow,
  tokens,
  usageDaily,
  usageMonthly,
  usageSeries,
}: ProjectsDashboardPenProps) {
  const chartBars = toBars(usageSeries);
  const activeToken = tokens.find((token) => token.status !== "revoked") ?? tokens[0] ?? null;
  const activeTokensCount = tokens.filter((token) => token.status !== "revoked").length;
  const endpoint = connection?.endpoint ?? null;
  const tokenFallback = connection?.tokenPreview ?? activeToken?.prefix ?? null;
  const healthStatus = overviewRow?.healthStatus ?? "idle";
  const healthLabel = healthStatus === "active" ? "Active" : healthStatus === "error" ? "Error" : "Idle";
  const healthSubtitle =
    healthStatus === "active"
      ? "All systems operational"
      : healthStatus === "error"
        ? "Action required"
        : "Awaiting activity";

  const stats = [
    {
      key: "m1",
      icon: Zap,
      iconClassName: "text-[var(--vr-accent-2)]",
      label: "VibeTokens (30d)",
      value: usageMonthly ? usageMonthly.vibeTokens.toLocaleString() : "0",
      note: usageMonthly ? `${usageMonthly.inTokens.toLocaleString()} in · ${usageMonthly.outTokens.toLocaleString()} out` : "No usage data",
    },
    {
      key: "m2",
      icon: Activity,
      iconClassName: "text-[var(--vr-accent-2)]",
      label: "Events (30d)",
      value: usageMonthly ? usageMonthly.eventCount.toLocaleString() : "0",
      note: usageDaily ? `${usageDaily.eventCount.toLocaleString()} events in last 24h` : "No daily events",
    },
    {
      key: "m3",
      icon: KeyRound,
      iconClassName: "text-[var(--vr-warning)]",
      label: "Active Tokens",
      value: activeTokensCount.toLocaleString(),
      note: activeToken ? `Last used ${formatRelativeTime(activeToken.lastUsedAt)}` : "Mint your first token",
    },
    {
      key: "m4",
      icon: HeartPulse,
      iconClassName: "text-[var(--vr-success)]",
      label: "Health",
      value: healthLabel,
      valueClassName: healthStatus === "active" ? "text-[var(--vr-success)]" : "text-[var(--vr-text-strong)]",
      note: healthSubtitle,
    },
  ];

  return (
    <div className="mx-auto max-w-[1240px] space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stats.map((item, index) => {
          const Icon = item.icon;
          return (
            <article
              className="vr-fade-up vr-hover-lift space-y-2 rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5"
              key={item.key}
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <div className="flex items-center gap-2 text-xs text-[var(--vr-text-muted)]">
                <Icon className={`size-3.5 ${item.iconClassName}`} />
                <span>{item.label}</span>
              </div>
              <p
                className={`font-mono text-[28px] font-semibold leading-none ${item.valueClassName ?? "text-[var(--vr-text-strong)]"}`}
              >
                {item.value}
              </p>
              <p className="text-[11px] text-[var(--vr-text-dim)]">{item.note}</p>
            </article>
          );
        })}
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <article className="vr-fade-up rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6" style={{ animationDelay: "110ms" }}>
          <h2 className="text-[15px] font-semibold text-[var(--vr-text-strong)]">Quick Integration</h2>
          <div className="mt-4 space-y-3">
            <QuickIntegrationCredentials endpoint={endpoint} tokenFallback={tokenFallback} />
            <div className="flex flex-wrap gap-2">
              {activeProject ? (
                <>
                  <Link
                    className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-[var(--vr-accent)] to-[var(--vr-accent-2)] px-4 py-2 text-xs font-semibold text-white transition hover:brightness-110"
                    href={`/projects/${activeProject.id}/tokens`}
                  >
                    <Plus className="size-3.5" />
                    Mint Token
                  </Link>
                  <Link
                    className="inline-flex items-center gap-1.5 rounded-md border border-[var(--vr-divider)] px-4 py-2 text-xs font-medium text-[var(--vr-text-muted)] transition hover:bg-[var(--vr-bg-elevated)]"
                    href={`/projects/${activeProject.id}/tokens`}
                  >
                    <RefreshCw className="size-3.5" />
                    Rotate
                  </Link>
                </>
              ) : (
                <p className="text-xs text-[var(--vr-text-dim)]">Select a project to manage tokens.</p>
              )}
            </div>
          </div>
        </article>

        <article className="vr-fade-up rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6" style={{ animationDelay: "150ms" }}>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-[15px] font-semibold text-[var(--vr-text-strong)]">Usage Trend (30d)</h2>
            <div className="rounded-md bg-[var(--vr-bg-elevated)] px-2.5 py-1 text-[11px] text-[var(--vr-text-muted)]">Daily</div>
          </div>
          <div className="flex h-[140px] items-end gap-[3px]">
            {chartBars.map((bar, index) => (
              <div
                className={
                  index === chartBars.length - 1
                    ? "w-full rounded-t-[3px] bg-gradient-to-b from-[var(--vr-accent-2)] to-[var(--vr-accent)] shadow-[0_0_18px_rgba(122,45,190,0.45)]"
                    : "w-full rounded-t-[3px] bg-[var(--vr-accent)]/35"
                }
                key={`${bar.dayLabel}-${index}`}
                style={{ height: `${bar.height}%` }}
                title={`${bar.vibeTokens.toLocaleString()} VT`}
              />
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between text-[10px] text-[var(--vr-text-faint)]">
            <span>{chartBars[0]?.dayLabel || "-"}</span>
            <span>{chartBars[Math.floor(chartBars.length / 2)]?.dayLabel || "-"}</span>
            <span>{chartBars[chartBars.length - 1]?.dayLabel || "-"}</span>
          </div>
        </article>
      </section>

      <section className="vr-fade-up rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6" style={{ animationDelay: "180ms" }}>
        <h2 className="mb-4 text-[15px] font-semibold text-[var(--vr-text-strong)]">Token Management</h2>
        <div className="overflow-x-auto rounded-lg border border-[var(--vr-border)]">
          <table className="min-w-full text-left">
            <thead className="bg-[var(--vr-bg-input)] text-[11px] uppercase tracking-[0.04em] text-[var(--vr-text-dim)]">
              <tr>
                <th className="px-4 py-2.5">Token Prefix</th>
                <th className="px-4 py-2.5">Last Used</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {activeToken ? (
                <tr className="border-t border-[var(--vr-border)]">
                  <td className="px-4 py-3 font-mono text-xs text-[var(--vr-text-main)]">{activeToken.prefix}</td>
                  <td className="px-4 py-3 text-xs text-[var(--vr-text-muted)]">{formatRelativeTime(activeToken.lastUsedAt)}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2.5 py-1 text-[11px] ${tokenBadgeClassName(activeToken.status)}`}>
                      {activeToken.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {activeProject ? (
                      <Link
                        className="rounded-md border border-[var(--vr-divider)] px-3 py-1.5 text-[11px] text-[var(--vr-text-muted)] transition hover:bg-[var(--vr-bg-elevated)]"
                        href={`/projects/${activeProject.id}/tokens`}
                      >
                        Open tokens
                      </Link>
                    ) : (
                      <span className="text-xs text-[var(--vr-text-dim)]">-</span>
                    )}
                  </td>
                </tr>
              ) : (
                <tr className="border-t border-[var(--vr-border)]">
                  <td className="px-4 py-6 text-center text-xs text-[var(--vr-text-dim)]" colSpan={4}>
                    No tokens available for this project.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="vr-fade-up rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6" style={{ animationDelay: "220ms" }}>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-[15px] font-semibold text-[var(--vr-text-strong)]">Recent API Logs</h2>
          {activeProject ? (
            <Link className="text-xs font-medium text-[var(--vr-accent-2)] transition hover:text-[var(--vr-accent-2)]" href={`/projects/${activeProject.id}/api-logs`}>
              View all →
            </Link>
          ) : null}
        </div>
        <div className="overflow-x-auto rounded-lg border border-[var(--vr-border)]">
          <table className="min-w-full text-left">
            <thead className="bg-[var(--vr-bg-input)] text-[11px] uppercase tracking-[0.04em] text-[var(--vr-text-dim)]">
              <tr>
                <th className="px-4 py-2.5">Time</th>
                <th className="px-4 py-2.5">Action</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Tool</th>
                <th className="px-4 py-2.5">Request ID</th>
              </tr>
            </thead>
            <tbody>
              {logs.length > 0 ? (
                logs.map((log) => (
                  <tr className="border-t border-[var(--vr-border)] text-xs" key={log.id}>
                    <td className="px-4 py-3 font-mono text-[var(--vr-text-muted)]">{formatLogTime(log.createdAt)}</td>
                    <td className="px-4 py-3 text-[var(--vr-text-main)]">{log.action}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-[10px] ${statusClassName(log.status)}`}>
                        {log.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-[var(--vr-text-muted)]">{log.toolName ?? "-"}</td>
                    <td className="px-4 py-3 font-mono text-[var(--vr-text-dim)]">{log.requestId ?? "-"}</td>
                  </tr>
                ))
              ) : (
                <tr className="border-t border-[var(--vr-border)]">
                  <td className="px-4 py-6 text-center text-xs text-[var(--vr-text-dim)]" colSpan={5}>
                    {activeProject ? "No logs for this project yet." : "Select a project to view API logs."}
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
