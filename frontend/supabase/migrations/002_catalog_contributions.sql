-- Automatic catalog pillar aggregates (crowdsourced from successful API scores).
-- Apply in Supabase SQL Editor. Service role bypasses RLS for writes from backend.

create table if not exists public.catalog_pillar_aggregates (
  catalog_key text not null,
  pillar_key text not null,
  contribution_count integer not null default 0,
  sum_scores double precision not null default 0,
  last_score double precision,
  last_at timestamptz,
  api_version text,
  primary key (catalog_key, pillar_key)
);

create index if not exists catalog_pillar_aggregates_catalog_key_idx
  on public.catalog_pillar_aggregates (catalog_key);

comment on table public.catalog_pillar_aggregates is
  'Rolling sum/count per pillar per NYC metro catalog row; updated by merge_catalog_contribution RPC.';

alter table public.catalog_pillar_aggregates enable row level security;

-- No anon/authenticated policies: reads/writes via service role (backend) only for now.
-- Add "select for anon" later if the map should query aggregates from the client.

create or replace function public.merge_catalog_contribution(
  p_catalog_key text,
  p_scores jsonb,
  p_api_version text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  k text;
  v text;
  n double precision;
begin
  if p_catalog_key is null or length(trim(p_catalog_key)) = 0 then
    return;
  end if;
  if p_scores is null or jsonb_typeof(p_scores) <> 'object' then
    return;
  end if;
  for k, v in select * from jsonb_each_text(p_scores)
  loop
    begin
      n := v::double precision;
    exception when others then
      continue;
    end;
    if n is null or n <> n then -- NaN check
      continue;
    end if;
    insert into public.catalog_pillar_aggregates (
      catalog_key, pillar_key, contribution_count, sum_scores, last_score, last_at, api_version
    )
    values (p_catalog_key, k, 1, n, n, now(), p_api_version)
    on conflict (catalog_key, pillar_key) do update set
      contribution_count = public.catalog_pillar_aggregates.contribution_count + 1,
      sum_scores = public.catalog_pillar_aggregates.sum_scores + excluded.sum_scores,
      last_score = excluded.last_score,
      last_at = excluded.last_at,
      api_version = coalesce(excluded.api_version, public.catalog_pillar_aggregates.api_version);
  end loop;
end;
$$;

revoke all on function public.merge_catalog_contribution(text, jsonb, text) from public;
grant execute on function public.merge_catalog_contribution(text, jsonb, text) to service_role;

notify pgrst, 'reload schema';
