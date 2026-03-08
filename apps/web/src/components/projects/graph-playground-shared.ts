"use client";

import Graph from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";
import noverlap from "graphology-layout-noverlap";
import type { Sigma } from "sigma";

import type { ParsedControlPlaneError } from "@/lib/api/control-plane-error";
import type { ProjectGraphPayload } from "@/lib/api/types";

export type SigmaNodeAttributes = {
  label: string;
  color: string;
  size: number;
  x: number;
  y: number;
  entityType: string;
  factCount: number;
};

export type SigmaEdgeAttributes = {
  label: string;
  color: string;
  size: number;
  weight: number;
  episodeCount: number;
  relationshipType: string;
};

export type HoverNodeState = {
  nodeId: string;
  x: number;
  y: number;
};

export type HoverEdgeState = {
  edgeId: string;
  x: number;
  y: number;
};

function ensureFiniteNodePositions(graph: Graph<SigmaNodeAttributes, SigmaEdgeAttributes>): void {
  let fallbackIndex = 0;
  graph.forEachNode((node, attributes) => {
    const hasValidX = typeof attributes.x === "number" && Number.isFinite(attributes.x);
    const hasValidY = typeof attributes.y === "number" && Number.isFinite(attributes.y);
    if (hasValidX && hasValidY) {
      fallbackIndex += 1;
      return;
    }

    const angle = (fallbackIndex + 1) * (Math.PI / 6);
    const radius = 8 + (fallbackIndex % 12);
    graph.mergeNodeAttributes(node, {
      x: hasValidX ? attributes.x : Math.cos(angle) * radius,
      y: hasValidY ? attributes.y : Math.sin(angle) * radius,
    });
    fallbackIndex += 1;
  });
}

export function colorForEntityType(type: string): string {
  const normalized = type.toLowerCase();
  if (normalized.includes("file") || normalized.includes("module")) {
    return "#59C7FF";
  }
  if (normalized.includes("decision") || normalized.includes("person")) {
    return "#C57CFF";
  }
  if (normalized.includes("event")) {
    return "#F5BC67";
  }
  if (normalized.includes("place") || normalized.includes("location")) {
    return "#4ED7A7";
  }
  return "#7B8CFF";
}

export function formatDateTime(value: string | null): string {
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

function toErrorDetailText(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim().length > 0) {
    return detail.trim();
  }
  if (detail && typeof detail === "object") {
    try {
      return JSON.stringify(detail);
    } catch {
      return null;
    }
  }
  return null;
}

export function getParsedErrorText(parsed: ParsedControlPlaneError | null): string {
  return toErrorDetailText(parsed?.detail) ?? parsed?.message ?? "Control-plane request failed unexpectedly.";
}

export function isGraphDependencyUnavailable(parsed: ParsedControlPlaneError | null): boolean {
  if (!parsed || parsed.status !== 503) {
    return false;
  }

  const detail = (toErrorDetailText(parsed.detail) ?? "").toLowerCase();
  return (
    detail.includes("graph dependency check failed") ||
    detail.includes("falkordb") ||
    detail.includes("connection refused") ||
    detail.includes("localhost:6380")
  );
}

export function createGraphologyGraph(payload: ProjectGraphPayload): Graph<SigmaNodeAttributes, SigmaEdgeAttributes> {
  const graph = new Graph<SigmaNodeAttributes, SigmaEdgeAttributes>({ type: "undirected", multi: false });
  const count = payload.nodes.length || 1;

  payload.nodes.forEach((node, index) => {
    const ratio = (index + 1) / count;
    const angle = ratio * Math.PI * 2;
    graph.addNode(node.entityId, {
      label: node.name,
      color: colorForEntityType(node.type),
      size: Math.max(5, Math.min(26, 5 + Math.sqrt(node.factCount + 1) * 2.1)),
      x: Math.cos(angle) * (6 + (index % 10)),
      y: Math.sin(angle) * (6 + (index % 10)),
      entityType: node.type,
      factCount: node.factCount,
    });
  });

  payload.edges.forEach((edge) => {
    if (!graph.hasNode(edge.sourceEntityId) || !graph.hasNode(edge.targetEntityId)) {
      return;
    }
    if (graph.hasEdge(edge.edgeId)) {
      return;
    }

    graph.addEdgeWithKey(edge.edgeId, edge.sourceEntityId, edge.targetEntityId, {
      label: edge.label,
      color: "rgba(123, 140, 255, 0.14)",
      size: Math.max(1, Math.min(6, 0.8 + edge.weight * 0.18)),
      weight: edge.weight,
      episodeCount: edge.episodeCount,
      relationshipType: edge.type,
    });
  });

  if (graph.order > 1) {
    try {
      forceAtlas2.assign(graph, {
        iterations: 140,
        settings: {
          ...forceAtlas2.inferSettings(graph),
          gravity: 0.2,
          scalingRatio: 3.8,
          slowDown: 1.8,
        },
      });
      noverlap.assign(graph, {
        maxIterations: 140,
        settings: {
          margin: 4,
          ratio: 1.18,
        },
      });
    } catch {
      // Layout is best effort only.
    }
  }

  ensureFiniteNodePositions(graph);

  return graph;
}

export function downloadJson(filename: string, payload: unknown): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function downloadPngFromSigma(
  sigma: Sigma<SigmaNodeAttributes, SigmaEdgeAttributes> | null,
  filename: string,
): void {
  if (!sigma) {
    return;
  }
  const layers = Object.values(sigma.getCanvases());
  if (layers.length === 0) {
    return;
  }

  const width = layers[0].width;
  const height = layers[0].height;
  const exportCanvas = document.createElement("canvas");
  exportCanvas.width = width;
  exportCanvas.height = height;
  const context = exportCanvas.getContext("2d");
  if (!context) {
    return;
  }

  for (const layer of layers) {
    context.drawImage(layer, 0, 0);
  }

  const url = exportCanvas.toDataURL("image/png");
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
}
