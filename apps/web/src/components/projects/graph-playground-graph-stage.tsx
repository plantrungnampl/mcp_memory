"use client";

import Link from "next/link";
import {
  Loader2,
  RefreshCw,
} from "lucide-react";
import {
  SigmaContainer,
  useLoadGraph,
  useRegisterEvents,
  useSetSettings,
  useSigma,
} from "@react-sigma/core";
import type { Dispatch, SetStateAction } from "react";
import { useEffect, useRef, useState } from "react";
import type { Sigma } from "sigma";
import type Graph from "graphology";

import type { ParsedControlPlaneError } from "@/lib/api/control-plane-error";
import type { ProjectGraphPayload } from "@/lib/api/types";

import {
  type HoverEdgeState,
  type HoverNodeState,
  type SigmaEdgeAttributes,
  type SigmaNodeAttributes,
  formatDateTime,
} from "./graph-playground-shared";

function emptyStateCopy(payload: ProjectGraphPayload | undefined): { eyebrow: string; title: string; body: string } {
  if (!payload) {
    return {
      eyebrow: "No graph data yet",
      title: "There is no data yet to build this map",
      body: "Save memory or run indexing to populate this project graph.",
    };
  }
  if (payload.mode === "concepts" && payload.emptyReason === "concepts_unavailable") {
    return {
      eyebrow: "No concept graph yet",
      title: "Only code-like entities are available right now",
      body: "Switch to Code Topology to inspect modules. Concept graph stays empty until memory contains domain-level entities.",
    };
  }
  if (payload.mode === "code" && payload.emptyReason === "no_ready_index") {
    return {
      eyebrow: "Code topology unavailable",
      title: "There is no READY code index snapshot yet",
      body: "Run indexing first, then reopen Code Topology.",
    };
  }
  return {
    eyebrow: payload.mode === "code" ? "No code topology yet" : "No graph data yet",
    title: payload.mode === "code" ? "There is no module graph to render yet" : "There is no memory yet to build this map",
    body:
      payload.mode === "code"
        ? "No module import relationships were found in the latest READY snapshot."
        : "Chat with the AI, create more episodes, or refresh this panel after the runtime finishes ingesting new data.",
  };
}

type GraphPlaygroundGraphStageProps = {
  projectId: string;
  graphPayload: ProjectGraphPayload | undefined;
  graphologyGraph: Graph<SigmaNodeAttributes, SigmaEdgeAttributes>;
  graphError: ParsedControlPlaneError | null;
  graphErrorText: string;
  showGraphDependencyHint: boolean;
  isLoading: boolean;
  isFetching: boolean;
  showEdgeLabels: boolean;
  selectedTypes: Set<string>;
  searchQuery: string;
  searchMatches: Set<string>;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
  onRequestRefresh: () => void;
  onSigmaInstanceChange: Dispatch<SetStateAction<Sigma<SigmaNodeAttributes, SigmaEdgeAttributes> | null>>;
};

function SigmaGraphLoader({ graph }: { graph: Graph<SigmaNodeAttributes, SigmaEdgeAttributes> }) {
  const loadGraph = useLoadGraph<SigmaNodeAttributes, SigmaEdgeAttributes>();
  useEffect(() => {
    loadGraph(graph);
  }, [graph, loadGraph]);
  return null;
}

function SigmaReady({
  onReady,
}: {
  onReady: Dispatch<SetStateAction<Sigma<SigmaNodeAttributes, SigmaEdgeAttributes> | null>>;
}) {
  const sigma = useSigma<SigmaNodeAttributes, SigmaEdgeAttributes>();
  useEffect(() => {
    onReady(sigma);
    return () => onReady(null);
  }, [onReady, sigma]);
  return null;
}

function SigmaSelectionFocus({ selectedNodeId }: { selectedNodeId: string | null }) {
  const sigma = useSigma<SigmaNodeAttributes, SigmaEdgeAttributes>();

  useEffect(() => {
    if (!selectedNodeId) {
      return;
    }

    const graph = sigma.getGraph();
    if (!graph.hasNode(selectedNodeId)) {
      return;
    }

    const nodeDisplayData = sigma.getNodeDisplayData(selectedNodeId);
    if (!nodeDisplayData) {
      return;
    }

    sigma.getCamera().animate(
      { x: nodeDisplayData.x, y: nodeDisplayData.y, ratio: 0.62 },
      { duration: 420 },
    );
  }, [selectedNodeId, sigma]);

  return null;
}

