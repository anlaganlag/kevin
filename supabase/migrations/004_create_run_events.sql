-- supabase/migrations/004_create_run_events.sql
-- Fine-grained event log for run execution. Each status change,
-- block completion, or error is recorded as an immutable event.

create table if not exists run_events (
  event_id     bigint generated always as identity primary key,
  run_id       uuid not null references runs(run_id) on delete cascade,
  event_type   text not null,  -- status_change, block_started, block_completed, block_failed, error
  payload      jsonb default '{}',
  created_at   timestamptz default now()
);

create index idx_run_events_run_id on run_events(run_id);
create index idx_run_events_created on run_events(created_at);

comment on table run_events is 'Immutable event log for run execution — append-only, never update/delete.';
