"""
Unit tests for trace context propagation.

Tests async-safe context management using contextvars.
"""

import asyncio
import sys
from pathlib import Path

import pytest

from src.observability.context import (
    add_session_end_timestamp,
    clear_trace_context,
    get_trace_id,
    get_trace_metadata,
    set_trace_id,
    set_trace_metadata,
)


class TestTraceContext:
    """Test trace context propagation using contextvars"""

    def setup_method(self):
        """Clear context before each test"""
        clear_trace_context()

    def teardown_method(self):
        """Clear context after each test"""
        clear_trace_context()

    def test_set_and_get_trace_id(self):
        """Should set and retrieve trace ID"""
        trace_id = set_trace_id("test-trace-123")
        assert trace_id == "test-trace-123"
        assert get_trace_id() == "test-trace-123"

    def test_auto_generate_trace_id(self):
        """Should auto-generate UUID if not provided"""
        trace_id = set_trace_id()
        assert trace_id is not None
        assert len(trace_id) == 36  # UUID format
        assert get_trace_id() == trace_id

    def test_get_trace_id_before_set(self):
        """Should return None if trace ID not set"""
        assert get_trace_id() is None

    def test_set_trace_metadata(self):
        """Should store custom metadata in context"""
        set_trace_id("test-123")
        set_trace_metadata("room_id", "room_abc")
        set_trace_metadata("participant_id", "p_456")

        metadata = get_trace_metadata()
        assert metadata["room_id"] == "room_abc"
        assert metadata["participant_id"] == "p_456"
        assert metadata["trace_id"] == "test-123"

    def test_get_trace_metadata_includes_timestamps(self):
        """Metadata should include start timestamp after set_trace_id"""
        set_trace_id()
        metadata = get_trace_metadata()
        assert "timestamp_start" in metadata
        assert "T" in metadata["timestamp_start"]  # ISO format

    def test_add_session_end_timestamp(self):
        """Should add end timestamp to context"""
        set_trace_id()
        add_session_end_timestamp()

        metadata = get_trace_metadata()
        assert "timestamp_end" in metadata
        assert "T" in metadata["timestamp_end"]  # ISO format

    def test_clear_trace_context(self):
        """Should clear all context data"""
        set_trace_id("test-123")
        set_trace_metadata("key", "value")

        clear_trace_context()

        assert get_trace_id() is None
        metadata = get_trace_metadata()
        assert len(metadata) == 0

    def test_metadata_immutability(self):
        """Getting metadata should return copy, not reference"""
        set_trace_id("test-123")
        metadata1 = get_trace_metadata()
        metadata1["external_change"] = "should not affect context"

        metadata2 = get_trace_metadata()
        assert "external_change" not in metadata2

    async def test_async_context_isolation(self):
        """Each async task should have isolated context"""

        async def task_a():
            set_trace_id("trace-a")
            await asyncio.sleep(0.01)
            return get_trace_id()

        async def task_b():
            set_trace_id("trace-b")
            await asyncio.sleep(0.01)
            return get_trace_id()

        # Run tasks concurrently
        results = await asyncio.gather(task_a(), task_b())

        # Each task should see its own trace ID
        assert "trace-a" in results
        assert "trace-b" in results

    async def test_async_metadata_isolation(self):
        """Metadata should be isolated across async tasks"""

        async def task_with_metadata(task_id):
            set_trace_id(f"trace-{task_id}")
            set_trace_metadata("task_id", task_id)
            await asyncio.sleep(0.01)
            metadata = get_trace_metadata()
            return metadata["task_id"]

        # Run multiple tasks concurrently
        results = await asyncio.gather(
            task_with_metadata(1),
            task_with_metadata(2),
            task_with_metadata(3),
        )

        # Each should have its own task_id
        assert results == [1, 2, 3]

    def test_set_metadata_creates_copy(self):
        """Setting metadata should not mutate existing context"""
        set_trace_id("test-123")

        # Get initial metadata
        initial = get_trace_metadata()
        initial_keys = set(initial.keys())

        # Add new metadata
        set_trace_metadata("new_key", "new_value")

        # New metadata should exist
        updated = get_trace_metadata()
        assert "new_key" in updated
        assert updated["new_key"] == "new_value"

        # Old metadata should still exist
        for key in initial_keys:
            assert key in updated
