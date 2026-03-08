"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type ProjectDetailTabsProps = {
  projectId: string;
};

const TAB_ITEMS = [
  {
    key: "graph",
    label: "Graph Playground",
    href: (projectId: string) => `/projects/${projectId}/graphs/playground`,
  },
  {
    key: "timeline",
    label: "Timeline",
    href: (projectId: string) => `/projects/${projectId}/timeline`,
  },
  { key: "usage", label: "Usage", href: (projectId: string) => `/projects/${projectId}/usage` },
] as const;

function tabClassName(active: boolean): string {
  if (active) {
    return "inline-flex items-center rounded-md border border-[var(--vr-accent)]/35 bg-[var(--vr-accent)]/20 px-3 py-1.5 text-xs font-semibold text-[var(--vr-text-strong)]";
  }
  return "inline-flex items-center rounded-md px-3 py-1.5 text-xs font-medium text-[var(--vr-text-dim)] transition hover:bg-[var(--vr-bg-elevated)] hover:text-[var(--vr-text-main)]";
}

export function ProjectDetailTabs({ projectId }: ProjectDetailTabsProps) {
  const pathname = usePathname();

  return (
    <section className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-3">
      <nav className="flex flex-wrap items-center gap-1">
        {TAB_ITEMS.map((item) => {
          const href = item.href(projectId);
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link className={tabClassName(active)} href={href} key={item.key}>
              {item.label}
            </Link>
          );
        })}
      </nav>
    </section>
  );
}
