# Site Master, Contracts and Rates

## Setup sequence
1. Create an active client and assign its approved internal operations/management staff.
2. Record its contract reference, validity, billing/credit terms, services and signatory. Draft agreements can be prepared before activation.
3. Create a site with its address, branch, contact and internal coordinators. Codes SITE-DAS-0001 onward are allocated automatically and immutable; the client cannot be changed. GPS coordinates are optional but must be supplied together. The default boundary is 100 metres. Staffing requirements include day, night and general shifts.
4. Link the active contract in Site Master, then enter dated rate cards under Contracts & Rates.

## Pricing
Rate cards identify service/category, basis, validity and daily/hourly/monthly amounts. Monthly amounts derive daily equivalents from billable days and hourly equivalents from duty hours using decimal half-up rounding. Healthcare is displayed as HEALTHCARE and maps to the existing database NURSING vertical. Wage indexation is recorded for agreement/rate planning; automatic indexation scheduling is a later payroll/billing task. These are commercial billing rates, not employee wages.

Active rate periods cannot overlap for the same site/service/category. A started rate cannot be repriced or cancelled: end its validity prospectively and add a successor. Historical periods remain available for attendance billing. Contract dates/services cannot exclude active rate cards. Current rates must end before a site can change contract.

## Access and history
Site roles use sites permissions; operations and supervisors require an explicit create/edit grant to write. Contracts and commercial rates use contracts permissions and internal office roles; administrative roles create/edit. Employees and client portal accounts cannot access these internal masters. Operational site responses omit commercial amounts.

Site, contract and rate changes retain snapshots, actor and timestamp. Version checks reject stale saves. Records are inactivated/closed rather than deleted. New internal counter/history tables have RLS and revoked public Data API privileges.

## Verification
Isolated backend tests cover persistence, codes, scope/branch/coordinator checks, GPS and date validation, decimal calculations, overlap prevention, revision history and access restrictions. Frontend build and lint are checked. Production verification confirms deployment SHA, migration history, master API access, validation and anonymous rejection without adding sample business records.

Roster, attendance, payroll and invoice end-to-end UAT remain later action-list stages. Attendance billing now selects rate validity for each attendance date; this does not complete the billing stage.

Commercial validity uses the Indian business date. The updated attendance-rate SQL was verified with PostgreSQL EXPLAIN. Existing database advisories outside these masters (employee generator search paths, legacy foreign key indexes and Supabase leaked-password protection) remain tracked for the employee/security stages; no new master-specific security or missing-index advisory was reported.
