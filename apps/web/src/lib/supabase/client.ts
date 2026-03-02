import { createBrowserClient } from "@supabase/ssr";

import { publicEnv } from "@/lib/env";

export function createBrowserSupabaseClient() {
  if (!publicEnv.hasSupabase) {
    return null;
  }

  return createBrowserClient(publicEnv.supabaseUrl, publicEnv.supabasePublishableKey);
}
