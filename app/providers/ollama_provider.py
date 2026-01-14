from typing import List, Dict
import requests
from app.providers.base import LLMProvider

class OllamaLLMProvider(LLMProvider):
    """Ollama LLM provider implementation"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url.rstrip('/')
        self.model = model
    
    def generate(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int = 1000) -> str:
        """Generate response using Ollama API"""
        try:
            # Convert OpenAI-style messages to Ollama format
            prompt = self._messages_to_prompt(messages)
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                },
                timeout=120  # 2 minute timeout for generation
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API returned status {response.status_code}: {response.text}")
            
            result = response.json()
            return result.get('response', '')
            
        except requests.exceptions.Timeout:
            raise Exception("Ollama request timed out. The model might be too slow or the server is overloaded.")
        except requests.exceptions.ConnectionError:
            raise Exception(f"Cannot connect to Ollama at {self.base_url}. Please check the URL and ensure Ollama is running.")
        except Exception as e:
            raise Exception(f"Ollama API error: {str(e)}")
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert OpenAI-style messages to a single prompt string"""
        prompt_parts = []
        
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if role == 'system':
                prompt_parts.append(f"System: {content}")
            elif role == 'user':
                prompt_parts.append(f"User: {content}")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")
        
        prompt_parts.append("Assistant:")  # Prompt for the model to continue
        return "\n\n".join(prompt_parts)
    
    def test_connection(self) -> tuple[bool, str]:
        """Test Ollama API connection"""
        try:
            # Test if Ollama is reachable
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            
            if response.status_code != 200:
                return False, f"Ollama API returned status {response.status_code}"
            
            # Check if the specified model is available
            models = response.json().get('models', [])
            model_names = [m.get('name', '') for m in models]
            
            if self.model not in model_names and f"{self.model}:latest" not in model_names:
                available = ", ".join(model_names[:5])  # Show first 5
                return False, f"Model '{self.model}' not found. Available: {available}"
            
            return True, f"Connected to Ollama ({self.model})"
            
        except requests.exceptions.Timeout:
            return False, f"Connection to {self.base_url} timed out"
        except requests.exceptions.ConnectionError:
            return False, f"Cannot connect to Ollama at {self.base_url}"
        except Exception as e:
            return False, f"Ollama connection test failed: {str(e)}"
    
    @staticmethod
    def list_available_models(base_url: str) -> tuple[bool, List[str], str]:
        """
        List all available models from Ollama
        
        Returns:
            Tuple of (success, model_list, error_message)
        """
        try:
            response = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=5)
            
            if response.status_code != 200:
                return False, [], f"Ollama API returned status {response.status_code}"
            
            models = response.json().get('models', [])
            model_names = [m.get('name', '') for m in models if m.get('name')]
            
            return True, model_names, ""
            
        except requests.exceptions.Timeout:
            return False, [], f"Connection to {base_url} timed out"
        except requests.exceptions.ConnectionError:
            return False, [], f"Cannot connect to Ollama at {base_url}"
        except Exception as e:
            return False, [], f"Error listing models: {str(e)}"
