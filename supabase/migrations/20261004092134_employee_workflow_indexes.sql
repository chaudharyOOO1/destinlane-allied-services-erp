-- Existing constraints already cover guard/employee identities; remove redundant indexes.
drop index public.guard_profiles_employee_unique;
drop index public.ux_employees_employee_code;
create index employee_approval_categories_approver_idx on public.employee_approval_categories(approver_user_id);
create index employee_approval_requests_category_idx on public.employee_approval_requests(category_id);
create index employee_approval_requests_decided_idx on public.employee_approval_requests(decided_by);
create index employee_approval_requests_submitted_idx on public.employee_approval_requests(submitted_by);
create index employee_intimations_client_idx on public.employee_intimations(client_id);
create index employee_intimations_creator_idx on public.employee_intimations(created_by);
create index employee_joining_creator_idx on public.employee_joining_drafts(created_by);
create unique index employee_joining_intimation_unique on public.employee_joining_drafts(intimation_id);
-- Explicitly document the backend-only API boundary for joining tables.
revoke all on public.employee_intimations,public.employee_joining_drafts,public.employee_approval_categories,public.employee_approval_requests from anon,authenticated;
create policy employee_intimations_backend_only on public.employee_intimations for all to anon,authenticated using(false) with check(false);
create policy employee_joining_backend_only on public.employee_joining_drafts for all to anon,authenticated using(false) with check(false);
create policy employee_approval_categories_backend_only on public.employee_approval_categories for all to anon,authenticated using(false) with check(false);
create policy employee_approval_requests_backend_only on public.employee_approval_requests for all to anon,authenticated using(false) with check(false);
