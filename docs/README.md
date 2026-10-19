# Documentation index

## Start here

- [Company Money simplification and release](engineering/EVERYDAY_MONEY_RELEASE.md): everyday recording, backend mappings and verification.

- [Verified production release record](engineering/RELEASE_20261018.md).

- [Action plan and acceptance gates](ACTION_PLAN.md): approved scope, what/how/why, delivery order and current state.
- [Audit and defect register](engineering/AUDIT.md): evidence, limitations and next investigations.
- [Functional specification: saving and staff](functional/SAVING_AND_STAFF.md): business rules, API contracts and error behaviour.
- [User guide: staff and saving](user-guides/STAFF_AND_SAVING.md): operator steps and recovery.
- [Developer handover](engineering/HANDOVER.md): architecture, setup, tests, migration and release procedures.
- [Review checklist](engineering/REVIEW_CHECKLIST.md) and [contribution rules](../CONTRIBUTING.md).
- [Decision register](engineering/DECISIONS.md): why the architecture and scope were chosen.

- [Travel Expenses functional specification](functional/TRAVEL_EXPENSES.md), [user guide](user-guides/TRAVEL_EXPENSES.md) and [release handover](engineering/TRAVEL_EXPENSES_RELEASE.md).

- [MD accounting specification](functional/MD_ACCOUNTING.md), [bookkeeping user guide](user-guides/MD_ACCOUNTING.md) and [release/developer handover](engineering/MD_ACCOUNTING_RELEASE.md).

## Existing module specifications

[Company](COMPANY_SETUP.md), [access](ACCESS_CONTROLS.md), [hierarchy](LOGIN_HIERARCHY.md), [clients](CLIENT_MASTER.md), [sites/contracts](SITE_CONTRACT_RATE_MASTER.md), [employees](EMPLOYEE_MASTER.md), [staff](STAFF_MASTER.md), [rosters/deployment](ROSTER_DEPLOYMENT.md), [attendance](ATTENDANCE_MASTER.md).

These describe implemented/intended behaviour. They are not proof of live acceptance. The audit records the current evidence. Older references to Owner mean the visible Management role; stable backend enums remain unchanged.

## Documentation maintenance

Every behaviour change must update its functional specification, affected user steps, relevant tests and handover/status entry in the same change. Record source paths, verification commands, results and limitations. Keep secrets, real identity documents and production data out of examples.

New module guides should cover: purpose, authorised users, prerequisites, numbered task steps, expected result, validation/error recovery and known limits. New functional specifications should cover: rules, state transitions, API/data ownership, permission boundaries, failure/retry behaviour and acceptance checks. Link each new document here.
