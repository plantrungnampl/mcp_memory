import assert from "node:assert/strict";
import test from "node:test";

test("mapProjectExportPayload converts snake_case export payloads", async () => {
  process.env.CONTROL_PLANE_API_BASE_URL = "http://localhost:8010";
  process.env.CONTROL_PLANE_INTERNAL_SECRET = "test-control-plane-secret";

  const { mapProjectExportPayload } = await import("./control-plane-exports");
  const mapped = mapProjectExportPayload({
    export_id: "exp_123",
    project_id: "proj_123",
    status: "pending",
    format: "json_v1",
    object_url: null,
    expires_at: null,
    error: null,
    requested_by: "user_123",
    requested_at: "2026-03-19T10:00:00Z",
    completed_at: null,
    job_id: "job_123",
  });

  assert.deepEqual(mapped, {
    exportId: "exp_123",
    projectId: "proj_123",
    status: "pending",
    format: "json_v1",
    objectUrl: null,
    expiresAt: null,
    error: null,
    requestedBy: "user_123",
    requestedAt: "2026-03-19T10:00:00Z",
    completedAt: null,
    jobId: "job_123",
  });
});

test("mapMaintenanceJobPayload converts optional maintenance fields", async () => {
  process.env.CONTROL_PLANE_API_BASE_URL = "http://localhost:8010";
  process.env.CONTROL_PLANE_INTERNAL_SECRET = "test-control-plane-secret";

  const { mapMaintenanceJobPayload } = await import("./control-plane-exports");
  const mapped = mapMaintenanceJobPayload({
    job_id: "job_retention",
    kind: "retention",
    status: "queued",
    retention_days: 30,
    force: true,
  });

  assert.deepEqual(mapped, {
    jobId: "job_retention",
    kind: "retention",
    status: "queued",
    retentionDays: 30,
    force: true,
  });
});
