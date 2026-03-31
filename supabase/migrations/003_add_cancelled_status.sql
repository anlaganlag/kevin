-- supabase/migrations/003_add_cancelled_status.sql
-- Add 'cancelled' as a valid terminal status for runs.

alter table runs drop constraint if exists runs_status_check;
alter table runs add constraint runs_status_check
  check (status in (
    'pending', 'dispatched', 'dispatch_failed',
    'running', 'completed', 'failed', 'cancelled'
  ));
