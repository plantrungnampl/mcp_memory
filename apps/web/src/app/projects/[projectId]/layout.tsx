import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import {
  getAuthenticatedProjectUser,
  getProjectsBaseData,
} from "@/app/projects/_lib/projects-server";
import { AuthRequiredCard } from "@/components/projects/auth-required-card";
import { ProjectsWorkspaceShell } from "@/components/projects/projects-workspace-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getUsage } from "@/lib/api/control-plane";

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
    .then((value) => ({ value, error: null as string | null }))
    .catch((error: unknown) => ({
      value: null,
      error: error instanceof Error ? error.message : "Control-plane request failed unexpectedly.",
    }));

  if (baseData.error || !baseData.value) {
    return (
      <main className="min-h-screen bg-[radial-gradient(circle_at_12%_12%,rgba(122,45,190,0.2),transparent_32%),linear-gradient(180deg,#0a0810_0%,#130d1d_100%)] px-4 py-8 md:px-8">
        <div className="mx-auto max-w-4xl">
          <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/80 text-slate-100">
            <CardHeader>
              <CardDescription className="text-slate-300">Control-plane backend</CardDescription>
              <CardTitle>Workspace request failed</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-slate-300">
              <p>{baseData.error}</p>
              <Button asChild variant="outline">
                <Link href="/projects">Back to projects</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </main>
    );
  }

  const activeProject = baseData.value.projects.find((project) => project.id === projectId);
  if (!activeProject) {
    notFound();
  }

  const usageMonthlyResult = await getUsage(user, activeProject.id, "monthly")
    .then((value) => ({ value, error: null as string | null }))
    .catch((error: unknown) => ({
      value: null,
      error: error instanceof Error ? error.message : "Control-plane request failed unexpectedly.",
    }));

  if (usageMonthlyResult.error || !usageMonthlyResult.value) {
    return (
      <main className="min-h-screen bg-[radial-gradient(circle_at_12%_12%,rgba(122,45,190,0.2),transparent_32%),linear-gradient(180deg,#0a0810_0%,#130d1d_100%)] px-4 py-8 md:px-8">
        <div className="mx-auto max-w-4xl">
          <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/80 text-slate-100">
            <CardHeader>
              <CardDescription className="text-slate-300">Control-plane backend</CardDescription>
              <CardTitle>Workspace request failed</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-slate-300">
              <p>{usageMonthlyResult.error}</p>
              <Button asChild variant="outline">
                <Link href="/projects">Back to projects</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </main>
    );
  }

  return (
    <ProjectsWorkspaceShell
      activeProject={activeProject}
      projects={baseData.value.projects}
      view="workspace"
      usageMonthlyVibeTokens={usageMonthlyResult.value.vibeTokens}
      userEmail={user.email}
    >
      {children}
    </ProjectsWorkspaceShell>
  );
}
