# Contributing and review contract

Read [docs/README.md](docs/README.md) and [handover](docs/engineering/HANDOVER.md) before editing. Existing generated agent notes may contain historical routes and completion claims; use current code, tests and the audit as evidence.

1. Tie each change to an action-plan item or defect ID. State the user-visible problem and acceptance criteria before implementation.
2. Keep changes focused. Preserve user work, existing IDs, role enums and migration history. Avoid unrelated refactoring and dependency updates.
3. Enforce access, validation, duplicate prevention and financial rules server-side. Hidden buttons are not security controls.
4. Treat mutation success separately from refresh failure. Never automatically retry a create, payment or other mutation without an explicit idempotency contract. Test rejected writes, stale versions and relevant post-save read failures.
5. Update functional and user documentation when behaviour changes. Document decisions and migration/recovery implications. Comments should explain non-obvious reasons, not repeat code.
6. Run relevant checks from the handover and report passed, failed, skipped and unrun checks separately. A compile/build or mocked browser test alone is not business acceptance.
7. Use the PR template and [review checklist](docs/engineering/REVIEW_CHECKLIST.md). State scope, evidence, remaining gaps and rollback. Do not mark a workflow production-ready without acceptance evidence.
8. Use fictional test data and local/disposable databases. Never commit credentials, production exports or sensitive screenshots. Do not use production seed scripts or run bootstrap migrations against a populated production database.
9. Study ERPNext/HRMS workflows as references. Before directly copying third-party code, review its licence and record provenance and obligations. Do not present copied code as an independent implementation.

CI provides feedback; it does not itself enforce human approval or branch protection. Repository administrators must configure required checks/reviews separately if desired. No branch-protection changes are part of this update.
