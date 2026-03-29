# Executor as a Service — MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Kevin into an async Executor service: 3 Edge Functions + 1 DB table + Kevin CLI executor mode + GitHub Actions dispatch workflow.

**Architecture:** Supabase Edge Function (API layer) → GitHub Actions (compute layer) → callback to Edge Function. Single `runs` table in Supabase. Kevin CLI gets new `--run-id` executor mode that replaces issue-fetching with CLI params and adds HTTP callback.

**Tech Stack:** Supabase Edge Functions (Deno/TypeScript), PostgreSQL, Python (Kevin CLI), GitHub Actions

**Spec:** `docs/superpowers/specs/2026-03-29-executor-as-a-service-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `supabase/functions/execute/index.ts` | POST /execute — create run, dispatch to GitHub Actions |
| `supabase/functions/status/index.ts` | GET /status/{run_id} — query run state |
| `supabase/functions/callback/index.ts` | POST /callback — receive Kevin results, update DB |
| `supabase/functions/_shared/auth.ts` | API Key validation helper |
| `supabase/functions/_shared/hmac.ts` | HMAC-SHA256 sign/verify helper |
| `supabase/functions/_shared/transitions.ts` | State machine transition validation |
| `supabase/functions/_shared/supabase.ts` | Supabase client factory |
| `supabase/migrations/001_create_runs.sql` | runs table DDL |
| `.github/workflows/kevin-executor.yaml` | repository_dispatch workflow |
| `kevin/callback.py` | HTTP callback client (Kevin → Edge Function) |
| `kevin/tests/test_callback.py` | Tests for callback client |

### Modified Files

| File | Change |
|------|--------|
| `kevin/cli.py` | Add executor mode args + `cmd_run_executor()` entry point |
| `kevin/tests/test_cli_executor.py` | Tests for executor CLI mode (new file) |

---

## Task 1: Supabase Migration — runs table

**Files:**
- Create: `supabase/migrations/001_create_runs.sql`

- [ ] **Step 1: Create Supabase project structure**

```bash
mkdir -p supabase/migrations supabase/functions/_shared
```

- [ ] **Step 2: Write migration**

```sql
-- supabase/migrations/001_create_runs.sql

create table if not exists runs (
  run_id         uuid primary key default gen_random_uuid(),
  blueprint_id   text not null,
  instruction    text not null,
  context        jsonb default '{}',
  callback_url   text,
  status         text not null default 'pending'
                   check (status in (
                     'pending', 'dispatched', 'dispatch_failed',
                     'running', 'completed', 'failed'
                   )),
  result         jsonb,
  error_code     text,
  error_message  text,
  created_at     timestamptz default now(),
  updated_at     timestamptz default now()
);

create index idx_runs_status on runs(status);

-- Auto-update updated_at
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger runs_updated_at
  before update on runs
  for each row execute function update_updated_at();
```

- [ ] **Step 3: Commit**

```bash
git add supabase/
git commit -m "feat: add runs table migration for executor service"
```

---

## Task 2: Shared Edge Function Utilities

**Files:**
- Create: `supabase/functions/_shared/auth.ts`
- Create: `supabase/functions/_shared/hmac.ts`
- Create: `supabase/functions/_shared/transitions.ts`
- Create: `supabase/functions/_shared/supabase.ts`

- [ ] **Step 1: Write auth helper**

```typescript
// supabase/functions/_shared/auth.ts

export function validateApiKey(req: Request): boolean {
  const header = req.headers.get("authorization") ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  const expected = Deno.env.get("EXECUTOR_API_KEY") ?? "";
  if (!expected || !token) return false;
  return timingSafeEqual(token, expected);
}

function timingSafeEqual(a: string, b: string): boolean {
  const enc = new TextEncoder();
  const bufA = enc.encode(a);
  const bufB = enc.encode(b);
  if (bufA.length !== bufB.length) return false;
  let result = 0;
  for (let i = 0; i < bufA.length; i++) {
    result |= bufA[i] ^ bufB[i];
  }
  return result === 0;
}
```

- [ ] **Step 2: Write HMAC helper**

```typescript
// supabase/functions/_shared/hmac.ts

