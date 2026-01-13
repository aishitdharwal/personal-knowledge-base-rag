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

class ChatMessage(BaseModel):
    """Chat message from user"""
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    """Response from the RAG system"""
    answer: str
    sources: List[dict]
    conversation_id: str
    rewritten_query: Optional[str] = None

class UploadResponse(BaseModel):
    """Response after document upload"""
    doc_id: str
    filename: str
    num_chunks: int
    message: str
