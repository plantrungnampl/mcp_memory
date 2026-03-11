import {
  createExportAction,
  mintTokenAction,
  revokeTokenAction,
  rotateTokenAction,
} from "@/app/projects/actions";
import { getProjectOpsDashboard } from "@/app/projects/_lib/ops-dashboard";
import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { AuthRequiredCard } from "@/components/projects/auth-required-card";
import { TokenDashboardPanel } from "@/components/projects/token-dashboard-panel";

type TokensPageProps = {
  params: Promise<{ projectId: string }>;
};

export default async function ProjectTokensPage({ params }: TokensPageProps) {
  const { projectId } = await params;
  const user = await getAuthenticatedProjectUser();

  if (!user) {
    return <AuthRequiredCard />;
  }

  const initialData = await getProjectOpsDashboard(user, projectId);

  return (
    <TokenDashboardPanel
      createExportAction={createExportAction}
      initialData={initialData}
      mintTokenAction={mintTokenAction}
      projectId={projectId}
      revokeTokenAction={revokeTokenAction}
      rotateTokenAction={rotateTokenAction}
    />
  );
}
