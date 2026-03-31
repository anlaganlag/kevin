import { verifyHmac } from "../_shared/hmac.ts";
import { isValidTransition } from "../_shared/transitions.ts";
import { getSupabase } from "../_shared/supabase.ts";
import { corsOptions, json } from "../_shared/cors.ts";

const HMAC_SECRET = Deno.env.get("CALLBACK_HMAC_SECRET") ?? "";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return corsOptions();

  if (req.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  // Read body as text for HMAC verification
  const rawBody = await req.text();
  const signature = req.headers.get("x-signature") ?? "";

  if (!HMAC_SECRET || !signature) {
    return new Response(JSON.stringify({ error: "Missing signature" }), { status: 403 });
  }

  const valid = await verifyHmac(HMAC_SECRET, rawBody, signature);
  if (!valid) {
    return new Response(JSON.stringify({ error: "Invalid signature" }), { status: 403 });
  }

  const body = JSON.parse(rawBody);
  const { run_id, status, result, error_code, error_message } = body;

  if (!run_id || !status) {
    return new Response(
      JSON.stringify({ error: "run_id and status are required" }),
      { status: 400 },
    );
  }

  const db = getSupabase();

  // Fetch current run
  const { data: run, error: fetchErr } = await db
    .from("runs")
    .select("status")
    .eq("run_id", run_id)
    .single();

  if (fetchErr || !run) {
    return new Response(JSON.stringify({ error: "Run not found" }), { status: 404 });
  }

  // Validate state transition
  if (!isValidTransition(run.status, status)) {
    return new Response(
      JSON.stringify({
        error: "Invalid state transition",
        from: run.status,
        to: status,
      }),
      { status: 409 },
    );
  }

  // Update run
  const update: Record<string, unknown> = { status };
  if (result !== undefined) update.result = result;
  if (error_code) update.error_code = error_code;
  if (error_message) update.error_message = error_message;

  const { error: updateErr } = await db
    .from("runs")
    .update(update)
    .eq("run_id", run_id);

  if (updateErr) {
    return new Response(
      JSON.stringify({ error: "Failed to update run", detail: updateErr.message }),
      { status: 500 },
    );
  }

  // Webhook forwarding: if run reached a terminal state and has a client callback_url,
  // forward the result to the client so they don't need to poll.
  const TERMINAL = new Set(["completed", "failed", "dispatch_failed"]);
  if (TERMINAL.has(status)) {
    const { data: fullRun } = await db
      .from("runs")
      .select("callback_url, result, error_code, error_message")
      .eq("run_id", run_id)
      .single();

    const clientUrl = fullRun?.callback_url;
    // Only forward if the client provided their own callback_url (not the internal one)
    const internalBase = Deno.env.get("CALLBACK_BASE_URL") ?? "";
    if (clientUrl && !clientUrl.startsWith(internalBase)) {
      try {
        await fetch(clientUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            run_id,
            status,
            result: fullRun.result,
            error_code: fullRun.error_code,
            error_message: fullRun.error_message,
          }),
        });
      } catch {
        // Best-effort: don't fail the callback if webhook forwarding fails
      }
    }
  }

  return new Response(JSON.stringify({ ok: true }), { status: 200 });
});
