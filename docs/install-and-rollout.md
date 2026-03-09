# Install and Roll Out the Template

## 1. Install Codex CLI

Use npm globally:

```bash
npm i -g @openai/codex@latest
codex
```

Authenticate on first run.

## 2. Put files in the repository root

Copy the following into the root of your repository:

- `.codex/config.toml`
- `AGENTS.md`
- `agents/`
- `apps/web/AGENTS.md`
- `services/api/AGENTS.md`

## 3. Confirm your repository matches the assumptions

This package assumes:

- frontend path: `apps/web`
- backend path: `services/api`
- frontend package manager: `pnpm`
- backend runner: `uv`

If any of these are false, edit the files before doing real work.

## 4. Confirm command availability

From the repository root, these commands should work:

```bash
pnpm --dir apps/web lint
pnpm --dir apps/web build
uv run --directory services/api ruff check .
uv run --directory services/api pytest -q
```

If they fail because your scripts or tooling differ, fix the files now.

## 5. Start Codex from the repo root

```bash
cd /path/to/repo
codex
```

Do not start from a random subdirectory on first rollout. Start at the root so instruction loading is predictable.

## 6. Verify instruction discovery

Ask Codex:

```text
List the instruction files you loaded and summarize the rules.
```

Expected result:

- root `AGENTS.md`
- `apps/web/AGENTS.md` when the task touches the frontend
- `services/api/AGENTS.md` when the task touches the backend

## 7. Verify multi-agent is enabled

The configuration file in this package enables multi-agent directly. If you also use the interactive switch, restart Codex after changing experimental settings.

## 8. Run a safe first task

Use one of these before any large implementation:

- PR review
- frontend bug investigation
- backend bug investigation
- frontend/backend contract review

## 9. Only then allow code edits

Do not start by asking multiple agents to code.

Start with this sequence:

1. explorer maps the problem
2. reviewers identify risk and likely root cause
3. browser debugger reproduces if it is a UI problem
4. worker makes the smallest safe change
5. main agent validates and summarizes

## 10. Keep the template alive

After 1 to 2 weeks of real use:

- remove commands people never use
- add repo-specific commands that always matter
- add rules for recurring failure modes
- tighten directory-specific `AGENTS.md` files

A stale `AGENTS.md` is worse than none. Keep it current.
