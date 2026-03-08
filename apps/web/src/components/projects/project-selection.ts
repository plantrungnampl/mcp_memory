import type { ReadonlyURLSearchParams } from "next/navigation";

import type { ProjectSummary } from "@/lib/api/types";

export const PROJECT_STORAGE_KEY = "viberecall:lastProjectId";

export function extractPathProjectId(pathname: string): string | null {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length < 2 || segments[0] !== "projects") {
    return null;
  }
  return segments[1] ?? null;
}

export function resolveSelectedProjectId(input: {
  pathname: string;
  searchParams: ReadonlyURLSearchParams;
  projects: ProjectSummary[];
}): string | null {
  const { pathname, searchParams, projects } = input;
  const knownProjectIds = new Set(projects.map((project) => project.id));
  const isDirectoryPath = pathname === "/projects";

  const pathProjectId = extractPathProjectId(pathname);
  if (!isDirectoryPath) {
    return pathProjectId;
  }

  const queryProjectId = searchParams.get("project");
  return queryProjectId && knownProjectIds.has(queryProjectId) ? queryProjectId : null;
}
