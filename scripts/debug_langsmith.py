"""
Debug script to see actual LangSmith API errors.

This enables verbose logging to see what's failing.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Enable DEBUG logging for observability module
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(name)s: %(message)s'
)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(override=True)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from observability import ObservabilityTracer, set_trace_id


async def main():
    """Test with full error visibility"""

    print("\n" + "="*60)
    print("LANGSMITH DEBUG TEST - Full Error Visibility")
    print("="*60 + "\n")

    # Create tracer
    print("[1] Creating tracer from environment...")
    tracer = ObservabilityTracer.from_env()

    print(f"    - Enabled: {tracer.config.enabled}")
    print(f"    - Environment: {tracer.config.environment}")
    print(f"    - Project: {tracer.config.langsmith_project}")
    print(f"    - API Key: {tracer.config.langsmith_api_key[:20]}... (truncated)")
    print(f"    - Client initialized: {tracer.client is not None}")
    print()

    if not tracer.config.enabled:
        print("[ERROR] Observability disabled - check env vars")
        return 1

    if not tracer.client:
        print("[ERROR] LangSmith client failed to initialize - check API key")
        return 1

    # Set trace context
    print("[2] Setting trace context...")
    trace_id = set_trace_id()
    print(f"    - Trace ID: {trace_id}")
    print()

    # Start session
    print("[3] Starting session (this will call LangSmith API)...")
    try:
        await tracer.start_session(
            room_id="debug_test_room",
            participant_id="debug_participant",
            agent_name="Camille",
            debug_mode=True
        )
        print("    - Session started successfully")
        print(f"    - Session run: {tracer.session_run}")
    except Exception as e:
        print(f"    - [ERROR] Exception during start_session: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Wait for async post
    print("\n[4] Waiting for async post to complete...")
    await asyncio.sleep(2.0)
    print("    - Wait complete")
    print()

    # End session
    print("[5] Ending session...")
    try:
        await tracer.end_session(debug_test=True)
        print("    - Session ended successfully")
    except Exception as e:
        print(f"    - [ERROR] Exception during end_session: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Final wait
    print("\n[6] Waiting for final async posts...")
    await asyncio.sleep(2.0)
    print("    - Wait complete")
    print()

    # Cleanup
    print("[7] Closing tracer...")
    await tracer.close()
    print("    - Tracer closed")
    print()

    print("="*60)
    print("TEST COMPLETE - Check logs above for any errors")
    print("="*60)
    print()
    print(f"If no errors above, check LangSmith for trace: {trace_id}")
    print(f"Project: {tracer.config.langsmith_project}")
    print()

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n[FATAL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
