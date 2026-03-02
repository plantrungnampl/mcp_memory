import { Activity } from "lucide-react";
import type { ReactNode } from "react";

import type { PlanName, ProjectSummary } from "@/lib/api/types";

import { ProjectsWorkspaceNav } from "@/components/projects/projects-workspace-nav";

type ProjectsWorkspaceShellProps = {
  children: ReactNode;
  projects: ProjectSummary[];
  activeProject: ProjectSummary | null;
  usageMonthlyVibeTokens: number | null;
  userEmail: string | null;
  view: "directory" | "workspace";
};

const PLAN_QUOTA: Record<PlanName, number> = {
  free: 100_000,
  pro: 5_000_000,
  team: 20_000_000,
};

export function ProjectsWorkspaceShell({
  children,
  projects,
  activeProject,
  usageMonthlyVibeTokens,
  userEmail,
  view,
}: ProjectsWorkspaceShellProps) {
  const planQuota = activeProject ? PLAN_QUOTA[activeProject.plan] : null;
  const safeUsageTokens = usageMonthlyVibeTokens ?? 0;
  const usagePct =
    planQuota === null
      ? 0
      : Math.min(100, Math.round((safeUsageTokens / Math.max(planQuota, 1)) * 100));

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_15%_15%,rgba(122,45,190,0.28),transparent_30%),radial-gradient(circle_at_85%_10%,rgba(0,245,255,0.14),transparent_24%),linear-gradient(180deg,#0a0810_0%,#130d1d_100%)] text-slate-100">
      <div className="flex min-h-screen">
        <aside className="hidden w-64 shrink-0 border-r border-[#7a2dbe]/25 bg-[#110d1a]/80 backdrop-blur lg:flex lg:flex-col">
          <div className="border-b border-[#7a2dbe]/20 px-5 py-5">
            <div className="flex items-center gap-3">
              <div className="flex size-8 items-center justify-center rounded-md bg-[#7a2dbe]/25 shadow-[0_0_20px_rgba(122,45,190,0.5)]">
                <Activity className="size-4 text-[#00f5ff]" />
              </div>
              <p className="text-base font-bold tracking-tight text-[#d8bbff]">VibeRecall</p>
            </div>
          </div>

          <ProjectsWorkspaceNav activeProjectId={activeProject?.id ?? null} projects={projects} />

          <div className="border-t border-[#7a2dbe]/20 p-4">
            <div className="rounded-xl border border-[#7a2dbe]/35 bg-[#7a2dbe]/10 p-3">
              <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-[0.14em] text-[#dcbfff]">
                <span>{activeProject ? `${activeProject.plan} plan` : "No project selected"}</span>
                <span>{activeProject ? `${usagePct}%` : "--"}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-800/70">
                <div className="h-full rounded-full bg-[#7a2dbe]" style={{ width: `${usagePct}%` }} />
              </div>
              {activeProject && planQuota !== null ? (
                <p className="mt-2 text-[11px] text-slate-300">
                  {safeUsageTokens.toLocaleString()} / {planQuota.toLocaleString()} VibeTokens
                </p>
              ) : (
                <p className="mt-2 text-[11px] text-slate-300">
                  Pick a project in sidebar to sync the directory and workspace tabs.
                </p>
              )}
            </div>
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          {view === "workspace" ? (
            <header className="border-b border-[#7a2dbe]/20 bg-[#0f0a17]/75 px-4 py-4 backdrop-blur md:px-8">
              <div className="flex flex-wrap items-center justify-between gap-3 md:gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Project Workspace</p>
                  <p className="text-sm font-semibold text-slate-100">{activeProject?.name ?? "Unknown project"}</p>
                  <p className="font-mono text-[11px] text-slate-500">
                    {activeProject?.id ?? "Project context unavailable"}
                  </p>
                </div>

                <div className="flex items-center gap-2 rounded-md border border-[#7a2dbe]/30 bg-[#1a1325] px-3 py-2">
                  <div className="hidden text-right text-[11px] md:block">
                    <p className="font-semibold text-slate-200">{userEmail ?? "unknown"}</p>
                    <p className="uppercase tracking-[0.16em] text-slate-400">Owner</p>
                  </div>
                  <div className="flex size-8 items-center justify-center rounded-full bg-[#7a2dbe]/25 text-xs font-bold text-[#00f5ff]">
                    {(userEmail ?? "U").charAt(0).toUpperCase()}
                  </div>
                </div>
              </div>
            </header>
          ) : null}

          {view === "directory" ? (
            <header className="border-b border-[#7a2dbe]/20 bg-[#0f0a17]/55 px-4 py-3 backdrop-blur md:px-8">
              <div className="flex justify-end">
                <div className="flex items-center gap-2 rounded-md border border-[#7a2dbe]/30 bg-[#1a1325] px-3 py-2">
                  <div className="hidden text-right text-[11px] md:block">
                    <p className="font-semibold text-slate-200">{userEmail ?? "unknown"}</p>
                    <p className="uppercase tracking-[0.16em] text-slate-400">Owner</p>
                  </div>
                  <div className="flex size-8 items-center justify-center rounded-full bg-[#7a2dbe]/25 text-xs font-bold text-[#00f5ff]">
                    {(userEmail ?? "U").charAt(0).toUpperCase()}
                  </div>
                </div>
              </div>
            </header>
          ) : null}

          <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">{children}</div>
        </section>
      </div>
    </main>
  );
}
