"""
Configuration classes for RAGAnything

Contains configuration dataclasses with environment variable support
"""

from dataclasses import dataclass, field
from typing import List
from lightrag.utils import get_env_value


@dataclass
class RAGAnythingConfig:
    """Configuration class for RAGAnything with environment variable support"""

    # Directory Configuration
    # ---
    working_dir: str = field(default=get_env_value("WORKING_DIR", "./rag_storage", str))
    """Directory where RAG storage and cache files are stored."""

    # Parser Configuration
    # ---
    parse_method: str = field(default=get_env_value("PARSE_METHOD", "auto", str))
    """Default parsing method for document parsing: 'auto', 'ocr', or 'txt'."""

    parser_output_dir: str = field(default=get_env_value("OUTPUT_DIR", "./output", str))
    """Default output directory for parsed content."""

    parser: str = field(default=get_env_value("PARSER", "mineru", str))
    """Parser selection: 'mineru' or 'docling'."""

    display_content_stats: bool = field(
        default=get_env_value("DISPLAY_CONTENT_STATS", True, bool)
    )
    """Whether to display content statistics during parsing."""

    # Multimodal Processing Configuration
    # ---
    enable_image_processing: bool = field(
        default=get_env_value("ENABLE_IMAGE_PROCESSING", True, bool)
    )
    """Enable image content processing."""

    enable_table_processing: bool = field(
        default=get_env_value("ENABLE_TABLE_PROCESSING", True, bool)
    )
    """Enable table content processing."""

    enable_equation_processing: bool = field(
        default=get_env_value("ENABLE_EQUATION_PROCESSING", True, bool)
    )
    """Enable equation content processing."""

    # Batch Processing Configuration
    # ---
    max_concurrent_files: int = field(
        default=get_env_value("MAX_CONCURRENT_FILES", 1, int)
    )
    """Maximum number of files to process concurrently."""

    supported_file_extensions: List[str] = field(
        default_factory=lambda: get_env_value(
            "SUPPORTED_FILE_EXTENSIONS",
            ".pdf,.jpg,.jpeg,.png,.bmp,.tiff,.tif,.gif,.webp,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.md",
            str,
        ).split(",")
    )
    """List of supported file extensions for batch processing."""

    recursive_folder_processing: bool = field(
        default=get_env_value("RECURSIVE_FOLDER_PROCESSING", True, bool)
    )
    """Whether to recursively process subfolders in batch mode."""

    # Context Extraction Configuration
    # ---
    context_window: int = field(default=get_env_value("CONTEXT_WINDOW", 1, int))
    """Number of pages/chunks to include before and after current item for context."""

    context_mode: str = field(default=get_env_value("CONTEXT_MODE", "page", str))
    """Context extraction mode: 'page' for page-based, 'chunk' for chunk-based."""

    max_context_tokens: int = field(
        default=get_env_value("MAX_CONTEXT_TOKENS", 2000, int)
    )
    """Maximum number of tokens in extracted context."""

    include_headers: bool = field(default=get_env_value("INCLUDE_HEADERS", True, bool))
    """Whether to include document headers and titles in context."""

    include_captions: bool = field(
        default=get_env_value("INCLUDE_CAPTIONS", True, bool)
    )
    """Whether to include image/table captions in context."""

    context_filter_content_types: List[str] = field(
        default_factory=lambda: get_env_value(
            "CONTEXT_FILTER_CONTENT_TYPES", "text", str
        ).split(",")
    )
    """Content types to include in context extraction (e.g., 'text', 'image', 'table')."""

    content_format: str = field(default=get_env_value("CONTENT_FORMAT", "minerU", str))
    """Default content format for context extraction when processing documents."""

    # Custom Models Configuration
    # ---
    # DeepSeek API Configuration
    deepseek_api_key: str = field(default=get_env_value("DEEPSEEK_API_KEY", "", str))
    """DeepSeek API key for LLM requests."""

    deepseek_base_url: str = field(default=get_env_value("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1", str))
    """DeepSeek API base URL."""

    deepseek_model: str = field(default=get_env_value("DEEPSEEK_MODEL", "deepseek-chat", str))
    """DeepSeek model name to use for text generation."""

    deepseek_vision_model: str = field(default=get_env_value("DEEPSEEK_VISION_MODEL", "deepseek-vl", str))
    """DeepSeek vision model name for image analysis."""

    deepseek_timeout: int = field(default=get_env_value("DEEPSEEK_TIMEOUT", 240, int))
    """Timeout in seconds for DeepSeek API requests."""

    # Qwen Local Embedding Model Configuration
    qwen_model_name: str = field(default=get_env_value("QWEN_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B", str))
    """Qwen embedding model identifier."""

    embedding_device: str = field(default=get_env_value("EMBEDDING_DEVICE", "auto", str))
    """Device for embedding model: 'auto', 'cuda', 'cpu'."""

    embedding_batch_size: int = field(default=get_env_value("EMBEDDING_BATCH_SIZE", 32, int))
    """Batch size for embedding processing."""

    embedding_max_length: int = field(default=get_env_value("EMBEDDING_MAX_LENGTH", 512, int))
    """Maximum sequence length for embedding model."""

    model_cache_dir: str = field(default=get_env_value("MODEL_CACHE_DIR", "./models", str))
    """Directory to cache downloaded models."""

    def __post_init__(self):
        """Post-initialization setup for backward compatibility and path normalization"""
        import os
        
        # Normalize all directory paths to absolute paths
        self.working_dir = os.path.abspath(self.working_dir)
        self.parser_output_dir = os.path.abspath(self.parser_output_dir)
        self.model_cache_dir = os.path.abspath(self.model_cache_dir)
        
        # Support legacy environment variable names for backward compatibility
        legacy_parse_method = get_env_value("MINERU_PARSE_METHOD", None, str)
        if legacy_parse_method and not get_env_value("PARSE_METHOD", None, str):
            self.parse_method = legacy_parse_method
            import warnings

            warnings.warn(
                "MINERU_PARSE_METHOD is deprecated. Use PARSE_METHOD instead.",
                DeprecationWarning,
                stacklevel=2,
            )

    @property
    def mineru_parse_method(self) -> str:
        """
        Backward compatibility property for old code.

        .. deprecated::
           Use `parse_method` instead. This property will be removed in a future version.
        """
        import warnings

        warnings.warn(
            "mineru_parse_method is deprecated. Use parse_method instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.parse_method

    @mineru_parse_method.setter
    def mineru_parse_method(self, value: str):
        """Setter for backward compatibility"""
        import warnings

        warnings.warn(
            "mineru_parse_method is deprecated. Use parse_method instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.parse_method = value
