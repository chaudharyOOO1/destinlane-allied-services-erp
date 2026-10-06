-- Runtime columns omitted from the original enterprise SQL history.
alter table public.clients
 add column if not exists branch varchar(100),
 add column if not exists credit_terms_days integer not null default 30,
 add column if not exists registration_no varchar(100),
 add column if not exists billing_cycle varchar(30) default 'MONTHLY';
alter table public.sites add column if not exists contractual_rate numeric(12,2) not null default 0;
alter table public.staff_profiles add column if not exists staff_code text unique;
-- The roster ORM and enterprise services use text values, not the legacy enum.
drop index public.roster_employee_day_active;
alter table public.shift_rosters alter column status type text using status::text;
alter table public.shift_rosters add constraint roster_status_valid
 check(status in ('SCHEDULED','COMPLETED','CANCELLED'));
create unique index roster_employee_day_active on public.shift_rosters(guard_id,date)
 where status in ('SCHEDULED','COMPLETED');
