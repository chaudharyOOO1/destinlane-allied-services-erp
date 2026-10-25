-- Employee wages are independent of rates billed to clients. Append new rates
-- instead of editing history. Finalised slips remain immutable snapshots.
create table if not exists public.employee_wage_rates (
    id bigserial primary key,
    employee_id uuid not null references public.employees(id),
    effective_from date not null,
    daily_rate numeric(12,2) not null check (daily_rate > 0),
    reason text not null check (length(btrim(reason)) between 5 and 1000),
    created_by integer not null references public.users(id),
    created_at timestamptz not null default now(),
    unique(employee_id,effective_from)
);
create index if not exists employee_wages_effective_idx
    on public.employee_wage_rates(employee_id,effective_from desc);
alter table public.employee_wage_rates enable row level security;
revoke all on public.employee_wage_rates from anon,authenticated;
revoke all on sequence public.employee_wage_rates_id_seq from anon,authenticated;
