import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { AuthRequiredCard } from "@/components/projects/auth-required-card";
import { ControlPlaneErrorState } from "@/components/projects/control-plane-error-state";
import { ProjectApiLogsPanel } from "@/components/projects/project-api-logs-panel";
import {
  API_LOGS_PAGE_SIZE,
  buildApiLogsSearchParams,
  normalizeApiLogsSearchState,
} from "@/lib/api/api-logs-search";
import { getProjectApiLogsAnalytics } from "@/lib/api/control-plane";

type ApiLogsPageProps = {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{
    range?: string;
    status_filter?: string;
    tool?: string;
    q?: string;
    cursor?: string;
  }>;
};

function buildRetryHref(projectId: string): string {
  const params = buildApiLogsSearchParams(
    normalizeApiLogsSearchState({
      range: "30d",
      statusFilter: "all",
      tool: null,
      query: null,
      cursor: null,
      limit: API_LOGS_PAGE_SIZE,
    }),
  );
  return `/projects/${projectId}/api-logs?${params.toString()}`;
}

export default async function ProjectApiLogsPage({
  params,
  searchParams,
}: ApiLogsPageProps) {
  const { projectId } = await params;
  const query = await searchParams;
  const user = await getAuthenticatedProjectUser();

  if (!user) {
    return <AuthRequiredCard />;
  }

  const filters = normalizeApiLogsSearchState({
    range: query.range,
    statusFilter: query.status_filter,
    tool: query.tool,
    query: query.q,
    cursor: query.cursor,
    limit: API_LOGS_PAGE_SIZE,
  });

  const analyticsResult = await getProjectApiLogsAnalytics(user, projectId, filters)
    .then((value) => ({ value, error: null as unknown }))
    .catch((error: unknown) => ({
      value: null,
      error,
    }));

  if (analyticsResult.error || !analyticsResult.value) {
    return (
      <ControlPlaneErrorState
        actionHref={buildRetryHref(projectId)}
        actionLabel="Retry"
        error={analyticsResult.error}
        title="API Logs request failed"
      />
    );
  }

  return (
    <ProjectApiLogsPanel
      initialAnalytics={analyticsResult.value}
      initialSearchState={filters}
      projectId={projectId}
    />
  );
}
