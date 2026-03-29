"""Kevin Teams Bot — aiohttp server with Bot Framework + notify endpoint."""

import hashlib
import hmac
import json
import sys
import traceback

from aiohttp import web
from aiohttp.web import Request, Response
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import Activity, Attachment

from bot import KevinBot
from cards import build_run_status_card
from config import BotConfig

config = BotConfig()

settings = BotFrameworkAdapterSettings(
    app_id=config.APP_ID,
    app_password=config.APP_PASSWORD,
    channel_auth_tenant=config.APP_TENANT_ID,
)
adapter = BotFrameworkAdapter(settings)


async def on_error(context: TurnContext, error: Exception) -> None:
    print(f"[ERROR] {error}", file=sys.stderr)
    traceback.print_exc()
    await context.send_activity("Sorry, something went wrong.")


adapter.on_turn_error = on_error

bot = KevinBot()

# Card activity ID 注册表：run_id → {conversation_id, activity_id}
card_registry: dict[str, dict] = {}


async def handle_messages(req: Request) -> Response:
    """POST /api/messages — Teams 消息入口。"""
    if "application/json" not in req.headers.get("Content-Type", ""):
        return Response(status=415)

    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    response = await adapter.process_activity(activity, auth_header, bot.on_turn)
    if response:
        return Response(body=response.body, status=response.status)
    return Response(status=201)


def _verify_secret(req: Request, body_bytes: bytes) -> bool:
    """验证 GitHub Actions 请求的 HMAC 签名。无 secret 配置时跳过。"""
    if not config.BOT_SECRET:
        return True
    signature = req.headers.get("X-Bot-Signature", "")
    expected = hmac.new(
        config.BOT_SECRET.encode(), body_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


async def handle_notify(req: Request) -> Response:
    """POST /api/notify — 接收 Kevin 运行状态推送，发送/更新 Adaptive Card。"""
    body_bytes = await req.read()

    if not _verify_secret(req, body_bytes):
        return Response(status=401, text="Invalid signature")

    payload = json.loads(body_bytes)
    run_id = payload.get("run_id", "")

    if not bot.conversation_references:
        return web.json_response(
            {"error": "No conversation references. Send a message to the bot first."},
            status=400,
        )

    card = build_run_status_card(payload)
    attachment = Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card,
    )
    activity = Activity(
        type="message",
        attachments=[attachment],
    )

    # 向所有已知的 conversation 推送（通常只有一个）
    for conv_id, ref_dict in bot.conversation_references.items():
        try:
            # 构建 ConversationReference
            from botbuilder.schema import ConversationAccount, ConversationReference, ChannelAccount as CA

            conv_ref = ConversationReference(
                conversation=ConversationAccount(id=ref_dict["conversation"]["id"]),
                service_url=ref_dict["service_url"],
                channel_id=ref_dict["channel_id"],
                bot=CA(
                    id=ref_dict["bot"]["id"],
                    name=ref_dict["bot"].get("name"),
                ) if ref_dict.get("bot") else None,
            )

            async def _send(turn_context: TurnContext) -> None:
                resp = await turn_context.send_activity(activity)
                if resp and resp.id and run_id:
                    card_registry[run_id] = {
                        "conversation_id": conv_id,
                        "activity_id": resp.id,
                    }

            # 检查是否应该更新已有 Card
            existing = card_registry.get(run_id)
            if existing and existing["conversation_id"] == conv_id:
                async def _update(turn_context: TurnContext) -> None:
                    activity.id = existing["activity_id"]
                    await turn_context.update_activity(activity)

                await adapter.continue_conversation(conv_ref, _update, config.APP_ID)
            else:
                await adapter.continue_conversation(conv_ref, _send, config.APP_ID)

        except Exception as e:
            print(f"[NOTIFY ERROR] conv={conv_id}: {e}", file=sys.stderr)
            traceback.print_exc()

    return web.json_response({"ok": True, "run_id": run_id})


async def handle_health(req: Request) -> Response:
    """GET /api/health — 健康检查。"""
    refs = list(bot.conversation_references.keys())
    return web.json_response({
        "status": "ok",
        "bot": "kevin-teams-bot",
        "conversations": len(refs),
    })


app = web.Application()
app.router.add_post("/api/messages", handle_messages)
app.router.add_post("/api/notify", handle_notify)
app.router.add_get("/api/health", handle_health)

if __name__ == "__main__":
    print(f"Kevin Teams Bot starting on port {config.PORT}...")
    web.run_app(app, host="0.0.0.0", port=config.PORT)
