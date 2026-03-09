Investigate a full-stack regression that may involve both apps/web and services/api.

Use multi-agent with these roles:
- explorer
- frontend_reviewer
- backend_reviewer
- browser_debugger

Instructions:
1. Have explorer map the frontend entry point, API client boundary, backend handler, and response path.
2. Have browser_debugger reproduce the visible symptom if it is browser-observable.
3. Have frontend_reviewer assess rendering, state, routing, and cache behavior.
4. Have backend_reviewer assess validation, schema, typing, and error-handling behavior.
5. Compare findings and state the current frontend/backend contract in exact terms.
6. If the root cause is clear, have worker make the smallest safe change.
7. Validate both sides with the relevant commands.
8. Return:
   - observed symptom
   - current contract
   - corrected contract
   - files changed
   - validation results
   - anything not yet proven
