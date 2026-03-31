// supabase/functions/health/index.ts
// Dedicated health check endpoint — no authentication required.

import { AVAILABLE_BLUEPRINTS } from "../_shared/blueprints.ts";
import { getSupabase } from "../_shared/supabase.ts";
import { corsOptions, json } from "../_shared/cors.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return corsOptions();

  if (req.method !== "GET") {
    return json({ error: "Method not allowed" }, 405);
  }

  // Basic service info (always returned even if DB is unreachable)
  const service = "kevin-executor";
  const timestamp = new Date().toISOString();

  // Probe database connectivity and gather run stats
  let db_connected = false;
  let recent_runs: Record<string, number> = {};
  try {
    const db = getSupabase();

    // Count runs by status in the last 24 hours
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    const { data, error } = await db
      .from("runs")
      .select("status")
      .gte("created_at", since);

    if (!error) {
      db_connected = true;
      recent_runs = (data ?? []).reduce(
        (acc: Record<string, number>, row: { status: string }) => {
          acc[row.status] = (acc[row.status] ?? 0) + 1;
          return acc;
        },
        {} as Record<string, number>,
      );
    }
  } catch {
    // DB probe failed — service is still up, just degraded
  }

  const status = db_connected ? "ok" : "degraded";

  return json({
    status,
    service,
    timestamp,
    available_blueprints: AVAILABLE_BLUEPRINTS,
    blueprints_count: AVAILABLE_BLUEPRINTS.length,
    database: {
      connected: db_connected,
      recent_runs_24h: recent_runs,
    },
  });
});
