"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";
import type { Sigma } from "sigma";

import type {
  ProjectGraphEntityDetail,
  ProjectGraphPayload,
  ProjectTimelinePayload,
} from "@/lib/api/types";
import { fetchQueryJson, normalizeQueryError } from "@/lib/query/fetch";
import { projectQueryKeys } from "@/lib/query/keys";

import { GraphPlaygroundControlRail } from "./graph-playground-control-rail";
import { GraphPlaygroundEntityInspector } from "./graph-playground-entity-inspector";
import { GraphPlaygroundGraphStage } from "./graph-playground-graph-stage";
import { GraphPlaygroundHero } from "./graph-playground-hero";
import { GraphPlaygroundRecentThreads } from "./graph-playground-recent-threads";
import {
  type SigmaEdgeAttributes,
  type SigmaNodeAttributes,
  createGraphologyGraph,
  downloadJson,
  downloadPngFromSigma,
  getParsedErrorText,
  isGraphDependencyUnavailable,
} from "./graph-playground-shared";

type GraphPlaygroundPanelProps = {
  projectId: string;
};

const DESKTOP_MEDIA_QUERY = "(min-width: 1024px)";

function getIsDesktopViewport(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return window.matchMedia(DESKTOP_MEDIA_QUERY).matches;
}

function matchesSearch(node: ProjectGraphPayload["nodes"][number], searchLower: string): boolean {
  return (
    node.name.toLowerCase().includes(searchLower) ||
    node.type.toLowerCase().includes(searchLower) ||
    node.entityId.toLowerCase().includes(searchLower)
  );
}

