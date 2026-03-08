import type { ReactNode } from "react";

import { ProjectDetailTabs } from "@/components/projects/project-detail-tabs";

type ProjectWorkspaceTabsLayoutProps = {
  children: ReactNode;
  params: Promise<{ projectId: string }>;
};

export default async function ProjectWorkspaceTabsLayout({
  children,
  params,
}: ProjectWorkspaceTabsLayoutProps) {
  const { projectId } = await params;

  return (
    <div className="space-y-4">
      <ProjectDetailTabs projectId={projectId} />
      {children}
    </div>
  );
}
