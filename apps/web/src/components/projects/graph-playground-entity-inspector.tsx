"use client";

import Link from "next/link";
import { Loader2, X } from "lucide-react";

import type { ParsedControlPlaneError } from "@/lib/api/control-plane-error";
import type { GraphViewMode, ProjectGraphEntityDetail, ProjectGraphNode } from "@/lib/api/types";

import { formatDateTime, getParsedErrorText } from "./graph-playground-shared";

type GraphPlaygroundEntityInspectorProps = {
  projectId: string;
  mode: GraphViewMode;
  selectedNode: ProjectGraphNode | null;
  data: ProjectGraphEntityDetail | undefined;
  isLoading: boolean;
  isError: boolean;
  error: ParsedControlPlaneError | null;
  onClear: () => void;
};

export function GraphPlaygroundEntityInspector({
  projectId,
  mode,
  selectedNode,
  data,
  isLoading,
  isError,
  error,
  onClear,
}: GraphPlaygroundEntityInspectorProps) {
  const errorText = getParsedErrorText(error);

  return (
    <aside className="rounded-[24px] border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--vr-text-dim)]">
            Contextual Inspector
          </p>
          <h2 className="mt-2 text-lg font-semibold text-[var(--vr-text-strong)]">
            {selectedNode?.name ?? "Focused Entity"}
          </h2>
          <p className="mt-1 text-sm text-[var(--vr-text-main)]">
            {selectedNode?.type ??
              (mode === "concepts"
                ? "Inspect facts, provenance, and jump deeper into the timeline."
                : "Inspect module-level code citations, symbols, and import relationships.")}
          </p>
        </div>
        <button
          className="inline-flex items-center gap-1 rounded-full border border-[var(--vr-divider)] px-3 py-1.5 text-xs text-[var(--vr-text-dim)] transition hover:text-[var(--vr-text-main)]"
          onClick={onClear}
          type="button"
        >
          <X className="size-3.5" />
          Clear
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-4 py-3 text-sm text-[var(--vr-text-dim)]">
          <Loader2 className="size-4 animate-spin" />
          Loading entity details...
        </div>
      ) : isError ? (
        <div className="rounded-2xl border border-rose-400/25 bg-rose-500/8 px-4 py-4">
          <p className="text-sm text-rose-100">{errorText}</p>
          {error?.requestId ? (
            <p className="mt-2 font-mono text-[11px] text-[var(--vr-text-dim)]">Request ID: {error.requestId}</p>
          ) : null}
        </div>
      ) : data ? (
        <div className="space-y-4">
          <div className="rounded-[20px] border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] p-4">
            <p className="text-lg font-semibold text-[var(--vr-text-strong)]">{data.entity.name}</p>
            <p className="mt-1 text-sm text-[var(--vr-text-dim)]">{data.entity.type}</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-bg-card)] px-3 py-3">
                <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--vr-text-dim)]">
                  {data.mode === "concepts" ? "Facts" : "Symbols"}
                </p>
                <p className="mt-2 text-2xl font-semibold text-[var(--vr-text-strong)]">{data.entity.factCount}</p>
              </div>
              <div className="rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-bg-card)] px-3 py-3">
                <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--vr-text-dim)]">
                  {data.mode === "concepts" ? "Episodes" : "Files"}
                </p>
                <p className="mt-2 text-2xl font-semibold text-[var(--vr-text-strong)]">{data.entity.episodeCount}</p>
              </div>
            </div>
          </div>

          {data.mode === "concepts" ? (
            <>
              <section className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-[var(--vr-text-strong)]">Facts</h3>
                  <span className="text-xs text-[var(--vr-text-dim)]">{data.facts.length} loaded</span>
                </div>
                <div className="max-h-[280px] space-y-2 overflow-y-auto pr-1">
                  {data.facts.map((fact) => (
                    <article
                      className="rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-4 py-3"
                      key={fact.factId}
                    >
                      <p className="text-sm leading-6 text-[var(--vr-text-main)]">{fact.text}</p>
                      <p className="mt-2 text-[11px] text-[var(--vr-text-dim)]">
                        valid_at {formatDateTime(fact.validAt)} • episodes {fact.provenance.episodeIds.length}
                      </p>
                    </article>
                  ))}
                </div>
              </section>

              <section className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-[var(--vr-text-strong)]">Provenance</h3>
                  <span className="text-xs text-[var(--vr-text-dim)]">{data.provenance.length} rows</span>
                </div>
                <div className="max-h-[240px] space-y-2 overflow-y-auto pr-1">
                  {data.provenance.map((episode) => (
                    <article
                      className="rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-bg-card)] px-4 py-3"
                      key={episode.episodeId}
                    >
                      <p className="font-mono text-[10px] text-[var(--vr-graph-cyan)]">{episode.episodeId}</p>
                      <p className="mt-2 text-sm text-[var(--vr-text-main)]">
                        {episode.summary?.trim() || "No summary available."}
                      </p>
                      <p className="mt-2 text-[11px] text-[var(--vr-text-dim)]">
                        {formatDateTime(episode.referenceTime ?? episode.ingestedAt)}
                      </p>
                    </article>
                  ))}
                </div>
              </section>
            </>
          ) : (
            <>
              <section className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-[var(--vr-text-strong)]">Module Files</h3>
                  <span className="text-xs text-[var(--vr-text-dim)]">{data.entity.filePaths?.length ?? 0} files</span>
                </div>
                <div className="max-h-[220px] space-y-2 overflow-y-auto pr-1">
                  {(data.entity.filePaths ?? []).map((filePath) => (
                    <article
                      className="rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-4 py-3"
                      key={filePath}
                    >
                      <p className="font-mono text-xs text-[var(--vr-text-main)]">{filePath}</p>
                    </article>
                  ))}
                </div>
              </section>

              <section className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-[var(--vr-text-strong)]">Related Modules</h3>
                  <span className="text-xs text-[var(--vr-text-dim)]">{data.relatedEntities.length} rows</span>
                </div>
                <div className="max-h-[220px] space-y-2 overflow-y-auto pr-1">
                  {data.relatedEntities.map((entity) => (
                    <article
                      className="rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-bg-card)] px-4 py-3"
                      key={`${entity.relationType}-${entity.entityId}`}
                    >
                      <p className="text-sm font-medium text-[var(--vr-text-strong)]">{entity.name}</p>
                      <p className="mt-1 text-[11px] text-[var(--vr-text-dim)]">
                        {entity.relationType} • {entity.supportCount} files
                      </p>
                    </article>
                  ))}
                </div>
              </section>

              <section className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-[var(--vr-text-strong)]">Top Symbols</h3>
                  <span className="text-xs text-[var(--vr-text-dim)]">{data.symbols.length} symbols</span>
                </div>
                <div className="max-h-[220px] space-y-2 overflow-y-auto pr-1">
                  {data.symbols.map((symbol) => (
                    <article
                      className="rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-4 py-3"
                      key={symbol.entityId}
                    >
                      <p className="text-sm font-medium text-[var(--vr-text-main)]">{symbol.name}</p>
                      <p className="mt-1 text-[11px] text-[var(--vr-text-dim)]">
                        {symbol.kind || "symbol"} • {symbol.filePath || "unknown file"}
                      </p>
                    </article>
                  ))}
                </div>
              </section>

              <section className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-[var(--vr-text-strong)]">Code Citations</h3>
                  <span className="text-xs text-[var(--vr-text-dim)]">{data.citations.length} snippets</span>
                </div>
                <div className="max-h-[240px] space-y-2 overflow-y-auto pr-1">
                  {data.citations.map((citation) => (
                    <article
                      className="rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-bg-card)] px-4 py-3"
                      key={citation.citationId}
                    >
                      <p className="font-mono text-[10px] text-[var(--vr-graph-cyan)]">{citation.filePath || "unknown file"}</p>
                      <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--vr-text-main)]">
                        {citation.snippet?.trim() || "No snippet available."}
                      </p>
                    </article>
                  ))}
                </div>
              </section>
            </>
          )}

          <div className="flex flex-wrap gap-2">
            {data.mode === "concepts" ? (
              <Link
                className="inline-flex rounded-full border border-[var(--vr-divider)] px-4 py-2 text-sm text-[var(--vr-text-main)] transition hover:bg-[var(--vr-bg-elevated)] hover:text-[var(--vr-text-strong)]"
                href={`/projects/${projectId}/timeline`}
              >
                View in Timeline
              </Link>
            ) : null}
            <button
              className="inline-flex cursor-not-allowed rounded-full border border-[var(--vr-divider)] px-4 py-2 text-sm text-[var(--vr-text-dim)] opacity-60"
              disabled
              type="button"
            >
              Delete this entity
            </button>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-4 py-4 text-sm text-[var(--vr-text-dim)]">
          {mode === "concepts"
            ? "Select a node to inspect facts and provenance."
            : "Select a module to inspect files, symbols, and code citations."}
        </div>
      )}
    </aside>
  );
}
