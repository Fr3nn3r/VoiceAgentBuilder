"""
Unit tests for prompt loader module.

Tests prompt loading and template variable substitution.
"""

import os
from datetime import datetime, timezone
from unittest.mock import mock_open, patch

import pytest

from src.prompts.prompt_loader import load_system_prompt


def test_load_system_prompt_success():
    """Test successful prompt loading with variable substitution"""
    mock_content = """
    You are Camille.
    Current time: {{ $now.setZone('UTC+1') }}
    Help patients book appointments.
    """

    expected_start = """
    You are Camille.
    Current time: 20"""  # Should start with "20" from year (2025...)

    with patch("builtins.open", mock_open(read_data=mock_content)):
        result = load_system_prompt("camille")

        # Verify template variable was replaced
        assert "{{ $now.setZone('UTC+1') }}" not in result
        assert result.startswith(expected_start)
        assert "Camille" in result


def test_load_system_prompt_timestamp_format():
    """Test that timestamp is in ISO format"""
    mock_content = "Time: {{ $now.setZone('UTC+1') }}"

    with patch("builtins.open", mock_open(read_data=mock_content)):
        result = load_system_prompt("test")

        # Extract the timestamp part (after "Time: ")
        timestamp_str = result.replace("Time: ", "").strip()

        # Verify it's parseable as ISO format
        try:
            parsed = datetime.fromisoformat(timestamp_str)
            assert parsed is not None
        except ValueError:
            pytest.fail(f"Timestamp is not valid ISO format: {timestamp_str}")


def test_load_system_prompt_file_not_found():
    """Test handling of missing prompt file"""
    with patch("builtins.open", side_effect=FileNotFoundError):
        with pytest.raises(FileNotFoundError):
            load_system_prompt("nonexistent")


def test_load_system_prompt_custom_name():
    """Test loading prompt with custom name"""
    mock_content = "Custom prompt content"

    with patch("builtins.open", mock_open(read_data=mock_content)) as mock_file:
        result = load_system_prompt("custom_agent")

        # Verify correct filename was requested
        mock_file.assert_called()
        call_args = mock_file.call_args[0][0]
        assert "custom_agent.md" in call_args
        assert result == mock_content


def test_load_system_prompt_preserves_content():
    """Test that non-template content is preserved exactly"""
    mock_content = """
    Bonjour! Je suis Camille.

    **Instructions:**
    - Be polite
    - Speak French
    - No template here
    """

    with patch("builtins.open", mock_open(read_data=mock_content)):
        result = load_system_prompt("test")

        # Verify content is preserved
        assert "Bonjour! Je suis Camille." in result
        assert "**Instructions:**" in result
        assert "Be polite" in result
        assert "Speak French" in result
