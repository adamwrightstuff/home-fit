-- Run this in Supabase SQL Editor (Dashboard → SQL Editor) to create the saved_scores table and RLS.
-- Replace if you already have a table and want to reset (drops first).

-- Table: one row per saved place score per user.
create table if not exists public.saved_scores (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  input text not null,
  coordinates jsonb not null,
  location_info jsonb not null,
  score_payload jsonb not null,
  priorities jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, input)
);

create index if not exists saved_scores_user_id_idx on public.saved_scores(user_id);
create index if not exists saved_scores_updated_at_idx on public.saved_scores(updated_at desc);

alter table public.saved_scores enable row level security;

create policy "Users can select own saved_scores"
  on public.saved_scores for select
  using (auth.uid() = user_id);

create policy "Users can insert own saved_scores"
  on public.saved_scores for insert
  with check (auth.uid() = user_id);

create policy "Users can update own saved_scores"
  on public.saved_scores for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "Users can delete own saved_scores"
  on public.saved_scores for delete
  using (auth.uid() = user_id);

-- Optional: trigger to keep updated_at in sync
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists saved_scores_updated_at on public.saved_scores;
create trigger saved_scores_updated_at
  before update on public.saved_scores
  for each row execute function public.set_updated_at();
