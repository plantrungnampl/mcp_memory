Create a CSV for batch review and fan out workers with spawn_agents_on_csv.

Use this when you need one worker per component, route, or API module.

Example instruction:

Create /tmp/review-items.csv with columns item_path,item_type,owner.
Then call spawn_agents_on_csv with:
- csv_path: /tmp/review-items.csv
- id_column: item_path
- instruction: "Review {item_path} of type {item_type} owned by {owner}. Return JSON with keys item_path, risk, summary, and follow_up via report_agent_job_result."
- output_csv_path: /tmp/review-results.csv
- output_schema: object with required string fields item_path, risk, summary, and follow_up
- max_concurrency: 4

Use this for:
- component audits
- route audits
- API module audits
- policy or ownership reviews
