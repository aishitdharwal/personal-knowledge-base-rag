# Conversation History Feature

## Overview

The system now includes a comprehensive conversation history feature that allows users to:
- View all past conversations in a sidebar
- Switch between conversations seamlessly
- Continue previous conversations from where they left off
- Delete unwanted conversations
- Start new conversations anytime

## What's New

### 🎯 Features

1. **Conversation Sidebar**
   - Left sidebar showing all conversations
   - Conversations sorted by most recent first
   - Each conversation shows:
     - Title (auto-generated from first message)
     - Preview (first 100 characters)
     - Time ago (e.g., "5m ago", "2h ago", "3d ago")
     - Delete button (✕)

2. **Conversation Persistence**
   - All conversations saved to `data/conversations.json`
   - Automatically saves after each message
   - Persists across server restarts
   - Includes conversation metadata (title, timestamps, message count)

3. **Conversation Management**
   - Click any conversation to load it
   - Active conversation highlighted in blue
   - "New Chat" button to start fresh conversation
   - Delete individual conversations
   - All conversation history preserved

4. **Seamless Switching**
   - Click to switch between conversations instantly
   - All messages loaded and displayed
   - Conversation settings (LLM provider, models) restored
   - Chat input remains ready for new messages

## Architecture Changes

### Backend (Python)

#### 1. **RAG Engine Updates** (`app/rag_engine.py`)

**New Methods**:
- `get_all_conversations()` - Returns list of all conversations with metadata
- `get_conversation(conversation_id)` - Returns specific conversation with all messages
- `delete_conversation(conversation_id)` - Deletes a conversation
- `_load_conversations()` - Loads conversations from disk on startup
- `_save_conversations()` - Saves conversations to disk after changes
- `_generate_title(first_message)` - Auto-generates conversation title

**Enhanced Methods**:
- `_add_to_conversation()` - Now includes timestamps and titles
- `reset_conversation()` - Now persists deletion to disk

**Data Structure**:
```python
{
  "conversation_id": {
    "messages": [
      {"role": "user", "content": "..."},
      {"role": "assistant", "content": "..."}
    ],
    "settings": LLMSettings,
    "title": "First message preview...",
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:35:00"
  }
}
```

#### 2. **API Endpoints** (`app/main.py`)

**New Endpoints**:
```python
GET  /conversations                    # List all conversations
GET  /conversations/{conversation_id}  # Get specific conversation
DELETE /conversations/{conversation_id} # Delete conversation
```

**Response Format**:
```json
// GET /conversations
{
  "conversations": [
    {
      "conversation_id": "uuid",
      "title": "What is machine learning...",
      "created_at": "2024-01-15T10:30:00",
      "updated_at": "2024-01-15T10:35:00",
      "message_count": 4,
      "preview": "What is machine learning and how does it work?"
    }
  ]
}

// GET /conversations/{id}
{
  "conversation_id": "uuid",
  "title": "What is machine learning...",
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:35:00",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "settings": {
    "answer_provider": "openai",
    "answer_model": "gpt-4",
    ...
  }
}
```

### Frontend (JavaScript)

#### 1. **UI Structure** (`templates/index.html`)

**New HTML Elements**:
```html
<div class="chat-container">
  <div class="conversations-sidebar">
    <div class="conversations-header">
      <h3>💬 Conversations</h3>
      <button id="newConversationBtn">+ New Chat</button>
    </div>
    <div id="conversationsList">
      <!-- Conversation items dynamically loaded -->
    </div>
  </div>

  <div class="chat-section">
    <!-- Existing chat interface -->
  </div>
</div>
```

**New CSS Classes**:
- `.chat-container` - Flex container for sidebar + chat
- `.conversations-sidebar` - Left sidebar (280px wide)
- `.conversations-header` - Header with title and new chat button
- `.conversations-list` - Scrollable list of conversations
- `.conversation-item` - Individual conversation card
- `.conversation-item.active` - Active conversation (blue border)
- `.conversation-title` - Conversation title with ellipsis
- `.conversation-preview` - Message preview
- `.conversation-meta` - Time ago + delete button
- `.conversation-delete` - Delete button (✕)

#### 2. **JavaScript Functions**

**New Functions**:
```javascript
loadConversations()           // Fetch and display all conversations
displayConversations(convs)   // Render conversation list
loadConversation(convId)      // Load specific conversation
deleteConversation(convId)    // Delete conversation
formatTimeAgo(isoString)      // Format timestamp to "5m ago"
```

**Modified Functions**:
```javascript
sendMessage()                 // Now calls loadConversations() after sending
startNewConversation()        // Simplified - just clears current state
window.onload()               // Now calls loadConversations() on load
```

## User Experience

### Starting a Conversation
1. Visit main page (`/`)
2. See "No conversations yet" in sidebar
3. Type a message and hit Send
4. Conversation automatically created with title from first message
5. Appears in sidebar immediately

