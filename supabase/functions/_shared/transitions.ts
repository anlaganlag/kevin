// supabase/functions/_shared/transitions.ts

const TRANSITIONS: Record<string, Set<string>> = {
  // pending -> running: tolerated when Actions reports running before the execute
  // function finishes updating to "dispatched" (race with fast runners).
  pending:          new Set(["dispatched", "dispatch_failed", "running", "cancelled"]),
  // dispatched -> failed: workflow crashed before Kevin CLI could run (fallback callback)
  dispatched:       new Set(["running", "failed", "cancelled"]),
  running:          new Set(["completed", "failed", "cancelled"]),
};

export function isValidTransition(from: string, to: string): boolean {
  return TRANSITIONS[from]?.has(to) ?? false;
}
