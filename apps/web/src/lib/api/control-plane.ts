import "server-only";

import type {
  ApiLogsRange,
  ApiLogsStatusFilter,
  CreatedProjectResult,
  GraphViewMode,
  MaintenanceJob,
  ProjectGraphEntityDetail,
  ProjectGraphPayload,
  ProjectIndexSummary,
  ProjectApiLogsAnalyticsPayload,
  ProjectApiLogsPage,
  ProjectBillingOverview,
  ProjectTimelinePayload,
  McpConnectionInfo,
  ProjectOverviewRow,
  PlaintextTokenReveal,
  ProjectExport,
  ProjectSummary,
  ProjectToken,
  UsageAnalyticsPayload,
  UsageRange,
  UsageSeries,
  UsageSummary,
} from "@/lib/api/types";
import {
  createControlPlaneHeaders,
  getControlPlaneRequestMeta,
  type ControlPlaneUser,
} from "@/lib/api/control-plane-headers";
import { serverEnv } from "@/lib/server-env";

const nativeFetch = globalThis.fetch.bind(globalThis);

function getRequestPath(input: Parameters<typeof globalThis.fetch>[0]): string {
  if (typeof input === "string") {
    return new URL(input).pathname;
  }
  if (input instanceof URL) {
    return input.pathname;
  }
  return new URL(input.url).pathname;
}

function logControlPlaneEvent(level: "info" | "warn" | "error", payload: Record<string, unknown>): void {
  console[level](
    JSON.stringify({
      component: "control-plane-bff",
      ...payload,
    }),
  );
}

async function fetchControlPlane(
  input: Parameters<typeof globalThis.fetch>[0],
  init?: Parameters<typeof globalThis.fetch>[1],
): Promise<Response> {
  const meta = getControlPlaneRequestMeta(init?.headers);
  const method = (init?.method ?? "GET").toUpperCase();
  const path = getRequestPath(input);

  if (meta) {
    logControlPlaneEvent("info", {
      event: "control_plane_request_start",
      request_id: meta.requestId,
      method,
      path,
      assertion_attached: meta.assertionAttached,
      user_id_present: meta.userIdPresent,
    });
  }

  try {
    const response = await nativeFetch(input, init);
    if (meta) {
      logControlPlaneEvent(response.ok ? "info" : "warn", {
        event: "control_plane_request_complete",
        request_id: response.headers.get("X-Request-Id") ?? meta.requestId,
        method,
        path,
        status: response.status,
        assertion_attached: meta.assertionAttached,
        user_id_present: meta.userIdPresent,
      });
    }
    return response;
  } catch (error) {
    if (meta) {
      logControlPlaneEvent("error", {
        event: "control_plane_request_network_error",
        request_id: meta.requestId,
        method,
        path,
        assertion_attached: meta.assertionAttached,
        user_id_present: meta.userIdPresent,
        error: error instanceof Error ? error.message : "Unknown network error",
      });
    }
    throw error;
  }
}

const fetch: typeof globalThis.fetch = fetchControlPlane;
export { createControlPlaneHeaders, type ControlPlaneUser } from "@/lib/api/control-plane-headers";
const controlPlaneHeaders = createControlPlaneHeaders;

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    const requestId = response.headers.get("X-Request-Id");
    const requestIdSegment = requestId ? ` [request_id=${requestId}]` : "";
    throw new Error(`Control-plane request failed (${response.status})${requestIdSegment}: ${body}`);
  }

  return response.json() as Promise<T>;
}

export function mapProjectIndexSummary(payload: {
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
}): ProjectIndexSummary {
  return {
    status: payload.status,
    currentRunId: payload.current_run_id,
    latestReadyAt: payload.latest_ready_at,
    queuedAt: payload.queued_at,
    startedAt: payload.started_at,
    completedAt: payload.completed_at,
    ageSeconds: payload.age_seconds,
    errorCode: payload.error_code,
    errorMessage: payload.error_message,
    recommendedAction: payload.recommended_action,
  };
}

export async function getProjects(user: ControlPlaneUser): Promise<ProjectSummary[]> {
  const response = await fetch(`${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects`, {
    cache: "no-store",
    headers: controlPlaneHeaders(user),
  });
  const payload = await parseJson<{
    projects: Array<{
      id: string;
      name: string;
      plan: ProjectSummary["plan"];
      created_at: string;
    }>;
  }>(response);
  return payload.projects.map((project) => ({
    id: project.id,
    name: project.name,
    plan: project.plan,
    createdAt: project.created_at,
  }));
}

