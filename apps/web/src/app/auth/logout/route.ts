import { NextResponse } from "next/server";

import { publicEnv } from "@/lib/env";
import { getServerSupabaseClient } from "@/lib/supabase/server";

export async function POST() {
  const supabase = await getServerSupabaseClient();

  if (supabase) {
    await supabase.auth.signOut();
  }

  return NextResponse.redirect(new URL("/login", publicEnv.appUrl), 303);
}
