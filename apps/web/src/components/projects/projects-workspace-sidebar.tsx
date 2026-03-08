"use client";

import { useQuery } from "@tanstack/react-query";

import { ProjectPlanUsageCard } from "@/components/projects/project-plan-usage-card";
import { useProjectsUserEmail } from "@/components/projects/projects-query-provider";
import { ProjectsWorkspaceNav } from "@/components/projects/projects-workspace-nav";
import { WorkspaceUserMenu } from "@/components/projects/workspace-user-menu";
import {
  fetchProjectsDirectory,
  PROJECTS_DIRECTORY_STALE_TIME_MS,
} from "@/lib/query/projects-directory";
import { projectQueryKeys } from "@/lib/query/keys";

export function ProjectsWorkspaceSidebar() {
  const userEmail = useProjectsUserEmail();
  const directoryQuery = useQuery({
    queryKey: projectQueryKeys.directory(),
    queryFn: fetchProjectsDirectory,
    staleTime: PROJECTS_DIRECTORY_STALE_TIME_MS,
  });
  const projects = directoryQuery.data?.projects ?? [];

  return (
    <>
      <ProjectsWorkspaceNav activeProjectId={null} projects={projects} />

      <div className="mt-auto space-y-4 px-5 pb-5">
        <ProjectPlanUsageCard projects={projects} />
        <div className="h-px bg-[var(--vr-border)]" />
        <WorkspaceUserMenu
          align="left"
          direction="up"
          roleLabel="Owner"
          userEmail={userEmail}
          variant="sidebar"
        />
      </div>
    </>
  );
}
