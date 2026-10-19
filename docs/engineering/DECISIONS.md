# Decision register

## ADR-001 — Improve the existing application

Status: accepted by the user, October 2026.

Keep React/Vite + FastAPI + PostgreSQL/Supabase and the existing deployment. ERPNext/Frappe HR provide reference workflows. Running their complete stack would require different hosting and substantial adaptation; trimming modules would not remove core framework services. Oracle capacity is unavailable and hosting migration does not solve our current saving defects.

Consequences: reuse working features, fix confirmed defects first, validate each operational workflow independently. We own implementation, maintenance and correctness. Free hosting limits remain applicable. Direct third-party code reuse requires a licence/provenance review.

## ADR-002 — Documentation accompanies behaviour

Status: accepted by the user, 18 October 2026.

Maintain functional rules, operator guidance, verification evidence and developer handover with each change. Use an indexed documentation set, defect IDs, review checklist and PR template. This avoids conversational history becoming a prerequisite for maintenance.

## ADR-003 — Confirmed writes survive read failures

Status: implemented locally for Staff Master, SAVE-001.

A successful mutation response is authoritative for the issued ID and version. Apply that response immediately and clear temporary passwords. Follow-up reads can enrich the record and refresh lists; failures produce an explicit refresh warning without representing the write as rejected. Do not automatically retry mutations.

An HTTP timeout or lost mutation response remains an uncertain outcome: verify the record before retrying creation. This change does not provide general request idempotency or distributed transactions across Supabase Auth and PostgreSQL.

## ADR-004 — Business actions over the existing accounting engine

Status: approved by the user, 19 October 2026; implemented in Company Money.

Daily recording asks for business reason, category, party, amount and reference. The server generates balanced drafts; the existing posting engine and ledger remain authoritative. Advanced Accounting retains accountant controls and multi-line tax/accrual work. This reduces operator effort without duplicating monetary truth or interpreting every bank deposit as income. Preview does not save, draft does not enter reports, and confirmation is explicit. Classification and genuine opening figures still require accountant review.

## ADR-005 — Source permissions and honest unavailable states

Status: implemented, 19 October 2026.

A dashboard grant opens a page, not every source register. The backend checks effective source permissions before SQL and isolates independent sections. A true zero is distinct from a restricted or failed source. No attendance percentage, financial collection or statutory payment liability is invented when source data is missing. Retire the old Management pseudo-P&L instead of presenting gross invoice values and multiplied payroll joins as profit. The MD posted ledger remains separate.

## ADR-006 — Load the requested workspace

Status: implemented, 19 October 2026.

Use lazy route imports with an explicit loading state and reload/recovery boundary. This reduces the initial production JavaScript entry from roughly 659 kB to 193 kB before compression; individual module code is fetched as needed. Do not remove workflow validation or backend rules to reduce the bundle. Rendering/network recovery must not automatically repeat a mutation.
