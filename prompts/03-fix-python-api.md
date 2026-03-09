Investigate and fix a backend issue in services/api.

Use multi-agent with these roles:
- explorer
- backend_reviewer

Instructions:
1. Have explorer map the request path, service layer, and response boundary.
2. Have backend_reviewer identify the likely failure mode, schema risk, type risk, and smallest backend file set to change.
3. If the cause is clear, have worker implement the smallest safe fix.
4. Validate with:
   - uv run --directory services/api ruff check .
   - uv run --directory services/api mypy .
   - uv run --directory services/api pytest -q
5. Return:
   - what was wrong
   - why the fix is correct
   - files changed
   - validation results
   - remaining risk
