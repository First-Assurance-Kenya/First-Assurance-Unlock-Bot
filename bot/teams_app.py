import asyncio
import logging
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from microsoft_teams.api import MessageActivity
from microsoft_teams.apps import ActivityContext, App

from bot.teams_session import get_session, handle_user_input

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("account-unlock-bot")

from fastapi import FastAPI
from microsoft_teams.apps.http.fastapi_adapter import FastAPIAdapter

# Enterprise Security Hardening:
# Disable Swagger docs, Redoc, and OpenAPI schemas so no endpoint schema is exposed
secure_fastapi = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
adapter = FastAPIAdapter(app=secure_fastapi)

allow_unauth = os.getenv("DANGEROUSLY_ALLOW_UNAUTHENTICATED_REQUESTS", "false").lower() == "true"

app = App(
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    tenant_id=os.getenv("TENANT_ID") or None,
    http_server_adapter=adapter,
    dangerously_allow_unauthenticated_requests=allow_unauth,
)


async def send_welcome(ctx: ActivityContext) -> None:
    conversation_id = ctx.activity.conversation.id
    sender_name = ctx.activity.from_.name if ctx.activity.from_ else "Unknown"
    sender_id = ctx.activity.from_.id if ctx.activity.from_ else "N/A"
    reply_text, card = get_session(
        conversation_id, requester_name=sender_name, requester_id=sender_id
    ).start_with_card()
    if card is not None:
        await ctx.send(card)
    else:
        await ctx.send(reply_text.strip())


@app.on_install_add
async def handle_install(ctx: ActivityContext) -> None:
    await send_welcome(ctx)


@app.on_message
async def handle_message(ctx: ActivityContext[MessageActivity]) -> None:
    conversation_id = ctx.activity.conversation.id
    activity_text = ctx.activity.text
    activity_value = ctx.activity.value
    sender_name = ctx.activity.from_.name if ctx.activity.from_ else "Unknown"
    sender_id = ctx.activity.from_.id if ctx.activity.from_ else "Unknown"

    logger.info(
        "AUDIT: Message received from user='%s' (ID: %s) in conv='%s'",
        sender_name,
        sender_id,
        conversation_id,
    )

    reply_text, card = handle_user_input(
        conversation_id,
        text=activity_text,
        value=activity_value,
        requester_name=sender_name,
        requester_id=sender_id,
    )

    if card is not None:
        await ctx.send(card)
    else:
        await ctx.send(reply_text.strip())


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3978"))
    logger.info("Starting Account Unlock bot on port %s", port)
    asyncio.run(app.start(port=port))
