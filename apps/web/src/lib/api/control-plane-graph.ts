import type {
  ApiLogsRange,
  ApiLogsStatusFilter,
  GraphViewMode,
  ProjectApiLogsAnalyticsPayload,
  ProjectApiLogsPage,
  ProjectGraphEntityDetail,
  ProjectGraphPayload,
  ProjectIndexSummary,
  ProjectTimelinePayload,
} from "@/lib/api/types";
import { serverEnv } from "@/lib/server-env";

import {
  controlPlaneHeaders,
  fetchControlPlane,
  mapProjectIndexSummary,
  parseJson,
  type ControlPlaneUser,
} from "@/lib/api/control-plane-shared";

export async function getProjectGraph(
  user: ControlPlaneUser,
  projectId: string,
  input?: {
    mode?: GraphViewMode;
    query?: string | null;
    entityTypes?: string[];
    lastDays?: number | null;
    maxNodes?: number;
    maxEdges?: number;
    maxFacts?: number;
  },
): Promise<ProjectGraphPayload> {
  const params = new URLSearchParams();
  params.set("mode", input?.mode ?? "concepts");
  if (input?.query && input.query.trim()) {
    params.set("q", input.query.trim());
  }
  if (input?.entityTypes && input.entityTypes.length > 0) {
    params.set("entity_types", input.entityTypes.join(","));
  }
  if (typeof input?.lastDays === "number" && input.lastDays > 0) {
    params.set("last_days", String(input.lastDays));
  }
  if (typeof input?.maxNodes === "number") {
    params.set("max_nodes", String(input.maxNodes));
  }
  if (typeof input?.maxEdges === "number") {
    params.set("max_edges", String(input.maxEdges));
  }
  if (typeof input?.maxFacts === "number") {
    params.set("max_facts", String(input.maxFacts));
  }
  const query = params.toString();
  const response = await fetchControlPlane(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/graph${query ? `?${query}` : ""}`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    graph: {
      generated_at: string;
      mode: GraphViewMode;
      empty_reason: ProjectGraphPayload["emptyReason"];
      index_summary: {
        status: ProjectIndexSummary["status"];
        current_run_id: string | null;
        latest_ready_at: string | null;
        queued_at: string | null;
        started_at: string | null;
        completed_at: string | null;
        age_seconds: number | null;
        error_code: string | null;
        error_message: string | null;
        recommended_action: ProjectIndexSummary["recommendedAction"];
      } | null;
      available_modes: GraphViewMode[];
      node_primary_label: string;
      node_secondary_label: string;
      edge_support_label: string;
      entity_count: number;
      relationship_count: number;
      truncated: boolean;
      nodes: Array<{
        entity_id: string;
        type: string;
        name: string;
        fact_count: number;
        episode_count: number;
        reference_time: string | null;
        hover_text: Array<{ text: string; reference_time: string | null }>;
      }>;
      edges: Array<{
        edge_id: string;
        type: string;
        source_entity_id: string;
        target_entity_id: string;
        weight: number;
        episode_count: number;
        label: string;
      }>;
    };
  }>(response);

  return {
    generatedAt: payload.graph.generated_at,
    mode: payload.graph.mode,
    emptyReason: payload.graph.empty_reason,
    indexSummary: payload.graph.index_summary ? mapProjectIndexSummary(payload.graph.index_summary) : null,
    availableModes: payload.graph.available_modes,
    nodePrimaryLabel: payload.graph.node_primary_label,
    nodeSecondaryLabel: payload.graph.node_secondary_label,
    edgeSupportLabel: payload.graph.edge_support_label,
    entityCount: payload.graph.entity_count,
    relationshipCount: payload.graph.relationship_count,
    truncated: payload.graph.truncated,
    nodes: payload.graph.nodes.map((node) => ({
      entityId: node.entity_id,
      type: node.type,
      name: node.name,
      factCount: node.fact_count,
      episodeCount: node.episode_count,
      referenceTime: node.reference_time,
      hoverText: node.hover_text.map((item) => ({
        text: item.text,
        referenceTime: item.reference_time,
      })),
    })),
    edges: payload.graph.edges.map((edge) => ({
      edgeId: edge.edge_id,
      type: edge.type,
      sourceEntityId: edge.source_entity_id,
      targetEntityId: edge.target_entity_id,
      weight: edge.weight,
      episodeCount: edge.episode_count,
      label: edge.label,
    })),
  };
}

export async function getProjectIndexSummary(
  user: ControlPlaneUser,
  projectId: string,
): Promise<ProjectIndexSummary> {
  const response = await fetchControlPlane(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/index-status`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    index_summary: {
      status: ProjectIndexSummary["status"];
      current_run_id: string | null;
      latest_ready_at: string | null;
      queued_at: string | null;
      started_at: string | null;
      completed_at: string | null;
      age_seconds: number | null;
      error_code: string | null;
      error_message: string | null;
      recommended_action: ProjectIndexSummary["recommendedAction"];
    };
  }>(response);
  return mapProjectIndexSummary(payload.index_summary);
}

