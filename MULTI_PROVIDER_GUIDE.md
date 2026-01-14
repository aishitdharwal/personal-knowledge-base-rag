# Multi-Provider RAG System - Implementation Complete! 🎉

## Overview
The Personal Knowledge Base now supports multiple LLM and embedding providers with per-conversation settings.

## ✅ Features Implemented

### 1. **Multiple LLM Providers**
- ✅ OpenAI (GPT-4, GPT-4-turbo, GPT-3.5-turbo)
- ✅ Ollama (Self-hosted SLMs: llama3.2, mistral, etc.)
- ✅ Per-conversation provider selection
- ✅ Connection testing for all providers

### 2. **Multiple Embedding Providers**
- ✅ OpenAI Embeddings (text-embedding-3-small, text-embedding-3-large)
- ✅ Sentence Transformers (Local: all-MiniLM-L6-v2, all-mpnet-base-v2)
- ✅ Locked after first document upload
- ✅ Can only change after reset

### 3. **Query Rewriting**
- ✅ Separate provider selection for query rewriting
- ✅ Can use OpenAI or Ollama
- ✅ Option to disable completely
- ✅ Per-conversation rewrite settings

### 4. **Advanced UI**
- ✅ Settings modal (gear icon) for global defaults
- ✅ Per-conversation settings with visible display
- ✅ Embedding selection modal on first upload
- ✅ Connection testing buttons
- ✅ Dynamic Ollama model loading
- ✅ Settings persistence in localStorage

### 5. **PDF Support**
- ✅ Upload and process PDF files
- ✅ Text extraction with PyPDF2
- ✅ Page markers for context

## 🚀 How to Use

### Installation

1. **Install new dependencies:**
```bash
pip install -r requirements.txt
```

The new dependencies are:
- `requests` - For Ollama API calls
- `sentence-transformers` - For local embeddings
- `torch` - Required by sentence-transformers

2. **Set up Ollama (Optional - for self-hosted SLM):**
```bash
# On your EC2 instance or local machine
curl https://ollama.ai/install.sh | sh
ollama pull llama3.2
ollama serve
```

3. **Start the application:**
```bash
python run.py
```

### First Time Setup

1. **Open the app** at http://localhost:8000

2. **Click the gear icon (⚙️)** to open settings

3. **Select Embedding Provider** (CRITICAL - Do this first!):
   - Choose OpenAI or Sentence Transformers
   - Select model
   - Test connection
   - Save

4. **Set Default LLM Settings**:
   - Answer Provider: OpenAI or Ollama
   - Query Rewriting: OpenAI, Ollama, or Disabled
   - Test connections
   - Save defaults

5. **Upload Documents**:
   - If no embedding provider is set, you'll be prompted
   - Once set, it's locked until you reset

### Using Different Providers

#### OpenAI (Cloud)
- Requires OpenAI API key in `.env`
- Higher quality, costs per usage
- Models: GPT-4, GPT-4-turbo, GPT-3.5-turbo

#### Ollama (Self-Hosted)
- Free to use
- Requires Ollama server running
- Enter IP address: `http://YOUR_EC2_IP:11434`
- Click "Load Models" to fetch available models
- Models: llama3.2, mistral, codellama, etc.

#### Sentence Transformers (Local)
- Free, runs locally
- No API key required
- Good quality embeddings
- Models: all-MiniLM-L6-v2 (384 dim), all-mpnet-base-v2 (768 dim)

### Per-Conversation Settings

1. Start a new conversation
2. Click "Change" button in conversation settings bar
3. Select providers for this specific conversation
4. Settings persist for that conversation only

## 🎯 UI Guide

### Main Interface
- **Sidebar**: Upload documents, view document list
- **Chat Area**: Conversation with visible settings
- **Settings Icon (⚙️)**: Global configuration

### Settings Modal
- **Embedding Provider**: One-time selection (locked after upload)
- **Default LLM Settings**: Used for new conversations
- **Query Rewriting**: Separate provider or disable

### Conversation Settings
- Shows current providers being used
- "Change" button to override for this conversation
- Displays: "Using OpenAI (gpt-4) | Rewrite: openai"

## 📝 Configuration Files

### `.env`
```bash
OPENAI_API_KEY=sk-your-key-here
OLLAMA_URL=http://localhost:11434  # Optional default
```

### `app/config.py`
All default settings can be customized:
- Default providers
- Ollama models list
- Embedding models
- API endpoints

