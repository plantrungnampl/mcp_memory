# CONTINUITY.md (Canonical)
## Goal
- Keep the repository aligned with the current spec-v3 backend reality without widening scope unnecessarily.
- Treat the current entity-resolution and unresolved-mention backend slice in `apps/mcp-api` as code-complete unless new defects are found.
- Close the current spec-v3 pass through rollout validation evidence when a real deployed target is available.
- Add a supported public deployment path for `apps/web` on Vercel with the backend runtime on a DigitalOcean Droplet, without breaking the existing Render path.
- Add a standalone public Docusaurus docs surface in `apps/docs` without breaking the control-plane onboarding flow.
- Expand the public docs content so external operators and AI coding-agent users can run VibeRecall without needing the internal spec bundle.

## Constraints
- Default to the smallest safe change set.
- Do not change MCP runtime behavior, schema, or public contracts unless validation exposes a concrete defect.
- Keep this file as a current-state ledger, not a running changelog.
- Query existing project memory before substantial project work.
- For Next.js implementation work, consult the local Next.js docs / MCP docs flow before coding.
- Public docs must remain a separate static site; `apps/web` should only keep `/docs` as a compatibility redirect.

## Key decisions
- On 2026-03-11, the current spec-v3 entity-resolution pass was closed as a docs/contract/rollout-alignment pass, not a new backend feature slice.
- The public MCP surface currently has 25 tools; docs and READMEs must track that runtime truth instead of the older 11-tool snapshot.
- `viberecall_resolve_reference` keeps the additive `unresolved_mention` response field; no new public tool was added in this closeout.
- Remote Supabase migration history for the entity-resolution slice was repaired on 2026-03-11 by recording `017_entity_resolution_foundation` as version `20260310151321`, derived from the migration file's UTC timestamp.
- Backend Python support is treated as `>=3.12,<3.14`, matching `apps/mcp-api/pyproject.toml`; docs should not imply broader support.
- Current runtime auth remains Supabase-based in `apps/web`; Clerk guidance in repo instructions is policy for future auth work, not the active runtime implementation.
- On 2026-03-11, the preferred self-managed hosted topology was set to `apps/web` on Vercel plus `api + worker + falkordb + redis` on one DigitalOcean Droplet via Docker Compose and a host-level Caddy reverse proxy.
- The DigitalOcean path keeps Postgres external, keeps the full async runtime (`QUEUE_BACKEND=celery`), and self-hosts Redis for now to minimize rollout change.
- On 2026-03-11, public docs moved to a standalone `apps/docs` Docusaurus 3.9.2 app intended for `docs.<domain>`.
- `apps/web` keeps `/docs` only as a compatibility redirect driven by `NEXT_PUBLIC_DOCS_URL`; landing/docs CTAs must use that env value instead of hardcoding an internal route.
- Public docs content is curated under `apps/docs/docs` from repo-root `docs/` and `viberecall_spec_md/`; internal-only quota, capacity, and backlog material stays outside the public site.
- On 2026-03-11, the public docs site was expanded beyond onboarding into six sections: Getting Started, MCP Reference, Agent Guides, Playbooks & Rules, Architecture, and Troubleshooting.
- Codex and Claude Code guidance remains remote-HTTP-first and tool-first; prompts and resources are documented only as optional, compatibility-dependent accelerators.
- On 2026-03-11, the copy-paste agent rules were strengthened to require `viberecall_get_status` at task start, explicit stop-and-ask behavior for unclear scope or trust boundaries, and stricter gating for indexing and fact correction.
- On 2026-03-11, the public landing page scope was narrowed away from pricing-tier marketing: the navbar and footer should no longer surface `Pricing`, the pricing cards were replaced with a free-access banner, and public landing FAQ copy should avoid paid-plan language.
- On 2026-03-11, internal `/projects` UI work was narrowed to a presentation-only scrub: visible plan labels should be removed from the sidebar card, project tiles, and directory table, while the underlying `free/pro/team` model remains unchanged.
- On 2026-03-11, the `/projects/[projectId]/tokens` page was narrowed further to end-user actions only: maintenance controls should be hidden from the current user-facing tokens UI while retention/migration/purge capabilities remain implemented behind the existing server and backend layers.
- On 2026-03-11, project-facing copy actions in the MCP setup and token surfaces were standardized on a shared client-side clipboard helper with a fallback path, so copy buttons do not depend solely on `navigator.clipboard.writeText()`.
- On 2026-03-11, the project workspace header ID chip was corrected from a decorative server-rendered icon into a real client-side copy control using the shared clipboard helper.

