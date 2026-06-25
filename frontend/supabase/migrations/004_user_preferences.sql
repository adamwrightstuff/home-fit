-- User preferences: persists Explorer weights, dealbreakers, and filter settings across sessions.
-- One row per user, upserted on change.

create table if not exists public.user_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  explorer_options jsonb not null default '{}',
  updated_at timestamptz not null default now()
);

alter table public.user_preferences enable row level security;

create policy "Users can select own preferences"
  on public.user_preferences for select
  using (auth.uid() = user_id);

create policy "Users can insert own preferences"
  on public.user_preferences for insert
  with check (auth.uid() = user_id);

create policy "Users can update own preferences"
  on public.user_preferences for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop trigger if exists user_preferences_updated_at on public.user_preferences;
create trigger user_preferences_updated_at
  before update on public.user_preferences
  for each row execute function public.set_updated_at();

NOTIFY pgrst, 'reload schema';
