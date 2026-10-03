-- Company legal files are private. Backend role checks decide staff access.
insert into storage.buckets (id,name,public,file_size_limit,allowed_mime_types)
values ('company-legal-documents','company-legal-documents',false,3145728,array['application/pdf','image/jpeg','image/png'])
on conflict (id) do nothing;
create policy company_legal_files_backend_only on storage.objects as restrictive
for all to anon, authenticated
using (bucket_id <> 'company-legal-documents')
with check (bucket_id <> 'company-legal-documents');
create policy company_settings_backend_only on public.company_settings
for all to anon, authenticated using (false) with check (false);
create policy company_history_backend_only on public.company_settings_history
for all to anon, authenticated using (false) with check (false);
create policy company_documents_backend_only on public.company_documents
for all to anon, authenticated using (false) with check (false);
