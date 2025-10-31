"""
System prompt loader with template variable substitution.

Loads prompts from markdown files and replaces template placeholders
with dynamic values (e.g., current timestamp).
"""

import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("prompts.prompt_loader")


def load_system_prompt(prompt_name: str = "camille") -> str:
    """
    Load system prompt from markdown file with variable substitution.

    Args:
        prompt_name: Name of the prompt file (without .md extension)

    Returns:
        Prompt content with all template variables replaced

    Raises:
        FileNotFoundError: If prompt file doesn't exist

    Example:
        >>> prompt = load_system_prompt("camille")
        >>> "Bonjour" in prompt
        True
    """
    # Build path to prompts directory (voice-agent/prompts/)
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "prompts",
        f"{prompt_name}.md",
    )

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read()

            # Replace timestamp placeholder with current UTC+1 time
            now_utc_plus_1 = datetime.now(timezone.utc) + timedelta(hours=1)
            content = content.replace(
                "{{ $now.setZone('UTC+1') }}", now_utc_plus_1.isoformat()
            )

            logger.info(f"[Prompts] Loaded system prompt: {prompt_name}.md")
            return content

    except FileNotFoundError:
        logger.error(f"[Prompts] Prompt file not found: {prompt_path}")
        raise
