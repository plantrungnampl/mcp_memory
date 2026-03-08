"use client";

import Link from "next/link";
import { ArrowUpRight, Loader2 } from "lucide-react";

import type { ParsedControlPlaneError } from "@/lib/api/control-plane-error";
import type { ProjectTimelinePayload } from "@/lib/api/types";

import { formatDateTime, getParsedErrorText } from "./graph-playground-shared";

type GraphPlaygroundRecentThreadsProps = {
  projectId: string;
  data: ProjectTimelinePayload | undefined;
  isLoading: boolean;
  isError: boolean;
  error: ParsedControlPlaneError | null;
};

export function GraphPlaygroundRecentThreads({
  projectId,
  data,
  isLoading,
  isError,
  error,
}: GraphPlaygroundRecentThreadsProps) {
  const errorText = getParsedErrorText(error);
  const rows = (data?.rows ?? []).slice(0, 6);

  return (
    <section className="rounded-[24px] border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--vr-text-dim)]">
            Recent Threads
          </p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--vr-text-strong)]">Conversation traces behind the graph</h2>
          <p className="mt-1 text-sm text-[var(--vr-text-main)]">
            Compact recent episodes so the graph keeps most of the horizontal space.
          </p>
        </div>
        <Link
          className="inline-flex items-center gap-1 rounded-full border border-[var(--vr-divider)] px-4 py-2 text-sm text-[var(--vr-text-main)] transition hover:bg-[var(--vr-bg-elevated)] hover:text-[var(--vr-text-strong)]"
          href={`/projects/${projectId}/timeline`}
        >
          Open full timeline
          <ArrowUpRight className="size-3.5" />
        </Link>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-4 py-3 text-sm text-[var(--vr-text-dim)]">
          <Loader2 className="size-4 animate-spin" />
          Loading recent threads...
        </div>
      ) : isError ? (
        <div className="rounded-2xl border border-rose-400/25 bg-rose-500/8 px-4 py-4">
          <p className="text-sm text-rose-100">{errorText}</p>
          {error?.requestId ? (
            <p className="mt-2 font-mono text-[11px] text-[var(--vr-text-dim)]">Request ID: {error.requestId}</p>
          ) : null}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-2xl border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-4 py-4 text-sm text-[var(--vr-text-dim)]">
          No recent timeline episodes yet.
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
          {rows.map((episode) => (
            <article
              className="rounded-[20px] border border-[var(--vr-divider)] bg-[var(--vr-graph-overlay)] px-4 py-3"
              key={episode.episodeId}
            >
              <p className="font-mono text-[10px] text-[var(--vr-graph-cyan)]">{episode.episodeId}</p>
              <p className="mt-2 line-clamp-3 text-sm leading-6 text-[var(--vr-text-main)]">
                {episode.summary?.trim() || "No summary available."}
              </p>
              <p className="mt-3 text-[11px] text-[var(--vr-text-dim)]">
                {formatDateTime(episode.referenceTime ?? episode.ingestedAt)}
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
