import { cn } from "@/lib/utils";

import styles from "./landing-page.module.css";

type GraphTone = "primary" | "accent" | "neutral";

type GraphNode = {
  id: string;
  x: number;
  y: number;
  size: number;
  tone: GraphTone;
  delay: number;
  mobileHidden?: boolean;
};

type GraphEdge = {
  from: string;
  to: string;
  tone: GraphTone;
  width: number;
  delay: number;
  mobileHidden?: boolean;
};

const graphNodes: GraphNode[] = [
  { id: "n1", x: 12, y: 13, size: 10, tone: "primary", delay: 160 },
  { id: "n2", x: 28, y: 19, size: 12, tone: "accent", delay: 320 },
  { id: "n3", x: 46, y: 23, size: 10, tone: "primary", delay: 480 },
  { id: "n4", x: 72, y: 14, size: 12, tone: "neutral", delay: 650 },
  { id: "n5", x: 83, y: 31, size: 9, tone: "accent", delay: 840, mobileHidden: true },
  { id: "n6", x: 63, y: 39, size: 9, tone: "primary", delay: 940 },
  { id: "n7", x: 49, y: 48, size: 8, tone: "accent", delay: 1120 },
  { id: "n8", x: 29, y: 56, size: 10, tone: "primary", delay: 1260 },
  { id: "n9", x: 67, y: 62, size: 8, tone: "accent", delay: 1400 },
  { id: "n10", x: 21, y: 72, size: 9, tone: "primary", delay: 1580 },
  { id: "n11", x: 39, y: 79, size: 8, tone: "accent", delay: 1720, mobileHidden: true },
  { id: "n12", x: 78, y: 74, size: 11, tone: "neutral", delay: 1880 },
];

const graphEdges: GraphEdge[] = [
  { from: "n1", to: "n2", tone: "primary", width: 0.33, delay: 120 },
  { from: "n2", to: "n3", tone: "accent", width: 0.35, delay: 220 },
  { from: "n3", to: "n4", tone: "neutral", width: 0.28, delay: 360 },
  { from: "n4", to: "n5", tone: "accent", width: 0.26, delay: 460, mobileHidden: true },
  { from: "n3", to: "n6", tone: "primary", width: 0.3, delay: 540 },
  { from: "n6", to: "n7", tone: "accent", width: 0.3, delay: 620 },
  { from: "n7", to: "n8", tone: "primary", width: 0.28, delay: 700 },
  { from: "n8", to: "n10", tone: "primary", width: 0.25, delay: 810 },
  { from: "n7", to: "n9", tone: "accent", width: 0.26, delay: 900 },
  { from: "n9", to: "n12", tone: "neutral", width: 0.3, delay: 1020 },
  { from: "n10", to: "n11", tone: "accent", width: 0.24, delay: 1140, mobileHidden: true },
  { from: "n11", to: "n12", tone: "primary", width: 0.24, delay: 1260, mobileHidden: true },
  { from: "n6", to: "n12", tone: "accent", width: 0.24, delay: 1380 },
  { from: "n2", to: "n8", tone: "neutral", width: 0.22, delay: 1520, mobileHidden: true },
  { from: "n1", to: "n7", tone: "primary", width: 0.22, delay: 1640, mobileHidden: true },
  { from: "n4", to: "n9", tone: "accent", width: 0.24, delay: 1760 },
];

const nodeClassMap: Record<GraphTone, string> = {
  primary: styles.graphNodePrimary,
  accent: styles.graphNodeAccent,
  neutral: styles.graphNodeNeutral,
};

const edgeBaseClassMap: Record<GraphTone, string> = {
  primary: styles.graphEdgePrimary,
  accent: styles.graphEdgeAccent,
  neutral: styles.graphEdgeNeutral,
};

const edgeFlowClassMap: Record<GraphTone, string> = {
  primary: styles.graphEdgeFlowPrimary,
  accent: styles.graphEdgeFlowAccent,
  neutral: styles.graphEdgeFlowNeutral,
};

const nodeLookup = new Map(graphNodes.map((node) => [node.id, node]));

export function KnowledgeGraphPanel() {
  return (
    <div className="relative" aria-hidden="true">
      <div className="absolute -inset-10 rounded-full bg-[#7a2dbe]/22 blur-[100px]" />

      <div
        className={cn(
          "relative aspect-square overflow-hidden rounded-2xl border border-white/10 bg-black/45 p-1",
          styles.graphPanel,
        )}
      >
        <div className={styles.graphNoise} />

        <div className="absolute inset-0 flex items-center justify-center opacity-30">
          <div className={cn("size-full rounded-full border border-[#7a2dbe]/20", styles.orbitSlow)} />
          <div className={cn("absolute size-3/4 rounded-full border border-[#00f5ff]/20", styles.orbitMedium)} />
          <div className={cn("absolute size-1/2 rounded-full border border-[#7a2dbe]/20", styles.orbitFast)} />
        </div>

        <svg viewBox="0 0 100 100" className="absolute inset-0 z-10 size-full" role="presentation">
          {graphEdges.map((edge) => {
            const from = nodeLookup.get(edge.from);
            const to = nodeLookup.get(edge.to);

            if (!from || !to) {
              return null;
            }

            return (
              <g key={`${edge.from}-${edge.to}`} className={cn(edge.mobileHidden && styles.mobileHidden)}>
                <line
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  strokeWidth={edge.width}
                  className={cn(styles.graphEdgeBase, edgeBaseClassMap[edge.tone])}
                />
                <line
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  strokeWidth={edge.width + 0.1}
                  className={cn(styles.graphEdgeFlow, edgeFlowClassMap[edge.tone])}
                  style={{ animationDelay: `${edge.delay}ms` }}
                />
              </g>
            );
          })}
        </svg>

        <div className={styles.graphScanSweep} />

        <div className="relative z-20 size-full">
          {graphNodes.map((node) => (
            <span
              key={node.id}
              className={cn(styles.graphNodeAnchor, node.mobileHidden && styles.mobileHidden)}
              style={{ left: `${node.x}%`, top: `${node.y}%`, animationDelay: `${node.delay}ms` }}
            >
              <span
                className={cn(styles.graphNode, nodeClassMap[node.tone])}
                style={{ width: node.size, height: node.size, animationDelay: `${node.delay}ms` }}
              />
            </span>
          ))}
        </div>

        <div className="absolute bottom-8 left-8 z-30 rounded-lg border border-white/10 bg-[#1a1622]/80 p-4 backdrop-blur">
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-slate-400">
            Knowledge Graph v2.4
          </span>
          <div className="mt-2 flex gap-1">
            <div className="h-1 w-8 rounded-full bg-[#7a2dbe]" />
            <div className="h-1 w-4 rounded-full bg-[#00f5ff]" />
          </div>
        </div>
      </div>
    </div>
  );
}
