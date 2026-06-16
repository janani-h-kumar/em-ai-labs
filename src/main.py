"""
Enterprise agent manager with runtime orchestration and tooling.
"""

import asyncio
import logging
import time

from src.agent_manager import AgentManager
from src.utils.logging_utils import setup_structured_logging

# Setup structured logging — must happen before any logger.getLogger() calls
setup_structured_logging()
logger = logging.getLogger(__name__)


async def run_interactive_chat():
    """Run interactive chat loop with agent system."""
    print("\n" + "=" * 50)
    print("AI Lab — Agent Orchestration System")
    print("=" * 50)
    print("Type 'exit' to quit, 'health' for status\n")

    try:
        startup_start = time.perf_counter()
        manager = AgentManager()
        logger.info(
            "Application startup complete",
            extra={"startup_duration_sec": round(time.perf_counter() - startup_start, 2)},
        )
    except Exception as e:
        print(f"Failed to initialise: {e}")
        return

    while True:
        try:
            msg = input("You: ").strip()

            if not msg:
                continue
            if msg.lower() in ("exit", "quit"):
                print("\nGoodbye!\n")
                break
            if msg.lower() == "help":
                print("\nCommands: exit/quit, health, or ask a question\n")
                continue
            if msg.lower() == "health":
                # FIX: health_check() is async — must be awaited
                status = await manager.health_check()
                print(f"\nSystem Health: {status}\n")
                continue

            response = await manager.handle(msg)
            print(f"\nAssistant: {response}\n")

        except KeyboardInterrupt:
            print("\n\nGoodbye!\n")
            break
        except Exception as e:
            logger.error("Unexpected error: %s", e)
            print(f"Error: {e}\n")


if __name__ == "__main__":
    asyncio.run(run_interactive_chat())
