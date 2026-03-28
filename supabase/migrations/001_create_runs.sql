-- supabase/migrations/001_create_runs.sql

create table if not exists runs (
  run_id         uuid primary key default gen_random_uuid(),
  blueprint_id   text not null,
  instruction    text not null,
  context        jsonb default '{}',
  callback_url   text,
  status         text not null default 'pending'
                   check (status in (
                     'pending', 'dispatched', 'dispatch_failed',
                     'running', 'completed', 'failed'
                   )),
  result         jsonb,
  error_code     text,
  error_message  text,
  created_at     timestamptz default now(),
  updated_at     timestamptz default now()
);

create index idx_runs_status on runs(status);

-- Auto-update updated_at
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger runs_updated_at
  before update on runs
  for each row execute function update_updated_at();