export async function verifyHmac(
  secret: string,
  body: string,
  signature: string,
): Promise<boolean> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(body));
  const expected = arrayToHex(new Uint8Array(sig));
  return timingSafeCompare(expected, signature);
}

export async function signHmac(secret: string, body: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(body));
  return arrayToHex(new Uint8Array(sig));
}

function arrayToHex(arr: Uint8Array): string {
  return Array.from(arr).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function timingSafeCompare(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}
```

- [ ] **Step 3: Write state machine transitions**

```typescript
// supabase/functions/_shared/transitions.ts

const TRANSITIONS: Record<string, Set<string>> = {
  pending:          new Set(["dispatched", "dispatch_failed"]),
  dispatched:       new Set(["running"]),
  running:          new Set(["completed", "failed"]),
};

export function isValidTransition(from: string, to: string): boolean {
  return TRANSITIONS[from]?.has(to) ?? false;
}
```

- [ ] **Step 4: Write Supabase client factory**

```typescript
// supabase/functions/_shared/supabase.ts

import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

let _client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (_client) return _client;
  const url = Deno.env.get("SUPABASE_URL")!;
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  _client = createClient(url, key);
  return _client;
}
```

- [ ] **Step 5: Commit**

```bash
git add supabase/functions/_shared/
git commit -m "feat: add shared Edge Function utilities (auth, hmac, transitions, supabase)"
```

---

## Task 3: POST /execute Edge Function

**Files:**
- Create: `supabase/functions/execute/index.ts`

- [ ] **Step 1: Write the execute function**

```typescript
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
```

- [ ] **Step 2: Commit**

```bash
git add supabase/functions/execute/
git commit -m "feat: add POST /execute Edge Function"
```

---

## Task 4: GET /status Edge Function

**Files:**
- Create: `supabase/functions/status/index.ts`

- [ ] **Step 1: Write the status function**

```typescript
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
```

- [ ] **Step 2: Commit**

```bash
git add supabase/functions/status/
git commit -m "feat: add GET /status Edge Function"
```

---

## Task 5: POST /callback Edge Function

**Files:**
- Create: `supabase/functions/callback/index.ts`

- [ ] **Step 1: Write the callback function**

```typescript
// supabase/functions/callback/index.ts

import { verifyHmac } from "../_shared/hmac.ts";
import { isValidTransition } from "../_shared/transitions.ts";
import { getSupabase } from "../_shared/supabase.ts";

const HMAC_SECRET = Deno.env.get("CALLBACK_HMAC_SECRET") ?? "";

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), { status: 405 });
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

  return new Response(JSON.stringify({ ok: true }), { status: 200 });
});
```

- [ ] **Step 2: Commit**

```bash
git add supabase/functions/callback/
git commit -m "feat: add POST /callback Edge Function with HMAC + state machine validation"
```

---

## Task 6: Kevin Callback Client

**Files:**
- Create: `kevin/callback.py`
- Create: `kevin/tests/test_callback.py`

- [ ] **Step 1: Write failing test**

```python
# kevin/tests/test_callback.py

import hashlib
import hmac
import json
from unittest.mock import patch, MagicMock

import pytest

from kevin.callback import CallbackClient


