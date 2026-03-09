"use client";

import { Download, Filter, RefreshCw, Search, X } from "lucide-react";

import type { GraphViewMode, ProjectGraphNode, ProjectGraphPayload } from "@/lib/api/types";

import { colorForEntityType } from "./graph-playground-shared";
import { GraphPlaygroundSearchPalette } from "./graph-playground-search-palette";

type GraphPlaygroundControlRailProps = {
  projectId: string;
  mode: GraphViewMode;
  graphPayload: ProjectGraphPayload | undefined;
  searchQuery: string;
  selectedNodeId: string | null;
  availableTypes: string[];
  selectedTypeSet: Set<string>;
  showLast30Days: boolean;
  showEdgeLabels: boolean;
  searchResultNodes: ProjectGraphNode[];
  isRefreshing: boolean;
  onSearchChange: (value: string) => void;
  onSelectNode: (nodeId: string) => void;
  onToggleType: (type: string) => void;
  onClearTypes: () => void;
  onViewModeChange: (mode: GraphViewMode) => void;
  onToggleLast30Days: () => void;
  onToggleEdgeLabels: () => void;
  onRefresh: () => void;
  onExportPng: () => void;
  onExportJson: () => void;
};

function chipClassName(active: boolean) {
  if (active) {
    return "border-transparent bg-[var(--vr-bg-elevated)] text-[var(--vr-text-strong)] shadow-[inset_0_0_0_1px_rgba(123,140,255,0.25)]";
  }
  return "border-[var(--vr-divider)] bg-transparent text-[var(--vr-text-dim)] hover:border-[var(--vr-border-strong)] hover:text-[var(--vr-text-main)]";
}

function toggleClassName(active: boolean) {
  if (active) {
    return "border-[var(--vr-border-strong)] bg-[var(--vr-bg-elevated)] text-[var(--vr-text-strong)] shadow-[inset_0_0_0_1px_rgba(123,140,255,0.18)]";
  }
  return "border-[var(--vr-divider)] bg-transparent text-[var(--vr-text-main)] hover:bg-[var(--vr-bg-elevated)]";
}

