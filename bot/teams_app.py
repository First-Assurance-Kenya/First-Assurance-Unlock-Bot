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

from microsoft_teams.api import MessageActivity, TypingActivityInput
from microsoft_teams.apps import ActivityContext, App


from bot.teams_session import get_session, handle_user_input

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("account-unlock-bot")

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from microsoft_teams.apps.http.fastapi_adapter import FastAPIAdapter

# Enterprise Security Hardening:
# Disable Swagger docs, Redoc, and OpenAPI schemas so no endpoint schema is exposed
secure_fastapi = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

# Mount corporate brand assets directory for logo delivery
assets_dir = ROOT / "assets"
assets_dir.mkdir(exist_ok=True)
secure_fastapi.mount("/static", StaticFiles(directory=assets_dir), name="static")

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
    try:
        await ctx.send(TypingActivityInput())
    except Exception as e:
        logger.debug("Typing indicator suppressed: %s", e)

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
    sender = ctx.activity.from_
    sender_name = sender.name if sender else "Unknown"
    sender_id = sender.id if sender else "Unknown"
    sender_email = getattr(sender, "email", None) if sender else None
    sender_upn = getattr(sender, "user_principal_name", None) if sender else None
    sender_aad_id = getattr(sender, "aad_object_id", None) if sender else None

    logger.info(
        "AUDIT: Message received from user='%s' (UPN: %s, ID: %s, AAD: %s) in conv='%s'",
        sender_name,
        sender_upn or sender_email or "N/A",
        sender_id,
        sender_aad_id or "N/A",
        conversation_id,
    )

    # Immediately show the 3 animated typing dots in Teams chat for responsive UX
    try:
        await ctx.send(TypingActivityInput())
    except Exception as e:
        logger.debug("Typing indicator suppressed: %s", e)

    reply_text, card = handle_user_input(
        conversation_id,
        text=activity_text,
        value=activity_value,
        requester_name=sender_name,
        requester_id=sender_id,
        requester_email=sender_email,
        requester_upn=sender_upn,
        requester_aad_id=sender_aad_id,
    )

    if card is not None:
        await ctx.send(card)
    else:
        await ctx.send(reply_text.strip())



if __name__ == "__main__":
    port = int(os.getenv("PORT", "3978"))
    logger.info("Starting Account Unlock bot on port %s", port)
    asyncio.run(app.start(port=port))