export async function getProjectTokens(
  user: ControlPlaneUser,
  projectId: string,
): Promise<ProjectToken[]> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/tokens`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    tokens: Array<{
      token_id: string;
      prefix: string;
      created_at: string;
      last_used_at: string | null;
      revoked_at: string | null;
      expires_at: string | null;
      status: ProjectToken["status"];
    }>;
  }>(response);
  return payload.tokens.map((token) => ({
    tokenId: token.token_id,
    prefix: token.prefix,
    createdAt: token.created_at,
    lastUsedAt: token.last_used_at,
    revokedAt: token.revoked_at,
    expiresAt: token.expires_at,
    status: token.status,
  }));
}

export async function getConnection(
  user: ControlPlaneUser,
  projectId: string,
): Promise<McpConnectionInfo> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/connection`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    endpoint: string;
    token_preview: string | null;
  }>(response);
  return {
    endpoint: payload.endpoint,
    tokenPreview: payload.token_preview ?? "No token provisioned yet",
  };
}

export async function createProject(
  user: ControlPlaneUser,
  input: { name: string; plan: "free" | "pro" | "team" },
): Promise<CreatedProjectResult> {
  const response = await fetch(`${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects`, {
    method: "POST",
    cache: "no-store",
    headers: controlPlaneHeaders(user),
    body: JSON.stringify(input),
  });
  const payload = await parseJson<{
    project: {
      id: string;
      name: string;
      plan: ProjectSummary["plan"];
      created_at: string;
    };
    connection: {
      endpoint: string;
      token_preview: string | null;
    };
    token: {
      token_id: string;
      prefix: string;
      plaintext: string | null;
      created_at: string;
      revoked_at: string | null;
      expires_at: string | null;
      status: PlaintextTokenReveal["status"];
    };
  }>(response);

  return {
    project: {
      id: payload.project.id,
      name: payload.project.name,
      plan: payload.project.plan,
      createdAt: payload.project.created_at,
    },
    connection: {
      endpoint: payload.connection.endpoint,
      tokenPreview: payload.connection.token_preview ?? "No token provisioned yet",
    },
    token: {
      tokenId: payload.token.token_id,
      prefix: payload.token.prefix,
      plaintext: payload.token.plaintext ?? "",
      createdAt: payload.token.created_at,
      revokedAt: payload.token.revoked_at,
      expiresAt: payload.token.expires_at,
      status: payload.token.status,
    },
  };
}

export async function mintToken(
  user: ControlPlaneUser,
  projectId: string,
): Promise<PlaintextTokenReveal> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/tokens`,
    {
      method: "POST",
      cache: "no-store",
      headers: controlPlaneHeaders(user),
      body: JSON.stringify({}),
    },
  );
  const payload = await parseJson<{
    token: {
      token_id: string;
      prefix: string;
      plaintext: string | null;
      created_at: string;
      revoked_at: string | null;
      expires_at: string | null;
      status: PlaintextTokenReveal["status"];
    };
  }>(response);

  return {
    tokenId: payload.token.token_id,
    prefix: payload.token.prefix,
    plaintext: payload.token.plaintext ?? "",
    createdAt: payload.token.created_at,
    revokedAt: payload.token.revoked_at,
    expiresAt: payload.token.expires_at,
    status: payload.token.status,
  };
}

export async function rotateToken(
  user: ControlPlaneUser,
  projectId: string,
  tokenId: string,
): Promise<PlaintextTokenReveal> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/tokens/${tokenId}/rotate`,
    {
      method: "POST",
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    new_token: {
      token_id: string;
      prefix: string;
      plaintext: string | null;
      created_at: string;
      revoked_at: string | null;
      expires_at: string | null;
      status: PlaintextTokenReveal["status"];
    };
  }>(response);

  return {
    tokenId: payload.new_token.token_id,
    prefix: payload.new_token.prefix,
    plaintext: payload.new_token.plaintext ?? "",
    createdAt: payload.new_token.created_at,
    revokedAt: payload.new_token.revoked_at,
    expiresAt: payload.new_token.expires_at,
    status: payload.new_token.status,
  };
}

