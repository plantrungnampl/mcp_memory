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
