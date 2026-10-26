# Collaboration and delivery process

1. Read the task and relevant context; inspect branch, working tree and owned paths. State the requirement IDs, intended change, inputs and evidence required. Preserve unrelated files and data.
2. Agree shared interfaces before parallel implementation: event topic/schema, database migration, API response, env variables and ports. Owners edit disjoint paths; request changes through the controller when crossing ownership.
3. Implement the approved scope. Keep source/configuration status distinct from measured runtime status. Do not start provider polling, acquire datasets, train models, publish issues, or host the application merely to improve the score.
4. Run appropriate checks. Distinguish unit/ASGI component tests, real PostgreSQL/Kafka integration, browser checks, controlled fault recovery and external provider evaluation. Preserve command, timestamp, revision/diff, counts and failures.
5. Handoff using the template below. Controller integrates and runs whole-journey acceptance. An independent reviewer examines the resulting diff and evidence; findings and responses are recorded without calling agent review a human peer review.
6. Update the tracker and validation ledger only after evidence exists. Hosting, human reviews, lawful acquisition/coverage and unmeasured model quality remain explicit external or data-dependent gates.

Handoff template:

```text
Task / requirement IDs:
Owner and owned paths:
Inputs / agreed interfaces:
Files changed and resulting behavior:
Validation commands / exit status / evidence references:
Known limitations / unresolved findings:
Next owner and acceptance needed:
```

An approval to implement is not permission to publish or send external messages. Create local commits only when authorized by the user; a commit does not authorize a push. The current handoff authorizes a local commit and explicitly prohibits pushing. The tracked Markdown tracker becomes public when an authorized maintainer publishes the branch; local files alone do not prove public issue creation. To use issues, select the supplied feature template, link requirement IDs and evidence, then add the actual URL to the tracker.
