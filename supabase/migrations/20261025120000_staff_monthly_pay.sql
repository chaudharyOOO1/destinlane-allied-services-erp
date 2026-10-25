-- Staff remuneration is proposed per branch/month; active staff are never
-- included automatically in deployed-employee attendance payroll.
create table if not exists public.staff_monthly_pay (
    id bigserial primary key,
    staff_id integer not null references public.internal_staff(id),
    payroll_month date not null check (extract(day from payroll_month)=1),
    branch text not null,
    gross_pay numeric(12,2) not null check (gross_pay>0),
    deductions numeric(12,2) not null check (deductions>=0 and deductions<=gross_pay),
    net_pay numeric(12,2) generated always as (gross_pay-deductions) stored,
    work_note text not null check (length(btrim(work_note)) between 10 and 2000),
    status text not null default 'DRAFT' check (status in ('DRAFT','APPROVED','REJECTED','PAID')),
    version integer not null default 1,
    created_by integer not null references public.users(id),
    approved_by integer references public.users(id),
    approved_at timestamptz,
    decision_note text,
    paid_by integer references public.users(id),
    paid_on date,
    payment_reference text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(staff_id,payroll_month)
);
create table if not exists public.staff_monthly_pay_audit (
    id bigserial primary key,
    pay_id bigint not null references public.staff_monthly_pay(id),
    actor_id integer not null references public.users(id),
    action text not null,
    snapshot jsonb not null,
    created_at timestamptz not null default now()
);
alter table public.staff_monthly_pay enable row level security;
alter table public.staff_monthly_pay_audit enable row level security;
revoke all on public.staff_monthly_pay,public.staff_monthly_pay_audit from anon,authenticated;
revoke all on sequence public.staff_monthly_pay_id_seq,public.staff_monthly_pay_audit_id_seq from anon,authenticated;
