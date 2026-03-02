import Link from "next/link";
import {
  ArrowRight,
  Ban,
  Bot,
  CalendarClock,
  CheckCircle2,
  CloudOff,
  Code2,
  Fingerprint,
  GitBranch,
  History,
  LockKeyhole,
  Network,
  PencilLine,
  PlugZap,
  RefreshCw,
  Rocket,
  Shield,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  Workflow,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { KnowledgeGraphPanel } from "@/components/landing/knowledge-graph-panel";

import {
  compatibilityLabels,
  faqItems,
  featureItems,
  howItWorksSteps,
  pricingPlans,
  securityHighlights,
  temporalEdgeItems,
} from "./landing-data";
import styles from "./landing-page.module.css";

const compatibilityIcons = [TerminalSquare, PencilLine, Bot, Code2];
const featureIcons = [GitBranch, History, ShieldCheck, Network];
const howItWorksIcons = [PlugZap, Workflow, Sparkles];
const temporalIcons = [CalendarClock, RefreshCw, Network];

const toneMap = {
  primary: {
    badge: "bg-[#7a2dbe]/10 text-[#7a2dbe] border-[#7a2dbe]/20",
    border: "hover:border-[#7a2dbe]/50",
    icon: "text-[#7a2dbe]",
  },
  accent: {
    badge: "bg-[#00f5ff]/10 text-[#00f5ff] border-[#00f5ff]/20",
    border: "hover:border-[#00f5ff]/50",
    icon: "text-[#00f5ff]",
  },
} as const;

export function LandingSections() {
  return (
    <>
      <section className={cn("border-y border-white/5 bg-[#0a080c]/65 py-12", styles.sectionReveal, styles.revealDelay1)}>
        <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-center gap-8 px-6 opacity-70 md:gap-16">
          {compatibilityLabels.map((label, index) => {
            const Icon = compatibilityIcons[index];
            return (
              <div
                key={label}
                className="flex items-center gap-2 grayscale transition-all hover:grayscale-0"
              >
                <Icon className="size-7" />
                <span className="text-xl font-bold">{label}</span>
              </div>
            );
          })}
          <div className="rounded border border-[#00f5ff]/30 bg-[#00f5ff]/5 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-[#00f5ff]">
            Native MCP Support
          </div>
        </div>
      </section>

      <section id="features" className={cn("bg-[#1a1622]/35 py-24", styles.sectionReveal, styles.revealDelay1)}>
        <div className="mx-auto w-full max-w-7xl px-6">
          <div className="mb-20 flex flex-col items-center text-center">
            <h2 className="mb-6 text-3xl font-bold text-slate-100 md:text-5xl">Designed for Agentic Workflows</h2>
            <div className="h-1 w-20 rounded-full bg-[#00f5ff]" />
          </div>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
            {featureItems.map((item, index) => {
              const Icon = featureIcons[index];
              const tone = toneMap[item.tone];

              return (
                <article
                  key={item.title}
                  className={cn(
                    "flex flex-col gap-4 rounded-2xl border border-white/5 bg-[#1a1622] p-8 transition-all",
                    tone.border,
                  )}
                >
                  <div className={cn("flex size-12 items-center justify-center rounded-xl border", tone.badge)}>
                    <Icon className={cn("size-6", tone.icon)} />
                  </div>
                  <h3 className="text-lg font-bold text-slate-100">{item.title}</h3>
                  <p className="text-sm leading-relaxed text-slate-400">{item.description}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section
        id="how-it-works"
        className={cn("relative bg-[#0a080c] py-24", styles.sectionReveal, styles.revealDelay2)}
      >
        <div className="pointer-events-none absolute left-1/2 top-1/2 size-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#7a2dbe]/7 blur-[120px]" />

        <div className="relative z-10 mx-auto w-full max-w-7xl px-6">
          <div className="mb-16 text-center">
            <h2 className="mb-4 text-3xl font-bold text-slate-100 md:text-5xl">How It Works</h2>
            <p className="text-lg text-slate-400">Three steps to infinite context.</p>
          </div>

          <div className="grid grid-cols-1 gap-12 md:grid-cols-3">
            {howItWorksSteps.map((step, index) => {
              const Icon = howItWorksIcons[index];
              const tone = toneMap[step.tone];
              const isLast = index === howItWorksSteps.length - 1;

              return (
                <article key={step.title} className="group relative flex flex-col items-center text-center">
                  <div className="relative mb-12">
                    <div
                      className={cn(
                        "absolute -inset-6 rounded-full opacity-0 blur-2xl transition-opacity duration-500 group-hover:opacity-100",
                        step.tone === "primary" ? "bg-[#7a2dbe]/40" : "bg-[#00f5ff]/30",
                      )}
                    />
                    <div
                      className={cn(
                        "relative flex size-28 items-center justify-center rounded-3xl border-2 bg-[#1a1622] transition-all duration-500 group-hover:scale-110",
                        step.tone === "primary"
                          ? "border-[#7a2dbe]/30 shadow-[0_0_50px_-10px_rgba(122,45,190,0.5)] group-hover:border-[#7a2dbe]"
                          : "border-[#00f5ff]/30 shadow-[0_0_50px_-10px_rgba(0,245,255,0.4)] group-hover:border-[#00f5ff]",
                      )}
                    >
                      <Icon className={cn("size-12", tone.icon)} />
                    </div>
                  </div>

                  <h3 className="mb-4 text-2xl font-bold text-slate-100">{step.title}</h3>
                  <p className="text-lg text-slate-400">{step.description}</p>

                  {!isLast ? (
                    <ArrowRight
                      className={cn(
                        "absolute right-[-3.1rem] top-14 hidden size-9 text-white/10 lg:block",
                        styles.pulseArrow,
                      )}
                    />
                  ) : null}
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className={cn("overflow-hidden border-y border-white/5 bg-[#1a1622]/45 py-24", styles.sectionReveal, styles.revealDelay2)}>
        <div className="mx-auto grid w-full max-w-7xl grid-cols-1 items-center gap-16 px-6 lg:grid-cols-2">
          <div>
            <h2 className="mb-8 text-3xl font-bold text-slate-100 md:text-5xl">The Temporal Edge</h2>
            <div className="space-y-8">
              {temporalEdgeItems.map((item, index) => {
                const Icon = temporalIcons[index];
                const tone = toneMap[item.tone];

                return (
                  <article key={item.title} className="flex gap-6">
                    <div className={cn("flex size-12 shrink-0 items-center justify-center rounded-lg border", tone.badge)}>
                      <Icon className={cn("size-5", tone.icon)} />
                    </div>
                    <div>
                      <h3 className="mb-2 text-lg font-bold text-slate-100">{item.title}</h3>
                      <p className="text-sm text-slate-400">{item.description}</p>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>

          <KnowledgeGraphPanel />
        </div>
      </section>

      <section id="pricing" className={cn("py-24", styles.sectionReveal, styles.revealDelay3)}>
        <div className="mx-auto w-full max-w-7xl px-6">
          <div className="mb-16 text-center">
            <h2 className="mb-4 text-4xl font-bold text-slate-100">Pricing for Every Developer</h2>
            <p className="text-slate-400">Scale your memory capacity with VibeTokens.</p>
          </div>

          <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
            {pricingPlans.map((plan) => (
              <article
                key={plan.name}
                className={cn(
                  "relative flex flex-col rounded-2xl border border-white/5 bg-[#1a1622] p-8 transition-all",
                  plan.highlighted ? `z-10 scale-[1.03] border-2 border-[#7a2dbe] ${styles.priceHighlight}` : "",
                )}
              >
                {plan.highlighted ? (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 rounded-full bg-[#7a2dbe] px-4 py-1 text-[10px] font-black uppercase tracking-tight text-white">
                    Most Popular
                  </div>
                ) : null}

                <div className="mb-8">
                  <h3 className="mb-2 text-xl font-bold text-slate-100">{plan.name}</h3>
                  <div className="flex items-baseline gap-1">
                    <span className="text-4xl font-black text-slate-100">{plan.price}</span>
                    <span className="text-slate-500">{plan.cadence}</span>
                  </div>
                </div>

                <div className="mb-8 flex flex-1 flex-col gap-4">
                  {plan.features.map((feature) => (
                    <div
                      key={`${plan.name}-${feature.label}`}
                      className={cn(
                        "flex items-center gap-3 text-sm text-slate-300",
                        feature.included ? "" : "opacity-50",
                      )}
                    >
                      {feature.included ? (
                        <CheckCircle2
                          className={cn(
                            "size-4",
                            plan.highlighted ? "text-[#00f5ff]" : "text-[#7a2dbe]",
                          )}
                        />
                      ) : (
                        <Ban className="size-4" />
                      )}
                      {feature.label}
                    </div>
                  ))}
                </div>

                <Link
                  href={plan.ctaLabel === "Contact Sales" ? "#" : "/projects"}
                  className={cn(
                    "inline-flex w-full items-center justify-center rounded-xl py-3 font-bold transition-all",
                    plan.highlighted
                      ? "bg-[#7a2dbe] text-white hover:brightness-110"
                      : "border border-white/10 text-white hover:bg-white/5",
                  )}
                >
                  {plan.ctaLabel}
                </Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className={cn("py-24", styles.sectionReveal, styles.revealDelay3)}>
        <div className="mx-auto grid w-full max-w-7xl grid-cols-1 items-center gap-12 px-6 md:grid-cols-2">
          <div className="flex flex-col gap-6">
            <h2 className="text-3xl font-bold text-slate-100">Security First by Design</h2>
            <p className="text-slate-400">
              Your source code is your competitive advantage. We treat it with the highest level of
              security and isolation.
            </p>
            <ul className="space-y-4">
              {securityHighlights.map((item, index) => {
                const Icon = [ShieldCheck, LockKeyhole, Fingerprint][index];
                return (
                  <li key={item} className="flex items-center gap-3">
                    <Icon className="size-5 text-green-400" />
                    <span className="font-medium text-slate-200">{item}</span>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-white/5 bg-[#1a1622] p-6 text-center">
              <Shield className="size-10 text-[#7a2dbe]" />
              <span className="text-sm font-bold text-slate-200">Zero Trust Architecture</span>
            </div>
            <div className="translate-y-8 rounded-2xl border border-white/5 bg-[#1a1622] p-6 text-center">
              <div className="flex flex-col items-center justify-center gap-4">
                <CloudOff className="size-10 text-[#00f5ff]" />
                <span className="text-sm font-bold text-slate-200">Local Cache Priority</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="faq" className={cn("bg-[#1a1622]/40 py-24", styles.sectionReveal, styles.revealDelay4)}>
        <div className="mx-auto w-full max-w-3xl px-6">
          <div className="mb-16 text-center">
            <h2 className="mb-4 text-3xl font-bold text-slate-100">Frequently Asked Questions</h2>
          </div>

          <div className="space-y-4">
            {faqItems.map((item) => (
              <article key={item.question} className="rounded-xl border border-white/5 bg-[#1a1622]/70 p-6">
                <h3 className="mb-2 text-lg font-bold text-slate-200">{item.question}</h3>
                <p className="text-sm text-slate-400">{item.answer}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className={cn("relative overflow-hidden py-32", styles.sectionReveal, styles.revealDelay4)}>
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#7a2dbe]/10 to-transparent" />
        <div className="pointer-events-none absolute left-1/2 top-1/2 size-[800px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#7a2dbe]/20 blur-[160px]" />

        <div className="relative z-10 mx-auto w-full max-w-4xl px-6 text-center">
          <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2">
            <span className="size-2 rounded-full bg-green-500" />
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-300">
              100+ new developers joined today
            </span>
          </div>

          <h2 className="mb-8 text-5xl font-black tracking-tighter text-white md:text-7xl">
            Build with <span className={styles.purpleGradientText}>Superhuman</span> Memory.
          </h2>

          <p className="mx-auto mb-12 max-w-2xl text-xl leading-relaxed text-slate-400">
            Stop repeating yourself to your agent. Start building with a permanent, evolving knowledge
            base that lives where you code.
          </p>

          <div className="flex flex-col items-center justify-center gap-6 sm:flex-row">
            <Link
              href="/projects"
              className="inline-flex w-full items-center justify-center gap-3 rounded-2xl bg-[#7a2dbe] px-10 py-5 text-lg font-bold text-white shadow-[0_0_40px_-10px_rgba(122,45,190,0.6)] transition-all hover:scale-105 sm:w-auto"
            >
              <Rocket className="size-5" />
              Get Started Free
            </Link>

            <Link
              href="#"
              className="inline-flex w-full items-center justify-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-10 py-5 text-lg font-bold text-slate-200 transition-all hover:bg-white/10 sm:w-auto"
            >
              Talk to Engineering
            </Link>
          </div>

          <p className="mt-10 text-xs font-bold uppercase tracking-[0.16em] text-slate-500">
            No credit card required • SOC2 Compliant • Native MCP
          </p>
        </div>
      </section>
    </>
  );
}
