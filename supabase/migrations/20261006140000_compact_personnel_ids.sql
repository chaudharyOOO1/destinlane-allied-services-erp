-- Retain existing immutable IDs and login identities; use compact IDs for new records.
alter table public.internal_staff drop constraint internal_staff_staff_code_check;
alter table public.internal_staff add constraint internal_staff_staff_code_check
 check(staff_code ~ '^(DASS|S-DAS-)[0-9]{4,}$');
create or replace function public.generate_employee_code() returns trigger language plpgsql set search_path=public,pg_temp as $$
declare value text;
begin
 if new.employee_code is null or btrim(new.employee_code)='' then
   value := nextval('public.employee_das_code_seq')::text;
   new.employee_code := 'DASE' || lpad(value,greatest(4,length(value)),'0');
 end if;
 return new;
end; $$;
revoke all on function public.generate_employee_code() from public,anon,authenticated;
