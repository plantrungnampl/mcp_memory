import Link from "next/link";
import { BrainCircuit, ExternalLink } from "lucide-react";

import { cn } from "@/lib/utils";

import { navItems } from "./landing-data";
import { LandingAuthControls } from "./landing-auth-controls";
import styles from "./landing-page.module.css";

export function LandingHeader() {
  return (
    <header className={cn("sticky top-0 z-50 border-b border-white/5", styles.glassHeader)}>
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between px-6">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl border border-[#7a2dbe]/30 bg-[#7a2dbe]/20">
            <BrainCircuit className="size-5 text-[#00f5ff]" />
          </div>
          <span className="text-xl font-bold uppercase italic tracking-tight text-slate-100">
            VibeRecall <span className="text-[#00f5ff]">PRO</span>
          </span>
        </div>

        <nav className="hidden items-center gap-8 md:flex">
          {navItems.map((item) => (
            <Link
              key={item.label}
              href={item.href}
              className="flex items-center gap-1 text-sm font-medium text-slate-400 transition-colors hover:text-[#00f5ff]"
              {...(item.external ? { target: "_blank", rel: "noreferrer" } : {})}
            >
              {item.label}
              {item.external ? <ExternalLink className="size-3.5" /> : null}
            </Link>
          ))}
        </nav>

        <LandingAuthControls />
      </div>
    </header>
  );
}
