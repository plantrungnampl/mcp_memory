import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { AuthRequiredCard } from "@/components/projects/auth-required-card";
import { GraphPlaygroundPanelClient } from "@/components/projects/graph-playground-panel-client";

type GraphPlaygroundPageProps = {
  params: Promise<{ projectId: string }>;
};

export default async function GraphPlaygroundPage({ params }: GraphPlaygroundPageProps) {
  const { projectId } = await params;
  const user = await getAuthenticatedProjectUser();

  if (!user) {
    return <AuthRequiredCard />;
  }

  return <GraphPlaygroundPanelClient projectId={projectId} />;
}
