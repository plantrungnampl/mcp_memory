"use client";

import { useActionState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FolderKanban, Plus } from "lucide-react";

import type { ProjectActionState } from "@/app/projects/action-types";
import type { PlanName, ProjectSummary } from "@/lib/api/types";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type ProjectListPlaceholderProps = {
  projects: ProjectSummary[];
  activeProjectId: string | null;
  createProjectAction: (
    prevState: ProjectActionState,
    formData: FormData,
  ) => Promise<ProjectActionState>;
};

const INITIAL_STATE: ProjectActionState = {
  ok: false,
  message: null,
  nonce: null,
  projectId: null,
  tokenPlaintext: null,
  tokenPrefix: null,
};

const PLAN_STYLES: Record<PlanName, string> = {
  free: "bg-stone-900 text-stone-50",
  pro: "bg-amber-700 text-amber-50",
  team: "bg-emerald-700 text-emerald-50",
};

export function ProjectListPlaceholder({
  projects,
  activeProjectId,
  createProjectAction,
}: ProjectListPlaceholderProps) {
  const router = useRouter();
  const [state, formAction, pending] = useActionState(createProjectAction, INITIAL_STATE);

  useEffect(() => {
    if (state.ok && state.projectId) {
      router.push(`/projects/${state.projectId}/tokens`);
      router.refresh();
    }
  }, [router, state.ok, state.projectId, state.nonce]);

  return (
    <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/78 text-slate-100">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardDescription className="text-slate-400">Projects</CardDescription>
          <CardTitle className="text-slate-200">Workspaces</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          action={formAction}
          className="grid gap-3 rounded-2xl border border-[#7a2dbe]/25 bg-[#1a1325]/70 p-3"
        >
          <label className="text-xs uppercase tracking-[0.2em] text-slate-400" htmlFor="project-name">
            Create project
          </label>
          <div className="flex gap-2">
            <Input
              className="border-[#7a2dbe]/35 bg-[#120e1d] text-slate-100 placeholder:text-slate-500"
              id="project-name"
              name="name"
              placeholder="Team Memory"
            />
            <Button
              className="border-[#7a2dbe]/45 bg-[#120e1d] text-slate-100 hover:bg-[#1d1530]"
              disabled={pending}
              size="sm"
              type="submit"
              variant="outline"
            >
              <Plus className="size-4" />
              {pending ? "Creating..." : "New project"}
            </Button>
          </div>
          {state.message ? (
            <p className="text-xs text-slate-300">{state.message}</p>
          ) : null}
          {state.ok && state.tokenPlaintext ? (
            <div className="rounded-xl border border-emerald-300/40 bg-emerald-900/25 px-3 py-2">
              <p className="text-xs font-medium text-emerald-200">Copy token now (shown once)</p>
              <p className="mt-1 font-mono text-xs text-emerald-100">{state.tokenPlaintext}</p>
            </div>
          ) : null}
        </form>

        {projects.length > 0 ? (
          <div className="grid gap-3">
            {projects.map((project) => {
              const isActive = project.id === activeProjectId;
              return (
                <Link
                  href={`/projects/${project.id}/tokens`}
                  key={project.id}
                  className={`rounded-3xl border px-4 py-4 transition ${
                    isActive
                      ? "border-[#00f5ff]/45 bg-[#1f1730] shadow-[0_0_0_1px_rgba(0,245,255,0.2)]"
                      : "border-[#7a2dbe]/22 bg-[#181127]/80 hover:border-[#7a2dbe]/55"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-slate-100">{project.name}</p>
                      <p className="mt-1 font-mono text-xs text-slate-500">{project.id}</p>
                    </div>
                    <div
                      className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.18em] ${PLAN_STYLES[project.plan]}`}
                    >
                      {project.plan}
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        ) : (
          <div className="rounded-[1.5rem] border border-dashed border-[#7a2dbe]/30 bg-[#1a1325]/60 px-5 py-8 text-center">
            <FolderKanban className="mx-auto size-5 text-slate-400" />
            <p className="mt-4 font-[family:var(--font-heading)] text-2xl text-slate-100">
              No projects yet
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Create the first project to receive a project-scoped MCP endpoint and token.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
