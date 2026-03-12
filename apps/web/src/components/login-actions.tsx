"use client";

import { useState, useTransition } from "react";
import { Mail } from "lucide-react";

import { createBrowserSupabaseClient } from "@/lib/supabase/client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type LoginActionsProps = {
  appUrl: string;
  enabled: boolean;
};

function GoogleIcon() {
  return (
    <svg
      aria-hidden="true"
      className="size-4"
      viewBox="0 0 24 24"
    >
      <path
        d="M21.8 12.23c0-.72-.06-1.25-.19-1.8H12v3.56h5.65c-.11.88-.68 2.21-1.95 3.1l-.02.12 2.84 2.15.2.02c1.86-1.68 2.92-4.15 2.92-7.15Z"
        fill="#4285F4"
      />
      <path
        d="M12 22c2.76 0 5.08-.88 6.78-2.39l-3.23-2.47c-.86.59-2.01 1-3.55 1-2.71 0-5-1.75-5.82-4.16l-.11.01-2.96 2.24-.04.1C4.76 19.65 8.1 22 12 22Z"
        fill="#34A853"
      />
      <path
        d="M6.18 13.98A5.89 5.89 0 0 1 5.84 12c0-.69.12-1.37.33-1.98l-.01-.13-2.99-2.28-.1.05A9.85 9.85 0 0 0 2 12c0 1.57.38 3.05 1.07 4.34l3.11-2.36Z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.86c1.94 0 3.24.82 3.98 1.5l2.9-2.77C17.07 2.96 14.76 2 12 2 8.1 2 4.76 4.35 3.07 7.66l3.1 2.36C7 7.61 9.29 5.86 12 5.86Z"
        fill="#EA4335"
      />
    </svg>
  );
}

export function LoginActions({ appUrl, enabled }: LoginActionsProps) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const callbackUrl = `${appUrl.replace(/\/$/, "")}/auth/callback`;

  async function signInWithGoogle() {
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
        provider: "google",
        options: {
          redirectTo: callbackUrl,
        },
      });

      setStatus(error ? error.message : "Redirecting to Google...");
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
        onClick={signInWithGoogle}
      >
        <GoogleIcon />
        Continue with Google
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
