/** @type {import('@docusaurus/types').Config} */
const docsOrigin = process.env.DOCUSAURUS_URL?.trim();
const vercelUrl = process.env.VERCEL_URL?.trim();
const previewOrigin = vercelUrl ? `https://${vercelUrl}` : undefined;
const resolvedDocsOrigin = docsOrigin || previewOrigin || "http://localhost:3001";
const isProductionEnv =
  (process.env.APP_ENV ?? "").trim().toLowerCase() === "production" ||
  (process.env.VERCEL_ENV ?? "").trim().toLowerCase() === "production";

if (isProductionEnv && !docsOrigin) {
  throw new Error("Missing DOCUSAURUS_URL in production.");
}

const config = {
  title: "VibeRecall Docs",
  tagline: "Documentation for the VibeRecall MCP memory platform.",
  favicon: "img/favicon.svg",
  url: resolvedDocsOrigin,
  baseUrl: "/",
  noIndex: !isProductionEnv,
  onBrokenLinks: "throw",
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: "throw",
    },
  },
  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },
  presets: [
    [
      "classic",
      {
        docs: {
          routeBasePath: "/",
          sidebarPath: "./sidebars.mjs",
        },
        blog: false,
        pages: false,
        theme: {
          customCss: "./src/css/custom.css",
        },
      },
    ],
  ],
  themeConfig: {
    image: "img/social-card.png",
    navbar: {
      title: "VibeRecall Docs",
      items: [
        {
          to: "/getting-started/quickstart",
          label: "Getting Started",
          position: "left",
        },
        {
          to: "/mcp-reference/connection",
          label: "MCP Reference",
          position: "left",
        },
        {
          to: "/agent-guides/overview",
          label: "Agent Guides",
          position: "left",
        },
        {
          to: "/playbooks/agent-rules-overview",
          label: "Playbooks",
          position: "left",
        },
        {
          to: "/architecture/system-overview",
          label: "Architecture",
          position: "left",
        },
        {
          to: "/troubleshooting/common-failures",
          label: "Troubleshooting",
          position: "left",
        },
      ],
    },
    footer: {
      style: "dark",
      links: [
        {
          title: "Docs",
          items: [
            {
              label: "Quickstart",
              to: "/getting-started/quickstart",
            },
            {
              label: "Deployment Topology",
              to: "/architecture/deployment-topology",
            },
          ],
        },
        {
          title: "Agents",
          items: [
            {
              label: "Codex Guide",
              to: "/agent-guides/codex",
            },
            {
              label: "Claude Code Guide",
              to: "/agent-guides/claude-code",
            },
            {
              label: "Agent Rules",
              to: "/playbooks/agent-rules-overview",
            },
          ],
        },
      ],
      copyright: `Copyright ${new Date().getFullYear()} VibeRecall.`,
    },
  },
};

export default config;
