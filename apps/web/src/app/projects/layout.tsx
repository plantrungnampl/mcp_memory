import type { Metadata } from "next";
import type { ReactNode } from "react";

import { CONTROL_PLANE_TITLE } from "@/lib/seo";

import "./projects-theme.css";

type ProjectsLayoutProps = {
  children: ReactNode;
};

export const metadata: Metadata = {
  title: {
    default: CONTROL_PLANE_TITLE,
    template: `%s | ${CONTROL_PLANE_TITLE}`,
  },
  robots: {
    index: false,
    follow: false,
    googleBot: {
      index: false,
      follow: false,
      noimageindex: true,
      "max-image-preview": "none",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
};

export default function ProjectsLayout({ children }: ProjectsLayoutProps) {
  return <div className="vr-projects-scope">{children}</div>;
}
