-- Backend-only attendance workflow; existing records and photographs are retained.
alter table public.attendance add column version integer not null default 1;
alter table public.attendance add column source text not null default 'LEGACY';
alter table public.attendance add column duty_hours numeric not null default 8;
alter table public.attendance add column policy_snapshot jsonb not null default '{}';
create unique index attendance_one_roster on public.attendance(roster_id) where roster_id is not null;
alter table public.attendance add constraint attendance_hours_valid check(coalesce(shift_hours,0)>=0 and coalesce(overtime_hours,0)>=0 and coalesce(shift_hours,0)+coalesce(overtime_hours,0)<=24);
alter table public.attendance add constraint attendance_time_order check(check_out_time is null or (check_in_time is not null and check_out_time>=check_in_time));
create table public.attendance_shift_rules(site_id integer references public.sites(id) on delete restrict,shift_type text check(shift_type in ('DAY','NIGHT','GENERAL')),start_time time not null,duty_hours numeric not null check(duty_hours>0 and duty_hours<=16),grace_minutes integer not null default 15 check(grace_minutes between 0 and 120),version integer not null default 1,updated_by integer references public.users(id),updated_at timestamptz not null default now(),primary key(site_id,shift_type));
create index attendance_rules_updated_by on public.attendance_shift_rules(updated_by);
create table public.employee_attendance_access(employee_id uuid primary key references public.employees(id) on delete restrict,pin_hash text not null,session_version integer not null default 1,failed_attempts integer not null default 0,locked_until timestamptz,updated_by integer references public.users(id),updated_at timestamptz not null default now());
create index employee_attendance_access_updated_by on public.employee_attendance_access(updated_by);
create table public.employee_device_bindings(employee_id uuid primary key references public.employees(id) on delete restrict,device_hash text not null,bound_at timestamptz not null default now());
create table public.attendance_selfies(id uuid primary key default gen_random_uuid(),employee_id uuid not null references public.employees(id) on delete restrict,kind text not null check(kind in ('check-in','check-out')),storage_path text not null unique,mime_type text not null,sha256 text not null,created_at timestamptz not null default now(),used_at timestamptz);
create index attendance_selfies_employee_id on public.attendance_selfies(employee_id);
create table public.attendance_history(id bigint generated always as identity primary key,attendance_id uuid references public.attendance(id) on delete restrict,employee_id uuid references public.employees(id) on delete restrict,changed_by integer references public.users(id),action text not null,details jsonb not null,created_at timestamptz not null default now());
create index attendance_history_attendance on public.attendance_history(attendance_id);
create index attendance_history_employee on public.attendance_history(employee_id);
create index attendance_history_changed_by on public.attendance_history(changed_by);
create table public.attendance_corrections(id uuid primary key default gen_random_uuid(),roster_id integer not null references public.shift_rosters(id) on delete restrict,base_version integer not null,proposed jsonb not null,reason text not null,assigned_to integer not null references public.users(id),submitted_by integer not null references public.users(id),status text not null default 'PENDING' check(status in ('PENDING','APPROVED','REJECTED')),remarks text,decided_by integer references public.users(id),created_at timestamptz not null default now(),decided_at timestamptz);
create unique index attendance_one_pending_correction on public.attendance_corrections(roster_id) where status='PENDING';
create index attendance_corrections_assigned on public.attendance_corrections(assigned_to);
create index attendance_corrections_submitter on public.attendance_corrections(submitted_by);
create index attendance_corrections_decider on public.attendance_corrections(decided_by);
alter table public.attendance_shift_rules enable row level security;
alter table public.employee_attendance_access enable row level security;
alter table public.employee_device_bindings enable row level security;
alter table public.attendance_selfies enable row level security;
alter table public.attendance_history enable row level security;
alter table public.attendance_corrections enable row level security;
revoke all on public.attendance_shift_rules,public.employee_attendance_access,public.employee_device_bindings,public.attendance_selfies,public.attendance_history,public.attendance_corrections from anon,authenticated;
create policy attendance_rules_backend_only on public.attendance_shift_rules to anon,authenticated using(false) with check(false);
create policy attendance_access_backend_only on public.employee_attendance_access to anon,authenticated using(false) with check(false);
create policy attendance_devices_backend_only on public.employee_device_bindings to anon,authenticated using(false) with check(false);
create policy attendance_selfies_backend_only on public.attendance_selfies to anon,authenticated using(false) with check(false);
create policy attendance_history_backend_only on public.attendance_history to anon,authenticated using(false) with check(false);
create policy attendance_corrections_backend_only on public.attendance_corrections to anon,authenticated using(false) with check(false);
do $$ begin
if to_regclass('storage.buckets') is not null and to_regclass('storage.objects') is not null then
update storage.buckets set public=false,file_size_limit=3145728,allowed_mime_types=array['image/jpeg','image/png','image/webp'] where id='employee-selfies';
drop policy if exists "Allow employee selfie uploads" on storage.objects;
create policy employee_selfies_backend_only on storage.objects as restrictive for all to anon,authenticated using(bucket_id<>'employee-selfies') with check(bucket_id<>'employee-selfies');

end if;
end; $$;
