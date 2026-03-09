import type { ApiLogsRange, ApiLogsStatusFilter, GraphViewMode, UsageRange } from "@/lib/api/types";

export const projectQueryKeys = {
  directory() {
    return ["projects", "directory"] as const;
  },
  usageMonthly(projectId: string | null) {
    return ["projects", projectId, "usage", "monthly"] as const;
  },
  usageAnalytics(projectId: string, range: UsageRange) {
    return ["projects", projectId, "usage", "analytics", range] as const;
  },
  graph(projectId: string, input: { mode: GraphViewMode; last30Days: boolean; maxNodes: number; maxEdges: number }) {
    return ["projects", projectId, "graph", input] as const;
  },
  graphTimeline(projectId: string) {
    return ["projects", projectId, "graph", "timeline"] as const;
  },
  graphEntityDetail(projectId: string, entityId: string | null, mode: GraphViewMode) {
    return ["projects", projectId, "graph", mode, "entity", entityId] as const;
  },
  opsDashboard(projectId: string) {
    return ["projects", projectId, "ops-dashboard"] as const;
  },
  timeline(projectId: string, input: { limit: number; initialOffset: number }) {
    return ["projects", projectId, "timeline", input] as const;
  },
  apiLogsAnalytics(
    projectId: string,
    input: {
      range: ApiLogsRange;
      statusFilter: ApiLogsStatusFilter;
      tool: string | null;
      query: string | null;
      cursor: string | null;
      limit: number;
    },
  ) {
    return ["projects", projectId, "api-logs", "analytics", input] as const;
  },
} as const;
