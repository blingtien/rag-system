# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **RAG-Anything**, a comprehensive multimodal RAG system built on LightRAG that processes documents containing text, images, tables, equations, and other multimedia content. It provides end-to-end document parsing, multimodal content analysis, and intelligent retrieval capabilities.

## Development Commands

### Installation and Setup
```bash
# Install from source with all dependencies
cd RAG-Anything
pip install -e '.[all]'

# Install specific feature sets
pip install -e '.[image]'     # Image format support (BMP, TIFF, GIF, WebP)
pip install -e '.[text]'      # Text file processing (TXT, MD)
pip install -e '.[markdown]'  # Enhanced markdown conversion

# External dependencies for office documents
# Ubuntu/Debian: sudo apt-get install libreoffice
# macOS: brew install --cask libreoffice
# Windows: Download from libreoffice.org
```

### Development Tools
```bash
# Format code with Ruff
ruff format .

# Lint code with Ruff
ruff check --fix .

# Check pre-commit hooks
pre-commit run --all-files

# Build package
python3 setup.py build

# Install in development mode
python3 setup.py develop
```

### Testing and Examples
```bash
# Run example scripts (no API key required for parsing tests)
python examples/office_document_test.py --file path/to/document.docx
python examples/image_format_test.py --file path/to/image.bmp
python examples/text_format_test.py --file path/to/document.md

# Check system dependencies
python examples/office_document_test.py --check-libreoffice --file dummy
python examples/image_format_test.py --check-pillow --file dummy
python examples/text_format_test.py --check-reportlab --file dummy

# Full RAG processing examples (requires API keys)
python examples/raganything_example.py path/to/document.pdf --api-key YOUR_API_KEY
python examples/modalprocessors_example.py --api-key YOUR_API_KEY
```

### Batch Processing
```bash
# Process multiple documents
python -m raganything.batch_parser path/to/docs/ --output ./output --workers 4
python -m raganything.batch_parser path/to/docs/ --parser mineru --method auto

# Enhanced markdown conversion
python -m raganything.enhanced_markdown document.md --output document.pdf
python -m raganything.enhanced_markdown document.md --method weasyprint --css custom.css
```

## Architecture Overview

### Core Components

**Main Classes:**
- `RAGAnything` (`raganything/raganything.py`): Main orchestrator class that integrates document parsing, multimodal processing, and LightRAG
- `RAGAnythingConfig` (`raganything/config.py`): Configuration management with environment variable support
- `MineruParser`/`DoclingParser` (`raganything/parser.py`): Document parsing backends for different file formats

**Multimodal Processors:**
- `ImageModalProcessor`: Processes images with vision models for description generation
- `TableModalProcessor`: Analyzes structured data and statistical patterns
- `EquationModalProcessor`: Handles mathematical expressions and LaTeX formulas
- `GenericModalProcessor`: Extensible processor for custom content types
- `ContextExtractor`: Provides surrounding content context for enhanced analysis

**Processing Pipeline:**
1. **Document Parsing** → MinerU/Docling converts documents to structured content lists
2. **Content Analysis** → Categorizes and routes different content types through specialized processors
3. **Multimodal Knowledge Graph** → Extracts entities and relationships across text and multimodal content
4. **Intelligent Retrieval** → Hybrid vector-graph search with modality-aware ranking

### File Structure
```
raganything/
├── raganything.py      # Main orchestrator class
├── config.py           # Configuration with environment variables
├── parser.py           # Document parsing (MinerU, Docling)
├── modalprocessors.py  # Specialized multimodal content processors
├── processor.py        # ProcessorMixin for document processing
├── query.py           # QueryMixin for retrieval operations
├── batch.py           # BatchMixin for parallel processing
├── enhanced_markdown.py # Advanced markdown to PDF conversion
├── prompt.py          # Prompt templates for LLM interactions
└── utils.py           # Utility functions

examples/               # Example scripts and usage demonstrations
docs/                  # Detailed feature documentation
```

## Key Configuration

