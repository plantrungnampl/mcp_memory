# Common Failure Modes and How This Template Prevents Them

## Failure 1: multiple agents edit the same feature

### What goes wrong

- overlapping diffs
- incompatible assumptions
- duplicated fixes
- bad final merge quality

### Prevention in this template

Only `worker` is allowed to edit code.

## Failure 2: frontend and backend fix different contracts

### What goes wrong

- UI expects one response shape
- API returns another
- tests pass in isolation but fail in integration

### Prevention in this template

The root `AGENTS.md` requires contract mapping before cross-stack edits.

## Failure 3: browser bugs are "fixed" without reproduction

### What goes wrong

- engineer changes likely code path
- real issue is elsewhere
- bug appears fixed locally but not in the user path

### Prevention in this template

Use `browser_debugger` to reproduce first for UI issues.

## Failure 4: Python fixes swallow exceptions

### What goes wrong

- hidden failures
- misleading success responses
- broken retry and alerting behavior

### Prevention in this template

The backend instructions forbid broad exception swallowing and require explicit error handling.

## Failure 5: Next.js client/server boundary confusion

### What goes wrong

- unnecessary `'use client'`
- hydration issues
- broken server component assumptions

### Prevention in this template

The frontend instructions default to server components and require justification for client components.

## Failure 6: AGENTS.md contains commands that do not exist

### What goes wrong

Codex obediently runs broken commands and wastes time.

### Prevention in this template

Rollout instructions require command verification before real tasks.
