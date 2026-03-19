import type { ProjectIndexSummary } from "@/lib/api/types";
import {
  createControlPlaneHeaders,
  getControlPlaneRequestMeta,
  type ControlPlaneUser,
} from "@/lib/api/control-plane-headers";

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

export async function fetchControlPlane(
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

export async function parseJson<T>(response: Response): Promise<T> {
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

export { createControlPlaneHeaders, type ControlPlaneUser };

export function controlPlaneHeaders(
  user: ControlPlaneUser,
  extraHeaders?: Record<string, string>,
): HeadersInit {
  return createControlPlaneHeaders(user, extraHeaders);
}
