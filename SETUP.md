# Setup and Run Guide

## Quick Start

### 1. Install Dependencies

```bash
cd /Users/aishitdharwal/Documents/personal-knowledge-assistant-v2
pip install -r requirements.txt
```

### 2. Configure OpenAI API Key

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=sk-your-actual-key-here
```

### 3. Run the Application

**Option 1: Using the run script (Recommended)**
```bash
python run.py
```

**Option 2: Using uvicorn directly**
```bash
# From the project root directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
uvicorn app.main:app --reload
```

The application will start at: http://localhost:8000

## Using the Application

### Upload Documents
1. Click "Choose File" in the sidebar
2. Select a `.txt` or `.md` file
3. Click "Upload"
4. The document will be processed into chunks and embedded

### Chat with Your Knowledge Base
1. Type your question in the chat input
2. Press Enter or click "Send"
3. Get answers with source citations showing which documents were used

### Manage Documents
- View all uploaded documents in the sidebar
- See chunk count for each document
- Delete individual documents using the Delete button
- Reset entire knowledge base with "Reset All" button

## Features Explained

### Conversational Memory
- The system maintains conversation context
- You can ask follow-up questions naturally
- Reference previous messages in the conversation
- Each conversation has a unique ID for continuity

### Source Citations
- Every answer shows which documents were used
- See specific chunk IDs for transparency
- Preview text snippets from source chunks
- Similarity scores indicate relevance

### Document Processing
- Fixed-size chunking (1000 chars with 200 char overlap)
- Automatic embedding generation
- Persistent FAISS index storage
- Metadata tracking for all documents

## Configuration

Edit `app/config.py` to customize:

```python
CHUNK_SIZE = 1000           # Size of text chunks
CHUNK_OVERLAP = 200         # Overlap between chunks
TOP_K_RESULTS = 5           # Number of chunks to retrieve
MAX_CONVERSATION_HISTORY = 10  # Messages to keep in context
```

## API Endpoints

You can also interact with the system programmatically:

### Upload a Document
```bash
curl -X POST "http://localhost:8000/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.txt"
```

### Chat
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is this about?", "conversation_id": null}'
```

### List Documents
```bash
curl -X GET "http://localhost:8000/documents"
```

### Delete Document
```bash
curl -X DELETE "http://localhost:8000/documents/{doc_id}"
```

### Reset Knowledge Base
```bash
curl -X POST "http://localhost:8000/reset"
```

### Health Check
```bash
curl -X GET "http://localhost:8000/health"
```

## Troubleshooting

### Issue: "Module not found" errors
**Solution**: Make sure you're in the project directory and have installed all dependencies:
```bash
pip install -r requirements.txt
```

### Issue: "OpenAI API key not found"
**Solution**: Ensure your `.env` file exists and contains a valid API key:
```bash
export OPENAI_API_KEY=sk-your-key-here
```

### Issue: FAISS index corruption
**Solution**: Delete the data directory and restart:
```bash
rm -rf data/
uvicorn app.main:app --reload
```

### Issue: Out of memory errors
**Solution**: Reduce batch size or chunk size in `app/config.py`

## File Structure Overview

```
├── app/
│   ├── main.py              # FastAPI routes and app initialization
│   ├── models.py            # Pydantic models for request/response
│   ├── config.py            # Configuration settings
│   ├── document_processor.py # Text chunking logic
│   ├── vector_store.py      # FAISS operations and embeddings
│   └── rag_engine.py        # RAG pipeline with conversation memory
├── templates/
│   └── index.html           # Web interface
├── data/
│   ├── documents/           # Uploaded files (auto-created)
│   ├── faiss_index/         # FAISS index files (auto-created)
│   └── metadata.json        # Document metadata (auto-created)
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (create this)
└── README.md               # Project documentation
```

## Development Tips

### Adding New Features
- Document processing: Modify `document_processor.py`
- Vector search: Modify `vector_store.py`
- RAG logic: Modify `rag_engine.py`
- API endpoints: Modify `main.py`
- UI: Modify `templates/index.html`

### Testing Different Chunk Sizes
Edit `app/config.py`:
```python
CHUNK_SIZE = 500    # Smaller chunks = more granular
CHUNK_OVERLAP = 100 # More overlap = better context preservation
```

### Using Different Models
Edit `app/config.py`:
```python
EMBEDDING_MODEL = "text-embedding-3-large"  # More accurate embeddings
LLM_MODEL = "gpt-4-turbo"                   # Different LLM
```

## Production Considerations

For production deployment:

1. **Use environment variables** for all secrets
2. **Add authentication** to protect endpoints
3. **Implement rate limiting** to prevent abuse
4. **Add logging** for debugging and monitoring
5. **Use production ASGI server** like gunicorn
6. **Set up database** for metadata instead of JSON
7. **Add file upload limits** to prevent disk space issues
8. **Implement backup** for FAISS index and documents

## Next Steps

Consider adding:
- Multi-user support with authentication
- Advanced chunking strategies (semantic, hierarchical)
- Query expansion and reformulation
- Answer quality evaluation
- Export conversation history
- Batch document upload
- Document update/versioning
- Advanced search filters
- Integration with cloud storage
