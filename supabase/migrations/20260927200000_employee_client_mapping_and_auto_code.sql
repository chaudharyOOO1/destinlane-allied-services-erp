alter table public.employees
  add column if not exists client_id integer references public.clients(id) on delete set null;

create index if not exists idx_employees_client_id on public.employees(client_id);

create unique index if not exists ux_employees_employee_code on public.employees(employee_code);

comment on column public.employees.client_id is 'Primary client deployment/mapping for the employee.';
