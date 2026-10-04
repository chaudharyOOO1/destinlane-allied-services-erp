-- Preserve codes beyond 9999 and enforce server-only sequencing.
create or replace function public.generate_employee_code() returns trigger language plpgsql set search_path=public,pg_temp as $$
declare value text;
begin
 if new.employee_code is null or btrim(new.employee_code)='' then
   value := nextval('public.employee_das_code_seq')::text;
   new.employee_code := 'E-DAS-' || lpad(value,greatest(4,length(value)),'0');
 end if;
 return new;
end; $$;
revoke all on sequence public.employee_das_code_seq from public,anon,authenticated;
revoke all on function public.generate_employee_code() from public,anon,authenticated;
create index employee_documents_compliance_lookup on public.employee_documents(employee_id,document_type,verification_status,expiry_date);
