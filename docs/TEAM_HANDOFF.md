> Historical v0.1 notes retained for context. For the current Git workflow and verified status, use README.md, AGENT_DESIGN.md and BUILD_STATUS.md.

# Two-person team handoff

This split is a suggested ownership plan; adjust to actual contributors before making public contribution claims.

## Owner A — backend & correctness

- FalkorDB schema and Cypher plan verification with real Docker instance.
- FastAPI routes, graph repository, agent policy and subprocess runner.
- Unit/integration tests, auth/timeout checks and quality review.
- Actual evaluation numbers gathered after testing.

## Owner B — developer experience & demo

- Dashboard graph view, evidence panel, interactions and responsive QA.
- README/architecture docs, demo story, recording and submission form.
- Review changes and independently test edge cases against the backend.

## Integration milestones

1. Pull project and run Docker Compose on one laptop.
2. Verify graph health via `/api/v1/health/ready`.
3. Run `python scripts/smoke_test.py`; capture output.
4. Visually verify all 3 investigation types.
5. Review security limitations; don't overclaim functionality.
6. Review AI disclosure and assignment of contributions.
7. Push to a public GitHub repo with appropriate team permissions.
8. Film an authentic screen demo and submit under Track 01.

## Review questions judges may ask

- Why FalkorDB and not an SQL join? What changes without the graph?
- Where exactly is the business invariant stored, and who decides it?
- What code does the runner execute? How does it avoid using an LLM's opinion as ground truth?
- What happens if baseline already fails?
- What would it take to run arbitrary customer PRs safely?
- What currently cannot be claimed about the system's real-world detection rate?

## Hackathon submission rules

Verify official details at https://www.wemakedevs.org/hackathons/falkordb/rules. Submission requires public repo, README with graph model, Cypher queries, demo video and deployment or complete local instructions. Deadline 18 Oct 2026, 11:59 PM IST. AI coding tools must be disclosed and participants must understand the implementation.
