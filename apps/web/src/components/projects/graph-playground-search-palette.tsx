"use client";

import { ArrowUpRight } from "lucide-react";

import type { ProjectGraphNode } from "@/lib/api/types";

type GraphPlaygroundSearchPaletteProps = {
  nodes: ProjectGraphNode[];
  searchQuery: string;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
};

export function GraphPlaygroundSearchPalette({
  nodes,
  searchQuery,
  selectedNodeId,
  onSelectNode,
}: GraphPlaygroundSearchPaletteProps) {
  if (searchQuery.trim().length === 0) {
    return null;
  }

  return (
    <div className="absolute left-0 right-0 top-[calc(100%+0.65rem)] z-20 overflow-hidden rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-bg-card)] shadow-[0_24px_70px_rgba(0,0,0,0.4)]">
      <div className="flex items-center justify-between border-b border-[var(--vr-divider)] px-3.5 py-2.5 text-[11px] uppercase tracking-[0.16em] text-[var(--vr-text-dim)]">
        <span>Search Results</span>
        <span>{nodes.length} matches</span>
      </div>

      {nodes.length === 0 ? (
        <div className="px-4 py-4 text-sm text-[var(--vr-text-dim)]">
          No nodes match <span className="text-[var(--vr-text-main)]">“{searchQuery.trim()}”</span>.
        </div>
      ) : (
        <div className="max-h-[320px] overflow-y-auto p-2">
          {nodes.map((node) => {
            const active = selectedNodeId === node.entityId;
            return (
              <button
                className={`flex w-full items-start justify-between gap-3 rounded-xl px-3 py-2.5 text-left transition ${
                  active
                    ? "bg-[var(--vr-bg-elevated)] text-[var(--vr-text-strong)]"
                    : "text-[var(--vr-text-main)] hover:bg-[var(--vr-bg-elevated)] hover:text-[var(--vr-text-strong)]"
                }`}
                key={node.entityId}
                onClick={() => onSelectNode(node.entityId)}
                type="button"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{node.name}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-[var(--vr-text-dim)]">
                    <span>{node.type}</span>
                    <span>•</span>
                    <span>{node.factCount} facts</span>
                  </div>
                </div>
                <ArrowUpRight className="mt-0.5 size-3.5 shrink-0 text-[var(--vr-text-faint)]" />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
