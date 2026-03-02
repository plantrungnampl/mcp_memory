import type {
  CreatedProjectResult,
  MaintenanceJob,
  ProjectApiLogsPage,
  ProjectBillingOverview,
  McpConnectionInfo,
  ProjectOverviewRow,
  PlaintextTokenReveal,
  ProjectExport,
  ProjectSummary,
  ProjectToken,
  UsageSeries,
  UsageSummary,
} from "@/lib/api/types";
import { serverEnv } from "@/lib/server-env";

export type ControlPlaneUser = {
  id: string;
  email?: string | null;
};

function controlPlaneHeaders(
  user: ControlPlaneUser,
  extraHeaders?: Record<string, string>,
): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Control-Plane-Secret": serverEnv.controlPlaneInternalSecret,
    "X-Control-Plane-User-Id": user.id,
    "X-Control-Plane-User-Email": user.email ?? "",
    ...extraHeaders,
  };
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Control-plane request failed (${response.status}): ${body}`);
  }

  return response.json() as Promise<T>;
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
  };
}

export async function getProjectApiLogs(
  user: ControlPlaneUser,
  projectId: string,
  input?: { limit?: number; cursor?: number | null },
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
    })),
    nextCursor: payload.next_cursor,
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
