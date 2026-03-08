import type { ReactNode } from "react";

import { ProjectsWorkspaceSidebar } from "@/components/projects/projects-workspace-sidebar";

type ProjectsWorkspaceShellProps = {
  children: ReactNode;
};

export function ProjectsWorkspaceShell({ children }: ProjectsWorkspaceShellProps) {
  return (
    <main className="min-h-screen bg-[var(--vr-bg-root)] text-[var(--vr-text-strong)]">
      <div className="flex min-h-screen">
        <aside className="hidden w-[260px] shrink-0 border-r border-[var(--vr-border)] bg-[var(--vr-bg-sidebar)] lg:sticky lg:top-0 lg:flex lg:h-screen lg:self-start lg:flex-col lg:overflow-y-auto">
          <div className="space-y-6 px-5 py-6">
            <div className="flex items-center gap-2">
              <div className="size-2 rounded-full bg-[var(--vr-accent-2)]" />
              <p className="font-mono text-[11px] font-semibold tracking-[0.2em] text-[var(--vr-text-strong)]">
                VIBERECALL
              </p>
            </div>
          </div>

          <ProjectsWorkspaceSidebar />
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">{children}</div>
        </section>
      </div>
    </main>
  );
}
