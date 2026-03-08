"use client";

import dynamic from "next/dynamic";

type GraphPlaygroundPanelClientProps = {
  projectId: string;
};

const GraphPlaygroundPanelNoSSR = dynamic(
  () => import("./graph-playground-panel").then((module) => module.GraphPlaygroundPanel),
  {
    ssr: false,
    loading: () => (
      <div className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6 text-sm text-[var(--vr-text-dim)]">
        Loading Graph Playground...
      </div>
    ),
  },
);

export function GraphPlaygroundPanelClient({ projectId }: GraphPlaygroundPanelClientProps) {
  return <GraphPlaygroundPanelNoSSR projectId={projectId} />;
}
