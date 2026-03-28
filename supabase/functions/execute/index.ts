// supabase/functions/execute/index.ts

import { validateApiKey } from "../_shared/auth.ts";
import { getSupabase } from "../_shared/supabase.ts";

const GITHUB_TOKEN = Deno.env.get("GITHUB_TOKEN") ?? "";
const DISPATCH_REPO = Deno.env.get("DISPATCH_REPO") ?? "anlaganlag/AgenticSDLC";
const CALLBACK_BASE_URL = Deno.env.get("CALLBACK_BASE_URL") ?? "";

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), { status: 405 });
  }

  if (!validateApiKey(req)) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), { status: 401 });
  }

  const body = await req.json();
  const { blueprint_id, instruction, context, callback_url } = body;

  if (!blueprint_id || !instruction) {
    return new Response(
      JSON.stringify({ error: "blueprint_id and instruction are required" }),
      { status: 400 },
    );
  }

  const db = getSupabase();

  // Insert run record
  const { data: run, error: insertErr } = await db
    .from("runs")
    .insert({
      blueprint_id,
      instruction,
      context: context ?? {},
      callback_url: callback_url ?? null,
      status: "pending",
    })
    .select("run_id, status")
    .single();

  if (insertErr || !run) {
    return new Response(
      JSON.stringify({ error: "Failed to create run", detail: insertErr?.message }),
      { status: 500 },
    );
  }

  // Dispatch to GitHub Actions
  const callbackUrl = `${CALLBACK_BASE_URL}/callback`;
  const dispatchOk = await triggerDispatch(run.run_id, {
    blueprint_id,
    instruction,
    context: JSON.stringify(context ?? {}),
    callback_url: callbackUrl,
  });

  if (!dispatchOk) {
    await db
      .from("runs")
      .update({ status: "dispatch_failed", error_code: "DISPATCH_FAILED" })
      .eq("run_id", run.run_id);

    return new Response(
      JSON.stringify({ run_id: run.run_id, status: "dispatch_failed" }),
      { status: 502 },
    );
  }

  // Mark as dispatched
  await db.from("runs").update({ status: "dispatched" }).eq("run_id", run.run_id);

  return new Response(
    JSON.stringify({ run_id: run.run_id, status: "dispatched" }),
    { status: 202 },
  );
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