### Switching Conversations
1. See list of all conversations in left sidebar
2. Click any conversation to load it
3. All messages instantly displayed
4. Active conversation highlighted in blue
5. Ready to continue from where you left off

### Managing Conversations
1. Hover over conversation to see delete button (✕)
2. Click ✕ to delete (with confirmation)
3. If active conversation deleted, chat area clears
4. Click "+ New Chat" to start fresh conversation

### Time Display
- "Just now" - Less than 1 minute
- "5m ago" - Minutes ago
- "2h ago" - Hours ago
- "3d ago" - Days ago
- "Jan 15" - More than a week ago

## File Locations

### Backend
- `app/rag_engine.py` - Conversation logic and persistence
- `app/main.py` - API endpoints (lines 271-312)

### Frontend
- `templates/index.html` - UI and JavaScript

### Data
- `data/conversations.json` - Persisted conversations (auto-created)

## Migration Notes

### Existing Conversations
- Conversations created before this feature will NOT be persisted
- After update, users start with empty conversation history
- First new conversation will create `data/conversations.json`

### Backward Compatibility
- All existing API endpoints unchanged
- Existing chat functionality works as before
- New endpoints are additive only

## Configuration

### Conversation Storage
**File**: `data/conversations.json`
**Format**: JSON
**Location**: Configured by `DATA_PATH` in `app/config.py`

### Conversation Settings
- **Max history per conversation**: Controlled by `MAX_CONVERSATION_HISTORY` (default: 10 messages)
- **Query rewrite history**: Controlled by `QUERY_REWRITE_HISTORY` (default: 5 Q&A pairs)
- **Auto-save**: Every message automatically saved to disk

## Testing

### Manual Testing
```bash
# Start the application
python run.py

# Visit http://localhost:8000
# 1. Send a message → conversation appears in sidebar
# 2. Send more messages → conversation updates
# 3. Click "+ New Chat" → new conversation
# 4. Send message in new conversation → second conversation appears
# 5. Click first conversation → loads all messages
# 6. Click delete (✕) on conversation → deleted
```

### API Testing
```bash
# List conversations
curl http://localhost:8000/conversations

# Get specific conversation
curl http://localhost:8000/conversations/{conversation_id}

# Delete conversation
curl -X DELETE http://localhost:8000/conversations/{conversation_id}
```

## Performance Considerations

### Storage
- Each conversation stored in single JSON file
- File size grows with number of conversations
- Typical conversation: ~1-10 KB
- 100 conversations: ~100 KB - 1 MB (negligible)

### Load Time
- Conversations loaded once on app startup
- List conversations: O(n) where n = number of conversations
- Load specific conversation: O(1) dictionary lookup
- No database queries required

### Memory
- All conversations kept in memory
- Minimal memory footprint (<10 MB for thousands of conversations)
- Instant access without database overhead

## Future Enhancements

### Potential Features
1. **Search conversations** - Search by title or content
2. **Rename conversations** - Edit auto-generated titles
3. **Archive conversations** - Hide without deleting
4. **Export conversations** - Download as PDF/JSON
5. **Conversation tags** - Organize by topic
6. **Conversation stats** - Message count, tokens used
7. **Shared conversations** - Share via URL
8. **Conversation folders** - Group related conversations

### Scalability
For thousands of conversations:
1. Consider pagination in sidebar
2. Add lazy loading (load messages on demand)
3. Move to database (PostgreSQL) instead of JSON
4. Add full-text search index
5. Implement conversation archiving

## Security Considerations

### Data Privacy
- Conversations stored locally in `data/` directory
- No external storage or cloud sync
- Access controlled by file system permissions

### Sensitive Information
- Users should not share conversations containing:
  - API keys or credentials
  - Personal identifiable information (PII)
  - Confidential business data
- No built-in encryption (file system encryption recommended)

### Multi-User Environments
- Current implementation: single-user
- For multi-user: add user authentication and conversation ownership
- Implement per-user conversation storage

## Troubleshooting

### Conversations Not Appearing
1. Check `data/conversations.json` exists and is readable
2. Check browser console for JavaScript errors
3. Verify `/conversations` API endpoint returns data
4. Check file permissions on `data/` directory

### Conversations Not Persisting
1. Check write permissions on `data/` directory
2. Verify `conversations.json` is writable
3. Check server logs for save errors
4. Ensure disk space available

### Conversation Loading Slowly
1. Check `conversations.json` file size
2. If > 10 MB, consider archiving old conversations
3. Check network tab for slow API responses
4. Verify server has adequate resources

## Summary

The conversation history feature provides a complete chat history management system with:
- ✅ Persistent storage across restarts
- ✅ Easy conversation switching
- ✅ Auto-generated titles
- ✅ Time-based sorting
- ✅ Simple deletion
- ✅ Clean, intuitive UI
- ✅ No database required
- ✅ Minimal performance impact

Users can now maintain multiple ongoing conversations and easily return to previous discussions without losing context!
