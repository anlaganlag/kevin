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
                "- `ping` \u2014 check connectivity"
            )
        elif text.lower() == "ping":
            await turn_context.send_activity("pong \U0001f3d3")
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
