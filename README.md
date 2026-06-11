# AI Integration — Smart Customer Inquiry System

AI-powered classification and routing system for B2B/SaaS customer inquiries via Telegram bot with real-time web dashboard.

## Features

- **AI Classification** — LLM (OpenRouter) + keyword fallback for categorizing inquiries
- **Auto-Routing** — automatic forwarding to the right department
- **Auto-Responses** — instant replies for common requests
- **Web Dashboard** — real-time ticket management for the company (password protected)
- **Operator Replies** — respond to customers directly from the dashboard
- **WebSocket** — live updates without page refresh

## Architecture

```
Customer (Telegram Bot)          Company (Web Dashboard)
        │                                │
        ▼                                ▼
  Send message                  View/Edit/Reply tickets
        │                                │
        ▼                                ▼
  AI Classification ◄──── SQLite DB ────► Operator Actions
        │                                │
        ▼                                ▼
  Auto-reply + Route             Send reply via Telegram API
```

## Project Structure

```
ai_integration/
├── src/ai_integration/       # Main package
│   ├── bot.py                # Telegram bot (customer-facing)
│   ├── api.py                # FastAPI server (company dashboard)
│   ├── config.py             # Settings (Pydantic)
│   ├── models.py             # SQLAlchemy models
│   ├── classifier.py         # LLM + keyword classification
│   ├── router.py             # Department routing
│   ├── autoresponder.py      # Auto-response templates
│   ├── analytics.py          # Statistics
│   └── main.py               # Entry point
├── frontend/
│   └── index.html            # Web dashboard (standalone, no CDN)
├── tests/                    # Test suite
├── pyproject.toml            # Project config
├── .env.example              # Environment template
└── README.md
```

## Quick Start

```bash
# Clone
git clone <repo-url>
cd ai_integration

# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your tokens

# Run
python -m ai_integration.main
```

Dashboard: http://localhost:8000 (password: `admin123`)

## Configuration

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `OPENROUTER_API_KEY` | API key from openrouter.ai |
| `DASHBOARD_PASSWORD` | Web dashboard password |
| `ROUTING_*_CHAT_ID` | Department Telegram chat IDs |

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | How it works |

## Web Dashboard

- **Login** — password authentication
- **Tickets** — filter by category/status/priority
- **Details** — click any ticket for full info
- **Reply** — respond to customers directly
- **Edit** — change category/priority/status
- **Delete** — remove tickets

## Tech Stack

- Python 3.11+ / asyncio
- python-telegram-bot — Telegram API
- OpenRouter — LLM classification (free models)
- FastAPI + uvicorn — API server
- SQLAlchemy + aiosqlite — database
- WebSocket — real-time updates
- httpx — Telegram API calls from dashboard
