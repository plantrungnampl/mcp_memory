import {
  parseControlPlaneError,
  type ParsedControlPlaneError,
} from "@/lib/api/control-plane-error";

export class ControlPlaneQueryError extends Error {
  status: number;
  detail?: unknown;
  requestId?: string;

  constructor(parsed: ParsedControlPlaneError) {
    super(parsed.message);
    this.name = "ControlPlaneQueryError";
    this.status = parsed.status;
    this.detail = parsed.detail;
    this.requestId = parsed.requestId;
  }
}

export async function fetchQueryJson<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(input, {
    cache: "no-store",
    ...init,
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    const parsed = parseControlPlaneError(`Request failed (${response.status}): ${body}`);
    throw new ControlPlaneQueryError(parsed);
  }

  return response.json() as Promise<T>;
}

export function normalizeQueryError(error: unknown): ParsedControlPlaneError {
  if (error instanceof ControlPlaneQueryError) {
    return {
      status: error.status,
      message: error.message,
      detail: error.detail,
      requestId: error.requestId,
    };
  }

  return parseControlPlaneError(error);
}
