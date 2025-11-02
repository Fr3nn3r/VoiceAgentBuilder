"""
Observability configuration from environment variables.

Follows Single Responsibility Principle: only handles config loading and validation.
"""

import os
from dataclasses import dataclass
from typing import Literal

Environment = Literal["dev", "prod"]


@dataclass
class ObservabilityConfig:
    """
    Configuration for LangSmith observability.

    Attributes:
        enabled: Whether observability is active (default: False for safety)
        environment: Deployment environment (dev or prod)
        langsmith_api_key: LangSmith API key for authentication
        langsmith_project: LangSmith project name for trace organization
    """

    enabled: bool
    environment: Environment
    langsmith_api_key: str
    langsmith_project: str

    @classmethod
    def from_env(cls) -> "ObservabilityConfig":
        """
        Load configuration from environment variables.

        Environment variables:
            OBSERVABILITY_ENABLED: "true" or "false" (default: false)
            ENVIRONMENT: "dev" or "prod" (required if enabled)
            LANGSMITH_API_KEY: LangSmith API key (required if enabled)
            LANGSMITH_PROJECT: LangSmith project name (required if enabled)

        Returns:
            ObservabilityConfig instance

        Raises:
            ValueError: If enabled but required credentials are missing
            ValueError: If environment is not "dev" or "prod"
        """
        enabled = os.getenv("OBSERVABILITY_ENABLED", "false").lower() in (
            "true",
            "1",
            "yes",
        )

        # If disabled, return minimal config (values won't be used)
        if not enabled:
            return cls(
                enabled=False,
                environment="dev",
                langsmith_api_key="",
                langsmith_project="",
            )

        # If enabled, validate all required fields
        environment = os.getenv("ENVIRONMENT", "").lower()
        if environment not in ("dev", "prod"):
            raise ValueError(
                f"ENVIRONMENT must be 'dev' or 'prod', got: '{environment}'"
            )

        langsmith_api_key = os.getenv("LANGSMITH_API_KEY", "")
        if not langsmith_api_key:
            raise ValueError(
                "LANGSMITH_API_KEY must be set when OBSERVABILITY_ENABLED=true"
            )

        langsmith_project = os.getenv("LANGSMITH_PROJECT", "")
        if not langsmith_project:
            raise ValueError(
                "LANGSMITH_PROJECT must be set when OBSERVABILITY_ENABLED=true"
            )

        return cls(
            enabled=True,
            environment=environment,  # type: ignore
            langsmith_api_key=langsmith_api_key,
            langsmith_project=langsmith_project,
        )

    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.enabled and self.environment == "prod"

    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.enabled and self.environment == "dev"