export async function revokeToken(
  user: ControlPlaneUser,
  projectId: string,
  tokenId: string,
): Promise<ProjectToken> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/tokens/${tokenId}/revoke`,
    {
      method: "POST",
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    token: {
      token_id: string;
      prefix: string;
      created_at: string;
      last_used_at: string | null;
      revoked_at: string | null;
      expires_at: string | null;
      status: ProjectToken["status"];
    };
  }>(response);

  return {
    tokenId: payload.token.token_id,
    prefix: payload.token.prefix,
    createdAt: payload.token.created_at,
    lastUsedAt: payload.token.last_used_at,
    revokedAt: payload.token.revoked_at,
    expiresAt: payload.token.expires_at,
    status: payload.token.status,
  };
}

export async function getUsage(
  user: ControlPlaneUser,
  projectId: string,
  period: "daily" | "monthly",
): Promise<UsageSummary> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/usage?period=${period}`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    usage: {
      period: "daily" | "monthly";
      vibe_tokens: number;
      in_tokens: number;
      out_tokens: number;
      event_count: number;
    };
  }>(response);

  return {
    period: payload.usage.period,
    vibeTokens: payload.usage.vibe_tokens,
    inTokens: payload.usage.in_tokens,
    outTokens: payload.usage.out_tokens,
    eventCount: payload.usage.event_count,
  };
}

