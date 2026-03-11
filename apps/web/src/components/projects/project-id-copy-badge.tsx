"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";

import { copyTextToClipboard } from "@/lib/copy-to-clipboard";

type ProjectIdCopyBadgeProps = {
  projectId: string;
};

export function ProjectIdCopyBadge({ projectId }: ProjectIdCopyBadgeProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy(): Promise<void> {
    const ok = await copyTextToClipboard(projectId);
    if (!ok) {
      toast.error("Unable to copy project id.");
      return;
    }

    setCopied(true);
    toast.success("Project ID copied.");
    window.setTimeout(() => {
      setCopied(false);
    }, 1500);
  }

  return (
    <button
      aria-label="Copy project ID"
      className="flex items-center gap-1 rounded-md bg-[var(--vr-bg-elevated)] px-2.5 py-1.5 text-left transition hover:bg-[var(--vr-bg-input)]"
      onClick={() => {
        void handleCopy();
      }}
      type="button"
    >
      <p className="font-mono text-[11px] text-[var(--vr-text-dim)]">ID: {projectId}</p>
      {copied ? (
        <Check className="size-3 text-emerald-400" />
      ) : (
        <Copy className="size-3 text-[var(--vr-text-dim)]" />
      )}
    </button>
  );
}
