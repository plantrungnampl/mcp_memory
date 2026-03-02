import Link from "next/link";

import { createProjectAction } from "@/app/projects/actions";
import {
  getAuthenticatedProjectUser,
  getProjectsBaseData,
} from "@/app/projects/_lib/projects-server";
import { AuthRequiredCard } from "@/components/projects/auth-required-card";
import { ProjectsWorkspaceShell } from "@/components/projects/projects-workspace-shell";
import { ProjectListPlaceholder } from "@/components/project-list-placeholder";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getUsage } from "@/lib/api/control-plane";

type ProjectsPageProps = {
  searchParams: Promise<{ project?: string }>;
};

export default async function ProjectsPage({ searchParams }: ProjectsPageProps) {
  const params = await searchParams;
  const selectedProjectId = params.project?.trim() ?? null;

  const user = await getAuthenticatedProjectUser();
  if (!user) {
    return <AuthRequiredCard />;
  }

  const dataResult = await getProjectsBaseData(user)
    .then((value) => ({ value, error: null as string | null }))
    .catch((error: unknown) => ({
      value: null,
      error: error instanceof Error ? error.message : "Control-plane request failed unexpectedly.",
    }));

  if (dataResult.error || !dataResult.value) {
    return (
      <main className="min-h-screen bg-[radial-gradient(circle_at_12%_12%,rgba(122,45,190,0.2),transparent_32%),linear-gradient(180deg,#0a0810_0%,#130d1d_100%)] px-4 py-8 md:px-8">
        <div className="mx-auto max-w-4xl">
          <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/80 text-slate-100">
            <CardHeader>
              <CardDescription className="text-slate-300">Control-plane backend</CardDescription>
              <CardTitle>Metadata request failed</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-slate-300">
              <p>{dataResult.error}</p>
              <Button asChild variant="outline">
                <Link href="/projects">Retry</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </main>
    );
  }

  const { projects, overviewRows } = dataResult.value;
  const activeProject =
    selectedProjectId && selectedProjectId.length > 0
      ? projects.find((project) => project.id === selectedProjectId) ?? null
      : null;
  const usageMonthlyVibeTokens = activeProject
    ? await getUsage(user, activeProject.id, "monthly")
        .then((value) => value.vibeTokens)
        .catch(() => null)
    : null;

  return (
    <ProjectsWorkspaceShell
      activeProject={activeProject}
      projects={projects}
      usageMonthlyVibeTokens={usageMonthlyVibeTokens}
      userEmail={user.email}
      view="directory"
    >
      <div className="mx-auto max-w-7xl space-y-6">
        <div>
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Control Plane</p>
          <h1 className="mt-1 text-3xl font-black tracking-tight">Projects Directory</h1>
          <p className="mt-1 text-sm text-slate-400">
            Create or select a project, then move into its dedicated workspace tabs.
          </p>
        </div>

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
    </ProjectsWorkspaceShell>
  );
}
