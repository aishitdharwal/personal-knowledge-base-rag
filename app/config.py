import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# AWS Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Default LLM Provider Settings
DEFAULT_ANSWER_PROVIDER = "openai"  # 'openai' or 'ollama'
DEFAULT_ANSWER_MODEL = "gpt-4"
DEFAULT_REWRITE_PROVIDER = "openai"  # 'openai', 'ollama', or 'disabled'
DEFAULT_REWRITE_MODEL = "gpt-3.5-turbo"
DEFAULT_EMBEDDING_PROVIDER = "openai"  # 'openai' or 'sentence-transformers'

# OpenAI Models
OPENAI_MODELS = {
    "answer": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
    "rewrite": ["gpt-3.5-turbo", "gpt-4"],
    "embedding": ["text-embedding-3-small", "text-embedding-3-large"]
}

# Ollama Configuration
DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODELS = [
    "llama3.2",
    "llama3.2:3b", 
    "llama3.2:1b",
    "llama3.1",
    "mistral",
    "mixtral",
    "codellama",
    "phi3"
]

# Sentence Transformers Configuration
SENTENCE_TRANSFORMER_MODEL = "all-MiniLM-L6-v2"  # 384 dimensions

# OCR Configuration
OCR_ENABLED = True  # Enable OCR for scanned PDFs and images
OCR_PRIMARY = "textract"  # 'textract' or 'easyocr' - AWS Textract is cloud-based, high quality
OCR_FALLBACK = None  # No fallback - Textract is reliable enough
OCR_MIN_TEXT_LENGTH = 100  # Minimum text length before triggering OCR
OCR_LANGUAGES = ['en']  # Languages for OCR

# AWS Textract Configuration
TEXTRACT_MAX_PAGES = 100  # Maximum pages to process with Textract (cost control)
TEXTRACT_TIMEOUT = 300  # Timeout in seconds for Textract API calls

# Chunking Configuration
CHUNK_SIZE = 1000  # characters
CHUNK_OVERLAP = 200  # characters

# Vector Store Configuration
FAISS_INDEX_PATH = "data/faiss_index"
METADATA_PATH = "data/metadata.json"
DOCUMENTS_PATH = "data/documents"
EMBEDDING_CONFIG_PATH = "data/embedding_config.json"

# RAG Configuration
TOP_K_RESULTS = 5  # Number of chunks to retrieve
MAX_CONVERSATION_HISTORY = 10  # Number of previous messages to keep in context
QUERY_REWRITE_HISTORY = 5  # Number of past Q&A pairs to use for query rewriting

# Ensure directories exist
os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
os.makedirs(DOCUMENTS_PATH, exist_ok=True)
os.makedirs("data", exist_ok=True)