## State
- Backend validation for the current entity-resolution/unresolved-mention slice is green.
- Live Supabase schema and migration history are aligned for `016_pin_memory_salience`, `017_entity_resolution_foundation`, and `018_unresolved_mentions_identity`.
- Spec docs, backend README, and root README are aligned with the implemented backend contract and scope model.
- The repo contains explicit DigitalOcean deployment artifacts alongside the existing Render artifacts: a DO-specific compose file, a Caddy proxy config, and a Vercel + DigitalOcean runbook.
- The repo now contains a standalone Docusaurus docs app under `apps/docs`, with expanded public docs for getting started, MCP reference, agent guides, playbooks, architecture, and troubleshooting.
- `apps/web/src/app/docs/page.tsx` now redirects to the external docs URL instead of rendering a separate onboarding page.
- Validation for the docs split completed on 2026-03-11 with one environment caveat: Docusaurus build passed, web typecheck passed, and the web production build passed with webpack fallback after the default Turbopack build hit an environment-level panic while binding a port during CSS processing.
- The current docs content now includes public-safe Codex and Claude Code setup guidance, installation profiles, local workspace bridge guidance, and copy-paste agent rule templates.
- The current playbooks now enforce stricter agent behavior around project verification, trust-boundary escalation, and canonical-memory mutation.
- The public landing page now presents VibeRecall as free for everyone at the marketing layer only; internal plan models and backend contracts remain unchanged in this pass.
- The `/projects` UI no longer needs to surface plan tiers directly; usage and created-date presentation are sufficient for the current product posture.
- The `/projects/[projectId]/tokens` UI no longer needs to surface maintenance operations to normal users; exports, tokens, connection, usage, and logs remain user-facing, while maintenance stays as an internal capability.
- The MCP setup and token-related copy controls now share one clipboard implementation with a fallback path for stricter browser/security contexts.
- The workspace header project ID chip is now an actual copy action instead of a static icon.

