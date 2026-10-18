-- MD-only double-entry books. No financial balances or business transactions are seeded.
create table public.md_accounting_setup (
 id integer primary key check(id=1), books_start_date date not null,
 financial_year_start_month integer not null default 4 check(financial_year_start_month between 1 and 12),
 closed_through date, opening_confirmed boolean not null default false,
 opening_reason varchar(1000) not null default '', version integer not null default 1,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
insert into public.md_accounting_setup(id,books_start_date)
values(1,make_date(extract(year from timezone('Asia/Kolkata',now()))::integer-case when extract(month from timezone('Asia/Kolkata',now()))<4 then 1 else 0 end,4,1));
create table public.md_ledger_accounts (
 id serial primary key, code varchar(20) not null unique, name varchar(150) not null,
 section varchar(30) not null check(section in ('NON_CURRENT_ASSET','CURRENT_ASSET','EQUITY','NON_CURRENT_LIABILITY','CURRENT_LIABILITY','REVENUE','EXPENSE')),
 group_name varchar(120) not null, is_bank boolean not null default false,
 bank_details json not null default '{}',is_active boolean not null default true,version integer not null default 1,
 created_at timestamptz not null default now(),updated_at timestamptz not null default now(),
 check(not is_bank or section='CURRENT_ASSET')
);
insert into public.md_ledger_accounts(code,name,section,group_name,is_bank) values
 ('1000','Cash in hand','CURRENT_ASSET','Cash and cash equivalents',false),
 ('1010','Company Current Account','CURRENT_ASSET','Cash and cash equivalents',true),
 ('1100','Trade receivables','CURRENT_ASSET','Trade receivables',false),
 ('1201','Input CGST control','CURRENT_ASSET','Other current assets',false),
 ('1202','Input SGST control','CURRENT_ASSET','Other current assets',false),
 ('1203','Input IGST control','CURRENT_ASSET','Other current assets',false),
 ('1300','TDS receivable','CURRENT_ASSET','Other current assets',false),
 ('1500','Property plant and equipment','NON_CURRENT_ASSET','Property plant and equipment',false),
 ('1590','Accumulated depreciation','NON_CURRENT_ASSET','Property plant and equipment',false),
 ('2000','Trade payables','CURRENT_LIABILITY','Trade payables',false),
 ('2101','Output CGST payable','CURRENT_LIABILITY','Statutory dues',false),
 ('2102','Output SGST payable','CURRENT_LIABILITY','Statutory dues',false),
 ('2103','Output IGST payable','CURRENT_LIABILITY','Statutory dues',false),
 ('2200','TDS payable','CURRENT_LIABILITY','Statutory dues',false),
 ('2300','Payroll payable','CURRENT_LIABILITY','Employee dues',false),
 ('2400','PF ESIC and other statutory payable','CURRENT_LIABILITY','Statutory dues',false),
 ('2500','Customer advances','CURRENT_LIABILITY','Other current liabilities',false),
 ('2600','Short-term borrowings','CURRENT_LIABILITY','Borrowings',false),
 ('2700','Long-term borrowings','NON_CURRENT_LIABILITY','Borrowings',false),
 ('3000','Share capital','EQUITY','Share capital',false),
 ('3100','Retained earnings','EQUITY','Reserves and surplus',false),
 ('4000','Service revenue excluding GST','REVENUE','Revenue from operations',false),
 ('5000','Employee remuneration expense','EXPENSE','Employee benefit expense',false),
 ('5100','Travel expense','EXPENSE','Other expenses',false),
 ('5200','Employer statutory contribution expense','EXPENSE','Employee benefit expense',false),
 ('5300','Other operating expenses','EXPENSE','Other expenses',false),
 ('5400','Depreciation expense','EXPENSE','Depreciation and amortisation',false);
create table public.md_journal_entries (
 id serial primary key,entry_date date not null,kind varchar(20) not null check(kind in ('OPENING','PAYMENT','RECEIPT','CONTRA','JOURNAL','REVERSAL')),
 narration varchar(1000) not null,party varchar(200) not null default '',reference varchar(150) not null default '',
 status varchar(20) not null default 'DRAFT' constraint md_journal_status check(status in ('DRAFT','POSTED')),
 version integer not null default 1,created_by integer not null references public.users(id) on delete restrict,
 posted_by integer references public.users(id) on delete restrict,posted_at timestamptz,
 reversal_of integer unique references public.md_journal_entries(id) on delete restrict,
 created_at timestamptz not null default now(),updated_at timestamptz not null default now()
);
create index ix_md_journal_entries_entry_date on public.md_journal_entries(entry_date);
create table public.md_journal_lines (
 id serial primary key, entry_id integer not null references public.md_journal_entries(id) on delete restrict,
 account_id integer not null references public.md_ledger_accounts(id) on delete restrict,
 debit numeric(14,2) not null default 0,credit numeric(14,2) not null default 0,description varchar(500) not null default '',
 created_at timestamptz not null default now(),updated_at timestamptz not null default now(),
 constraint md_line_one_side check((debit>0 and credit=0) or (credit>0 and debit=0))
);
create index ix_md_journal_lines_entry_id on public.md_journal_lines(entry_id);
create index ix_md_journal_lines_account_id on public.md_journal_lines(account_id);
create table public.md_bank_statement_lines (
 id serial primary key,account_id integer not null references public.md_ledger_accounts(id) on delete restrict,
 statement_id varchar(150) not null,entry_date date not null,reference varchar(150) not null default '',description varchar(500) not null default '',
 debit numeric(14,2) not null default 0,credit numeric(14,2) not null default 0,
 imported_by integer not null references public.users(id) on delete restrict,
 matched_line_id integer unique references public.md_journal_lines(id) on delete restrict,
 matched_by integer references public.users(id) on delete restrict,matched_at timestamptz,
 created_at timestamptz not null default now(),updated_at timestamptz not null default now(),
 unique(account_id,statement_id),constraint md_statement_one_side check((debit>0 and credit=0) or (credit>0 and debit=0))
);
create index ix_md_bank_statement_lines_account_id on public.md_bank_statement_lines(account_id);
create table public.md_accounting_audit (
 id serial primary key,actor_id integer not null references public.users(id) on delete restrict,
 action varchar(40) not null,reference varchar(150) not null default '',details json not null default '{}',
 created_at timestamptz not null default now(),updated_at timestamptz not null default now()
);

-- Defend posted records even if a future endpoint forgets application checks.
create function public.md_protect_posted_journal() returns trigger language plpgsql set search_path=public as $$
begin
 if old.status='POSTED' then raise exception 'Posted vouchers are immutable. Record a reversal.'; end if;
 if tg_op='DELETE' then return old; end if; return new;
end $$;
create trigger md_journal_immutable before update or delete on public.md_journal_entries for each row execute function public.md_protect_posted_journal();
create function public.md_protect_posted_lines() returns trigger language plpgsql set search_path=public as $$
declare parent integer; state text;
begin
 if tg_op='DELETE' then parent:=old.entry_id; else parent:=new.entry_id; end if;
 select status into state from public.md_journal_entries where id=parent for update;
 if state='POSTED' then raise exception 'Posted voucher lines are immutable.'; end if;
 if tg_op='UPDATE' and old.entry_id<>new.entry_id then
  select status into state from public.md_journal_entries where id=old.entry_id for update;
  if state='POSTED' then raise exception 'Posted voucher lines are immutable.'; end if;
 end if;
 if tg_op='DELETE' then return old; end if; return new;
end $$;
create trigger md_lines_immutable before insert or update or delete on public.md_journal_lines for each row execute function public.md_protect_posted_lines();
create function public.md_check_posted_balance() returns trigger language plpgsql set search_path=public as $$
declare dr numeric; cr numeric; n integer;
begin
 if new.status='POSTED' then
  select coalesce(sum(debit),0),coalesce(sum(credit),0),count(*) into dr,cr,n from public.md_journal_lines where entry_id=new.id;
  if n<2 or dr<=0 or dr<>cr then raise exception 'Posted voucher must have equal nonzero debits and credits.'; end if;
 end if; return null;
end $$;
create constraint trigger md_balanced_posting after insert or update on public.md_journal_entries deferrable initially deferred for each row execute function public.md_check_posted_balance();

do $$ declare t text; begin
 foreach t in array array['md_accounting_setup','md_ledger_accounts','md_journal_entries','md_journal_lines','md_bank_statement_lines','md_accounting_audit'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('revoke all on public.%I from public,anon,authenticated',t);
  if t<>'md_accounting_setup' then execute format('revoke all on sequence public.%I from public,anon,authenticated',t||'_id_seq'); end if;
 end loop;
end $$;
