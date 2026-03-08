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

export type PricingPlan = {
  name: string;
  price: string;
  cadence: string;
  description: string;
  ctaLabel: string;
  highlighted?: boolean;
  features: string[];
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
  links: string[];
};

export const navItems: NavItem[] = [
  { label: "Features", href: "#features" },
  { label: "How It Works", href: "#how-it-works" },
  { label: "Pricing", href: "#pricing" },
  { label: "Docs", href: "/docs" },
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

export const pricingPlans: PricingPlan[] = [
  {
    name: "Free",
    price: "$0",
    cadence: "/month",
    description: "Perfect for trying out memory-powered coding.",
    ctaLabel: "Start Free",
    features: [
      "100 VibeTokens / month",
      "1 project",
      "Basic memory persistence",
      "Community support",
    ],
  },
  {
    name: "Pro",
    price: "$9",
    cadence: "/month",
    description: "For developers who ship fast and need full recall.",
    ctaLabel: "Get Pro",
    highlighted: true,
    features: [
      "5,000 VibeTokens / month",
      "Unlimited projects",
      "Advanced temporal search",
      "Priority support",
      "JSON export",
    ],
  },
  {
    name: "Team",
    price: "$29",
    cadence: "/month",
    description: "For teams building complex projects together.",
    ctaLabel: "Contact Sales",
    features: [
      "Unlimited VibeTokens",
      "Shared team workspace",
      "Admin controls & audit logs",
      "Dedicated support + SLA",
    ],
  },
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
    question: "What are VibeTokens?",
    answer:
      "VibeTokens are the usage unit for VibeRecall. Each save, search, or fact update consumes tokens. Plans include monthly token allowances with rollover.",
  },
  {
    question: "Can I export my data?",
    answer:
      "Yes. Pro and Team plans include full JSON export of all your project memory — episodes, facts, and the complete knowledge graph.",
  },
];

export const footerColumns: FooterLinkColumn[] = [
  {
    title: "Product",
    links: ["Features", "Pricing", "Documentation", "Changelog"],
  },
  {
    title: "Company",
    links: ["About", "Blog", "Contact"],
  },
  {
    title: "Legal",
    links: ["Privacy Policy", "Terms of Service"],
  },
];
