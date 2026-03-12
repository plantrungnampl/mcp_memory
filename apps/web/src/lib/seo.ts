import { publicEnv } from "@/lib/env";

export const BRAND_NAME = "VibeRecall";
export const CONTROL_PLANE_TITLE = "VibeRecall Control Plane";
export const CONTROL_PLANE_DESCRIPTION = "Project-scoped MCP memory infrastructure for coding agents.";
export const MARKETING_PAGE_TITLE = "VibeRecall | Long-term Memory for Coding Agents";
export const MARKETING_DESCRIPTION =
  "Long-term memory infrastructure for coding agents. VibeRecall gives Codex, Claude Code, Cursor, and MCP-native workflows persistent project context across sessions.";
export const MARKETING_KEYWORDS = [
  "coding agent memory",
  "MCP memory",
  "persistent memory for coding agents",
  "long-term memory for AI agents",
  "Codex memory",
  "Claude Code memory",
  "project-scoped MCP",
  "developer tools",
] as const;
export const DOCS_QUICKSTART_PATH = "/getting-started/quickstart";
export const GITHUB_REPO_URL = "https://github.com/plantrungnampl/mcp_memory";

export function getAppUrl(path = "/"): string {
  return new URL(path, publicEnv.appUrl).toString();
}

export function getDocsUrl(path = "/"): string {
  return new URL(path, publicEnv.docsUrl).toString();
}

export function getMetadataBase(): URL {
  return new URL(publicEnv.appUrl);
}

export function sanitizeJsonLd(value: unknown): string {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}
