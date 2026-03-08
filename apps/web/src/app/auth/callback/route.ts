import { NextResponse } from "next/server";

import { publicEnv } from "@/lib/env";
import { getServerSupabaseClient } from "@/lib/supabase/server";

function resolveSafeNextPath(value: string | null): string {
  if (!value) {
    return "/projects";
  }

  if (!value.startsWith("/") || value.startsWith("//")) {
    return "/projects";
  }

  return value;
}

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get("code");
  const next = resolveSafeNextPath(requestUrl.searchParams.get("next"));

  if (!code) {
    return NextResponse.redirect(new URL("/login", publicEnv.appUrl));
  }

  const supabase = await getServerSupabaseClient();
  if (!supabase) {
    return NextResponse.redirect(new URL("/login", publicEnv.appUrl));
  }

  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) {
    return NextResponse.redirect(new URL("/login", publicEnv.appUrl));
  }

  return NextResponse.redirect(new URL(next, publicEnv.appUrl));
}
