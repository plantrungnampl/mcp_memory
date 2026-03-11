"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useSearchParams } from "next/navigation";

import { resolveSelectedProjectId } from "@/components/projects/project-selection";
import type { PlanName, ProjectSummary, UsageSummary } from "@/lib/api/types";
import { fetchQueryJson } from "@/lib/query/fetch";
import { projectQueryKeys } from "@/lib/query/keys";

const PLAN_QUOTA: Record<PlanName, number> = {
  free: 100_000,
  pro: 5_000_000,
  team: 20_000_000,
};

type ProjectPlanUsageCardProps = {
  projects: ProjectSummary[];
};

async function fetchUsageMonthly(projectId: string): Promise<UsageSummary> {
  const payload = await fetchQueryJson<{ usage: UsageSummary }>(
    `/api/projects/${projectId}/usage?period=monthly`,
  );
  return payload.usage;
}

export function ProjectPlanUsageCard({ projects }: ProjectPlanUsageCardProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const selectedProjectId = resolveSelectedProjectId({
    pathname,
    searchParams,
    projects,
  });
  const selectedProject = selectedProjectId
    ? projects.find((project) => project.id === selectedProjectId) ?? null
    : null;

  const usageQuery = useQuery({
    queryKey: projectQueryKeys.usageMonthly(selectedProjectId),
    queryFn: () => fetchUsageMonthly(selectedProjectId as string),
    enabled: Boolean(selectedProjectId),
    staleTime: 30_000,
  });

  const usageQuota = selectedProject ? PLAN_QUOTA[selectedProject.plan] : null;
  const safeUsageTokens = usageQuery.data?.vibeTokens ?? 0;
  const usagePct =
    usageQuota === null
      ? 0
      : Math.min(100, Math.round((safeUsageTokens / Math.max(usageQuota, 1)) * 100));
  const cardLabel = selectedProject ? "Usage this month" : "No project";
  const detailLabel =
    selectedProject && usageQuota !== null
      ? `${safeUsageTokens.toLocaleString()} / ${usageQuota.toLocaleString()} VibeTokens`
      : "Select project to load usage data.";

  return (
    <div className="rounded-[10px] border border-[var(--vr-border)] bg-[var(--vr-bg-elevated)] p-4">
      <div className="mb-2 flex items-center justify-between text-xs font-semibold">
        <span className="text-[var(--vr-text-main)]">{cardLabel}</span>
        <span className="font-mono text-[var(--vr-accent-2)]">{selectedProject ? `${usagePct}%` : "--"}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[var(--vr-divider)]">
        <div
          className="h-full rounded-full bg-gradient-to-r from-[var(--vr-accent)] to-[var(--vr-accent-2)]"
          style={{ width: `${usagePct}%` }}
        />
      </div>
      <p className="mt-2 text-[11px] text-[var(--vr-text-dim)]">{detailLabel}</p>
      {usageQuery.isError ? (
        <p className="mt-1 text-[10px] text-rose-300">Usage unavailable</p>
      ) : null}
    </div>
  );
}
