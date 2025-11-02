"""
Integration test for LangSmith observability - Week 1 "Hello World" trace.

This script verifies that we can successfully send a trace to LangSmith.

Setup:
1. Create LangSmith account at https://smith.langchain.com
2. Get API key from Settings -> API Keys
3. Create project: medical-voice-agent-dev
4. Set environment variables:
   - OBSERVABILITY_ENABLED=true
   - ENVIRONMENT=dev
   - LANGSMITH_API_KEY=lsv2_pt_...
   - LANGSMITH_PROJECT=medical-voice-agent-dev

Run:
    python scripts/test_observability_hello_world.py

Expected output:
    [OK] Config loaded successfully
    [OK] Trace ID: <uuid>
    [OK] Session started
    [OK] Session ended
    [OK] Check LangSmith UI for trace: https://smith.langchain.com/...

Exit codes:
    0 - Success (trace sent successfully)
    1 - Configuration error
    2 - LangSmith API error
"""

import asyncio
import sys
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(override=True)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from observability import ObservabilityTracer, set_trace_id, set_trace_metadata


async def main():
    """Send hello-world trace to LangSmith"""

    print("[INFO] LangSmith Observability - Hello World Test")
    print("[INFO] " + "=" * 50)

    # Step 1: Load configuration
    print("[INFO] Loading configuration from environment...")
    tracer = ObservabilityTracer.from_env()

    if not tracer.config.enabled:
        print("[ERROR] Observability is DISABLED")
        print("[ERROR] Please set environment variables:")
        print("[ERROR]   OBSERVABILITY_ENABLED=true")
        print("[ERROR]   ENVIRONMENT=dev")
        print("[ERROR]   LANGSMITH_API_KEY=lsv2_pt_...")
        print("[ERROR]   LANGSMITH_PROJECT=medical-voice-agent-dev")
        return 1

    print(f"[OK] Config loaded successfully")
    print(f"[OK] Environment: {tracer.config.environment}")
    print(f"[OK] Project: {tracer.config.langsmith_project}")
    print()

    # Step 2: Create trace context
    print("[INFO] Creating trace context...")
    trace_id = set_trace_id()
    set_trace_metadata("test_type", "hello_world")
    set_trace_metadata("test_timestamp", "2025-11-01T00:00:00Z")
    print(f"[OK] Trace ID: {trace_id}")
    print()

    # Step 3: Start session
    print("[INFO] Starting session trace...")
    try:
        await tracer.start_session(
            room_id="test_room_hello_world",
            participant_id="test_participant_001",
            agent_name="Camille",
            test_mode=True,
        )
        print("[OK] Session started")
    except Exception as e:
        print(f"[ERROR] Failed to start session: {e}")
        return 2

    # Give async tasks time to post
    await asyncio.sleep(1.0)
    print()

    # Step 4: Create a test tool span
    print("[INFO] Creating test tool span...")
    try:
        async with tracer.tool_span(
            "tool.hello_world",
            {"message": "Hello from observability test!", "test": True},
        ):
            # Simulate tool execution
            await asyncio.sleep(0.1)
        print("[OK] Tool span created")
    except Exception as e:
        print(f"[ERROR] Failed to create tool span: {e}")
        return 2

    # Give async tasks time to post
    await asyncio.sleep(1.0)
    print()

    # Step 5: End session
    print("[INFO] Ending session trace...")
    try:
        await tracer.end_session(
            test_result="success",
            total_test_turns=1,
        )
        print("[OK] Session ended")
    except Exception as e:
        print(f"[ERROR] Failed to end session: {e}")
        return 2

    # Give async tasks time to complete
    await asyncio.sleep(2.0)
    print()

    # Step 6: Cleanup
    print("[INFO] Cleaning up...")
    await tracer.close()
    print("[OK] Tracer closed")
    print()

    # Success message
    print("[SUCCESS] " + "=" * 50)
    print("[SUCCESS] Trace sent successfully!")
    print()
    print("[INFO] Next steps:")
    print(f"[INFO] 1. Visit https://smith.langchain.com/")
    print(f"[INFO] 2. Open project: {tracer.config.langsmith_project}")
    print(f"[INFO] 3. Find trace with ID: {trace_id}")
    print("[INFO] 4. Verify trace contains:")
    print("[INFO]    - Session start/end events")
    print("[INFO]    - Tool span: tool.hello_world")
    print("[INFO]    - Metadata: test_type, room_id, participant_id")
    print()

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[INFO] Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n[FATAL] Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(3)
