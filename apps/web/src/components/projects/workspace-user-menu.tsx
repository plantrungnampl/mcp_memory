"use client";

import { LogOut } from "lucide-react";
import { useEffect, useRef, useState } from "react";

type WorkspaceUserMenuProps = {
  userEmail: string | null;
  roleLabel?: string;
  variant: "sidebar" | "header";
  align?: "left" | "right";
  direction?: "up" | "down";
};

function avatarInitial(userEmail: string | null): string {
  return (userEmail ?? "U").trim().charAt(0).toUpperCase() || "U";
}

export function WorkspaceUserMenu({
  userEmail,
  roleLabel = "Owner",
  variant,
  align = "right",
  direction = "down",
}: WorkspaceUserMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    function handleOutside(event: MouseEvent) {
      if (!rootRef.current) {
        return;
      }
      const target = event.target;
      if (target instanceof Node && !rootRef.current.contains(target)) {
        setOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    }

    window.addEventListener("mousedown", handleOutside);
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("mousedown", handleOutside);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  const emailLabel = userEmail ?? "unknown";
  const baseMenuClassName =
    "absolute z-50 rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-2 shadow-[0_20px_44px_rgba(0,0,0,0.4)]";
  const placementClassName =
    variant === "sidebar"
      ? [
          baseMenuClassName,
          "left-0 right-0 w-auto",
          direction === "up" ? "bottom-full mb-2" : "top-full mt-2",
        ].join(" ")
      : [
          baseMenuClassName,
          "w-60",
          align === "left" ? "left-0" : "right-0",
          direction === "up" ? "bottom-full mb-2" : "top-full mt-2",
        ].join(" ");

  return (
    <div className="relative" ref={rootRef}>
      {variant === "sidebar" ? (
        <button
          aria-expanded={open}
          aria-haspopup="menu"
          className="flex w-full items-center gap-3 rounded-lg px-1 py-1.5 text-left transition hover:bg-[var(--vr-bg-elevated)]"
          onClick={() => setOpen((current) => !current)}
          ref={buttonRef}
          type="button"
        >
          <div className="flex size-8 items-center justify-center rounded-full bg-[var(--vr-accent)] text-xs font-semibold text-[var(--vr-text-strong)]">
            {avatarInitial(userEmail)}
          </div>
          <div className="min-w-0">
            <p className="truncate text-xs text-[var(--vr-text-main)]">{emailLabel}</p>
            <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--vr-text-dim)]">{roleLabel}</p>
          </div>
        </button>
      ) : (
        <button
          aria-expanded={open}
          aria-haspopup="menu"
          className="flex items-center gap-2 rounded-full border border-[var(--vr-divider)] bg-[var(--vr-bg-elevated)] px-2 py-1 transition hover:bg-[var(--vr-bg-card)]"
          onClick={() => setOpen((current) => !current)}
          ref={buttonRef}
          type="button"
        >
          <div className="flex size-6 items-center justify-center rounded-full bg-[var(--vr-accent)] text-[10px] font-semibold text-[var(--vr-text-strong)]">
            {avatarInitial(userEmail)}
          </div>
          <p className="pr-1 text-xs text-[var(--vr-text-main)]">{emailLabel}</p>
        </button>
      )}

      {open ? (
        <div className={placementClassName} role="menu">
          <div className="mb-2 flex items-center gap-2 rounded-lg bg-[var(--vr-bg-elevated)] px-2.5 py-2">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-[var(--vr-accent)] text-[11px] font-semibold text-[var(--vr-text-strong)]">
              {avatarInitial(userEmail)}
            </div>
            <div className="min-w-0">
              <p className="truncate text-xs text-[var(--vr-text-main)]">{emailLabel}</p>
              <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--vr-text-dim)]">{roleLabel}</p>
            </div>
          </div>
          <form action="/auth/logout" method="post">
            <button
              className="inline-flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-xs text-rose-300 transition hover:bg-rose-500/12 hover:text-rose-200"
              role="menuitem"
              type="submit"
            >
              <LogOut className="size-3.5" />
              Logout
            </button>
          </form>
        </div>
      ) : null}
    </div>
  );
}
