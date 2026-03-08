"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { createContext, ReactNode, useContext, useState } from "react";

import type { ProjectsDirectoryPayload } from "@/lib/api/types";
import { createQueryClient } from "@/lib/query/client";
import { projectQueryKeys } from "@/lib/query/keys";

const ProjectsUserEmailContext = createContext<string | null>(null);

type ProjectsQueryProviderProps = {
  children: ReactNode;
  initialDirectoryData: ProjectsDirectoryPayload;
  userEmail: string | null;
};

export function ProjectsQueryProvider({
  children,
  initialDirectoryData,
  userEmail,
}: ProjectsQueryProviderProps) {
  const [queryClient] = useState(() => {
    const client = createQueryClient();
    client.setQueryData(projectQueryKeys.directory(), initialDirectoryData);
    return client;
  });

  return (
    <ProjectsUserEmailContext.Provider value={userEmail}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ProjectsUserEmailContext.Provider>
  );
}

export function useProjectsUserEmail(): string | null {
  return useContext(ProjectsUserEmailContext);
}
