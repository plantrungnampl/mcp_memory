"use client";

import { useActionState, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  CircleEllipsis,
  Copy,
  Database,
  Download,
  FolderKanban,
  KeyRound,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShieldX,
  TerminalSquare,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import type {
  ExportActionState,
  MaintenanceActionState,
  ProjectActionState,
  TokenActionState,
} from "@/app/projects/action-types";
import type {
  McpConnectionInfo,
  ProjectExport,
  ProjectOverviewRow,
  ProjectSummary,
  ProjectToken,
  UsageSeries,
  UsageSummary,
} from "@/lib/api/types";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type ProjectsDashboardProps = {
  userEmail: string | null;
  projects: ProjectSummary[];
  overviewRows: ProjectOverviewRow[];
  activeProjectId: string | null;
  tokens: ProjectToken[];
  connection: McpConnectionInfo | null;
  usageDaily: UsageSummary | null;
  usageMonthly: UsageSummary | null;
  usageSeries: UsageSeries | null;
  exports: ProjectExport[];
  createProjectAction: (
    prevState: ProjectActionState,
    formData: FormData,
  ) => Promise<ProjectActionState>;
  mintTokenAction: (prevState: TokenActionState, formData: FormData) => Promise<TokenActionState>;
  rotateTokenAction: (prevState: TokenActionState, formData: FormData) => Promise<TokenActionState>;
  revokeTokenAction: (prevState: TokenActionState, formData: FormData) => Promise<TokenActionState>;
  createExportAction: (
    prevState: ExportActionState,
    formData: FormData,
  ) => Promise<ExportActionState>;
  runRetentionAction: (
    prevState: MaintenanceActionState,
    formData: FormData,
  ) => Promise<MaintenanceActionState>;
  migrateInlineToObjectAction: (
    prevState: MaintenanceActionState,
    formData: FormData,
  ) => Promise<MaintenanceActionState>;
  purgeProjectAction: (
    prevState: MaintenanceActionState,
    formData: FormData,
  ) => Promise<MaintenanceActionState>;
};

const INITIAL_PROJECT_STATE: ProjectActionState = {
  ok: false,
  message: null,
  nonce: null,
  projectId: null,
  tokenPlaintext: null,
  tokenPrefix: null,
};

const INITIAL_TOKEN_STATE: TokenActionState = {
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

const INITIAL_MAINTENANCE_STATE: MaintenanceActionState = {
  ok: false,
  message: null,
  nonce: null,
  jobId: null,
  kind: null,
  status: null,
};

const PLAN_QUOTA: Record<ProjectSummary["plan"], number> = {
  free: 100_000,
  pro: 5_000_000,
  team: 20_000_000,
};

function formatTimeAgo(value: string | null): string {
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

function statusBadgeStyle(status: ProjectOverviewRow["healthStatus"]): string {
  if (status === "active") {
    return "text-emerald-400";
  }
  if (status === "error") {
    return "text-rose-400";
  }
  return "text-amber-300";
}

function exportStatusStyle(status: ProjectExport["status"]): string {
  if (status === "complete") {
    return "bg-emerald-500/20 text-emerald-200";
  }
  if (status === "failed") {
    return "bg-rose-500/20 text-rose-200";
  }
  if (status === "processing") {
    return "bg-amber-500/20 text-amber-200";
  }
  return "bg-slate-700 text-slate-200";
}

function exportStatusLabel(status: ProjectExport["status"]): string {
  if (status === "complete") {
    return "Complete";
  }
  if (status === "failed") {
    return "Failed";
  }
  if (status === "processing") {
    return "Processing";
  }
  return "Pending";
}

function chartBars(series: UsageSeries | null): Array<{ dayLabel: string; vibeTokens: number; height: number }> {
  const source = series?.series ?? [];
  if (source.length === 0) {
    return [];
  }
  const maxValue = Math.max(1, ...source.map((entry) => entry.vibeTokens));
  return source.map((entry) => {
    const date = new Date(entry.bucketStart);
    return {
      dayLabel: Number.isNaN(date.getTime())
        ? entry.bucketStart
        : date.toLocaleDateString("en-US", { month: "short", day: "2-digit" }),
      vibeTokens: entry.vibeTokens,
      height: Math.max(8, Math.round((entry.vibeTokens / maxValue) * 100)),
    };
  });
}

export function ProjectsDashboard({
  userEmail,
  projects,
  overviewRows,
  activeProjectId,
  tokens,
  connection,
  usageDaily,
  usageMonthly,
  usageSeries,
  exports,
  createProjectAction,
  mintTokenAction,
  rotateTokenAction,
  revokeTokenAction,
  createExportAction,
  runRetentionAction,
  migrateInlineToObjectAction,
  purgeProjectAction,
}: ProjectsDashboardProps) {
  const router = useRouter();
  const [purgeConfirmInput, setPurgeConfirmInput] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [createState, createFormAction, createPending] = useActionState(
    createProjectAction,
    INITIAL_PROJECT_STATE,
  );
  const [mintState, mintFormAction, mintPending] = useActionState(mintTokenAction, INITIAL_TOKEN_STATE);
  const [rotateState, rotateFormAction, rotatePending] = useActionState(
    rotateTokenAction,
    INITIAL_TOKEN_STATE,
  );
  const [revokeState, revokeFormAction, revokePending] = useActionState(
    revokeTokenAction,
    INITIAL_TOKEN_STATE,
  );
  const [exportState, exportFormAction, exportPending] = useActionState(
    createExportAction,
    INITIAL_EXPORT_STATE,
  );
  const [retentionState, retentionFormAction, retentionPending] = useActionState(
    runRetentionAction,
    INITIAL_MAINTENANCE_STATE,
  );
  const [migrateState, migrateFormAction, migratePending] = useActionState(
    migrateInlineToObjectAction,
    INITIAL_MAINTENANCE_STATE,
  );
  const [purgeState, purgeFormAction, purgePending] = useActionState(
    purgeProjectAction,
    INITIAL_MAINTENANCE_STATE,
  );

  const bars = useMemo(() => chartBars(usageSeries), [usageSeries]);
  const activeProject = projects.find((entry) => entry.id === activeProjectId) ?? null;
  const planQuota = activeProject ? PLAN_QUOTA[activeProject.plan] : PLAN_QUOTA.free;
  const usageMonthlyValue = usageMonthly?.vibeTokens ?? 0;
  const usagePct = Math.min(100, Math.round((usageMonthlyValue / Math.max(planQuota, 1)) * 100));
  const activeToken = tokens.find((token) => token.status !== "revoked") ?? tokens[0] ?? null;
  const tokenPreview = activeToken?.prefix ?? connection?.tokenPreview ?? "No token available";
  const latestTokenReveal = rotateState.tokenPlaintext ?? mintState.tokenPlaintext ?? createState.tokenPlaintext;

  useEffect(() => {
    if (createState.ok && createState.projectId) {
      router.push(`/projects?project=${createState.projectId}`);
      router.refresh();
    }
  }, [createState.nonce, createState.ok, createState.projectId, router]);

  useEffect(() => {
    if (
      mintState.ok ||
      rotateState.ok ||
      revokeState.ok ||
      exportState.ok ||
      retentionState.ok ||
      migrateState.ok ||
      purgeState.ok
    ) {
      router.refresh();
    }
  }, [
    exportState.nonce,
    exportState.ok,
    mintState.nonce,
    mintState.ok,
    migrateState.nonce,
    migrateState.ok,
    purgeState.nonce,
    purgeState.ok,
    retentionState.nonce,
    retentionState.ok,
    revokeState.nonce,
    revokeState.ok,
    rotateState.nonce,
    rotateState.ok,
    router,
  ]);

  useEffect(() => {
    if (!createState.nonce || !createState.message) {
      return;
    }
    if (createState.ok) {
      toast.success(createState.message);
      return;
    }
    toast.error(createState.message);
  }, [createState.message, createState.nonce, createState.ok]);

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

  useEffect(() => {
    if (!retentionState.nonce || !retentionState.message) {
      return;
    }
    if (retentionState.ok) {
      toast.success(retentionState.message);
      return;
    }
    toast.error(retentionState.message);
  }, [retentionState.message, retentionState.nonce, retentionState.ok]);

  useEffect(() => {
    if (!migrateState.nonce || !migrateState.message) {
      return;
    }
    if (migrateState.ok) {
      toast.success(migrateState.message);
      return;
    }
    toast.error(migrateState.message);
  }, [migrateState.message, migrateState.nonce, migrateState.ok]);

  useEffect(() => {
    if (!purgeState.nonce || !purgeState.message) {
      return;
    }
    if (purgeState.ok) {
      toast.success(purgeState.message);
      return;
    }
    toast.error(purgeState.message);
  }, [purgeState.message, purgeState.nonce, purgeState.ok]);

  useEffect(() => {
    if (!activeProjectId) {
      return;
    }
    const hasRunningExport = exports.some(
      (entry) => entry.status === "pending" || entry.status === "processing",
    );
    if (!hasRunningExport) {
      return;
    }
    const timer = window.setInterval(() => router.refresh(), 5_000);
    return () => window.clearInterval(timer);
  }, [activeProjectId, exports, router]);

  async function copyValue(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(`${label} copied`);
    } catch {
      toast.error(`Could not copy ${label.toLowerCase()}`);
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_15%_15%,rgba(122,45,190,0.28),transparent_30%),radial-gradient(circle_at_85%_10%,rgba(0,245,255,0.14),transparent_24%),linear-gradient(180deg,#0a0810_0%,#130d1d_100%)] text-slate-100">
      <div className="flex min-h-screen">
        <aside className="hidden w-64 shrink-0 border-r border-[#7a2dbe]/25 bg-[#110d1a]/80 backdrop-blur xl:flex xl:flex-col">
          <div className="border-b border-[#7a2dbe]/20 px-5 py-5">
            <div className="flex items-center gap-3">
              <div className="flex size-8 items-center justify-center rounded-md bg-[#7a2dbe]/25 shadow-[0_0_20px_rgba(122,45,190,0.5)]">
                <Activity className="size-4 text-[#00f5ff]" />
              </div>
              <p className="text-base font-bold tracking-tight text-[#d8bbff]">VibeRecall</p>
            </div>
          </div>
          <nav className="flex-1 space-y-2 p-4 text-sm">
            <Link
              href="/projects"
              className="flex items-center gap-3 rounded-md border border-[#7a2dbe]/35 bg-[#7a2dbe]/18 px-3 py-2 text-[#ebd9ff]"
            >
              <FolderKanban className="size-4" />
              Projects
            </Link>
            <span className="flex items-center gap-3 rounded-md px-3 py-2 text-slate-400">
              <BarChart3 className="size-4" />
              VibeTokens (Soon)
            </span>
            <span className="flex items-center gap-3 rounded-md px-3 py-2 text-slate-400">
              <Activity className="size-4" />
              Usage Analytics (Soon)
            </span>
            <span className="flex items-center gap-3 rounded-md px-3 py-2 text-slate-400">
              <Database className="size-4" />
              Billing (Soon)
            </span>
            <span className="flex items-center gap-3 rounded-md px-3 py-2 text-slate-400">
              <TerminalSquare className="size-4" />
              API Logs (Soon)
            </span>
          </nav>
          <div className="border-t border-[#7a2dbe]/20 p-4">
            <div className="rounded-xl border border-[#7a2dbe]/35 bg-[#7a2dbe]/10 p-3">
              <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-[0.14em] text-[#dcbfff]">
                <span>{activeProject?.plan ?? "free"} plan</span>
                <span>{usagePct}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-800/70">
                <div className="h-full rounded-full bg-[#7a2dbe]" style={{ width: `${usagePct}%` }} />
              </div>
              <p className="mt-2 text-[11px] text-slate-300">
                {(usageMonthly?.vibeTokens ?? 0).toLocaleString()} / {planQuota.toLocaleString()} VibeTokens
              </p>
            </div>
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-[#7a2dbe]/20 bg-[#0f0a17]/75 px-4 py-4 backdrop-blur md:px-8">
            <div className="flex flex-wrap items-center gap-3 md:gap-4">
              <div className="relative min-w-[14rem] flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
                <Input
                  className="border-[#7a2dbe]/25 bg-[#1b1228] pl-10 text-sm text-slate-200 placeholder:text-slate-500"
                  placeholder="Search projects, tokens, logs..."
                  readOnly
                  value=""
                />
              </div>
              <button className="rounded-md border border-[#7a2dbe]/30 p-2 text-slate-300 hover:text-[#00f5ff]">
                <Bell className="size-4" />
              </button>
              <button className="rounded-md border border-[#7a2dbe]/30 p-2 text-slate-300 hover:text-[#00f5ff]">
                <Settings className="size-4" />
              </button>
              <div className="flex items-center gap-2 rounded-md border border-[#7a2dbe]/30 bg-[#1a1325] px-3 py-2">
                <div className="hidden text-right text-[11px] md:block">
                  <p className="font-semibold text-slate-200">{userEmail ?? "unknown"}</p>
                  <p className="uppercase tracking-[0.16em] text-slate-400">Owner</p>
                </div>
                <div className="flex size-8 items-center justify-center rounded-full bg-[#7a2dbe]/25 text-xs font-bold text-[#00f5ff]">
                  {(userEmail ?? "U").charAt(0).toUpperCase()}
                </div>
              </div>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
            <div className="space-y-6">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <h1 className="text-3xl font-black tracking-tight">Project Dashboard</h1>
                  <p className="mt-1 text-sm text-slate-400">
                    Real-time control-plane monitoring and operations for your active projects.
                  </p>
                </div>
                <form action={createFormAction} className="flex w-full max-w-md gap-2">
                  <Input
                    className="border-[#7a2dbe]/30 bg-[#1b1228] text-slate-100 placeholder:text-slate-500"
                    name="name"
                    placeholder="New project name"
                  />
                  <Button className="bg-[#7a2dbe] hover:bg-[#6923a8]" disabled={createPending} type="submit">
                    <Plus className="size-4" />
                    {createPending ? "Creating..." : "New Project"}
                  </Button>
                </form>
              </div>

              {latestTokenReveal ? (
                <div className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 p-3 text-xs text-emerald-200">
                  <p className="font-semibold uppercase tracking-[0.16em]">Token reveal (copy now)</p>
                  <p className="mt-1 break-all font-mono">{latestTokenReveal}</p>
                </div>
              ) : null}

              <div className="grid gap-6 xl:grid-cols-12">
                <div className="rounded-xl border border-[#7a2dbe]/30 bg-[#120e1d]/75 p-5 xl:col-span-8">
                  <div className="mb-6 flex items-center justify-between">
                    <div>
                      <h2 className="text-lg font-bold">VibeTokens Consumption</h2>
                      <p className="text-xs text-slate-400">Daily usage in the last {usageSeries?.windowDays ?? 30} days</p>
                    </div>
                    <div className="rounded-md border border-[#7a2dbe]/30 bg-[#7a2dbe]/20 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#d8bbff]">
                      30D
                    </div>
                  </div>

                  {bars.length > 0 ? (
                    <div className="flex h-48 items-end gap-1">
                      {bars.map((bar, index) => (
                        <div
                          className={`w-full rounded-t-sm ${index === bars.length - 1 ? "bg-[#7a2dbe] shadow-[0_0_18px_rgba(122,45,190,0.5)]" : "bg-[#7a2dbe]/35"}`}
                          key={`${bar.dayLabel}-${index}`}
                          style={{ height: `${bar.height}%` }}
                          title={`${bar.dayLabel}: ${bar.vibeTokens.toLocaleString()} VT`}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="flex h-48 items-center justify-center rounded-md border border-dashed border-[#7a2dbe]/30 text-sm text-slate-400">
                      No usage events yet
                    </div>
                  )}

                  <div className="mt-4 flex items-center justify-between text-[10px] uppercase tracking-[0.14em] text-slate-400">
                    <span>{bars[0]?.dayLabel ?? "-"}</span>
                    <span>{bars[Math.floor(bars.length / 2)]?.dayLabel ?? "-"}</span>
                    <span>{bars[bars.length - 1]?.dayLabel ?? "-"}</span>
                  </div>
                </div>

                <div className="rounded-xl border border-[#7a2dbe]/30 bg-[#120e1d]/75 p-5 xl:col-span-4">
                  <h2 className="mb-4 text-lg font-bold">Quick Integration</h2>
                  <div className="space-y-4">
                    <div>
                      <p className="mb-1 text-[11px] uppercase tracking-[0.14em] text-slate-400">MCP endpoint</p>
                      <div className="flex gap-2">
                        <Input
                          className="border-[#7a2dbe]/30 bg-[#1b1228] font-mono text-xs text-[#dcbfff]"
                          readOnly
                          value={connection?.endpoint ?? "Select a project to view endpoint"}
                        />
                        <Button
                          className="border-[#7a2dbe]/30 bg-[#221833] text-slate-200 hover:bg-[#2c2040]"
                          onClick={() => {
                            if (connection?.endpoint) {
                              void copyValue(connection.endpoint, "Endpoint");
                            }
                          }}
                          type="button"
                          variant="outline"
                        >
                          <Copy className="size-4" />
                        </Button>
                      </div>
                    </div>
                    <div>
                      <p className="mb-1 text-[11px] uppercase tracking-[0.14em] text-slate-400">Secret token</p>
                      <div className="flex gap-2">
                        <Input
                          className="border-[#7a2dbe]/30 bg-[#1b1228] font-mono text-xs text-[#dcbfff]"
                          readOnly
                          type={showToken ? "text" : "password"}
                          value={tokenPreview}
                        />
                        <Button
                          className="border-[#7a2dbe]/30 bg-[#221833] text-slate-200 hover:bg-[#2c2040]"
                          onClick={() => setShowToken((current) => !current)}
                          type="button"
                          variant="outline"
                        >
                          {showToken ? "Hide" : "Show"}
                        </Button>
                      </div>
                      <p className="mt-1 text-[11px] text-slate-400">
                        Last activity: {formatTimeAgo(overviewRows.find((row) => row.id === activeProjectId)?.lastActivityAt ?? null)}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {activeProjectId ? (
                        <form action={mintFormAction}>
                          <input name="project_id" type="hidden" value={activeProjectId} />
                          <Button disabled={mintPending} size="sm" type="submit" variant="outline">
                            <KeyRound className="size-4" />
                            {mintPending ? "Minting..." : "Mint token"}
                          </Button>
                        </form>
                      ) : null}
                      {activeProjectId && activeToken ? (
                        <form action={rotateFormAction}>
                          <input name="project_id" type="hidden" value={activeProjectId} />
                          <input name="token_id" type="hidden" value={activeToken.tokenId} />
                          <Button disabled={rotatePending} size="sm" type="submit" variant="outline">
                            <RefreshCw className="size-4" />
                            {rotatePending ? "Rotating..." : "Rotate active"}
                          </Button>
                        </form>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>

              <div className="overflow-hidden rounded-xl border border-[#7a2dbe]/30 bg-[#120e1d]/75">
                <div className="flex items-center justify-between border-b border-[#7a2dbe]/20 px-5 py-4">
                  <h2 className="text-lg font-bold">Active Projects</h2>
                  <span className="text-xs uppercase tracking-[0.14em] text-slate-400">{overviewRows.length} projects</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-sm">
                    <thead className="text-[11px] uppercase tracking-[0.14em] text-slate-400">
                      <tr>
                        <th className="px-5 py-3">Project</th>
                        <th className="px-5 py-3">Status</th>
                        <th className="px-5 py-3">Last activity</th>
                        <th className="px-5 py-3">Tokens (30d)</th>
                        <th className="px-5 py-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#7a2dbe]/15">
                      {overviewRows.map((row) => (
                        <tr
                          className={row.id === activeProjectId ? "bg-[#7a2dbe]/10" : "hover:bg-[#7a2dbe]/6"}
                          key={row.id}
                        >
                          <td className="px-5 py-4">
                            <div>
                              <p className="font-semibold">{row.name}</p>
                              <p className="font-mono text-xs text-slate-500">{row.id}</p>
                            </div>
                          </td>
                          <td className="px-5 py-4">
                            <span className={`inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] ${statusBadgeStyle(row.healthStatus)}`}>
                              <span
                                className={`size-2 rounded-full ${row.healthStatus === "active" ? "bg-emerald-400" : row.healthStatus === "error" ? "bg-rose-400" : "bg-amber-300"}`}
                              />
                              {row.healthStatus}
                            </span>
                          </td>
                          <td className="px-5 py-4 text-xs text-slate-300">{formatTimeAgo(row.lastActivityAt)}</td>
                          <td className="px-5 py-4">
                            <span className="font-mono text-sm">{row.vibeTokensWindow.toLocaleString()}</span>
                          </td>
                          <td className="px-5 py-4 text-right">
                            <Button asChild size="sm" variant="ghost">
                              <Link href={`/projects?project=${row.id}`}>
                                <CircleEllipsis className="size-4" />
                                Open
                              </Link>
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="grid gap-6 xl:grid-cols-2">
                <div className="space-y-4 rounded-xl border border-[#7a2dbe]/30 bg-[#120e1d]/75 p-5">
                  <h2 className="text-lg font-bold">Token + Export Operations</h2>
                  {tokens.length > 0 ? (
                    <div className="space-y-3">
                      {tokens.map((token) => (
                        <div className="rounded-lg border border-[#7a2dbe]/20 bg-[#1b1228] p-3" key={token.tokenId}>
                          <div className="flex items-center justify-between gap-2">
                            <div>
                              <p className="font-mono text-xs text-[#dcbfff]">{token.prefix}</p>
                              <p className="text-[11px] text-slate-400">Last used: {formatTimeAgo(token.lastUsedAt)}</p>
                            </div>
                            <span className="rounded-full border border-[#7a2dbe]/30 px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-slate-300">
                              {token.status}
                            </span>
                          </div>
                          {activeProjectId ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              <form action={rotateFormAction}>
                                <input name="project_id" type="hidden" value={activeProjectId} />
                                <input name="token_id" type="hidden" value={token.tokenId} />
                                <Button disabled={rotatePending || token.status === "revoked"} size="sm" type="submit" variant="outline">
                                  <RefreshCw className="size-4" />
                                  Rotate
                                </Button>
                              </form>
                              <form action={revokeFormAction}>
                                <input name="project_id" type="hidden" value={activeProjectId} />
                                <input name="token_id" type="hidden" value={token.tokenId} />
                                <Button disabled={revokePending || token.status === "revoked"} size="sm" type="submit" variant="outline">
                                  <ShieldX className="size-4" />
                                  Revoke
                                </Button>
                              </form>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-lg border border-dashed border-[#7a2dbe]/20 bg-[#1b1228] p-4 text-sm text-slate-400">
                      Select a project to manage tokens.
                    </div>
                  )}

                  {activeProjectId ? (
                    <form action={exportFormAction} className="pt-2">
                      <input name="project_id" type="hidden" value={activeProjectId} />
                      <Button disabled={exportPending} type="submit" variant="outline">
                        <Download className="size-4" />
                        {exportPending ? "Queueing..." : "Create export snapshot"}
                      </Button>
                    </form>
                  ) : null}

                  <div className="space-y-2">
                    {exports.map((entry) => (
                      <div className="rounded-lg border border-[#7a2dbe]/20 bg-[#1b1228] p-3 text-sm" key={entry.exportId}>
                        <div className="flex items-center justify-between gap-2">
                          <p className="font-mono text-xs text-slate-300">{entry.exportId}</p>
                          <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] ${exportStatusStyle(entry.status)}`}>
                            {exportStatusLabel(entry.status)}
                          </span>
                        </div>
                        <p className="mt-1 text-[11px] text-slate-400">{entry.jobId ?? "No job id"}</p>
                        {entry.status === "complete" && entry.objectUrl ? (
                          <div className="mt-2">
                            <Button asChild size="sm" variant="outline">
                              <a href={entry.objectUrl} rel="noreferrer" target="_blank">
                                <Download className="size-4" />
                                Download JSON
                              </a>
                            </Button>
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-4 rounded-xl border border-[#7a2dbe]/30 bg-[#120e1d]/75 p-5">
                  <h2 className="text-lg font-bold">Maintenance + Rollups</h2>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-lg border border-[#7a2dbe]/20 bg-[#1b1228] p-4">
                      <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">24h usage</p>
                      <p className="mt-2 text-2xl font-bold">{(usageDaily?.vibeTokens ?? 0).toLocaleString()}</p>
                      <p className="text-xs text-slate-400">events: {(usageDaily?.eventCount ?? 0).toLocaleString()}</p>
                    </div>
                    <div className="rounded-lg border border-[#7a2dbe]/20 bg-[#1b1228] p-4">
                      <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">30d usage</p>
                      <p className="mt-2 text-2xl font-bold">{(usageMonthly?.vibeTokens ?? 0).toLocaleString()}</p>
                      <p className="text-xs text-slate-400">events: {(usageMonthly?.eventCount ?? 0).toLocaleString()}</p>
                    </div>
                  </div>

                  {activeProjectId ? (
                    <div className="space-y-3">
                      <form action={retentionFormAction}>
                        <input name="project_id" type="hidden" value={activeProjectId} />
                        <Button disabled={retentionPending} type="submit" variant="outline">
                          <RefreshCw className="size-4" />
                          {retentionPending ? "Queueing retention..." : "Run retention"}
                        </Button>
                      </form>
                      <form action={migrateFormAction} className="rounded-lg border border-[#7a2dbe]/20 bg-[#1b1228] p-3">
                        <input name="project_id" type="hidden" value={activeProjectId} />
                        <div className="flex flex-wrap items-center gap-3">
                          <label className="flex items-center gap-2 text-xs text-amber-200">
                            <input className="size-4" name="force" type="checkbox" value="1" />
                            Force migration
                          </label>
                          <Button disabled={migratePending} size="sm" type="submit" variant="outline">
                            <Database className="size-4" />
                            {migratePending ? "Queueing..." : "Migrate inline->object"}
                          </Button>
                        </div>
                      </form>
                      <form action={purgeFormAction} className="rounded-lg border border-rose-400/30 bg-rose-400/10 p-3">
                        <input name="project_id" type="hidden" value={activeProjectId} />
                        <p className="mb-2 text-xs text-rose-200">
                          Type project id to confirm destructive purge.
                        </p>
                        <Input
                          autoComplete="off"
                          className="border-rose-400/30 bg-[#2a131f] text-rose-100 placeholder:text-rose-300/60"
                          name="confirm_project_id"
                          onChange={(event) => setPurgeConfirmInput(event.target.value)}
                          placeholder={`Type ${activeProjectId}`}
                          value={purgeConfirmInput}
                        />
                        <div className="mt-3">
                          <Button
                            disabled={purgePending || purgeConfirmInput !== activeProjectId}
                            size="sm"
                            type="submit"
                            variant="outline"
                          >
                            <Trash2 className="size-4" />
                            {purgePending ? "Queueing purge..." : "Purge project"}
                          </Button>
                        </div>
                      </form>
                    </div>
                  ) : (
                    <div className="rounded-lg border border-dashed border-[#7a2dbe]/20 bg-[#1b1228] p-4 text-sm text-slate-400">
                      Select a project to run maintenance actions.
                    </div>
                  )}

                  {retentionState.jobId ? (
                    <p className="rounded-lg bg-emerald-500/15 px-3 py-2 text-xs text-emerald-200">
                      Retention queued: {retentionState.jobId}
                    </p>
                  ) : null}
                  {migrateState.jobId ? (
                    <p className="rounded-lg bg-amber-500/15 px-3 py-2 text-xs text-amber-200">
                      Migration queued: {migrateState.jobId}
                    </p>
                  ) : null}
                  {purgeState.jobId ? (
                    <p className="rounded-lg bg-rose-500/15 px-3 py-2 text-xs text-rose-200">
                      Purge queued: {purgeState.jobId}
                    </p>
                  ) : null}
                </div>
              </div>

              {createState.message && !createState.ok ? (
                <div className="flex items-center gap-2 rounded-xl border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-sm text-rose-100">
                  <AlertTriangle className="size-4" />
                  {createState.message}
                </div>
              ) : null}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
