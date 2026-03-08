"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Activity, BarChart3, FolderKanban, Orbit, TerminalSquare } from "lucide-react";
import type { ComponentType, MouseEvent } from "react";
import { useEffect, useMemo } from "react";

import { PROJECT_STORAGE_KEY, resolveSelectedProjectId } from "@/components/projects/project-selection";
import type { ProjectSummary } from "@/lib/api/types";

type ProjectsWorkspaceNavProps = {
  projects: ProjectSummary[];
  activeProjectId: string | null;
};

type NavItem = {
  id: "projects" | "tokens" | "graphPlayground" | "usage" | "apiLogs";
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  disabled?: boolean;
};

function itemClassName(active: boolean, disabled?: boolean): string {
  if (disabled) {
    return "flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-slate-500";
  }
  if (active) {
    return "flex items-center gap-3 rounded-md border border-[#7a2dbe]/35 bg-[#7a2dbe]/18 px-3 py-2 text-[#ebd9ff]";
  }
  return "flex items-center gap-3 rounded-md px-3 py-2 text-slate-300 hover:bg-[#7a2dbe]/10";
}

export function ProjectsWorkspaceNav({ projects, activeProjectId }: ProjectsWorkspaceNavProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const isDirectoryPath = pathname === "/projects";
  const knownProjectIds = useMemo(() => new Set(projects.map((project) => project.id)), [projects]);
  const selectedProjectId = resolveSelectedProjectId({
    pathname,
    searchParams,
    projects,
  });

  const navProjectId = selectedProjectId ?? activeProjectId ?? projects[0]?.id ?? null;

  useEffect(() => {
    if (!navProjectId) {
      return;
    }
    window.localStorage.setItem(PROJECT_STORAGE_KEY, navProjectId);
  }, [navProjectId]);

  useEffect(() => {
    if (!isDirectoryPath || selectedProjectId || projects.length === 0) {
      return;
    }
    const storedProjectId = window.localStorage.getItem(PROJECT_STORAGE_KEY);
    if (!storedProjectId || !knownProjectIds.has(storedProjectId)) {
      return;
    }
    const params = new URLSearchParams(searchParams.toString());
    params.set("project", storedProjectId);
    const nextQuery = params.toString();
    window.history.replaceState(null, "", nextQuery ? `/projects?${nextQuery}` : "/projects");
  }, [
    isDirectoryPath,
    knownProjectIds,
    projects.length,
    searchParams,
    selectedProjectId,
  ]);

  function handleProjectChange(nextProjectId: string): void {
    if (!knownProjectIds.has(nextProjectId)) {
      return;
    }

    window.localStorage.setItem(PROJECT_STORAGE_KEY, nextProjectId);

    if (isDirectoryPath) {
      const params = new URLSearchParams(searchParams.toString());
      params.set("project", nextProjectId);
      const nextQuery = params.toString();
      window.history.replaceState(null, "", nextQuery ? `/projects?${nextQuery}` : "/projects");
      return;
    }

    const segments = pathname.split("/").filter(Boolean);
    const suffix = segments[0] === "projects" ? segments.slice(2).join("/") : "";
    if (suffix.length > 0) {
      router.push(`/projects/${nextProjectId}/${suffix}`);
      return;
    }

    router.push(`/projects/${nextProjectId}/tokens`);
  }

  const navItems: NavItem[] = [
    {
      id: "projects",
      href: "/projects",
      label: "Projects",
      icon: FolderKanban,
    },
    {
      id: "tokens",
      href: navProjectId ? `/projects/${navProjectId}/tokens` : "/projects",
      label: "VibeTokens",
      icon: BarChart3,
      disabled: !navProjectId,
    },
    {
      id: "graphPlayground",
      href: navProjectId ? `/projects/${navProjectId}/graphs/playground` : "/projects",
      label: "Graphs / Playground",
      icon: Orbit,
      disabled: !navProjectId,
    },
    {
      id: "usage",
      href: navProjectId ? `/projects/${navProjectId}/usage` : "/projects",
      label: "Usage Analytics",
      icon: Activity,
      disabled: !navProjectId,
    },
    {
      id: "apiLogs",
      href: navProjectId ? `/projects/${navProjectId}/api-logs` : "/projects",
      label: "API Logs",
      icon: TerminalSquare,
      disabled: !navProjectId,
    },
  ];

  return (
    <nav className="flex-1 space-y-2 p-4 text-sm">
      <div className="mb-4 rounded-md border border-[#7a2dbe]/25 bg-[#19122a]/60 p-3">
        <label
          className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.12em] text-[#dcbfff]"
          htmlFor="sidebar-project-select"
        >
          Active project
        </label>
        <select
          className="w-full rounded-md border border-[#7a2dbe]/35 bg-[#110d1a] px-2 py-2 text-xs text-slate-100 outline-none transition focus:border-[#00f5ff]/70"
          disabled={projects.length === 0}
          id="sidebar-project-select"
          onChange={(event) => handleProjectChange(event.target.value)}
          value={selectedProjectId ?? ""}
        >
          <option disabled value="">
            {projects.length === 0 ? "No projects available" : "Select a project"}
          </option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </div>

      {navItems.map((item) => {
        const isActive = (() => {
          if (item.id === "projects") {
            return pathname === "/projects";
          }
          if (item.disabled) {
            return false;
          }
          return pathname === item.href || pathname.startsWith(`${item.href}/`);
        })();
        const Icon = item.icon;
        return (
          <Link
            aria-disabled={item.disabled}
            className={itemClassName(isActive, item.disabled)}
            href={item.href}
            key={item.id}
            onClick={item.disabled ? (event: MouseEvent<HTMLAnchorElement>) => event.preventDefault() : undefined}
          >
            <Icon className="size-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
