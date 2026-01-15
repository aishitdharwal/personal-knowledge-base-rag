# Conversation Storage Upgrade - PostgreSQL Integration

## Overview

The conversation history feature has been upgraded to use **PostgreSQL (RDS)** for persistent storage instead of local JSON files. This provides:

- ✅ **Durability**: Conversations survive container restarts and deployments
- ✅ **Scalability**: Multiple containers can share conversation state
- ✅ **Consistency**: Single source of truth for all conversation data
- ✅ **Backup**: Automatic RDS snapshots and point-in-time recovery

## Architecture

### Storage Strategy

The system uses a **hybrid approach** with graceful fallback:

1. **Primary Storage**: PostgreSQL RDS (when available)
2. **Backup Storage**: Local JSON file (automatic backup)
3. **Fallback**: Local JSON file (when DB unavailable)

### Database Schema

```sql
CREATE TABLE conversations (
    conversation_id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    messages JSON NOT NULL,
    settings JSON
);

CREATE INDEX idx_conversations_updated_at ON conversations(updated_at DESC);
CREATE INDEX idx_conversations_created_at ON conversations(created_at DESC);
```

## Components

### 1. ConversationStore (`app/conversation_store.py`)

New module that handles all database interactions:

```python
from app.conversation_store import ConversationStore

# Initialize (auto-detects DB connection from env vars)
store = ConversationStore()

# Check if DB is available
if store.is_available():
    print("Using PostgreSQL for conversations")

# Save conversation
store.save_conversation(conv_id, {
    'title': 'My Chat',
    'created_at': datetime.now(),
    'updated_at': datetime.now(),
    'messages': [...],
    'settings': {...}
})

# Get conversation
conv = store.get_conversation(conv_id)

# Get all conversations
convs = store.get_all_conversations()

# Delete conversation
store.delete_conversation(conv_id)
```

### 2. RAGEngine Updates

The `RAGEngine` class has been updated to use `ConversationStore`:

**Key Changes:**
- Auto-initializes `ConversationStore` in constructor
- `_load_conversations()` tries PostgreSQL first, falls back to JSON
- `_save_conversations()` saves to both PostgreSQL and JSON (backup)
- `delete_conversation()` deletes from both storage locations

### 3. Database Migration

SQL script to initialize the conversations table:

```bash
# Run migration on RDS
psql -h <rds-endpoint> -U raguser -d ragdb -f infrastructure/scripts/init-conversations-db.sql
```

Or the table is auto-created by SQLAlchemy on first connection.

## Configuration

### Environment Variables

The system uses existing database environment variables:

```bash
# Required for PostgreSQL storage
DB_HOST=your-rds-endpoint.rds.amazonaws.com
DB_PORT=5432
DB_NAME=ragdb
DB_USER=raguser
DB_PASSWORD=your-secure-password

# Optional - for custom configuration
DATA_PATH=data  # Fallback JSON file location
```

### Connection String Format

```
postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}
```

## Deployment

### Local Development

When running locally without RDS:

```bash
# System automatically falls back to JSON file storage
python run.py

# Conversations saved to: data/conversations.json
```

### AWS Deployment

The system automatically uses RDS when deployed to AWS:

1. **Environment Variables** are set via ECS task definition
2. **RDS Endpoint** is provided by CloudFormation outputs
3. **Database Connection** is established on startup
4. **Conversations Table** is auto-created if it doesn't exist

### Migration from JSON to PostgreSQL

When deploying with existing JSON conversations:

1. System loads existing conversations from `data/conversations.json` on first startup
2. On first save, conversations are written to both PostgreSQL and JSON
3. Future loads prioritize PostgreSQL
4. JSON file remains as backup

## Testing

### Local Testing with PostgreSQL

```bash
# Start local PostgreSQL with Docker
docker run --name postgres-test \
  -e POSTGRES_USER=raguser \
  -e POSTGRES_PASSWORD=testpass \
  -e POSTGRES_DB=ragdb \
  -p 5432:5432 \
  -d postgres:15

# Enable pgvector extension
docker exec postgres-test psql -U raguser -d ragdb -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Set environment variables
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=ragdb
export DB_USER=raguser
export DB_PASSWORD=testpass

# Run application
python run.py
```

### Testing CRUD Operations

```python
# Test script
from app.conversation_store import ConversationStore
from datetime import datetime

store = ConversationStore()

# Create conversation
conv_id = "test-123"
store.save_conversation(conv_id, {
    'title': 'Test Chat',
    'created_at': datetime.now(),
    'updated_at': datetime.now(),
    'messages': [
        {'role': 'user', 'content': 'Hello'},
        {'role': 'assistant', 'content': 'Hi there!'}
    ],
    'settings': None
})

# Read conversation
conv = store.get_conversation(conv_id)
print(f"Found: {conv['title']}")

# List all
all_convs = store.get_all_conversations()
print(f"Total conversations: {len(all_convs)}")

# Delete
store.delete_conversation(conv_id)
print("Deleted successfully")
```

## Monitoring

### Check Storage Backend

