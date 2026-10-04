# Roster and deployment

Recruitment remains pending. This module schedules approved workforce employees; internal office staff are a separate master.

DAY, NIGHT and GENERAL shifts are supported. The existing safety rule is retained: one SCHEDULED or COMPLETED assignment per employee per calendar day, across all client sites. A partial unique index enforces it against concurrent writes. Cancelled records remain in the register and do not prevent scheduling a replacement.

Scheduling checks active employee/deployment profiles, joining APPROVED, matching client/branch, active site/client, and verified police/medical/gunman licence files valid on the deployment date. Linked contracts must be active and cover the date and service vertical. New or changed deployments cannot be backdated. Compliance checking applies separately to every day in repeated schedules.

Repeat scheduling covers up to 31 days with chosen weekdays and is atomic: conflicts or expired compliance on any selected date add no assignments. Change and cancellation require the current version and a reason, and preserve history. Attendance locks the assignment; completed/cancelled records cannot be edited. Attendance punching locks its roster row to avoid racing cancellation. Completion is reserved for the attendance workflow rather than arbitrary scheduling payloads.

The page provides available-employee selection, client/site/date/status filters, changes, cancellations, an audit trail and staffing coverage for all three shifts. Coverage uses configured site requirements, reports vacancies/surplus and flags assignments whose employees are no longer deployable. No salary or billing amounts are returned through the operational options.

Operations/Supervisor accounts need explicitly granted roster write permission. Cancellation requires edit, not create. Private history uses server-only database access with RLS and foreign-key indexes.

Tests use an isolated database for same-day clashes, General shifts, returned date availability, version conflicts, attendance locks, weekday repetition, atomic failure, future expiry, client/branch alignment, contract validity, gunman licences, staffing shortfall and permission routing. Production verification is read-only while real employee/client/site setup is pending.
