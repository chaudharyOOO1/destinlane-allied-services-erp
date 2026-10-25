alter table public.users add column if not exists failed_login_attempts integer not null default 0;
alter table public.users add column if not exists login_locked_until timestamptz;
