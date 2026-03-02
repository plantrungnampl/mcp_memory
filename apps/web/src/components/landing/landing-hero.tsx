import Link from "next/link";
import { ArrowRight, LogIn } from "lucide-react";

import { cn } from "@/lib/utils";

import styles from "./landing-page.module.css";

export function LandingHero() {
  return (
    <section className="relative overflow-hidden pb-16 pt-20 md:pb-24 md:pt-32">
      <div className={styles.heroBlobLeft} />
      <div className={styles.heroBlobRight} />

      <div className="relative z-10 mx-auto grid w-full max-w-7xl grid-cols-1 items-center gap-12 px-6 lg:grid-cols-2">
        <div className={cn("flex flex-col gap-8", styles.sectionReveal)}>
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-[#7a2dbe]/25 bg-[#7a2dbe]/12 px-3 py-1">
            <span className={cn("text-[10px] font-bold uppercase tracking-[0.16em] text-[#b995df]", styles.cyanGlow)}>
              Native MCP Memory
            </span>
          </div>

          <h1 className="text-5xl font-black leading-[1.08] tracking-tight text-slate-100 md:text-7xl">
            Never forget a single <span className={styles.purpleGradientText}>line of code</span> again.
          </h1>

          <p className="max-w-2xl text-lg leading-relaxed text-slate-400 md:text-xl">
            Long-term memory for your coding agent. VibeRecall PRO persists context across sessions,
            enabling Claude and Cursor to remember your entire architecture forever.
          </p>

          <div className="mt-2 flex flex-wrap gap-4">
            <Link
              href="/projects"
              className="inline-flex items-center gap-2 rounded-xl bg-[#7a2dbe] px-8 py-4 text-base font-bold text-white transition-all hover:shadow-[0_0_30px_-6px_rgba(122,45,190,0.6)]"
            >
              <LogIn className="size-4.5" />
              Get Started with GitHub
            </Link>
            <Link
              href="/docs"
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-8 py-4 text-base font-bold text-slate-200 transition-all hover:bg-white/10"
            >
              View Docs
              <ArrowRight className="size-4.5" />
            </Link>
          </div>
        </div>

        <div className={cn("group relative", styles.sectionReveal, styles.revealDelay1)}>
          <div className="absolute -inset-1 rounded-2xl bg-gradient-to-r from-[#7a2dbe] to-[#00f5ff] opacity-25 blur transition duration-1000 group-hover:opacity-40" />
          <div
            className={cn(
              "relative aspect-video overflow-hidden rounded-2xl border border-white/10 bg-[#1a1622]",
              styles.terminalGlow,
            )}
          >
            <div className="flex items-center justify-between border-b border-white/5 bg-black/40 px-4 py-2">
              <div className="flex gap-1.5">
                <div className="size-2.5 rounded-full bg-red-500/50" />
                <div className="size-2.5 rounded-full bg-yellow-500/50" />
                <div className="size-2.5 rounded-full bg-green-500/50" />
              </div>
              <div className="font-mono text-[10px] text-slate-500">viberecall-memory-stream.log</div>
            </div>

            <div className="space-y-4 p-6 font-mono text-xs sm:text-sm">
              <div className="flex gap-3">
                <span className="shrink-0 text-[#00f5ff]">AI:</span>
                <span className="text-slate-300">
                  Checking VibeRecall... Found session context from Oct 12th. I remember you refactored
                  the auth hook to use the new Temporal Knowledge Graph. Should I apply the same pattern
                  here?
                </span>
              </div>
              <div className="flex gap-3 border-l-2 border-[#7a2dbe]/50 py-1 pl-4">
                <span className="shrink-0 text-[#9f66d2]">SYS:</span>
                <span className="italic text-[#b995df]">
                  [MCP] Recalling &apos;auth-refactor-schema&apos; via Graphiti... 100% Match.
                </span>
              </div>
              <div className="flex gap-3">
                <span className="shrink-0 text-slate-500">122:</span>
                <span className="text-green-400">export const useSecureAuth = () =&gt; {'{'}</span>
              </div>
              <div className="flex gap-3">
                <span className="shrink-0 text-slate-500">123:</span>
                <span className="text-slate-400">{`  // Memory restored successfully`}</span>
              </div>
            </div>

            <div className="mt-auto h-2 bg-gradient-to-r from-[#7a2dbe]/55 via-[#00f5ff]/55 to-[#7a2dbe]/55" />
          </div>
        </div>
      </div>
    </section>
  );
}
