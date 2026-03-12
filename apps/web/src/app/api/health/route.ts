import { NextResponse } from "next/server";

import { createControlPlaneHeaders } from "@/lib/api/control-plane-headers";
import { publicEnv } from "@/lib/env";
import { serverEnv } from "@/lib/server-env";

type HealthProbe = {
  detail: string | null;
  ok: boolean;
  requestId: string | null;
  status: number | null;
};

type WebHealthPayload = {
  app: "viberecall-web";
  backendHealth: HealthProbe;
  controlPlaneRead: HealthProbe;
  ok: boolean;
  supabaseConfigured: boolean;
};

async function probeJsonEndpoint(
  fetchImpl: typeof fetch,
  input: string,
  init?: RequestInit,
): Promise<HealthProbe> {
  try {
    const response = await fetchImpl(input, {
      cache: "no-store",
      ...init,
    });
    const requestId = response.headers.get("X-Request-Id");
    const responseText = await response.text();
    return {
      ok: response.ok,
      status: response.status,
      requestId,
      detail: response.ok ? null : responseText || null,
    };
  } catch (error) {
    return {
      ok: false,
      status: null,
      requestId: null,
      detail: error instanceof Error ? error.message : "Unknown network error",
    };
  }
}

export async function runHealthChecks(fetchImpl: typeof fetch = fetch): Promise<WebHealthPayload> {
  const backendHealth = await probeJsonEndpoint(
    fetchImpl,
    `${serverEnv.controlPlaneApiBaseUrl}/healthz`,
  );
  const controlPlaneRead = await probeJsonEndpoint(
    fetchImpl,
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects`,
    {
      headers: createControlPlaneHeaders({
        id: "healthcheck-web",
        email: null,
      }),
    },
  );

  return {
    ok: backendHealth.ok && controlPlaneRead.ok,
    app: "viberecall-web",
    supabaseConfigured: publicEnv.hasSupabase,
    backendHealth,
    controlPlaneRead,
  };
}

export async function GET() {
  const payload = await runHealthChecks();
  return NextResponse.json(payload, {
    status: payload.ok ? 200 : 503,
  });
}
