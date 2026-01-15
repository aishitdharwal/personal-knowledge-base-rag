# Personal Knowledge Base with Conversational RAG

An intelligent knowledge assistant that ingests documents (txt/md/pdf), performs semantic search, and enables natural conversations with source citations.

## Features

### Document Management
- **Batch Upload**: Drag-and-drop or select multiple files (txt, md, pdf)
- **PDF Processing**: Text extraction with optional OCR via AWS Textract
- **Search & Filter**: Real-time search and sorting by name or chunk count
- **Bulk Operations**: Select and delete multiple documents at once
- **Document Details**: View all chunks and metadata for any document
- **Download**: Retrieve original uploaded files

### Conversational RAG
- **Query Rewriting**: Contextual query reformulation for better retrieval
- **Semantic Search**: FAISS or PostgreSQL+pgvector vector similarity search
- **Multi-Provider Support**: OpenAI or Ollama (local) LLMs
- **Conversation Memory**: Multi-turn dialogue with context awareness
- **Source Citations**: Precise document and chunk-level citations
- **Persistent Storage**: FAISS index and document metadata persistence

### Web Interface
- **Main Chat Page** (`/`) - Clean interface for querying documents
- **Document Management** (`/manage`) - Dedicated page for file management

## Tech Stack

- **Backend**: FastAPI
- **Frontend**: FastAPI Templates + HTML
- **Vector Store**: FAISS (persistent)
- **LLM**: GPT-4 (OpenAI)
- **Embeddings**: OpenAI text-embedding-3-small
- **Chunking**: Fixed-size chunking with overlap

## Project Structure

```
personal-knowledge-assistant-v2/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── models.py               # Pydantic models
│   ├── document_processor.py   # Document chunking and processing
│   ├── vector_store.py         # FAISS vector store operations
│   ├── rag_engine.py           # RAG pipeline with conversation memory
│   └── config.py               # Configuration
├── templates/
│   ├── index.html              # Main chat page
│   └── manage.html             # Document management page
├── data/
│   ├── documents/              # Uploaded documents
│   ├── faiss_index/            # FAISS index files
│   └── metadata.json           # Document metadata
├── requirements.txt
└── README.md
```

## Setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Set environment variables**:
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

3. **Run the application**:
```bash
python run.py
```

4. **Access the application**:
```
Main Chat: http://localhost:8000
Document Management: http://localhost:8000/manage
```

## API Endpoints

### Pages
- `GET /` - Main chat interface
- `GET /manage` - Document management interface

### Document Operations
- `POST /upload` - Upload single document
- `POST /upload-batch` - Upload multiple documents
- `GET /documents` - List all documents
- `GET /documents/{doc_id}/details` - Get document details with chunks
- `GET /documents/{doc_id}/download` - Download original file
- `DELETE /documents/{doc_id}` - Delete a document
- `POST /documents/batch-delete` - Delete multiple documents
- `POST /reset` - Reset entire knowledge base

### Chat Operations
- `POST /chat` - Chat with your knowledge base

### Configuration
- `GET /config/embedding` - Get embedding provider settings
- `POST /config/embedding` - Set embedding provider
- `POST /config/test-connection` - Test LLM provider connection
- `GET /health` - System health check

## Usage

1. **Manage Documents**:
   - Click "📚 Manage Documents" button or visit `/manage`
   - Drag-and-drop files or click "Choose Files"
   - Upload single or multiple files
   - Search, sort, view details, download, or delete documents

2. **Chat with Documents**:
   - Go to main page (`/`)
   - Ask questions about your documents
   - Get answers with precise source citations
   - Start new conversations as needed
4. Have natural conversations with memory of previous exchanges

## How It Works

1. **Document Processing**: Documents are split into fixed-size chunks with overlap
2. **Embedding Generation**: Each chunk is embedded using OpenAI's embedding model
3. **Vector Storage**: Embeddings stored in FAISS for fast similarity search
4. **Retrieval**: User query is embedded and similar chunks are retrieved
5. **Generation**: GPT-4 generates answers using retrieved context and conversation history
6. **Citations**: System provides document name and chunk references for transparency
