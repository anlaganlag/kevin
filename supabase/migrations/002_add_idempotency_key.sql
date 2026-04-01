-- supabase/migrations/002_add_idempotency_key.sql
-- Prevents duplicate runs when clients retry on network failure.

alter table runs add column if not exists idempotency_key text;

-- Unique constraint: only one non-terminal run per key
create unique index if not exists idx_runs_idempotency_active
  on runs (idempotency_key)
  where idempotency_key is not null
    and status not in ('completed', 'failed', 'dispatch_failed');
