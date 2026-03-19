import type {
  CreatedProjectResult,
  McpConnectionInfo,
  PlaintextTokenReveal,
  ProjectOverviewRow,
  ProjectSummary,
  ProjectToken,
} from "@/lib/api/types";
import { serverEnv } from "@/lib/server-env";

import {
  controlPlaneHeaders,
  fetchControlPlane,
  parseJson,
  type ControlPlaneUser,
} from "@/lib/api/control-plane-shared";

export async function getProjects(user: ControlPlaneUser): Promise<ProjectSummary[]> {
  const response = await fetchControlPlane(`${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects`, {
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
  const response = await fetchControlPlane(
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
  const response = await fetchControlPlane(
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
  const response = await fetchControlPlane(`${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects`, {
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
  const response = await fetchControlPlane(
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
  const response = await fetchControlPlane(
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
  const response = await fetchControlPlane(
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

export async function getProjectsOverview(
  user: ControlPlaneUser,
  input: { windowDays: number },
): Promise<ProjectOverviewRow[]> {
  const response = await fetchControlPlane(
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
