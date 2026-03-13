type PublicEnv = {
  marketingUrl: string;
  appUrl: string;
  docsUrl: string;
  mcpBaseUrl: string;
  supabaseUrl: string;
  supabasePublishableKey: string;
  hasSupabase: boolean;
};

type PublicEnvSource = Partial<
  Pick<
    NodeJS.ProcessEnv,
    | "APP_ENV"
    | "VERCEL_ENV"
    | "NEXT_PUBLIC_MARKETING_URL"
    | "NEXT_PUBLIC_APP_URL"
    | "NEXT_PUBLIC_DOCS_URL"
    | "NEXT_PUBLIC_MCP_BASE_URL"
    | "NEXT_PUBLIC_SUPABASE_URL"
    | "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"
  >
>;

const LOCAL_PUBLIC_DEFAULTS = {
  NEXT_PUBLIC_MARKETING_URL: "http://localhost:3000",
  NEXT_PUBLIC_APP_URL: "http://localhost:3000",
  NEXT_PUBLIC_DOCS_URL: "http://localhost:3001",
  NEXT_PUBLIC_MCP_BASE_URL: "http://localhost:8010",
} as const;

function isProductionEnv(env: PublicEnvSource): boolean {
  return (
    (env.APP_ENV ?? "").trim().toLowerCase() === "production" ||
    (env.VERCEL_ENV ?? "").trim().toLowerCase() === "production"
  );
}

function readPublicUrl(
  env: PublicEnvSource,
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

export function resolvePublicEnv(env: PublicEnvSource): PublicEnv {
  const marketingUrl = readPublicUrl(env, "NEXT_PUBLIC_MARKETING_URL");
  const appUrl = readPublicUrl(env, "NEXT_PUBLIC_APP_URL");
  const docsUrl = readPublicUrl(env, "NEXT_PUBLIC_DOCS_URL");
  const mcpBaseUrl = readPublicUrl(env, "NEXT_PUBLIC_MCP_BASE_URL");
  const supabaseUrl = env.NEXT_PUBLIC_SUPABASE_URL?.trim() ?? "";
  const supabasePublishableKey = env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim() ?? "";

  return {
    marketingUrl,
    appUrl,
    docsUrl,
    mcpBaseUrl,
    supabaseUrl,
    supabasePublishableKey,
    hasSupabase: Boolean(supabaseUrl && supabasePublishableKey),
  };
}

function readProcessPublicEnv(): PublicEnvSource {
  // Direct NEXT_PUBLIC_* access keeps client-side env values eligible for Next.js build-time inlining.
  return {
    APP_ENV: process.env.APP_ENV,
    VERCEL_ENV: process.env.VERCEL_ENV,
    NEXT_PUBLIC_MARKETING_URL: process.env.NEXT_PUBLIC_MARKETING_URL,
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
    NEXT_PUBLIC_DOCS_URL: process.env.NEXT_PUBLIC_DOCS_URL,
    NEXT_PUBLIC_MCP_BASE_URL: process.env.NEXT_PUBLIC_MCP_BASE_URL,
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
  };
}

export const publicEnv = resolvePublicEnv(readProcessPublicEnv());