## Done
- Refreshed `README.md`, `apps/mcp-api/README.md`, and `viberecall_spec_md/` contract docs to match the current 25-tool MCP runtime.
- Corrected residual spec-v3 doc drift in `01_architecture.md`, `06_pipelines_latency.md`, `appendix_A_mcp_examples.md`, and `appendix_D_capacity.md`.
- Fixed `apps/mcp-api/scripts/smoke_deployed_mcp.py` so SSE responses are parsed from the first `data:` frame instead of hanging on `response.read()` against FastMCP keep-alive streams.
- Verified focused backend graph tests: `cd apps/mcp-api && uv run pytest -q tests/test_mcp_graph.py` -> `17 passed`.
- Verified full backend suite: `pnpm test:backend` -> `162 passed, 2 skipped`.
- Verified repo release gate twice during the spec closeout before this docs pass.
- Repaired remote Supabase migration-history drift for `017_entity_resolution_foundation` and confirmed ordering in `supabase_migrations.schema_migrations`.
- Added `ops/docker-compose.digitalocean.yml` for the hosted DigitalOcean runtime with persistent mounts for FalkorDB, Redis, object storage, and export storage.
- Added `ops/caddy/Caddyfile` and `ops/vercel-digitalocean-public-ga.md` for the default Vercel + DigitalOcean public rollout path.
- Added `apps/docs` with Docusaurus 3.9.2 configuration, curated public docs content, and root scripts for local docs development and docs validation.
- Wired `NEXT_PUBLIC_DOCS_URL` into `apps/web`, root env examples, and the repo CI surface.
- Verified `node /home/theshy/.cache/node/corepack/v1/pnpm/10.30.3/bin/pnpm.cjs --dir apps/docs build`.
- Verified `node /home/theshy/.cache/node/corepack/v1/pnpm/10.30.3/bin/pnpm.cjs --dir apps/web typecheck`.
- Verified `./node_modules/.bin/next build --webpack` from `apps/web`.
- Observed that the default `next build` Turbopack path panics in this environment with `Operation not permitted` while binding a port during CSS processing; treat that as an environment-specific validator issue, not a confirmed regression from this docs slice.
- Expanded `apps/docs` content with detailed operator guidance, deeper MCP reference pages, Codex and Claude Code guides, and copy-paste playbooks for AI coding agents.
- Strengthened the public rules templates so normal coding agents must verify runtime/project status first, stop on unclear scope, and avoid unsanctioned indexing or fact correction.
- Removed pricing-tier messaging from the public landing shell and replaced it with free-for-everyone messaging without changing internal plan or billing-related code paths.
- Scrubbed visible plan labels from the internal `/projects` UI while keeping plan-backed quota calculations and control-plane contracts intact.
- Hid the maintenance section from the `/projects/[projectId]/tokens` page and removed its user-facing wiring from the page/component boundary, while keeping existing maintenance server actions and backend routes untouched.
- Added a shared clipboard helper in `apps/web` and rewired the project-created modal, token-issued modal, and quick integration credentials panel to use it.
- Replaced the static project ID chip in the workspace header with a dedicated client component that copies the active project ID and provides visual feedback.
- Verified `pnpm --dir apps/docs build` after the docs-content expansion.
- Verified `git diff --check -- apps/docs CONTINUITY.md` for tracked changes; `apps/docs` is untracked in this checkout, so exact source files must still be enumerated manually when reporting this turn.
- Verified `pnpm --dir apps/web typecheck` and `pnpm --dir apps/web build` after hiding the user-facing maintenance controls.
- Verified `pnpm --dir apps/web typecheck` and `pnpm --dir apps/web build` after the clipboard-fallback patch.
- Verified `pnpm --dir apps/web typecheck` and `pnpm --dir apps/web build` after making the workspace header project ID chip clickable.

## Now
- Repository state is stable after the spec closeout, migration-history repair, and hosted-topology docs updates.
- The current active slice is the user-facing control-plane cleanup pass on `apps/web`, keeping operator-only concepts out of the normal project UI without changing backend capability.
- Remaining work after this turn is operational only: provision the real docs Vercel project and bind a production `docs.<domain>`.

## Next
- Provision a separate Vercel project for `apps/docs` and bind `docs.<domain>` once a real production domain is chosen.
- Populate Vercel and Droplet production envs, then launch `ops/docker-compose.digitalocean.yml` behind Caddy.
- Run `pnpm smoke:mcp:deployed -- --base-url <deployed_api_base> --project-id <qa_project_id> --token <qa_plaintext_token>` once a real target is available.
- Run authenticated browser QA for `/projects`, `/projects/[projectId]/tokens`, `/projects/[projectId]/api-logs`, `/projects/[projectId]/usage`, and `/projects/[projectId]/graphs/playground` on the deployed web app.
- Run deployed browser QA for `https://docs.<your-domain>` and confirm `https://app.<your-domain>/docs` redirects there.
- Review whether the public docs expansion should eventually be mirrored by README shortcuts or separate deploy runbooks, without widening the current docs-only scope retroactively.
- Record deployed validation results here, then only choose the next spec-v3 feature slice after rollout evidence exists.

## Open questions
- UNCONFIRMED: which real production domains will back `app.<domain>`, `docs.<domain>`, and `api.<domain>` for the public rollout.
- UNCONFIRMED: when a real QA `project_id` and plaintext MCP token will be available for deployed smoke.
- UNCONFIRMED: which bounded spec-v3 slice should land next after deployed validation is captured.
- UNCONFIRMED: whether product wants a future dedicated unresolved-mention backlog/admin surface or will keep the current additive `resolve_reference` behavior only.
