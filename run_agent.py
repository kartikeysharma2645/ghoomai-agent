r"""Local startup entry point for the GhoomAI Fetch.ai agent.

This script constructs and runs the GhoomAI agent in mailbox mode. The agent
connects to Agentverse via a secure mailbox channel and does not require a
publicly reachable HTTP endpoint.

Usage (Windows PowerShell):

    .venv\Scripts\python.exe run_agent.py

Prerequisites:
  * Set ``AGENT_SEED_PHRASE`` in a local ``.env`` file (never commit it).
  * Install dependencies: ``.\.venv\Scripts\python.exe -m pip install -r requirements.txt``

The separate FastAPI health service (``GET /status`` on port 8000) is not
started by this script and remains independently runnable via:

    .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

from app.agent import create_agent

logger = logging.getLogger(__name__)


def main() -> int:
    """Load environment, construct the agent, and start the runtime.

    Returns:
        0 on clean shutdown, 1 on configuration error.
    """
    load_dotenv()

    try:
        agent = create_agent()
    except RuntimeError as exc:
        # Do not print the seed phrase or any secret information.
        logger.error(str(exc))
        return 1

    agent.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
