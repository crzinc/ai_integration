from __future__ import annotations

import structlog

from .config import settings
from .models import Category, Priority

logger = structlog.get_logger()

# Category -> chat ID mapping
ROUTING_MAP: dict[str, int] = {
    Category.SALES.value: settings.routing_sales_chat_id,
    Category.SUPPORT.value: settings.routing_support_chat_id,
    Category.TECHNICAL.value: settings.routing_tech_chat_id,
    Category.BILLING.value: settings.routing_billing_chat_id,
    Category.MANAGEMENT.value: settings.routing_management_chat_id,
}


def get_routing_target(category: str, priority: str) -> dict:
    """
    Determine where to route a ticket based on category and priority.

    Returns:
        {
            "chat_id": int or None,
            "department": str,
            "should_notify": bool,
            "escalate": bool,
            "reason": str,
        }
    """
    chat_id = ROUTING_MAP.get(category)
    department = category
    should_notify = True
    escalate = False
    reason = ""

    # Critical priority always escalates to management
    if priority == Priority.CRITICAL.value:
        escalate = True
        management_chat = settings.routing_management_chat_id
        if management_chat:
            chat_id = management_chat
            department = Category.MANAGEMENT.value
            reason = "Critical priority - escalated to management"
            logger.info(
                "critical_escalation",
                original_category=category,
                escalated_to=department,
            )

    # Unknown/spam goes to admin or gets dropped
    elif category in (Category.UNKNOWN.value, Category.SPAM.value):
        should_notify = False
        reason = f"Category '{category}' - no routing"
        logger.info("unrouted_message", category=category)

    else:
        if chat_id:
            reason = f"Routed to {department} team"
        else:
            reason = f"No chat ID configured for {department}"
            should_notify = False
            logger.warning("missing_chat_id", category=category)

    return {
        "chat_id": chat_id,
        "department": department,
        "should_notify": should_notify,
        "escalate": escalate,
        "reason": reason,
    }


def format_routing_message(
    message_text: str,
    classification: dict,
    user_info: dict,
    ticket_id: int,
) -> str:
    """Format a message for forwarding to the responsible team."""
    category_emoji = {
        Category.SALES.value: "\U0001f4bc",
        Category.SUPPORT.value: "\U0001f6e0\ufe0f",
        Category.TECHNICAL.value: "\U0001f527",
        Category.BILLING.value: "\U0001f4b3",
        Category.MANAGEMENT.value: "\U0001f451",
    }

    priority_emoji = {
        Priority.LOW.value: "\U0001f7e2",
        Priority.MEDIUM.value: "\U0001f7e1",
        Priority.HIGH.value: "\U0001f7e0",
        Priority.CRITICAL.value: "\U0001f534",
    }

    emoji = category_emoji.get(classification.get("category", ""), "\U0001f4ac")
    p_emoji = priority_emoji.get(classification.get("priority", ""), "\u26aa")

    lines = [
        f"{emoji} **Новое обращение #{ticket_id}** {p_emoji}",
        "",
        f"\U0001f464 **От:** {user_info.get('name', 'N/A')} (@{user_info.get('username', 'N/A')})",
        f"\U0001f4ca **Категория:** {classification.get('category', 'N/A')}",
    ]

    if classification.get("subcategory"):
        lines.append(f"\U0001f3f7\ufe0f **Подкатегория:** {classification['subcategory']}")

    lines.extend([
        f"\U0001f53d **Приоритет:** {classification.get('priority', 'N/A')}",
        f"\U0001f9e0 **Настроение:** {classification.get('sentiment', 'N/A')}",
        f"\U0001f4cf **Уверенность:** {classification.get('confidence', 0):.0%}",
    ])

    if classification.get("reasoning"):
        lines.extend(["", f"\U0001f4a1 **Анализ:** {classification['reasoning']}"])

    lines.extend([
        "",
        "\u2501" * 30,
        "",
        message_text,
        "",
        "\u2501" * 30,
        "",
        f"\U0001f517 Ticket ID: {ticket_id}",
    ])

    return "\n".join(lines)
