export type AccentTone = "primary" | "accent";

export type NavItem = {
  label: string;
  href: string;
  external?: boolean;
};

export type FeatureItem = {
  title: string;
  description: string;
  tone: AccentTone;
};

export type HowItWorksStep = {
  title: string;
  description: string;
  tone: AccentTone;
};

export type TemporalEdgeItem = {
  title: string;
  description: string;
  tone: AccentTone;
};

export type PricingPlan = {
  name: string;
  price: string;
  cadence: string;
  ctaLabel: string;
  highlighted?: boolean;
  features: Array<{
    label: string;
    included: boolean;
  }>;
};

export type FaqItem = {
  question: string;
  answer: string;
};

export const navItems: NavItem[] = [
  { label: "Features", href: "#features" },
  { label: "Pricing", href: "#pricing" },
  { label: "Docs", href: "/docs" },
  { label: "GitHub", href: "#", external: true },
];

export const compatibilityLabels = ["Claude Code", "Cursor", "Windsurf", "VS Code"];

export const featureItems: FeatureItem[] = [
  {
    title: "Temporal Knowledge Graph",
    description:
      "Powered by Graphiti for deep context mapping. Maps relationships between code entities over time.",
    tone: "primary",
  },
  {
    title: "Multi-session Recall",
    description:
      "Carry context seamlessly across sessions. Close your editor, come back weeks later, your agent still knows.",
    tone: "accent",
  },
  {
    title: "100% Project Isolation",
    description:
      "Strict boundaries for security. Context from Project A will never leak into Project B. Private and secure.",
    tone: "primary",
  },
  {
    title: "Bi-temporal Awareness",
    description:
      'Understand the "Why" and "When". See how your logic evolved to prevent repeating past architectural mistakes.',
    tone: "accent",
  },
];

export const howItWorksSteps: HowItWorksStep[] = [
  {
    title: "1. Connect MCP",
    description:
      "Paste your unique VibeRecall URL into Cursor, Claude, or Windsurf settings in seconds.",
    tone: "primary",
  },
  {
    title: "2. Code Naturally",
    description:
      "The agent automatically saves coding episodes and architectural decisions to your graph.",
    tone: "accent",
  },
  {
    title: "3. Precise Recall",
    description:
      'Ask "Why did we choose this pattern?" and get an immediate, context-aware answer.',
    tone: "primary",
  },
];

export const temporalEdgeItems: TemporalEdgeItem[] = [
  {
    title: "Bi-temporal Awareness",
    description:
      "Track events by both when they happened in your project history and when they were recorded in the system.",
    tone: "accent",
  },
  {
    title: "Incremental Memory Updates",
    description:
      "Only new context is ingested. No more re-sending massive files to your agent's context window.",
    tone: "primary",
  },
  {
    title: "Entity Relationship Graph",
    description:
      "Memory isn't a flat file; it's a living graph of your code's entities, functions, and logic chains.",
    tone: "accent",
  },
];

export const pricingPlans: PricingPlan[] = [
  {
    name: "Free",
    price: "$0",
    cadence: "/forever",
    ctaLabel: "Get Started",
    features: [
      { label: "Basic memory persistence", included: true },
      { label: "100 VibeTokens / month", included: true },
      { label: "No Priority Support", included: false },
    ],
  },
  {
    name: "Pro",
    price: "$9",
    cadence: "/month",
    ctaLabel: "Go Pro Now",
    highlighted: true,
    features: [
      { label: "Unlimited Session History", included: true },
      { label: "5,000 VibeTokens / month", included: true },
      { label: "Priority Recall Speed", included: true },
      { label: "Advanced Graph Insight", included: true },
    ],
  },
  {
    name: "Team",
    price: "$29",
    cadence: "/month",
    ctaLabel: "Contact Sales",
    features: [
      { label: "Shared Team Workspace", included: true },
      { label: "Unlimited VibeTokens", included: true },
      { label: "Admin Dashboard & Controls", included: true },
    ],
  },
];

export const securityHighlights = [
  "100% Project Isolation - No Cross-Project Leakage",
  "AES-256 Encryption at Rest & In-Transit",
  "SOC2 Type II Ready Architecture",
];

export const faqItems: FaqItem[] = [
  {
    question: "Is my data private?",
    answer:
      "Yes. Each project has its own isolated memory graph. We never use your data to train models, and our infrastructure follows strict SOC2 guidelines.",
  },
  {
    question: "Does this add latency to my agent?",
    answer:
      "VibeRecall is built for speed. Recall queries typically take less than 150ms, ensuring your agent's response time remains snappy.",
  },
  {
    question: "What are VibeTokens?",
    answer:
      "VibeTokens are our unit of measure for memory storage and indexing. 5,000 tokens per month is typically enough for active development on 3-4 medium-sized projects.",
  },
  {
    question: "Can I export my memory?",
    answer:
      "Absolutely. You can export your entire knowledge graph as a structured JSON file at any time from the dashboard.",
  },
];

export const footerLinks = ["Terms", "Privacy", "Security", "Status"];
