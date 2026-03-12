type PublicEnv = {
  appUrl: string;
  docsUrl: string;
  mcpBaseUrl: string;
  supabaseUrl: string;
  supabasePublishableKey: string;
  hasSupabase: boolean;
};

const LOCAL_PUBLIC_DEFAULTS = {
  NEXT_PUBLIC_APP_URL: "http://localhost:3000",
  NEXT_PUBLIC_DOCS_URL: "http://localhost:3001",
  NEXT_PUBLIC_MCP_BASE_URL: "http://localhost:8010",
} as const;

function isProductionEnv(env: NodeJS.ProcessEnv): boolean {
  return (
    (env.APP_ENV ?? "").trim().toLowerCase() === "production" ||
    (env.VERCEL_ENV ?? "").trim().toLowerCase() === "production"
  );
}

function readPublicUrl(
  env: NodeJS.ProcessEnv,
  name: keyof typeof LOCAL_PUBLIC_DEFAULTS,
): string {
  const value = env[name]?.trim();
  if (value) {
    return value;
  }
  if (isProductionEnv(env)) {
    throw new Error(`Missing required public environment variable: ${name}`);
  }
  return LOCAL_PUBLIC_DEFAULTS[name];
}

export function resolvePublicEnv(env: NodeJS.ProcessEnv = process.env): PublicEnv {
  const appUrl = readPublicUrl(env, "NEXT_PUBLIC_APP_URL");
  const docsUrl = readPublicUrl(env, "NEXT_PUBLIC_DOCS_URL");
  const mcpBaseUrl = readPublicUrl(env, "NEXT_PUBLIC_MCP_BASE_URL");
  const supabaseUrl = env.NEXT_PUBLIC_SUPABASE_URL?.trim() ?? "";
  const supabasePublishableKey = env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim() ?? "";

  return {
    appUrl,
    docsUrl,
    mcpBaseUrl,
    supabaseUrl,
    supabasePublishableKey,
    hasSupabase: Boolean(supabaseUrl && supabasePublishableKey),
  };
}

export const publicEnv = resolvePublicEnv();
