"use client";

import { useState, useTransition } from "react";
import { Github, Mail } from "lucide-react";

import { createBrowserSupabaseClient } from "@/lib/supabase/client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type LoginActionsProps = {
  appUrl: string;
  enabled: boolean;
};

export function LoginActions({ appUrl, enabled }: LoginActionsProps) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const callbackUrl = `${appUrl.replace(/\/$/, "")}/auth/callback`;

  async function signInWithGithub() {
    if (!enabled) {
      setStatus("Supabase env vars are missing.");
      return;
    }

    const supabase = createBrowserSupabaseClient();
    if (!supabase) {
      setStatus("Supabase client could not be created.");
      return;
    }

    startTransition(async () => {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "github",
        options: {
          redirectTo: callbackUrl,
        },
      });

      setStatus(error ? error.message : "Redirecting to GitHub...");
    });
  }

  async function sendMagicLink() {
    if (!enabled) {
      setStatus("Supabase env vars are missing.");
      return;
    }

    const supabase = createBrowserSupabaseClient();
    if (!supabase) {
      setStatus("Supabase client could not be created.");
      return;
    }

    startTransition(async () => {
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: callbackUrl,
        },
      });

      setStatus(error ? error.message : "Magic link sent. Check your inbox.");
    });
  }

  return (
    <div className="grid gap-4">
      <Button disabled={isPending || !enabled} onClick={signInWithGithub} size="lg">
        <Github className="size-4" />
        Continue with GitHub
      </Button>

      <div className="grid gap-3 rounded-[1.5rem] border border-black/8 bg-stone-50/70 p-4">
        <label className="text-xs uppercase tracking-[0.2em] text-stone-500" htmlFor="email">
          Email magic link
        </label>
        <Input
          id="email"
          onChange={(event) => setEmail(event.target.value)}
          placeholder="team@viberecall.ai"
          type="email"
          value={email}
        />
        <Button
          disabled={isPending || !enabled || email.length < 4}
          onClick={sendMagicLink}
          variant="outline"
        >
          <Mail className="size-4" />
          Send sign-in link
        </Button>
      </div>

      {status ? (
        <p className="rounded-2xl bg-stone-100/80 px-4 py-3 text-sm leading-6 text-stone-600">
          {status}
        </p>
      ) : null}
    </div>
  );
}