function SigmaInteractiveSettings({
  hoveredNode,
  hoveredEdge,
  selectedNode,
  selectedTypes,
  searchMatches,
  searchQuery,
  showEdgeLabels,
}: {
  hoveredNode: string | null;
  hoveredEdge: string | null;
  selectedNode: string | null;
  selectedTypes: Set<string>;
  searchMatches: Set<string>;
  searchQuery: string;
  showEdgeLabels: boolean;
}) {
  const setSettings = useSetSettings<SigmaNodeAttributes, SigmaEdgeAttributes>();
  const sigma = useSigma<SigmaNodeAttributes, SigmaEdgeAttributes>();

  useEffect(() => {
    const graph = sigma.getGraph();
    const searchActive = searchQuery.trim().length > 0;
    const hasFocusContext =
      searchActive ||
      hoveredNode !== null ||
      hoveredEdge !== null ||
      selectedNode !== null;

    setSettings({
      renderEdgeLabels: showEdgeLabels,
      enableEdgeEvents: true,
      defaultEdgeType: "line",
      labelRenderedSizeThreshold: 16,
      labelDensity: 0.05,
      labelGridCellSize: 110,
      nodeReducer: (node, data) => {
        if (selectedTypes.size > 0 && !selectedTypes.has(String(data.entityType))) {
          return { ...data, hidden: true };
        }

        if (!hasFocusContext) {
          return { ...data, hidden: false };
        }

        const searchMatch = !searchActive || searchMatches.has(node);
        const connectedToHover =
          hoveredNode !== null &&
          graph.hasNode(hoveredNode) &&
          node !== hoveredNode &&
          graph.areNeighbors(node, hoveredNode);
        const connectedToSelection =
          selectedNode !== null &&
          graph.hasNode(selectedNode) &&
          node !== selectedNode &&
          graph.areNeighbors(node, selectedNode);
        const emphasized =
          node === hoveredNode ||
          node === selectedNode ||
          connectedToHover ||
          connectedToSelection ||
          (searchActive && searchMatch);

        return {
          ...data,
          color: emphasized
            ? data.color
            : searchActive && !searchMatch
              ? "rgba(88, 97, 122, 0.18)"
              : "rgba(98, 106, 126, 0.34)",
          size:
            node === hoveredNode
              ? data.size * 1.16
              : node === selectedNode
                ? data.size * 1.12
                : data.size,
          hidden: false,
        };
      },
      edgeReducer: (edge, data) => {
        const [source, target] = graph.extremities(edge);
        const sourceType = String(graph.getNodeAttribute(source, "entityType"));
        const targetType = String(graph.getNodeAttribute(target, "entityType"));
        if (selectedTypes.size > 0 && (!selectedTypes.has(sourceType) || !selectedTypes.has(targetType))) {
          return { ...data, hidden: true };
        }
        if (!hasFocusContext) {
          return { ...data, hidden: false };
        }

        const searchConnected = !searchActive || searchMatches.has(source) || searchMatches.has(target);
        const hovered =
          edge === hoveredEdge ||
          (hoveredNode !== null && (source === hoveredNode || target === hoveredNode));
        const selected =
          selectedNode !== null && (source === selectedNode || target === selectedNode);
        const emphasized = hovered || selected;

        return {
          ...data,
          color: emphasized
            ? "rgba(226, 236, 255, 0.92)"
            : searchConnected
              ? "rgba(123, 140, 255, 0.24)"
              : "rgba(77, 84, 107, 0.12)",
          size: emphasized ? Math.max(1.7, data.size + 0.7) : data.size,
          hidden: false,
        };
      },
    });
    sigma.refresh();
  }, [
    hoveredEdge,
    hoveredNode,
    searchMatches,
    searchQuery,
    selectedNode,
    selectedTypes,
    setSettings,
    showEdgeLabels,
    sigma,
  ]);

  return null;
}

