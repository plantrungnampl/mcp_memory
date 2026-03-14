import assert from "node:assert/strict";
import test from "node:test";

test("getProjectIndexUiState returns stalled copy", async () => {
  const { getProjectIndexUiState } = await import("./project-index-summary");

  const state = getProjectIndexUiState({
    status: "stalled",
    currentRunId: "idx_stalled",
    latestReadyAt: null,
    queuedAt: "2026-03-14T11:55:00Z",
    startedAt: null,
    completedAt: null,
    ageSeconds: 300,
    errorCode: null,
    errorMessage: null,
    recommendedAction: "check_workers",
  });

  assert.equal(state.badgeLabel, "Index stalled");
  assert.match(state.body, /worker|queue/i);
  assert.equal(state.tone, "warning");
});

test("getProjectIndexUiState returns ready copy", async () => {
  const { getProjectIndexUiState } = await import("./project-index-summary");

  const state = getProjectIndexUiState({
    status: "ready",
    currentRunId: null,
    latestReadyAt: "2026-03-14T11:58:00Z",
    queuedAt: null,
    startedAt: null,
    completedAt: null,
    ageSeconds: 120,
    errorCode: null,
    errorMessage: null,
    recommendedAction: "none",
  });

  assert.equal(state.badgeLabel, "Index ready");
  assert.match(state.body, /Last indexed at/i);
  assert.equal(state.tone, "success");
});
