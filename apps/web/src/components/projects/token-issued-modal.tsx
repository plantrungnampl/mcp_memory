"use client";

import { useEffect } from "react";
import { Copy, X } from "lucide-react";
import { toast } from "sonner";

import { copyTextToClipboard } from "@/lib/copy-to-clipboard";

type TokenIssuedModalProps = {
  open: boolean;
  mode: "mint" | "rotate";
  tokenPlaintext: string;
  endpoint: string | null;
  onClose: () => void;
};

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

export function TokenIssuedModal({
  open,
  mode,
  tokenPlaintext,
  endpoint,
  onClose,
}: TokenIssuedModalProps) {
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
  }, [onClose, open]);

  if (!open) {
    return null;
  }

  const modalTitle = mode === "rotate" ? "Token rotated" : "New token minted";

  return (
    <div
      aria-hidden={false}
      className="fixed inset-0 z-[90] flex items-center justify-center bg-black/70 px-3 py-6 sm:px-6"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
      role="presentation"
    >
      <div
        aria-labelledby="token-modal-title"
        aria-modal="true"
        className="w-full max-w-2xl rounded-2xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5 text-[var(--vr-text-strong)] shadow-[0_25px_80px_rgba(0,0,0,0.45)] sm:p-6"
        role="dialog"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold" id="token-modal-title">
              {modalTitle}
            </h2>
            <p className="mt-1 text-sm text-[var(--vr-text-dim)]">
              Copy the full token now. It is shown once for security.
            </p>
          </div>
          <button
            aria-label="Close token modal"
            className="rounded-md p-1.5 text-[var(--vr-text-dim)] transition hover:bg-[var(--vr-bg-elevated)] hover:text-[var(--vr-text-main)]"
            onClick={onClose}
            type="button"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="mt-5 space-y-3">
          <div className="rounded-lg border border-emerald-400/35 bg-emerald-900/20 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-200">Full Secret Token</p>
            <div className="mt-2 flex items-center justify-between gap-3 rounded-md border border-emerald-300/30 bg-black/20 px-3 py-2">
              <p className="truncate font-mono text-xs text-emerald-100">{tokenPlaintext}</p>
              <button
                className="rounded-md p-1 text-emerald-200 transition hover:bg-emerald-500/20 hover:text-emerald-100"
                onClick={() => copyText(tokenPlaintext, "Token")}
                type="button"
              >
                <Copy className="size-3.5" />
              </button>
            </div>
          </div>

          <div className="rounded-lg border border-[var(--vr-divider)] bg-[var(--vr-bg-root)] p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--vr-text-dim)]">MCP Endpoint</p>
            <div className="mt-2 flex items-center justify-between gap-3 rounded-md border border-[var(--vr-divider)] bg-[var(--vr-bg-input)] px-3 py-2">
              <p className="truncate font-mono text-xs text-[var(--vr-text-muted)]">
                {endpoint ?? "No endpoint available"}
              </p>
              <button
                className="rounded-md p-1 text-[var(--vr-text-dim)] transition hover:bg-[var(--vr-bg-elevated)] hover:text-[var(--vr-text-main)] disabled:cursor-not-allowed disabled:opacity-40"
                disabled={!endpoint}
                onClick={() => {
                  if (endpoint) {
                    void copyText(endpoint, "Endpoint");
                  }
                }}
                type="button"
              >
                <Copy className="size-3.5" />
              </button>
            </div>
          </div>
        </div>

        <div className="mt-5 flex justify-end">
          <button
            className="rounded-md border border-[var(--vr-divider)] bg-[var(--vr-bg-elevated)] px-4 py-2 text-xs font-semibold text-[var(--vr-text-strong)] transition hover:bg-[var(--vr-bg-input)]"
            onClick={onClose}
            type="button"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
