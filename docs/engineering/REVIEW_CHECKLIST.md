# Human review checklist

Use this with the PR template. Mark not-applicable items with a reason; do not invent verification evidence.

- [ ] Problem/defect and acceptance criteria are explicit; diff is focused and source paths are easy to follow.
- [ ] Functional specification and affected user steps match the final behaviour; documentation index and handover/status are current.
- [ ] Authentication, backend permissions, target-user protections and tenant/record scope are enforced independently of UI visibility.
- [ ] Required fields, duplicate rules, immutable IDs, financial precision and state transitions are preserved where affected.
- [ ] Confirmed mutation success is distinct from read failure; rejected writes retain input; timeouts are not silently retried.
- [ ] New ID/version is retained; stale edits are rejected; secrets are cleared where appropriate and never logged.
- [ ] Regression checks reproduce the original failure; mocked checks are distinguished from real database and production acceptance.
- [ ] Relevant tests/build/lint ran, counts and warnings are reported, skipped/unrun checks and service stubs are named.
- [ ] Migration scope, order, existing-data compatibility and recovery are documented; no bootstrap against production.
- [ ] No real personal records, secrets, generated exports or unintended dependency/lockfile changes are included.
- [ ] Third-party code, if reused, has recorded provenance and licence review.
- [ ] Release target, post-deployment checks, rollback and remaining risks are stated; local work is not labelled deployed.

Branch protection and mandatory human reviews are repository settings, not enforced by this document or PR checkboxes.
