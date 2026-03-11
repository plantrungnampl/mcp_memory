---
title: Deployment Topology
sidebar_position: 2
---

The supported public hosting pattern separates the control plane, docs site, and MCP runtime by responsibility.

## Recommended public topology

- `app.<your-domain>` -> `apps/web` on Vercel
- `docs.<your-domain>` -> `apps/docs` on Vercel
- `api.<your-domain>` -> MCP API runtime

The backend runtime can be hosted on:

- a single DigitalOcean Droplet using Docker Compose, Caddy, Redis, and FalkorDB
- Render for API and worker, with Redis provisioned separately

The public docs stay separate on purpose. They are documentation, not a special route tree inside the control plane.

## Why the docs site is separate

- Docs release independently from the control plane
- Public documentation does not need the web app runtime
- `app.<your-domain>/docs` can remain a compatibility redirect instead of duplicating content
- docs outages and control-plane outages can be reasoned about separately

## Web env contract

The control plane should be built with:

- `NEXT_PUBLIC_APP_URL=https://app.<your-domain>`
- `NEXT_PUBLIC_DOCS_URL=https://docs.<your-domain>`
- `NEXT_PUBLIC_MCP_BASE_URL=https://api.<your-domain>`

Keep `NEXT_PUBLIC_*` values aligned before the Vercel build starts, because they are baked into the client bundle at build time.

If `NEXT_PUBLIC_DOCS_URL` is wrong at build time, `/docs` in the web app will redirect to the wrong place until you rebuild and redeploy.

## Recommended production split

Use this separation unless you have a strong reason not to:

- Vercel project 1: `apps/web`
- Vercel project 2: `apps/docs`
- backend runtime: API, worker, Redis, and graph services on the chosen backend path

Benefits:

- the docs site can stay static and simple
- the control plane can evolve without dragging docs deployment concerns into every change
- the MCP runtime can scale or fail independently of the docs surface

## Operational rollout order

Use this order for first public rollout:

1. deploy `apps/docs`
2. confirm `docs.<your-domain>` resolves and renders
3. deploy `apps/web` with `NEXT_PUBLIC_DOCS_URL` pointing at the docs domain
4. deploy the MCP runtime at `api.<your-domain>`
5. verify the quickstart flow against the public API domain

That order avoids the awkward intermediate state where the web app redirects users to a docs host that does not exist yet.

## Hosted rollout checklist

Before public cutover:

1. run repo-level validation
2. deploy the web app and docs app as separate Vercel projects
3. deploy the API runtime on the chosen backend path
4. run MCP smoke checks against `api.<your-domain>`
5. run browser QA against `app.<your-domain>`
6. verify the docs site loads correctly at `docs.<your-domain>`

## Local-to-hosted alignment checklist

Before you call a deployment "good", verify:

- the local docs dev server and production docs host use the same information architecture
- `NEXT_PUBLIC_DOCS_URL` matches the real docs deployment
- MCP smoke instructions in the docs reference the public API host, not an internal admin route
- agent setup examples use placeholders consistently
- browser links from the control plane land on the external docs site

That check is cheap and catches most docs-topology regressions.
