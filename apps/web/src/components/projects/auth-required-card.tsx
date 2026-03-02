import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function AuthRequiredCard() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_12%_12%,rgba(122,45,190,0.2),transparent_32%),linear-gradient(180deg,#0a0810_0%,#130d1d_100%)] px-4 py-8 md:px-8">
      <div className="mx-auto max-w-3xl">
        <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/80 text-slate-100">
          <CardHeader>
            <CardDescription className="text-slate-300">Authentication required</CardDescription>
            <CardTitle>Sign in to access project dashboard</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-slate-300">
            <p>This page renders owner-scoped control-plane data. Sign in to continue.</p>
            <Button asChild>
              <Link href="/login">Go to login</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
