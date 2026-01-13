import faiss
import numpy as np
import json
import os
from typing import List, Tuple
from openai import OpenAI
from app.models import DocumentChunk
from app.config import (
    OPENAI_API_KEY, 
    EMBEDDING_MODEL, 
    FAISS_INDEX_PATH, 
    METADATA_PATH
)

class VectorStore:
    """Manages FAISS vector store for document embeddings"""
    
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.index = None
        self.chunks = []
        self.dimension = 1536  # OpenAI embedding dimension
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        """Load existing FAISS index or create a new one"""
        index_file = os.path.join(FAISS_INDEX_PATH, "index.faiss")
        
        if os.path.exists(index_file) and os.path.exists(METADATA_PATH):
            # Load existing index and metadata
            self.index = faiss.read_index(index_file)
            with open(METADATA_PATH, 'r') as f:
                metadata = json.load(f)
                self.chunks = [DocumentChunk(**chunk) for chunk in metadata['chunks']]
            print(f"Loaded existing index with {len(self.chunks)} chunks")
        else:
            # Create new index
            self.index = faiss.IndexFlatL2(self.dimension)
            self.chunks = []
            print("Created new FAISS index")
    
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
    
    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a list of texts using OpenAI"""
        response = self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts
        )
        embeddings = [item.embedding for item in response.data]
        return np.array(embeddings, dtype=np.float32)
    
    def add_documents(self, chunks: List[DocumentChunk]):
        """
        Add document chunks to the vector store
        
        Args:
            chunks: List of DocumentChunk objects to add
        """
        if not chunks:
            return
        
        # Extract text from chunks
        texts = [chunk.text for chunk in chunks]
        
        # Generate embeddings
        embeddings = self._get_embeddings(texts)
        
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
        if self.index.ntotal == 0:
            return []
        
        # Generate query embedding
        query_embedding = self._get_embeddings([query])
        
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
        self.index = faiss.IndexFlatL2(self.dimension)
        self.chunks = []
        
        if remaining_chunks:
            self.add_documents(remaining_chunks)
        else:
            self._save_index()
        
        print(f"Deleted document {doc_id}")
    
    def reset(self):
        """Reset the entire vector store"""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.chunks = []
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