export function GraphPlaygroundPanel({ projectId }: GraphPlaygroundPanelProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const deferredSearchQuery = useDeferredValue(searchQuery);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [showLast30Days, setShowLast30Days] = useState(true);
  const [showEdgeLabels, setShowEdgeLabels] = useState(false);
  const [maxNodes, setMaxNodes] = useState(500);
  const [maxEdges, setMaxEdges] = useState(1200);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [sigmaInstance, setSigmaInstance] = useState<Sigma<SigmaNodeAttributes, SigmaEdgeAttributes> | null>(null);
  const [isDesktopViewport, setIsDesktopViewport] = useState(getIsDesktopViewport);

  useEffect(() => {
    const mediaQueryList = window.matchMedia(DESKTOP_MEDIA_QUERY);
    const handleChange = (event: MediaQueryListEvent) => {
      setIsDesktopViewport(event.matches);
    };

    mediaQueryList.addEventListener("change", handleChange);

    return () => {
      mediaQueryList.removeEventListener("change", handleChange);
    };
  }, []);

  const graphQuery = useQuery({
    queryKey: projectQueryKeys.graph(projectId, {
      last30Days: showLast30Days,
      maxNodes,
      maxEdges,
    }),
    queryFn: () =>
      fetchQueryJson<ProjectGraphPayload>(
        `/api/projects/${projectId}/graph?max_nodes=${maxNodes}&max_edges=${maxEdges}${showLast30Days ? "&last_days=30" : ""}`,
      ),
    refetchInterval: 10_000,
    staleTime: 5_000,
  });

  const timelineQuery = useQuery({
    queryKey: projectQueryKeys.graphTimeline(projectId),
    queryFn: () =>
      fetchQueryJson<ProjectTimelinePayload>(`/api/projects/${projectId}/timeline?limit=30&offset=0`),
    refetchInterval: 10_000,
    staleTime: 5_000,
  });

  const graphPayload = graphQuery.data;
  const graphError = graphQuery.isError ? normalizeQueryError(graphQuery.error) : null;
  const graphErrorText = getParsedErrorText(graphError);
  const showGraphDependencyHint = isGraphDependencyUnavailable(graphError);
  const timelineError = timelineQuery.isError ? normalizeQueryError(timelineQuery.error) : null;

  const selectedTypeSet = useMemo(() => new Set(selectedTypes), [selectedTypes]);
  const searchLower = deferredSearchQuery.trim().toLowerCase();

  const selectedNodeIdSafe =
    selectedNodeId && graphPayload?.nodes.some((node) => node.entityId === selectedNodeId)
      ? selectedNodeId
      : null;

  const entityDetailQuery = useQuery({
    queryKey: projectQueryKeys.graphEntityDetail(projectId, selectedNodeIdSafe),
    queryFn: () =>
      fetchQueryJson<ProjectGraphEntityDetail>(
        `/api/projects/${projectId}/graph/entities/${encodeURIComponent(selectedNodeIdSafe ?? "")}?fact_limit=120&episode_limit=120&max_facts_scan=5000`,
      ),
    enabled: selectedNodeIdSafe !== null,
    refetchInterval: 10_000,
    staleTime: 5_000,
  });
  const entityDetailError = entityDetailQuery.isError
    ? normalizeQueryError(entityDetailQuery.error)
    : null;

  const availableTypes = useMemo(
    () => Array.from(new Set((graphPayload?.nodes ?? []).map((node) => node.type))).sort((a, b) => a.localeCompare(b)),
    [graphPayload],
  );

  const searchMatches = useMemo(() => {
    const matches = new Set<string>();
    if (!graphPayload || searchLower.length === 0) {
      return matches;
    }

    for (const node of graphPayload.nodes) {
      if (selectedTypeSet.size > 0 && !selectedTypeSet.has(node.type)) {
        continue;
      }
      if (matchesSearch(node, searchLower)) {
        matches.add(node.entityId);
      }
    }
    return matches;
  }, [graphPayload, searchLower, selectedTypeSet]);

  const searchResultNodes = useMemo(() => {
    if (!graphPayload || searchLower.length === 0) {
      return [];
    }

    return graphPayload.nodes
      .filter((node) => searchMatches.has(node.entityId))
      .sort((left, right) => right.factCount - left.factCount)
      .slice(0, 8);
  }, [graphPayload, searchLower, searchMatches]);

  const mobileNodes = useMemo(() => {
    const nodes = graphPayload?.nodes ?? [];
    return nodes
      .filter((node) => {
        if (selectedTypeSet.size > 0 && !selectedTypeSet.has(node.type)) {
          return false;
        }
        if (searchLower.length > 0) {
          return searchMatches.has(node.entityId);
        }
        return true;
      })
      .sort((left, right) => right.factCount - left.factCount)
      .slice(0, 120);
  }, [graphPayload, searchLower, searchMatches, selectedTypeSet]);

  const selectedNode =
    selectedNodeIdSafe && graphPayload
      ? graphPayload.nodes.find((node) => node.entityId === selectedNodeIdSafe) ?? null
      : null;

  const graphologyGraph = useMemo(
    () =>
      createGraphologyGraph(
        graphPayload ?? {
          generatedAt: "",
          entityCount: 0,
          relationshipCount: 0,
          truncated: false,
          nodes: [],
          edges: [],
        },
      ),
    [graphPayload],
  );

  const refreshAll = useCallback(() => {
    void graphQuery.refetch();
    void timelineQuery.refetch();
    if (selectedNodeIdSafe) {
      void entityDetailQuery.refetch();
    }
  }, [entityDetailQuery, graphQuery, selectedNodeIdSafe, timelineQuery]);

  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value);
  }, []);

  const handleToggleType = useCallback((type: string) => {
    setSelectedTypes((previous) => {
      const next = previous.includes(type)
        ? previous.filter((item) => item !== type)
        : [...previous, type];

      if (selectedNodeId && next.length > 0) {
        const selectedNode = graphPayload?.nodes.find((node) => node.entityId === selectedNodeId);
        if (selectedNode && !next.includes(selectedNode.type)) {
          setSelectedNodeId(null);
        }
      }

      return next;
    });
  }, [graphPayload, selectedNodeId]);

  const handleClearTypes = useCallback(() => {
    setSelectedTypes([]);
  }, []);

  const handleSelectNode = useCallback((nodeId: string | null) => {
    setSelectedNodeId(nodeId);
  }, []);

  const handleShowLast30DaysToggle = useCallback(() => {
    setShowLast30Days((value) => !value);
  }, []);

  const handleShowEdgeLabelsToggle = useCallback(() => {
    setShowEdgeLabels((value) => !value);
  }, []);

  const handleLoadMore = useCallback(() => {
    setMaxNodes((value) => Math.min(2500, value + 250));
    setMaxEdges((value) => Math.min(8000, value + 1000));
  }, []);

  const handleExportPng = useCallback(() => {
    downloadPngFromSigma(sigmaInstance, `graph-${projectId}.png`);
  }, [projectId, sigmaInstance]);

  const handleExportJson = useCallback(() => {
    if (!graphPayload) {
      return;
    }
    downloadJson(`graph-${projectId}.json`, graphPayload);
  }, [graphPayload, projectId]);

  return (
    <div className="mx-auto max-w-[1440px] space-y-5">
      <GraphPlaygroundHero
        graphPayload={graphPayload}
        isError={graphQuery.isError}
        isLoading={graphQuery.isLoading || graphQuery.isFetching}
      />

      <GraphPlaygroundControlRail
        availableTypes={availableTypes}
        graphPayload={graphPayload}
        isRefreshing={graphQuery.isFetching || timelineQuery.isFetching}
        onClearTypes={handleClearTypes}
        onExportJson={handleExportJson}
        onExportPng={handleExportPng}
        onRefresh={refreshAll}
        onSearchChange={handleSearchChange}
        onSelectNode={(nodeId) => handleSelectNode(nodeId)}
        onToggleEdgeLabels={handleShowEdgeLabelsToggle}
        onToggleLast30Days={handleShowLast30DaysToggle}
        onToggleType={handleToggleType}
        projectId={projectId}
        searchQuery={searchQuery}
        searchResultNodes={searchResultNodes}
        selectedNodeId={selectedNodeIdSafe}
        selectedTypeSet={selectedTypeSet}
        showEdgeLabels={showEdgeLabels}
        showLast30Days={showLast30Days}
      />

      {graphPayload?.truncated ? (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-[22px] border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          <p>
            Graph density is intentionally capped for readability. Load more only if you need broader context.
          </p>
          <button
            className="rounded-full border border-amber-300/30 px-4 py-2 text-xs font-medium transition hover:bg-amber-400/15"
            onClick={handleLoadMore}
            type="button"
          >
            Load more nodes
          </button>
        </section>
      ) : null}

      {!isDesktopViewport ? (
        <section className="space-y-4">
          <div className="rounded-[24px] border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
            <h2 className="text-sm font-semibold text-[var(--vr-text-strong)]">Mobile List View</h2>
            <p className="mt-1 text-sm text-[var(--vr-text-dim)]">
              Graph canvas stays disabled on small screens so the information remains readable.
            </p>
          </div>

          {graphQuery.isLoading ? (
            <div className="flex items-center gap-2 rounded-[24px] border border-[var(--vr-border)] bg-[var(--vr-bg-card)] px-5 py-4 text-sm text-[var(--vr-text-dim)]">
              <Loader2 className="size-4 animate-spin" />
              Loading graph...
            </div>
          ) : graphError ? (
            <div className="rounded-[24px] border border-rose-400/25 bg-rose-500/8 px-5 py-4">
              <p className="text-sm text-rose-100">{graphErrorText}</p>
              {graphError.requestId ? (
                <p className="mt-2 font-mono text-[11px] text-[var(--vr-text-dim)]">Request ID: {graphError.requestId}</p>
              ) : null}
            </div>
          ) : mobileNodes.length === 0 ? (
            <div className="rounded-[24px] border border-[var(--vr-border)] bg-[var(--vr-bg-card)] px-5 py-4 text-sm text-[var(--vr-text-dim)]">
              No matching nodes for the current filters.
            </div>
          ) : (
            <div className="space-y-2">
              {mobileNodes.map((node) => (
                <button
                  className="flex w-full items-center justify-between rounded-[22px] border border-[var(--vr-border)] bg-[var(--vr-bg-card)] px-4 py-3 text-left transition hover:bg-[var(--vr-bg-elevated)]"
                  key={node.entityId}
                  onClick={() => handleSelectNode(node.entityId)}
                  type="button"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-[var(--vr-text-strong)]">{node.name}</p>
                    <p className="text-xs text-[var(--vr-text-dim)]">{node.type}</p>
                  </div>
                  <span className="font-mono text-xs text-[var(--vr-graph-cyan)]">{node.factCount}</span>
                </button>
              ))}
            </div>
          )}

          {selectedNodeIdSafe ? (
            <GraphPlaygroundEntityInspector
              data={entityDetailQuery.data}
              error={entityDetailError}
              isError={entityDetailQuery.isError}
              isLoading={entityDetailQuery.isLoading}
              onClear={() => handleSelectNode(null)}
              projectId={projectId}
              selectedNode={selectedNode}
            />
          ) : null}

          <GraphPlaygroundRecentThreads
            data={timelineQuery.data}
            error={timelineError}
            isError={timelineQuery.isError}
            isLoading={timelineQuery.isLoading}
            projectId={projectId}
          />
        </section>
      ) : (
        <>
          {selectedNodeIdSafe ? (
            <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
              <GraphPlaygroundGraphStage
                graphError={graphError}
                graphErrorText={graphErrorText}
                graphPayload={graphPayload}
                graphologyGraph={graphologyGraph}
                isFetching={graphQuery.isFetching}
                isLoading={graphQuery.isLoading}
                onRequestRefresh={refreshAll}
                onSelectNode={handleSelectNode}
                onSigmaInstanceChange={setSigmaInstance}
                projectId={projectId}
                searchMatches={searchMatches}
                searchQuery={searchQuery}
                selectedNodeId={selectedNodeIdSafe}
                selectedTypes={selectedTypeSet}
                showEdgeLabels={showEdgeLabels}
                showGraphDependencyHint={showGraphDependencyHint}
              />
              <GraphPlaygroundEntityInspector
                data={entityDetailQuery.data}
                error={entityDetailError}
                isError={entityDetailQuery.isError}
                isLoading={entityDetailQuery.isLoading}
                onClear={() => handleSelectNode(null)}
                projectId={projectId}
                selectedNode={selectedNode}
              />
            </section>
          ) : (
            <GraphPlaygroundGraphStage
              graphError={graphError}
              graphErrorText={graphErrorText}
              graphPayload={graphPayload}
              graphologyGraph={graphologyGraph}
              isFetching={graphQuery.isFetching}
              isLoading={graphQuery.isLoading}
              onRequestRefresh={refreshAll}
              onSelectNode={handleSelectNode}
              onSigmaInstanceChange={setSigmaInstance}
              projectId={projectId}
              searchMatches={searchMatches}
              searchQuery={searchQuery}
              selectedNodeId={selectedNodeIdSafe}
              selectedTypes={selectedTypeSet}
              showEdgeLabels={showEdgeLabels}
              showGraphDependencyHint={showGraphDependencyHint}
            />
          )}

          <GraphPlaygroundRecentThreads
            data={timelineQuery.data}
            error={timelineError}
            isError={timelineQuery.isError}
            isLoading={timelineQuery.isLoading}
            projectId={projectId}
          />
        </>
      )}
    </div>
  );
}
