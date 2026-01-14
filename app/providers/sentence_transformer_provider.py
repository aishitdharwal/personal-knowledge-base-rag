from typing import List
from sentence_transformers import SentenceTransformer
from app.providers.base import EmbeddingProvider
from app.config import SENTENCE_TRANSFORMER_MODEL

class SentenceTransformerProvider(EmbeddingProvider):
    """Sentence Transformers embedding provider for local embeddings"""
    
    def __init__(self, model_name: str = SENTENCE_TRANSFORMER_MODEL):
        self.model_name = model_name
        self.model = None
        self._dimension = None
        self._load_model()
    
    def _load_model(self):
        """Load the sentence transformer model"""
        try:
            self.model = SentenceTransformer(self.model_name)
            # Get dimension from model
            self._dimension = self.model.get_sentence_embedding_dimension()
            print(f"[SentenceTransformer] Loaded model '{self.model_name}' with dimension {self._dimension}")
        except Exception as e:
            raise Exception(f"Failed to load Sentence Transformer model: {str(e)}")
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Sentence Transformers"""
        try:
            if self.model is None:
                self._load_model()
            
            # Generate embeddings
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            
            # Convert to list of lists
            return embeddings.tolist()
            
        except Exception as e:
            raise Exception(f"Sentence Transformer embedding error: {str(e)}")
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        if self._dimension is None:
            if self.model is None:
                self._load_model()
            self._dimension = self.model.get_sentence_embedding_dimension()
        return self._dimension
    
    def test_connection(self) -> tuple[bool, str]:
        """Test if the model can be loaded and used"""
        try:
            if self.model is None:
                self._load_model()
            
            # Test embedding generation
            test_embedding = self.model.encode(["test"], convert_to_numpy=True)
            
            if test_embedding is not None and len(test_embedding) > 0:
                return True, f"Sentence Transformer loaded ({self.model_name}, dim={self._dimension})"
            else:
                return False, "Model loaded but failed to generate embeddings"
                
        except Exception as e:
            return False, f"Sentence Transformer test failed: {str(e)}"
