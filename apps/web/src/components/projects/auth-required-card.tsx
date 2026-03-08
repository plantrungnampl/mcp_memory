import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function AuthRequiredCard() {
  return (
    <main className="min-h-screen bg-[var(--vr-bg-root)] px-4 py-8 md:px-8">
      <div className="mx-auto max-w-3xl">
        <Card className="border-[var(--vr-border)] bg-[var(--vr-bg-card)] text-[var(--vr-text-strong)]">
          <CardHeader>
            <CardDescription className="text-[var(--vr-text-main)]">Authentication required</CardDescription>
            <CardTitle>Sign in to access project dashboard</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-[var(--vr-text-main)]">
            <p>This page renders owner-scoped control-plane data. Sign in to continue.</p>
            <Button
              asChild
              className="bg-gradient-to-r from-[var(--vr-accent)] to-[var(--vr-accent-2)] text-white hover:brightness-110"
            >
              <Link href="/login">Go to login</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