export async function getProjectGraphEntityDetail(
  user: ControlPlaneUser,
  projectId: string,
  entityId: string,
  input?: {
    mode?: GraphViewMode;
    factLimit?: number;
    episodeLimit?: number;
    maxFactsScan?: number;
  },
): Promise<ProjectGraphEntityDetail> {
  const params = new URLSearchParams();
  params.set("mode", input?.mode ?? "concepts");
  if (typeof input?.factLimit === "number") {
    params.set("fact_limit", String(input.factLimit));
  }
  if (typeof input?.episodeLimit === "number") {
    params.set("episode_limit", String(input.episodeLimit));
  }
  if (typeof input?.maxFactsScan === "number") {
    params.set("max_facts_scan", String(input.maxFactsScan));
  }
  const query = params.toString();
  const encodedEntityId = encodeURIComponent(entityId);
  const response = await fetchControlPlane(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/graph/entities/${encodedEntityId}${query ? `?${query}` : ""}`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    mode: GraphViewMode;
    entity: {
      entity_id: string;
      type: string;
      name: string;
      fact_count: number;
      episode_count: number;
      file_paths?: string[];
      language?: string | null;
      kind?: string | null;
    };
    facts: Array<{
      fact_id: string;
      text: string;
      valid_at: string | null;
      invalid_at: string | null;
      ingested_at: string | null;
      provenance: {
        episode_ids: string[];
        reference_time: string | null;
        ingested_at: string | null;
      };
    }>;
    provenance: Array<{
      episode_id: string;
      reference_time: string | null;
      ingested_at: string | null;
      summary: string | null;
      metadata: Record<string, unknown>;
    }>;
    related_entities: Array<{
      entity_id: string;
      type: string;
      name: string;
      relation_type: string;
      support_count: number;
    }>;
    citations: Array<{
      citation_id: string;
      source_type: string;
      entity_id: string;
      file_path: string | null;
      line_start: number | null;
      line_end: number | null;
      snippet: string | null;
    }>;
    symbols: Array<{
      entity_id: string;
      name: string;
      kind: string | null;
      file_path: string | null;
      line_start: number | null;
      line_end: number | null;
      language: string | null;
    }>;
  }>(response);

  return {
    mode: payload.mode,
    entity: {
      entityId: payload.entity.entity_id,
      type: payload.entity.type,
      name: payload.entity.name,
      factCount: payload.entity.fact_count,
      episodeCount: payload.entity.episode_count,
      filePaths: payload.entity.file_paths,
      language: payload.entity.language,
      kind: payload.entity.kind,
    },
    facts: payload.facts.map((fact) => ({
      factId: fact.fact_id,
      text: fact.text,
      validAt: fact.valid_at,
      invalidAt: fact.invalid_at,
      ingestedAt: fact.ingested_at,
      provenance: {
        episodeIds: fact.provenance.episode_ids,
        referenceTime: fact.provenance.reference_time,
        ingestedAt: fact.provenance.ingested_at,
      },
    })),
    provenance: payload.provenance.map((episode) => ({
      episodeId: episode.episode_id,
      referenceTime: episode.reference_time,
      ingestedAt: episode.ingested_at,
      summary: episode.summary,
      metadata: episode.metadata,
    })),
    relatedEntities: payload.related_entities.map((entity) => ({
      entityId: entity.entity_id,
      type: entity.type,
      name: entity.name,
      relationType: entity.relation_type,
      supportCount: entity.support_count,
    })),
    citations: payload.citations.map((citation) => ({
      citationId: citation.citation_id,
      sourceType: citation.source_type,
      entityId: citation.entity_id,
      filePath: citation.file_path,
      lineStart: citation.line_start,
      lineEnd: citation.line_end,
      snippet: citation.snippet,
    })),
    symbols: payload.symbols.map((symbol) => ({
      entityId: symbol.entity_id,
      name: symbol.name,
      kind: symbol.kind,
      filePath: symbol.file_path,
      lineStart: symbol.line_start,
      lineEnd: symbol.line_end,
      language: symbol.language,
    })),
  };
}

export async function getProjectTimeline(
  user: ControlPlaneUser,
  projectId: string,
  input?: {
    limit?: number;
    offset?: number;
    fromTime?: string | null;
    toTime?: string | null;
  },
): Promise<ProjectTimelinePayload> {
  const params = new URLSearchParams();
  params.set("limit", String(input?.limit ?? 50));
  params.set("offset", String(input?.offset ?? 0));
  if (input?.fromTime) {
    params.set("from_time", input.fromTime);
  }
  if (input?.toTime) {
    params.set("to_time", input.toTime);
  }
  const response = await fetchControlPlane(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/timeline?${params.toString()}`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    timeline: {
      rows: Array<{
        episode_id: string;
        reference_time: string | null;
        ingested_at: string | null;
        summary: string | null;
        metadata: Record<string, unknown>;
      }>;
      offset: number;
      limit: number;
      has_more: boolean;
      next_offset: number | null;
    };
  }>(response);

  return {
    rows: payload.timeline.rows.map((row) => ({
      episodeId: row.episode_id,
      referenceTime: row.reference_time,
      ingestedAt: row.ingested_at,
      summary: row.summary,
      metadata: row.metadata,
    })),
    offset: payload.timeline.offset,
    limit: payload.timeline.limit,
    hasMore: payload.timeline.has_more,
    nextOffset: payload.timeline.next_offset,
  };
}

