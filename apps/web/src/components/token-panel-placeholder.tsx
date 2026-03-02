"use client";

import { useActionState, useEffect, useState } from "react";
import {
  Database,
  Download,
  FileArchive,
  KeyRound,
  RotateCw,
  ShieldCheck,
  ShieldX,
  Trash2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import type {
  ExportActionState,
  MaintenanceActionState,
  TokenActionState,
} from "@/app/projects/action-types";
import type { McpConnectionInfo, ProjectExport, ProjectToken, UsageSummary } from "@/lib/api/types";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type TokenPanelPlaceholderProps = {
  activeProjectId: string | null;
  tokens: ProjectToken[];
  connection: McpConnectionInfo | null;
  usageDaily: UsageSummary | null;
  usageMonthly: UsageSummary | null;
  exports: ProjectExport[];
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

const INITIAL_MAINTENANCE_STATE: MaintenanceActionState = {
  ok: false,
  message: null,
  nonce: null,
  jobId: null,
  kind: null,
  status: null,
};

function statusLabel(status: ProjectToken["status"]): string {
  if (status === "grace") {
    return "Grace";
  }
  if (status === "revoked") {
    return "Revoked";
  }
  return "Active";
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

function maintenanceKindLabel(kind: MaintenanceActionState["kind"]): string {
  if (kind === "retention") {
    return "Retention";
  }
  if (kind === "purge_project") {
    return "Purge";
  }
  if (kind === "migrate_inline_to_object") {
    return "Migrate inline->object";
  }
  return "Maintenance";
}

export function TokenPanelPlaceholder({
  activeProjectId,
  tokens,
  connection,
  usageDaily,
  usageMonthly,
  exports,
  mintTokenAction,
  rotateTokenAction,
  revokeTokenAction,
  createExportAction,
  runRetentionAction,
  migrateInlineToObjectAction,
  purgeProjectAction,
}: TokenPanelPlaceholderProps) {
  const router = useRouter();
  const [purgeConfirmInput, setPurgeConfirmInput] = useState("");
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
    migrateState.nonce,
    migrateState.ok,
    mintState.ok,
    mintState.nonce,
    purgeState.nonce,
    purgeState.ok,
    retentionState.nonce,
    retentionState.ok,
    revokeState.ok,
    revokeState.nonce,
    rotateState.nonce,
    rotateState.ok,
    router,
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
    const timer = window.setInterval(() => {
      router.refresh();
    }, 5_000);
    return () => {
      window.clearInterval(timer);
    };
  }, [activeProjectId, exports, router]);

  const latestReveal = rotateState.tokenPlaintext ?? mintState.tokenPlaintext;
  const latestMessage =
    exportState.message ?? revokeState.message ?? rotateState.message ?? mintState.message;

  return (
    <div className="grid gap-4">
      <Card className="border-black/8 bg-stone-950 text-stone-50">
        <CardHeader>
          <CardDescription className="text-stone-300">MCP endpoint</CardDescription>
          <CardTitle className="text-stone-50">Project transport details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-stone-200">
          {connection ? (
            <>
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 font-mono text-xs leading-6">
                {connection.endpoint}
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 font-mono text-xs">
                {connection.tokenPreview ?? "No token provisioned yet"}
              </div>
            </>
          ) : (
            <div className="rounded-2xl border border-dashed border-white/10 bg-white/5 px-4 py-4 text-sm leading-6 text-stone-300">
              Select a project to view endpoint and token posture.
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/78 text-slate-100">
        <CardHeader>
          <CardDescription className="text-slate-400">Token posture</CardDescription>
          <CardTitle className="text-slate-100">Active and historical tokens</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-slate-200">
          {activeProjectId ? (
            <form action={mintFormAction}>
              <input name="project_id" type="hidden" value={activeProjectId} />
              <Button
                className="border-[#7a2dbe]/45 bg-[#120e1d] text-slate-100 hover:bg-[#1d1530]"
                disabled={mintPending}
                size="sm"
                type="submit"
                variant="outline"
              >
                <KeyRound className="size-4" />
                {mintPending ? "Minting..." : "Mint token"}
              </Button>
            </form>
          ) : null}

          {latestMessage ? <p className="text-xs text-slate-300">{latestMessage}</p> : null}
          {latestReveal ? (
            <div className="rounded-xl border border-emerald-300/45 bg-emerald-900/25 px-3 py-2">
              <p className="text-xs font-medium text-emerald-200">Copy token now (shown once)</p>
              <p className="mt-1 font-mono text-xs text-emerald-100">{latestReveal}</p>
            </div>
          ) : null}

          {tokens.length ? (
            <div className="grid gap-3">
              {tokens.map((token) => (
                <div
                  className="grid gap-3 rounded-2xl border border-[#7a2dbe]/25 bg-[#1a1325]/70 px-4 py-3"
                  key={token.tokenId}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-slate-100">{token.prefix}</p>
                      <p className="font-mono text-xs text-slate-500">{token.tokenId}</p>
                    </div>
                    <div className="rounded-full bg-[#241a39] px-3 py-1 text-xs uppercase tracking-[0.18em] text-[#e6d4ff]">
                      {statusLabel(token.status)}
                    </div>
                  </div>
                  <div className="text-xs text-slate-400">
                    Last used: {token.lastUsedAt ?? "never"} · Expires: {token.expiresAt ?? "never"}
                  </div>
                  {activeProjectId ? (
                    <div className="flex flex-wrap gap-2">
                      <form action={rotateFormAction}>
                        <input name="project_id" type="hidden" value={activeProjectId} />
                        <input name="token_id" type="hidden" value={token.tokenId} />
                        <Button
                          className="border-[#7a2dbe]/45 bg-[#120e1d] text-slate-100 hover:bg-[#1d1530]"
                          disabled={rotatePending || token.status === "revoked"}
                          size="sm"
                          type="submit"
                          variant="outline"
                        >
                          <RotateCw className="size-4" />
                          Rotate
                        </Button>
                      </form>
                      <form action={revokeFormAction}>
                        <input name="project_id" type="hidden" value={activeProjectId} />
                        <input name="token_id" type="hidden" value={token.tokenId} />
                        <Button
                          className="border-rose-500/50 bg-rose-900/20 text-rose-100 hover:bg-rose-900/35"
                          disabled={revokePending || token.status === "revoked"}
                          size="sm"
                          type="submit"
                          variant="outline"
                        >
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
            <div className="rounded-2xl border border-dashed border-[#7a2dbe]/30 bg-[#1a1325]/60 px-4 py-4 text-sm leading-6 text-slate-300">
              {activeProjectId
                ? "No token is associated with this project yet."
                : "Select a project to manage tokens."}
            </div>
          )}

          <div className="flex items-center gap-2 text-xs text-slate-400">
            <ShieldCheck className="size-4" />
            Rotate keeps the previous token valid for a short grace window.
          </div>
        </CardContent>
      </Card>

      <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/78 text-slate-100">
        <CardHeader>
          <CardDescription className="text-slate-400">Usage</CardDescription>
          <CardTitle className="text-slate-100">Token rollups</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm text-slate-200">
          <div className="rounded-2xl border border-[#7a2dbe]/25 bg-[#1a1325]/70 px-4 py-3">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Last 24h</p>
            <p className="mt-2 font-[family:var(--font-heading)] text-2xl text-slate-100">
              {usageDaily ? usageDaily.vibeTokens.toLocaleString() : "0"} VT
            </p>
            <p className="text-xs text-slate-400">
              Events: {usageDaily ? usageDaily.eventCount.toLocaleString() : "0"}
            </p>
          </div>
          <div className="rounded-2xl border border-[#7a2dbe]/25 bg-[#1a1325]/70 px-4 py-3">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Last 30d</p>
            <p className="mt-2 font-[family:var(--font-heading)] text-2xl text-slate-100">
              {usageMonthly ? usageMonthly.vibeTokens.toLocaleString() : "0"} VT
            </p>
            <p className="text-xs text-slate-400">
              Events: {usageMonthly ? usageMonthly.eventCount.toLocaleString() : "0"}
            </p>
          </div>
        </CardContent>
      </Card>

      <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/78 text-slate-100">
        <CardHeader>
          <CardDescription className="text-slate-400">Exports</CardDescription>
          <CardTitle className="text-slate-100">Project memory snapshots</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-slate-200">
          {activeProjectId ? (
            <form action={exportFormAction}>
              <input name="project_id" type="hidden" value={activeProjectId} />
              <Button
                className="border-[#7a2dbe]/45 bg-[#120e1d] text-slate-100 hover:bg-[#1d1530]"
                disabled={exportPending}
                size="sm"
                type="submit"
                variant="outline"
              >
                <FileArchive className="size-4" />
                {exportPending ? "Queueing..." : "Create export"}
              </Button>
            </form>
          ) : null}

          {exports.length > 0 ? (
            <div className="grid gap-3">
              {exports.map((entry) => (
                <div
                  className="grid gap-3 rounded-2xl border border-[#7a2dbe]/25 bg-[#1a1325]/70 px-4 py-3"
                  key={entry.exportId}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-slate-100">{entry.exportId}</p>
                      <p className="font-mono text-xs text-slate-500">{entry.jobId ?? "No job id"}</p>
                    </div>
                    <div
                      className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.18em] ${exportStatusStyle(entry.status)}`}
                    >
                      {exportStatusLabel(entry.status)}
                    </div>
                  </div>
                  <div className="text-xs text-slate-400">
                    Requested: {entry.requestedAt} · Completed: {entry.completedAt ?? "in progress"}
                  </div>
                  {entry.error ? (
                    <div className="rounded-xl border border-rose-500/35 bg-rose-900/20 px-3 py-2 text-xs text-rose-200">
                      {entry.error}
                    </div>
                  ) : null}
                  {entry.status === "complete" && entry.objectUrl ? (
                    <Button
                      asChild
                      className="border-[#7a2dbe]/45 bg-[#120e1d] text-slate-100 hover:bg-[#1d1530]"
                      size="sm"
                      variant="outline"
                    >
                      <a href={entry.objectUrl} rel="noreferrer" target="_blank">
                        <Download className="size-4" />
                        Download JSON
                      </a>
                    </Button>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-[#7a2dbe]/30 bg-[#1a1325]/60 px-4 py-4 text-sm leading-6 text-slate-300">
              {activeProjectId
                ? "No export has been created for this project yet."
                : "Select a project to manage exports."}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/78 text-slate-100">
        <CardHeader>
          <CardDescription className="text-slate-400">Maintenance</CardDescription>
          <CardTitle className="text-slate-100">Retention, migration, and purge</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-slate-200">
          {activeProjectId ? (
            <div className="grid gap-3">
              <form action={retentionFormAction}>
                <input name="project_id" type="hidden" value={activeProjectId} />
                <Button
                  className="border-[#7a2dbe]/45 bg-[#120e1d] text-slate-100 hover:bg-[#1d1530]"
                  disabled={retentionPending}
                  size="sm"
                  type="submit"
                  variant="outline"
                >
                  <RotateCw className="size-4" />
                  {retentionPending ? "Queueing retention..." : "Run retention"}
                </Button>
              </form>

              <form
                action={migrateFormAction}
                className="space-y-3 rounded-2xl border border-[#7a2dbe]/25 bg-[#1a1325]/60 p-3"
              >
                <input name="project_id" type="hidden" value={activeProjectId} />
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-slate-300">Move large inline episodes to object storage.</p>
                  <Button
                    className="border-[#7a2dbe]/45 bg-[#120e1d] text-slate-100 hover:bg-[#1d1530]"
                    disabled={migratePending}
                    size="sm"
                    type="submit"
                    variant="outline"
                  >
                    <Database className="size-4" />
                    {migratePending ? "Queueing migrate..." : "Run migration"}
                  </Button>
                </div>
                <label className="flex items-center gap-2 text-xs text-amber-200">
                  <input className="size-4" name="force" type="checkbox" value="1" />
                  Force migration (advanced, skip safety gate)
                </label>
              </form>

              <form
                action={purgeFormAction}
                className="space-y-3 rounded-2xl border border-rose-500/40 bg-rose-900/20 p-3"
              >
                <input name="project_id" type="hidden" value={activeProjectId} />
                <p className="text-xs text-rose-200">
                  Purge deletes project graph, episodes, exports, and scrubs logs.
                </p>
                <Input
                  autoComplete="off"
                  className="h-10 rounded-xl border-rose-500/45 bg-rose-950/20 text-rose-50 placeholder:text-rose-200/65"
                  name="confirm_project_id"
                  onChange={(event) => setPurgeConfirmInput(event.target.value)}
                  placeholder={`Type ${activeProjectId} to confirm`}
                  value={purgeConfirmInput}
                />
                <Button
                  className="border-rose-500/50 bg-rose-900/20 text-rose-100 hover:bg-rose-900/35"
                  disabled={purgePending || purgeConfirmInput !== activeProjectId}
                  size="sm"
                  type="submit"
                  variant="outline"
                >
                  <Trash2 className="size-4" />
                  {purgePending ? "Queueing purge..." : "Purge project"}
                </Button>
              </form>
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-[#7a2dbe]/30 bg-[#1a1325]/60 px-4 py-4 text-sm leading-6 text-slate-300">
              Select a project to run maintenance actions.
            </div>
          )}

          {retentionState.jobId ? (
            <div className="rounded-xl border border-emerald-300/35 bg-emerald-900/20 px-3 py-2 text-xs text-emerald-200">
              {maintenanceKindLabel(retentionState.kind)} queued: {retentionState.jobId} (
              {retentionState.status})
            </div>
          ) : null}
          {migrateState.jobId ? (
            <div className="rounded-xl border border-amber-300/35 bg-amber-900/20 px-3 py-2 text-xs text-amber-200">
              {maintenanceKindLabel(migrateState.kind)} queued: {migrateState.jobId} (
              {migrateState.status})
            </div>
          ) : null}
          {purgeState.jobId ? (
            <div className="rounded-xl border border-rose-300/35 bg-rose-900/20 px-3 py-2 text-xs text-rose-200">
              {maintenanceKindLabel(purgeState.kind)} queued: {purgeState.jobId} ({purgeState.status})
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
