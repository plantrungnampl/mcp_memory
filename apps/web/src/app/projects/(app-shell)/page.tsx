import { createProjectAction } from "@/app/projects/actions";
import { ProjectsDirectoryPanel } from "@/components/projects/projects-directory-panel";

export default async function ProjectsPage() {
  return <ProjectsDirectoryPanel createProjectAction={createProjectAction} />;
}
