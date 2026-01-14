import faiss
import numpy as np
import json
import os
from typing import List, Tuple, Optional
from app.models import DocumentChunk, EmbeddingSettings
from app.providers.base import EmbeddingProvider
from app.providers.openai_provider import OpenAIEmbeddingProvider
from app.providers.sentence_transformer_provider import SentenceTransformerProvider
from app.config import (
    FAISS_INDEX_PATH, 
    METADATA_PATH,
    EMBEDDING_CONFIG_PATH,
    DEFAULT_EMBEDDING_PROVIDER
)

class VectorStore:
    """Manages FAISS vector store for document embeddings with multiple provider support"""
    
    def __init__(self):
        self.embedding_provider: Optional[EmbeddingProvider] = None
        self.embedding_settings: Optional[EmbeddingSettings] = None
        self.index = None
        self.chunks = []
        self.dimension = None
        self._load_or_create_index()
    
    def _load_embedding_config(self) -> Optional[EmbeddingSettings]:
        """Load embedding configuration from disk"""
        if os.path.exists(EMBEDDING_CONFIG_PATH):
            with open(EMBEDDING_CONFIG_PATH, 'r') as f:
                config = json.load(f)
                return EmbeddingSettings(**config)
        return None
    
    def _save_embedding_config(self, settings: EmbeddingSettings):
        """Save embedding configuration to disk"""
        with open(EMBEDDING_CONFIG_PATH, 'w') as f:
            json.dump(settings.model_dump(), f, indent=2)
    
    def _initialize_embedding_provider(self, settings: EmbeddingSettings):
        """Initialize the embedding provider based on settings"""
        if settings.provider == "openai":
            model = settings.model or "text-embedding-3-small"
            self.embedding_provider = OpenAIEmbeddingProvider(model=model)
        elif settings.provider == "sentence-transformers":
            model = settings.model or "all-MiniLM-L6-v2"
            self.embedding_provider = SentenceTransformerProvider(model_name=model)
        else:
            raise ValueError(f"Unknown embedding provider: {settings.provider}")
        
        self.embedding_settings = settings
        self.dimension = self.embedding_provider.get_dimension()
    
    def set_embedding_provider(self, provider: str, model: Optional[str] = None) -> EmbeddingSettings:
        """
        Set the embedding provider (can only be done before uploading documents)
        
        Args:
            provider: 'openai' or 'sentence-transformers'
            model: Specific model name (optional)
            
        Returns:
            EmbeddingSettings object
            
        Raises:
            Exception: If documents already exist
        """
        if len(self.chunks) > 0:
            raise Exception("Cannot change embedding provider after documents have been uploaded. Please reset the knowledge base first.")
        
        # Create temporary provider to get dimension
        if provider == "openai":
            model = model or "text-embedding-3-small"
            temp_provider = OpenAIEmbeddingProvider(model=model)
        elif provider == "sentence-transformers":
            model = model or "all-MiniLM-L6-v2"
            temp_provider = SentenceTransformerProvider(model_name=model)
        else:
            raise ValueError(f"Unknown embedding provider: {provider}")
        
        dimension = temp_provider.get_dimension()
        
        # Create settings
        settings = EmbeddingSettings(
            provider=provider,
            model=model,
            dimension=dimension
        )
        
        # Initialize provider
        self._initialize_embedding_provider(settings)
        
        # Save configuration
        self._save_embedding_config(settings)
        
        # Recreate index with correct dimension
        self.index = faiss.IndexFlatL2(self.dimension)
        
        print(f"Embedding provider set to {provider} (model: {model}, dimension: {dimension})")
        return settings
    
    def get_embedding_settings(self) -> Optional[EmbeddingSettings]:
        """Get current embedding settings"""
        return self.embedding_settings
    
    def is_locked(self) -> bool:
        """Check if embedding provider is locked (documents exist)"""
        return len(self.chunks) > 0
    
    def _load_or_create_index(self):
        """Load existing FAISS index or create a new one"""
        index_file = os.path.join(FAISS_INDEX_PATH, "index.faiss")
        
        # Load embedding configuration
        self.embedding_settings = self._load_embedding_config()
        
        if os.path.exists(index_file) and os.path.exists(METADATA_PATH) and self.embedding_settings:
            # Load existing index and metadata
            self.index = faiss.read_index(index_file)
            with open(METADATA_PATH, 'r') as f:
                metadata = json.load(f)
                self.chunks = [DocumentChunk(**chunk) for chunk in metadata['chunks']]
            
            # Initialize embedding provider
            self._initialize_embedding_provider(self.embedding_settings)
            
            print(f"Loaded existing index with {len(self.chunks)} chunks using {self.embedding_settings.provider}")
        else:
            # No existing index - will be created when embedding provider is set
            print("No existing index found. Please set embedding provider before uploading documents.")
    
    def _save_index(self):
        """Save FAISS index and metadata to disk"""
        index_file = os.path.join(FAISS_INDEX_PATH, "index.faiss")
        faiss.write_index(self.index, index_file)
        
        # Save metadata
        metadata = {
            'chunks': [chunk.model_dump() for chunk in self.chunks]
        }
        with open(METADATA_PATH, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"Saved index with {len(self.chunks)} chunks")
    
    def add_documents(self, chunks: List[DocumentChunk]):
        """
        Add document chunks to the vector store
        
        Args:
            chunks: List of DocumentChunk objects to add
        """
        if not chunks:
            return
        
        # Check if embedding provider is set
        if self.embedding_provider is None:
            raise Exception("Embedding provider not set. Please set embedding provider before uploading documents.")
        
        # Extract text from chunks
        texts = [chunk.text for chunk in chunks]
        
        # Generate embeddings
        embeddings_list = self.embedding_provider.embed(texts)
        embeddings = np.array(embeddings_list, dtype=np.float32)
        
        # Add to FAISS index
        self.index.add(embeddings)
        
        # Store chunks metadata
        self.chunks.extend(chunks)
        
        # Save to disk
        self._save_index()
        
        print(f"Added {len(chunks)} chunks to vector store")
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[DocumentChunk, float]]:
        """
        Search for similar chunks using semantic search
        
        Args:
            query: Search query text
            top_k: Number of results to return
            
        Returns:
            List of tuples (DocumentChunk, similarity_score)
        """
        if self.index is None or self.index.ntotal == 0:
            return []
        
        if self.embedding_provider is None:
            raise Exception("Embedding provider not initialized")
        
        # Generate query embedding
        query_embeddings = self.embedding_provider.embed([query])
        query_embedding = np.array(query_embeddings, dtype=np.float32)
        
        # Search FAISS index
        distances, indices = self.index.search(query_embedding, min(top_k, self.index.ntotal))
        
        # Prepare results
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx < len(self.chunks):
                results.append((self.chunks[idx], float(distance)))
        
        return results
    
    def delete_document(self, doc_id: str):
        """
        Delete all chunks for a specific document
        Note: FAISS doesn't support deletion, so we rebuild the index
        
        Args:
            doc_id: Document ID to delete
        """
        # Filter out chunks from the document
        remaining_chunks = [chunk for chunk in self.chunks if chunk.doc_id != doc_id]
        
        if len(remaining_chunks) == len(self.chunks):
            print(f"No chunks found for document {doc_id}")
            return
        
        # Rebuild index with remaining chunks
        if self.embedding_provider and self.dimension:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.chunks = []
            
            if remaining_chunks:
                self.add_documents(remaining_chunks)
            else:
                self._save_index()
        
        print(f"Deleted document {doc_id}")
    
    def reset(self):
        """Reset the entire vector store including embedding configuration"""
        if self.dimension:
            self.index = faiss.IndexFlatL2(self.dimension)
        self.chunks = []
        
        # Clear embedding configuration
        if os.path.exists(EMBEDDING_CONFIG_PATH):
            os.remove(EMBEDDING_CONFIG_PATH)
        
        self.embedding_provider = None
        self.embedding_settings = None
        
        self._save_index()
        print("Vector store reset")
    
    def get_all_documents(self) -> List[dict]:
        """Get list of all unique documents in the store"""
        docs = {}
        for chunk in self.chunks:
            if chunk.doc_id not in docs:
                docs[chunk.doc_id] = {
                    'doc_id': chunk.doc_id,
                    'doc_name': chunk.doc_name,
                    'num_chunks': 0
                }
            docs[chunk.doc_id]['num_chunks'] += 1
        
        return list(docs.values())
