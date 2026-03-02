import { notFound } from "next/navigation";

import {
  getProjects,
  getProjectsOverview,
  type ControlPlaneUser,
} from "@/lib/api/control-plane";
import type { ProjectOverviewRow, ProjectSummary } from "@/lib/api/types";
import { getServerSupabaseClient } from "@/lib/supabase/server";

export type AuthenticatedProjectUser = ControlPlaneUser & {
  email: string | null;
};

export async function getAuthenticatedProjectUser(): Promise<AuthenticatedProjectUser | null> {
  const supabase = await getServerSupabaseClient();
  const auth = supabase ? await supabase.auth.getUser() : { data: { user: null } };
  const authUser = auth.data.user;

  if (!authUser) {
    return null;
  }

  return {
    id: authUser.id,
    email: authUser.email ?? null,
  };
}

export async function getProjectsBaseData(
  user: ControlPlaneUser,
): Promise<{ projects: ProjectSummary[]; overviewRows: ProjectOverviewRow[] }> {
  const [projects, overviewRows] = await Promise.all([
    getProjects(user),
    getProjectsOverview(user, { windowDays: 30 }),
  ]);

  return { projects, overviewRows };
}

export function resolveActiveProject(
  projects: ProjectSummary[],
  projectId: string,
): ProjectSummary {
  const activeProject = projects.find((project) => project.id === projectId);
  if (!activeProject) {
    notFound();
  }
  return activeProject;
}
