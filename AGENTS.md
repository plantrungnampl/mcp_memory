# Repository Guidelines
## Working model

- The main Codex thread owns requirements, constraints, and the final answer.
- Use multi-agent for exploration, review, reproduction, and evidence gathering.
- Only the `worker` role may edit code.
- Do not allow parallel code edits by multiple agents.
- For full-stack issues, map the frontend/backend contract before changing both sides.

## Project Structure & Module Organization
This repository is a pnpm workspace with two apps under `apps/`:
- `apps/web`: Next.js 16 App Router control-plane UI (`src/app`, `src/components`, `src/lib`).
- `apps/mcp-api`: FastAPI + FastMCP backend (`src/viberecall_mcp`, `migrations`, `tests`).

Operational files live in `ops/` (for example `ops/docker-compose.runtime.yml`). Product and architecture notes are in `viberecall_spec_md/`. Environment defaults are defined in `.env`.

## Build, Test, and Development Commands
From repository root:
- `pnpm install`: install workspace dependencies.
- `pnpm dev:web`: run the web app on `http://localhost:3000`.
- `pnpm build:web`: production build for the web app.
- `pnpm lint:web`: run ESLint for the web app.

Backend (`apps/mcp-api`):
- `uv sync --locked`: install Python dependencies.
- `uv run uvicorn viberecall_mcp.app:create_app --factory --reload --port 8010`: run API locally.
- `uv run pytest -q`: run backend tests.

Optional integration suites (require local services) are documented in `apps/mcp-api/README.md`.

## Coding Style & Naming Conventions
- TypeScript/React: follow Next.js + ESLint config (`apps/web/eslint.config.mjs`), 2-space indentation, PascalCase components, kebab-case filenames for routes/util files.
- Python: PEP 8, 4-space indentation, snake_case modules/functions, explicit typing for new public interfaces.
- Keep business logic in `src/lib` (web) and `src/viberecall_mcp` (API), not in UI/view glue.

## Testing Guidelines
- Backend framework: `pytest` with `pytest-asyncio` (`[tool.pytest.ini_options]` in `pyproject.toml`).
- Place tests in `apps/mcp-api/tests` as `test_*.py`.
- Run `uv run pytest -q` before opening a PR.
- Web app currently enforces quality through `pnpm typecheck`, `pnpm lint`, and `pnpm build` (CI-required).

## Commit & Pull Request Guidelines
Git history is not available in this checkout (`.git` missing), so use Conventional Commits by default (`feat:`, `fix:`, `refactor:`, `chore:`). Keep commits focused and atomic.

PRs should include:
- Why: problem statement and scope.
- How: key implementation decisions.
- Validation: exact commands run (for example `uv run pytest -q`, `pnpm --dir apps/web build`).
- Screenshots for visible UI changes.

## Security & Configuration Tips
Do not commit secrets. Copy `.env.example` to `.env` and keep `CONTROL_PLANE_INTERNAL_SECRET` and service credentials local-only. Validate config changes against both app READMEs and CI workflow expectations.

## Good delegation patterns

### Use `explorer` when

- you need to locate ownership
- you need to trace a code path
- you need a quick map of relevant files

### Use `frontend_reviewer` when

- a Next.js page, layout, route, server action, cache, or client boundary may be involved
- hydration, routing, or state ownership is unclear

### Use `backend_reviewer` when

- request validation, response shape, typing, persistence, or error handling may be involved

### Use `contract_reviewer` when

- a full-stack issue may require coordinated frontend/backend changes
- request shape, response shape, auth assumptions, or cache boundaries may be drifting

### Use `security_reviewer` when

- auth, authorization, sessions, cookies, uploads, webhooks, CORS, or secret handling may be involved

### Use `browser_debugger` when

- the bug is user-visible in the browser
- reproduction steps, screenshots, console output, or network evidence matter

### Use `monitor` when

- a command runs for a while and someone needs to watch progress
- tests, logs, retries, or dev-server startup behavior matter

### Use `research` when

- the task depends on specs, architecture notes, product docs, or external references
- you need evidence on framework behavior or tradeoffs before implementation

### Use `worker` when

- the likely cause is already evidenced
- only a small or medium implementation should happen

## Default final-answer format for implementation tasks

1. what was wrong
2. what files changed
3. why this fix is the smallest safe fix
4. what validation ran
5. what remains unverified
Use VibeRecall as the project memory source for this repository.

Connection rules:
- Treat tools as the required integration surface.
- Do not assume prompts or resources are available.
- Start each meaningful task by calling viberecall_get_status to verify the active project and runtime health.

Default tool behavior:
- After viberecall_get_status succeeds, start meaningful tasks with viberecall_get_context_pack.
- Inspect `context_mode`, `index_status`, `index_hint`, `gaps`, `architecture_overview`, `architecture_map`, `related_modules`, `related_files`, `relevant_symbols`, and `citations` before deciding whether more repo context is needed.
- Use viberecall_search_entities only when the task is entity-centric.
- Use viberecall_get_neighbors only after the relevant entity is known.
- Save meaningful discoveries with viberecall_save_episode.
- Check viberecall_get_index_status before requesting viberecall_index_repo.

Project overview rules:
- For feature work, large refactors, and other architecture-sensitive changes on an existing codebase, treat project overview as required before implementation.
- For repo-local agents, use a hybrid flow: get runtime/context truth from VibeRecall first, then inspect the local repository directly with shell/search/runtime tools before editing.
- If get_context_pack still lacks code overview for a task that depends on repo structure, use viberecall_get_index_status and then viberecall_index_repo only within an explicitly trusted workflow.
- For local unpublished code, use an explicit Git source, workspace bundle flow, or local backend path; do not assume the hosted MCP server can read the local workspace directly.

Safety rules:
- Do not spam repeated broad searches without changing scope or query.
- Do not assume the hosted MCP server can read the local repository path.
- For local dirty-worktree indexing, use a Git source or workspace bundle flow.
- Do not call viberecall_index_repo unless the workflow is explicitly trusted and code context is actually stale or missing.
- Do not use merge or split entity tools unless the task is explicitly operator-approved.
- Reconnect the MCP server if a session becomes stale.
- Stop and ask the human if the active project, environment, token scope, or trust boundary is unclear.
- Stop and ask the human if the task appears to require privileged maintenance tools that are not already explicitly approved.

When correcting stale knowledge:
- Inspect lineage with viberecall_explain_fact before using viberecall_update_fact.
- Do not use viberecall_update_fact unless fact correction is part of an explicitly trusted workflow.

Preferred daily-driver tools:
- viberecall_get_status
- viberecall_get_context_pack
- viberecall_search_memory
- viberecall_get_fact
- viberecall_get_facts
- viberecall_search_entities
- viberecall_get_neighbors
- viberecall_explain_fact
- viberecall_save_episode
- viberecall_get_index_status
