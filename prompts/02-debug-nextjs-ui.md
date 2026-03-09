Investigate a browser-visible bug in apps/web.

Use multi-agent with these roles:
- browser_debugger
- explorer
- frontend_reviewer

Instructions:
1. Have browser_debugger reproduce the issue and collect evidence.
2. Have explorer map the route, component, state, and API path involved.
3. Have frontend_reviewer identify the likely failure mode and smallest frontend file set to change.
4. If and only if the cause is clear, have worker implement the smallest safe fix.
5. Validate with:
   - pnpm --dir apps/web lint
   - pnpm --dir apps/web build
   - pnpm --dir apps/web test
6. Return:
   - reproduction summary
   - root cause
   - files changed
   - validation results
   - anything still unverified
