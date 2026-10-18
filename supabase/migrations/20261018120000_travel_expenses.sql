-- Additive migration: keep claims/decisions and post to existing expenses only on payment.
create table public.travel_expense_claims (
 id serial primary key,
 requester_id integer not null references public.users(id) on delete restrict,
 purpose varchar(500) not null, origin varchar(150) not null, destination varchar(150) not null,
 start_date date not null, end_date date not null, branch varchar(100) not null default '',
 items json not null, total_amount numeric(12,2) not null,
 missing_receipt_reason varchar(1000) not null default '',
 status varchar(20) not null default 'DRAFT', version integer not null default 1 check(version > 0),
 submitted_at timestamptz, reviewed_by integer references public.users(id) on delete restrict,
 reviewed_at timestamptz, review_remarks varchar(1000) not null default '',
 paid_by integer references public.users(id) on delete restrict,
 payment_date date, payment_reference varchar(150), expense_id uuid unique references public.expenses(id) on delete restrict,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 constraint travel_claim_status check(status in ('DRAFT','SUBMITTED','APPROVED','REJECTED','PAID')),
 constraint travel_claim_positive_amount check(total_amount > 0),
 constraint travel_claim_dates check(end_date >= start_date),
 constraint travel_claim_payment check((status='PAID' and expense_id is not null and paid_by is not null and payment_date is not null and payment_reference is not null) or (status<>'PAID' and expense_id is null)),
 constraint travel_claim_no_self_review check(reviewed_by is null or reviewed_by<>requester_id),
 constraint travel_claim_no_self_payment check(paid_by is null or paid_by<>requester_id)
);
create index ix_travel_expense_claims_requester_id on public.travel_expense_claims(requester_id);
create index ix_travel_expense_claims_status on public.travel_expense_claims(status);
create table public.travel_expense_receipts (
 id serial primary key, claim_id integer not null references public.travel_expense_claims(id) on delete restrict,
 filename varchar(255) not null, storage_path varchar(300) not null unique,
 mime_type varchar(100) not null, size_bytes integer not null check(size_bytes > 0 and size_bytes <= 3145728),
 sha256 varchar(64) not null, uploaded_by integer not null references public.users(id) on delete restrict,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(claim_id,sha256)
);
create index ix_travel_expense_receipts_claim_id on public.travel_expense_receipts(claim_id);
create table public.travel_expense_history (
 id serial primary key, claim_id integer not null references public.travel_expense_claims(id) on delete restrict,
 actor_id integer not null references public.users(id) on delete restrict,
 action varchar(30) not null, version integer not null, details json not null,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create index ix_travel_expense_history_claim_id on public.travel_expense_history(claim_id);

-- Browser access is exclusively through the authenticated backend and row scoping.
alter table public.travel_expense_claims enable row level security;
alter table public.travel_expense_receipts enable row level security;
alter table public.travel_expense_history enable row level security;
revoke all on public.travel_expense_claims, public.travel_expense_receipts, public.travel_expense_history from public, anon, authenticated;
revoke all on sequence public.travel_expense_claims_id_seq, public.travel_expense_receipts_id_seq, public.travel_expense_history_id_seq from public, anon, authenticated;

-- Local PostgreSQL has no storage schema; Supabase does. Do not create fake storage tables.
do $$ begin
 if to_regclass('storage.buckets') is not null then
  insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
  values('travel-expense-receipts','travel-expense-receipts',false,3145728,array['application/pdf','image/jpeg','image/png'])
  on conflict(id) do update set public=false,file_size_limit=3145728,allowed_mime_types=array['application/pdf','image/jpeg','image/png'];
 end if;
 if to_regclass('storage.objects') is not null then
  -- Restrictive policies also protect against pre-existing permissive browser policies.
  execute 'create policy travel_receipts_backend_only on storage.objects as restrictive for all to anon, authenticated using (bucket_id <> ''travel-expense-receipts'') with check (bucket_id <> ''travel-expense-receipts'')';
 end if;
end $$;