export async function getUsageSeries(
  user: ControlPlaneUser,
  projectId: string,
  input: { windowDays: number; bucket: "day" },
): Promise<UsageSeries> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/usage/series?window_days=${input.windowDays}&bucket=${input.bucket}`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    window_days: number;
    bucket: "day";
    series: Array<{
      bucket_start: string;
      vibe_tokens: number;
      in_tokens: number;
      out_tokens: number;
      event_count: number;
    }>;
  }>(response);
  return {
    windowDays: payload.window_days,
    bucket: payload.bucket,
    series: payload.series.map((entry) => ({
      bucketStart: entry.bucket_start,
      vibeTokens: entry.vibe_tokens,
      inTokens: entry.in_tokens,
      outTokens: entry.out_tokens,
      eventCount: entry.event_count,
    })),
  };
}

export async function getUsageAnalytics(
  user: ControlPlaneUser,
  projectId: string,
  range: UsageRange,
): Promise<UsageAnalyticsPayload> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/usage/analytics?range=${range}`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    range: UsageRange;
    window_days: number;
    date_range_label: string;
    summary: {
      api_calls: { value: number | null; change_pct: number | null };
      tokens_consumed: { value: number | null; change_pct: number | null };
      avg_response_time_ms: { value: number | null; change_pct: number | null };
      error_rate_pct: { value: number | null; change_pct: number | null };
    };
    trend: Array<{
      bucket_start: string;
      day_label: string;
      api_calls: number;
      vibe_tokens: number;
    }>;
    tool_distribution: Array<{
      tool: string;
      api_calls: number;
      share_pct: number;
    }>;
    token_breakdown: Array<{
      token_id: string;
      prefix: string;
      status: "active" | "grace" | "revoked";
      api_calls: number;
      vibe_tokens: number;
      avg_latency_ms: number | null;
      share_pct: number;
    }>;
    highlights: {
      peak_hour: string;
      most_active_token: string;
      busiest_day: string;
    };
  }>(response);

  return {
    range: payload.range,
    windowDays: payload.window_days,
    dateRangeLabel: payload.date_range_label,
    summary: {
      apiCalls: {
        value: payload.summary.api_calls.value,
        changePct: payload.summary.api_calls.change_pct,
      },
      tokensConsumed: {
        value: payload.summary.tokens_consumed.value,
        changePct: payload.summary.tokens_consumed.change_pct,
      },
      avgResponseTimeMs: {
        value: payload.summary.avg_response_time_ms.value,
        changePct: payload.summary.avg_response_time_ms.change_pct,
      },
      errorRatePct: {
        value: payload.summary.error_rate_pct.value,
        changePct: payload.summary.error_rate_pct.change_pct,
      },
    },
    trend: payload.trend.map((entry) => ({
      bucketStart: entry.bucket_start,
      dayLabel: entry.day_label,
      apiCalls: entry.api_calls,
      vibeTokens: entry.vibe_tokens,
    })),
    toolDistribution: payload.tool_distribution.map((entry) => ({
      tool: entry.tool,
      apiCalls: entry.api_calls,
      sharePct: entry.share_pct,
    })),
    tokenBreakdown: payload.token_breakdown.map((entry) => ({
      tokenId: entry.token_id,
      prefix: entry.prefix,
      status: entry.status,
      apiCalls: entry.api_calls,
      vibeTokens: entry.vibe_tokens,
      avgLatencyMs: entry.avg_latency_ms,
      sharePct: entry.share_pct,
    })),
    highlights: {
      peakHour: payload.highlights.peak_hour,
      mostActiveToken: payload.highlights.most_active_token,
      busiestDay: payload.highlights.busiest_day,
    },
  };
}

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
  const response = await fetch(
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
  const response = await fetch(
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
  const response = await fetch(
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
  const response = await fetch(
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

export async function getProjectBillingOverview(
  user: ControlPlaneUser,
  projectId: string,
): Promise<ProjectBillingOverview> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/billing/overview`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    project_id: string;
    plan: ProjectBillingOverview["plan"];
    monthly_quota_vibe_tokens: number | null;
    current_month_vibe_tokens: number;
    current_month_events: number;
    remaining_vibe_tokens: number | null;
    utilization_pct: number | null;
    reset_at: string;
    last_7d_vibe_tokens: number;
    projected_month_vibe_tokens: number;
    plan_monthly_price_cents: number;
    renews_at: string;
    invoices: Array<{
      invoice_id: string;
      invoice_date: string;
      description: string;
      amount_cents: number;
      currency: string;
      status: ProjectBillingOverview["invoices"][number]["status"];
      pdf_url: string | null;
    }>;
    payment_method: {
      payment_method_id: string;
      brand: string;
      last4: string;
      exp_month: number;
      exp_year: number;
      is_default: boolean;
    } | null;
    billing_contact: {
      email: string | null;
      tax_id: string | null;
    };
  }>(response);

  return {
    projectId: payload.project_id,
    plan: payload.plan,
    monthlyQuotaVibeTokens: payload.monthly_quota_vibe_tokens,
    currentMonthVibeTokens: payload.current_month_vibe_tokens,
    currentMonthEvents: payload.current_month_events,
    remainingVibeTokens: payload.remaining_vibe_tokens,
    utilizationPct: payload.utilization_pct,
    resetAt: payload.reset_at,
    last7dVibeTokens: payload.last_7d_vibe_tokens,
    projectedMonthVibeTokens: payload.projected_month_vibe_tokens,
    planMonthlyPriceCents: payload.plan_monthly_price_cents,
    renewsAt: payload.renews_at,
    invoices: payload.invoices.map((invoice) => ({
      invoiceId: invoice.invoice_id,
      invoiceDate: invoice.invoice_date,
      description: invoice.description,
      amountCents: invoice.amount_cents,
      currency: invoice.currency,
      status: invoice.status,
      pdfUrl: invoice.pdf_url,
    })),
    paymentMethod: payload.payment_method
      ? {
          paymentMethodId: payload.payment_method.payment_method_id,
          brand: payload.payment_method.brand,
          last4: payload.payment_method.last4,
          expMonth: payload.payment_method.exp_month,
          expYear: payload.payment_method.exp_year,
          isDefault: payload.payment_method.is_default,
        }
      : null,
    billingContact: {
      email: payload.billing_contact.email,
      taxId: payload.billing_contact.tax_id,
    },
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
  const response = await fetch(
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
  const response = await fetch(
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

export async function getProjectsOverview(
  user: ControlPlaneUser,
  input: { windowDays: number },
): Promise<ProjectOverviewRow[]> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/overview?window_days=${input.windowDays}`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    window_days: number;
    projects: Array<{
      id: string;
      name: string;
      plan: ProjectOverviewRow["plan"];
      created_at: string;
      last_activity_at: string | null;
      vibe_tokens_window: number;
      token_preview: string | null;
      token_status: ProjectOverviewRow["tokenStatus"];
      health_status: ProjectOverviewRow["healthStatus"];
    }>;
  }>(response);
  return payload.projects.map((project) => ({
    id: project.id,
    name: project.name,
    plan: project.plan,
    createdAt: project.created_at,
    lastActivityAt: project.last_activity_at,
    vibeTokensWindow: project.vibe_tokens_window,
    tokenPreview: project.token_preview,
    tokenStatus: project.token_status,
    healthStatus: project.health_status,
  }));
}

function mapProjectExport(payload: {
  export_id: string;
  project_id: string;
  status: ProjectExport["status"];
  format: "json_v1";
  object_url: string | null;
  expires_at: string | null;
  error: string | null;
  requested_by: string | null;
  requested_at: string;
  completed_at: string | null;
  job_id: string | null;
}): ProjectExport {
  return {
    exportId: payload.export_id,
    projectId: payload.project_id,
    status: payload.status,
    format: payload.format,
    objectUrl: payload.object_url,
    expiresAt: payload.expires_at,
    error: payload.error,
    requestedBy: payload.requested_by,
    requestedAt: payload.requested_at,
    completedAt: payload.completed_at,
    jobId: payload.job_id,
  };
}

function mapMaintenanceJob(payload: {
  job_id: string;
  kind: MaintenanceJob["kind"];
  status: MaintenanceJob["status"];
  retention_days?: number;
  force?: boolean;
}): MaintenanceJob {
  return {
    jobId: payload.job_id,
    kind: payload.kind,
    status: payload.status,
    retentionDays: payload.retention_days ?? null,
    force: payload.force ?? null,
  };
}

export async function getProjectExports(
  user: ControlPlaneUser,
  projectId: string,
): Promise<ProjectExport[]> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/exports`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    exports: Array<{
      export_id: string;
      project_id: string;
      status: ProjectExport["status"];
      format: "json_v1";
      object_url: string | null;
      expires_at: string | null;
      error: string | null;
      requested_by: string | null;
      requested_at: string;
      completed_at: string | null;
      job_id: string | null;
    }>;
  }>(response);
  return payload.exports.map(mapProjectExport);
}

export async function createProjectExport(
  user: ControlPlaneUser,
  projectId: string,
  input: { format: "json_v1" },
  idempotencyKey: string,
): Promise<ProjectExport> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/exports`,
    {
      method: "POST",
      cache: "no-store",
      headers: controlPlaneHeaders(user, { "Idempotency-Key": idempotencyKey }),
      body: JSON.stringify(input),
    },
  );
  const payload = await parseJson<{
    export: {
      export_id: string;
      project_id: string;
      status: ProjectExport["status"];
      format: "json_v1";
      object_url: string | null;
      expires_at: string | null;
      error: string | null;
      requested_by: string | null;
      requested_at: string;
      completed_at: string | null;
      job_id: string | null;
    };
  }>(response);
  return mapProjectExport(payload.export);
}

