import type { ProjectIndexSummary } from "@/lib/api/types";

type ProjectIndexUiTone = "neutral" | "warning" | "danger" | "success";

export type ProjectIndexUiState = {
  badgeLabel: string;
  headline: string;
  body: string;
  tone: ProjectIndexUiTone;
};

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "unknown time";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function getProjectIndexUiState(summary: ProjectIndexSummary | null | undefined): ProjectIndexUiState {
  if (!summary) {
    return {
      badgeLabel: "Index unavailable",
      headline: "Code index status is unavailable right now",
      body: "The control plane could not confirm the latest code index state for this project.",
      tone: "neutral",
    };
  }

  switch (summary.status) {
    case "missing":
      return {
        badgeLabel: "No index yet",
        headline: "There is no READY code index snapshot for this project",
        body: "Code-aware retrieval stays memory-only until the first trusted index run completes.",
        tone: "neutral",
      };
    case "queued":
      return {
        badgeLabel: "Index queued",
        headline: "A code index run has been accepted and is waiting to start",
        body: `Queued at ${formatTimestamp(summary.queuedAt)}. Wait for the worker to pick it up before expecting code topology.`,
        tone: "neutral",
      };
    case "running":
      return {
        badgeLabel: "Index building",
        headline: "A code index run is currently building this project snapshot",
        body: `Started at ${formatTimestamp(summary.startedAt)}. Code topology will appear after the run becomes READY.`,
        tone: "neutral",
      };
    case "stalled":
      return {
        badgeLabel: "Index stalled",
        headline: "The latest code index run appears stuck",
        body: "The worker or queue may be unavailable. Check worker health, queue delivery, or API logs before retrying.",
        tone: "warning",
      };
    case "failed":
      return {
        badgeLabel: "Index failed",
        headline: "The last code index run failed",
        body: summary.errorMessage ?? "Retry indexing after reviewing the backend error and worker logs.",
        tone: "danger",
      };
    case "ready":
      return {
        badgeLabel: "Index ready",
        headline: "The latest code index snapshot is ready",
        body: `Last indexed at ${formatTimestamp(summary.latestReadyAt)}.`,
        tone: "success",
      };
  }
}
