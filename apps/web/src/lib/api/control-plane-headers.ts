import { randomUUID } from "node:crypto";

import { createSignedControlPlaneAssertion } from "@/lib/auth/control-plane-assertion-core";
import { serverEnv } from "@/lib/server-env";

export type ControlPlaneUser = {
  id: string;
  email?: string | null;
};

export type ControlPlaneRequestMeta = {
  assertionAttached: boolean;
  requestId: string;
  userIdPresent: boolean;
};

const requestMetaStore = new WeakMap<object, ControlPlaneRequestMeta>();

function createControlPlaneRequestId(): string {
  return `req_${randomUUID().replace(/-/g, "").slice(0, 16)}`;
}

export function createControlPlaneHeaders(
  user: ControlPlaneUser,
  extraHeaders?: Record<string, string>,
): HeadersInit {
  const requestId = extraHeaders?.["X-Request-Id"] ?? createControlPlaneRequestId();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Control-Plane-Assertion": createSignedControlPlaneAssertion(
      serverEnv.controlPlaneInternalSecret,
      user,
    ),
    "X-Request-Id": requestId,
    ...extraHeaders,
  };

  requestMetaStore.set(headers, {
    assertionAttached: true,
    requestId,
    userIdPresent: Boolean(user.id),
  });

  return headers;
}

export function getControlPlaneRequestMeta(headers: RequestInit["headers"]): ControlPlaneRequestMeta | null {
  if (!headers || typeof headers !== "object") {
    return null;
  }
  return requestMetaStore.get(headers as object) ?? null;
}
