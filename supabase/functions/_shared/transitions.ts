// supabase/functions/_shared/transitions.ts

const TRANSITIONS: Record<string, Set<string>> = {
  pending:          new Set(["dispatched", "dispatch_failed"]),
  dispatched:       new Set(["running"]),
  running:          new Set(["completed", "failed"]),
};

export function isValidTransition(from: string, to: string): boolean {
  return TRANSITIONS[from]?.has(to) ?? false;
}