function SigmaEventBridge({
  onNodeHover,
  onNodeLeave,
  onEdgeHover,
  onEdgeLeave,
  onSelectNode,
}: {
  onNodeHover: (state: HoverNodeState) => void;
  onNodeLeave: () => void;
  onEdgeHover: (state: HoverEdgeState) => void;
  onEdgeLeave: () => void;
  onSelectNode: (nodeId: string | null) => void;
}) {
  const registerEvents = useRegisterEvents<SigmaNodeAttributes, SigmaEdgeAttributes>();
  const sigma = useSigma<SigmaNodeAttributes, SigmaEdgeAttributes>();

  useEffect(() => {
    registerEvents({
      enterNode: ({ node, event }) => onNodeHover({ nodeId: node, x: event.x, y: event.y }),
      leaveNode: () => onNodeLeave(),
      enterEdge: ({ edge, event }) => onEdgeHover({ edgeId: edge, x: event.x, y: event.y }),
      leaveEdge: () => onEdgeLeave(),
      clickNode: ({ node }) => onSelectNode(node),
      clickStage: () => onSelectNode(null),
      doubleClickNode: ({ node }) => {
        const data = sigma.getNodeDisplayData(node);
        if (!data) {
          return;
        }
        sigma.getCamera().animate(
          { x: data.x, y: data.y, ratio: 0.5 },
          { duration: 400 },
        );
      },
    });
  }, [onEdgeHover, onEdgeLeave, onNodeHover, onNodeLeave, onSelectNode, registerEvents, sigma]);

  return null;
}