export async function getProjectExport(
  user: ControlPlaneUser,
  projectId: string,
  exportId: string,
): Promise<ProjectExport> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/exports/${exportId}`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    export: {
      export_id: string;
      project_id: string;
      status: ProjectExport["status"];
      format: "json_v1";
      object_url: string | null;
      expires_at: string | null;
      error: string | null;
      requested_by: string | null;
      requested_at: string;
      completed_at: string | null;
      job_id: string | null;
    };
  }>(response);
  return mapProjectExport(payload.export);
}

export async function runProjectRetention(
  user: ControlPlaneUser,
  projectId: string,
): Promise<MaintenanceJob> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/retention/run`,
    {
      method: "POST",
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    job: {
      job_id: string;
      kind: "retention";
      status: "queued";
      retention_days?: number;
    };
  }>(response);
  return mapMaintenanceJob(payload.job);
}

export async function purgeProject(
  user: ControlPlaneUser,
  projectId: string,
  idempotencyKey: string,
): Promise<MaintenanceJob> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/purge`,
    {
      method: "POST",
      cache: "no-store",
      headers: controlPlaneHeaders(user, { "Idempotency-Key": idempotencyKey }),
    },
  );
  const payload = await parseJson<{
    job: {
      job_id: string;
      kind: "purge_project";
      status: "queued";
    };
  }>(response);
  return mapMaintenanceJob(payload.job);
}

export async function migrateInlineToObject(
  user: ControlPlaneUser,
  projectId: string,
  input: { force: boolean },
  idempotencyKey: string,
): Promise<MaintenanceJob> {
  const response = await fetch(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/migrate-inline-to-object`,
    {
      method: "POST",
      cache: "no-store",
      headers: controlPlaneHeaders(user, { "Idempotency-Key": idempotencyKey }),
      body: JSON.stringify(input),
    },
  );
  const payload = await parseJson<{
    job: {
      job_id: string;
      kind: "migrate_inline_to_object";
      status: "queued";
      force?: boolean;
    };
  }>(response);
  return mapMaintenanceJob(payload.job);
}
