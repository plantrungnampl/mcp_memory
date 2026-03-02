# Repository Guidelines

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
