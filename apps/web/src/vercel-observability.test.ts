import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("apps/web declares the Vercel Speed Insights dependency", async () => {
  const packageJson = JSON.parse(
    await readFile(new URL("../package.json", import.meta.url), "utf8"),
  ) as {
    dependencies?: Record<string, string>;
  };

  assert.ok(
    packageJson.dependencies?.["@vercel/speed-insights"],
    "expected apps/web/package.json to include @vercel/speed-insights",
  );
});

test("root layout mounts Speed Insights for production observability", async () => {
  const source = await readFile(new URL("./app/layout.tsx", import.meta.url), "utf8");

  assert.match(source, /@vercel\/speed-insights\/next/);
  assert.match(source, /publicEnv\.isProduction/);
  assert.match(source, /<SpeedInsights\s*\/>/);
});
