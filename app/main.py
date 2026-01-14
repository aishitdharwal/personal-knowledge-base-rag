from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
import os
import shutil
from datetime import datetime

from app.models import (
    ChatMessage, ChatResponse, UploadResponse, 
    ConnectionTestRequest, ConnectionTestResponse,
    OllamaModelsRequest, OllamaModelsResponse,
    EmbeddingSettings
)
from app.document_processor import DocumentProcessor
from app.vector_store import VectorStore
from app.rag_engine import RAGEngine
from app.providers.openai_provider import OpenAILLMProvider, OpenAIEmbeddingProvider
from app.providers.ollama_provider import OllamaLLMProvider
from app.providers.sentence_transformer_provider import SentenceTransformerProvider
from app.config import DOCUMENTS_PATH, OPENAI_MODELS, OLLAMA_MODELS

# Initialize FastAPI app
app = FastAPI(title="Personal Knowledge Base with Multi-Provider Support", version="2.0.0")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Initialize components
vector_store = VectorStore()
document_processor = DocumentProcessor()
rag_engine = RAGEngine(vector_store)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main web interface"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and process a document (txt, md, or pdf)
    """
    # Validate file type
    if not file.filename.endswith(('.txt', '.md', '.pdf')):
        raise HTTPException(status_code=400, detail="Only .txt, .md, and .pdf files are supported")
    
    try:
        # Check if embedding provider is set
        if vector_store.embedding_provider is None:
            raise HTTPException(
                status_code=400, 
                detail="Please select an embedding provider before uploading documents"
            )
        
        # Generate unique document ID
        doc_id = str(uuid.uuid4())
        
        # Save uploaded file
        file_path = os.path.join(DOCUMENTS_PATH, f"{doc_id}_{file.filename}")
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Process document into chunks
        chunks = document_processor.process_document(file_path, doc_id, file.filename)
        
        # Add chunks to vector store
        vector_store.add_documents(chunks)
        
        return UploadResponse(
            doc_id=doc_id,
            filename=file.filename,
            num_chunks=len(chunks),
            message=f"Successfully uploaded and processed {file.filename}"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
async def chat(chat_message: ChatMessage):
    """
    Chat with the knowledge base
    """
    try:
        # Generate conversation ID if not provided
        conversation_id = chat_message.conversation_id or str(uuid.uuid4())
        
        # Get answer from RAG engine with settings
        answer, sources, rewritten_query, settings = rag_engine.chat(
            chat_message.message, 
            conversation_id,
            chat_message.settings
        )
        
        return ChatResponse(
            answer=answer,
            sources=sources,
            conversation_id=conversation_id,
            rewritten_query=rewritten_query,
            settings=settings
        )
    
    except Exception as e:
        error_msg = str(e)
        if "Query rewriting failed" in error_msg or "Answer generation failed" in error_msg:
            raise HTTPException(status_code=500, detail=error_msg)
        else:
            raise HTTPException(status_code=500, detail=f"Error generating response: {error_msg}")

@app.get("/documents")
async def list_documents():
    """Get list of all uploaded documents"""
    try:
        documents = vector_store.get_all_documents()
        return {"documents": documents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document from the knowledge base"""
    try:
        vector_store.delete_document(doc_id)
        
        # Delete file from disk
        for filename in os.listdir(DOCUMENTS_PATH):
            if filename.startswith(doc_id):
                os.remove(os.path.join(DOCUMENTS_PATH, filename))
                break
        
        return {"message": f"Document {doc_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

@app.post("/reset")
async def reset_knowledge_base():
    """Reset the entire knowledge base"""
    try:
        vector_store.reset()
        
        # Delete all document files
        for filename in os.listdir(DOCUMENTS_PATH):
            file_path = os.path.join(DOCUMENTS_PATH, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
        
        # Reset all conversations
        rag_engine.conversations = {}
        
        return {"message": "Knowledge base reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting knowledge base: {str(e)}")

# New endpoints for multi-provider support

@app.get("/config/models")
async def get_available_models():
    """Get available models for all providers"""
    return {
        "openai": OPENAI_MODELS,
        "ollama": OLLAMA_MODELS
    }

@app.post("/config/test-connection", response_model=ConnectionTestResponse)
async def test_connection(request: ConnectionTestRequest):
    """Test connection to a provider"""
    try:
        if request.provider == "openai":
            provider = OpenAILLMProvider(model=request.model)
            success, message = provider.test_connection()
            return ConnectionTestResponse(success=success, message=message)
            
        elif request.provider == "ollama":
            if not request.ollama_url:
                return ConnectionTestResponse(success=False, message="Ollama URL is required")
            
            provider = OllamaLLMProvider(base_url=request.ollama_url, model=request.model)
            success, message = provider.test_connection()
            return ConnectionTestResponse(success=success, message=message)
            
        else:
            return ConnectionTestResponse(success=False, message=f"Unknown provider: {request.provider}")
            
    except Exception as e:
        return ConnectionTestResponse(success=False, message=f"Connection test failed: {str(e)}")

@app.post("/config/ollama-models", response_model=OllamaModelsResponse)
async def get_ollama_models(request: OllamaModelsRequest):
    """Get available models from Ollama instance"""
    try:
        success, models, error_msg = OllamaLLMProvider.list_available_models(request.ollama_url)
        return OllamaModelsResponse(success=success, models=models, message=error_msg if not success else "")
    except Exception as e:
        return OllamaModelsResponse(success=False, models=[], message=str(e))

@app.get("/config/embedding")
async def get_embedding_config():
    """Get current embedding configuration"""
    settings = vector_store.get_embedding_settings()
    is_locked = vector_store.is_locked()
    
    return {
        "settings": settings.model_dump() if settings else None,
        "is_locked": is_locked
    }

@app.post("/config/embedding")
async def set_embedding_config(provider: str, model: str = None):
    """Set embedding provider configuration"""
    try:
        if vector_store.is_locked():
            raise HTTPException(
                status_code=400,
                detail="Cannot change embedding provider after documents have been uploaded. Please reset the knowledge base first."
            )
        
        settings = vector_store.set_embedding_provider(provider, model)
        return {"success": True, "settings": settings.model_dump()}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/config/test-embedding")
async def test_embedding_provider(provider: str, model: str = None):
    """Test embedding provider connection"""
    try:
        if provider == "openai":
            test_model = model or "text-embedding-3-small"
            provider_obj = OpenAIEmbeddingProvider(model=test_model)
        elif provider == "sentence-transformers":
            test_model = model or "all-MiniLM-L6-v2"
            provider_obj = SentenceTransformerProvider(model_name=test_model)
        else:
            return {"success": False, "message": f"Unknown embedding provider: {provider}"}
        
        success, message = provider_obj.test_connection()
        return {"success": success, "message": message}
        
    except Exception as e:
        return {"success": False, "message": f"Test failed: {str(e)}"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    embedding_settings = vector_store.get_embedding_settings()
    
    return {
        "status": "healthy",
        "total_chunks": len(vector_store.chunks),
        "total_documents": len(vector_store.get_all_documents()),
        "active_conversations": len(rag_engine.conversations),
        "embedding_provider": embedding_settings.provider if embedding_settings else None,
        "embedding_locked": vector_store.is_locked()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
