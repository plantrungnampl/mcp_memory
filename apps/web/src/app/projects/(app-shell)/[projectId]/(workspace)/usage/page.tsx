import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { AuthRequiredCard } from "@/components/projects/auth-required-card";
import { UsageAnalyticsPanel } from "@/components/projects/usage-analytics-panel";
import { getUsageAnalytics } from "@/lib/api/control-plane";
import { normalizeUsageRange } from "@/lib/api/usage-range";

type UsagePageProps = {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ range?: string | string[] }>;
};

export default async function ProjectUsagePage({ params, searchParams }: UsagePageProps) {
  const { projectId } = await params;
  const resolvedSearchParams = await searchParams;
  const user = await getAuthenticatedProjectUser();

  if (!user) {
    return <AuthRequiredCard />;
  }

  const range = normalizeUsageRange(resolvedSearchParams.range);
  const analytics = await getUsageAnalytics(user, projectId, range);

  return (
    <UsageAnalyticsPanel
      initialAnalytics={analytics}
      initialRange={range}
      projectId={projectId}
    />
  );
}
