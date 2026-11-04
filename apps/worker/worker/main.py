"""Background worker entrypoint."""

import asyncio
import logging
import os
import signal
import sys
from typing import Any

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("repopilot.worker")

_running = True


def handle_shutdown(sig: int, frame: Any) -> None:
    """Handle graceful shutdown signals."""
    global _running
    logger.info("Shutdown signal received: %s. Stopping worker...", sig)
    _running = False


async def run_worker() -> None:
    """Main worker loop."""
    logger.info("RepoPilot Worker started. Listening for background jobs...")
    while _running:
        await asyncio.sleep(1)
    logger.info("Worker stopped cleanly.")


def main() -> None:
    """Worker process entrypoint."""
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