export function GraphPlaygroundControlRail({
  projectId,
  mode,
  graphPayload,
  searchQuery,
  selectedNodeId,
  availableTypes,
  selectedTypeSet,
  showLast30Days,
  showEdgeLabels,
  searchResultNodes,
  isRefreshing,
  onSearchChange,
  onSelectNode,
  onToggleType,
  onClearTypes,
  onViewModeChange,
  onToggleLast30Days,
  onToggleEdgeLabels,
  onRefresh,
  onExportPng,
  onExportJson,
}: GraphPlaygroundControlRailProps) {
  return (
    <section className="rounded-[22px] border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-4 sm:p-[18px]">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2.5 xl:flex-nowrap">
          <div className="flex shrink-0 items-center gap-2 rounded-full border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] p-1">
            {(["concepts", "code"] as const).map((item) => {
              const active = item === mode;
              return (
                <button
                  className={`rounded-full px-3 py-2 text-xs font-medium transition ${
                    active
                      ? "bg-[var(--vr-bg-elevated)] text-[var(--vr-text-strong)] shadow-[inset_0_0_0_1px_rgba(123,140,255,0.25)]"
                      : "text-[var(--vr-text-dim)] hover:text-[var(--vr-text-main)]"
                  }`}
                  key={item}
                  onClick={() => onViewModeChange(item)}
                  type="button"
                >
                  {item === "concepts" ? "Concept graph" : "Code topology"}
                </button>
              );
            })}
          </div>
          <div className="min-w-[280px] flex-1">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--vr-text-dim)]">
              Explore Controls
            </p>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[var(--vr-text-faint)]" />
              <input
                className="w-full rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-bg-input)] py-2.5 pl-10 pr-4 text-sm text-[var(--vr-text-strong)] outline-none transition focus:border-[var(--vr-border-strong)]"
                onChange={(event) => onSearchChange(event.target.value)}
                placeholder={mode === "concepts" ? "Search concepts, entity types, or IDs" : "Search modules"}
                value={searchQuery}
              />
              <GraphPlaygroundSearchPalette
                nodes={searchResultNodes}
                onSelectNode={onSelectNode}
                primaryCountLabel={graphPayload?.nodePrimaryLabel ?? "Facts"}
                searchQuery={searchQuery}
                selectedNodeId={selectedNodeId}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 xl:ml-auto xl:pt-6">
            <button
              aria-pressed={showLast30Days}
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium transition ${toggleClassName(showLast30Days)}`}
              onClick={onToggleLast30Days}
              hidden={mode !== "concepts"}
              type="button"
            >
              <span>30d</span>
              <span className="text-[10px] uppercase tracking-[0.14em] text-[var(--vr-text-dim)]">
                {showLast30Days ? "On" : "Off"}
              </span>
            </button>
            <button
              aria-pressed={showEdgeLabels}
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium transition ${toggleClassName(showEdgeLabels)}`}
              onClick={onToggleEdgeLabels}
              type="button"
            >
              <span>Labels</span>
              <span className="text-[10px] uppercase tracking-[0.14em] text-[var(--vr-text-dim)]">
                {showEdgeLabels ? "On" : "Off"}
              </span>
            </button>
            <button
              className="inline-flex items-center justify-center gap-2 rounded-full border border-[var(--vr-divider)] bg-[var(--vr-bg-elevated)] px-3.5 py-2 text-xs font-medium text-[var(--vr-text-main)] transition hover:text-[var(--vr-text-strong)] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isRefreshing}
              onClick={onRefresh}
              type="button"
            >
              <RefreshCw className={`size-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
              Refresh
            </button>
            <button
              className="inline-flex items-center justify-center gap-2 rounded-full border border-[var(--vr-divider)] bg-[var(--vr-bg-elevated)] px-3.5 py-2 text-xs font-medium text-[var(--vr-text-main)] transition hover:text-[var(--vr-text-strong)] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!graphPayload}
              onClick={onExportPng}
              type="button"
            >
              <Download className="size-3.5" />
              PNG
            </button>
            <button
              className="inline-flex items-center justify-center gap-2 rounded-full border border-[var(--vr-divider)] bg-[var(--vr-bg-elevated)] px-3.5 py-2 text-xs font-medium text-[var(--vr-text-main)] transition hover:text-[var(--vr-text-strong)] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!graphPayload}
              onClick={onExportJson}
              type="button"
            >
              <Download className="size-3.5" />
              JSON
            </button>
          </div>
        </div>

        {mode === "concepts" ? (
          <div className="rounded-[18px] border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-3 py-2.5">
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="flex shrink-0 items-center gap-2 pr-1">
              <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--vr-text-dim)]">
                <Filter className="size-3.5" />
                Entity Types
              </p>
              {selectedTypeSet.size > 0 ? (
                <button
                  className="inline-flex items-center gap-1 rounded-full border border-[var(--vr-divider)] px-2 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-[var(--vr-text-dim)] transition hover:border-[var(--vr-border-strong)] hover:text-[var(--vr-text-main)]"
                  onClick={onClearTypes}
                  type="button"
                >
                  <X className="size-3" />
                  Clear
                </button>
              ) : null}
            </div>

            {availableTypes.length === 0 ? (
              <p className="text-xs text-[var(--vr-text-dim)]">No entity types available yet.</p>
            ) : (
              <div className="vr-chip-rail flex min-w-0 flex-1 gap-2 overflow-x-auto pb-0.5">
                {availableTypes.map((type) => {
                  const active = selectedTypeSet.has(type);
                  return (
                    <button
                      aria-pressed={active}
                      className={`shrink-0 inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition ${chipClassName(active)}`}
                      key={type}
                      onClick={() => onToggleType(type)}
                      type="button"
                    >
                      <span
                        className="size-2 rounded-full"
                        style={{ backgroundColor: colorForEntityType(type) }}
                      />
                      {type}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          </div>
        ) : (
          <div className="rounded-[18px] border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-3 py-2.5 text-sm text-[var(--vr-text-dim)]">
            Code topology renders modules only. File paths and symbols stay in the inspector so renames and moves do not dominate the canvas.
          </div>
        )}

        <p className="text-[11px] text-[var(--vr-text-dim)]">
          Exports reflect the current {mode === "concepts" ? "concept" : "code"} graph slice for{" "}
          <span className="text-[var(--vr-text-main)]">{projectId}</span>.
        </p>
      </div>
    </section>
  );
}
