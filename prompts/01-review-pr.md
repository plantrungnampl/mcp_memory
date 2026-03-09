Review the current branch against the main branch.

Use multi-agent with these roles:
- explorer
- frontend_reviewer
- backend_reviewer

Instructions:
1. Have explorer map the changed code paths and group changes by ownership.
2. Have frontend_reviewer review Next.js/UI/rendering/state/caching risks.
3. Have backend_reviewer review Python validation/typing/error-handling/contract risks.
4. Wait for all reviewers.
5. Return one consolidated review with:
   - correctness risks
   - regression risks
   - missing tests
   - API contract risks
   - the top 3 issues to fix first

Do not edit code.
