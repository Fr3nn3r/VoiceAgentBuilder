"""
Test script for conversation persistence implementation.
Tests both test mode (local JSON) and N8N mode (without actually calling webhooks).
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from persistence import ConversationData, create_persistence
from persistence.conversation_recorder import ConversationRecorder


async def test_conversation_recorder():
    """Test the conversation recorder"""
    print("\n[OK] Testing ConversationRecorder...")

    recorder = ConversationRecorder(voice_agent_name="Camille")

    # Simulate conversation
    recorder.add_agent_message(
        "Bonjour, cabinet du docteur Fillion, Camille à l'appareil."
    )
    recorder.add_user_message("Bonjour, je voudrais prendre rendez-vous.")
    recorder.add_agent_message("Bien sûr! Quel est votre nom complet?")
    recorder.add_user_message("Jean Dupont.")
    recorder.add_agent_message("Merci Jean. Quel est votre numéro de téléphone?")
    recorder.add_user_message("C'est le 01 23 45 67 89.")

    # Set patient info
    recorder.set_patient_info(
        patient_name="Jean Dupont",
        phone_number="01 23 45 67 89",
        birth_date="1980-05-15",
        reason="Consultation générale",
    )

    # Set appointment info
    recorder.set_appointment_info(
        appointment_date="2025-11-05", appointment_time="14:30"
    )

    # Get transcript
    transcript = recorder.get_full_transcript()
    print(f"\n[OK] Transcript captured ({recorder.get_turn_count()} turns):")
    print(transcript[:200] + "..." if len(transcript) > 200 else transcript)

    print(f"\n[OK] Summary: {recorder.get_summary()}")

    return recorder


async def test_test_persistence():
    """Test the test mode persistence (local JSON)"""
    print("\n\n[OK] Testing TestConversationPersistence...")

    # Create test persistence
    persistence = create_persistence(test_mode=True)
    print(f"[OK] Created persistence: {type(persistence).__name__}")

    # Create sample conversation data
    data = ConversationData(
        voice_agent_name="Camille",
        transcript="[2025-10-30T14:23:45] AGENT: Bonjour...\n[2025-10-30T14:23:47] USER: Bonjour...",
        conversation_date="2025-10-30",
        patient_name="Jean Dupont",
        phone_number="01 23 45 67 89",
        birth_date="1980-05-15",
        reason="Consultation générale",
        appointment_date="2025-11-05",
        appointment_time="14:30",
        audio_recording_url="https://example.com/recording.mp3",
    )

    # Store conversation
    success = await persistence.store_conversation(data)

    if success:
        print("[OK] Conversation stored successfully!")
        print("[OK] Check logs/conversations/ directory for the JSON file")
    else:
        print("[X] Failed to store conversation")

    await persistence.close()


async def test_n8n_persistence_dry_run():
    """Test N8N persistence initialization (without calling webhook)"""
    print("\n\n[OK] Testing N8nConversationPersistence initialization...")

    try:
        # Create N8N persistence with test URL
        persistence = create_persistence(
            webhook_url="https://test.example.com",
            webhook_token="test-token",
            test_mode=False,
        )
        print(f"[OK] Created persistence: {type(persistence).__name__}")
        print("[OK] N8N persistence initialized successfully (dry run)")

        await persistence.close()
    except Exception as e:
        print(f"[X] Error: {e}")


async def test_integration():
    """Test full integration: recorder + persistence"""
    print("\n\n[OK] Testing full integration...")

    # Create recorder and simulate conversation
    recorder = await test_conversation_recorder()

    # Create test persistence
    persistence = create_persistence(test_mode=True)

    # Build conversation data from recorder
    data = ConversationData(
        voice_agent_name=recorder.voice_agent_name,
        transcript=recorder.get_full_transcript(),
        conversation_date="2025-10-30",
        patient_name=recorder.patient_name,
        phone_number=recorder.phone_number,
        birth_date=recorder.birth_date,
        reason=recorder.reason,
        appointment_date=recorder.appointment_date,
        appointment_time=recorder.appointment_time,
        audio_recording_url=None,
    )

    # Store
    success = await persistence.store_conversation(data)

    if success:
        print("\n[OK] Full integration test PASSED!")
    else:
        print("\n[X] Full integration test FAILED")

    await persistence.close()


async def main():
    print("=" * 60)
    print("Testing Conversation Persistence Implementation")
    print("=" * 60)

    try:
        await test_conversation_recorder()
        await test_test_persistence()
        await test_n8n_persistence_dry_run()
        await test_integration()

        print("\n" + "=" * 60)
        print("[OK] All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[X] Test failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
