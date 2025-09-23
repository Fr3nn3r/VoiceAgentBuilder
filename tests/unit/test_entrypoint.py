"""Tests for entrypoint and helper functions"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestEntrypoint:
    """Test the main entrypoint and helper functions"""

    def test_prewarm_loads_vad(self):
        """Test that prewarm function loads VAD model"""
        from n8n_agent import prewarm

        mock_proc = MagicMock()
        mock_proc.userdata = {}

        with patch('livekit.plugins.silero.VAD.load') as mock_vad_load:
            mock_vad = MagicMock()
            mock_vad_load.return_value = mock_vad

            prewarm(mock_proc)

            mock_vad_load.assert_called_once()
            assert mock_proc.userdata["vad"] == mock_vad

    @pytest.mark.asyncio
    async def test_entrypoint_requires_webhook_url(self, mock_job_context):
        """Test that entrypoint raises error without webhook URL"""
        from n8n_agent import entrypoint

        with patch.dict(os.environ, {}, clear=True):
            # Remove N8N_WEBHOOK_URL from environment
            if 'N8N_WEBHOOK_URL' in os.environ:
                del os.environ['N8N_WEBHOOK_URL']

            with pytest.raises(ValueError, match="Missing n8n webhook URL"):
                await entrypoint(mock_job_context)

    @pytest.mark.asyncio
    async def test_entrypoint_with_webhook_url(self, mock_job_context):
        """Test entrypoint with valid webhook URL"""
        mock_job_context.proc.userdata = {"vad": MagicMock()}

        with patch.dict(os.environ, {
            'N8N_WEBHOOK_URL': 'https://test.webhook.com/endpoint',
            'N8N_WEBHOOK_TOKEN': 'test_token'
        }):
            # Set the context variable directly
            from livekit.agents.job import _JobContextVar
            token = _JobContextVar.set(mock_job_context)
            try:
                from n8n_agent import entrypoint

                with patch('n8n_agent.N8nWebhookLLM') as mock_llm_class:
                    with patch('n8n_agent.AgentSession') as mock_session_class:
                        with patch('n8n_agent.Agent') as mock_agent_class:
                            with patch('livekit.plugins.deepgram.STT'):
                                with patch('livekit.plugins.cartesia.TTS'):
                                    with patch('livekit.plugins.turn_detector.multilingual.MultilingualModel'):
                                        with patch('livekit.plugins.noise_cancellation.BVC'):
                                            # Setup mocks
                                            mock_session = AsyncMock()
                                            mock_session.start = AsyncMock()
                                            mock_session.on = MagicMock()
                                            mock_session_class.return_value = mock_session

                                            mock_agent = MagicMock()
                                            mock_agent_class.return_value = mock_agent

                                            # Run entrypoint
                                            await entrypoint(mock_job_context)

                                            # Verify webhook LLM was created with correct params
                                            mock_llm_class.assert_called_once_with(
                                                webhook_url='https://test.webhook.com/endpoint',
                                                webhook_token='test_token',
                                                timeout=8.0
                                            )

                                            # Verify session was created
                                            mock_session_class.assert_called_once()

                                            # Verify session was started
                                            mock_session.start.assert_called_once()

                                            # Verify context connected
                                            mock_job_context.connect.assert_called_once()
            finally:
                _JobContextVar.reset(token)

    @pytest.mark.asyncio
    async def test_entrypoint_without_token(self, mock_job_context):
        """Test entrypoint works without webhook token"""
        mock_job_context.proc.userdata = {"vad": MagicMock()}

        with patch.dict(os.environ, {
            'N8N_WEBHOOK_URL': 'https://test.webhook.com/endpoint'
        }, clear=True):
            # Ensure N8N_WEBHOOK_TOKEN is not set
            if 'N8N_WEBHOOK_TOKEN' in os.environ:
                del os.environ['N8N_WEBHOOK_TOKEN']

            # Set the context variable directly
            from livekit.agents.job import _JobContextVar
            token = _JobContextVar.set(mock_job_context)
            try:
                from n8n_agent import entrypoint

                with patch('n8n_agent.N8nWebhookLLM') as mock_llm_class:
                    with patch('n8n_agent.AgentSession') as mock_session_class:
                        with patch('n8n_agent.Agent'):
                            with patch('livekit.plugins.deepgram.STT'):
                                with patch('livekit.plugins.cartesia.TTS'):
                                    with patch('livekit.plugins.turn_detector.multilingual.MultilingualModel'):
                                        with patch('livekit.plugins.noise_cancellation.BVC'):
                                            mock_session = AsyncMock()
                                            mock_session.start = AsyncMock()
                                            mock_session.on = MagicMock()
                                            mock_session_class.return_value = mock_session

                                            await entrypoint(mock_job_context)

                                            # Verify empty token is passed
                                            mock_llm_class.assert_called_once_with(
                                                webhook_url='https://test.webhook.com/endpoint',
                                                webhook_token='',
                                                timeout=8.0
                                            )
            finally:
                _JobContextVar.reset(token)

    @pytest.mark.asyncio
    async def test_entrypoint_registers_event_handlers(self, mock_job_context):
        """Test that entrypoint registers necessary event handlers"""
        mock_job_context.proc.userdata = {"vad": MagicMock()}

        with patch.dict(os.environ, {'N8N_WEBHOOK_URL': 'https://test.webhook.com'}):
            # Set the context variable directly
            from livekit.agents.job import _JobContextVar
            token = _JobContextVar.set(mock_job_context)
            try:
                from n8n_agent import entrypoint

                with patch('n8n_agent.N8nWebhookLLM'):
                    with patch('n8n_agent.AgentSession') as mock_session_class:
                        with patch('n8n_agent.Agent'):
                            with patch('livekit.plugins.deepgram.STT'):
                                with patch('livekit.plugins.cartesia.TTS'):
                                    with patch('livekit.plugins.turn_detector.multilingual.MultilingualModel'):
                                        with patch('livekit.plugins.noise_cancellation.BVC'):
                                            mock_session = AsyncMock()
                                            mock_session.start = AsyncMock()
                                            mock_session.on = MagicMock()
                                            mock_session_class.return_value = mock_session

                                            await entrypoint(mock_job_context)

                                            # Verify event handlers were registered
                                            calls = mock_session.on.call_args_list
                                            event_names = [call[0][0] for call in calls]

                                            assert "agent_false_interruption" in event_names
                                            assert "metrics_collected" in event_names
            finally:
                _JobContextVar.reset(token)

    @pytest.mark.asyncio
    async def test_entrypoint_sets_log_context(self, mock_job_context):
        """Test that entrypoint sets up logging context"""
        mock_job_context.proc.userdata = {"vad": MagicMock()}
        mock_job_context.room.name = "test_room_123"

        with patch.dict(os.environ, {'N8N_WEBHOOK_URL': 'https://test.webhook.com'}):
            # Set the context variable directly
            from livekit.agents.job import _JobContextVar
            token = _JobContextVar.set(mock_job_context)
            try:
                from n8n_agent import entrypoint

                with patch('n8n_agent.N8nWebhookLLM'):
                    with patch('n8n_agent.AgentSession') as mock_session_class:
                        with patch('n8n_agent.Agent'):
                            with patch('livekit.plugins.deepgram.STT'):
                                with patch('livekit.plugins.cartesia.TTS'):
                                    with patch('livekit.plugins.turn_detector.multilingual.MultilingualModel'):
                                        with patch('livekit.plugins.noise_cancellation.BVC'):
                                            mock_session = AsyncMock()
                                            mock_session.start = AsyncMock()
                                            mock_session.on = MagicMock()
                                            mock_session_class.return_value = mock_session

                                            await entrypoint(mock_job_context)

                                            # Verify log context was set
                                            assert mock_job_context.log_context_fields["room"] == "test_room_123"
            finally:
                _JobContextVar.reset(token)

    @pytest.mark.asyncio
    async def test_entrypoint_adds_shutdown_callback(self, mock_job_context):
        """Test that entrypoint adds usage logging shutdown callback"""
        mock_job_context.proc.userdata = {"vad": MagicMock()}

        with patch.dict(os.environ, {'N8N_WEBHOOK_URL': 'https://test.webhook.com'}):
            # Set the context variable directly
            from livekit.agents.job import _JobContextVar
            token = _JobContextVar.set(mock_job_context)
            try:
                from n8n_agent import entrypoint

                with patch('n8n_agent.N8nWebhookLLM'):
                    with patch('n8n_agent.AgentSession') as mock_session_class:
                        with patch('n8n_agent.Agent'):
                            with patch('livekit.plugins.deepgram.STT'):
                                with patch('livekit.plugins.cartesia.TTS'):
                                    with patch('livekit.plugins.turn_detector.multilingual.MultilingualModel'):
                                        with patch('livekit.plugins.noise_cancellation.BVC'):
                                            mock_session = AsyncMock()
                                            mock_session.start = AsyncMock()
                                            mock_session.on = MagicMock()
                                            mock_session_class.return_value = mock_session

                                            await entrypoint(mock_job_context)

                                            # Verify shutdown callback was added
                                            mock_job_context.add_shutdown_callback.assert_called_once()
                                            callback = mock_job_context.add_shutdown_callback.call_args[0][0]
                                            assert callable(callback)
            finally:
                _JobContextVar.reset(token)