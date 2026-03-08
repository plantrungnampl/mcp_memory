const CONTROL_PLANE_ERROR_PATTERN =
  /^Control-plane request failed \((\d{3})\)(?:\s+\[request_id=([^\]]+)\])?:\s*([\s\S]*)$/;
const REQUEST_ERROR_PATTERN = /^Request failed \((\d{3})\):\s*([\s\S]*)$/;

export type ParsedControlPlaneError = {
  status: number;
  message: string;
  detail?: unknown;
  requestId?: string;
};

function tryParseJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function toStatus(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return fallback;
}

function parseStructuredBody(
  body: unknown,
  fallbackStatus: number,
  requestId?: string,
): ParsedControlPlaneError {
  if (!body || typeof body !== "object") {
    return {
      status: fallbackStatus,
      message: "Control-plane request failed.",
      detail: body,
      requestId,
    };
  }

  const detail = "detail" in body ? (body as { detail?: unknown }).detail : body;
  const nestedRequestId =
    "request_id" in body && typeof (body as { request_id?: unknown }).request_id === "string"
      ? (body as { request_id: string }).request_id
      : undefined;
  const message =
    "error" in body && typeof (body as { error?: unknown }).error === "string"
      ? (body as { error: string }).error
      : "message" in body && typeof (body as { message?: unknown }).message === "string"
        ? (body as { message: string }).message
        : "Control-plane request failed.";
  const status =
    "upstream_status" in body
      ? toStatus((body as { upstream_status?: unknown }).upstream_status, fallbackStatus)
      : fallbackStatus;

  return {
    status,
    message,
    detail,
    requestId: requestId ?? nestedRequestId,
  };
}

function parseKnownErrorPattern(
  match: RegExpExecArray | null,
  requestIdIndex?: number,
): ParsedControlPlaneError | null {
  if (!match) {
    return null;
  }

  const status = toStatus(match[1], 500);
  const requestId = requestIdIndex !== undefined ? match[requestIdIndex] || undefined : undefined;
  const bodyIndex = requestIdIndex !== undefined ? requestIdIndex + 1 : 2;
  const rawBody = (match[bodyIndex] ?? "").trim();
  if (rawBody.length === 0) {
    return {
      status,
      message: "Control-plane request failed.",
      requestId,
    };
  }

  const parsedBody = tryParseJson(rawBody);
  return parseStructuredBody(parsedBody, status, requestId);
}

function parseErrorText(value: string): ParsedControlPlaneError {
  const controlPlaneMatch = parseKnownErrorPattern(CONTROL_PLANE_ERROR_PATTERN.exec(value), 2);
  if (controlPlaneMatch) {
    return controlPlaneMatch;
  }

  const requestMatch = parseKnownErrorPattern(REQUEST_ERROR_PATTERN.exec(value));
  if (requestMatch) {
    return requestMatch;
  }

  if (value.trim().length === 0) {
    return {
      status: 500,
      message: "Control-plane request failed unexpectedly.",
    };
  }

  return {
    status: 500,
    message: value,
  };
}

export function parseControlPlaneError(error: unknown): ParsedControlPlaneError {
  if (typeof error === "string") {
    return parseErrorText(error);
  }

  if (!(error instanceof Error)) {
    return {
      status: 500,
      message: "Control-plane request failed unexpectedly.",
    };
  }

  return parseErrorText(error.message);
}
