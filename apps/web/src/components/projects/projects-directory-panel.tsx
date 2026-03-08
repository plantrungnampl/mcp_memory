"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import type { ProjectActionState } from "@/app/projects/action-types";
import { ProjectListPlaceholder } from "@/components/project-list-placeholder";
import { resolveSelectedProjectId } from "@/components/projects/project-selection";
import { ControlPlaneErrorState } from "@/components/projects/control-plane-error-state";
import { useProjectsUserEmail } from "@/components/projects/projects-query-provider";
import { WorkspaceUserMenu } from "@/components/projects/workspace-user-menu";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { normalizeQueryError } from "@/lib/query/fetch";
import {
  fetchProjectsDirectory,
  PROJECTS_DIRECTORY_STALE_TIME_MS,
} from "@/lib/query/projects-directory";
import { projectQueryKeys } from "@/lib/query/keys";

type ProjectsDirectoryPanelProps = {
  createProjectAction: (
    prevState: ProjectActionState,
    formData: FormData,
  ) => Promise<ProjectActionState>;
};

export function ProjectsDirectoryPanel({ createProjectAction }: ProjectsDirectoryPanelProps) {
  const userEmail = useProjectsUserEmail();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const directoryQuery = useQuery({
    queryKey: projectQueryKeys.directory(),
    queryFn: fetchProjectsDirectory,
    staleTime: PROJECTS_DIRECTORY_STALE_TIME_MS,
  });

  if (!directoryQuery.data) {
    return (
      <ControlPlaneErrorState
        actionHref="/projects"
        actionLabel="Retry"
        error={directoryQuery.error}
        title="Metadata request failed"
      />
    );
  }

  const directoryError = directoryQuery.isError
    ? normalizeQueryError(directoryQuery.error)
    : null;
  const { projects, overviewRows } = directoryQuery.data;
  const selectedProjectId = resolveSelectedProjectId({
    pathname,
    searchParams,
    projects,
  });
  const activeProject =
    selectedProjectId && selectedProjectId.length > 0
      ? projects.find((project) => project.id === selectedProjectId) ?? null
      : null;

  return (
    <div className="space-y-6">
      <header className="border-b border-[var(--vr-border)] pb-3">
        <div className="flex justify-end">
          <WorkspaceUserMenu roleLabel="Owner" userEmail={userEmail} variant="header" />
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-6">
        <div>
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Control Plane</p>
          <h1 className="mt-1 text-3xl font-black tracking-tight">Projects Directory</h1>
          <p className="mt-1 text-sm text-slate-400">
            Create or select a project, then move into its dedicated workspace tabs.
          </p>
        </div>

        {directoryError ? (
          <div className="rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            Projects directory data may be stale. {directoryError.message}
          </div>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-12">
          <div className="xl:col-span-4">
            <ProjectListPlaceholder
              activeProjectId={activeProject?.id ?? null}
              createProjectAction={createProjectAction}
              projects={projects}
            />
          </div>

          <div className="xl:col-span-8">
            <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/80 text-slate-100">
              <CardHeader>
                <CardDescription className="text-slate-300">Overview (30d)</CardDescription>
                <CardTitle>Project health and activity</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-sm">
                    <thead className="text-[11px] uppercase tracking-[0.14em] text-slate-400">
                      <tr>
                        <th className="px-3 py-2">Project</th>
                        <th className="px-3 py-2">Plan</th>
                        <th className="px-3 py-2">Health</th>
                        <th className="px-3 py-2">VibeTokens</th>
                        <th className="px-3 py-2 text-right">Open</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#7a2dbe]/20">
                      {overviewRows.map((row) => (
                        <tr key={row.id}>
                          <td className="px-3 py-3">
                            <p className="font-semibold text-slate-100">{row.name}</p>
                            <p className="font-mono text-xs text-slate-500">{row.id}</p>
                          </td>
                          <td className="px-3 py-3 uppercase text-slate-300">{row.plan}</td>
                          <td className="px-3 py-3 uppercase text-slate-300">{row.healthStatus}</td>
                          <td className="px-3 py-3 font-mono text-slate-200">
                            {row.vibeTokensWindow.toLocaleString()}
                          </td>
                          <td className="px-3 py-3 text-right">
                            <Button asChild size="sm" variant="outline">
                              <Link href={`/projects/${row.id}/tokens`}>Open</Link>
                            </Button>
                          </td>
                        </tr>
                      ))}
                      {overviewRows.length === 0 ? (
                        <tr>
                          <td className="px-3 py-8 text-center text-slate-400" colSpan={5}>
                            No projects yet.
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
