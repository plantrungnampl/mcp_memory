"use client";

import { useMemo } from "react";
import { Copy } from "lucide-react";
import { toast } from "sonner";

type QuickIntegrationCredentialsProps = {
  endpoint: string | null;
  tokenFallback: string | null;
};

function normalizeValue(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function maskTokenPreview(value: string): string {
  if (value.length <= 7) {
    return `${value.slice(0, 2)}*****`;
  }
  return `${value.slice(0, 3)}*****${value.slice(-4)}`;
}

async function copyText(content: string | null, label: string): Promise<void> {
  if (!content) {
    toast.error(`No ${label.toLowerCase()} available.`);
    return;
  }
  try {
    await navigator.clipboard.writeText(content);
    toast.success(`${label} copied.`);
  } catch {
    toast.error(`Unable to copy ${label.toLowerCase()}.`);
  }
}

export function QuickIntegrationCredentials({
  endpoint,
  tokenFallback,
}: QuickIntegrationCredentialsProps) {
  const endpointValue = normalizeValue(endpoint);
  const tokenFallbackValue = normalizeValue(tokenFallback);
  const tokenDisplay = useMemo(
    () => (tokenFallbackValue ? maskTokenPreview(tokenFallbackValue) : "No token provisioned yet"),
    [tokenFallbackValue],
  );

  return (
    <>
      <div className="space-y-1">
        <p className="text-[11px] font-medium text-[var(--vr-text-dim)]">MCP Endpoint</p>
        <div className="flex items-center justify-between rounded-md border border-[var(--vr-divider)] bg-[var(--vr-bg-root)] px-3 py-2">
          <p className="truncate font-mono text-xs text-[var(--vr-text-muted)]">
            {endpointValue ?? "No endpoint available"}
          </p>
          <button
            aria-label="Copy MCP endpoint"
            className="rounded-md p-1 text-[var(--vr-text-dim)] transition hover:bg-[var(--vr-bg-elevated)] hover:text-[var(--vr-text-main)] disabled:cursor-not-allowed disabled:opacity-40"
            disabled={!endpointValue}
            onClick={() => copyText(endpointValue, "Endpoint")}
            type="button"
          >
            <Copy className="size-3.5" />
          </button>
        </div>
      </div>

      <div className="space-y-1">
        <p className="text-[11px] font-medium text-[var(--vr-text-dim)]">Secret Token</p>
        <div className="flex items-center justify-between rounded-md border border-[var(--vr-divider)] bg-[var(--vr-bg-root)] px-3 py-2">
          <p className="truncate font-mono text-xs text-[var(--vr-text-muted)]">{tokenDisplay}</p>
          <button
            aria-label="Copy secret token"
            className="rounded-md p-1 text-[var(--vr-text-dim)] opacity-40"
            disabled
            type="button"
          >
            <Copy className="size-3.5" />
          </button>
        </div>
        <p className="text-[10px] text-[var(--vr-text-faint)]">
          Preview only. Full token is shown once in the mint/rotate modal.
        </p>
      </div>
    </>
  );
}
