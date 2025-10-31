"""
Prompt loading and management module.

Handles loading system prompts from markdown files with template variable substitution.
"""

from .prompt_loader import load_system_prompt

__all__ = ["load_system_prompt"]
