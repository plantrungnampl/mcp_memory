import type { MaintenanceJob, ProjectExport } from "@/lib/api/types";
import { serverEnv } from "@/lib/server-env";

import {
  controlPlaneHeaders,
  fetchControlPlane,
  parseJson,
  type ControlPlaneUser,
} from "@/lib/api/control-plane-shared";

export function mapProjectExportPayload(payload: {
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

export function mapMaintenanceJobPayload(payload: {
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
  const response = await fetchControlPlane(
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
  return payload.exports.map(mapProjectExportPayload);
}

export async function createProjectExport(
  user: ControlPlaneUser,
  projectId: string,
  input: { format: "json_v1" },
  idempotencyKey: string,
): Promise<ProjectExport> {
  const response = await fetchControlPlane(
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
  return mapProjectExportPayload(payload.export);
}

export async function getProjectExport(
  user: ControlPlaneUser,
  projectId: string,
  exportId: string,
): Promise<ProjectExport> {
  const response = await fetchControlPlane(
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
  return mapProjectExportPayload(payload.export);
}

export async function runProjectRetention(
  user: ControlPlaneUser,
  projectId: string,
): Promise<MaintenanceJob> {
  const response = await fetchControlPlane(
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
  return mapMaintenanceJobPayload(payload.job);
}

export async function purgeProject(
  user: ControlPlaneUser,
  projectId: string,
  idempotencyKey: string,
): Promise<MaintenanceJob> {
  const response = await fetchControlPlane(
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
  return mapMaintenanceJobPayload(payload.job);
}

export async function migrateInlineToObject(
  user: ControlPlaneUser,
  projectId: string,
  input: { force: boolean },
  idempotencyKey: string,
): Promise<MaintenanceJob> {
  const response = await fetchControlPlane(
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
  return mapMaintenanceJobPayload(payload.job);
}
