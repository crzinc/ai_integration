from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Ticket


async def get_stats(
    session: AsyncSession,
    period_hours: int = 24,
) -> dict:
    """Get statistics for the specified time period."""
    since = datetime.utcnow() - timedelta(hours=period_hours)

    # Total tickets
    total_q = select(func.count(Ticket.id)).where(Ticket.created_at >= since)
    total = (await session.execute(total_q)).scalar() or 0

    # By category
    cat_q = (
        select(Ticket.category, func.count(Ticket.id))
        .where(Ticket.created_at >= since)
        .group_by(Ticket.category)
    )
    by_category = dict((await session.execute(cat_q)).all())

    # By priority
    pri_q = (
        select(Ticket.priority, func.count(Ticket.id))
        .where(Ticket.created_at >= since)
        .group_by(Ticket.priority)
    )
    by_priority = dict((await session.execute(pri_q)).all())

    # By status
    stat_q = (
        select(Ticket.status, func.count(Ticket.id))
        .where(Ticket.created_at >= since)
        .group_by(Ticket.status)
    )
    by_status = dict((await session.execute(stat_q)).all())

    # Average confidence
    avg_conf_q = select(func.avg(Ticket.confidence)).where(Ticket.created_at >= since)
    avg_confidence = (await session.execute(avg_conf_q)).scalar() or 0

    # Auto-response rate
    auto_q = (
        select(func.count(Ticket.id))
        .where(Ticket.created_at >= since)
        .where(Ticket.auto_response_sent.is_(True))
    )
    auto_responded = (await session.execute(auto_q)).scalar() or 0

    # Sentiment distribution
    sent_q = (
        select(Ticket.sentiment, func.count(Ticket.id))
        .where(Ticket.created_at >= since)
        .where(Ticket.sentiment.isnot(None))
        .group_by(Ticket.sentiment)
    )
    by_sentiment = dict((await session.execute(sent_q)).all())

    return {
        "period_hours": period_hours,
        "total_tickets": total,
        "by_category": by_category,
        "by_priority": by_priority,
        "by_status": by_status,
        "by_sentiment": by_sentiment,
        "avg_confidence": round(float(avg_confidence), 3),
        "auto_response_rate": round(auto_responded / max(total, 1), 3),
        "auto_responded_count": auto_responded,
    }


def format_stats_message(stats: dict) -> str:
    """Format stats for Telegram display."""
    lines = [
        f"\U0001f4ca **Статистика за {stats['period_hours']}ч**",
        "",
        f"\U0001f4e8 Всего обращений: **{stats['total_tickets']}**",
        f"\U0001f916 Автоответов: **{stats['auto_responded_count']}** ({stats['auto_response_rate']:.0%})",
        f"\U0001f4cf Средняя уверенность: **{stats['avg_confidence']:.0%}**",
        "",
        "\U0001f4c2 **По категориям:**",
    ]

    category_labels = {
        "sales": "\U0001f4bc Продажи",
        "support": "\U0001f6e0\ufe0f Поддержка",
        "technical": "\U0001f527 Техника",
        "billing": "\U0001f4b3 Биллинг",
        "management": "\U0001f451 Руководство",
        "spam": "\U0001f4a9 Спам",
        "unknown": "\u2753 Неизвестно",
    }

    for cat, count in stats.get("by_category", {}).items():
        label = category_labels.get(cat, cat)
        lines.append(f"  {label}: {count}")

    lines.extend(["", "\U0001f53d **По приоритету:**"])

    priority_labels = {
        "low": "\U0001f7e2 Низкий",
        "medium": "\U0001f7e1 Средний",
        "high": "\U0001f7e0 Высокий",
        "critical": "\U0001f534 Критический",
    }

    for pri, count in stats.get("by_priority", {}).items():
        label = priority_labels.get(pri, pri)
        lines.append(f"  {label}: {count}")

    if stats.get("by_sentiment"):
        lines.extend(["", "\U0001f9e0 **Настроение:**"])
        sentiment_labels = {
            "positive": "\U0001f60a Позитив",
            "neutral": "\U0001f610 Нейтрально",
            "negative": "\U0001f61e Негатив",
            "angry": "\U0001f621 Гнев",
        }
        for sent, count in stats.get("by_sentiment", {}).items():
            label = sentiment_labels.get(sent, sent)
            lines.append(f"  {label}: {count}")

    return "\n".join(lines)
