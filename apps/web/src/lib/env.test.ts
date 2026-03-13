import assert from "node:assert/strict";
import test from "node:test";

test("resolvePublicEnv uses local defaults outside production", async () => {
  const { resolvePublicEnv } = await import("./env");

  const resolved = resolvePublicEnv({
    APP_ENV: "development",
  });

  assert.equal(resolved.marketingUrl, "http://localhost:3000");
  assert.equal(resolved.appUrl, "http://localhost:3000");
  assert.equal(resolved.docsUrl, "http://localhost:3001");
  assert.equal(resolved.mcpBaseUrl, "http://localhost:8010");
});

test("resolvePublicEnv throws when required public urls are missing in production", async () => {
  const { resolvePublicEnv } = await import("./env");

  assert.throws(
    () =>
      resolvePublicEnv({
        APP_ENV: "production",
        NEXT_PUBLIC_APP_URL: "https://app.example.com",
        NEXT_PUBLIC_DOCS_URL: "https://docs.example.com",
        NEXT_PUBLIC_MCP_BASE_URL: "https://api.example.com",
      }),
    /Missing required public environment variable: NEXT_PUBLIC_MARKETING_URL/,
  );
});

test("resolvePublicEnv enables Supabase only when both public values are present", async () => {
  const { resolvePublicEnv } = await import("./env");

  const configured = resolvePublicEnv({
    APP_ENV: "development",
    NEXT_PUBLIC_SUPABASE_URL: "https://example.supabase.co",
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_example",
  });
  const missingKey = resolvePublicEnv({
    APP_ENV: "development",
    NEXT_PUBLIC_SUPABASE_URL: "https://example.supabase.co",
  });

  assert.equal(configured.hasSupabase, true);
  assert.equal(configured.supabaseUrl, "https://example.supabase.co");
  assert.equal(configured.supabasePublishableKey, "sb_publishable_example");
  assert.equal(missingKey.hasSupabase, false);
});

test("resolveServerEnv requires explicit control plane api base url", async () => {
  process.env.CONTROL_PLANE_API_BASE_URL = "https://api.example.com";
  process.env.CONTROL_PLANE_INTERNAL_SECRET = "test-secret";
  const { resolveServerEnv } = await import("./server-env");

  assert.throws(
    () =>
      resolveServerEnv({
        NODE_ENV: "test",
        CONTROL_PLANE_INTERNAL_SECRET: "test-secret",
      } as NodeJS.ProcessEnv),
    /Missing required server environment variable: CONTROL_PLANE_API_BASE_URL/,
  );
});
