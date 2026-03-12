import assert from "node:assert/strict";
import test from "node:test";

function makeResponse(body: unknown, init: { requestId?: string; status: number }): Response {
  return new Response(JSON.stringify(body), {
    status: init.status,
    headers: init.requestId ? { "X-Request-Id": init.requestId } : undefined,
  });
}

test("runHealthChecks probes backend health and signed control-plane read", async () => {
  Object.assign(process.env, {
    NODE_ENV: "test",
    NEXT_PUBLIC_APP_URL: "https://app.example.com",
    NEXT_PUBLIC_DOCS_URL: "https://docs.example.com",
    NEXT_PUBLIC_MCP_BASE_URL: "https://api.example.com",
    CONTROL_PLANE_API_BASE_URL: "https://api.example.com",
    CONTROL_PLANE_INTERNAL_SECRET: "test-control-plane-secret",
  });

  const { runHealthChecks } = await import("./route");
  const requests: Array<{ headers: RequestInit["headers"]; url: string }> = [];

  const payload = await runHealthChecks(async (input, init) => {
    const url = String(input);
    requests.push({ url, headers: init?.headers });
    if (url.endsWith("/healthz")) {
      return makeResponse({ status: "ok" }, { status: 200, requestId: "req_health_1" });
    }
    return makeResponse({ projects: [] }, { status: 200, requestId: "req_cp_1" });
  });

  assert.equal(payload.ok, true);
  assert.equal(payload.backendHealth.requestId, "req_health_1");
  assert.equal(payload.controlPlaneRead.requestId, "req_cp_1");
  assert.equal(requests[0]?.url, "https://api.example.com/healthz");
  assert.equal(requests[1]?.url, "https://api.example.com/api/control-plane/projects");
  const controlPlaneHeaders = requests[1]?.headers as Record<string, string>;
  assert.match(controlPlaneHeaders["X-Control-Plane-Assertion"], /^v1\./);
  assert.match(controlPlaneHeaders["X-Request-Id"], /^req_[a-z0-9]+$/);
});

test("runHealthChecks reports degraded when control-plane read fails", async () => {
  Object.assign(process.env, {
    NODE_ENV: "test",
    NEXT_PUBLIC_APP_URL: "https://app.example.com",
    NEXT_PUBLIC_DOCS_URL: "https://docs.example.com",
    NEXT_PUBLIC_MCP_BASE_URL: "https://api.example.com",
    CONTROL_PLANE_API_BASE_URL: "https://api.example.com",
    CONTROL_PLANE_INTERNAL_SECRET: "test-control-plane-secret",
  });

  const { runHealthChecks } = await import("./route");

  const payload = await runHealthChecks(async (input) => {
    const url = String(input);
    if (url.endsWith("/healthz")) {
      return makeResponse({ status: "ok" }, { status: 200, requestId: "req_health_ok" });
    }
    return makeResponse({ detail: "Missing control-plane assertion" }, { status: 401, requestId: "req_cp_fail" });
  });

  assert.equal(payload.ok, false);
  assert.equal(payload.backendHealth.ok, true);
  assert.equal(payload.controlPlaneRead.ok, false);
  assert.equal(payload.controlPlaneRead.status, 401);
  assert.match(payload.controlPlaneRead.detail ?? "", /Missing control-plane assertion/);
});
