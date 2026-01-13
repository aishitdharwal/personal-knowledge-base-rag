import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-4"
QUERY_REWRITE_MODEL = "gpt-3.5-turbo"  # Cheaper model for query rewriting

# Chunking Configuration
CHUNK_SIZE = 1000  # characters
CHUNK_OVERLAP = 200  # characters

# Vector Store Configuration
FAISS_INDEX_PATH = "data/faiss_index"
METADATA_PATH = "data/metadata.json"
DOCUMENTS_PATH = "data/documents"

# RAG Configuration
TOP_K_RESULTS = 5  # Number of chunks to retrieve
MAX_CONVERSATION_HISTORY = 10  # Number of previous messages to keep in context
QUERY_REWRITE_HISTORY = 5  # Number of past Q&A pairs to use for query rewriting

# Ensure directories exist
os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
os.makedirs(DOCUMENTS_PATH, exist_ok=True)
os.makedirs("data", exist_ok=True)
