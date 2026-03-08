import type { ApiLogsRange, ApiLogsStatusFilter } from "@/lib/api/types";

export const API_LOGS_PAGE_SIZE = 5;
export const API_LOGS_RANGE_OPTIONS: ApiLogsRange[] = ["24h", "7d", "30d", "90d", "all"];

export type ApiLogsSearchState = {
  range: ApiLogsRange;
  statusFilter: ApiLogsStatusFilter;
  tool: string | null;
  query: string | null;
  cursor: string | null;
  limit: number;
};

export function normalizeApiLogsRange(value: string | null | undefined): ApiLogsRange {
  if (value && API_LOGS_RANGE_OPTIONS.includes(value as ApiLogsRange)) {
    return value as ApiLogsRange;
  }
  return "30d";
}

export function normalizeApiLogsStatusFilter(
  value: string | null | undefined,
): ApiLogsStatusFilter {
  if (value === "success" || value === "error" || value === "all") {
    return value;
  }
  return "all";
}

export function normalizeOptionalSearchValue(value: string | null | undefined): string | null {
  const normalized = value?.trim() ?? "";
  return normalized.length > 0 ? normalized : null;
}

export function normalizeApiLogsLimit(value: string | number | null | undefined): number {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return Math.floor(value);
  }

  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isNaN(parsed) && parsed > 0) {
      return parsed;
    }
  }

  return API_LOGS_PAGE_SIZE;
}

export function normalizeApiLogsSearchState(input: {
  range?: string | null;
  statusFilter?: string | null;
  tool?: string | null;
  query?: string | null;
  cursor?: string | null;
  limit?: string | number | null;
}): ApiLogsSearchState {
  return {
    range: normalizeApiLogsRange(input.range),
    statusFilter: normalizeApiLogsStatusFilter(input.statusFilter),
    tool: normalizeOptionalSearchValue(input.tool),
    query: normalizeOptionalSearchValue(input.query),
    cursor: normalizeOptionalSearchValue(input.cursor),
    limit: normalizeApiLogsLimit(input.limit),
  };
}

export function buildApiLogsSearchParams(input: ApiLogsSearchState): URLSearchParams {
  const params = new URLSearchParams();
  params.set("range", input.range);
  params.set("status_filter", input.statusFilter);
  params.set("limit", String(input.limit));
  if (input.tool) {
    params.set("tool", input.tool);
  }
  if (input.query) {
    params.set("q", input.query);
  }
  if (input.cursor) {
    params.set("cursor", input.cursor);
  }
  return params;
}
