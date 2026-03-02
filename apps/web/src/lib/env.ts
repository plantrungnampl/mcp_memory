const appUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
const mcpBaseUrl = process.env.NEXT_PUBLIC_MCP_BASE_URL ?? "http://localhost:8010";
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const supabasePublishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";

export const publicEnv = {
  appUrl,
  mcpBaseUrl,
  supabaseUrl,
  supabasePublishableKey,
  hasSupabase: Boolean(supabaseUrl && supabasePublishableKey),
};
