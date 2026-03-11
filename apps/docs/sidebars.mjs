/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  docsSidebar: [
    "intro",
    {
      type: "category",
      label: "Getting Started",
      items: ["getting-started/quickstart", "getting-started/local-development"],
    },
    {
      type: "category",
      label: "MCP Reference",
      items: ["mcp-reference/connection", "mcp-reference/tool-surface"],
    },
    {
      type: "category",
      label: "Agent Guides",
      items: [
        "agent-guides/overview",
        "agent-guides/codex",
        "agent-guides/claude-code",
        "agent-guides/installation-profiles",
        "agent-guides/local-workspace-bridge",
      ],
    },
    {
      type: "category",
      label: "Playbooks & Rules",
      items: [
        "playbooks/agent-rules-overview",
        "playbooks/codex-rules-template",
        "playbooks/claude-rules-template",
        "playbooks/task-playbook",
        "playbooks/failure-recovery",
      ],
    },
    {
      type: "category",
      label: "Architecture",
      items: ["architecture/system-overview", "architecture/deployment-topology"],
    },
    {
      type: "category",
      label: "Troubleshooting",
      items: ["troubleshooting/common-failures"],
    },
  ],
};

export default sidebars;
