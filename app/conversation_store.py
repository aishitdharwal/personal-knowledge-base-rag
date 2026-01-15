"""
Conversation storage using PostgreSQL for persistence
"""
import os
import json
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from app.models import LLMSettings

Base = declarative_base()


class ConversationDB(Base):
    """SQLAlchemy model for conversations"""
    __tablename__ = 'conversations'

    conversation_id = Column(String(255), primary_key=True)
    title = Column(String(500), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    messages = Column(JSON, nullable=False)  # Store messages as JSON array
    settings = Column(JSON, nullable=True)  # Store LLM settings as JSON

    def to_dict(self) -> Dict:
        """Convert DB model to dictionary"""
        return {
            'conversation_id': self.conversation_id,
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'messages': self.messages,
            'settings': self.settings
        }


class ConversationStore:
    """PostgreSQL-based conversation storage"""

    def __init__(self, engine=None):
        """
        Initialize conversation store

        Args:
            engine: Optional SQLAlchemy engine. If not provided, creates one from env vars.
        """
        if engine:
            self.engine = engine
        else:
            # Get database connection details from environment
            db_host = os.getenv('DB_HOST')
            db_port = os.getenv('DB_PORT', '5432')
            db_name = os.getenv('DB_NAME', 'ragdb')
            db_user = os.getenv('DB_USER', 'raguser')
            db_password = os.getenv('DB_PASSWORD')

            if not all([db_host, db_password]):
                # Fallback to None if DB not configured (will use JSON file storage)
                self.engine = None
                self.Session = None
                print("Database connection not configured. Using fallback storage.")
                return

            # Create connection string
            connection_string = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

            # Create engine
            self.engine = create_engine(connection_string, echo=False)

        self.Session = sessionmaker(bind=self.engine)

        # Create tables
        Base.metadata.create_all(self.engine)

        print("ConversationStore initialized with PostgreSQL backend")

    def is_available(self) -> bool:
        """Check if database connection is available"""
        return self.engine is not None

    def save_conversation(self, conversation_id: str, conversation_data: Dict):
        """
        Save or update a conversation

        Args:
            conversation_id: Unique conversation identifier
            conversation_data: Dictionary with keys: title, created_at, updated_at, messages, settings
        """
        if not self.is_available():
            return False

        session = self.Session()
        try:
            # Parse datetime strings if they're strings
            created_at = conversation_data.get('created_at')
            updated_at = conversation_data.get('updated_at')

            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)

            # Serialize settings if it's a LLMSettings object
            settings = conversation_data.get('settings')
            if settings and hasattr(settings, 'dict'):
                settings = settings.dict()

            # Check if conversation exists
            existing = session.query(ConversationDB).filter_by(conversation_id=conversation_id).first()

            if existing:
                # Update existing
                existing.title = conversation_data.get('title', existing.title)
                existing.updated_at = updated_at or datetime.now()
                existing.messages = conversation_data.get('messages', existing.messages)
                existing.settings = settings
            else:
                # Create new
                new_conv = ConversationDB(
                    conversation_id=conversation_id,
                    title=conversation_data.get('title', 'New Conversation'),
                    created_at=created_at or datetime.now(),
                    updated_at=updated_at or datetime.now(),
                    messages=conversation_data.get('messages', []),
                    settings=settings
                )
                session.add(new_conv)

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"Error saving conversation: {e}")
            return False
        finally:
            session.close()

    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """
        Get a specific conversation by ID

        Args:
            conversation_id: Conversation identifier

        Returns:
            Dictionary with conversation data or None if not found
        """
        if not self.is_available():
            return None

        session = self.Session()
        try:
            conv = session.query(ConversationDB).filter_by(conversation_id=conversation_id).first()
            if conv:
                return conv.to_dict()
            return None
        finally:
            session.close()

    def get_all_conversations(self) -> List[Dict]:
        """
        Get all conversations

        Returns:
            List of conversation dictionaries
        """
        if not self.is_available():
            return []

        session = self.Session()
        try:
            conversations = session.query(ConversationDB).order_by(ConversationDB.updated_at.desc()).all()
            return [conv.to_dict() for conv in conversations]
        finally:
            session.close()

    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation

        Args:
            conversation_id: Conversation identifier

        Returns:
            True if deleted, False otherwise
        """
        if not self.is_available():
            return False

        session = self.Session()
        try:
            conv = session.query(ConversationDB).filter_by(conversation_id=conversation_id).first()
            if conv:
                session.delete(conv)
                session.commit()
                return True
            return False
        finally:
            session.close()

    def load_all_conversations_for_memory(self) -> Dict[str, Dict]:
        """
        Load all conversations into memory format (for RAGEngine)

        Returns:
            Dictionary with conversation_id as keys and conversation data as values
        """
        if not self.is_available():
            return {}

        session = self.Session()
        try:
            conversations = session.query(ConversationDB).all()
            result = {}
            for conv in conversations:
                conv_dict = conv.to_dict()
                # Convert settings back to LLMSettings if present
                if conv_dict.get('settings'):
                    try:
                        conv_dict['settings'] = LLMSettings(**conv_dict['settings'])
                    except:
                        conv_dict['settings'] = None

                result[conv.conversation_id] = conv_dict

            return result
        finally:
            session.close()
