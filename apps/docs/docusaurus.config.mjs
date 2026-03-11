/** @type {import('@docusaurus/types').Config} */
const config = {
  title: "VibeRecall Docs",
  tagline: "Documentation for the VibeRecall MCP memory platform.",
  favicon: "data:,",
  url: process.env.DOCUSAURUS_URL ?? "https://docs.example.com",
  baseUrl: "/",
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
