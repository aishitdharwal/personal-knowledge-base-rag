from pydantic import BaseModel
from typing import List, Optional

class DocumentChunk(BaseModel):
    """Represents a chunk of text from a document"""
    doc_id: str
    doc_name: str
    chunk_id: int
    text: str
    start_char: int
    end_char: int

class DocumentMetadata(BaseModel):
    """Metadata for an uploaded document"""
    doc_id: str
    filename: str
    upload_date: str
    num_chunks: int
    file_size: int

class LLMSettings(BaseModel):
    """LLM provider settings for a conversation"""
    answer_provider: str  # 'openai' or 'ollama'
    answer_model: str
    rewrite_provider: str  # 'openai', 'ollama', or 'disabled'
    rewrite_model: Optional[str] = None
    ollama_url: Optional[str] = None

class ChatMessage(BaseModel):
    """Chat message from user"""
    message: str
    conversation_id: Optional[str] = None
    settings: Optional[LLMSettings] = None

class ChatResponse(BaseModel):
    """Response from the RAG system"""
    answer: str
    sources: List[dict]
    conversation_id: str
    rewritten_query: Optional[str] = None
    settings: Optional[LLMSettings] = None

class UploadResponse(BaseModel):
    """Response after document upload"""
    doc_id: str
    filename: str
    num_chunks: int
    message: str

class EmbeddingSettings(BaseModel):
    """Embedding provider settings"""
    provider: str  # 'openai' or 'sentence-transformers'
    model: Optional[str] = None
    dimension: int

class ConnectionTestRequest(BaseModel):
    """Request to test provider connection"""
    provider: str  # 'openai' or 'ollama'
    model: str
    ollama_url: Optional[str] = None

class ConnectionTestResponse(BaseModel):
    """Response from connection test"""
    success: bool
    message: str

class OllamaModelsRequest(BaseModel):
    """Request to list Ollama models"""
    ollama_url: str

class OllamaModelsResponse(BaseModel):
    """Response with Ollama models"""
    success: bool
    models: List[str]
    message: str