export function GraphPlaygroundGraphStage({
  projectId,
  graphPayload,
  graphologyGraph,
  graphError,
  graphErrorText,
  showGraphDependencyHint,
  isLoading,
  isFetching,
  showEdgeLabels,
  selectedTypes,
  searchQuery,
  searchMatches,
  selectedNodeId,
  onSelectNode,
  onRequestRefresh,
  onSigmaInstanceChange,
}: GraphPlaygroundGraphStageProps) {
  const [hoveredNodeState, setHoveredNodeState] = useState<HoverNodeState | null>(null);
  const [hoveredEdgeState, setHoveredEdgeState] = useState<HoverEdgeState | null>(null);
  const [sigmaCanvasUnavailable, setSigmaCanvasUnavailable] = useState(false);
  const [canMountSigma, setCanMountSigma] = useState(false);
  const sigmaMountTargetRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const target = sigmaMountTargetRef.current;
    if (!target) {
      return;
    }

    let frameId: number | null = null;

    const updateCanMount = () => {
      const currentTarget = sigmaMountTargetRef.current;
      if (!currentTarget) {
        setCanMountSigma(false);
        return;
      }
      const rect = currentTarget.getBoundingClientRect();
      const style = window.getComputedStyle(currentTarget);
      const hasMeasurableSize = rect.width > 0 && rect.height > 0;
      const hasRenderableLayout =
        currentTarget.isConnected && style.display !== "none" && style.visibility !== "hidden";

      setCanMountSigma(hasMeasurableSize && hasRenderableLayout);
    };

    const scheduleUpdate = () => {
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId);
      }
      frameId = window.requestAnimationFrame(() => {
        frameId = null;
        updateCanMount();
      });
    };

    scheduleUpdate();

    if (typeof ResizeObserver === "undefined") {
      return () => {
        if (frameId !== null) {
          window.cancelAnimationFrame(frameId);
        }
      };
    }

    const observer = new ResizeObserver(scheduleUpdate);
    observer.observe(target);
    return () => {
      observer.disconnect();
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, [graphPayload?.nodes.length, selectedNodeId]);

  const hoveredNode =
    hoveredNodeState && graphPayload
      ? graphPayload.nodes.find((node) => node.entityId === hoveredNodeState.nodeId) ?? null
      : null;
  const hoveredEdge =
    hoveredEdgeState && graphPayload
      ? graphPayload.edges.find((edge) => edge.edgeId === hoveredEdgeState.edgeId) ?? null
      : null;

  const sigmaStatusLabel = graphPayload
    ? `${graphPayload.entityCount.toLocaleString()} nodes • ${graphPayload.relationshipCount.toLocaleString()} relationships`
    : graphError
      ? "Knowledge map unavailable"
      : "Preparing knowledge map";

  return (
    <article className="vr-graph-stage relative min-h-[720px] overflow-hidden rounded-[28px] border border-[var(--vr-border)]">
      <div className="absolute inset-x-0 top-0 z-10 flex flex-wrap items-start justify-between gap-3 p-4">
        <div className="rounded-full border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-3 py-1.5 text-[11px] font-medium text-[var(--vr-text-main)] backdrop-blur-md">
          {graphPayload?.mode === "code" ? "Module topology • Double click to focus" : "Drag to explore • Double click to zoom"}
        </div>
        <div className="rounded-full border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-3 py-1.5 text-[11px] font-medium text-[var(--vr-text-main)] backdrop-blur-md">
          {sigmaStatusLabel}
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-full min-h-[720px] items-center justify-center gap-2 text-sm text-[var(--vr-text-dim)]">
          <Loader2 className="size-4 animate-spin" />
          Loading graph...
        </div>
      ) : graphError ? (
        <div className="flex h-full min-h-[720px] items-center justify-center p-6">
          <div className="w-full max-w-xl rounded-[24px] border border-rose-400/20 bg-[rgba(36,12,18,0.82)] p-6 text-left backdrop-blur-md">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-rose-200/80">
              {graphError.status === 503 ? "Graph dependency unavailable" : "Graph request failed"}
            </p>
            <h2 className="mt-2 text-xl font-semibold text-[var(--vr-text-strong)]">
              {graphError.status === 503 ? "Graph runtime is temporarily unavailable" : "Unable to load the graph"}
            </h2>
            <p className="mt-3 text-sm leading-6 text-[var(--vr-text-main)]">{graphErrorText}</p>

            {graphError.requestId ? (
              <p className="mt-3 font-mono text-xs text-[var(--vr-text-dim)]">
                Request ID: {graphError.requestId}
              </p>
            ) : null}

            {showGraphDependencyHint ? (
              <div className="mt-4 rounded-2xl border border-amber-300/25 bg-amber-400/10 px-4 py-3 text-sm text-amber-100">
                <p>Local runtime hint: start FalkorDB and Redis with <code>docker compose -f ops/docker-compose.runtime.yml up -d</code>.</p>
                <p className="mt-2">Then restart the MCP API process and refresh this panel.</p>
              </div>
            ) : null}

            <div className="mt-5 flex flex-wrap gap-2">
              <button
                className="inline-flex items-center gap-2 rounded-full border border-[var(--vr-divider)] px-4 py-2 text-sm text-[var(--vr-text-main)] transition hover:bg-[var(--vr-bg-elevated)] hover:text-[var(--vr-text-strong)]"
                onClick={onRequestRefresh}
                type="button"
              >
                <RefreshCw className={`size-4 ${isFetching ? "animate-spin" : ""}`} />
                Refresh Graph
              </button>
              <Link
                className="inline-flex items-center rounded-full border border-[var(--vr-divider)] px-4 py-2 text-sm text-[var(--vr-text-main)] transition hover:bg-[var(--vr-bg-elevated)] hover:text-[var(--vr-text-strong)]"
                href={`/projects/${projectId}/timeline`}
              >
                View Timeline
              </Link>
            </div>
          </div>
        </div>
      ) : graphPayload && graphPayload.nodes.length > 0 ? (
        <>
          <div className="absolute inset-x-0 bottom-0 z-10 flex flex-wrap items-center gap-2 p-4">
            {selectedNodeId ? (
              <div className="rounded-full border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-3 py-1.5 text-[11px] text-[var(--vr-text-main)] backdrop-blur-md">
                Focused entity inspector is open
              </div>
            ) : null}
            {searchQuery.trim().length > 0 ? (
              <div className="rounded-full border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-3 py-1.5 text-[11px] text-[var(--vr-text-main)] backdrop-blur-md">
                Search active: {searchMatches.size} matching nodes
              </div>
            ) : null}
          </div>

          <div className="w-full" ref={sigmaMountTargetRef} style={{ height: 720, minHeight: 720 }}>
            {canMountSigma ? (
              <SigmaContainer<SigmaNodeAttributes, SigmaEdgeAttributes>
                settings={{
                  allowInvalidContainer: true,
                  renderLabels: true,
                  renderEdgeLabels: showEdgeLabels,
                  labelDensity: 0.05,
                  labelGridCellSize: 110,
                  labelRenderedSizeThreshold: 16,
                  defaultNodeColor: "#7B8CFF",
                }}
                style={{ height: 720, minHeight: 720, width: "100%" }}
              >
                <SigmaReady onReady={onSigmaInstanceChange} />
                <SigmaGraphLoader graph={graphologyGraph} />
                <CanvasHealth sigmaMountReady={canMountSigma} setSigmaCanvasUnavailable={setSigmaCanvasUnavailable} />
                <SigmaSelectionFocus selectedNodeId={selectedNodeId} />
                <SigmaInteractiveSettings
                  hoveredEdge={hoveredEdgeState?.edgeId ?? null}
                  hoveredNode={hoveredNodeState?.nodeId ?? null}
                  searchMatches={searchMatches}
                  searchQuery={searchQuery}
                  selectedNode={selectedNodeId}
                  selectedTypes={selectedTypes}
                  showEdgeLabels={showEdgeLabels}
                />
                <SigmaEventBridge
                  onEdgeHover={setHoveredEdgeState}
                  onEdgeLeave={() => setHoveredEdgeState(null)}
                  onNodeHover={setHoveredNodeState}
                  onNodeLeave={() => setHoveredNodeState(null)}
                  onSelectNode={onSelectNode}
                />
              </SigmaContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-[var(--vr-text-dim)]">
                Preparing graph canvas...
              </div>
            )}
          </div>

          {sigmaCanvasUnavailable ? (
            <div className="absolute inset-x-0 bottom-16 z-10 px-4">
              <div className="rounded-2xl border border-amber-300/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-100">
                Graph canvas is not ready yet. Try <span className="font-medium">Refresh Graph</span> or resize the window.
              </div>
            </div>
          ) : null}

          {hoveredNode && hoveredNodeState ? (
            <div
              className="pointer-events-none absolute z-20 max-w-sm rounded-2xl border border-[var(--vr-divider)] bg-[rgba(12,15,24,0.94)] px-4 py-3 text-xs shadow-[0_22px_60px_rgba(0,0,0,0.46)] backdrop-blur-md"
              style={{
                left: hoveredNodeState.x + 14,
                top: hoveredNodeState.y + 14,
              }}
            >
              <p className="mb-1 text-sm font-semibold text-[var(--vr-text-strong)]">{hoveredNode.name}</p>
              <p className="mb-2 text-[10px] uppercase tracking-[0.08em] text-[var(--vr-text-dim)]">{hoveredNode.type}</p>
              <div className="space-y-1.5 text-[var(--vr-text-main)]">
                {hoveredNode.hoverText.slice(0, 3).map((item, index) => (
                  <p key={`${hoveredNode.entityId}-${index}`}>
                    {item.text}
                    <span className="ml-1 text-[var(--vr-text-faint)]">({formatDateTime(item.referenceTime)})</span>
                  </p>
                ))}
              </div>
            </div>
          ) : null}

          {!hoveredNode && hoveredEdge && hoveredEdgeState ? (
            <div
              className="pointer-events-none absolute z-20 max-w-sm rounded-2xl border border-[var(--vr-divider)] bg-[rgba(12,15,24,0.94)] px-4 py-3 text-xs shadow-[0_22px_60px_rgba(0,0,0,0.46)] backdrop-blur-md"
              style={{
                left: hoveredEdgeState.x + 14,
                top: hoveredEdgeState.y + 14,
              }}
            >
              <p className="font-semibold text-[var(--vr-text-strong)]">
                Relationship: {hoveredEdge.type}
              </p>
              <p className="mt-1 text-[var(--vr-text-main)]">{hoveredEdge.label}</p>
            </div>
          ) : null}
        </>
      ) : (
        <div className="flex h-full min-h-[720px] items-center justify-center px-6 text-center">
          <div className="max-w-lg rounded-[24px] border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-6 py-8">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--vr-text-dim)]">
              {emptyStateCopy(graphPayload).eyebrow}
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-[var(--vr-text-strong)]">
              {emptyStateCopy(graphPayload).title}
            </h2>
            <p className="mt-3 text-sm leading-6 text-[var(--vr-text-main)]">
              {emptyStateCopy(graphPayload).body}
            </p>
          </div>
        </div>
      )}
    </article>
  );
}

function CanvasHealth({
  sigmaMountReady,
  setSigmaCanvasUnavailable,
}: {
  sigmaMountReady: boolean;
  setSigmaCanvasUnavailable: Dispatch<SetStateAction<boolean>>;
}) {
  const sigma = useSigma<SigmaNodeAttributes, SigmaEdgeAttributes>();

  useEffect(() => {
    if (!sigmaMountReady) {
      setSigmaCanvasUnavailable(false);
      return;
    }

    const timeoutId = window.setTimeout(() => {
      const canvases = Object.values(sigma.getCanvases());
      const hasVisibleCanvas = canvases.some((canvas) => canvas.width > 8 && canvas.height > 8);
      setSigmaCanvasUnavailable(!hasVisibleCanvas);
    }, 450);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [setSigmaCanvasUnavailable, sigma, sigmaMountReady]);

  return null;
}
