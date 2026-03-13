import assert from "node:assert/strict";
import test from "node:test";

import { resolveHostRedirect } from "./proxy";

test("resolveHostRedirect sends apex host traffic to canonical marketing host", () => {
  const redirect = resolveHostRedirect("https://viberecall.dev/", "viberecall.dev", {
    marketingOrigin: "https://www.viberecall.dev",
    appOrigin: "https://app.viberecall.dev",
  });

  assert.deepEqual(redirect, {
    destination: "https://www.viberecall.dev/",
    statusCode: 308,
  });
});

test("resolveHostRedirect sends marketing app paths to the app host", () => {
  const redirect = resolveHostRedirect("https://www.viberecall.dev/projects/setup?from=hero", "www.viberecall.dev", {
    marketingOrigin: "https://www.viberecall.dev",
    appOrigin: "https://app.viberecall.dev",
  });

  assert.deepEqual(redirect, {
    destination: "https://app.viberecall.dev/projects/setup?from=hero",
    statusCode: 308,
  });
});

test("resolveHostRedirect sends the app root to login", () => {
  const redirect = resolveHostRedirect("https://app.viberecall.dev/", "app.viberecall.dev", {
    marketingOrigin: "https://www.viberecall.dev",
    appOrigin: "https://app.viberecall.dev",
  });

  assert.deepEqual(redirect, {
    destination: "https://app.viberecall.dev/login",
    statusCode: 307,
  });
});

test("resolveHostRedirect stays idle for local development", () => {
  const redirect = resolveHostRedirect("http://localhost:3000/projects", "localhost:3000", {
    marketingOrigin: "http://localhost:3000",
    appOrigin: "http://localhost:3000",
  });

  assert.equal(redirect, null);
});
