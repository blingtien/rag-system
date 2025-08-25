"""
Document Service - Business Logic Layer
Handles all document-related operations and business rules
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import UploadFile, HTTPException
from config.settings import Settings
from storage.state_manager import StateManager
from core.initialization import RAGInitializer
from utils.file_utils import SecureFileHandler
from utils.display_utils import get_document_display_info


class DocumentService:
    """Service class for document management operations"""
    
    def __init__(
        self,
        settings: Settings,
        state_manager: StateManager,
        rag_initializer: RAGInitializer
    ):
        self.settings = settings
        self.state_manager = state_manager
        self.rag_initializer = rag_initializer
        self.file_handler = SecureFileHandler(settings)
    
    async def upload_single(self, file: UploadFile) -> Dict[str, Any]:
        """
        Upload a single document file
        
        Args:
            file: The uploaded file
            
        Returns:
            Dictionary with upload result and document metadata
            
        Raises:
            ValueError: If file validation fails
            Exception: For other upload errors
        """
        # Validate and process file upload
        try:
            upload_result = await self.file_handler.handle_upload(file)
        except HTTPException as e:
            raise ValueError(e.detail)
        
        # Check for duplicate filenames
        existing_docs = await self.state_manager.find_documents_by_filename(
            upload_result["original_filename"]
        )
        if existing_docs:
            # Clean up uploaded file
            try:
                os.unlink(upload_result["file_path"])
            except OSError:
                pass
            raise ValueError(
                f"File '{upload_result['original_filename']}' already exists"
            )
        
        # Create document and task records
        document_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        
        document_data = {
            "document_id": document_id,
            "file_name": upload_result["original_filename"],
            "file_path": upload_result["file_path"],
            "file_size": upload_result["file_size"],
            "status": "uploaded",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "task_id": task_id
        }
        
        task_data = self._create_initial_task(task_id, document_id, upload_result)
        
        # Store in state manager
        await self.state_manager.save_document(document_id, document_data)
        await self.state_manager.save_task(task_id, task_data)
        
        return {
            "success": True,
            "message": "Document uploaded successfully",
            "task_id": task_id,
            "document_id": document_id,
            "file_name": upload_result["original_filename"],
            "file_size": upload_result["file_size"],
            "status": "uploaded"
        }
    
    async def upload_batch(self, files: List[UploadFile]) -> Dict[str, Any]:
        """
        Upload multiple documents in batch
        
        Args:
            files: List of uploaded files
            
        Returns:
            Dictionary with batch upload results
        """
        batch_operation_id = str(uuid.uuid4())
        uploaded_count = 0
        failed_count = 0
        results = []
        
        # Create batch operation tracking
        batch_operation = {
            "batch_operation_id": batch_operation_id,
            "operation_type": "upload",
            "status": "running",
            "total_items": len(files),
            "completed_items": 0,
            "failed_items": 0,
            "progress": 0.0,
            "started_at": datetime.now().isoformat(),
            "results": []
        }
        await self.state_manager.save_batch_operation(batch_operation_id, batch_operation)
        
        for i, file in enumerate(files):
            file_result = {
                "file_name": file.filename or f"unknown_file_{i}",
                "file_size": 0,
                "status": "failed",
                "message": "",
                "task_id": None,
                "document_id": None
            }
            
            try:
                # Process individual file upload
                single_result = await self.upload_single(file)
                file_result.update({
                    "file_size": single_result["file_size"],
                    "status": "success",
                    "message": "上传成功",
                    "task_id": single_result["task_id"],
                    "document_id": single_result["document_id"]
                })
                uploaded_count += 1
                batch_operation["completed_items"] += 1
                
            except ValueError as e:
                file_result["message"] = str(e)
                failed_count += 1
                batch_operation["failed_items"] += 1
            except Exception as e:
                file_result["message"] = f"Upload failed: {str(e)}"
                failed_count += 1
                batch_operation["failed_items"] += 1
            
            results.append(file_result)
            batch_operation["progress"] = ((i + 1) / len(files)) * 100
        
        # Complete batch operation
        batch_operation["status"] = "completed"
        batch_operation["completed_at"] = datetime.now().isoformat()
        batch_operation["results"] = results
        await self.state_manager.save_batch_operation(batch_operation_id, batch_operation)
        
        return {
            "success": failed_count == 0,
            "uploaded_count": uploaded_count,
            "failed_count": failed_count,
            "total_files": len(files),
            "results": results,
            "message": f"Batch upload completed: {uploaded_count} succeeded, {failed_count} failed"
        }
    
    async def list_documents(self) -> Dict[str, Any]:
        """
        Get list of all documents with enhanced display information
        
        Returns:
            Dictionary with document list and statistics
        """
        documents = await self.state_manager.get_all_documents()
        
        # Enhance documents with display information
        enhanced_documents = []
        for doc in documents.values():
            enhanced_doc = get_document_display_info(doc)
            enhanced_documents.append(enhanced_doc)
        
        # Sort by upload time (newest first)
        enhanced_documents.sort(key=lambda x: x["uploaded_at"], reverse=True)
        
        # Calculate status counts
        status_counts = {
            "uploaded": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0
        }
        for doc in documents.values():
            status = doc.get("status", "unknown")
            if status in status_counts:
                status_counts[status] += 1
        
        return {
            "success": True,
            "documents": enhanced_documents,
            "total_count": len(enhanced_documents),
            "status_counts": status_counts
        }
    
    async def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific document by ID
        
        Args:
            document_id: The document ID to retrieve
            
        Returns:
            Document data or None if not found
        """
        document = await self.state_manager.get_document(document_id)
        if document:
            return get_document_display_info(document)
        return None
    
    async def start_processing(self, document_id: str) -> Dict[str, Any]:
        """
        Start processing a document manually
        
        Args:
            document_id: The document ID to process
            
        Returns:
            Processing start result
            
        Raises:
            FileNotFoundError: If document not found
            ValueError: If document cannot be processed
        """
        document = await self.state_manager.get_document(document_id)
        if not document:
            raise FileNotFoundError("Document not found")
        
        if document["status"] != "uploaded":
            raise ValueError(f"Document cannot be processed. Current status: {document['status']}")
        
        task_id = document.get("task_id")
        if not task_id:
            raise ValueError("Processing task not found")
        
        # Update document and task status
        document["status"] = "processing"
        document["updated_at"] = datetime.now().isoformat()
        await self.state_manager.save_document(document_id, document)
        
        task = await self.state_manager.get_task(task_id)
        if task:
            task["status"] = "pending"
            task["updated_at"] = datetime.now().isoformat()
            await self.state_manager.save_task(task_id, task)
        
        # Note: Actual processing would be triggered here via ProcessingService
        # This is separated to maintain single responsibility
        
        return {
            "success": True,
            "message": f"Document processing started for {document['file_name']}",
            "document_id": document_id,
            "task_id": task_id,
            "status": "processing"
        }
    
    async def delete_documents(self, document_ids: List[str]) -> Dict[str, Any]:
        """
        Delete multiple documents
        
        Args:
            document_ids: List of document IDs to delete
            
        Returns:
            Deletion results
        """
        deleted_count = 0
        deletion_results = []
        rag_instance = self.rag_initializer.get_rag_instance()
        
        for doc_id in document_ids:
            result = {
                "document_id": doc_id,
                "file_name": "unknown",
                "status": "success",
                "message": "",
                "details": {}
            }
            
            try:
                document = await self.state_manager.get_document(doc_id)
                if not document:
                    result.update({
                        "status": "not_found",
                        "message": "Document not found"
                    })
                    deletion_results.append(result)
                    continue
                
                result["file_name"] = document.get("file_name", "unknown")
                
                # Delete from RAG system if exists
                rag_doc_id = document.get("rag_doc_id")
                if rag_doc_id and rag_instance:
                    deletion_result = await rag_instance.lightrag.adelete_by_doc_id(rag_doc_id)
                    result["details"]["rag_deletion"] = {
                        "status": deletion_result.status,
                        "message": deletion_result.message
                    }
                
                # Delete physical file
                file_path = document.get("file_path")
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    result["details"]["file_deletion"] = "File deleted"
                else:
                    result["details"]["file_deletion"] = "File not found or already deleted"
                
                # Remove from state manager
                await self.state_manager.delete_document(doc_id)
                
                # Remove associated task
                task_id = document.get("task_id")
                if task_id:
                    await self.state_manager.delete_task(task_id)
                
                deleted_count += 1
                result["message"] = f"Document {document['file_name']} deleted successfully"
                
            except Exception as e:
                result.update({
                    "status": "error",
                    "message": f"Deletion failed: {str(e)}",
                    "details": {"error": str(e)}
                })
            
            deletion_results.append(result)
        
        success_count = len([r for r in deletion_results if r["status"] == "success"])
        
        return {
            "success": success_count > 0,
            "message": f"Successfully deleted {success_count}/{len(document_ids)} documents",
            "deleted_count": success_count,
            "deletion_results": deletion_results
        }
    
    async def clear_all_documents(self) -> Dict[str, Any]:
        """
        Clear all documents and associated data
        
        Returns:
            Cleanup results with statistics
        """
        documents = await self.state_manager.get_all_documents()
        count = len(documents)
        
        clear_results = {
            "total_documents": count,
            "files_deleted": 0,
            "rag_deletions": {"success": 0, "failed": 0, "skipped": 0},
            "errors": []
        }
        
        rag_instance = self.rag_initializer.get_rag_instance()
        
        # Delete all documents
        for doc_id, doc in documents.items():
            try:
                # Delete from RAG system
                rag_doc_id = doc.get("rag_doc_id")
                if rag_doc_id and rag_instance:
                    try:
                        deletion_result = await rag_instance.lightrag.adelete_by_doc_id(rag_doc_id)
                        if deletion_result.status == "success":
                            clear_results["rag_deletions"]["success"] += 1
                        else:
                            clear_results["rag_deletions"]["failed"] += 1
                    except Exception as e:
                        clear_results["rag_deletions"]["failed"] += 1
                        clear_results["errors"].append(f"RAG deletion failed {rag_doc_id}: {str(e)}")
                else:
                    clear_results["rag_deletions"]["skipped"] += 1
                
                # Delete physical file
                file_path = doc.get("file_path")
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    clear_results["files_deleted"] += 1
                
                # Delete from state manager
                await self.state_manager.delete_document(doc_id)
                
                # Delete associated task
                task_id = doc.get("task_id")
                if task_id:
                    await self.state_manager.delete_task(task_id)
                    
            except Exception as e:
                clear_results["errors"].append(f"Document deletion failed {doc.get('file_name', doc_id)}: {str(e)}")
        
        # Clear all remaining state
        await self.state_manager.clear_all_documents()
        await self.state_manager.clear_all_tasks()
        
        success_rate = (clear_results["rag_deletions"]["success"] / max(count, 1)) * 100
        message = f"Cleared {count} documents, RAG deletion success rate: {success_rate:.1f}%"
        
        if clear_results["errors"]:
            message += f", {len(clear_results['errors'])} errors"
        
        return {
            "success": True,
            "message": message,
            "details": clear_results
        }
    
    def _create_initial_task(
        self,
        task_id: str,
        document_id: str,
        upload_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create initial task data structure"""
        return {
            "task_id": task_id,
            "status": "pending",
            "stage": "parsing",
            "progress": 0,
            "file_path": upload_result["file_path"],
            "file_name": upload_result["original_filename"],
            "file_size": upload_result["file_size"],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "document_id": document_id,
            "total_stages": 8,  # Number of processing stages
            "stage_details": {
                "parsing": {"status": "pending", "progress": 0},
                "separation": {"status": "pending", "progress": 0},
                "text_insert": {"status": "pending", "progress": 0},
                "image_process": {"status": "pending", "progress": 0},
                "table_process": {"status": "pending", "progress": 0},
                "equation_process": {"status": "pending", "progress": 0},
                "graph_build": {"status": "pending", "progress": 0},
                "indexing": {"status": "pending", "progress": 0},
            },
            "multimodal_stats": {
                "images_count": 0,
                "tables_count": 0,
                "equations_count": 0,
                "images_processed": 0,
                "tables_processed": 0,
                "equations_processed": 0,
                "processing_success_rate": 0.0,
                "text_chunks": 0,
                "knowledge_entities": 0,
                "knowledge_relationships": 0
            }
        }