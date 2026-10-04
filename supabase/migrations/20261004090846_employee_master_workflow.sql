alter table public.employees add column father_name text, add column profile jsonb not null default '{}'::jsonb, add column version integer not null default 1, add column updated_at timestamptz not null default now();
create unique index employees_aadhaar_unique on public.employees(aadhaar_no) where aadhaar_no is not null and aadhaar_no <> '';
alter table public.employee_intimations add column father_name text, add column aadhaar_no text, add column branch text;
alter table public.employee_approval_requests add column workflow_snapshot jsonb not null default '[]'::jsonb, add column step_index integer not null default 0;
create unique index employee_pending_request_unique on public.employee_approval_requests(employee_id) where status='PENDING';
create table public.employee_history(id bigint generated always as identity primary key, employee_id uuid not null references public.employees(id), changed_by integer references public.users(id), action text not null, version integer not null, details jsonb not null default '{}'::jsonb, created_at timestamptz not null default now());
create index employee_history_employee_idx on public.employee_history(employee_id,created_at);
create index employee_history_user_idx on public.employee_history(changed_by);
alter table public.employee_history enable row level security;
revoke all on public.employee_history from anon,authenticated;
create policy employee_history_backend_only on public.employee_history for all to anon,authenticated using(false) with check(false);
alter table public.guard_profiles alter column user_id drop not null;
create unique index guard_profiles_employee_unique on public.guard_profiles(employee_id);
create sequence public.employee_das_code_seq start with 70;
select setval('public.employee_das_code_seq', greatest(70,coalesce((select max(substring(employee_code from 'E-DAS-([0-9]+)')::bigint)+1 from public.employees where employee_code ~ '^E-DAS-[0-9]+$'),70)),false);
create or replace function public.generate_employee_code() returns trigger language plpgsql set search_path=public,pg_temp as $$
begin
 if new.employee_code is null or btrim(new.employee_code)='' then
   new.employee_code := 'E-DAS-' || lpad(nextval('public.employee_das_code_seq')::text,4,'0');
 end if;
 return new;
end; $$;
create or replace function public.protect_employee_code() returns trigger language plpgsql set search_path=public,pg_temp as $$
begin
 if new.employee_code is distinct from old.employee_code then raise exception 'Employee ID is permanent'; end if;
 return new;
end; $$;
create trigger employee_code_immutable before update on public.employees for each row execute function public.protect_employee_code();
alter function public.generate_employee_intimation_id() set search_path=public,pg_temp;
revoke all on function public.generate_employee_code() from public,anon,authenticated;
revoke all on function public.generate_employee_intimation_id() from public,anon,authenticated;
revoke all on function public.protect_employee_code() from public,anon,authenticated;
