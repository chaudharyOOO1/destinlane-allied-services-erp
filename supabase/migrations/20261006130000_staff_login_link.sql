-- Staff identity and ERP account are one explicit, immutable relationship.
alter table public.internal_staff add column user_id integer unique
 references public.users(id) on delete set null;
update public.internal_staff s set user_id=u.id from public.users u
 where upper(u.login_id)=s.staff_code;
