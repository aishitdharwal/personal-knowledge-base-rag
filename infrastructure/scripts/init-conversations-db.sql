-- Initialize conversations table in PostgreSQL
-- This script is idempotent and can be run multiple times safely

-- Create conversations table
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    messages JSON NOT NULL,
    settings JSON
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);

-- Print confirmation
DO $$
BEGIN
    RAISE NOTICE 'Conversations table initialized successfully';
END
$$;
