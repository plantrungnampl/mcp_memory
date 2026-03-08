import assert from "node:assert/strict";
import test from "node:test";

test("createControlPlaneHeaders attaches assertion and request id", async () => {
  process.env.CONTROL_PLANE_INTERNAL_SECRET = "test-control-plane-secret";
  process.env.CONTROL_PLANE_API_BASE_URL = "http://localhost:8010";

  const { createControlPlaneHeaders } = await import("./control-plane-headers");

  const headers = createControlPlaneHeaders({
    id: "user_123",
    email: "dev@example.com",
  }) as Record<string, string>;

  assert.equal(headers["Content-Type"], "application/json");
  assert.match(headers["X-Control-Plane-Assertion"], /^v1\./);
  assert.match(headers["X-Request-Id"], /^req_[a-z0-9]+$/);
});

test("parseControlPlaneError extracts request id from formatted errors", async () => {
  const { parseControlPlaneError } = await import("./control-plane-error");

  const parsed = parseControlPlaneError(
    new Error(
      'Control-plane request failed (401) [request_id=req_trace_123]: {"detail":"Missing control-plane assertion"}',
    ),
  );

  assert.equal(parsed.status, 401);
  assert.equal(parsed.requestId, "req_trace_123");
  assert.equal(parsed.detail, "Missing control-plane assertion");
});

test("parseControlPlaneError understands BFF request payloads", async () => {
  const { parseControlPlaneError } = await import("./control-plane-error");

  const parsed = parseControlPlaneError(
    new Error(
      'Request failed (503): {"error":"Control-plane request failed.","detail":"Graph dependency check failed for memory backend \\"graphiti\\": Error 111 connecting to localhost:6380. Connection refused.","request_id":"req_graph_456","upstream_status":503}',
    ),
  );

  assert.equal(parsed.status, 503);
  assert.equal(parsed.message, "Control-plane request failed.");
  assert.equal(
    parsed.detail,
    "Graph dependency check failed for memory backend \"graphiti\": Error 111 connecting to localhost:6380. Connection refused.",
  );
  assert.equal(parsed.requestId, "req_graph_456");
});
