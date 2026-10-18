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
