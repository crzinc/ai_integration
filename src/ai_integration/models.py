from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Category(str, enum.Enum):
    SALES = "sales"
    SUPPORT = "support"
    TECHNICAL = "technical"
    BILLING = "billing"
    MANAGEMENT = "management"
    SPAM = "spam"
    UNKNOWN = "unknown"


class Priority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(str, enum.Enum):
    NEW = "new"
    CLASSIFIED = "classified"
    ROUTED = "routed"
    AUTO_REPLIED = "auto_replied"
    PENDING_HUMAN = "pending_human"
    RESOLVED = "resolved"


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255))
    telegram_chat_id: Mapped[int] = mapped_column(index=True)
    message_text: Mapped[str] = mapped_column(Text)
    message_id: Mapped[int] = mapped_column(index=True)

    category: Mapped[str] = mapped_column(String(50), default=Category.UNKNOWN.value)
    subcategory: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    priority: Mapped[str] = mapped_column(String(20), default=Priority.MEDIUM.value)
    sentiment: Mapped[str | None] = mapped_column(String(20))

    status: Mapped[str] = mapped_column(String(30), default=TicketStatus.NEW.value)
    routed_to_chat_id: Mapped[int | None] = mapped_column()
    auto_response_sent: Mapped[bool] = mapped_column(default=False)
    auto_response_text: Mapped[str | None] = mapped_column(Text)
    operator_reply: Mapped[str | None] = mapped_column(Text)
    operator_replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    classification_reasoning: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
