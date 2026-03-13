import { ArrowRight, BookOpen } from "lucide-react";

import { getAppUrl, getDocsUrl } from "@/lib/seo";
import { cn } from "@/lib/utils";

import styles from "./landing-page.module.css";

export function LandingHero() {
  return (
    <section className="relative overflow-hidden px-6 pb-20 pt-[100px] md:px-[120px]">
      <div className={styles.heroBlobLeft} aria-hidden="true" />
      <div className={styles.heroBlobRight} aria-hidden="true" />

      <div className="relative z-10 mx-auto flex w-full max-w-[1200px] flex-col items-center gap-10 text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-[#7a2dbe]/27 bg-[#7a2dbe]/10 px-4 py-1.5">
          <span className="size-2 rounded-full bg-[#a855f7]" />
          <span className="text-[13px] font-medium text-[#c084fc]">Memory-as-a-Service for AI Agents</span>
        </div>

        <div className="flex flex-col items-center gap-3">
          <h1
            className={cn(
              "text-center text-5xl leading-[1.06] tracking-[-0.02em] text-white md:text-7xl",
              styles.fontDisplay,
            )}
          >
            Never Forget a Single{" "}
            <span className={styles.purpleGradientText}>Line of Code Again</span>
          </h1>
        </div>

        <p className="max-w-[700px] text-center text-lg leading-[1.6] text-[#8b8b90]">
          Long-term memory for your coding agent. VibeRecall builds a temporal knowledge graph of your
          project — remembering decisions, bugs, architecture, and context across every session.
        </p>

        <div className="flex flex-col items-center gap-4 sm:flex-row">
          <a
            href={getAppUrl("/projects")}
            className="inline-flex items-center gap-2.5 rounded-xl bg-gradient-to-br from-[#7a2dbe] to-[#9333ea] px-8 py-4 text-base font-semibold text-white shadow-[0_12px_28px_-16px_rgba(122,45,190,1)] transition-opacity hover:opacity-95"
          >
            <ArrowRight className="size-5" />
            Get Started Free
          </a>
          <a
            href={getDocsUrl("/")}
            className="inline-flex items-center gap-2.5 rounded-xl border border-[#2a2a2e] px-8 py-4 text-base font-medium text-[#adadb0] transition-colors hover:border-[#3a3a3f] hover:text-white"
          >
            <BookOpen className="size-5" />
            View Documentation
          </a>
        </div>

        <div className={cn("w-full max-w-[800px] overflow-hidden rounded-2xl border border-[#1f1f23] bg-[#111113]", styles.terminalGlow)}>
          <div className="flex items-center gap-2 rounded-t-2xl bg-[#141417] px-4 py-3">
            <div className="size-3 rounded-full bg-[#ef4444]" />
            <div className="size-3 rounded-full bg-[#eab308]" />
            <div className="size-3 rounded-full bg-[#22c55e]" />
            <span className={cn("ml-2 text-xs font-medium text-[#6b6b70]", styles.fontMono)}>
              claude-code — viberecall
            </span>
          </div>

          <div className={cn("space-y-3 p-6 text-left text-[13px] leading-[1.55] md:text-[13px]", styles.fontMono)}>
            <p className="text-[#c084fc]">{"> Why did we switch from REST to GraphQL in the auth module?"}</p>
            <p className="text-[#6b6b70]">Searching memory...</p>
            <div className="h-px w-full bg-[#1f1f23]" />
            <p className="text-[#22c55e]">Found 3 relevant episodes from your project history:</p>
            <p className="text-[#adadb0]">{"  [2025-12-15] Decided to migrate auth to GraphQL for"}</p>
            <p className="text-[#adadb0]">{"  real-time subscription support. REST couldn't handle"}</p>
            <p className="text-[#adadb0]">{"  WebSocket fallback gracefully. PR #247 by @alex."}</p>
            <p className="text-[#adadb0]">{"  [2025-12-18] Auth token refresh was refactored to use"}</p>
            <p className="text-[#adadb0]">{"  GraphQL mutations. Old REST endpoint deprecated."}</p>
          </div>
        </div>
      </div>
    </section>
  );
}
