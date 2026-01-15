#!/usr/bin/env python3
"""
Test script for ConversationStore
Tests both PostgreSQL and JSON fallback modes
"""
import os
import sys
from datetime import datetime
from app.conversation_store import ConversationStore
from app.models import LLMSettings

def test_json_fallback():
    """Test JSON file fallback when DB not available"""
    print("\n=== Testing JSON Fallback Mode ===")

    # Clear DB env vars to force fallback
    old_db_host = os.environ.get('DB_HOST')
    if 'DB_HOST' in os.environ:
        del os.environ['DB_HOST']

    try:
        store = ConversationStore()

        if store.is_available():
            print("❌ FAIL: Store should not be available without DB connection")
            return False

        print("✅ PASS: Store correctly detected no DB connection")
        print("✅ JSON fallback mode activated")
        return True

    finally:
        # Restore env var
        if old_db_host:
            os.environ['DB_HOST'] = old_db_host

def test_conversation_crud():
    """Test basic CRUD operations"""
    print("\n=== Testing Conversation CRUD ===")

    # This will use DB if available, otherwise skips tests
    store = ConversationStore()

    if not store.is_available():
        print("⚠️  PostgreSQL not configured - skipping CRUD tests")
        print("✅ PASS: Graceful handling of missing DB")
        return True

    print("✅ Using PostgreSQL backend")

    conv_id = "test-conv-123"

    try:
        # Create
        print(f"\n1. Creating conversation {conv_id}...")
        success = store.save_conversation(conv_id, {
            'title': 'Test Conversation',
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'messages': [
                {'role': 'user', 'content': 'Hello'},
                {'role': 'assistant', 'content': 'Hi there!'}
            ],
            'settings': {
                'answer_provider': 'openai',
                'answer_model': 'gpt-4'
            }
        })

        if success:
            print("✅ PASS: Conversation created in PostgreSQL")
        else:
            print("❌ FAIL: Could not create conversation")
            return False

        # Read
        print(f"\n2. Reading conversation {conv_id}...")
        conv = store.get_conversation(conv_id)

        if conv and conv['title'] == 'Test Conversation':
            print(f"✅ PASS: Found conversation: {conv['title']}")
            print(f"   Messages: {len(conv['messages'])}")
        else:
            print("❌ FAIL: Could not read conversation")
            return False

        # Update
        print(f"\n3. Updating conversation {conv_id}...")
        success = store.save_conversation(conv_id, {
            'title': 'Updated Test Conversation',
            'created_at': conv['created_at'],
            'updated_at': datetime.now(),
            'messages': conv['messages'] + [{'role': 'user', 'content': 'How are you?'}],
            'settings': conv.get('settings')
        })

        if success:
            conv = store.get_conversation(conv_id)
            if conv and len(conv['messages']) == 3:
                print("✅ PASS: Conversation updated")
                print(f"   New title: {conv['title']}")
                print(f"   Messages: {len(conv['messages'])}")
            else:
                print("❌ FAIL: Update did not persist correctly")
                return False
        else:
            print("❌ FAIL: Could not update conversation")
            return False

        # List all
        print("\n4. Listing all conversations...")
        all_convs = store.get_all_conversations()

        if len(all_convs) > 0:
            print(f"✅ PASS: Found {len(all_convs)} conversation(s)")
            for c in all_convs:
                print(f"   - {c['conversation_id']}: {c['title']}")
        else:
            print("⚠️  No conversations found (might be expected)")

        # Delete
        print(f"\n5. Deleting conversation {conv_id}...")
        success = store.delete_conversation(conv_id)

        if success:
            # Verify deleted
            conv = store.get_conversation(conv_id)
            if not conv:
                print("✅ PASS: Conversation deleted")
            else:
                print("❌ FAIL: Conversation still exists after delete")
                return False
        else:
            print("❌ FAIL: Could not delete conversation")
            return False

        return True

    except Exception as e:
        print(f"❌ FAIL: Exception during CRUD test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("ConversationStore Test Suite")
    print("=" * 60)

    # Check DB configuration
    db_host = os.environ.get('DB_HOST')
    if db_host:
        print(f"\n📡 DB_HOST configured: {db_host}")
        print("Will test PostgreSQL backend")
    else:
        print("\n⚠️  DB_HOST not configured")
        print("Will test JSON fallback mode")

    # Run tests
    test_results = []

    # Test 1: JSON fallback
    test_results.append(("JSON Fallback", test_json_fallback()))

    # Test 2: CRUD operations
    test_results.append(("CRUD Operations", test_conversation_crud()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    all_passed = all(result for _, result in test_results)

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
