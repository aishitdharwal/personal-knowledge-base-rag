from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
import os
import shutil
from datetime import datetime

from app.models import ChatMessage, ChatResponse, UploadResponse
from app.document_processor import DocumentProcessor
from app.vector_store import VectorStore
from app.rag_engine import RAGEngine
from app.config import DOCUMENTS_PATH

# Initialize FastAPI app
app = FastAPI(title="Personal Knowledge Base", version="1.0.0")

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
        
        # Get answer from RAG engine (includes query rewriting)
        answer, sources, rewritten_query = rag_engine.chat(chat_message.message, conversation_id)
        
        return ChatResponse(
            answer=answer,
            sources=sources,
            conversation_id=conversation_id,
            rewritten_query=rewritten_query
        )
    
    except Exception as e:
        # If it's a query rewriting error, return with specific message
        error_msg = str(e)
        if "Query rewriting failed" in error_msg:
            raise HTTPException(status_code=500, detail=f"Failed to process your query: {error_msg}")
        else:
            raise HTTPException(status_code=500, detail=f"Error generating response: {error_msg}")

@app.get("/documents")
async def list_documents():
    """
    Get list of all uploaded documents
    """
    try:
        documents = vector_store.get_all_documents()
        return {"documents": documents}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """
    Delete a document from the knowledge base
    """
    try:
        # Delete from vector store
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
    """
    Reset the entire knowledge base (delete all documents and vectors)
    """
    try:
        # Reset vector store
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

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "total_chunks": len(vector_store.chunks),
        "total_documents": len(vector_store.get_all_documents()),
        "active_conversations": len(rag_engine.conversations)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
