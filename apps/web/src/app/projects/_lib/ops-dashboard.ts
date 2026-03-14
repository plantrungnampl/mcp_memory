import "server-only";

import type { ProjectOpsDashboardPayload } from "@/lib/api/types";
import {
  getConnection,
  getProjectIndexSummary,
  getProjectApiLogs,
  getProjectExports,
  getProjectTokens,
  getProjectsOverview,
  getUsage,
  getUsageSeries,
  type ControlPlaneUser,
} from "@/lib/api/control-plane";

export async function getProjectOpsDashboard(
  user: ControlPlaneUser,
  projectId: string,
): Promise<ProjectOpsDashboardPayload> {
  const generatedAt = new Date().toISOString();
  const [tokens, connection, usageDaily, usageMonthly, exports] = await Promise.all([
    getProjectTokens(user, projectId),
    getConnection(user, projectId),
    getUsage(user, projectId, "daily"),
    getUsage(user, projectId, "monthly"),
    getProjectExports(user, projectId),
  ]);

  const [usageSeriesResult, logsResult, overviewResult, indexSummaryResult] = await Promise.allSettled([
    getUsageSeries(user, projectId, { windowDays: 30, bucket: "day" }),
    getProjectApiLogs(user, projectId, { limit: 5 }),
    getProjectsOverview(user, { windowDays: 30 }),
    getProjectIndexSummary(user, projectId),
  ]);

  const usageSeries = usageSeriesResult.status === "fulfilled" ? usageSeriesResult.value : null;
  const logs = logsResult.status === "fulfilled" ? logsResult.value.logs : [];
  const overviewRow =
    overviewResult.status === "fulfilled"
      ? overviewResult.value.find((project) => project.id === projectId) ?? null
      : null;
  const indexSummary = indexSummaryResult.status === "fulfilled" ? indexSummaryResult.value : null;

  return {
    generatedAt,
    tokens,
    connection,
    usageDaily,
    usageMonthly,
    usageSeries,
    overviewRow,
    indexSummary,
    logs,
    exports,
  };
}
