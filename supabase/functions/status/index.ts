// supabase/functions/status/index.ts

import { validateApiKey } from "../_shared/auth.ts";
import { corsOptions, json } from "../_shared/cors.ts";
import { checkRateLimit } from "../_shared/rate_limit.ts";
import { getSupabase } from "../_shared/supabase.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return corsOptions();

  if (req.method !== "GET") {
    return json({ error: "Method not allowed" }, 405);
  }

  if (!validateApiKey(req)) {
    return json({
      error: "Unauthorized",
      hint: "Add header: Authorization: Bearer <your-api-key>",
    }, 401);
  }

  const rl = checkRateLimit(req);
  if (rl.limited) {
    return json(
      { error: "Rate limit exceeded", hint: "Max 10 requests per minute" },
      429,
    );
  }

  // Extract run_id from URL path: /status/{run_id}
  const url = new URL(req.url);
  const segments = url.pathname.split("/").filter(Boolean);
  // Path: /status/<run_id> → segments = ["status", "<run_id>"]
  const runId = segments[segments.length - 1];

  const db = getSupabase();

  // No run_id → list recent runs
  if (!runId || runId === "status") {
    const rawLimit = Number(url.searchParams.get("limit"));
    const limit = Math.min(Math.max(rawLimit > 0 ? rawLimit : 10, 1), 50);
    const { data: runs, error } = await db
      .from("runs")
      .select("run_id, blueprint_id, status, instruction, error_code, created_at, updated_at")
      .order("created_at", { ascending: false })
      .limit(limit);

    if (error) {
      return json({ error: "Failed to list runs", detail: error.message }, 500);
    }

    return json({ runs, count: runs?.length ?? 0 });
  }

  // Validate UUID format
  const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (!UUID_RE.test(runId)) {
    return json({
      error: "Invalid run_id format",
      hint: "run_id must be a UUID, e.g. 675e04ae-0f40-4b41-b3ef-df238d5e6a6e",
    }, 400);
  }

  const { data: run, error } = await db
    .from("runs")
    .select("run_id, blueprint_id, status, instruction, result, error_code, error_message, created_at, updated_at")
    .eq("run_id", runId)
    .single();

  if (error || !run) {
    return json({ error: "Run not found", run_id: runId }, 404);
  }

  // Add elapsed time hint for long-running tasks
  const elapsed = Math.round((Date.now() - new Date(run.created_at).getTime()) / 1000);
  const response = { ...run, elapsed_seconds: elapsed };

  return json(response);
});
