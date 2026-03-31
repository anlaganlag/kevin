import json
from pathlib import Path

from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ChannelAccount

REFERENCES_FILE = Path(__file__).parent / ".conversation_references.json"


class KevinBot(ActivityHandler):
    """Minimal Teams bot — responds to messages and tracks conversation references."""

    def __init__(self) -> None:
        super().__init__()
        self.conversation_references: dict[str, dict] = self._load_references()

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        # 每次收到消息都保存 reference（用于主动推送）
        self._save_conversation_reference(turn_context)

        text = (turn_context.activity.text or "").strip()

        # 去掉 @mention 前缀
        if turn_context.activity.entities:
            for entity in turn_context.activity.entities:
                if entity.type == "mention":
                    mention_text = entity.additional_properties.get("text", "")
                    text = text.replace(mention_text, "").strip()

        if text.lower() in ("hello", "hi", "help", ""):
            await turn_context.send_activity(
                "Kevin Teams Bot is alive! \U0001f916\n\n"
                "Supported commands:\n"
                "- `help` \u2014 show this message\n"
                "- `ping` \u2014 check connectivity\n"
                "- `run <blueprint_id> <instruction>` \u2014 execute a blueprint\n"
                "- `status <run_id>` \u2014 check run status\n"
                "- `runs` \u2014 list recent runs\n"
                "- `cancel <run_id>` \u2014 cancel a running task"
            )
        elif text.lower() == "ping":
            await turn_context.send_activity("pong \U0001f3d3")
        elif text.lower().startswith("run "):
            await self._handle_run(turn_context, text[4:].strip())
        elif text.lower().startswith("status "):
            await self._handle_status(turn_context, text[7:].strip())
        elif text.lower() == "runs":
            await self._handle_list_runs(turn_context)
        elif text.lower().startswith("cancel "):
            await self._handle_cancel(turn_context, text[7:].strip())
        else:
            await turn_context.send_activity(
                f"Unknown command: `{text}`\n\nType `help` for available commands."
            )

    async def on_conversation_update_activity(self, turn_context: TurnContext) -> None:
        self._save_conversation_reference(turn_context)
        if turn_context.activity.members_added:
            for member in turn_context.activity.members_added:
                if member.id != turn_context.activity.recipient.id:
                    await turn_context.send_activity(
                        "Kevin Bot connected! Type `help` to get started."
                    )

    def _save_conversation_reference(self, turn_context: TurnContext) -> None:
        ref = TurnContext.get_conversation_reference(turn_context.activity)
        # 序列化为 dict 以便持久化
        ref_dict = {
            "conversation": {"id": ref.conversation.id},
            "service_url": ref.service_url,
            "channel_id": ref.channel_id,
            "bot": {"id": ref.bot.id, "name": ref.bot.name} if ref.bot else None,
        }
        self.conversation_references[ref.conversation.id] = ref_dict
        self._persist_references()

    def _persist_references(self) -> None:
        REFERENCES_FILE.write_text(json.dumps(self.conversation_references, indent=2))

    def _load_references(self) -> dict[str, dict]:
        if REFERENCES_FILE.exists():
            return json.loads(REFERENCES_FILE.read_text())
        return {}

    async def _handle_run(self, ctx: TurnContext, args: str) -> None:
        from kevin.teams_bot.executor_client import execute, is_configured

        if not is_configured():
            await ctx.send_activity("Executor not configured. Set EXECUTOR_BASE_URL and EXECUTOR_API_KEY.")
            return

        parts = args.split(" ", 1)
        if len(parts) < 2:
            await ctx.send_activity("Usage: `run <blueprint_id> <instruction>`")
            return

        blueprint_id, instruction = parts
        try:
            result = execute(blueprint_id, instruction)
            await ctx.send_activity(
                f"\u2705 Dispatched!\n\n"
                f"- **run_id**: `{result['run_id']}`\n"
                f"- **status**: {result['status']}\n\n"
                f"Use `status {result['run_id']}` to check progress."
            )
        except Exception as exc:
            await ctx.send_activity(f"\u274c Failed to dispatch: {exc}")

    async def _handle_status(self, ctx: TurnContext, run_id: str) -> None:
        from kevin.teams_bot.executor_client import get_status, is_configured

        if not is_configured():
            await ctx.send_activity("Executor not configured.")
            return

        try:
            run = get_status(run_id.strip())
            lines = [
                f"**Run** `{run['run_id']}`",
                f"- **Blueprint**: {run['blueprint_id']}",
                f"- **Status**: {run['status']}",
                f"- **Elapsed**: {run.get('elapsed_seconds', '?')}s",
            ]
            if run.get("error_message"):
                lines.append(f"- **Error**: {run['error_message']}")
            await ctx.send_activity("\n".join(lines))
        except Exception as exc:
            await ctx.send_activity(f"\u274c Failed to fetch status: {exc}")

    async def _handle_list_runs(self, ctx: TurnContext) -> None:
        from kevin.teams_bot.executor_client import list_runs, is_configured

        if not is_configured():
            await ctx.send_activity("Executor not configured.")
            return

        try:
            runs = list_runs(limit=5)
            if not runs:
                await ctx.send_activity("No runs found.")
                return
            lines = ["**Recent Runs**\n"]
            for r in runs:
                lines.append(f"- `{r['run_id'][:8]}...` {r['status']} — {r['blueprint_id']}")
            await ctx.send_activity("\n".join(lines))
        except Exception as exc:
            await ctx.send_activity(f"\u274c Failed to list runs: {exc}")

    async def _handle_cancel(self, ctx: TurnContext, run_id: str) -> None:
        from kevin.teams_bot.executor_client import cancel_run, is_configured

        if not is_configured():
            await ctx.send_activity("Executor not configured.")
            return

        try:
            result = cancel_run(run_id.strip())
            await ctx.send_activity(f"\u2705 Run `{result['run_id']}` cancelled.")
        except Exception as exc:
            await ctx.send_activity(f"\u274c Failed to cancel: {exc}")