```bash
# Check application logs on startup
# Look for one of:
# "Loaded N conversations from PostgreSQL"
# "Loaded N conversations from JSON file"
# "Database connection not configured. Using fallback storage."
```

### Verify Database Connection

```python
from app.conversation_store import ConversationStore

store = ConversationStore()
if store.is_available():
    print("✅ PostgreSQL connected")
else:
    print("⚠️ Using JSON fallback")
```

### Query Conversations Directly

```sql
-- Connect to RDS
psql -h <rds-endpoint> -U raguser -d ragdb

-- Count conversations
SELECT COUNT(*) FROM conversations;

-- List recent conversations
SELECT
    conversation_id,
    title,
    updated_at,
    jsonb_array_length(messages::jsonb) as message_count
FROM conversations
ORDER BY updated_at DESC
LIMIT 10;

-- Get conversation details
SELECT * FROM conversations WHERE conversation_id = 'your-conv-id';
```

## Backup and Recovery

### Automated Backups

- **RDS Snapshots**: Automatic daily snapshots (configured in CloudFormation)
- **JSON Backup**: Local file saved on every conversation update
- **Point-in-Time Recovery**: RDS supports up to 35 days of recovery

### Manual Backup

```bash
# Export all conversations from PostgreSQL
pg_dump -h <rds-endpoint> -U raguser -d ragdb \
  -t conversations --data-only --column-inserts \
  > conversations-backup.sql

# Restore from backup
psql -h <rds-endpoint> -U raguser -d ragdb < conversations-backup.sql
```

### Disaster Recovery

If PostgreSQL becomes unavailable:

1. System automatically falls back to JSON file
2. New conversations saved to JSON only
3. When DB recovers, restart application
4. Conversations in JSON will be loaded and synced to DB on next save

## Performance

### Expected Performance

- **Save Operation**: ~5-10ms (PostgreSQL) vs ~1-2ms (JSON)
- **Load All**: ~50-100ms for 1000 conversations
- **Single Get**: ~3-5ms
- **Delete**: ~5-10ms

### Optimization

- Indexed by `updated_at` for fast "recent conversations" queries
- Indexed by `created_at` for chronological sorting
- JSON columns for flexible message/settings storage
- Connection pooling via SQLAlchemy

## Security

### Database Security

- ✅ Credentials stored in environment variables (not in code)
- ✅ SSL/TLS connection to RDS (enforced)
- ✅ VPC isolation (RDS in private subnet)
- ✅ Security groups restrict access to ECS only
- ✅ IAM authentication supported (optional)

### Data Privacy

- Conversation data stored in encrypted RDS volume
- Encryption at rest (RDS encryption enabled)
- Encryption in transit (SSL/TLS connections)
- No conversation data in application logs

## Troubleshooting

### Issue: "Cannot import name 'DATA_PATH'"

**Solution**: Update `app/config.py` to include:
```python
DATA_PATH = "data"
```

### Issue: "Database connection not configured"

**Cause**: Missing environment variables

**Solution**: Set required env vars:
```bash
export DB_HOST=your-rds-endpoint
export DB_PASSWORD=your-password
```

### Issue: Conversations not persisting

**Check**:
1. Verify DB connection: Check startup logs
2. Verify table exists: `\dt` in psql
3. Check permissions: User should have INSERT/UPDATE/DELETE
4. Check logs for errors

### Issue: "relation 'conversations' does not exist"

**Solution**: Run migration script:
```bash
psql -h <rds-endpoint> -U raguser -d ragdb \
  -f infrastructure/scripts/init-conversations-db.sql
```

Or restart application (auto-creates table).

## Migration Checklist

Before deploying to production:

- [ ] RDS instance is running and accessible
- [ ] Environment variables configured in ECS task definition
- [ ] Security groups allow ECS → RDS communication
- [ ] Database user has required permissions
- [ ] Backup strategy configured (RDS snapshots)
- [ ] Monitoring/alerting set up for RDS metrics
- [ ] Test failover to JSON file storage
- [ ] Document recovery procedures for team

## API Endpoints (Unchanged)

The REST API remains the same:

- `GET /conversations` - List all conversations
- `GET /conversations/{id}` - Get specific conversation
- `DELETE /conversations/{id}` - Delete conversation

Backend storage change is transparent to frontend.

## Files Modified

1. `app/conversation_store.py` - New file (database operations)
2. `app/rag_engine.py` - Updated to use ConversationStore
3. `app/config.py` - Added DATA_PATH constant
4. `infrastructure/scripts/init-conversations-db.sql` - New migration script
5. `CONVERSATION_STORAGE_UPGRADE.md` - This documentation

## Next Steps

1. ✅ Test locally with PostgreSQL
2. ✅ Verify conversation CRUD operations
3. ⏳ Update deployment scripts
4. ⏳ Deploy to AWS
5. ⏳ Verify RDS connection in production
6. ⏳ Monitor performance and errors

## Support

For issues or questions:
- Check application logs for storage backend in use
- Verify RDS connectivity with `psql` or telnet
- Review this document for configuration details
- Test with local PostgreSQL before deploying
