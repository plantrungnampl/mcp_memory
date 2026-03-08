import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { AuthRequiredCard } from "@/components/projects/auth-required-card";
import { ProjectTimelinePanel } from "@/components/projects/project-timeline-panel";
import { getProjectTimeline } from "@/lib/api/control-plane";

type TimelinePageProps = {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ offset?: string | string[] }>;
};

function parseOffset(value: string | string[] | undefined): number {
  const raw = Array.isArray(value) ? value[0] : value;
  if (!raw) {
    return 0;
  }
  const parsed = Number.parseInt(raw, 10);
  if (Number.isNaN(parsed) || parsed < 0) {
    return 0;
  }
  return parsed;
}

export default async function ProjectTimelinePage({ params, searchParams }: TimelinePageProps) {
  const { projectId } = await params;
  const resolvedSearch = await searchParams;
  const user = await getAuthenticatedProjectUser();

  if (!user) {
    return <AuthRequiredCard />;
  }

  const offset = parseOffset(resolvedSearch.offset);
  const timeline = await getProjectTimeline(user, projectId, { limit: 50, offset });

  return (
    <ProjectTimelinePanel
      initialOffset={offset}
      initialTimeline={timeline}
      projectId={projectId}
    />
  );
}
