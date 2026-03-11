"use client";

import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useActionState, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Download,
  FileArchive,
  HeartPulse,
  KeyRound,
  Plus,
  RefreshCw,
  RotateCw,
  ShieldX,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import type {
  ExportActionState,
  TokenActionState,
} from "@/app/projects/action-types";
import type {
  ProjectExport,
  ProjectOpsDashboardPayload,
  ProjectToken,
  UsageSeries,
} from "@/lib/api/types";
import { fetchQueryJson, normalizeQueryError } from "@/lib/query/fetch";
import { projectQueryKeys } from "@/lib/query/keys";

import { Button } from "@/components/ui/button";
import { QuickIntegrationCredentials } from "@/components/projects/quick-integration-credentials";
import { TokenIssuedModal } from "@/components/projects/token-issued-modal";

type TokenDashboardPanelProps = {
  projectId: string;
  initialData: ProjectOpsDashboardPayload;
  mintTokenAction: (prevState: TokenActionState, formData: FormData) => Promise<TokenActionState>;
  rotateTokenAction: (prevState: TokenActionState, formData: FormData) => Promise<TokenActionState>;
  revokeTokenAction: (prevState: TokenActionState, formData: FormData) => Promise<TokenActionState>;
  createExportAction: (
    prevState: ExportActionState,
    formData: FormData,
  ) => Promise<ExportActionState>;
};

const INITIAL_STATE: TokenActionState = {
  ok: false,
  message: null,
  nonce: null,
  tokenPlaintext: null,
  tokenPrefix: null,
};

const INITIAL_EXPORT_STATE: ExportActionState = {
  ok: false,
  message: null,
  nonce: null,
  exportId: null,
  status: null,
};

type ChartBar = {
  dayLabel: string;
  height: number;
  vibeTokens: number;
};

const FALLBACK_SERIES = [45, 62, 38, 85, 55, 72, 48, 92, 110, 78, 95, 120, 68, 140];
const OPS_DASHBOARD_STALE_TIME_MS = 15_000;
const OPS_DASHBOARD_POLL_INTERVAL_MS = 5_000;

