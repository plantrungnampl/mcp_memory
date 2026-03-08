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
    <div className="grid gap-3">
      <Button
        className="h-[50px] rounded-xl bg-[#7A2DBE] text-sm font-semibold text-white hover:bg-[#8A3ED0] focus-visible:ring-[#7A2DBE]/60"
        disabled={isPending || !enabled}
        onClick={signInWithGithub}
      >
        <Github className="size-4" />
        Continue with GitHub
      </Button>

      <div className="my-1 flex items-center">
        <span className="h-px flex-1 bg-[#272243]" />
        <span className="px-3 text-xs font-medium text-[#6F6790]">or continue with email</span>
        <span className="h-px flex-1 bg-[#272243]" />
      </div>

      <div className="grid gap-2">
        <label className="text-xs font-medium text-[#C8C0E8]" htmlFor="email">
          Email magic link
        </label>
        <Input
          autoComplete="email"
          className="h-[50px] rounded-xl border-[#252145] bg-[#14122E] text-sm text-[#EDE8FF] placeholder:text-[#6E6994] focus-visible:border-[#3C3470]"
          id="email"
          onChange={(event) => setEmail(event.target.value)}
          placeholder="team@viberecall.ai"
          type="email"
          value={email}
        />
      </div>

      <Button
        className="h-[50px] rounded-xl border border-[#2D2750] bg-[#1B1735] text-sm font-semibold text-[#E2DCFF] hover:bg-[#262048] focus-visible:ring-[#7A2DBE]/60"
        disabled={isPending || !enabled || email.length < 4}
        onClick={sendMagicLink}
      >
        <Mail className="size-4" />
        Send sign-in link
      </Button>

      {status ? (
        <p className="min-h-[46px] rounded-lg border border-[#262143] bg-[#121026] px-4 py-3 text-sm leading-6 text-[#7D77A5]">
          {status}
        </p>
      ) : (
        <p className="min-h-[46px] rounded-lg border border-[#262143] bg-[#121026] px-4 py-3 text-sm leading-6 text-[#7D77A5]">
          Status messages appear here.
        </p>
      )}

      <p className="text-xs text-[#6F6790]">
        By continuing, you agree to workspace access and session policies.
      </p>
    </div>
  );
}
