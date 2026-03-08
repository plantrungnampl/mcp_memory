"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { CalendarClock, Clock3, Loader2 } from "lucide-react";
import { useMemo } from "react";

import type { ProjectTimelinePayload } from "@/lib/api/types";
import { fetchQueryJson, normalizeQueryError } from "@/lib/query/fetch";
import { projectQueryKeys } from "@/lib/query/keys";

type ProjectTimelinePanelProps = {
  projectId: string;
  initialOffset: number;
  initialTimeline: ProjectTimelinePayload;
};

const TIMELINE_PAGE_SIZE = 50;

function displayTime(value: string | null): string {
  if (!value) {
    return "n/a";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ProjectTimelinePanel({
  projectId,
  initialOffset,
  initialTimeline,
}: ProjectTimelinePanelProps) {
  const timelineQuery = useInfiniteQuery({
    queryKey: projectQueryKeys.timeline(projectId, {
      limit: TIMELINE_PAGE_SIZE,
      initialOffset,
    }),
    queryFn: ({ pageParam }) =>
      fetchQueryJson<ProjectTimelinePayload>(
        `/api/projects/${projectId}/timeline?limit=${TIMELINE_PAGE_SIZE}&offset=${pageParam}`,
      ),
    initialPageParam: initialOffset,
    initialData: {
      pages: [initialTimeline],
      pageParams: [initialOffset],
    },
    getNextPageParam: (lastPage) => lastPage.nextOffset ?? undefined,
    staleTime: 30_000,
  });

  const rows = useMemo(
    () => timelineQuery.data.pages.flatMap((page) => page.rows),
    [timelineQuery.data],
  );
  const timelineError = timelineQuery.isError
    ? normalizeQueryError(timelineQuery.error)
    : null;

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs text-[var(--vr-text-dim)]">{projectId}</p>
            <h1 className="text-xl font-semibold text-[var(--vr-text-strong)]">Timeline</h1>
          </div>
          <div className="inline-flex items-center gap-2 rounded-md border border-[var(--vr-divider)] px-3 py-1.5 text-xs text-[var(--vr-text-dim)]">
            <CalendarClock className="size-3.5" />
            {rows.length.toLocaleString()} episodes loaded
          </div>
        </div>
      </section>

      {timelineError ? (
        <div className="rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          Timeline data may be stale. {timelineError.message}
        </div>
      ) : null}

      <section className="space-y-3">
        {rows.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--vr-divider)] bg-[var(--vr-bg-card)] px-5 py-10 text-center text-sm text-[var(--vr-text-dim)]">
            Chưa có memory nào. Hãy chat với AI để bắt đầu xây graph.
          </div>
        ) : (
          rows.map((episode) => (
            <article
              className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] px-5 py-4"
              key={episode.episodeId}
            >
              <div className="mb-2 flex items-center justify-between gap-3">
                <p className="font-mono text-xs text-[var(--vr-accent-2)]">{episode.episodeId}</p>
                <span className="inline-flex items-center gap-1 text-xs text-[var(--vr-text-dim)]">
                  <Clock3 className="size-3.5" />
                  {displayTime(episode.referenceTime ?? episode.ingestedAt)}
                </span>
              </div>
              <p className="text-sm text-[var(--vr-text-main)]">
                {episode.summary?.trim() || "No summary available for this episode."}
              </p>
            </article>
          ))
        )}
      </section>

      {timelineQuery.hasNextPage ? (
        <div className="flex justify-center">
          <button
            className="inline-flex items-center gap-2 rounded-md border border-[var(--vr-divider)] px-3 py-2 text-sm text-[var(--vr-text-main)] transition hover:bg-[var(--vr-bg-elevated)] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={timelineQuery.isFetchingNextPage}
            onClick={() => void timelineQuery.fetchNextPage()}
            type="button"
          >
            {timelineQuery.isFetchingNextPage ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Loading...
              </>
            ) : (
              "Load more"
            )}
          </button>
        </div>
      ) : null}
    </div>
  );
}