class TestCallbackClient:
    def test_sign_body(self):
        client = CallbackClient(
            callback_url="https://example.com/callback",
            callback_secret="test-secret",
        )
        body = '{"run_id": "abc"}'
        sig = client._sign(body)
        expected = hmac.new(b"test-secret", body.encode(), hashlib.sha256).hexdigest()
        assert sig == expected

    @patch("kevin.callback.urllib.request.urlopen")
    def test_report_status_sends_hmac(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = CallbackClient(
            callback_url="https://example.com/callback",
            callback_secret="test-secret",
        )
        client.report_status(run_id="abc-123", status="running")

        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.get_header("X-signature") is not None
        assert req.get_header("Content-type") == "application/json"

        sent_body = json.loads(req.data.decode())
        assert sent_body["run_id"] == "abc-123"
        assert sent_body["status"] == "running"

    def test_noop_client_does_nothing(self):
        client = CallbackClient(callback_url="", callback_secret="")
        # Should not raise
        client.report_status(run_id="abc", status="running")

    @patch("kevin.callback.urllib.request.urlopen")
    def test_report_with_result(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = CallbackClient(
            callback_url="https://example.com/callback",
            callback_secret="secret",
        )
        client.report_status(
            run_id="abc",
            status="completed",
            result={"pr_url": "https://github.com/pr/1"},
        )

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode())
        assert sent["status"] == "completed"
        assert sent["result"]["pr_url"] == "https://github.com/pr/1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/randy/Documents/code/AgenticSDLC && python -m pytest kevin/tests/test_callback.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'kevin.callback'`

- [ ] **Step 3: Write callback client implementation**

```python
# kevin/callback.py
"""HTTP callback client for Executor-as-a-Service mode.

Kevin calls back to the Edge Function to report run status changes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import urllib.request
import urllib.error
from typing import Any

log = logging.getLogger(__name__)


class CallbackClient:
    """Sends HMAC-signed status updates to the Edge Function callback endpoint."""

    def __init__(self, *, callback_url: str, callback_secret: str) -> None:
        self._url = callback_url
        self._secret = callback_secret

    def report_status(
        self,
        *,
        run_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Send a status update to the callback URL. No-op if URL is empty."""
        if not self._url:
            return

        payload: dict[str, Any] = {"run_id": run_id, "status": status}
        if result is not None:
            payload["result"] = result
        if error_code:
            payload["error_code"] = error_code
        if error_message:
            payload["error_message"] = error_message

        body = json.dumps(payload)
        signature = self._sign(body)

        req = urllib.request.Request(
            self._url,
            data=body.encode(),
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                log.info("Callback %s → %s (HTTP %d)", run_id, status, resp.status)
        except (urllib.error.URLError, OSError) as exc:
            log.warning("Callback failed for %s: %s", run_id, exc)

    def _sign(self, body: str) -> str:
        return hmac.new(
            self._secret.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/randy/Documents/code/AgenticSDLC && python -m pytest kevin/tests/test_callback.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add kevin/callback.py kevin/tests/test_callback.py
git commit -m "feat: add CallbackClient for executor-mode HTTP callbacks"
```

---

## Task 7: Kevin CLI Executor Mode

**Files:**
- Modify: `kevin/cli.py` (add executor subcommand args + `cmd_run_executor` function)
- Create: `kevin/tests/test_cli_executor.py`

- [ ] **Step 1: Write failing test**

```python
# kevin/tests/test_cli_executor.py

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from kevin.cli import main


class TestExecutorMode:
    """Test the executor CLI entry point: kevin run --run-id ... --blueprint ..."""

    @patch("kevin.cli._execute_blocks")
    @patch("kevin.cli.load")
    @patch("kevin.cli.find_blueprint")
    def test_executor_mode_loads_blueprint_and_executes(
        self, mock_find, mock_load, mock_exec, tmp_path
    ):
        # Setup
        mock_find.return_value = tmp_path / "bp.yaml"
        mock_bp = MagicMock()
        mock_bp.blueprint_id = "bp_coding_task.1.0.0"
        mock_bp.blueprint_name = "Test"
        mock_bp.blocks = []
        mock_load.return_value = mock_bp

        mock_exec.return_value = "completed"

        ctx = json.dumps({"repo": "owner/app", "ref": "main"})

        result = main([
            "run",
            "--run-id", "test-uuid-123",
            "--blueprint", "bp_coding_task.1.0.0",
            "--instruction", "Add health check",
            "--context", ctx,
            "--callback-url", "https://example.com/callback",
            "--callback-secret", "secret123",
        ])

        assert result == 0
        mock_find.assert_called_once()
        mock_load.assert_called_once()

    def test_executor_mode_requires_run_id_with_instruction(self):
        """--instruction without --run-id should fail."""
        result = main([
            "run",
            "--instruction", "Add health check",
            "--blueprint", "bp_coding_task.1.0.0",
        ])
        # Should fail because --run-id is required when --instruction is set
        assert result != 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/randy/Documents/code/AgenticSDLC && python -m pytest kevin/tests/test_cli_executor.py -v
```

Expected: FAIL — unrecognized arguments `--run-id`, `--instruction`, `--context`, `--callback-url`, `--callback-secret`

- [ ] **Step 3: Add executor mode args to CLI parser**

In `kevin/cli.py`, locate the `run` subparser section (around line 40-60 where args are added). Add the new arguments after the existing ones:

```python
# Add after existing --blueprint arg (around line 55)
    run_sub.add_argument("--run-id", default="")
    run_sub.add_argument("--instruction", default="")
    run_sub.add_argument("--context", default="{}")
    run_sub.add_argument("--callback-url", default="")
    run_sub.add_argument("--callback-secret", default="")
```

- [ ] **Step 4: Add executor mode entry point in cmd_run**

In `kevin/cli.py`, at the top of `cmd_run()` (line ~105), add executor mode detection before the existing issue-mode logic:

```python
def cmd_run(args: argparse.Namespace) -> int:
    # --- Executor mode: --run-id present ---
    if getattr(args, "run_id", "") and getattr(args, "instruction", ""):
        return _cmd_run_executor(args)

    # --- Existing issue mode below ---
    ...
```

- [ ] **Step 5: Implement _cmd_run_executor function**

Add this function to `kevin/cli.py` (before `_cmd_run_inner`):

```python
def _cmd_run_executor(args: argparse.Namespace) -> int:
    """Executor-as-a-Service mode: blueprint + instruction + context from CLI args."""
    import json as _json
    from kevin.callback import CallbackClient

    cfg = build_config(
        repo=getattr(args, "repo", ""),
        target_repo=getattr(args, "target_repo", ""),
        dry_run=getattr(args, "dry_run", False),
        verbose=getattr(args, "verbose", False),
    )

    callback = CallbackClient(
        callback_url=args.callback_url,
        callback_secret=args.callback_secret,
    )

    # Report: running
    callback.report_status(run_id=args.run_id, status="running")

    # Load blueprint
    try:
        bp_path = find_blueprint(cfg.blueprints_dir, args.blueprint)
        bp = load(bp_path)
    except FileNotFoundError:
        callback.report_status(
            run_id=args.run_id,
            status="failed",
            error_code="BLUEPRINT_NOT_FOUND",
            error_message=f"Blueprint not found: {args.blueprint}",
        )
        return 1

    # Build variables from instruction + context
    ctx = _json.loads(args.context) if args.context else {}
    variables = {
        "instruction": args.instruction,
        "target_repo": str(cfg.target_repo),
        "repo_full": ctx.get("repo", cfg.repo_full_name),
        "owner": ctx.get("repo", "").split("/")[0] if ctx.get("repo") else cfg.repo_owner,
        "repo": ctx.get("repo", "").split("/")[-1] if ctx.get("repo") else cfg.repo_name,
        "ref": ctx.get("ref", "main"),
        "run_id": args.run_id,
        # Compat: map instruction to issue fields so existing prompt templates work
        "issue_number": ctx.get("issue_number", "0"),
        "issue_title": args.instruction,
        "issue_body": args.instruction,
        "issue_labels": "",
    }

    # Create local run state
    state_mgr = StateManager(cfg.state_dir)
    run = state_mgr.create_run(
        blueprint_id=bp.blueprint_id,
        issue_number=int(variables.get("issue_number", 0)),
        repo=variables.get("repo_full", ""),
        variables=variables,
        blueprint_path=bp_path,
    )

    # Execute blocks
    try:
        final_status = _execute_blocks(
            bp.blocks, variables, run, state_mgr, cfg,
        )
    except Exception as exc:
        callback.report_status(
            run_id=args.run_id,
            status="failed",
            error_code="BLOCK_FAILED",
            error_message=str(exc),
        )
        return 1

    # Build result
    block_results = []
    for bid, bs in run.blocks.items():
        entry = {"block_id": bid, "status": bs.status}
        if bs.error:
            entry["error"] = bs.error
        block_results.append(entry)

    if final_status == "completed":
        callback.report_status(
            run_id=args.run_id,
            status="completed",
            result={"summary": f"Blueprint {bp.blueprint_id} completed", "blocks": block_results},
        )
    else:
        failed_block = next((b for b in block_results if b["status"] == "failed"), None)
        callback.report_status(
            run_id=args.run_id,
            status="failed",
            error_code="BLOCK_FAILED",
            error_message=f"Block {failed_block['block_id']} failed" if failed_block else "Unknown",
            result={"blocks": block_results},
        )

    return 0 if final_status == "completed" else 1
```

- [ ] **Step 6: Add validation — run-id required when instruction is set**

In the argument validation section at the start of `cmd_run()`, before the executor mode check:

```python
def cmd_run(args: argparse.Namespace) -> int:
    # Validate: --instruction requires --run-id
    if getattr(args, "instruction", "") and not getattr(args, "run_id", ""):
        print("error: --instruction requires --run-id", file=sys.stderr)
        return 1

    # --- Executor mode ---
    if getattr(args, "run_id", "") and getattr(args, "instruction", ""):
        return _cmd_run_executor(args)
    ...
```

- [ ] **Step 7: Run tests**

```bash
cd /Users/randy/Documents/code/AgenticSDLC && python -m pytest kevin/tests/test_cli_executor.py -v
```

Expected: 2 passed

- [ ] **Step 8: Run full existing test suite to check no regression**

```bash
cd /Users/randy/Documents/code/AgenticSDLC && python -m pytest kevin/tests/ -v
```

Expected: All existing tests still pass

- [ ] **Step 9: Commit**

```bash
git add kevin/cli.py kevin/tests/test_cli_executor.py
git commit -m "feat: add executor mode to Kevin CLI (--run-id + --instruction + --callback)"
```

---

## Task 8: GitHub Actions Executor Workflow

**Files:**
- Create: `.github/workflows/kevin-executor.yaml`

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/kevin-executor.yaml
name: Kevin Executor

on:
  repository_dispatch:
    types: [executor-run]

jobs:
  execute:
    runs-on: ubuntu-latest
    timeout-minutes: 35
    steps:
      - name: Checkout AgenticSDLC
        uses: actions/checkout@v4

      - name: Checkout target repo
        if: github.event.client_payload.context != ''
        run: |
          CONTEXT='${{ github.event.client_payload.context }}'
          REPO=$(echo "$CONTEXT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('repo',''))" 2>/dev/null || echo "")
          REF=$(echo "$CONTEXT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('ref','main'))" 2>/dev/null || echo "main")
          if [ -n "$REPO" ]; then
            git clone "https://x-access-token:${{ secrets.GITHUB_TOKEN }}@github.com/${REPO}.git" target-repo
            cd target-repo && git checkout "$REF"
          fi

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Kevin
        run: pip install -e .

      - name: Install Claude Code CLI
        run: npm install -g @anthropic-ai/claude-code

      - name: Run Kevin Executor
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          TARGET_DIR="."
          if [ -d "target-repo" ]; then TARGET_DIR="target-repo"; fi

          python -m kevin run \
            --run-id "${{ github.event.client_payload.run_id }}" \
            --blueprint "${{ github.event.client_payload.blueprint_id }}" \
            --instruction "${{ github.event.client_payload.instruction }}" \
            --context '${{ github.event.client_payload.context }}' \
            --callback-url "${{ github.event.client_payload.callback_url }}" \
            --callback-secret "${{ secrets.CALLBACK_HMAC_SECRET }}" \
            --target-repo "$TARGET_DIR"

      - name: Upload run state
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: kevin-run-${{ github.event.client_payload.run_id }}
          path: |
            .kevin/runs/
            target-repo/.kevin/runs/
          retention-days: 30
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/kevin-executor.yaml
git commit -m "feat: add GitHub Actions workflow for executor-mode dispatch"
```

---

## Task 9: End-to-End Smoke Test Script

**Files:**
- Create: `scripts/test_executor_e2e.sh`

- [ ] **Step 1: Write the smoke test script**

```bash
#!/usr/bin/env bash
# scripts/test_executor_e2e.sh
#
# Smoke test for Executor as a Service.
# Prerequisites:
#   - EXECUTOR_API_KEY env var set
#   - EXECUTOR_BASE_URL env var set (e.g. https://<project>.supabase.co/functions/v1)
#
# Usage: ./scripts/test_executor_e2e.sh

set -euo pipefail

: "${EXECUTOR_API_KEY:?Set EXECUTOR_API_KEY}"
: "${EXECUTOR_BASE_URL:?Set EXECUTOR_BASE_URL}"

echo "=== Step 1: POST /execute ==="
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${EXECUTOR_BASE_URL}/execute" \
  -H "Authorization: Bearer ${EXECUTOR_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_id": "bp_coding_task.1.0.0",
    "instruction": "Add a /health endpoint that returns {\"status\": \"ok\"}",
    "context": {"repo": "anlaganlag/test-repo", "ref": "main"}
  }')

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)

