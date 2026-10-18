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

        # Fetch.ai Agentverse configuration (optional at startup).
        # The health endpoint does not require these values.
        self.agent_seed_phrase: Optional[str] = os.getenv("AGENT_SEED_PHRASE")
        self.agentverse_api_key: Optional[str] = os.getenv("AGENTVERSE_API_KEY")

    def validate(self) -> None:
        """Validate configuration.

        Raises:
            ValueError: If a required-but-missing setting is detected.
        """
        if self.api_timeout <= 0:
            raise ValueError("GHOOMAI_API_TIMEOUT must be a positive number")


settings = Settings()
