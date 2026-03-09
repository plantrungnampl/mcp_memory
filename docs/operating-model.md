# Operating Model

## The intended workflow

The right mental model is **supervisor plus specialists**, not **many coders editing at once**.

### Main agent responsibilities

The main agent should:

- keep the user goal and constraints stable
- decide which specialist roles to invoke
- compare specialist outputs
- decide whether there is enough evidence to edit code
- produce the final answer or implementation summary

### Specialist responsibilities

#### explorer

Use when you need to answer:

- where is the code path?
- which files own this behavior?
- what state transition or data flow is involved?
- what contract exists between UI and API?

#### frontend_reviewer

Use when you need to answer:

- is the Next.js behavior consistent with App Router rules?
- is state ownership clear?
- is the bug caused by caching, hydration, rendering boundaries, or routing?
- are tests missing around the changed UI path?

#### backend_reviewer

Use when you need to answer:

- is request validation correct?
- are response schemas stable?
- are errors explicit and typed?
- is the fix safe with respect to tests and typing?

#### browser_debugger

Use only when the bug is observable in a browser flow. It should:

- reproduce the exact sequence
- gather screenshots, console output, network evidence, and route transitions
- report observed behavior precisely
- never patch code

#### worker

Use only after the issue is understood. It should:

- make the smallest reasonable change
- keep unrelated files untouched
- validate only the changed behavior and essential adjacent risk
- stop if the task turns into a redesign

## What this package deliberately avoids

### 1. Parallel implementation

Multiple write-capable agents are usually a mistake for normal product work.

### 2. Giant all-in-one prompts

If the prompt asks investigation, reproduction, redesign, implementation, and exhaustive documentation all at once, agent behavior gets noisy.

### 3. Hidden repo assumptions

Every path and validation command in this package is explicit.

### 4. Tooling ambiguity

This package picks `pnpm` and `uv` on purpose. If your team uses something else, replace it everywhere.

## Practical concurrency guidance

Use these defaults unless you have a strong reason not to:

- `max_threads = 4` for everyday work
- `max_depth = 1`
- spawn 2 to 4 specialists, not 8 to 10

More threads is not automatically better. It increases noise and review overhead.
