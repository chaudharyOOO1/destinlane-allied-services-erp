-- Employee backend completion: approved IFSC master + employee photograph reference.
-- IFSC validation is exact-match only and accepts rows explicitly approved by an administrator.
-- Populate this table from the organization's approved/uploaded IFSC master before enabling bank-account onboarding.

create table if not exists public.ifsc_master (
  ifsc_code varchar(11) primary key,
  bank_name text not null,
  branch_name text,
  address text,
  city text,
  district text,
  state text,
  source text not null default 'APPROVED_INTERNAL',
  approved boolean not null default false,
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_ifsc_master_bank on public.ifsc_master(bank_name);
create index if not exists idx_ifsc_master_approved on public.ifsc_master(approved, ifsc_code);

alter table public.ifsc_master enable row level security;
drop policy if exists deny_ifsc_master_api on public.ifsc_master;
create policy deny_ifsc_master_api on public.ifsc_master
  for all to anon, authenticated
  using (false)
  with check (false);

alter table public.employees add column if not exists photo_url text;
