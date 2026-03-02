import Link from "next/link";
import { ReactNode } from "react";

import { Button } from "@/components/ui/button";

type AppShellProps = {
  children: ReactNode;
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
};

export function AppShell({
  children,
  eyebrow,
  title,
  description,
  actions,
}: AppShellProps) {
  return (
    <main className="relative min-h-screen overflow-hidden px-6 py-8 md:px-10">
      <div className="mesh-orb mesh-orb-left" />
      <div className="mesh-orb mesh-orb-right" />

      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 rounded-[2rem] border border-black/10 bg-[rgba(255,251,245,0.78)] p-6 shadow-[0_30px_120px_rgba(33,24,14,0.08)] backdrop-blur md:p-10">
        <header className="flex flex-col gap-6 border-b border-black/8 pb-6">
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs uppercase tracking-[0.28em] text-stone-500">
            <span>{eyebrow}</span>
            <nav className="flex items-center gap-2">
              <Button asChild size="sm" variant="ghost">
                <Link href="/">Overview</Link>
              </Button>
              <Button asChild size="sm" variant="ghost">
                <Link href="/login">Auth</Link>
              </Button>
              <Button asChild size="sm" variant="ghost">
                <Link href="/projects">Projects</Link>
              </Button>
            </nav>
          </div>

          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl space-y-3">
              <h1 className="font-[family:var(--font-heading)] text-4xl leading-[0.95] text-stone-950 md:text-6xl">
                {title}
              </h1>
              <p className="max-w-2xl text-sm leading-7 text-stone-600 md:text-base">
                {description}
              </p>
            </div>
            {actions ? <div className="shrink-0">{actions}</div> : null}
          </div>
        </header>

        {children}
      </div>
    </main>
  );
}
