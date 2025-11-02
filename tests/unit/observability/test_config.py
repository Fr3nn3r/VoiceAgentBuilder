"""
Unit tests for observability configuration.

Tests environment variable loading, validation, and error handling.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from src.observability.config import ObservabilityConfig


class TestObservabilityConfig:
    """Test ObservabilityConfig loading and validation"""

    def test_disabled_by_default(self):
        """Observability should be disabled by default for safety"""
        with patch.dict(os.environ, {}, clear=True):
            config = ObservabilityConfig.from_env()
            assert config.enabled is False
            assert config.environment == "dev"
            assert config.langsmith_api_key == ""
            assert config.langsmith_project == ""

    def test_explicit_disable(self):
        """Explicit OBSERVABILITY_ENABLED=false should work"""
        with patch.dict(
            os.environ, {"OBSERVABILITY_ENABLED": "false"}, clear=True
        ):
            config = ObservabilityConfig.from_env()
            assert config.enabled is False

    def test_enabled_with_all_credentials(self):
        """Enabling requires all credentials"""
        env_vars = {
            "OBSERVABILITY_ENABLED": "true",
            "ENVIRONMENT": "dev",
            "LANGSMITH_API_KEY": "lsv2_test_key",
            "LANGSMITH_PROJECT": "medical-voice-agent-dev",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ObservabilityConfig.from_env()
            assert config.enabled is True
            assert config.environment == "dev"
            assert config.langsmith_api_key == "lsv2_test_key"
            assert config.langsmith_project == "medical-voice-agent-dev"

    def test_enabled_missing_environment(self):
        """Enabling without ENVIRONMENT should raise error"""
        env_vars = {
            "OBSERVABILITY_ENABLED": "true",
            "LANGSMITH_API_KEY": "lsv2_test_key",
            "LANGSMITH_PROJECT": "test-project",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="ENVIRONMENT must be"):
                ObservabilityConfig.from_env()

    def test_enabled_invalid_environment(self):
        """ENVIRONMENT must be 'dev' or 'prod'"""
        env_vars = {
            "OBSERVABILITY_ENABLED": "true",
            "ENVIRONMENT": "staging",  # Invalid
            "LANGSMITH_API_KEY": "lsv2_test_key",
            "LANGSMITH_PROJECT": "test-project",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="ENVIRONMENT must be"):
                ObservabilityConfig.from_env()

    def test_enabled_missing_api_key(self):
        """Enabling without LANGSMITH_API_KEY should raise error"""
        env_vars = {
            "OBSERVABILITY_ENABLED": "true",
            "ENVIRONMENT": "dev",
            "LANGSMITH_PROJECT": "test-project",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="LANGSMITH_API_KEY"):
                ObservabilityConfig.from_env()

    def test_enabled_missing_project(self):
        """Enabling without LANGSMITH_PROJECT should raise error"""
        env_vars = {
            "OBSERVABILITY_ENABLED": "true",
            "ENVIRONMENT": "dev",
            "LANGSMITH_API_KEY": "lsv2_test_key",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="LANGSMITH_PROJECT"):
                ObservabilityConfig.from_env()

    def test_boolean_parsing_variants(self):
        """Test various boolean value formats"""
        variants = ["true", "True", "TRUE", "1", "yes"]
        for value in variants:
            env_vars = {
                "OBSERVABILITY_ENABLED": value,
                "ENVIRONMENT": "dev",
                "LANGSMITH_API_KEY": "test",
                "LANGSMITH_PROJECT": "test",
            }
            with patch.dict(os.environ, env_vars, clear=True):
                config = ObservabilityConfig.from_env()
                assert config.enabled is True

    def test_production_environment(self):
        """Test production environment configuration"""
        env_vars = {
            "OBSERVABILITY_ENABLED": "true",
            "ENVIRONMENT": "prod",
            "LANGSMITH_API_KEY": "lsv2_prod_key",
            "LANGSMITH_PROJECT": "medical-voice-agent-prod",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ObservabilityConfig.from_env()
            assert config.enabled is True
            assert config.environment == "prod"
            assert config.is_production() is True
            assert config.is_development() is False

    def test_development_environment(self):
        """Test development environment configuration"""
        env_vars = {
            "OBSERVABILITY_ENABLED": "true",
            "ENVIRONMENT": "dev",
            "LANGSMITH_API_KEY": "lsv2_dev_key",
            "LANGSMITH_PROJECT": "medical-voice-agent-dev",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ObservabilityConfig.from_env()
            assert config.is_production() is False
            assert config.is_development() is True

    def test_disabled_config_not_production_or_dev(self):
        """Disabled config should return False for both checks"""
        with patch.dict(os.environ, {}, clear=True):
            config = ObservabilityConfig.from_env()
            assert config.is_production() is False
            assert config.is_development() is False
