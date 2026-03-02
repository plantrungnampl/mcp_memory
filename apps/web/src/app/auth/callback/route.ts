import { NextResponse } from "next/server";

import { publicEnv } from "@/lib/env";
import { getServerSupabaseClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get("code");
  const next = requestUrl.searchParams.get("next") ?? "/projects";

  if (!code) {
    return NextResponse.redirect(new URL("/login", publicEnv.appUrl));
  }

  const supabase = await getServerSupabaseClient();
  if (!supabase) {
    return NextResponse.redirect(new URL("/login", publicEnv.appUrl));
  }

  await supabase.auth.exchangeCodeForSession(code);

  return NextResponse.redirect(new URL(next, publicEnv.appUrl));
}
