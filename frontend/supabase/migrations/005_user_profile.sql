-- Personal profile: facts about the user that adjust cached place scores (income, current home
-- cost, work hub, commute mode, office days, people they want to live near). Kept separate from
-- explorer_options, which holds UI state (weights, dealbreakers, filters). Same row, same RLS.

alter table public.user_preferences
  add column if not exists profile jsonb not null default '{}';

NOTIFY pgrst, 'reload schema';
