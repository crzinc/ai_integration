"""Entry point — run from project root: python main.py"""

import asyncio
import sys

from ai_integration.main import main, show_stats

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        asyncio.run(show_stats())
    else:
        asyncio.run(main())
