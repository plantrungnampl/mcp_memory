import type { ProjectsDirectoryPayload } from "@/lib/api/types";
import { fetchQueryJson } from "@/lib/query/fetch";

export const PROJECTS_DIRECTORY_STALE_TIME_MS = 30_000;

export async function fetchProjectsDirectory(): Promise<ProjectsDirectoryPayload> {
  return fetchQueryJson<ProjectsDirectoryPayload>("/api/projects/directory");
}
