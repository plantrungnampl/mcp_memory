"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Copy, ExternalLink, KeyRound, Link as LinkIcon, X } from "lucide-react";
import { toast } from "sonner";

import { copyTextToClipboard } from "@/lib/copy-to-clipboard";
import { Button } from "@/components/ui/button";

type McpClientKey = "codex" | "claude" | "cursor" | "cline";

type McpSnippet = {
  key: McpClientKey;
  label: string;
  pathHint: string;
  language: "toml" | "json";
  content: string;
};

type ProjectCreatedMcpModalProps = {
  open: boolean;
  projectId: string;
  endpoint: string;
  tokenPlaintext: string;
  onClose: () => void;
  onOpenProject: () => void;
};

function escapeTomlString(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function buildSnippets(endpoint: string, tokenPlaintext: string): McpSnippet[] {
  const authHeader = `Bearer ${tokenPlaintext}`;

  const codexToml = [
    "[mcp_servers.viberecall]",
    `url = "${escapeTomlString(endpoint)}"`,
    `http_headers = { Authorization = "${escapeTomlString(authHeader)}" }`,
  ].join("\n");

  const claudeJson = JSON.stringify(
    {
      mcpServers: {
        viberecall: {
          type: "http",
          url: endpoint,
          headers: {
            Authorization: authHeader,
          },
        },
      },
    },
    null,
    2,
  );

  const cursorJson = JSON.stringify(
    {
      mcpServers: {
        viberecall: {
          url: endpoint,
          headers: {
            Authorization: authHeader,
          },
        },
      },
    },
    null,
    2,
  );

  const clineJson = JSON.stringify(
    {
      mcpServers: {
        viberecall: {
          type: "streamableHttp",
          url: endpoint,
          headers: {
            Authorization: authHeader,
          },
          disabled: false,
        },
      },
    },
    null,
    2,
  );

  return [
    {
      key: "codex",
      label: "Codex",
      pathHint: "~/.codex/config.toml",
      language: "toml",
      content: codexToml,
    },
    {
      key: "claude",
      label: "Claude",
      pathHint: ".mcp.json",
      language: "json",
      content: claudeJson,
    },
    {
      key: "cursor",
      label: "Cursor",
      pathHint: ".cursor/mcp.json",
      language: "json",
      content: cursorJson,
    },
    {
      key: "cline",
      label: "Cline",
      pathHint: "cline_mcp_settings.json",
      language: "json",
      content: clineJson,
    },
  ];
}

async function copyText(content: string, label: string): Promise<void> {
  try {
    const copied = await copyTextToClipboard(content);
    if (!copied) {
      throw new Error("copy failed");
    }
    toast.success(`${label} copied.`);
  } catch {
    toast.error(`Unable to copy ${label.toLowerCase()}.`);
  }
}

function buildActiveClientBundle(input: {
  projectId: string;
  endpoint: string;
  tokenPlaintext: string;
  snippet: McpSnippet;
}): string {
  const { projectId, endpoint, tokenPlaintext, snippet } = input;
  return [
    "VibeRecall MCP Setup",
    `Project ID: ${projectId}`,
    `Endpoint: ${endpoint}`,
    `Token: ${tokenPlaintext}`,
    `Client: ${snippet.label}`,
    `Config file: ${snippet.pathHint}`,
    "",
    snippet.content,
  ].join("\n");
}

export function ProjectCreatedMcpModal({
  open,
  projectId,
  endpoint,
  tokenPlaintext,
  onClose,
  onOpenProject,
}: ProjectCreatedMcpModalProps) {
  const [activeClient, setActiveClient] = useState<McpClientKey>("codex");

  useEffect(() => {
    if (!open) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose]);

  const snippets = useMemo(
    () => buildSnippets(endpoint, tokenPlaintext),
    [endpoint, tokenPlaintext],
  );

  const activeSnippet = snippets.find((item) => item.key === activeClient) ?? snippets[0];
  const activeBundle = useMemo(
    () =>
      buildActiveClientBundle({
        projectId,
        endpoint,
        tokenPlaintext,
        snippet: activeSnippet,
      }),
    [activeSnippet, endpoint, projectId, tokenPlaintext],
  );

  if (!open) {
    return null;
  }

  return (
    <div
      aria-hidden={false}
      className="fixed inset-0 z-[80] flex items-center justify-center overflow-y-auto bg-black/70 px-3 py-6 sm:px-6"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
      role="presentation"
    >
      <div
        aria-labelledby="mcp-modal-title"
        aria-modal="true"
        className="w-full max-w-4xl overflow-hidden rounded-2xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] text-[var(--vr-text-strong)] shadow-[0_25px_80px_rgba(0,0,0,0.45)]"
        role="dialog"
      >
        <div className="flex items-start justify-between gap-4 border-b border-[var(--vr-border)] px-5 py-4 sm:px-6">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--vr-text-dim)]">Project created</p>
            <h2 className="mt-1 text-xl font-semibold" id="mcp-modal-title">
              MCP connection details
            </h2>
            <p className="mt-1 text-sm text-[var(--vr-text-main)]">
              Copy this token now. It is shown only once after project creation.
            </p>
          </div>
          <button
            aria-label="Close MCP setup modal"
            className="rounded-md border border-[var(--vr-divider)] p-2 text-[var(--vr-text-main)] transition hover:border-[var(--vr-accent-2)] hover:text-[var(--vr-text-strong)]"
            onClick={onClose}
            type="button"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="max-h-[80vh] space-y-4 overflow-y-auto overflow-x-hidden px-5 py-4 sm:px-6">
          <div className="grid gap-3 md:grid-cols-3">
            <button
              className="group rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-elevated)] p-3 text-left transition hover:border-[var(--vr-accent)]/45"
              onClick={() => copyText(projectId, "Project ID")}
              type="button"
            >
              <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--vr-text-dim)]">Project ID</p>
              <p className="mt-2 truncate font-mono text-xs text-[var(--vr-text-main)]">{projectId}</p>
              <p className="mt-2 inline-flex items-center gap-1 text-xs text-[var(--vr-accent-2)]">
                <Copy className="size-3" />
                Copy
              </p>
            </button>

            <button
              className="group rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-elevated)] p-3 text-left transition hover:border-[var(--vr-accent)]/45"
              onClick={() => copyText(endpoint, "Endpoint")}
              type="button"
            >
              <p className="inline-flex items-center gap-1 text-[11px] uppercase tracking-[0.16em] text-[var(--vr-text-dim)]">
                <LinkIcon className="size-3" />
                Endpoint
              </p>
              <p className="mt-2 truncate font-mono text-xs text-[var(--vr-text-main)]">{endpoint}</p>
              <p className="mt-2 inline-flex items-center gap-1 text-xs text-[var(--vr-accent-2)]">
                <Copy className="size-3" />
                Copy
              </p>
            </button>

            <button
              className="group rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-elevated)] p-3 text-left transition hover:border-[var(--vr-accent)]/45"
              onClick={() => copyText(tokenPlaintext, "Token")}
              type="button"
            >
              <p className="inline-flex items-center gap-1 text-[11px] uppercase tracking-[0.16em] text-[var(--vr-text-dim)]">
                <KeyRound className="size-3" />
                Token
              </p>
              <p className="mt-2 truncate font-mono text-xs text-[var(--vr-text-main)]">{tokenPlaintext}</p>
              <p className="mt-2 inline-flex items-center gap-1 text-xs text-[var(--vr-accent-2)]">
                <Copy className="size-3" />
                Copy
              </p>
            </button>
          </div>

          <div className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-elevated)] p-3">
            <div className="flex flex-wrap gap-2">
              {snippets.map((snippet) => {
                const active = activeClient === snippet.key;
                return (
                  <button
                    className={`rounded-md border px-3 py-1.5 text-xs font-medium transition ${
                      active
                        ? "border-[var(--vr-accent)]/70 bg-[var(--vr-accent)]/20 text-[var(--vr-text-strong)]"
                        : "border-[var(--vr-divider)] bg-[var(--vr-bg-card)] text-[var(--vr-text-main)] hover:border-[var(--vr-accent)]/45"
                    }`}
                    key={snippet.key}
                    onClick={() => setActiveClient(snippet.key)}
                    type="button"
                  >
                    {snippet.label}
                  </button>
                );
              })}
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-[var(--vr-text-main)]">
                Config file: <span className="font-mono text-[var(--vr-text-strong)]">{activeSnippet.pathHint}</span>
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  className="border-[var(--vr-accent)]/50 bg-[var(--vr-bg-card)] text-[var(--vr-text-main)] hover:bg-[var(--vr-bg-input)]"
                  onClick={() => copyText(activeBundle, "Active setup bundle")}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  <Copy className="size-4" />
                  Copy all
                </Button>
                <Button
                  className="border-[var(--vr-accent)]/50 bg-[var(--vr-bg-card)] text-[var(--vr-text-main)] hover:bg-[var(--vr-bg-input)]"
                  onClick={() => copyText(activeSnippet.content, `${activeSnippet.label} config`)}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  <Copy className="size-4" />
                  Copy config
                </Button>
              </div>
            </div>

            <div className="mt-3 overflow-hidden rounded-lg border border-[var(--vr-divider)] bg-[var(--vr-bg-input)]">
              <div className="flex items-center justify-between border-b border-[var(--vr-divider)] px-3 py-2 text-[11px] uppercase tracking-[0.14em] text-[var(--vr-text-dim)]">
                <span>{activeSnippet.label} ({activeSnippet.language})</span>
                <span className="inline-flex items-center gap-1 text-[var(--vr-text-main)]">
                  <Check className="size-3" />
                  Ready to paste
                </span>
              </div>
              <pre className="max-h-[340px] overflow-auto p-3 font-mono text-xs text-[var(--vr-text-main)]">
                <code>{activeSnippet.content}</code>
              </pre>
            </div>

          </div>
        </div>

        <div className="flex flex-wrap justify-end gap-2 border-t border-[var(--vr-border)] px-5 py-4 sm:px-6">
          <Button
            className="border-[var(--vr-divider)] bg-[var(--vr-bg-elevated)] text-[var(--vr-text-main)] hover:bg-[var(--vr-bg-input)]"
            onClick={onClose}
            type="button"
            variant="outline"
          >
            Close
          </Button>
          <Button
            className="bg-[var(--vr-accent)] text-white hover:bg-[var(--vr-accent-2)]"
            onClick={onOpenProject}
            type="button"
          >
            Open project
            <ExternalLink className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
