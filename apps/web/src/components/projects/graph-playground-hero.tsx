"use client";

import { Activity, Clock3, GitBranch } from "lucide-react";

import type { GraphViewMode, ProjectGraphPayload } from "@/lib/api/types";
import { getProjectIndexUiState } from "@/lib/project-index-summary";

import { formatDateTime } from "./graph-playground-shared";

type GraphPlaygroundHeroProps = {
  mode: GraphViewMode;
  graphPayload: ProjectGraphPayload | undefined;
  isLoading: boolean;
  isError: boolean;
};

function pillTone(isError: boolean, hasData: boolean) {
  if (isError) {
    return "border-rose-400/30 bg-rose-500/10 text-rose-100";
  }
  if (hasData) {
    return "border-emerald-400/25 bg-emerald-500/10 text-emerald-100";
  }
  return "border-[var(--vr-divider)] bg-[var(--vr-bg-elevated)] text-[var(--vr-text-main)]";
}

export function GraphPlaygroundHero({
  mode,
  graphPayload,
  isLoading,
  isError,
}: GraphPlaygroundHeroProps) {
  const hasData = Boolean(graphPayload);
  const indexUiState = getProjectIndexUiState(graphPayload?.indexSummary);
  const freshnessLabel = graphPayload
    ? `Updated ${formatDateTime(graphPayload.generatedAt)}`
    : isError
      ? "Graph unavailable"
      : isLoading
        ? "Refreshing knowledge map"
        : "Waiting for graph data";

  return (
    <section className="overflow-hidden rounded-[28px] border border-[var(--vr-border)] bg-[var(--vr-bg-card)]">
      <div className="relative overflow-hidden px-6 py-6 sm:px-7 sm:py-7">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(89,199,255,0.16),transparent_34%),radial-gradient(circle_at_top_right,rgba(197,124,255,0.14),transparent_30%),linear-gradient(180deg,rgba(12,14,24,0.96),rgba(10,10,15,0.92))]" />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-[var(--vr-divider)] to-transparent" />

        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.24em] text-[var(--vr-text-dim)]">
              {mode === "concepts" ? "Knowledge Map" : "Code Topology"}
            </p>
            <h1 className="mt-3 text-[30px] font-bold leading-[1.02] text-[var(--vr-text-strong)] sm:text-[34px]">
              {mode === "concepts" ? "Graph Playground" : "Code Topology"}
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--vr-text-main)] sm:text-[15px]">
              {mode === "concepts"
                ? "Explore your project&apos;s memory as a concept graph, with code and file-path entities removed from the default view."
                : "Inspect module-level imports without turning file paths into top-level nodes. Files and symbols stay in the inspector."}
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 lg:min-w-[520px]">
            <div className="rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-4 py-3">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-[var(--vr-text-dim)]">
                <Activity className="size-3.5 text-[var(--vr-graph-cyan)]" />
                Nodes
              </div>
              <p className="mt-2 text-2xl font-semibold text-[var(--vr-text-strong)]">
                {graphPayload ? graphPayload.entityCount.toLocaleString() : "—"}
              </p>
            </div>

            <div className="rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-4 py-3">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-[var(--vr-text-dim)]">
                <GitBranch className="size-3.5 text-[var(--vr-graph-indigo)]" />
                Relationships
              </div>
              <p className="mt-2 text-2xl font-semibold text-[var(--vr-text-strong)]">
                {graphPayload ? graphPayload.relationshipCount.toLocaleString() : "—"}
              </p>
            </div>

            <div className={`rounded-2xl border px-4 py-3 ${pillTone(isError, hasData)}`}>
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.16em]">
                <Clock3 className="size-3.5" />
                {mode === "code" ? "Index Status" : "Freshness"}
              </div>
              <p className="mt-2 text-sm font-medium leading-5">
                {mode === "code" ? indexUiState.badgeLabel : freshnessLabel}
              </p>
              {mode === "code" ? (
                <p className="mt-1 text-xs leading-5 opacity-90">{indexUiState.body}</p>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