export async function getProjectApiLogs(
  user: ControlPlaneUser,
  projectId: string,
  input?: { limit?: number; cursor?: number | string | null },
): Promise<ProjectApiLogsPage> {
  const limit = input?.limit ?? 50;
  const cursor = input?.cursor ?? null;
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (cursor !== null) {
    params.set("cursor", String(cursor));
  }
  const response = await fetchControlPlane(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/api-logs?${params.toString()}`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    logs: Array<{
      id: number;
      request_id: string | null;
      project_id: string | null;
      token_id: string | null;
      tool_name: string | null;
      action: string;
      args_hash: string | null;
      status: string;
      created_at: string | null;
      latency_ms?: number | null;
    }>;
    next_cursor: number | null;
  }>(response);

  return {
    logs: payload.logs.map((log) => ({
      id: log.id,
      requestId: log.request_id,
      projectId: log.project_id,
      tokenId: log.token_id,
      toolName: log.tool_name,
      action: log.action,
      argsHash: log.args_hash,
      status: log.status,
      createdAt: log.created_at,
      latencyMs: log.latency_ms ?? null,
    })),
    nextCursor: payload.next_cursor,
  };
}

export async function getProjectApiLogsAnalytics(
  user: ControlPlaneUser,
  projectId: string,
  input?: {
    range?: ApiLogsRange;
    statusFilter?: ApiLogsStatusFilter;
    tool?: string | null;
    query?: string | null;
    limit?: number;
    cursor?: string | null;
  },
): Promise<ProjectApiLogsAnalyticsPayload> {
  const params = new URLSearchParams();
  params.set("range", input?.range ?? "30d");
  params.set("status_filter", input?.statusFilter ?? "all");
  params.set("limit", String(input?.limit ?? 5));
  if (input?.tool && input.tool.trim()) {
    params.set("tool", input.tool.trim());
  }
  if (input?.query && input.query.trim()) {
    params.set("q", input.query.trim());
  }
  if (input?.cursor) {
    params.set("cursor", input.cursor);
  }
  const response = await fetchControlPlane(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/api-logs/analytics?${params.toString()}`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    range: ApiLogsRange;
    filters: {
      status_filter: ApiLogsStatusFilter;
      tool: string | null;
      q: string | null;
    };
    summary: {
      total_requests: { value: number | null; change_pct: number | null };
      success_rate_pct: { value: number | null; change_pct: number | null };
      error_count: { value: number | null; change_pct: number | null };
      p95_latency_ms: { value: number | null; change_pct: number | null };
    };
    table: {
      rows: Array<{
        id: number;
        time: string | null;
        tool: string | null;
        status: string | null;
        latency_ms: number | null;
        token_prefix: string | null;
        request_id: string | null;
        action: string | null;
      }>;
      tool_options: string[];
      pagination: {
        total_rows: number;
        showing_from: number;
        showing_to: number;
        next_cursor: string | null;
        prev_cursor: string | null;
      };
    };
  }>(response);

  return {
    range: payload.range,
    filters: {
      statusFilter: payload.filters.status_filter,
      tool: payload.filters.tool,
      query: payload.filters.q,
    },
    summary: {
      totalRequests: {
        value: payload.summary.total_requests.value,
        changePct: payload.summary.total_requests.change_pct,
      },
      successRatePct: {
        value: payload.summary.success_rate_pct.value,
        changePct: payload.summary.success_rate_pct.change_pct,
      },
      errorCount: {
        value: payload.summary.error_count.value,
        changePct: payload.summary.error_count.change_pct,
      },
      p95LatencyMs: {
        value: payload.summary.p95_latency_ms.value,
        changePct: payload.summary.p95_latency_ms.change_pct,
      },
    },
    table: {
      rows: payload.table.rows.map((row) => ({
        id: row.id,
        time: row.time,
        tool: row.tool,
        status: row.status,
        latencyMs: row.latency_ms,
        tokenPrefix: row.token_prefix,
        requestId: row.request_id,
        action: row.action,
      })),
      toolOptions: payload.table.tool_options,
      pagination: {
        totalRows: payload.table.pagination.total_rows,
        showingFrom: payload.table.pagination.showing_from,
        showingTo: payload.table.pagination.showing_to,
        nextCursor: payload.table.pagination.next_cursor,
        prevCursor: payload.table.pagination.prev_cursor,
      },
    },
  };
}
