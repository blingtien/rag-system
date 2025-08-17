# Custom Models Integration with RAGAnything

This document explains how to properly integrate custom models (Qwen embedding + DeepSeek LLM) with RAGAnything following the correct patterns from the official documentation.

## Key Corrections Made

The previous implementation had several issues that have been corrected:

1. **Embedding Function Pattern**: RAGAnything expects a simple lambda function that returns embeddings, not an `EmbeddingFunc` wrapper class
2. **No RAGAnythingConfig Class**: RAGAnything is initialized directly with function parameters, not through a configuration class
3. **Proper Parameter Passing**: `embedding_dim` and `max_token_size` are separate parameters in RAGAnything initialization
4. **Function Signatures**: LLM and vision functions use the exact signatures documented in RAGAnything examples

## Correct Implementation Pattern

### 1. Embedding Function
```python
# CORRECT: Returns (function, dimension) tuple
embedding_func, embedding_dim = get_qwen_embedding_func(
    model_name="Qwen/Qwen3-Embedding-0.6B",
    device="auto"
)

# INCORRECT (previous): Returned EmbeddingFunc wrapper
# embedding_func = get_qwen_embedding_func(...)
```

### 2. RAGAnything Initialization
```python
# CORRECT: Direct parameter passing following documentation
rag = RAGAnything(
    working_dir="./rag_storage",
    llm_model_func=lambda prompt, system_prompt=None, history_messages=[], **kwargs: deepseek_complete_if_cache(
        model="deepseek-chat",
        prompt=prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        api_key=api_key,
        **kwargs,
    ),
    embedding_func=embedding_func,
    embedding_dim=embedding_dim,
    max_token_size=512
)

# INCORRECT (previous): Using config class
# rag = RAGAnything(config=config, llm_model_func=..., embedding_func=...)
```

## Files Modified

### `/home/ragsvr/projects/ragsystem/RAG-Anything/raganything/custom_models.py`
- **Fixed**: `get_qwen_embedding_func()` now returns `(function, dimension)` tuple instead of `EmbeddingFunc` wrapper
- **Removed**: `EmbeddingFunc` import and wrapper usage
- **Added**: Proper type hints with `Tuple[callable, int]`

### `/home/ragsvr/projects/ragsystem/RAG-Anything/examples/custom_models_example.py`
- **Fixed**: Removed `RAGAnythingConfig` usage
- **Fixed**: Direct parameter passing to RAGAnything following documented patterns
- **Fixed**: Proper embedding function unpacking: `embedding_func, embedding_dim = get_qwen_embedding_func(...)`

### `/home/ragsvr/projects/ragsystem/RAG-Anything/examples/simple_custom_models_example.py` (NEW)
- **Added**: Simple, clean example following exact RAGAnything documentation patterns
- **Added**: Minimal example showing correct integration approach

## Environment Variables

Configure these in your `.env` file (template already exists in `env.example`):

```bash
# Required
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Optional - defaults shown
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_VISION_MODEL=deepseek-vl-chat
QWEN_MODEL_NAME=Qwen/Qwen3-Embedding-0.6B
EMBEDDING_DEVICE=auto
EMBEDDING_BATCH_SIZE=32
EMBEDDING_MAX_LENGTH=512
```

## Usage Examples

### Basic Usage
```python
import asyncio
from raganything import RAGAnything
from raganything.custom_models import get_qwen_embedding_func, deepseek_complete_if_cache

async def main():
    # Initialize embedding function
    embedding_func, embedding_dim = get_qwen_embedding_func()
    
    # Initialize RAGAnything with custom models
    rag = RAGAnything(
        working_dir="./rag_storage",
        llm_model_func=lambda prompt, **kwargs: deepseek_complete_if_cache(
            model="deepseek-chat",
            prompt=prompt,
            api_key="your-api-key",
            **kwargs
        ),
        embedding_func=embedding_func,
        embedding_dim=embedding_dim,
        max_token_size=512
    )
    
    # Process document
    await rag.process_document_complete("document.pdf", output_dir="./output")
    
    # Query
    result = await rag.aquery("What is this document about?", mode="hybrid")
    print(result)

asyncio.run(main())
```

### Running Examples
```bash
# Set environment variable
export DEEPSEEK_API_KEY=your_key_here

# Run simple example
python examples/simple_custom_models_example.py

# Run full example with document processing
python examples/custom_models_example.py path/to/document.pdf --output ./results
```

## Dependencies

Ensure these are installed:
```bash
pip install torch transformers
pip install raganything
```

The Qwen embedding model will be downloaded automatically on first use.

## Key Differences from OpenAI Integration

The RAGAnything documentation shows OpenAI integration like this:
```python
embedding_func=lambda texts: openai_embed(texts, model="text-embedding-3-large", api_key="key")
```

Our custom integration follows the same pattern:
```python
embedding_func=lambda texts: custom_embedding_function(texts)
```

The embedding function must:
1. Accept a list of strings
2. Return a list of lists of floats (embeddings)
3. Be a simple callable, not a class instance

## Troubleshooting

1. **"EmbeddingFunc not found"**: Make sure you're using the corrected version that doesn't import `EmbeddingFunc`
2. **"RAGAnythingConfig not found"**: Use direct parameter passing to `RAGAnything()` instead
3. **Embedding dimension errors**: Ensure `embedding_dim` is passed as separate parameter to RAGAnything
4. **API errors**: Verify `DEEPSEEK_API_KEY` is set correctly

## Testing

Validate your setup:
```python
from raganything.custom_models import validate_custom_models
results = validate_custom_models()
print(results)
```

This will check:
- DeepSeek API configuration
- PyTorch availability  
- Transformers library
- Qwen model accessibility