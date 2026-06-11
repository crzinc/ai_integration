"""AI Integration - Smart B2B/SaaS Customer Inquiry Classifier & Router.

Usage:
    python main.py              # Run Telegram bot + API server
    python main.py --stats      # Show current statistics
    python main.py --port 8000  # Custom port for API server
"""

from __future__ import annotations

import asyncio
import sys
from multiprocessing import Process

import structlog
import uvicorn

from .analytics import format_stats_message, get_stats
from .api import app  # noqa: E402
from .bot import create_bot
from .config import settings
from .models import async_session, init_db

logger = structlog.get_logger()


def run_api_server(port: int = 8000) -> None:
    """Run the FastAPI server in a separate process."""
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


async def run_bot() -> None:
    """Run the Telegram bot."""
    app = create_bot()
    logger.info("bot_starting")

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    logger.info("bot_running")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("bot_shutting_down")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


async def main() -> None:
    """Entry point - runs both bot and API server."""
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(__import__("logging"), settings.log_level.upper())
        ),
    )

    logger.info("starting_system", log_level=settings.log_level)

    # Initialize database
    await init_db()
    logger.info("database_initialized")

    # Parse port from args
    port = 8000
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    # Start API server in a separate process
    api_process = Process(target=run_api_server, args=(port,), daemon=True)
    api_process.start()
    logger.info("api_server_started", port=port)

    # Run bot in main process
    await run_bot()


async def show_stats() -> None:
    """Show current statistics."""
    await init_db()
    async with async_session() as session:
        stats = await get_stats(session, period_hours=24)
    print(format_stats_message(stats))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        asyncio.run(show_stats())
    else:
        asyncio.run(main())
