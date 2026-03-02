import { AppShell } from "@/components/app-shell";
import { LoginActions } from "@/components/login-actions";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { publicEnv } from "@/lib/env";

export default function LoginPage() {
  return (
    <AppShell
      eyebrow="Auth shell"
      title="Connect Supabase Auth before opening the control plane."
      description="This first slice wires the App Router shell, Supabase SSR helpers, and callback routes. The UI intentionally stays thin while the MCP backend becomes operational."
    >
      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <Card className="border-black/8 bg-white/75">
          <CardHeader>
            <CardDescription>Sign in</CardDescription>
            <CardTitle>OAuth or magic link</CardTitle>
          </CardHeader>
          <CardContent>
            <LoginActions appUrl={publicEnv.appUrl} enabled={publicEnv.hasSupabase} />
          </CardContent>
        </Card>

        <div className="grid gap-4">
          <Card className="border-black/8 bg-stone-950 text-stone-50">
            <CardHeader>
              <CardDescription className="text-stone-300">Environment</CardDescription>
              <CardTitle className="text-stone-50">Current wiring status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-stone-200">
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                NEXT_PUBLIC_SUPABASE_URL: {publicEnv.supabaseUrl ? "set" : "missing"}
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY:{" "}
                {publicEnv.supabasePublishableKey ? "set" : "missing"}
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                Redirect callback: {publicEnv.appUrl}/auth/callback
              </div>
            </CardContent>
          </Card>

          <Card className="border-black/8 bg-[linear-gradient(160deg,rgba(176,120,52,0.14),rgba(255,251,245,0.88))]">
            <CardHeader>
              <CardDescription>Why this page exists</CardDescription>
              <CardTitle>Shell first, then account flows</CardTitle>
            </CardHeader>
            <CardContent className="text-sm leading-7 text-stone-700">
              Supabase auth is wired through a dedicated callback route and a root `proxy.ts`
              refresh path so session handling can grow without refactoring the layout later.
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
