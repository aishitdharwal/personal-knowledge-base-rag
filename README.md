# Personal Knowledge Base with Conversational RAG

An intelligent knowledge assistant that ingests documents (txt/md), performs semantic search, and enables natural conversations with source citations.

## Features

- **Document Ingestion**: Upload txt/md files with automatic processing
- **Semantic Search**: FAISS-based vector similarity search
- **Conversational RAG**: Natural conversations with GPT-4 and conversation memory
- **Source Citations**: Precise document and chunk-level citations
- **Persistent Storage**: FAISS index and document metadata persistence

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
│   └── index.html              # Frontend UI
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
http://localhost:8000
```

## API Endpoints

- `GET /` - Web interface
- `POST /upload` - Upload documents (txt/md)
- `POST /chat` - Chat with your knowledge base
- `GET /documents` - List all documents
- `DELETE /documents/{doc_id}` - Delete a document
- `POST /reset` - Reset entire knowledge base

## Usage

1. Upload your txt/md documents through the web interface
2. Start asking questions about your documents
3. Get answers with precise source citations
4. Have natural conversations with memory of previous exchanges

## How It Works

1. **Document Processing**: Documents are split into fixed-size chunks with overlap
2. **Embedding Generation**: Each chunk is embedded using OpenAI's embedding model
3. **Vector Storage**: Embeddings stored in FAISS for fast similarity search
4. **Retrieval**: User query is embedded and similar chunks are retrieved
5. **Generation**: GPT-4 generates answers using retrieved context and conversation history
6. **Citations**: System provides document name and chunk references for transparency
