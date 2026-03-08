import type { ReactNode } from "react";

import "./projects-theme.css";

type ProjectsLayoutProps = {
  children: ReactNode;
};

export default function ProjectsLayout({ children }: ProjectsLayoutProps) {
  return <div className="vr-projects-scope">{children}</div>;
}
