import Link from "next/link";
import {
  Award,
  CalendarClock,
  CheckCircle2,
  Code2,
  Lock,
  MousePointerClick,
  Network,
  Plug,
  Search,
  Shield,
  Terminal,
  Wind,
} from "lucide-react";

import { DOCS_QUICKSTART_PATH, getDocsUrl } from "@/lib/seo";
import { cn } from "@/lib/utils";

import { KnowledgeGraphPanel } from "./knowledge-graph-panel";
import {
  compatibilityLabels,
  faqItems,
  featureItems,
  howItWorksSteps,
  securityCards,
  temporalEdgeItems,
} from "./landing-data";
import styles from "./landing-page.module.css";

const compatibilityIcons = [Terminal, MousePointerClick, Wind, Code2] as const;
const featureIcons = [Network, CalendarClock, Shield, Network] as const;
const stepIcons = [Plug, Code2, Search] as const;
const securityIcons = [Shield, Lock, Award] as const;

const featureToneMap: Record<string, string> = {
  primary: "bg-[#7a2dbe]/10 border-[#7a2dbe]/35 text-[#a855f7]",
  accent: "bg-[#00f5ff]/10 border-[#00f5ff]/35 text-[#00f5ff]",
  success: "bg-[#22c55e]/10 border-[#22c55e]/35 text-[#22c55e]",
};

