"""Application configuration loaded from environment variables.

Secret values (agent seed phrase, Agentverse API key, etc.) are loaded
from the environment but are never printed or logged by this module.
"""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

# Load variables from a .env file if one exists (local development only).
# Missing .env is not an error; environment variables take precedence.
load_dotenv()


class Settings:
    """Configuration for the GhoomAI Agent Python service."""

    def __init__(self) -> None:
        # GhoomAI API configuration
        self.api_base_url: str = os.getenv(
            "GHOOMAI_API_BASE_URL", "https://ghoomai.netlify.app"
        )
        self.api_timeout: float = float(
            os.getenv("GHOOMAI_API_TIMEOUT", "30.0")
        )

        # Fetch.ai Agent configuration
        self.agent_seed_phrase: Optional[str] = os.getenv("AGENT_SEED_PHRASE")
        self.agent_port: int = int(os.getenv("AGENT_PORT", "8001"))
        self.agent_network: str = os.getenv("AGENT_NETWORK", "mainnet")

        # Fetch.ai Agentverse configuration (needed for registration only).
        self.agentverse_api_key: Optional[str] = os.getenv("AGENTVERSE_API_KEY")

    def validate(self) -> None:
        """Validate configuration.

        Raises:
            ValueError: If a required-but-missing setting is detected.
        """
        if self.api_timeout <= 0:
            raise ValueError("GHOOMAI_API_TIMEOUT must be a positive number")
        if self.agent_port <= 0 or self.agent_port > 65535:
            raise ValueError("AGENT_PORT must be a valid TCP port (1-65535)")
        if self.agent_network not in ("mainnet", "testnet"):
            raise ValueError("AGENT_NETWORK must be 'mainnet' or 'testnet'")

    def require_agent_credentials(self) -> None:
        """Require agent credentials for agent startup.

        Raises:
            RuntimeError: If AGENT_SEED_PHRASE is missing.
        """
        if not self.agent_seed_phrase:
            raise RuntimeError(
                "AGENT_SEED_PHRASE is required to start the Fetch.ai agent. "
                "Set it in your .env file (never commit it)."
            )


settings = Settings()