function formatRelativeTime(value: string | null): string {
  if (!value) {
    return "never";
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return value;
  }
  const diffSeconds = Math.floor((Date.now() - timestamp) / 1000);
  if (diffSeconds < 60) {
    return "just now";
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

function exportStatusLabel(status: ProjectExport["status"]): string {
  if (status === "processing") {
    return "Processing";
  }
  if (status === "complete") {
    return "Complete";
  }
  if (status === "failed") {
    return "Failed";
  }
  return "Pending";
}

function exportStatusStyle(status: ProjectExport["status"]): string {
  if (status === "complete") {
    return "bg-emerald-500/25 text-emerald-100";
  }
  if (status === "failed") {
    return "bg-rose-500/25 text-rose-100";
  }
  if (status === "processing") {
    return "bg-amber-500/25 text-amber-100";
  }
  return "bg-slate-700/80 text-slate-100";
}

type ExportErrorMessage = {
  message: string;
  hint: string | null;
};

function formatExportErrorMessage(error: string): ExportErrorMessage {
  const normalized = error.trim();
  const lower = normalized.toLowerCase();

  if (
    lower.includes("memory backend is unreachable") ||
    lower.includes("falkordb") ||
    lower.includes("connection refused") ||
    lower.includes("failed to establish connection")
  ) {
    return {
      message: "Export could not reach the memory backend.",
      hint: "Start FalkorDB and verify FALKORDB_HOST/FALKORDB_PORT, then create a new export.",
    };
  }

  if (lower.includes("credentials") || lower.includes("authentication")) {
    return {
      message: "Export failed due to memory backend authentication.",
      hint: "Verify FalkorDB credentials in environment settings, then retry.",
    };
  }

  if (lower.includes("timeout")) {
    return {
      message: "Export timed out while collecting memory.",
      hint: "Please retry in a few minutes.",
    };
  }

  return {
    message: normalized || "Export failed unexpectedly.",
    hint: "Retry export. If it keeps failing, check API logs.",
  };
}

function toBars(series: UsageSeries | null): ChartBar[] {
  if (!series || series.series.length === 0) {
    const max = Math.max(...FALLBACK_SERIES);
    return FALLBACK_SERIES.map((value, index) => ({
      dayLabel:
        index === 0
          ? "Feb 1"
          : index === 7
            ? "Feb 15"
            : index === FALLBACK_SERIES.length - 1
              ? "Mar 1"
              : "",
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

export function TokenDashboardPanel({
  projectId,
  initialData,
  mintTokenAction,
  rotateTokenAction,
  revokeTokenAction,
  createExportAction,
}: TokenDashboardPanelProps) {
  const activeProjectId = projectId;
  const queryClient = useQueryClient();
  const [dismissedIssuedTokenNonce, setDismissedIssuedTokenNonce] = useState<string | null>(null);
  const [mintState, mintFormAction, mintPending] = useActionState(mintTokenAction, INITIAL_STATE);
  const [rotateState, rotateFormAction, rotatePending] = useActionState(
    rotateTokenAction,
    INITIAL_STATE,
  );
  const [revokeState, revokeFormAction, revokePending] = useActionState(
    revokeTokenAction,
    INITIAL_STATE,
  );
  const [exportState, exportFormAction, exportPending] = useActionState(
    createExportAction,
    INITIAL_EXPORT_STATE,
  );

  const opsDashboardQuery = useQuery({
    queryKey: projectQueryKeys.opsDashboard(projectId),
    queryFn: () =>
      fetchQueryJson<ProjectOpsDashboardPayload>(`/api/projects/${projectId}/ops-dashboard`),
    initialData,
    staleTime: OPS_DASHBOARD_STALE_TIME_MS,
    refetchInterval(query) {
      const dashboard = query.state.data as ProjectOpsDashboardPayload | undefined;
      return dashboard?.exports.some(
        (entry) => entry.status === "pending" || entry.status === "processing",
      )
        ? OPS_DASHBOARD_POLL_INTERVAL_MS
        : false;
    },
  });

  const dashboardData = opsDashboardQuery.data;
  const tokens = dashboardData.tokens;
  const connection = dashboardData.connection;
  const usageDaily = dashboardData.usageDaily;
  const usageMonthly = dashboardData.usageMonthly;
  const usageSeries = dashboardData.usageSeries;
  const overviewRow = dashboardData.overviewRow;
  const logs = dashboardData.logs;
  const exports = dashboardData.exports;
  const opsDashboardError = opsDashboardQuery.isError
    ? normalizeQueryError(opsDashboardQuery.error)
    : null;

  useEffect(() => {
    if (mintState.ok || rotateState.ok || revokeState.ok || exportState.ok) {
      void queryClient.invalidateQueries({
        queryKey: projectQueryKeys.opsDashboard(projectId),
      });
    }
  }, [
    mintState.nonce,
    mintState.ok,
    exportState.nonce,
    exportState.ok,
    revokeState.ok,
    revokeState.nonce,
    rotateState.nonce,
    rotateState.ok,
    projectId,
    queryClient,
  ]);

  useEffect(() => {
    if (!exportState.nonce || !exportState.message) {
      return;
    }
    if (exportState.ok) {
      toast.success(exportState.message);
      return;
    }
    toast.error(exportState.message);
  }, [exportState.message, exportState.nonce, exportState.ok]);

  const visibleTokens = useMemo(() => tokens.filter((token) => token.status !== "revoked"), [tokens]);
  const activeToken = useMemo(() => visibleTokens[0] ?? null, [visibleTokens]);
  const activeTokensCount = visibleTokens.length;
  const chartBars = useMemo(() => toBars(usageSeries), [usageSeries]);
  const endpoint = connection?.endpoint ?? null;
  const tokenFallback = activeToken?.prefix ?? (visibleTokens.length > 0 ? connection?.tokenPreview ?? null : null);
  const healthStatus = overviewRow?.healthStatus ?? "idle";
  const healthLabel = healthStatus === "active" ? "Active" : healthStatus === "error" ? "Error" : "Idle";
  const healthSubtitle =
    healthStatus === "active"
      ? "All systems operational"
      : healthStatus === "error"
        ? "Action required"
        : "Awaiting activity";
  const latestMessage =
    exportState.message ?? revokeState.message ?? rotateState.message ?? mintState.message;
  const issuedTokenCandidate = useMemo(() => {
    const mintCandidate =
      mintState.ok && mintState.nonce && mintState.tokenPlaintext
        ? {
            mode: "mint" as const,
            tokenPlaintext: mintState.tokenPlaintext,
            nonce: mintState.nonce,
          }
        : null;
    const rotateCandidate =
      rotateState.ok && rotateState.nonce && rotateState.tokenPlaintext
        ? {
            mode: "rotate" as const,
            tokenPlaintext: rotateState.tokenPlaintext,
            nonce: rotateState.nonce,
          }
        : null;

    if (!mintCandidate) {
      return rotateCandidate;
    }
    if (!rotateCandidate) {
      return mintCandidate;
    }

    const mintNonce = Number(mintCandidate.nonce);
    const rotateNonce = Number(rotateCandidate.nonce);
    if (Number.isFinite(mintNonce) && Number.isFinite(rotateNonce)) {
      return mintNonce >= rotateNonce ? mintCandidate : rotateCandidate;
    }
    return mintCandidate.nonce >= rotateCandidate.nonce ? mintCandidate : rotateCandidate;
  }, [
    mintState.nonce,
    mintState.ok,
    mintState.tokenPlaintext,
    rotateState.nonce,
    rotateState.ok,
    rotateState.tokenPlaintext,
  ]);
  const issuedTokenModal =
    issuedTokenCandidate && issuedTokenCandidate.nonce !== dismissedIssuedTokenNonce
      ? issuedTokenCandidate
      : null;

  function handleCloseIssuedTokenModal(): void {
    if (issuedTokenCandidate) {
      setDismissedIssuedTokenNonce(issuedTokenCandidate.nonce);
    }
  }

  const stats = [
    {
      key: "m1",
      icon: Zap,
      iconClassName: "text-[var(--vr-accent-2)]",
      label: "VibeTokens (30d)",
      value: usageMonthly ? usageMonthly.vibeTokens.toLocaleString() : "0",
      note: usageMonthly
        ? `${usageMonthly.inTokens.toLocaleString()} in · ${usageMonthly.outTokens.toLocaleString()} out`
        : "No usage data",
      noteClassName: "text-emerald-400",
      monoValue: true,
    },
    {
      key: "m2",
      icon: Activity,
      iconClassName: "text-[var(--vr-accent-2)]",
      label: "Events (30d)",
      value: usageMonthly ? usageMonthly.eventCount.toLocaleString() : "0",
      note: usageDaily
        ? `${usageDaily.eventCount.toLocaleString()} events in last 24h`
        : "No daily events",
      noteClassName: "text-[var(--vr-text-dim)]",
      monoValue: true,
    },
    {
      key: "m3",
      icon: KeyRound,
      iconClassName: "text-[var(--vr-warning)]",
      label: "Active Tokens",
      value: activeTokensCount.toLocaleString(),
      note: activeToken ? `Last used ${formatRelativeTime(activeToken.lastUsedAt)}` : "Mint your first token",
      noteClassName: "text-[var(--vr-text-dim)]",
      monoValue: true,
    },
    {
      key: "m4",
      icon: HeartPulse,
      iconClassName: "text-[var(--vr-success)]",
      label: "Health",
      value: healthLabel,
      valueClassName: healthStatus === "active" ? "text-[var(--vr-success)]" : "text-[var(--vr-text-strong)]",
      note: healthSubtitle,
      noteClassName: "text-[var(--vr-text-dim)]",
      monoValue: false,
    },
  ];

  return (
    <div className="mx-auto max-w-[1240px] space-y-6">
      {opsDashboardError ? (
        <div className="rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          Dashboard data may be stale. {opsDashboardError.message}
        </div>
      ) : null}

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
                className={`${item.monoValue ? "font-mono font-semibold" : "font-sans font-bold"} text-[28px] leading-none ${item.valueClassName ?? "text-[var(--vr-text-strong)]"}`}
              >
                {item.value}
              </p>
              <p className={`text-[11px] ${item.noteClassName}`}>{item.note}</p>
            </article>
          );
        })}
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <article
          className="vr-fade-up rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6"
          style={{ animationDelay: "110ms" }}
        >
          <h2 className="text-[15px] font-semibold text-[var(--vr-text-strong)]">Quick Integration</h2>
          <div className="mt-4 space-y-3">
            <QuickIntegrationCredentials
              endpoint={endpoint}
              tokenFallback={tokenFallback}
            />
            <div className="flex flex-wrap gap-2">
              {activeProjectId ? (
                <>
                  <form action={mintFormAction}>
                    <input name="project_id" type="hidden" value={activeProjectId} />
                    <Button
                      className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-[var(--vr-accent)] to-[var(--vr-accent-2)] px-4 py-2 text-xs font-semibold text-white transition hover:brightness-110"
                      disabled={mintPending}
                      size="sm"
                      type="submit"
                    >
                      <Plus className="size-3.5" />
                      {mintPending ? "Minting..." : "Mint Token"}
                    </Button>
                  </form>

                  {activeToken ? (
                    <form action={rotateFormAction}>
                      <input name="project_id" type="hidden" value={activeProjectId} />
                      <input name="token_id" type="hidden" value={activeToken.tokenId} />
                      <Button
                        className="inline-flex items-center gap-1.5 rounded-md border border-[var(--vr-divider)] px-4 py-2 text-xs font-medium text-[var(--vr-text-muted)] transition hover:bg-[var(--vr-bg-elevated)]"
                        disabled={rotatePending || activeToken.status === "revoked"}
                        size="sm"
                        type="submit"
                        variant="outline"
                      >
                        <RefreshCw className="size-3.5" />
                        Rotate
                      </Button>
                    </form>
                  ) : null}
                </>
              ) : (
                <p className="text-xs text-[var(--vr-text-dim)]">Select a project to manage tokens.</p>
              )}
            </div>
            {latestMessage ? (
              <p className="text-xs text-[var(--vr-text-main)]">{latestMessage}</p>
            ) : null}
          </div>
        </article>

        <article
          className="vr-fade-up rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6"
          style={{ animationDelay: "150ms" }}
        >
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-[15px] font-semibold text-[var(--vr-text-strong)]">Usage Trend (30d)</h2>
            <div className="rounded-md bg-[var(--vr-bg-elevated)] px-2.5 py-1 text-[11px] text-[var(--vr-text-muted)]">
              Daily
            </div>
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

      <section
        className="vr-fade-up rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6"
        style={{ animationDelay: "180ms" }}
      >
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-[15px] font-semibold text-[var(--vr-text-strong)]">Token Management</h2>
          {activeProjectId ? (
            <form action={mintFormAction}>
              <input name="project_id" type="hidden" value={activeProjectId} />
              <Button
                className="border border-[var(--vr-divider)] bg-[var(--vr-bg-elevated)] text-xs text-[var(--vr-text-strong)] hover:bg-[var(--vr-bg-input)]"
                disabled={mintPending}
                size="sm"
                type="submit"
                variant="outline"
              >
                <KeyRound className="size-3.5" />
                {mintPending ? "Minting..." : "Mint token"}
              </Button>
            </form>
          ) : null}
        </div>
        <div className="overflow-x-auto rounded-lg border border-[var(--vr-border)]">
          <table className="min-w-full text-left">
            <thead className="bg-[var(--vr-bg-input)] text-[11px] uppercase tracking-[0.04em] text-[var(--vr-text-dim)]">
              <tr>
                <th className="w-[200px] px-4 py-2.5">Token Prefix</th>
                <th className="px-4 py-2.5">Last Used</th>
                <th className="w-[120px] px-4 py-2.5">Status</th>
                <th className="w-[140px] px-4 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {visibleTokens.length > 0 ? (
                visibleTokens.map((token) => (
                  <tr className="border-t border-[var(--vr-border)]" key={token.tokenId}>
                    <td className="w-[200px] px-4 py-3 align-middle">
                      <p className="font-mono text-xs text-[var(--vr-text-main)]">{token.prefix}</p>
                      <p className="font-mono text-[10px] text-[var(--vr-text-dim)]">{token.tokenId}</p>
                    </td>
                    <td className="px-4 py-3 align-middle text-xs text-[var(--vr-text-muted)]">
                      {formatRelativeTime(token.lastUsedAt)}
                    </td>
                    <td className="w-[120px] px-4 py-3 align-middle">
                      <span
                        className={`rounded-full px-2.5 py-1 text-[11px] ${tokenBadgeClassName(token.status)}`}
                      >
                        {token.status}
                      </span>
                    </td>
                    <td className="w-[140px] px-4 py-3 align-middle">
                      {activeProjectId ? (
                        <div className="flex flex-wrap gap-2">
                          <form action={rotateFormAction}>
                            <input name="project_id" type="hidden" value={activeProjectId} />
                            <input name="token_id" type="hidden" value={token.tokenId} />
                            <Button
                              className="border-[var(--vr-divider)] text-[11px]"
                              disabled={rotatePending || token.status === "revoked"}
                              size="sm"
                              type="submit"
                              variant="outline"
                            >
                              <RotateCw className="size-3.5" />
                              Rotate
                            </Button>
                          </form>
                          <form action={revokeFormAction}>
                            <input name="project_id" type="hidden" value={activeProjectId} />
                            <input name="token_id" type="hidden" value={token.tokenId} />
                            <Button
                              className="border-rose-500/50 bg-rose-900/20 text-[11px] text-rose-100 hover:bg-rose-900/35"
                              disabled={revokePending || token.status === "revoked"}
                              size="sm"
                              type="submit"
                              variant="outline"
                            >
                              <ShieldX className="size-3.5" />
                              Revoke
                            </Button>
                          </form>
                        </div>
                      ) : (
                        <span className="text-xs text-[var(--vr-text-dim)]">-</span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr className="border-t border-[var(--vr-border)]">
                  <td className="px-4 py-6 text-center text-xs text-[var(--vr-text-dim)]" colSpan={4}>
                    {activeProjectId
                      ? tokens.length > 0
                        ? "No active tokens available for this project."
                        : "No tokens available for this project."
                      : "Select a project to manage tokens."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section
        className="vr-fade-up rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6"
        style={{ animationDelay: "220ms" }}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-[15px] font-semibold text-[var(--vr-text-strong)]">Recent API Logs</h2>
          {activeProjectId ? (
            <Link
              className="text-xs font-medium text-[var(--vr-accent-2)] transition hover:text-[var(--vr-accent-2)]"
              href={`/projects/${activeProjectId}/api-logs`}
            >
              View all →
            </Link>
          ) : null}
        </div>
        <div className="overflow-x-auto rounded-lg border border-[var(--vr-border)]">
          <table className="min-w-full text-left">
            <thead className="bg-[var(--vr-bg-input)] text-[11px] uppercase tracking-[0.04em] text-[var(--vr-text-dim)]">
              <tr>
                <th className="w-[160px] px-4 py-2.5">Time</th>
                <th className="w-[100px] px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Tool</th>
                <th className="w-[160px] px-4 py-2.5">Request ID</th>
              </tr>
            </thead>
            <tbody>
              {logs.length > 0 ? (
                logs.map((log) => (
                  <tr className="border-t border-[var(--vr-border)] text-xs" key={log.id}>
                    <td className="w-[160px] px-4 py-3 font-mono text-[var(--vr-text-muted)]">
                      {formatLogTime(log.createdAt)}
                    </td>
                    <td className="w-[100px] px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-[10px] ${statusClassName(log.status)}`}>
                        {log.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-[var(--vr-text-muted)]">
                      {log.toolName ?? "-"}
                    </td>
                    <td className="w-[160px] px-4 py-3 font-mono text-[var(--vr-text-dim)]">
                      {log.requestId ?? "-"}
                    </td>
                  </tr>
                ))
              ) : (
                <tr className="border-t border-[var(--vr-border)]">
                  <td className="px-4 py-6 text-center text-xs text-[var(--vr-text-dim)]" colSpan={4}>
                    {activeProjectId ? "No logs for this project yet." : "Select a project to view API logs."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section
        className="vr-fade-up rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6"
        style={{ animationDelay: "250ms" }}
      >
        <h2 className="mb-4 text-[15px] font-semibold text-[var(--vr-text-strong)]">Operations</h2>
        <div className="grid gap-4 xl:grid-cols-[1.1fr_1fr]">
          <article className="space-y-4 rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-elevated)] p-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-[var(--vr-text-strong)]">Exports</h3>
              {activeProjectId ? (
                <form action={exportFormAction}>
                  <input name="project_id" type="hidden" value={activeProjectId} />
                  <Button disabled={exportPending} size="sm" type="submit" variant="outline">
                    <FileArchive className="size-3.5" />
                    {exportPending ? "Queueing..." : "Create export"}
                  </Button>
                </form>
              ) : null}
            </div>

            {exports.length > 0 ? (
              <div className="space-y-2">
                {exports.map((entry) => {
                  const exportError = entry.error ? formatExportErrorMessage(entry.error) : null;
                  return (
                    <div
                      className="rounded-lg border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-3"
                      key={entry.exportId}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate font-mono text-xs text-[var(--vr-text-main)]">{entry.exportId}</p>
                        <span
                          className={`rounded-full px-2 py-1 text-[10px] uppercase tracking-[0.08em] ${exportStatusStyle(entry.status)}`}
                        >
                          {exportStatusLabel(entry.status)}
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-[var(--vr-text-dim)]">
                        Requested: {entry.requestedAt}
                      </p>
                      {entry.status === "complete" && entry.objectUrl ? (
                        <Button asChild className="mt-2" size="sm" variant="outline">
                          <a href={entry.objectUrl} rel="noreferrer" target="_blank">
                            <Download className="size-3.5" />
                            Download JSON
                          </a>
                        </Button>
                      ) : null}
                      {exportError ? (
                        <div className="mt-2 space-y-1 rounded-md border border-rose-400/30 bg-rose-500/10 px-2.5 py-2">
                          <p className="break-words text-xs text-rose-200">{exportError.message}</p>
                          {exportError.hint ? (
                            <p className="break-words text-[11px] text-rose-100/80">{exportError.hint}</p>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-[var(--vr-border)] bg-[var(--vr-bg-card)] px-3 py-4 text-xs text-[var(--vr-text-dim)]">
                {activeProjectId
                  ? "No export has been created for this project yet."
                  : "Select a project to manage exports."}
              </div>
            )}
          </article>
        </div>
      </section>

      <TokenIssuedModal
        endpoint={endpoint}
        mode={issuedTokenModal?.mode ?? "mint"}
        onClose={handleCloseIssuedTokenModal}
        open={Boolean(issuedTokenModal)}
        tokenPlaintext={issuedTokenModal?.tokenPlaintext ?? ""}
      />
    </div>
  );
}