## 🔧 API Endpoints

### New Endpoints
- `GET /config/models` - Get available models
- `POST /config/test-connection` - Test LLM provider
- `POST /config/ollama-models` - List Ollama models
- `GET /config/embedding` - Get embedding config
- `POST /config/embedding` - Set embedding provider
- `POST /config/test-embedding` - Test embedding provider

### Updated Endpoints
- `POST /chat` - Now accepts `settings` parameter
- `POST /upload` - Checks for embedding provider

## 🏗️ Architecture

### Backend Structure
```
app/
├── providers/
│   ├── base.py                    # Abstract classes
│   ├── openai_provider.py         # OpenAI implementations
│   ├── ollama_provider.py         # Ollama implementations
│   └── sentence_transformer_provider.py
├── main.py                        # FastAPI with new endpoints
├── rag_engine.py                  # Multi-provider RAG
├── vector_store.py                # Multi-embedding vector store
└── config.py                      # Provider configurations
```

### Provider Pattern
- Abstract base classes for LLM and Embedding
- Concrete implementations for each provider
- Easy to add new providers (e.g., Anthropic, Cohere)

## 🎨 UI Components

### Modals
1. **Settings Modal**: Global configuration
2. **Conversation Settings Modal**: Per-conversation overrides
3. **Embedding Selection Modal**: First-time embedding choice

### Features
- Connection testing with visual feedback
- Dynamic model loading from Ollama
- Settings persistence in localStorage
- Error handling with retry options

## ⚠️ Important Notes

### Embedding Provider Lock
- **Cannot change** after uploading documents
- Different embedding dimensions are incompatible
- Must reset knowledge base to switch
- Warning shown in UI when locked

### Ollama Connection
- Must be reachable from the app
- Test connection before using
- Manual retry if connection fails
- IP address can be changed per conversation

### Query Rewriting
- Can be disabled per conversation
- Uses separate provider from answer generation
- Lower temperature (0.2) for consistency

## 🐛 Troubleshooting

### "Cannot connect to Ollama"
1. Check Ollama is running: `ollama serve`
2. Verify IP address is correct
3. Test connection in settings
4. Check firewall allows port 11434

### "Embedding provider not set"
1. Click gear icon
2. Select embedding provider
3. Test connection
4. Save before uploading

### "Model not found in Ollama"
1. Click "Load Models" to refresh
2. Pull model: `ollama pull llama3.2`
3. Verify model name matches exactly

### Sentence Transformers loading slow
- First time downloads model (~100MB)
- Subsequent runs are fast
- Models cached in `~/.cache/huggingface/`

## 🚀 Next Steps

### Possible Enhancements
1. Add more providers (Anthropic Claude, Cohere)
2. Model fine-tuning support
3. Advanced chunking strategies
4. Multi-modal support (images in PDFs)
5. Conversation export/import
6. Usage analytics per provider

### Performance Optimization
1. Caching for embeddings
2. Batch processing for large documents
3. Async model loading
4. Connection pooling for Ollama

## 📊 Testing Checklist

- [ ] OpenAI LLM works
- [ ] Ollama LLM works  
- [ ] OpenAI embeddings work
- [ ] Sentence Transformers work
- [ ] Query rewriting with OpenAI
- [ ] Query rewriting with Ollama
- [ ] Query rewriting disabled
- [ ] Per-conversation settings persist
- [ ] Embedding lock after upload
- [ ] Connection tests all pass
- [ ] Dynamic Ollama model loading
- [ ] PDF upload works
- [ ] Settings save to localStorage
- [ ] Conversation settings display correctly

## 🎓 Example Workflow

1. **Setup Ollama on EC2**:
   ```bash
   ssh ec2-instance
   ollama pull llama3.2:3b
   ollama serve
   ```

2. **Configure App**:
   - Set Sentence Transformers for embeddings
   - Default Answer: OpenAI GPT-4
   - Default Rewrite: OpenAI GPT-3.5

3. **Upload Documents**:
   - Embedding provider gets locked
   - Documents processed with Sentence Transformers

4. **Chat with Different Models**:
   - Conversation 1: GPT-4 (high quality)
   - Conversation 2: Change to Ollama llama3.2 (free)
   - Conversation 3: GPT-4 with rewriting disabled

5. **Compare Providers**:
   - Test response quality
   - Compare speed
   - Check costs

---

**Congratulations! Your multi-provider RAG system is ready to use! 🎉**
