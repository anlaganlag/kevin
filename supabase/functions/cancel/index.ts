// supabase/functions/cancel/index.ts
// Cancel a running or pending run.

import { validateApiKey } from "../_shared/auth.ts";
import { corsOptions, json } from "../_shared/cors.ts";
import { checkRateLimit } from "../_shared/rate_limit.ts";
import { isValidTransition } from "../_shared/transitions.ts";
import { getSupabase } from "../_shared/supabase.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return corsOptions();

  if (req.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  if (!validateApiKey(req)) {
    return json({ error: "Unauthorized" }, 401);
  }

  const rl = checkRateLimit(req);
  if (rl.limited) {
    return json({ error: "Rate limit exceeded" }, 429);
  }

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }

  const { run_id } = body as { run_id?: string };
  if (!run_id) {
    return json({ error: "run_id is required" }, 400);
  }

  const db = getSupabase();

  const { data: run, error: fetchErr } = await db
    .from("runs")
    .select("status")
    .eq("run_id", run_id)
    .single();

  if (fetchErr || !run) {
    return json({ error: "Run not found", run_id }, 404);
  }

  if (!isValidTransition(run.status, "cancelled")) {
    return json({
      error: "Cannot cancel",
      reason: `Run is already in terminal state: ${run.status}`,
      run_id,
    }, 409);
  }

  const { error: updateErr } = await db
    .from("runs")
    .update({ status: "cancelled", error_code: "CANCELLED", error_message: "Cancelled by user" })
    .eq("run_id", run_id);

  if (updateErr) {
    return json({ error: "Failed to cancel run", detail: updateErr.message }, 500);
  }

  return json({ run_id, status: "cancelled" });
});
