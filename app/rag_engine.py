from typing import List, Dict
from openai import OpenAI
from app.vector_store import VectorStore
from app.config import (
    OPENAI_API_KEY, 
    LLM_MODEL, 
    QUERY_REWRITE_MODEL,
    TOP_K_RESULTS, 
    MAX_CONVERSATION_HISTORY,
    QUERY_REWRITE_HISTORY
)

class RAGEngine:
    """Handles the RAG pipeline with conversation memory and query rewriting"""
    
    def __init__(self, vector_store: VectorStore):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.vector_store = vector_store
        self.conversations = {}  # conversation_id -> list of messages
    
    def _rewrite_query(self, current_query: str, conversation_id: str) -> str:
        """
        Rewrite the user query to be standalone and self-contained using conversation history
        
        Args:
            current_query: The current user query
            conversation_id: Conversation ID to get history from
            
        Returns:
            Rewritten standalone query
            
        Raises:
            Exception: If query rewriting fails
        """
        # Get conversation history
        history = self._get_conversation_history(conversation_id)
        
        # If no history, return original query
        if not history:
            return current_query
        
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
            # Call LLM for query rewriting
            response = self.client.chat.completions.create(
                model=QUERY_REWRITE_MODEL,
                messages=messages,
                temperature=0.2,  # Low temperature for consistent rewriting
                max_tokens=150
            )
            
            rewritten_query = response.choices[0].message.content.strip()
            
            # Validate that we got a proper response
            if not rewritten_query or len(rewritten_query) < 3:
                raise Exception("Query rewriting returned empty or invalid response")
            
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
        
        # Return last MAX_CONVERSATION_HISTORY messages
        return self.conversations[conversation_id][-MAX_CONVERSATION_HISTORY:]
    
    def _add_to_conversation(self, conversation_id: str, role: str, content: str):
        """Add a message to conversation history"""
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        
        self.conversations[conversation_id].append({
            'role': role,
            'content': content
        })
    
    def chat(self, query: str, conversation_id: str) -> tuple[str, List[dict], str]:
        """
        Generate answer using RAG with conversation memory and query rewriting
        
        Args:
            query: User query (may be contextual like "tell me more")
            conversation_id: Unique conversation identifier
            
        Returns:
            Tuple of (answer, sources, rewritten_query)
            
        Raises:
            Exception: If query rewriting fails
        """
        # Step 1: Rewrite query to be standalone
        try:
            rewritten_query = self._rewrite_query(query, conversation_id)
        except Exception as e:
            # Re-raise the exception to be handled by the API endpoint
            raise e
        
        # Step 2: Retrieve relevant context using rewritten query
        context, sources = self._build_context(rewritten_query)
        
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
- Be concise but comprehensive
- Always cite specific documents when making claims
- Use conversation history only to understand follow-up questions or references, not to answer them
"""
        
        # Get conversation history (only last few exchanges for context continuity)
        history = self._get_conversation_history(conversation_id)
        
        # Build messages for GPT-4
        messages = [{'role': 'system', 'content': system_prompt}]
        
        # Add LIMITED conversation history (only if it exists and is relevant)
        # Keep only the last 3 exchanges to prevent over-reliance on history
        if history:
            # Only include history if conversation_id is active
            recent_history = history[-6:]  # Last 3 Q&A pairs (6 messages)
            messages.extend(recent_history)
        
        # Add current query with FRESH context - this is the most important part
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
        
        # Generate response with lower temperature for more focused answers
        response = self.client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.3,  # Lower temperature for more deterministic, grounded answers
            max_tokens=1000
        )
        
        answer = response.choices[0].message.content
        
        # Add to conversation history (store only the query and answer, not the context)
        self._add_to_conversation(conversation_id, 'user', query)
        self._add_to_conversation(conversation_id, 'assistant', answer)
        
        return answer, sources, rewritten_query
    
    def reset_conversation(self, conversation_id: str):
        """Clear conversation history for a specific conversation"""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
    
    def get_active_conversations(self) -> List[str]:
        """Get list of active conversation IDs"""
        return list(self.conversations.keys())
