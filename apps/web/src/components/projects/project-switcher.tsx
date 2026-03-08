"use client";

import { ChevronDown } from "lucide-react";
import { useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { PROJECT_STORAGE_KEY } from "@/components/projects/project-selection";
import type { ProjectSummary } from "@/lib/api/types";

function extractPathProjectId(pathname: string): string | null {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length < 2 || segments[0] !== "projects") {
    return null;
  }
  return segments[1] ?? null;
}

type ProjectSwitcherProps = {
  projects: ProjectSummary[];
  activeProjectId: string | null;
};

export function ProjectSwitcher({ projects, activeProjectId }: ProjectSwitcherProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathProjectId = extractPathProjectId(pathname);
  const queryProjectId = searchParams.get("project");

  const knownProjectIds = useMemo(() => new Set(projects.map((project) => project.id)), [projects]);

  const selectedProjectId =
    pathProjectId && knownProjectIds.has(pathProjectId)
      ? pathProjectId
      : queryProjectId && knownProjectIds.has(queryProjectId)
        ? queryProjectId
        : null;

  const value = selectedProjectId ?? activeProjectId ?? projects[0]?.id ?? "";

  function handleChange(nextProjectId: string): void {
    if (!knownProjectIds.has(nextProjectId)) {
      return;
    }
    window.localStorage.setItem(PROJECT_STORAGE_KEY, nextProjectId);

    const segments = pathname.split("/").filter(Boolean);
    const suffix = segments[0] === "projects" && pathProjectId ? segments.slice(2).join("/") : "";
    if (suffix.length > 0) {
      router.push(`/projects/${nextProjectId}/${suffix}`);
      return;
    }
    router.push(`/projects/${nextProjectId}/tokens`);
  }

  return (
    <div className="relative min-w-[190px]">
      <select
        aria-label="Active project"
        className="h-9 w-full appearance-none rounded-md border border-[var(--vr-divider)] bg-[var(--vr-bg-elevated)] px-3 pr-8 text-xs font-medium text-[var(--vr-text-strong)] outline-none transition focus:border-[var(--vr-accent)]"
        disabled={projects.length === 0}
        onChange={(event) => handleChange(event.target.value)}
        value={value}
      >
        {projects.length === 0 ? (
          <option value="">No projects available</option>
        ) : null}
        {projects.map((project) => (
          <option key={project.id} value={project.id}>
            {project.name}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-3.5 -translate-y-1/2 text-[var(--vr-text-dim)]" />
    </div>
  );
}
