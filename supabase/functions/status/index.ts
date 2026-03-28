// supabase/functions/status/index.ts

import { validateApiKey } from "../_shared/auth.ts";
import { getSupabase } from "../_shared/supabase.ts";

Deno.serve(async (req) => {
  if (req.method !== "GET") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), { status: 405 });
  }

  if (!validateApiKey(req)) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), { status: 401 });
  }

  // Extract run_id from URL path: /status/{run_id}
  const url = new URL(req.url);
  const segments = url.pathname.split("/").filter(Boolean);
  // Path: /status/<run_id> → segments = ["status", "<run_id>"]
  const runId = segments[segments.length - 1];

  if (!runId || runId === "status") {
    return new Response(JSON.stringify({ error: "run_id is required" }), { status: 400 });
  }

  const db = getSupabase();
  const { data: run, error } = await db
    .from("runs")
    .select("run_id, blueprint_id, status, instruction, result, error_code, error_message, created_at, updated_at")
    .eq("run_id", runId)
    .single();

  if (error || !run) {
    return new Response(JSON.stringify({ error: "Run not found" }), { status: 404 });
  }

  return new Response(JSON.stringify(run), { status: 200 });
});