### Environment Variables
```bash
# Core settings
WORKING_DIR=./rag_storage
OUTPUT_DIR=./output
PARSER=mineru                    # mineru or docling
PARSE_METHOD=auto               # auto, ocr, or txt

# Multimodal processing
ENABLE_IMAGE_PROCESSING=true
ENABLE_TABLE_PROCESSING=true
ENABLE_EQUATION_PROCESSING=true

# Context extraction
CONTEXT_WINDOW=1
CONTEXT_MODE=page
MAX_CONTEXT_TOKENS=2000
INCLUDE_HEADERS=true
INCLUDE_CAPTIONS=true

# Batch processing
MAX_CONCURRENT_FILES=4
RECURSIVE_FOLDER_PROCESSING=true
```

### Supported File Formats
- **PDFs**: Research papers, reports, presentations
- **Office Documents**: DOC, DOCX, PPT, PPTX, XLS, XLSX (requires LibreOffice)
- **Images**: JPG, PNG, BMP, TIFF, GIF, WebP
- **Text Files**: TXT, MD (with enhanced PDF conversion)

## Common Patterns

### Document Processing
```python
# Basic usage
rag = RAGAnything(config=config, llm_model_func=llm_func, embedding_func=embed_func)
await rag.process_document_complete("document.pdf", output_dir="./output")

# With specific parser and method
await rag.process_document_complete(
    "document.pdf", 
    parser="mineru", 
    parse_method="auto",
    device="cuda",
    lang="en"
)
```

### Query Modes
```python
# Different retrieval strategies
text_result = await rag.aquery("question", mode="hybrid")    # Best overall
local_result = await rag.aquery("question", mode="local")    # Local patterns
global_result = await rag.aquery("question", mode="global")  # Global insights
naive_result = await rag.aquery("question", mode="naive")    # Simple similarity

# VLM-enhanced queries (automatic when vision_model_func provided)
vlm_result = await rag.aquery("Analyze the charts", vlm_enhanced=True)

# Multimodal queries with specific content
multimodal_result = await rag.aquery_with_multimodal(
    "Explain this table",
    multimodal_content=[{"type": "table", "table_data": "...", "table_caption": "..."}]
)
```

### Direct Content Insertion
```python
# Bypass parsing - insert pre-processed content
content_list = [
    {"type": "text", "text": "Content here", "page_idx": 0},
    {"type": "image", "img_path": "/absolute/path/image.jpg", "img_caption": ["Caption"], "page_idx": 1},
    {"type": "table", "table_body": "| A | B |\n|---|---|", "table_caption": ["Table"], "page_idx": 2}
]
await rag.insert_content_list(content_list, "document.pdf")
```

## MinerU 2.0 Integration

RAG-Anything uses MinerU 2.0 for document parsing. Key differences from v1:
- No more `magic-pdf.json` config files - all settings via parameters
- Command-line style configuration through function arguments
- Support for GPU acceleration and multiple backends
- Advanced OCR and table extraction capabilities

```python
# MinerU special parameters
await rag.process_document_complete(
    "document.pdf",
    lang="en",           # Document language for OCR
    device="cuda:0",     # Inference device
    start_page=0,        # Page range
    end_page=10,
    formula=True,        # Enable formula parsing
    table=True,          # Enable table parsing
    backend="pipeline"   # Parsing backend
)
```

## Code Quality

The project uses:
- **Ruff** for code formatting and linting (configured in `.pre-commit-config.yaml`)
- **Pre-commit hooks** for automated code quality checks
- **Setuptools** for package management with optional dependencies
- **Environment variable** configuration pattern throughout

When contributing:
1. Run `ruff format .` before committing
2. Ensure `ruff check --fix .` passes
3. Test with example scripts to verify functionality
4. Follow the existing pattern of mixins for extending `RAGAnything`

## External Dependencies

**Required:**
- `lightrag-hku`: Core RAG functionality
- `mineru[core]`: Document parsing engine
- `huggingface_hub`: Model downloads
- `tqdm`: Progress tracking

**Optional (install with extras):**
- `Pillow>=10.0.0`: Extended image format support
- `reportlab>=4.0.0`: Text file to PDF conversion
- `markdown`, `weasyprint`, `pygments`: Enhanced markdown conversion
- LibreOffice (external): Office document processing
- python版本有限使用3.10
- 不要上来就开发，先告诉我你计划怎么干，我同意后才允许开发编写或者修改
- 如果需要执行sudo命令，你随时提醒我手动执行
- 前端页面的访问地址是http://localhost:3000/
- 不要使用绝对路径，一律使用环境变量文件，为了后期好维护