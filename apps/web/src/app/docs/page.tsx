import Link from "next/link";
import { ArrowRight, TerminalSquare } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function DocsPage() {
  return (
    <AppShell
      eyebrow="Onboarding"
      title="Connect your IDE to VibeRecall MCP in minutes."
      description="Use this checklist to create a project, mint a token once, and verify save/search flows from your coding agent."
      actions={
        <Button asChild variant="outline">
          <Link href="/projects">
            Open projects
            <ArrowRight className="size-4" />
          </Link>
        </Button>
      }
    >
      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="border-black/8 bg-white/75">
          <CardHeader>
            <CardDescription>Quickstart</CardDescription>
            <CardTitle>IDE connection checklist</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-7 text-stone-700">
            <p>1. Sign in at /login, then open /projects.</p>
            <p>2. Create a project and copy the plaintext token immediately (shown once).</p>
            <p>3. Use endpoint format: <code className="font-mono">https://mcp.viberecall.ai/p/&lt;project_id&gt;/mcp</code>.</p>
            <p>4. Configure MCP client with bearer token: <code className="font-mono">vr_mcp_sk_...</code>.</p>
            <p>5. Run `viberecall_save` then `viberecall_search` to verify memory roundtrip.</p>
            <p>6. If your IDE starts returning <code className="font-mono">404 Session not found</code> after a backend reload or reconnect, restart the MCP client so it can initialize a fresh session.</p>
          </CardContent>
        </Card>

        <Card className="border-black/8 bg-stone-950 text-stone-50">
          <CardHeader>
            <CardDescription className="text-stone-300">Safety notes</CardDescription>
            <CardTitle className="text-stone-50">Token handling</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-7 text-stone-200">
            <p>Keep tokens in secure secrets storage, never commit into source control.</p>
            <p>Use rotate when onboarding new device; old token remains in grace window briefly.</p>
            <p>Use revoke for immediate cut-off when a token is leaked.</p>
            <p>Do not open the MCP endpoint in a normal browser tab to test it. MCP clients must negotiate the transport correctly and advertise the required Accept headers.</p>
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 font-mono text-xs">
              <TerminalSquare className="mb-2 size-4" />
              Authorization: Bearer vr_mcp_sk_...
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
