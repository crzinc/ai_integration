"""Telegram bot for customers — receives messages, classifies, auto-replies."""

from __future__ import annotations

import structlog
from telegram import Bot, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .autoresponder import get_auto_response, should_auto_respond
from .classifier import classify_by_keywords, classify_message
from .config import settings
from .models import Ticket, TicketStatus, async_session
from .router import format_routing_message, get_routing_target

logger = structlog.get_logger()

CATEGORY_EMOJI = {
    "sales": "💼", "support": "🛠️", "technical": "🔧",
    "billing": "💳", "management": "👑",
}


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Send any message and our AI assistant will classify your inquiry "
        "and forward it to the right team.\n\n"
        "You'll receive an auto-reply if possible, or a specialist will contact you shortly."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "ℹ️ How it works:\n\n"
        "1. Send your message\n"
        "2. AI classifies your inquiry\n"
        "3. We route it to the right department\n"
        "4. You get a reply (auto or from a specialist)\n\n"
        "Just type your question below 👇"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    user = message.from_user
    if not user:
        return

    logger.info("message_received", user_id=user.id, username=user.username)

    await message.chat.send_action("typing")

    # 1. Classify
    user_context = f"Username: {user.username}, Name: {user.first_name}"
    classification = await classify_message(message.text, user_context)

    if classification["confidence"] < 0.5:
        kw_result = classify_by_keywords(message.text)
        if kw_result and kw_result["confidence"] > classification["confidence"]:
            classification = kw_result

    # 2. Save ticket
    async with async_session() as session:
        ticket = Ticket(
            telegram_user_id=user.id,
            telegram_username=user.username,
            telegram_chat_id=message.chat_id,
            message_text=message.text,
            message_id=message.message_id,
            category=classification["category"],
            subcategory=classification.get("subcategory"),
            confidence=classification["confidence"],
            priority=classification["priority"],
            sentiment=classification.get("sentiment"),
            status=TicketStatus.CLASSIFIED.value,
            classification_reasoning=classification.get("reasoning"),
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        ticket_id = ticket.id

    # 3. Route to department
    routing = get_routing_target(classification["category"], classification["priority"])

    if routing["should_notify"] and routing["chat_id"]:
        user_info = {"name": user.first_name or "N/A", "username": user.username or "N/A"}
        forward_text = format_routing_message(
            message.text, classification, user_info, ticket_id
        )
        bot: Bot = context.bot
        try:
            await bot.send_message(
                chat_id=routing["chat_id"],
                text=forward_text,
                parse_mode="Markdown",
            )
            async with async_session() as session:
                ticket = await session.get(Ticket, ticket_id)
                if ticket:
                    ticket.status = TicketStatus.ROUTED.value
                    ticket.routed_to_chat_id = routing["chat_id"]
                    await session.commit()
        except Exception as e:
            logger.error("routing_failed", ticket_id=ticket_id, error=str(e))

    # 4. Auto-reply
    if should_auto_respond(classification):
        auto_text = get_auto_response(classification)
        if auto_text:
            try:
                await message.reply_text(auto_text)
                async with async_session() as session:
                    ticket = await session.get(Ticket, ticket_id)
                    if ticket:
                        ticket.auto_response_sent = True
                        ticket.auto_response_text = auto_text
                        ticket.status = TicketStatus.AUTO_REPLIED.value
                        await session.commit()
                logger.info("auto_response_sent", ticket_id=ticket_id)
            except Exception as e:
                logger.error("auto_response_failed", ticket_id=ticket_id, error=str(e))
    else:
        async with async_session() as session:
            ticket = await session.get(Ticket, ticket_id)
            if ticket:
                ticket.status = TicketStatus.PENDING_HUMAN.value
                await session.commit()

    # 5. Confirmation to customer
    emoji = CATEGORY_EMOJI.get(classification["category"], "📋")
    await message.reply_text(
        f"{emoji} Your request has been received (#{ticket_id}).\n"
        f"Our team will get back to you shortly."
    )


def create_bot() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("bot_created")
    return app
