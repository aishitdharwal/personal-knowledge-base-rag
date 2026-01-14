from typing import List, Dict
from openai import OpenAI
from app.providers.base import LLMProvider, EmbeddingProvider
from app.config import OPENAI_API_KEY

class OpenAILLMProvider(LLMProvider):
    """OpenAI LLM provider implementation"""
    
    def __init__(self, model: str = "gpt-4"):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = model
    
    def generate(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int = 1000) -> str:
        """Generate response using OpenAI API"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    def test_connection(self) -> tuple[bool, str]:
        """Test OpenAI API connection"""
        try:
            # Simple test with minimal tokens
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            return True, f"Connected to OpenAI ({self.model})"
        except Exception as e:
            return False, f"OpenAI connection failed: {str(e)}"

class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider implementation"""
    
    def __init__(self, model: str = "text-embedding-3-small"):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = model
        # OpenAI embedding dimensions
        self._dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536
        }
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API"""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            raise Exception(f"OpenAI embedding error: {str(e)}")
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        return self._dimensions.get(self.model, 1536)
    
    def test_connection(self) -> tuple[bool, str]:
        """Test OpenAI embedding API connection"""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=["test"]
            )
            return True, f"Connected to OpenAI Embeddings ({self.model})"
        except Exception as e:
            return False, f"OpenAI embedding connection failed: {str(e)}"
