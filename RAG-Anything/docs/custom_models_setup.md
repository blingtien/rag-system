# Custom Models Setup Guide

This guide explains how to configure RAGAnything with custom models:
- **Local Qwen embedding model** for text vectorization
- **DeepSeek API** for LLM text generation and vision processing

## Prerequisites

1. **Python 3.8+** with pip
2. **PyTorch 2.0+** (CPU or GPU version)
3. **DeepSeek API account** and API key

## Installation Steps

### 1. Install Dependencies

```bash
# Install base RAGAnything with all dependencies
cd RAG-Anything
pip install -e '.[all]'

# Install additional custom model dependencies
pip install torch>=2.0.0 transformers>=4.30.0 numpy>=1.21.0 requests>=2.25.0

# For GPU support (optional but recommended)
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 2. Configure Environment Variables

Copy the example configuration:
```bash
cp .env.custom_models .env
```

Edit `.env` and set your DeepSeek API key:
```bash
# REQUIRED: Replace with your actual DeepSeek API key
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

### 3. Validate Configuration

Before processing documents, validate your setup:
```bash
python examples/custom_models_example.py --validate-only dummy_file
```

Expected output:
```
Custom Models Configuration Validation
==================================================
✓ PASS deepseek_api_configured
✓ PASS torch_available
✓ PASS transformers_available
✓ PASS qwen_model_available
==================================================
```

## Usage Examples

### Basic Document Processing

```bash
# Process a PDF document
python examples/custom_models_example.py document.pdf --output ./results

# Process with specific parser
python examples/custom_models_example.py document.pdf --parser mineru --output ./results
```

### Python Code Integration

```python
import asyncio
from raganything import RAGAnything, RAGAnythingConfig
from raganything.custom_models import (
    get_qwen_embedding_func,
    deepseek_complete_if_cache,
    deepseek_vision_complete
)

async def main():
    # Create configuration
    config = RAGAnythingConfig()
    
    # Define DeepSeek LLM function
    def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
        return deepseek_complete_if_cache(
            model=config.deepseek_model,
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
            **kwargs
        )
    
    # Define DeepSeek vision function
    def vision_model_func(prompt, system_prompt=None, history_messages=[], 
                         image_data=None, messages=None, **kwargs):
        return deepseek_vision_complete(
            model=config.deepseek_vision_model,
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            image_data=image_data,
            messages=messages,
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
            **kwargs
        )
    
    # Create Qwen embedding function
    embedding_func = get_qwen_embedding_func()
    
    # Initialize RAGAnything
    rag = RAGAnything(
        config=config,
        llm_model_func=llm_model_func,
        vision_model_func=vision_model_func,
        embedding_func=embedding_func
    )
    
    # Process document
    await rag.process_document_complete("document.pdf", output_dir="./output")
    
    # Query the document
    result = await rag.aquery("What is the main topic?", mode="hybrid")
    print(result)

# Run the example
asyncio.run(main())
```

## Configuration Options

### DeepSeek API Settings

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DEEPSEEK_API_KEY` | *required* | Your DeepSeek API key |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | API endpoint URL |
| `DEEPSEEK_MODEL` | `deepseek-chat` | Model for text generation |
| `DEEPSEEK_VISION_MODEL` | `deepseek-vl` | Model for vision tasks |
| `DEEPSEEK_TIMEOUT` | `240` | Request timeout in seconds |

### Qwen Embedding Settings

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `QWEN_MODEL_NAME` | `Qwen/Qwen3-Embedding-0.6B` | HuggingFace model identifier |
| `EMBEDDING_DEVICE` | `auto` | Device: `auto`, `cuda`, `cpu` |
| `EMBEDDING_BATCH_SIZE` | `32` | Batch size for processing |
| `EMBEDDING_MAX_LENGTH` | `512` | Maximum sequence length |
| `MODEL_CACHE_DIR` | `./models` | Directory for cached models |

## Performance Optimization

### GPU Setup

For optimal performance with Qwen embedding model:

1. **Install CUDA-enabled PyTorch:**
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```

2. **Set GPU device:**
   ```bash
   export EMBEDDING_DEVICE=cuda
   ```

3. **Adjust batch size based on GPU memory:**
   ```bash
   # For 8GB GPU
   export EMBEDDING_BATCH_SIZE=64
   
   # For 4GB GPU
   export EMBEDDING_BATCH_SIZE=32
   ```

### Memory Management

- **Model caching:** Models are cached locally after first download
- **Batch processing:** Embedding model processes texts in configurable batches
- **Device management:** Automatic fallback from CUDA to CPU if GPU unavailable

## Troubleshooting

### Common Issues

1. **DeepSeek API key not working:**
   - Verify API key is correct
   - Check account has sufficient credits
   - Ensure base URL is correct

2. **Qwen model download fails:**
   - Check internet connection
   - Verify HuggingFace Hub access
   - Try manual download: `huggingface-cli download Qwen/Qwen3-Embedding-0.6B`

3. **CUDA out of memory:**
   - Reduce `EMBEDDING_BATCH_SIZE`
   - Use CPU: `export EMBEDDING_DEVICE=cpu`
   - Free GPU memory from other processes

4. **Transformers version conflicts:**
   ```bash
   pip install --upgrade transformers>=4.30.0
   ```

### Debug Mode

Enable verbose logging for debugging:
```bash
export VERBOSE=true
export LOG_LEVEL=DEBUG
python examples/custom_models_example.py document.pdf
```

## API Compatibility

The custom models are designed to be drop-in replacements for OpenAI models:

- **LLM function signature:** Compatible with `openai_complete_if_cache`
- **Embedding function:** Compatible with `openai_embed`
- **Vision model:** Supports both single image and multi-modal message formats

## Performance Comparison

Typical performance with custom models:

| Component | Model | Speed | Memory |
|-----------|-------|-------|--------|
| Embedding | Qwen-0.6B (CPU) | ~200 texts/sec | ~2GB |
| Embedding | Qwen-0.6B (GPU) | ~800 texts/sec | ~3GB |
| LLM | DeepSeek-Chat | ~15 tokens/sec | API-based |
| Vision | DeepSeek-VL | ~10 tokens/sec | API-based |

## Support

For issues specific to custom models integration:
1. Check the validation output: `python examples/custom_models_example.py --validate-only dummy`
2. Review logs in `./logs/custom_models_example.log`
3. Verify environment variables are correctly set
4. Test individual components (embedding, LLM) separately