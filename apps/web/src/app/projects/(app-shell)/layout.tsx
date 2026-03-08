import type { ReactNode } from "react";

import {
  getAuthenticatedProjectUser,
  getProjectsBaseData,
} from "@/app/projects/_lib/projects-server";
import { AuthRequiredCard } from "@/components/projects/auth-required-card";
import { ProjectsQueryProvider } from "@/components/projects/projects-query-provider";
import { ControlPlaneErrorState } from "@/components/projects/control-plane-error-state";
import { ProjectsWorkspaceShell } from "@/components/projects/projects-workspace-shell";

type ProjectsAppShellLayoutProps = {
  children: ReactNode;
};

export default async function ProjectsAppShellLayout({ children }: ProjectsAppShellLayoutProps) {
  const user = await getAuthenticatedProjectUser();
  if (!user) {
    return <AuthRequiredCard />;
  }

  const baseData = await getProjectsBaseData(user)
    .then((value) => ({ value, error: null as unknown }))
    .catch((error: unknown) => ({
      value: null,
      error,
    }));

  if (baseData.error || !baseData.value) {
    return (
      <main className="min-h-screen bg-[var(--vr-bg-root)] px-4 py-8 md:px-8">
        <div className="mx-auto max-w-4xl">
          <ControlPlaneErrorState
            actionHref="/projects"
            actionLabel="Back to projects"
            error={baseData.error}
            title="Workspace request failed"
          />
        </div>
      </main>
    );
  }

  return (
    <ProjectsQueryProvider initialDirectoryData={baseData.value} userEmail={user.email}>
      <ProjectsWorkspaceShell>
        {children}
      </ProjectsWorkspaceShell>
    </ProjectsQueryProvider>
  );
}