export function LandingSections() {
  return (
    <>
      <section className="border-y border-[#1f1f23] bg-[#0e0e14] px-6 py-10 md:px-[120px]">
        <div className="mx-auto flex w-full max-w-[1200px] flex-col items-center gap-6">
          <p className="text-xs font-semibold tracking-[0.18em] text-[#6b6b70]">WORKS WITH YOUR FAVORITE TOOLS</p>
          <div className="flex flex-wrap items-center justify-center gap-8 md:gap-12">
            {compatibilityLabels.map((label, index) => {
              const Icon = compatibilityIcons[index];
              return (
                <div key={label} className="flex items-center gap-2.5 text-[#8b8b90]">
                  <Icon className="size-5" />
                  <span className="text-sm font-medium">{label}</span>
                </div>
              );
            })}
            <div className="inline-flex items-center gap-1.5 rounded-full border border-[#22c55e]/30 bg-[#22c55e]/10 px-3.5 py-1.5">
              <span className="size-1.5 rounded-full bg-[#22c55e]" />
              <span className="text-[11px] font-semibold text-[#22c55e]">Native MCP</span>
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="px-6 py-24 md:px-[120px]">
        <div className="mx-auto w-full max-w-[1200px]">
          <div className="mb-16 flex flex-col items-center gap-4 text-center">
            <div className="rounded-full border border-[#7a2dbe]/35 bg-[#7a2dbe]/10 px-3.5 py-1.5">
              <span className="text-[11px] font-semibold tracking-[0.12em] text-[#c084fc]">CORE FEATURES</span>
            </div>
            <h2 className={cn("max-w-[760px] text-4xl leading-tight tracking-[-0.02em] text-white md:text-6xl", styles.fontDisplay)}>
              Everything Your Agent Needs to Remember
            </h2>
            <p className="max-w-[500px] text-base leading-relaxed text-[#8b8b90]">
              Purpose-built memory infrastructure that makes your AI coding assistant smarter with every
              session.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-4">
            {featureItems.map((item, index) => {
              const Icon = featureIcons[index];
              const toneClass = featureToneMap[item.tone] ?? featureToneMap.primary;

              return (
                <article
                  key={item.title}
                  className="rounded-2xl border border-[#1f1f23] bg-[#111113] p-7 transition-colors hover:border-[#2e2e33]"
                >
                  <div className={cn("mb-4 flex size-12 items-center justify-center rounded-xl border", toneClass)}>
                    <Icon className="size-5" />
                  </div>
                  <h3 className="mb-3 text-lg font-semibold text-white">{item.title}</h3>
                  <p className="text-sm leading-relaxed text-[#8b8b90]">{item.description}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="bg-[#0e0e14] px-6 py-24 md:px-[120px]">
        <div className="mx-auto w-full max-w-[1200px]">
          <div className="mb-16 flex flex-col items-center gap-4 text-center">
            <div className="rounded-full border border-[#7a2dbe]/35 bg-[#7a2dbe]/10 px-3.5 py-1.5">
              <span className="text-[11px] font-semibold tracking-[0.12em] text-[#c084fc]">HOW IT WORKS</span>
            </div>
            <h2 className={cn("max-w-[760px] text-4xl leading-tight tracking-[-0.02em] text-white md:text-6xl", styles.fontDisplay)}>
              Three Steps to Superhuman Memory
            </h2>
          </div>

          <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
            {howItWorksSteps.map((step, index) => {
              const Icon = stepIcons[index];

              return (
                <article key={step.title} className="rounded-2xl border border-[#1f1f23] bg-[#111113] p-8 text-center">
                  <div className="mx-auto mb-5 flex size-14 items-center justify-center rounded-full bg-gradient-to-br from-[#7a2dbe] to-[#9333ea] text-sm font-semibold text-white">
                    {step.number}
                  </div>
                  <Icon className="mx-auto mb-4 size-8 text-[#a855f7]" />
                  <h3 className="mb-3 text-2xl font-semibold text-white">{step.title}</h3>
                  <p className="text-sm leading-relaxed text-[#8b8b90]">{step.description}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="px-6 py-24 md:px-[120px]">
        <div className="mx-auto grid w-full max-w-[1200px] grid-cols-1 items-center gap-14 lg:grid-cols-2">
          <div className="flex flex-col gap-8">
            <div className="w-fit rounded-full border border-[#00f5ff]/35 bg-[#00f5ff]/10 px-3.5 py-1.5">
              <span className="text-[11px] font-semibold tracking-[0.12em] text-[#00f5ff]">THE TEMPORAL EDGE</span>
            </div>
            <h2 className={cn("max-w-[520px] text-4xl leading-[1.2] tracking-[-0.02em] text-white md:text-5xl", styles.fontDisplay)}>
              Your Code Has a Story. We Remember All of It.
            </h2>
            <p className="max-w-[500px] text-base leading-[1.65] text-[#8b8b90]">
              VibeRecall doesn&apos;t just store data — it understands the timeline of your project. Every
              decision, every refactor, every bug fix is woven into a living knowledge graph.
            </p>

            <ul className="space-y-4">
              {temporalEdgeItems.map((item) => (
                <li key={item.text} className="flex items-center gap-3.5 text-[#adadb0]">
                  <CheckCircle2 className="size-5 shrink-0 text-[#a855f7]" />
                  <span className="text-sm font-medium">{item.text}</span>
                </li>
              ))}
            </ul>
          </div>

          <KnowledgeGraphPanel />
        </div>
      </section>

      <section className="bg-[#0e0e14] px-6 py-24 md:px-[120px]">
        <div className="mx-auto w-full max-w-[1200px]">
          <div className="mx-auto max-w-[840px] rounded-[28px] border border-[#1f1f23] bg-[#111113] px-8 py-14 text-center md:px-14">
            <div className="mb-5 inline-flex rounded-full border border-[#22c55e]/35 bg-[#22c55e]/10 px-3.5 py-1.5">
              <span className="text-[11px] font-semibold tracking-[0.12em] text-[#22c55e]">FREE FOR EVERYONE</span>
            </div>
            <h2 className={cn("mb-4 text-4xl tracking-[-0.02em] text-white md:text-6xl", styles.fontDisplay)}>
              VibeRecall is free for everyone
            </h2>
            <p className="mx-auto max-w-[620px] text-base leading-[1.7] text-[#8b8b90]">
              No pricing tiers, no sales gate, and no credit card required to get started. Create a
              project, connect your MCP client, and start using persistent memory today.
            </p>
          </div>
        </div>
      </section>

      <section className="px-6 py-20 md:px-[120px]">
        <div className="mx-auto w-full max-w-[1200px]">
          <div className="mb-12 flex flex-col items-center gap-4 text-center">
            <div className="rounded-full border border-[#22c55e]/35 bg-[#22c55e]/10 px-3.5 py-1.5">
              <span className="text-[11px] font-semibold tracking-[0.12em] text-[#22c55e]">ENTERPRISE SECURITY</span>
            </div>
            <h2 className={cn("text-4xl tracking-[-0.02em] text-white md:text-6xl", styles.fontDisplay)}>
              Your Code Memories, Locked Down
            </h2>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {securityCards.map((card, index) => {
              const Icon = securityIcons[index];
              return (
                <article key={card.title} className="rounded-2xl border border-[#1f1f23] bg-[#111113] p-7 text-center">
                  <Icon className="mx-auto mb-4 size-8 text-[#22c55e]" />
                  <h3 className="mb-3 text-base font-semibold text-white">{card.title}</h3>
                  <p className="text-[13px] leading-relaxed text-[#8b8b90]">{card.description}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section id="faq" className="bg-[#0e0e14] px-6 py-20 md:px-[200px]">
        <div className="mx-auto w-full max-w-[1040px]">
          <h2 className={cn("mb-10 text-center text-4xl tracking-[-0.02em] text-white md:text-5xl", styles.fontDisplay)}>
            Frequently Asked Questions
          </h2>

          <div>
            {faqItems.map((item, index) => (
              <article
                key={item.question}
                className={cn("py-6", index < faqItems.length - 1 && "border-b border-[#1f1f23]")}
              >
                <h3 className="mb-3 text-base font-semibold text-white">{item.question}</h3>
                <p className="max-w-[920px] text-sm leading-[1.65] text-[#8b8b90]">{item.answer}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="px-6 py-24 md:px-[120px]">
        <div className="mx-auto flex w-full max-w-[920px] flex-col items-center gap-8 text-center">
          <h2 className={cn("text-5xl leading-tight tracking-[-0.02em] text-white md:text-6xl", styles.fontDisplay)}>
            Build with Superhuman Memory
          </h2>
          <p className="max-w-[520px] text-lg leading-[1.55] text-[#8b8b90]">
            Give your AI coding agent the context it deserves. Start remembering today.
          </p>

          <div className="flex flex-col items-center gap-4 sm:flex-row">
            <Link
              href="/projects"
              className="inline-flex items-center rounded-xl bg-gradient-to-br from-[#7a2dbe] to-[#9333ea] px-8 py-4 text-base font-semibold text-white shadow-[0_12px_28px_-16px_rgba(122,45,190,1)]"
            >
              Get Started
            </Link>
            <Link
              href={getDocsUrl(DOCS_QUICKSTART_PATH)}
              className="inline-flex items-center rounded-xl border border-[#2a2a2e] px-8 py-4 text-base font-medium text-[#adadb0] transition-colors hover:border-[#3a3a3f] hover:text-white"
            >
              Read Quickstart
            </Link>
          </div>

          <p className="text-[13px] text-[#6b6b70]">No credit card required  ·  SOC2 Compliant  ·  Native MCP</p>
        </div>
      </section>
    </>
  );
}
