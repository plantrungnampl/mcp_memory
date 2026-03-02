import { NextResponse } from "next/server";

import { publicEnv } from "@/lib/env";

export async function GET() {
  return NextResponse.json({
    ok: true,
    app: "viberecall-web",
    supabaseConfigured: publicEnv.hasSupabase,
    mcpBaseUrl: publicEnv.mcpBaseUrl,
  });
}
