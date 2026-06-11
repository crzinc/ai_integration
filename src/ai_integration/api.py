"""FastAPI server for company dashboard — ticket management, operator replies, auth."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import structlog
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from .config import settings
from .models import Ticket, TicketStatus, async_session

logger = structlog.get_logger()

app = FastAPI(title="Support Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth ---

_active_tokens: dict[str, datetime] = {}


def verify_token(token: str | None = None) -> bool:
    if not token:
        return False
    exp = _active_tokens.get(token)
    if not exp:
        return False
    if datetime.utcnow() > exp:
        _active_tokens.pop(token, None)
        return False
    return True


def require_auth(token: str | None = None) -> None:
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")


# --- WebSocket manager ---

class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def broadcast(self, data: dict) -> None:
        message = json.dumps(data, default=str)
        disconnected: list[WebSocket] = []
        for conn in self.active_connections:
            try:
                await conn.send_text(message)
            except Exception:
                disconnected.append(conn)
        for c in disconnected:
            self.disconnect(c)


manager = ConnectionManager()


# --- API Models ---

class TicketResponse(BaseModel):
    id: int
    telegram_user_id: int
    telegram_username: str | None
    message_text: str
    category: str
    subcategory: str | None
    confidence: float
    priority: str
    sentiment: str | None
    status: str
    auto_response_sent: bool
    auto_response_text: str | None
    operator_reply: str | None
    classification_reasoning: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    total_tickets: int
    by_category: dict[str, int]
    by_priority: dict[str, int]
    by_status: dict[str, int]
    by_sentiment: dict[str, int]
    avg_confidence: float
    auto_response_rate: float
    auto_responded_count: int


class LoginRequest(BaseModel):
    password: str


class ReplyRequest(BaseModel):
    text: str


class TicketEditRequest(BaseModel):
    category: str | None = None
    priority: str | None = None
    status: str | None = None
    message_text: str | None = None


# --- Auth routes ---

@app.post("/api/login")
async def login(body: LoginRequest) -> dict:
    if not secrets.compare_digest(body.password, settings.dashboard_password):
        raise HTTPException(status_code=401, detail="Wrong password")
    token = secrets.token_urlsafe(32)
    _active_tokens[token] = datetime.utcnow() + timedelta(hours=24)
    return {"token": token}


@app.get("/api/verify")
async def verify(token: str = "") -> dict:
    return {"ok": verify_token(token)}


# --- Protected routes ---

@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    index_path = Path(__file__).parent / "frontend" / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Dashboard not found</h1>")


@app.get("/api/tickets")
async def get_tickets(
    token: str = "",
    limit: int = 50,
    offset: int = 0,
    category: str | None = None,
    status: str | None = None,
    priority: str | None = None,
) -> list[TicketResponse]:
    require_auth(token)
    async with async_session() as session:
        query = select(Ticket).order_by(Ticket.created_at.desc())
        if category:
            query = query.where(Ticket.category == category)
        if status:
            query = query.where(Ticket.status == status)
        if priority:
            query = query.where(Ticket.priority == priority)
        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        return [TicketResponse.model_validate(t) for t in result.scalars().all()]


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int, token: str = "") -> TicketResponse | dict:
    require_auth(token)
    async with async_session() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            return {"error": "Ticket not found"}
        return TicketResponse.model_validate(ticket)


@app.get("/api/stats")
async def get_stats(token: str = "", period_hours: int = 24) -> StatsResponse:
    require_auth(token)
    async with async_session() as session:
        since = datetime.utcnow() - timedelta(hours=period_hours)

        total = (await session.execute(
            select(func.count(Ticket.id)).where(Ticket.created_at >= since)
        )).scalar() or 0

        by_category = dict((await session.execute(
            select(Ticket.category, func.count(Ticket.id))
            .where(Ticket.created_at >= since).group_by(Ticket.category)
        )).all())

        by_priority = dict((await session.execute(
            select(Ticket.priority, func.count(Ticket.id))
            .where(Ticket.created_at >= since).group_by(Ticket.priority)
        )).all())

        by_status = dict((await session.execute(
            select(Ticket.status, func.count(Ticket.id))
            .where(Ticket.created_at >= since).group_by(Ticket.status)
        )).all())

        by_sentiment = dict((await session.execute(
            select(Ticket.sentiment, func.count(Ticket.id))
            .where(Ticket.created_at >= since)
            .where(Ticket.sentiment.isnot(None))
            .group_by(Ticket.sentiment)
        )).all())

        avg_conf = (await session.execute(
            select(func.avg(Ticket.confidence)).where(Ticket.created_at >= since)
        )).scalar() or 0

        auto_count = (await session.execute(
            select(func.count(Ticket.id))
            .where(Ticket.created_at >= since)
            .where(Ticket.auto_response_sent.is_(True))
        )).scalar() or 0

        return StatsResponse(
            total_tickets=total,
            by_category=by_category,
            by_priority=by_priority,
            by_status=by_status,
            by_sentiment=by_sentiment,
            avg_confidence=round(float(avg_conf), 3),
            auto_response_rate=round(auto_count / max(total, 1), 3),
            auto_responded_count=auto_count,
        )


@app.get("/api/tickets/{ticket_id}/timeline")
async def get_ticket_timeline(ticket_id: int, token: str = "") -> list[dict]:
    require_auth(token)
    async with async_session() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            return []
        events = [
            {"time": str(ticket.created_at), "event": "created", "details": "Ticket created"},
            {"time": str(ticket.created_at), "event": "classified",
             "details": f"Category: {ticket.category}, Priority: {ticket.priority}"},
        ]
        if ticket.auto_response_sent:
            events.append({"time": str(ticket.updated_at), "event": "auto_replied",
                           "details": "Auto-response sent"})
        if ticket.status in (TicketStatus.ROUTED.value, TicketStatus.AUTO_REPLIED.value):
            events.append({"time": str(ticket.updated_at), "event": "routed",
                           "details": f"Status: {ticket.status}"})
        if ticket.operator_reply:
            events.append({"time": str(ticket.operator_replied_at or ticket.updated_at),
                           "event": "operator_reply", "details": ticket.operator_reply[:100]})
        return events


@app.put("/api/tickets/{ticket_id}")
async def update_ticket(
    ticket_id: int, body: TicketEditRequest, token: str = ""
) -> TicketResponse | dict:
    require_auth(token)
    async with async_session() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            return {"error": "Ticket not found"}
        if body.category is not None:
            ticket.category = body.category
        if body.priority is not None:
            ticket.priority = body.priority
        if body.status is not None:
            ticket.status = body.status
        if body.message_text is not None:
            ticket.message_text = body.message_text
        await session.commit()
        await session.refresh(ticket)
        await broadcast_ticket_update(ticket)
        return TicketResponse.model_validate(ticket)


@app.delete("/api/tickets/{ticket_id}")
async def delete_ticket(ticket_id: int, token: str = "") -> dict:
    require_auth(token)
    async with async_session() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            return {"error": "Ticket not found"}
        await session.delete(ticket)
        await session.commit()
        await manager.broadcast({"event": "ticket_deleted", "ticket_id": ticket_id})
        return {"ok": True, "deleted_id": ticket_id}


@app.post("/api/tickets/{ticket_id}/reply")
async def reply_to_ticket(ticket_id: int, body: ReplyRequest, token: str = "") -> dict:
    require_auth(token)
    async with async_session() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            return {"error": "Ticket not found"}

        # Send message to customer via Telegram
        tg_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient() as client:
                await client.post(tg_url, json={
                    "chat_id": ticket.telegram_chat_id,
                    "text": f"💬 Reply to your request #{ticket_id}:\n\n{body.text}",
                })
        except Exception as e:
            logger.error("reply_send_failed", ticket_id=ticket_id, error=str(e))
            return {"error": f"Failed to send: {e}"}

        # Update ticket
        ticket.operator_reply = body.text
        ticket.operator_replied_at = datetime.utcnow()
        ticket.status = TicketStatus.RESOLVED.value
        await session.commit()
        await session.refresh(ticket)

        await broadcast_ticket_update(ticket)
        return {"ok": True, "ticket_id": ticket_id}


# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# --- Broadcast helpers ---

async def broadcast_ticket(ticket: Ticket) -> None:
    ticket_data = TicketResponse.model_validate(ticket).model_dump()
    await manager.broadcast({"event": "new_ticket", "ticket": ticket_data})


async def broadcast_ticket_update(ticket: Ticket) -> None:
    ticket_data = TicketResponse.model_validate(ticket).model_dump()
    await manager.broadcast({"event": "ticket_updated", "ticket": ticket_data})
