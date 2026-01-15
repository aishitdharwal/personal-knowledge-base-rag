from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List
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
from app.rag_engine import RAGEngine
from app.providers.openai_provider import OpenAILLMProvider, OpenAIEmbeddingProvider
from app.providers.ollama_provider import OllamaLLMProvider
from app.providers.sentence_transformer_provider import SentenceTransformerProvider
from app.config import DOCUMENTS_PATH, OPENAI_MODELS, OLLAMA_MODELS

# Initialize FastAPI app
app = FastAPI(title="Personal Knowledge Base with Multi-Provider Support", version="2.0.0")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Initialize components - Use PostgreSQL if enabled, otherwise FAISS
USE_POSTGRES = os.getenv('USE_POSTGRES', 'false').lower() == 'true'

if USE_POSTGRES:
    print("Using PostgreSQL with pgvector for vector storage")
    from app.vector_store_postgres import PostgresVectorStore
    vector_store = PostgresVectorStore()
else:
    print("Using FAISS for vector storage")
    from app.vector_store import VectorStore
    vector_store = VectorStore()

document_processor = DocumentProcessor()
rag_engine = RAGEngine(vector_store)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main web interface"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/manage", response_class=HTMLResponse)
async def manage_documents(request: Request):
    """Serve the document management interface"""
    return templates.TemplateResponse("manage.html", {"request": request})

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

@app.get("/config/ocr-status")
async def get_ocr_status():
    """Get OCR availability and configuration status"""
    return document_processor.get_ocr_status()

# Conversation management endpoints

@app.get("/conversations")
async def list_conversations():
    """Get all conversations with metadata"""
    try:
        conversations = rag_engine.get_all_conversations()
        return {"conversations": conversations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing conversations: {str(e)}")

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all messages"""
    try:
        conversation = rag_engine.get_conversation(conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Convert LLMSettings to dict if present
        if conversation.get('settings'):
            conversation['settings'] = conversation['settings'].dict()

        return conversation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting conversation: {str(e)}")

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a specific conversation"""
    try:
        success = rag_engine.delete_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"message": "Conversation deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting conversation: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    embedding_settings = vector_store.get_embedding_settings()
    ocr_status = document_processor.get_ocr_status()

    # Get document count
    all_docs = vector_store.get_all_documents()
    total_docs = len(all_docs)
    total_chunks = sum(doc['num_chunks'] for doc in all_docs)

    return {
        "status": "healthy",
        "total_chunks": total_chunks,
        "total_documents": total_docs,
        "active_conversations": len(rag_engine.conversations),
        "embedding_provider": embedding_settings.provider if embedding_settings else None,
        "embedding_locked": vector_store.is_locked(),
        "ocr_enabled": ocr_status['ocr_enabled'],
        "ocr_engine": ocr_status.get('engine'),
        "textract_available": ocr_status['textract_available'],
        "vector_store_type": "PostgreSQL" if USE_POSTGRES else "FAISS"
    }

# New endpoints for enhanced document management

@app.get("/documents/{doc_id}/details")
async def get_document_details(doc_id: str):
    """Get detailed information about a document including all chunks"""
    try:
        # Get all chunks for this document
        chunks = [chunk for chunk in vector_store.chunks if chunk.doc_id == doc_id]

        if not chunks:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

        # Get file info
        file_path = None
        file_size = 0
        for filename in os.listdir(DOCUMENTS_PATH):
            if filename.startswith(doc_id):
                file_path = os.path.join(DOCUMENTS_PATH, filename)
                file_size = os.path.getsize(file_path)
                break

        return {
            "doc_id": doc_id,
            "doc_name": chunks[0].doc_name,
            "num_chunks": len(chunks),
            "file_size": file_size,
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char
                }
                for chunk in sorted(chunks, key=lambda x: x.chunk_id)
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting document details: {str(e)}")

@app.get("/documents/{doc_id}/download")
async def download_document(doc_id: str):
    """Download the original document file"""
    try:
        # Find the file
        file_path = None
        original_filename = None

        for filename in os.listdir(DOCUMENTS_PATH):
            if filename.startswith(doc_id):
                file_path = os.path.join(DOCUMENTS_PATH, filename)
                # Extract original filename (format: {doc_id}_{original_filename})
                original_filename = filename[len(doc_id) + 1:]
                break

        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

        return FileResponse(
            path=file_path,
            filename=original_filename,
            media_type='application/octet-stream'
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading document: {str(e)}")

@app.post("/documents/batch-delete")
async def batch_delete_documents(doc_ids: List[str]):
    """Delete multiple documents at once"""
    try:
        deleted = []
        errors = []

        for doc_id in doc_ids:
            try:
                vector_store.delete_document(doc_id)

                # Delete file from disk
                for filename in os.listdir(DOCUMENTS_PATH):
                    if filename.startswith(doc_id):
                        os.remove(os.path.join(DOCUMENTS_PATH, filename))
                        break

                deleted.append(doc_id)
            except Exception as e:
                errors.append({"doc_id": doc_id, "error": str(e)})

        return {
            "message": f"Successfully deleted {len(deleted)} document(s)",
            "deleted": deleted,
            "errors": errors
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in batch delete: {str(e)}")

@app.post("/upload-batch")
async def upload_batch_documents(files: List[UploadFile] = File(...)):
    """Upload and process multiple documents at once"""
    results = []

    for file in files:
        try:
            # Validate file type
            if not file.filename.endswith(('.txt', '.md', '.pdf')):
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": "Only .txt, .md, and .pdf files are supported"
                })
                continue

            # Check if embedding provider is set
            if vector_store.embedding_provider is None:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": "Please select an embedding provider before uploading documents"
                })
                continue

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

            results.append({
                "filename": file.filename,
                "success": True,
                "doc_id": doc_id,
                "num_chunks": len(chunks)
            })

        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })

    successful = sum(1 for r in results if r.get("success"))
    return {
        "message": f"Processed {successful}/{len(files)} files successfully",
        "results": results
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
