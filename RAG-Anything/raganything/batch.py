"""
Batch processing functionality for RAGAnything

Contains methods for processing multiple documents in batch mode
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import time

from .batch_parser import BatchParser, BatchProcessingResult

if TYPE_CHECKING:
    from .config import RAGAnythingConfig


class BatchMixin:
    """BatchMixin class containing batch processing functionality for RAGAnything"""

    # Type hints for mixin attributes (will be available when mixed into RAGAnything)
    config: "RAGAnythingConfig"
    logger: logging.Logger

    # Type hints for methods that will be available from other mixins
    async def _ensure_lightrag_initialized(self) -> None: ...
    async def process_document_complete(self, file_path: str, **kwargs) -> None: ...

    # ==========================================
    # ORIGINAL BATCH PROCESSING METHOD (RESTORED)
    # ==========================================

    async def process_folder_complete(
        self,
        folder_path: str,
        output_dir: str = None,
        parse_method: str = None,
        display_stats: bool = None,
        split_by_character: str | None = None,
        split_by_character_only: bool = False,
        file_extensions: Optional[List[str]] = None,
        recursive: bool = None,
        max_workers: int = None,
    ):
        """
        Process all supported files in a folder

        Args:
            folder_path: Path to the folder containing files to process
            output_dir: Directory for parsed outputs (optional)
            parse_method: Parsing method to use (optional)
            display_stats: Whether to display statistics (optional)
            split_by_character: Character to split by (optional)
            split_by_character_only: Whether to split only by character (optional)
            file_extensions: List of file extensions to process (optional)
            recursive: Whether to process folders recursively (optional)
            max_workers: Maximum number of workers for concurrent processing (optional)
        """
        if output_dir is None:
            output_dir = self.config.parser_output_dir
        if parse_method is None:
            parse_method = self.config.parse_method
        if display_stats is None:
            display_stats = True
        if file_extensions is None:
            file_extensions = self.config.supported_file_extensions
        if recursive is None:
            recursive = self.config.recursive_folder_processing
        if max_workers is None:
            max_workers = self.config.max_concurrent_files

        await self._ensure_lightrag_initialized()

        # Get all files in the folder
        folder_path_obj = Path(folder_path)
        if not folder_path_obj.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        # Collect files based on supported extensions
        files_to_process = []
        for file_ext in file_extensions:
            if recursive:
                pattern = f"**/*{file_ext}"
            else:
                pattern = f"*{file_ext}"
            files_to_process.extend(folder_path_obj.glob(pattern))

        if not files_to_process:
            self.logger.warning(f"No supported files found in {folder_path}")
            return

        self.logger.info(
            f"Found {len(files_to_process)} files to process in {folder_path}"
        )

        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Process files with controlled concurrency
        semaphore = asyncio.Semaphore(max_workers)
        tasks = []

        async def process_single_file(file_path: Path):
            async with semaphore:
                try:
                    await self.process_document_complete(
                        str(file_path),
                        output_dir=output_dir,
                        parse_method=parse_method,
                        split_by_character=split_by_character,
                        split_by_character_only=split_by_character_only,
                    )
                    return True, str(file_path), None
                except Exception as e:
                    self.logger.error(f"Failed to process {file_path}: {str(e)}")
                    return False, str(file_path), str(e)

        # Create tasks for all files
        for file_path in files_to_process:
            task = asyncio.create_task(process_single_file(file_path))
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        successful_files = []
        failed_files = []
        for result in results:
            if isinstance(result, Exception):
                failed_files.append(("unknown", str(result)))
            else:
                success, file_path, error = result
                if success:
                    successful_files.append(file_path)
                else:
                    failed_files.append((file_path, error))

        # Display statistics if requested
        if display_stats:
            self.logger.info("Processing complete!")
            self.logger.info(f"  Successful: {len(successful_files)} files")
            self.logger.info(f"  Failed: {len(failed_files)} files")
            if failed_files:
                self.logger.warning("Failed files:")
                for file_path, error in failed_files:
                    self.logger.warning(f"  - {file_path}: {error}")

    # ==========================================
    # NEW ENHANCED BATCH PROCESSING METHODS
    # ==========================================

    def process_documents_batch(
        self,
        file_paths: List[str],
        output_dir: Optional[str] = None,
        parse_method: Optional[str] = None,
        max_workers: Optional[int] = None,
        recursive: Optional[bool] = None,
        show_progress: bool = True,
        **kwargs,
    ) -> BatchProcessingResult:
        """
        Process multiple documents in batch using the new BatchParser

        Args:
            file_paths: List of file paths or directories to process
            output_dir: Output directory for parsed files
            parse_method: Parsing method to use
            max_workers: Maximum number of workers for parallel processing
            recursive: Whether to process directories recursively
            show_progress: Whether to show progress bar
            **kwargs: Additional arguments passed to the parser

        Returns:
            BatchProcessingResult: Results of the batch processing
        """
        # Use config defaults if not specified
        if output_dir is None:
            output_dir = self.config.parser_output_dir
        if parse_method is None:
            parse_method = self.config.parse_method
        if max_workers is None:
            max_workers = self.config.max_concurrent_files
        if recursive is None:
            recursive = self.config.recursive_folder_processing

        # Create batch parser
        batch_parser = BatchParser(
            parser_type=self.config.parser,
            max_workers=max_workers,
            show_progress=show_progress,
            skip_installation_check=True,  # Skip installation check for better UX
        )

        # Process batch
        return batch_parser.process_batch(
            file_paths=file_paths,
            output_dir=output_dir,
            parse_method=parse_method,
            recursive=recursive,
            **kwargs,
        )

    async def process_documents_batch_async(
        self,
        file_paths: List[str],
        output_dir: Optional[str] = None,
        parse_method: Optional[str] = None,
        max_workers: Optional[int] = None,
        recursive: Optional[bool] = None,
        show_progress: bool = True,
        **kwargs,
    ) -> BatchProcessingResult:
        """
        Asynchronously process multiple documents in batch

        Args:
            file_paths: List of file paths or directories to process
            output_dir: Output directory for parsed files
            parse_method: Parsing method to use
            max_workers: Maximum number of workers for parallel processing
            recursive: Whether to process directories recursively
            show_progress: Whether to show progress bar
            **kwargs: Additional arguments passed to the parser

        Returns:
            BatchProcessingResult: Results of the batch processing
        """
        # Use config defaults if not specified
        if output_dir is None:
            output_dir = self.config.parser_output_dir
        if parse_method is None:
            parse_method = self.config.parse_method
        if max_workers is None:
            max_workers = self.config.max_concurrent_files
        if recursive is None:
            recursive = self.config.recursive_folder_processing

        # Create batch parser
        batch_parser = BatchParser(
            parser_type=self.config.parser,
            max_workers=max_workers,
            show_progress=show_progress,
            skip_installation_check=True,  # Skip installation check for better UX
        )

        # Process batch asynchronously
        return await batch_parser.process_batch_async(
            file_paths=file_paths,
            output_dir=output_dir,
            parse_method=parse_method,
            recursive=recursive,
            **kwargs,
        )

    def get_supported_file_extensions(self) -> List[str]:
        """Get list of supported file extensions for batch processing"""
        batch_parser = BatchParser(parser_type=self.config.parser)
        return batch_parser.get_supported_extensions()

    def filter_supported_files(
        self, file_paths: List[str], recursive: Optional[bool] = None
    ) -> List[str]:
        """
        Filter file paths to only include supported file types

        Args:
            file_paths: List of file paths to filter
            recursive: Whether to process directories recursively

        Returns:
            List of supported file paths
        """
        if recursive is None:
            recursive = self.config.recursive_folder_processing

        batch_parser = BatchParser(parser_type=self.config.parser)
        return batch_parser.filter_supported_files(file_paths, recursive)

    async def process_documents_with_rag_batch(
        self,
        file_paths: List[str],
        output_dir: Optional[str] = None,
        parse_method: Optional[str] = None,
        max_workers: Optional[int] = None,
        recursive: Optional[bool] = None,
        show_progress: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Process documents in batch and then add them to RAG

        This method combines document parsing (with caching) and RAG insertion.
        Unlike process_documents_batch, this uses process_document_complete
        which properly handles parse caching.

        Args:
            file_paths: List of file paths or directories to process
            output_dir: Output directory for parsed files
            parse_method: Parsing method to use
            max_workers: Maximum number of workers for parallel processing
            recursive: Whether to process directories recursively
            show_progress: Whether to show progress bar
            **kwargs: Additional arguments passed to the parser

        Returns:
            Dict containing processing results
        """
        start_time = time.time()

        # Use config defaults if not specified
        if output_dir is None:
            output_dir = self.config.parser_output_dir
        if parse_method is None:
            parse_method = self.config.parse_method
        if max_workers is None:
            max_workers = self.config.max_concurrent_files
        if recursive is None:
            recursive = self.config.recursive_folder_processing

        self.logger.info("Starting batch processing with RAG integration")

        # Initialize RAG system and ensure parse cache is ready
        await self._ensure_lightrag_initialized()

        # Get supported files using BatchParser for filtering
        batch_parser = BatchParser(
            parser_type=self.config.parser,
            skip_installation_check=True,
        )
        
        # Filter to supported files
        supported_files = batch_parser.filter_supported_files(file_paths, recursive)
        
        if not supported_files:
            self.logger.warning("No supported files found to process")
            return {
                "successful_files": [],
                "failed_files": [],
                "total_files": 0,
                "total_processing_time": 0.0,
                "successful_rag_files": 0,
                "failed_rag_files": 0,
            }

        self.logger.info(f"Found {len(supported_files)} files to process")

        # Process files with controlled concurrency using process_document_complete
        # This ensures proper caching and RAG integration
        semaphore = asyncio.Semaphore(max_workers)
        
        async def process_single_file_with_rag(file_path: str):
            async with semaphore:
                try:
                    # Use process_document_complete which handles both parsing (with cache) and RAG
                    await self.process_document_complete(
                        file_path,
                        output_dir=output_dir,
                        parse_method=parse_method,
                        **kwargs,
                    )
                    return True, file_path, None
                except Exception as e:
                    self.logger.error(f"Failed to process {file_path}: {str(e)}")
                    return False, file_path, str(e)

        # Create tasks for all files
        tasks = []
        for file_path in supported_files:
            task = asyncio.create_task(process_single_file_with_rag(file_path))
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        successful_files = []
        failed_files = []
        errors = {}
        
        for result in results:
            if isinstance(result, Exception):
                # Task itself failed
                failed_files.append(("unknown", str(result)))
                errors["unknown"] = str(result)
            else:
                success, file_path, error = result
                if success:
                    successful_files.append(file_path)
                else:
                    failed_files.append(file_path)
                    if error:
                        errors[file_path] = error

        processing_time = time.time() - start_time

        # Log summary
        self.logger.info(
            f"Batch processing complete: {len(successful_files)} successful, "
            f"{len(failed_files)} failed, {processing_time:.2f}s total"
        )

        return {
            "successful_files": successful_files,
            "failed_files": failed_files,
            "total_files": len(supported_files),
            "total_processing_time": processing_time,
            "successful_rag_files": len(successful_files),
            "failed_rag_files": len(failed_files),
            "errors": errors,
        }
