import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import {
  getAuthenticatedProjectUser,
  getProjectsBaseData,
} from "@/app/projects/_lib/projects-server";
import { AuthRequiredCard } from "@/components/projects/auth-required-card";
import { ControlPlaneErrorState } from "@/components/projects/control-plane-error-state";
import { ProjectIdCopyBadge } from "@/components/projects/project-id-copy-badge";
import { ProjectSwitcher } from "@/components/projects/project-switcher";
import { WorkspaceUserMenu } from "@/components/projects/workspace-user-menu";

type ProjectWorkspaceLayoutProps = {
  children: ReactNode;
  params: Promise<unknown>;
};

export default async function ProjectWorkspaceLayout({
  children,
  params,
}: ProjectWorkspaceLayoutProps) {
  const resolvedParams = await params;
  if (
    !resolvedParams ||
    typeof resolvedParams !== "object" ||
    !("projectId" in resolvedParams) ||
    typeof resolvedParams.projectId !== "string"
  ) {
    notFound();
  }
  const projectId = resolvedParams.projectId;

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

  const activeProject = baseData.value.projects.find((project) => project.id === projectId);
  if (!activeProject) {
    notFound();
  }

  return (
    <div className="space-y-4">
      <header className="border-b border-[var(--vr-border)] pb-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] tracking-[0.04em] text-[var(--vr-text-dim)]">Project Workspace</p>
            <p className="text-lg font-semibold text-[var(--vr-text-strong)]">{activeProject.name}</p>
          </div>

          <div className="flex items-center gap-3">
            <ProjectSwitcher activeProjectId={activeProject.id} projects={baseData.value.projects} />
            <ProjectIdCopyBadge projectId={activeProject.id} />
            <WorkspaceUserMenu roleLabel="Owner" userEmail={user.email} variant="header" />
          </div>
        </div>
      </header>

      {children}
    </div>
  );
}
