import { publicEnv } from "@/lib/env";
import {
  DOCS_QUICKSTART_PATH,
  GITHUB_REPO_URL,
  getDocsUrl,
} from "@/lib/seo";

export type NavItem = {
  label: string;
  href: string;
};

export type FeatureTone = "primary" | "accent" | "success";

export type FeatureItem = {
  title: string;
  description: string;
  tone: FeatureTone;
};

export type HowItWorksStep = {
  number: string;
  title: string;
  description: string;
  icon: "plug" | "code" | "search";
};

export type TemporalEdgeItem = {
  text: string;
};

export type SecurityCard = {
  title: string;
  description: string;
  icon: "shield" | "lock" | "award";
};

export type FaqItem = {
  question: string;
  answer: string;
};

export type FooterLinkColumn = {
  title: string;
  links: Array<{
    label: string;
    href?: string;
  }>;
};

export const navItems: NavItem[] = [
  { label: "Features", href: "#features" },
  { label: "How It Works", href: "#how-it-works" },
  { label: "Docs", href: publicEnv.docsUrl },
];

export const compatibilityLabels = ["Claude Code", "Cursor", "Windsurf", "VS Code"];

export const featureItems: FeatureItem[] = [
  {
    title: "Temporal Knowledge Graph",
    description:
      "Automatically builds a rich graph of entities, relationships, and decisions from your coding sessions.",
    tone: "primary",
  },
  {
    title: "Multi-Session Recall",
    description:
      "Your agent remembers context from days, weeks, or months ago — no more repeating yourself every session.",
    tone: "primary",
  },
  {
    title: "100% Project Isolation",
    description:
      "Hard-wired data boundaries ensure zero cross-project leakage. Each project lives in its own secure namespace.",
    tone: "success",
  },
  {
    title: "Bi-Temporal Awareness",
    description:
      "Distinguishes when events happened vs. when they were recorded. Time-travel through your project's history.",
    tone: "accent",
  },
];

export const howItWorksSteps: HowItWorksStep[] = [
  {
    number: "01",
    icon: "plug",
    title: "Connect via MCP",
    description:
      "Add VibeRecall to your IDE in seconds. One config line and your agent has persistent memory.",
  },
  {
    number: "02",
    icon: "code",
    title: "Code Naturally",
    description:
      "Work as you normally do. VibeRecall silently captures decisions, patterns, and context in the background.",
  },
  {
    number: "03",
    icon: "search",
    title: "Precise Recall",
    description:
      "Ask anything about your project history. Get instant, contextual answers backed by your real coding timeline.",
  },
];

export const temporalEdgeItems: TemporalEdgeItem[] = [
  { text: "Bi-temporal awareness — event time vs. transaction time" },
  { text: "Incremental memory — no massive context windows" },
  { text: "Entity-relationship graph for deep project understanding" },
  { text: "Hybrid search — semantic + temporal filtering" },
];

export const securityCards: SecurityCard[] = [
  {
    icon: "shield",
    title: "100% Project Isolation",
    description: "Hard data boundaries per project. Zero cross-contamination.",
  },
  {
    icon: "lock",
    title: "AES-256 Encryption",
    description: "All data encrypted at rest and in transit. Your memories are yours alone.",
  },
  {
    icon: "award",
    title: "SOC2 Type II Ready",
    description: "Enterprise-grade compliance. Audit logs for every operation.",
  },
];

export const faqItems: FaqItem[] = [
  {
    question: "Is my code stored or analyzed?",
    answer:
      "No. VibeRecall stores facts, decisions, and context — not your actual source code. Your codebase stays on your machine.",
  },
  {
    question: "How much latency does VibeRecall add?",
    answer:
      "Near-zero. Saves are fast-acknowledged and processed asynchronously. Searches use hybrid retrieval optimized for sub-second response times.",
  },
  {
    question: "Is VibeRecall really free?",
    answer:
      "Yes. VibeRecall is free for everyone. Create a project, connect your MCP client, and start using persistent memory without a pricing gate.",
  },
  {
    question: "How do I get started?",
    answer:
      "Open the control plane, create a project, then follow the docs to connect your MCP client and start using VibeRecall in your workflow.",
  },
];

export const footerColumns: FooterLinkColumn[] = [
  {
    title: "Product",
    links: [
      { label: "Features", href: "/#features" },
      { label: "How It Works", href: "/#how-it-works" },
      { label: "Documentation", href: publicEnv.docsUrl },
      { label: "Quickstart", href: getDocsUrl(DOCS_QUICKSTART_PATH) },
    ],
  },
  {
    title: "Company",
    links: [{ label: "GitHub", href: GITHUB_REPO_URL }],
  },
];
