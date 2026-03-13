"use client";

import { useEffect, useState } from "react";

import { publicEnv } from "@/lib/env";
import { getAppUrl } from "@/lib/seo";
import { createBrowserSupabaseClient } from "@/lib/supabase/client";

type LandingAuthState = {
  isLoading: boolean;
  email: string | null;
};

function getAvatarInitial(email: string | null) {
  if (!email) {
    return "U";
  }

  return email.trim().charAt(0).toUpperCase() || "U";
}

export function LandingAuthControls() {
  const [authState, setAuthState] = useState<LandingAuthState>({
    isLoading: publicEnv.hasSupabase,
    email: null,
  });

  useEffect(() => {
    const supabase = createBrowserSupabaseClient();
    if (!supabase) {
      return;
    }

    let isMounted = true;

    const hydrateUser = async () => {
      const { data, error } = await supabase.auth.getUser();
      if (!isMounted) {
        return;
      }

      if (error || !data.user) {
        setAuthState({ isLoading: false, email: null });
        return;
      }

      setAuthState({ isLoading: false, email: data.user.email ?? null });
    };

    void hydrateUser();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!isMounted) {
        return;
      }

      setAuthState({
        isLoading: false,
        email: session?.user?.email ?? null,
      });
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const isSignedIn = Boolean(authState.email);

  if (isSignedIn) {
    return (
      <div className="hidden items-center gap-3 md:flex">
        <a
          href={getAppUrl("/projects")}
          className="rounded-lg bg-gradient-to-b from-[#7a2dbe] to-[#9333ea] px-6 py-2.5 text-sm font-semibold text-white shadow-[0_8px_22px_-12px_rgba(122,45,190,0.85)] transition-opacity hover:opacity-95"
        >
          Projects
        </a>
        <div className="flex items-center gap-2 rounded-full border border-white/12 bg-[#191925] px-2.5 py-1.5">
          <div className="flex size-6 items-center justify-center rounded-full border border-white/20 bg-[#7a2dbe]/35 text-xs font-semibold text-white">
            {getAvatarInitial(authState.email)}
          </div>
          <span className="max-w-[13rem] truncate text-xs text-[#c7c7d1]">{authState.email}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="hidden items-center gap-3 md:flex">
      <a
        href={getAppUrl("/login")}
        className="rounded-lg px-5 py-2.5 text-sm font-medium text-[#adadb0] transition-colors hover:text-white"
      >
        Sign In
      </a>
      <a
        href={getAppUrl("/projects")}
        className="rounded-lg bg-gradient-to-b from-[#7a2dbe] to-[#9333ea] px-6 py-2.5 text-sm font-semibold text-white shadow-[0_8px_22px_-12px_rgba(122,45,190,0.85)] transition-opacity hover:opacity-95"
      >
        {authState.isLoading ? "Loading..." : "Get Started"}
      </a>
    </div>
  );
}
