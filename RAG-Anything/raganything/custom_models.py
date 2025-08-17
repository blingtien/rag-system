"""
Custom model implementations for RAGAnything

This module provides:
1. Local Qwen embedding model integration
2. DeepSeek API wrapper functions  
3. Helper utilities for model management
"""

import os
import logging
import requests
import json
from typing import List, Dict, Any, Optional, Union, Tuple
import torch
from transformers import AutoTokenizer, AutoModel
import numpy as np

logger = logging.getLogger(__name__)


class QwenEmbeddingModel:
    """Local Qwen embedding model wrapper"""
    
    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Embedding-0.6B",
        device: str = "auto",
        batch_size: int = 32,
        max_length: int = 512,
        cache_dir: Optional[str] = None,
        trust_remote_code: bool = True,
    ):
        """
        Initialize Qwen embedding model
        
        Args:
            model_name: HuggingFace model identifier
            device: Device to use ('auto', 'cuda', 'cpu')
            batch_size: Batch size for inference
            max_length: Maximum sequence length
            cache_dir: Directory to cache model files
            trust_remote_code: Whether to trust remote code
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self.cache_dir = cache_dir or os.getenv("MODEL_CACHE_DIR", "./models")
        
        # Determine device
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        logger.info(f"Initializing Qwen embedding model on device: {self.device}")
        
        try:
            # Load tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                cache_dir=self.cache_dir,
                trust_remote_code=trust_remote_code
            )
            
            self.model = AutoModel.from_pretrained(
                model_name,
                cache_dir=self.cache_dir,
                trust_remote_code=trust_remote_code,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
            ).to(self.device)
            
            self.model.eval()
            
            # Get embedding dimension
            with torch.no_grad():
                test_input = self.tokenizer(
                    "test", 
                    return_tensors="pt", 
                    truncation=True, 
                    max_length=self.max_length
                ).to(self.device)
                test_output = self.model(**test_input)
                self.embedding_dim = test_output.last_hidden_state.mean(dim=1).shape[-1]
                
            logger.info(f"Qwen model loaded successfully. Embedding dimension: {self.embedding_dim}")
            
        except Exception as e:
            logger.error(f"Failed to load Qwen model: {e}")
            raise
    
    def encode(self, texts: List[str]) -> np.ndarray:
        """
        Encode texts to embeddings
        
        Args:
            texts: List of texts to encode
            
        Returns:
            numpy array of embeddings
        """
        all_embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]
            
            try:
                # Tokenize batch
                inputs = self.tokenizer(
                    batch_texts,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=self.max_length
                ).to(self.device)
                
                # Get embeddings
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    # Use mean pooling over sequence length
                    embeddings = outputs.last_hidden_state.mean(dim=1)
                    # Normalize embeddings
                    embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                    
                all_embeddings.append(embeddings.cpu().numpy())
                
            except Exception as e:
                logger.error(f"Error encoding batch {i//self.batch_size + 1}: {e}")
                # Return zero embeddings for failed batch
                batch_size = len(batch_texts)
                zero_embeddings = np.zeros((batch_size, self.embedding_dim))
                all_embeddings.append(zero_embeddings)
        
        return np.vstack(all_embeddings)


# Global model instance for reuse
_qwen_model_instance = None


def get_qwen_embedding_func(
    model_name: str = None,
    device: str = None,
    batch_size: int = None,
    max_length: int = None,
    **kwargs
) -> Tuple[callable, int]:
    """
    Create embedding function for Qwen model compatible with LightRAG
    
    Args:
        model_name: Model identifier (defaults to env var or Qwen/Qwen3-Embedding-0.6B)
        device: Device to use (defaults to env var or auto)
        batch_size: Batch size (defaults to env var or 32)
        max_length: Max sequence length (defaults to env var or 512)
        **kwargs: Additional arguments for model initialization
        
    Returns:
        Tuple of (embedding_function, embedding_dimension)
    """
    global _qwen_model_instance
    
    # Get parameters from environment variables with fallbacks
    model_name = model_name or os.getenv("QWEN_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B")
    device = device or os.getenv("EMBEDDING_DEVICE", "auto")
    batch_size = batch_size or int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
    max_length = max_length or int(os.getenv("EMBEDDING_MAX_LENGTH", "512"))
    
    # Create model instance if not exists
    if _qwen_model_instance is None:
        logger.info("Creating new Qwen embedding model instance")
        _qwen_model_instance = QwenEmbeddingModel(
            model_name=model_name,
            device=device,
            batch_size=batch_size,
            max_length=max_length,
            **kwargs
        )
    
    def embedding_func(texts: List[str]) -> List[List[float]]:
        """Embedding function compatible with LightRAG"""
        try:
            embeddings = _qwen_model_instance.encode(texts)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error in embedding function: {e}")
            # Return zero embeddings as fallback
            return [[0.0] * _qwen_model_instance.embedding_dim for _ in texts]
    
    return embedding_func, _qwen_model_instance.embedding_dim


def deepseek_complete_if_cache(
    model: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    history_messages: List[Dict[str, str]] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    messages: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> str:
    """
    DeepSeek API completion function compatible with LightRAG
    
    Args:
        model: Model name to use
        prompt: User prompt
        system_prompt: Optional system prompt
        history_messages: Previous conversation history
        api_key: DeepSeek API key
        base_url: DeepSeek API base URL
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        messages: Pre-formatted messages (if provided, other params ignored)
        **kwargs: Additional API parameters
        
    Returns:
        Generated text response
    """
    # Get API credentials from environment if not provided
    api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
    base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    
    if not api_key:
        raise ValueError("DeepSeek API key is required. Set DEEPSEEK_API_KEY environment variable.")
    
    # Use pre-formatted messages if provided, otherwise build messages
    if messages:
        request_messages = messages
    else:
        request_messages = []
        
        if system_prompt:
            request_messages.append({"role": "system", "content": system_prompt})
        
        if history_messages:
            request_messages.extend(history_messages)
        
        request_messages.append({"role": "user", "content": prompt})
    
    # Prepare request
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Filter kwargs to only include JSON-serializable values
    safe_kwargs = {}
    for key, value in kwargs.items():
        try:
            json.dumps(value)
            safe_kwargs[key] = value
        except (TypeError, ValueError):
            # Skip non-serializable objects
            logger.debug(f"Skipping non-serializable parameter: {key}")
    
    data = {
        "model": model,
        "messages": request_messages,
        "temperature": temperature,
        "stream": False,
        **safe_kwargs
    }
    
    if max_tokens:
        data["max_tokens"] = max_tokens
    
    try:
        # Make API request
        response = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=data,
            timeout=int(os.getenv("DEEPSEEK_TIMEOUT", "240"))
        )
        
        response.raise_for_status()
        result = response.json()
        
        return result["choices"][0]["message"]["content"]
        
    except requests.exceptions.RequestException as e:
        logger.error(f"DeepSeek API request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response content: {e.response.text}")
        raise
    except KeyError as e:
        logger.error(f"Unexpected response format from DeepSeek API: {e}")
        logger.error(f"Response: {result if 'result' in locals() else 'No response'}")
        raise


def deepseek_vision_complete(
    model: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    history_messages: List[Dict[str, str]] = None,
    image_data: Optional[str] = None,
    messages: Optional[List[Dict[str, Any]]] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs
) -> str:
    """
    DeepSeek vision model completion function
    
    Args:
        model: Vision model name
        prompt: Text prompt
        system_prompt: Optional system prompt
        history_messages: Previous conversation history
        image_data: Base64 encoded image data
        messages: Pre-formatted messages (if provided, other params ignored)
        api_key: DeepSeek API key
        base_url: DeepSeek API base URL
        **kwargs: Additional API parameters
        
    Returns:
        Generated text response
    """
    # Use pre-formatted messages if provided
    if messages:
        return deepseek_complete_if_cache(
            model=model,
            prompt="",
            system_prompt=None,
            history_messages=[],
            messages=messages,
            api_key=api_key,
            base_url=base_url,
            **kwargs
        )
    
    # Handle image data
    if image_data:
        # Prepare vision messages
        content = [{"type": "text", "text": prompt}]
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
        })
        
        vision_messages = []
        if system_prompt:
            vision_messages.append({"role": "system", "content": system_prompt})
        
        if history_messages:
            vision_messages.extend(history_messages)
            
        vision_messages.append({"role": "user", "content": content})
        
        return deepseek_complete_if_cache(
            model=model,
            prompt="",
            system_prompt=None,
            history_messages=[],
            messages=vision_messages,
            api_key=api_key,
            base_url=base_url,
            **kwargs
        )
    else:
        # Fall back to text-only completion
        return deepseek_complete_if_cache(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            api_key=api_key,
            base_url=base_url,
            **kwargs
        )


def validate_custom_models() -> Dict[str, bool]:
    """
    Validate that custom models are properly configured
    
    Returns:
        Dictionary with validation results
    """
    validation_results = {
        "deepseek_api_configured": False,
        "qwen_model_available": False,
        "torch_available": False,
        "transformers_available": False
    }
    
    # Check DeepSeek API configuration
    if os.getenv("DEEPSEEK_API_KEY"):
        validation_results["deepseek_api_configured"] = True
    
    # Check PyTorch availability
    try:
        import torch
        validation_results["torch_available"] = True
    except ImportError:
        pass
    
    # Check transformers availability
    try:
        import transformers
        validation_results["transformers_available"] = True
    except ImportError:
        pass
    
    # Check if Qwen model can be loaded
    if validation_results["torch_available"] and validation_results["transformers_available"]:
        try:
            model_name = os.getenv("QWEN_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B")
            # Just check if tokenizer can be loaded (quick test)
            AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
            validation_results["qwen_model_available"] = True
        except Exception as e:
            logger.warning(f"Qwen model validation failed: {e}")
    
    return validation_results