echo "HTTP $HTTP_CODE"
echo "$BODY" | python3 -m json.tool

if [ "$HTTP_CODE" != "202" ]; then
  echo "FAIL: Expected 202, got $HTTP_CODE"
  exit 1
fi

RUN_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
echo "run_id: $RUN_ID"

echo ""
echo "=== Step 2: Poll GET /status ==="
for i in $(seq 1 60); do
  sleep 10
  STATUS_RESP=$(curl -s "${EXECUTOR_BASE_URL}/status/${RUN_ID}" \
    -H "Authorization: Bearer ${EXECUTOR_API_KEY}")
  STATUS=$(echo "$STATUS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "  [$i] status=$STATUS"

  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    echo ""
    echo "=== Final Result ==="
    echo "$STATUS_RESP" | python3 -m json.tool
    exit 0
  fi
done

echo "TIMEOUT: Run did not complete in 10 minutes"
exit 1
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/test_executor_e2e.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/test_executor_e2e.sh
git commit -m "feat: add executor e2e smoke test script"
```

---

## Task 10: Supabase Deployment & Secrets Setup

This task is manual / interactive — no TDD needed.

- [ ] **Step 1: Initialize Supabase project (if not already)**

```bash
cd /Users/randy/Documents/code/AgenticSDLC
npx supabase init  # if supabase/ config doesn't exist yet
```

- [ ] **Step 2: Link to remote project**

```bash
npx supabase link --project-ref <your-project-ref>
```

- [ ] **Step 3: Run migration**

```bash
npx supabase db push
```

- [ ] **Step 4: Set Edge Function secrets**

```bash
npx supabase secrets set \
  EXECUTOR_API_KEY="<generate-a-strong-key>" \
  CALLBACK_HMAC_SECRET="<generate-another-key>" \
  GITHUB_TOKEN="<github-pat-with-repo-dispatch>" \
  DISPATCH_REPO="anlaganlag/AgenticSDLC" \
  CALLBACK_BASE_URL="https://<project>.supabase.co/functions/v1"
```

- [ ] **Step 5: Deploy Edge Functions**

```bash
npx supabase functions deploy execute
npx supabase functions deploy status
npx supabase functions deploy callback
```

- [ ] **Step 6: Set GitHub Actions secrets**

In GitHub repo settings → Secrets → Actions:
- `CALLBACK_HMAC_SECRET` — same value as Edge Function secret
- `ANTHROPIC_API_KEY` — Claude API key (likely already set)

- [ ] **Step 7: Run smoke test**

```bash
export EXECUTOR_API_KEY="<the-key-you-set>"
export EXECUTOR_BASE_URL="https://<project>.supabase.co/functions/v1"
./scripts/test_executor_e2e.sh
```

Expected: POST returns 202, polling shows status progression pending → dispatched → running → completed/failed.
