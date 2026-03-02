"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { publicEnv } from "@/lib/env";
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
      <div className="flex items-center gap-3">
        <Link
          href="/projects"
          className="hidden rounded-lg bg-[#7a2dbe] px-5 py-2 text-sm font-bold text-white shadow-[0_0_20px_-5px_rgba(122,45,190,0.5)] transition-all hover:bg-[#6a24a8] sm:inline-flex"
        >
          Projects
        </Link>
        <div className="flex items-center gap-2 rounded-full border border-white/12 bg-slate-900/80 px-2 py-1.5">
          <div className="flex size-6 items-center justify-center rounded-full border border-white/15 bg-[#182739] text-xs font-semibold text-[#00f5ff]">
            {getAvatarInitial(authState.email)}
          </div>
          <span className="hidden max-w-[12rem] truncate text-xs text-slate-300 md:inline">
            {authState.email}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-4">
      <Link
        href="/login"
        className="hidden rounded-lg bg-[#7a2dbe] px-5 py-2 text-sm font-bold text-white shadow-[0_0_20px_-5px_rgba(122,45,190,0.5)] transition-all hover:bg-[#6a24a8] sm:inline-flex"
      >
        Sign In
      </Link>
      <div className="flex size-8 items-center justify-center overflow-hidden rounded-full border border-white/10 bg-slate-800">
        <span
          className={`size-2.5 rounded-full ${authState.isLoading ? "bg-slate-500" : "bg-[#00f5ff]"}`}
        />
      </div>
    </div>
  );
}
