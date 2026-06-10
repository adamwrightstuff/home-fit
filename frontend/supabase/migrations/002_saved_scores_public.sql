-- Migration: add is_public flag to saved_scores for shareable links.
-- Run in Supabase SQL Editor (Dashboard → SQL Editor).

alter table public.saved_scores
  add column if not exists is_public boolean not null default false;

create index if not exists saved_scores_is_public_idx on public.saved_scores(is_public) where is_public = true;

-- Allow anonymous (unauthenticated) users to read rows marked as public.
-- The anon role is used by Supabase for unauthenticated requests.
create policy "Anyone can read public saved_scores"
  on public.saved_scores for select
  using (is_public = true);

NOTIFY pgrst, 'reload schema';
