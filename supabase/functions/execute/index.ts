// supabase/functions/execute/index.ts

import { validateApiKey } from "../_shared/auth.ts";
import { AVAILABLE_BLUEPRINTS, VALID_BLUEPRINTS } from "../_shared/blueprints.ts";
import { corsOptions, json } from "../_shared/cors.ts";
import { checkRateLimit } from "../_shared/rate_limit.ts";
import { getSupabase } from "../_shared/supabase.ts";

const GITHUB_TOKEN = Deno.env.get("GITHUB_TOKEN") ?? "";
const DISPATCH_REPO = Deno.env.get("DISPATCH_REPO") ?? "centific-cn/AgenticSDLC";
const CALLBACK_BASE_URL = Deno.env.get("CALLBACK_BASE_URL") ?? "";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return corsOptions();

  // Health check
  if (req.method === "GET") {
    return json({
      status: "ok",
      service: "kevin-executor",
    });
  }

  if (req.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  if (!validateApiKey(req)) {
    return json({
      error: "Unauthorized",
      hint: "Add header: Authorization: Bearer <your-api-key>",
    }, 401);
  }

  // Rate limit
  const rl = checkRateLimit(req);
  if (rl.limited) {
    return json(
      { error: "Rate limit exceeded", hint: "Max 10 requests per minute" },
      429,
    );
  }

  // Safe JSON parse
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return json({
      error: "Invalid JSON body",
      hint: "Check for unescaped quotes or trailing commas in your JSON",
    }, 400);
  }

  const { blueprint_id, instruction, context, callback_url, idempotency_key } = body as {
    blueprint_id?: string;
    instruction?: string;
    context?: Record<string, unknown>;
    callback_url?: string;
    idempotency_key?: string;
  };

  if (!blueprint_id || !instruction) {
    return json({
      error: "blueprint_id and instruction are required",
      example: {
        blueprint_id: "bp_coding_task.1.0.0",
        instruction: "Add a /health endpoint",
        context: { repo: "owner/repo", ref: "main" },
      },
    }, 400);
  }

  if (!VALID_BLUEPRINTS.has(blueprint_id as string)) {
    return json({
      error: `Unknown blueprint: ${blueprint_id}`,
      available: AVAILABLE_BLUEPRINTS,
    }, 400);
  }

  // Validate context.repo format if provided
  const repo = (context as Record<string, string>)?.repo;
  if (repo && !/^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/.test(repo)) {
    return json({
      error: "Invalid context.repo format",
      hint: "Use owner/repo format, e.g. anlaganlag/test-repo",
    }, 400);
  }

  const db = getSupabase();

  // Idempotency: return existing run if key matches an active run
  if (idempotency_key) {
    const { data: existing } = await db
      .from("runs")
      .select("run_id, status")
      .eq("idempotency_key", idempotency_key)
      .not("status", "in", '("completed","failed","dispatch_failed")')
      .maybeSingle();

    if (existing) {
      return json({ run_id: existing.run_id, status: existing.status, deduplicated: true }, 200);
    }
  }

  // Insert run record
  const { data: run, error: insertErr } = await db
    .from("runs")
    .insert({
      blueprint_id,
      instruction,
      context: context ?? {},
      callback_url: callback_url ?? null,
      idempotency_key: idempotency_key ?? null,
      status: "pending",
    })
    .select("run_id, status")
    .single();

  if (insertErr || !run) {
    return json(
      { error: "Failed to create run", detail: insertErr?.message },
      500,
    );
  }

  // Dispatch to GitHub Actions
  const callbackUrl = `${CALLBACK_BASE_URL}/callback`;
  const dispatchOk = await triggerDispatch(run.run_id, {
    blueprint_id: blueprint_id as string,
    instruction: instruction as string,
    context: JSON.stringify(context ?? {}),
    callback_url: callbackUrl,
  });

  if (!dispatchOk) {
    await db
      .from("runs")
      .update({ status: "dispatch_failed", error_code: "DISPATCH_FAILED" })
      .eq("run_id", run.run_id);

    return json(
      { run_id: run.run_id, status: "dispatch_failed" },
      502,
    );
  }

  // Mark as dispatched
  await db.from("runs").update({ status: "dispatched" }).eq("run_id", run.run_id);

  return json({ run_id: run.run_id, status: "dispatched" }, 202);
});

async function triggerDispatch(
  runId: string,
  payload: Record<string, string>,
): Promise<boolean> {
  const url = `https://api.github.com/repos/${DISPATCH_REPO}/dispatches`;
  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `token ${GITHUB_TOKEN}`,
        Accept: "application/vnd.github.v3+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        event_type: "executor-run",
        client_payload: { run_id: runId, ...payload },
      }),
    });
    return resp.status === 204;
  } catch {
    return false;
  }
}
