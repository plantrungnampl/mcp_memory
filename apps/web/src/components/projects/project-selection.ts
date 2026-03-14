import type { ReadonlyURLSearchParams } from "next/navigation";

import type { ProjectSummary } from "@/lib/api/types";

export const PROJECT_STORAGE_KEY = "viberecall:lastProjectId";
type SearchParamsLike = Pick<ReadonlyURLSearchParams, "get">;

type ResolveProjectNavigationStateInput = {
  pathname: string;
  queryProjectId: string | null;
  projects: ProjectSummary[];
  activeProjectId?: string | null;
  storedProjectId?: string | null;
};

type ResolveProjectNavigationStateResult = {
  selectedProjectId: string | null;
  resolvedProjectId: string | null;
  shouldHydrateDirectoryQuery: boolean;
};

export function extractPathProjectId(pathname: string): string | null {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length < 2 || segments[0] !== "projects") {
    return null;
  }
  return segments[1] ?? null;
}

export function resolveProjectNavigationState(
  input: ResolveProjectNavigationStateInput,
): ResolveProjectNavigationStateResult {
  const {
    pathname,
    queryProjectId,
    projects,
    activeProjectId = null,
    storedProjectId = null,
  } = input;
  const knownProjectIds = new Set(projects.map((project) => project.id));
  const isDirectoryPath = pathname === "/projects";

  const pathProjectId = extractPathProjectId(pathname);
  const selectedProjectId = !isDirectoryPath
    ? pathProjectId
    : queryProjectId && knownProjectIds.has(queryProjectId)
      ? queryProjectId
      : null;

  const validActiveProjectId =
    activeProjectId && knownProjectIds.has(activeProjectId) ? activeProjectId : null;
  const validStoredProjectId =
    storedProjectId && knownProjectIds.has(storedProjectId) ? storedProjectId : null;
  const fallbackProjectId = projects[0]?.id ?? null;

  return {
    selectedProjectId,
    resolvedProjectId:
      selectedProjectId ?? validActiveProjectId ?? validStoredProjectId ?? fallbackProjectId,
    shouldHydrateDirectoryQuery:
      isDirectoryPath && !selectedProjectId && Boolean(validStoredProjectId),
  };
}

export function resolveSelectedProjectId(input: {
  pathname: string;
  searchParams: SearchParamsLike;
  projects: ProjectSummary[];
}): string | null {
  const { pathname, searchParams, projects } = input;
  return resolveProjectNavigationState({
    pathname,
    queryProjectId: searchParams.get("project"),
    projects,
  }).selectedProjectId;
}
