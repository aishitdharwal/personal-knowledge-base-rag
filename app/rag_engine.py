from typing import List, Dict, Optional
from datetime import datetime
import json
import os
from app.vector_store import VectorStore
from app.models import LLMSettings
from app.providers.base import LLMProvider
from app.providers.openai_provider import OpenAILLMProvider
from app.providers.ollama_provider import OllamaLLMProvider
from app.conversation_store import ConversationStore
from app.config import (
    TOP_K_RESULTS,
    MAX_CONVERSATION_HISTORY,
    QUERY_REWRITE_HISTORY,
    DEFAULT_ANSWER_PROVIDER,
    DEFAULT_ANSWER_MODEL,
    DEFAULT_REWRITE_PROVIDER,
    DEFAULT_REWRITE_MODEL,
    DEFAULT_OLLAMA_URL,
    DATA_PATH
)

class RAGEngine:
    """Handles the RAG pipeline with conversation memory, query rewriting, and multi-provider support"""

    def __init__(self, vector_store: VectorStore, conversation_store: Optional[ConversationStore] = None):
        self.vector_store = vector_store
        self.conversations = {}  # conversation_id -> {messages: [...], settings: LLMSettings, title: str, created_at: str, updated_at: str}
        self.conversations_path = os.path.join(DATA_PATH, "conversations.json")

        # Initialize conversation store (PostgreSQL or fallback to JSON)
        self.conversation_store = conversation_store or ConversationStore()

        self._load_conversations()
    
    def _get_default_settings(self) -> LLMSettings:
        """Get default LLM settings"""
        return LLMSettings(
            answer_provider=DEFAULT_ANSWER_PROVIDER,
            answer_model=DEFAULT_ANSWER_MODEL,
            rewrite_provider=DEFAULT_REWRITE_PROVIDER,
            rewrite_model=DEFAULT_REWRITE_MODEL,
            ollama_url=DEFAULT_OLLAMA_URL
        )
    
    def _get_llm_provider(self, settings: LLMSettings, for_rewriting: bool = False) -> Optional[LLMProvider]:
        """
        Get the appropriate LLM provider based on settings
        
        Args:
            settings: LLM settings
            for_rewriting: If True, use rewrite provider, else use answer provider
            
        Returns:
            LLMProvider instance or None if rewriting is disabled
        """
        if for_rewriting:
            provider = settings.rewrite_provider
            model = settings.rewrite_model
            
            if provider == "disabled":
                return None
        else:
            provider = settings.answer_provider
            model = settings.answer_model
        
        if provider == "openai":
            return OpenAILLMProvider(model=model)
        elif provider == "ollama":
            ollama_url = settings.ollama_url or DEFAULT_OLLAMA_URL
            return OllamaLLMProvider(base_url=ollama_url, model=model)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
    
    def _rewrite_query(self, current_query: str, conversation_id: str, settings: LLMSettings) -> Optional[str]:
        """
        Rewrite the user query to be standalone and self-contained using conversation history
        
        Args:
            current_query: The current user query
            conversation_id: Conversation ID to get history from
            settings: LLM settings for this conversation
            
        Returns:
            Rewritten standalone query or None if rewriting is disabled or no history
        """
        # Check if rewriting is disabled
        if settings.rewrite_provider == "disabled":
            return None
        
        # Get conversation history
        history = self._get_conversation_history(conversation_id)
        
        # If no history, return None (use original query)
        if not history:
            return None
        
        # Get last N Q&A pairs for rewriting context
        rewrite_history = history[-(QUERY_REWRITE_HISTORY * 2):]  # Each Q&A is 2 messages
        
        # Build conversation context for rewriting
        conversation_context = ""
        for msg in rewrite_history:
            role = "User" if msg['role'] == 'user' else "Assistant"
            conversation_context += f"{role}: {msg['content']}\n"
        
        # System prompt for query rewriting
        rewrite_prompt = """You are a query rewriting assistant. Your job is to take a user's query and rewrite it to be a standalone, self-contained question that can be understood without any conversation history.

Instructions:
1. Read the conversation history to understand the context
2. Rewrite the current query to include all necessary context from the conversation
3. The rewritten query should be a complete, standalone question
4. Keep the rewritten query concise but include all relevant context
5. If the query is already standalone, you may return it as-is or with minor improvements

Examples:
- "tell me more" → "Tell me more about [specific topic from previous query]"
- "what about X?" → "What about X in the context of [previous topic]?"
- "explain further" → "Explain [previous topic] in more detail"

Return ONLY the rewritten query, nothing else."""

        # Build messages for rewriting
        messages = [
            {'role': 'system', 'content': rewrite_prompt},
            {'role': 'user', 'content': f"""Conversation history:
{conversation_context}

Current query: {current_query}

Rewrite the current query to be standalone and self-contained:"""}
        ]
        
        try:
            # Get LLM provider for rewriting
            provider = self._get_llm_provider(settings, for_rewriting=True)
            
            if provider is None:
                return None
            
            # Call LLM for query rewriting
            rewritten_query = provider.generate(messages, temperature=0.2, max_tokens=150)
            
            # Validate that we got a proper response
            if not rewritten_query or len(rewritten_query.strip()) < 3:
                raise Exception("Query rewriting returned empty or invalid response")
            
            rewritten_query = rewritten_query.strip()
            print(f"[Query Rewrite] Original: '{current_query}' → Rewritten: '{rewritten_query}'")
            return rewritten_query
            
        except Exception as e:
            print(f"[Query Rewrite Error] {str(e)}")
            raise Exception(f"Query rewriting failed: {str(e)}")
    
    def _build_context(self, query: str, top_k: int = TOP_K_RESULTS) -> tuple[str, List[dict]]:
        """
        Retrieve relevant context from vector store
        
        Args:
            query: User query (should be rewritten/standalone)
            top_k: Number of chunks to retrieve
            
        Returns:
            Tuple of (context_text, sources)
        """
        # Search for similar chunks
        results = self.vector_store.search(query, top_k)
        
        if not results:
            return "", []
        
        # Build context string and sources
        context_parts = []
        sources = []
        
        for idx, (chunk, score) in enumerate(results, 1):
            context_parts.append(f"[Document {idx}: {chunk.doc_name}]\n{chunk.text}\n")
            sources.append({
                'document': chunk.doc_name,
                'chunk_id': chunk.chunk_id,
                'similarity_score': round(score, 4),
                'text_preview': chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text
            })
        
        context = "\n".join(context_parts)
        return context, sources
    
    def _get_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """Get conversation history for a given conversation ID"""
        if conversation_id not in self.conversations:
            return []
        
        messages = self.conversations[conversation_id].get('messages', [])
        # Return last MAX_CONVERSATION_HISTORY messages
        return messages[-MAX_CONVERSATION_HISTORY:]
    
    def _add_to_conversation(self, conversation_id: str, role: str, content: str, settings: LLMSettings):
        """Add a message to conversation history"""
        current_time = datetime.now().isoformat()

        if conversation_id not in self.conversations:
            # New conversation - generate title from first user message
            title = self._generate_title(content) if role == 'user' else 'New Conversation'
            self.conversations[conversation_id] = {
                'messages': [],
                'settings': settings,
                'title': title,
                'created_at': current_time,
                'updated_at': current_time
            }

        # Update conversation
        self.conversations[conversation_id]['messages'].append({
            'role': role,
            'content': content
        })
        self.conversations[conversation_id]['updated_at'] = current_time

        # Save to disk after each message
        self._save_conversations()
        
        # Update settings
        self.conversations[conversation_id]['settings'] = settings
    
    def _get_conversation_settings(self, conversation_id: str) -> Optional[LLMSettings]:
        """Get settings for a conversation"""
        if conversation_id in self.conversations:
            return self.conversations[conversation_id].get('settings')
        return None
    
    def chat(self, query: str, conversation_id: str, settings: Optional[LLMSettings] = None) -> tuple[str, List[dict], Optional[str], LLMSettings]:
        """
        Generate answer using RAG with conversation memory, query rewriting, and multi-provider support
        
        Args:
            query: User query (may be contextual like "tell me more")
            conversation_id: Unique conversation identifier
            settings: LLM settings (uses default or previous conversation settings if not provided)
            
        Returns:
            Tuple of (answer, sources, rewritten_query, applied_settings)
            
        Raises:
            Exception: If query rewriting or generation fails
        """
        # Determine settings to use
        if settings is None:
            # Try to get from previous conversation
            settings = self._get_conversation_settings(conversation_id)
            if settings is None:
                # Use defaults
                settings = self._get_default_settings()
        
        # Step 1: Rewrite query to be standalone (if enabled and has history)
        rewritten_query = None
        if settings.rewrite_provider != "disabled":
            try:
                rewritten_query = self._rewrite_query(query, conversation_id, settings)
            except Exception as e:
                # Re-raise the exception to be handled by the API endpoint
                raise e
        
        # Use rewritten query for retrieval if available, otherwise use original
        search_query = rewritten_query if rewritten_query else query
        
        # Step 2: Retrieve relevant context using search query
        context, sources = self._build_context(search_query)
        
        # Build system prompt with clear instructions
        system_prompt = """You are a helpful AI assistant that answers questions based on the provided context from the user's knowledge base.

CRITICAL RULES:
1. ALWAYS base your answer on the CURRENT context provided with each question
2. The context is retrieved fresh for EACH question - use it as your primary source
3. You may use conversation history for context about what was discussed, but NEVER to answer factual questions
4. If the current context doesn't contain the answer, say so clearly - don't rely on previous answers
5. Each question should be treated as requiring fresh information from the knowledge base
6. Cite specific documents from the CURRENT context when making claims

Instructions:
- Answer questions using ONLY the information from the CURRENT context provided below
- If the context doesn't contain enough information to answer, say so clearly
- Be concise but comprehensive
- Always cite specific documents when making claims
- Use conversation history only to understand follow-up questions or references, not to answer them
"""
        
        # Get conversation history (only last few exchanges for context continuity)
        history = self._get_conversation_history(conversation_id)
        
        # Build messages for LLM
        messages = [{'role': 'system', 'content': system_prompt}]
        
        # Add LIMITED conversation history
        if history:
            recent_history = history[-6:]  # Last 3 Q&A pairs (6 messages)
            messages.extend(recent_history)
        
        # Add current query with FRESH context
        if context:
            user_message = f"""===CURRENT CONTEXT FROM KNOWLEDGE BASE===
{context}

===END OF CURRENT CONTEXT===

User question: {query}

Remember: Answer ONLY based on the CURRENT CONTEXT provided above. Do not use information from previous answers unless explicitly present in the current context."""
        else:
            user_message = f"""===CURRENT CONTEXT FROM KNOWLEDGE BASE===
No relevant context found in the knowledge base for this question.

===END OF CURRENT CONTEXT===

User question: {query}"""
        
        messages.append({'role': 'user', 'content': user_message})
        
        # Step 3: Generate response using configured LLM provider
        try:
            provider = self._get_llm_provider(settings, for_rewriting=False)
            answer = provider.generate(messages, temperature=0.3, max_tokens=1000)
        except Exception as e:
            raise Exception(f"Answer generation failed: {str(e)}")
        
        # Add to conversation history (store only the query and answer, not the context)
        self._add_to_conversation(conversation_id, 'user', query, settings)
        self._add_to_conversation(conversation_id, 'assistant', answer, settings)
        
        return answer, sources, rewritten_query, settings
    
    def reset_conversation(self, conversation_id: str):
        """Clear conversation history for a specific conversation"""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            self._save_conversations()

    def delete_conversation(self, conversation_id: str):
        """Delete a specific conversation"""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]

            # Delete from database if available
            if self.conversation_store.is_available():
                try:
                    self.conversation_store.delete_conversation(conversation_id)
                except Exception as e:
                    print(f"Error deleting conversation from PostgreSQL: {e}")

            # Save updated state
            self._save_conversations()
            return True
        return False

    def get_active_conversations(self) -> List[str]:
        """Get list of active conversation IDs"""
        return list(self.conversations.keys())

    def get_all_conversations(self) -> List[Dict]:
        """Get all conversations with metadata"""
        conversations_list = []
        for conv_id, conv_data in self.conversations.items():
            messages = conv_data.get('messages', [])
            conversations_list.append({
                'conversation_id': conv_id,
                'title': conv_data.get('title', 'Untitled Conversation'),
                'created_at': conv_data.get('created_at', ''),
                'updated_at': conv_data.get('updated_at', ''),
                'message_count': len(messages),
                'preview': messages[0]['content'][:100] if messages else ''
            })

        # Sort by updated_at descending (most recent first)
        conversations_list.sort(key=lambda x: x['updated_at'], reverse=True)
        return conversations_list

    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get a specific conversation with all its messages"""
        if conversation_id not in self.conversations:
            return None

        conv_data = self.conversations[conversation_id]
        return {
            'conversation_id': conversation_id,
            'title': conv_data.get('title', 'Untitled Conversation'),
            'created_at': conv_data.get('created_at', ''),
            'updated_at': conv_data.get('updated_at', ''),
            'messages': conv_data.get('messages', []),
            'settings': conv_data.get('settings')
        }

    def _generate_title(self, first_message: str) -> str:
        """Generate a title from the first message"""
        # Take first 50 chars and clean up
        title = first_message[:50].strip()
        if len(first_message) > 50:
            title += "..."
        return title

    def _load_conversations(self):
        """Load conversations from PostgreSQL or disk (fallback)"""
        # Try loading from database first
        if self.conversation_store.is_available():
            try:
                self.conversations = self.conversation_store.load_all_conversations_for_memory()
                print(f"Loaded {len(self.conversations)} conversations from PostgreSQL")
                return
            except Exception as e:
                print(f"Error loading conversations from PostgreSQL: {e}")

        # Fallback to JSON file
        if os.path.exists(self.conversations_path):
            try:
                with open(self.conversations_path, 'r') as f:
                    data = json.load(f)
                    # Convert settings dict back to LLMSettings objects
                    for conv_id, conv_data in data.items():
                        if 'settings' in conv_data and conv_data['settings']:
                            conv_data['settings'] = LLMSettings(**conv_data['settings'])
                    self.conversations = data
                print(f"Loaded {len(self.conversations)} conversations from JSON file")
            except Exception as e:
                print(f"Error loading conversations from JSON: {e}")
                self.conversations = {}
        else:
            self.conversations = {}

    def _save_conversations(self):
        """Save conversations to PostgreSQL or disk (fallback)"""
        # Try saving to database first
        if self.conversation_store.is_available():
            try:
                for conv_id, conv_data in self.conversations.items():
                    self.conversation_store.save_conversation(conv_id, conv_data)
                # Also save to JSON as backup
                self._save_to_json_file()
                return
            except Exception as e:
                print(f"Error saving conversations to PostgreSQL: {e}")

        # Fallback to JSON file only
        self._save_to_json_file()

    def _save_to_json_file(self):
        """Save conversations to JSON file"""
        try:
            # Convert LLMSettings objects to dicts for JSON serialization
            serializable_data = {}
            for conv_id, conv_data in self.conversations.items():
                serializable_conv = conv_data.copy()
                if 'settings' in serializable_conv and serializable_conv['settings']:
                    serializable_conv['settings'] = serializable_conv['settings'].dict()
                serializable_data[conv_id] = serializable_conv

            os.makedirs(os.path.dirname(self.conversations_path), exist_ok=True)
            with open(self.conversations_path, 'w') as f:
                json.dump(serializable_data, f, indent=2)
        except Exception as e:
            print(f"Error saving conversations to JSON: {e}")
