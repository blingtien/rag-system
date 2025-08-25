"""
State Management Layer
Handles persistent storage and retrieval of application state
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import aiofiles


class StateManager:
    """Manages persistent state for documents, tasks, and batch operations"""
    
    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
        self.state_file = working_dir / "api_state.json"
        self._documents: Dict[str, Dict] = {}
        self._tasks: Dict[str, Dict] = {}
        self._batch_operations: Dict[str, Dict] = {}
        self._loaded = False
    
    async def load_state(self) -> None:
        """Load state from persistent storage"""
        if self._loaded:
            return
        
        try:
            if self.state_file.exists():
                async with aiofiles.open(self.state_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)
                
                self._documents = data.get("documents", {})
                self._tasks = data.get("tasks", {})
                self._batch_operations = data.get("batch_operations", {})
                
                print(f"Loaded state: {len(self._documents)} documents, {len(self._tasks)} tasks")
            
            # Load existing RAG documents
            await self._load_existing_rag_documents()
            
        except Exception as e:
            print(f"Failed to load state: {e}")
            # Initialize empty state
            self._documents = {}
            self._tasks = {}
            self._batch_operations = {}
        
        self._loaded = True
    
    async def save_state(self) -> None:
        """Save current state to persistent storage"""
        try:
            state_data = {
                "documents": self._documents,
                "tasks": self._tasks,
                "batch_operations": self._batch_operations,
                "saved_at": datetime.now().isoformat()
            }
            
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temporary file first, then rename for atomicity
            temp_file = self.state_file.with_suffix('.tmp')
            async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(state_data, ensure_ascii=False, indent=2))
            
            # Atomic rename
            temp_file.rename(self.state_file)
            
            print(f"Saved state: {len(self._documents)} documents")
            
        except Exception as e:
            print(f"Failed to save state: {e}")
    
    async def _load_existing_rag_documents(self) -> None:
        """Load documents that already exist in RAG system"""
        doc_status_file = self.working_dir / "kv_store_doc_status.json"
        if not doc_status_file.exists():
            return
        
        try:
            async with aiofiles.open(doc_status_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                rag_docs = json.loads(content)
            
            added_count = 0
            for rag_doc_id, doc_info in rag_docs.items():
                if doc_info.get('status') == 'processed':
                    # Check if document already exists in our state
                    existing = any(
                        doc.get('rag_doc_id') == rag_doc_id 
                        for doc in self._documents.values()
                    )
                    
                    if not existing:
                        # Generate new document record
                        document_id = f"rag_{rag_doc_id}"
                        file_name = os.path.basename(doc_info.get('file_path', f'document_{rag_doc_id}'))
                        
                        document = {
                            "document_id": document_id,
                            "file_name": file_name,
                            "file_path": doc_info.get('file_path', ''),
                            "file_size": doc_info.get('content_length', 0),
                            "status": "completed",
                            "created_at": doc_info.get('created_at', datetime.now().isoformat()),
                            "updated_at": doc_info.get('updated_at', datetime.now().isoformat()),
                            "processing_time": 0,
                            "content_length": doc_info.get('content_length', 0),
                            "chunks_count": doc_info.get('chunks_count', 0),
                            "rag_doc_id": rag_doc_id,
                            "content_summary": doc_info.get('content_summary', '')[:100] + "..." if doc_info.get('content_summary') else ""
                        }
                        
                        self._documents[document_id] = document
                        added_count += 1
            
            print(f"Loaded {added_count} existing RAG documents")
            
        except Exception as e:
            print(f"Failed to load existing RAG documents: {e}")
    
    # Document operations
    async def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        return self._documents.get(document_id)
    
    async def save_document(self, document_id: str, document_data: Dict[str, Any]) -> None:
        """Save or update document"""
        self._documents[document_id] = document_data
        await self.save_state()
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete document by ID"""
        if document_id in self._documents:
            del self._documents[document_id]
            await self.save_state()
            return True
        return False
    
    async def get_all_documents(self) -> Dict[str, Dict[str, Any]]:
        """Get all documents"""
        return self._documents.copy()
    
    async def find_documents_by_filename(self, filename: str) -> List[Dict[str, Any]]:
        """Find documents by filename"""
        return [
            doc for doc in self._documents.values() 
            if doc.get("file_name") == filename
        ]
    
    async def clear_all_documents(self) -> None:
        """Clear all documents"""
        self._documents.clear()
        await self.save_state()
    
    # Task operations
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID"""
        return self._tasks.get(task_id)
    
    async def save_task(self, task_id: str, task_data: Dict[str, Any]) -> None:
        """Save or update task"""
        self._tasks[task_id] = task_data
        await self.save_state()
    
    async def delete_task(self, task_id: str) -> bool:
        """Delete task by ID"""
        if task_id in self._tasks:
            del self._tasks[task_id]
            await self.save_state()
            return True
        return False
    
    async def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get all tasks"""
        return self._tasks.copy()
    
    async def get_tasks_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get tasks by status"""
        return [
            task for task in self._tasks.values() 
            if task.get("status") == status
        ]
    
    async def clear_all_tasks(self) -> None:
        """Clear all tasks"""
        self._tasks.clear()
        await self.save_state()
    
    # Batch operations
    async def get_batch_operation(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get batch operation by ID"""
        return self._batch_operations.get(batch_id)
    
    async def save_batch_operation(self, batch_id: str, batch_data: Dict[str, Any]) -> None:
        """Save or update batch operation"""
        self._batch_operations[batch_id] = batch_data
        await self.save_state()
    
    async def get_all_batch_operations(self) -> Dict[str, Dict[str, Any]]:
        """Get all batch operations"""
        return self._batch_operations.copy()
    
    async def get_batch_operations_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get batch operations by status"""
        return [
            batch for batch in self._batch_operations.values() 
            if batch.get("status") == status
        ]
    
    # Statistics and analytics
    async def get_statistics(self) -> Dict[str, Any]:
        """Get state statistics"""
        active_tasks = len([t for t in self._tasks.values() if t.get("status") == "running"])
        completed_docs = len([d for d in self._documents.values() if d.get("status") == "completed"])
        running_batches = len([b for b in self._batch_operations.values() if b.get("status") == "running"])
        
        return {
            "documents": {
                "total": len(self._documents),
                "completed": completed_docs,
                "processing": len([d for d in self._documents.values() if d.get("status") == "processing"]),
                "failed": len([d for d in self._documents.values() if d.get("status") == "failed"])
            },
            "tasks": {
                "total": len(self._tasks),
                "active": active_tasks,
                "completed": len([t for t in self._tasks.values() if t.get("status") == "completed"]),
                "failed": len([t for t in self._tasks.values() if t.get("status") == "failed"])
            },
            "batch_operations": {
                "total": len(self._batch_operations),
                "running": running_batches,
                "completed": len([b for b in self._batch_operations.values() if b.get("status") == "completed"])
            }
        }
    
    async def cleanup_old_data(self, max_age_days: int = 30) -> Dict[str, int]:
        """Clean up old completed tasks and batch operations"""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        cleaned_tasks = 0
        cleaned_batches = 0
        
        # Clean old completed tasks
        tasks_to_remove = []
        for task_id, task in self._tasks.items():
            if (task.get("status") in ["completed", "failed"] and 
                "completed_at" in task):
                try:
                    completed_at = datetime.fromisoformat(task["completed_at"])
                    if completed_at < cutoff_date:
                        tasks_to_remove.append(task_id)
                except ValueError:
                    continue
        
        for task_id in tasks_to_remove:
            del self._tasks[task_id]
            cleaned_tasks += 1
        
        # Clean old batch operations
        batches_to_remove = []
        for batch_id, batch in self._batch_operations.items():
            if (batch.get("status") in ["completed", "failed"] and 
                "completed_at" in batch):
                try:
                    completed_at = datetime.fromisoformat(batch["completed_at"])
                    if completed_at < cutoff_date:
                        batches_to_remove.append(batch_id)
                except ValueError:
                    continue
        
        for batch_id in batches_to_remove:
            del self._batch_operations[batch_id]
            cleaned_batches += 1
        
        if cleaned_tasks > 0 or cleaned_batches > 0:
            await self.save_state()
        
        return {
            "cleaned_tasks": cleaned_tasks,
            "cleaned_batches": cleaned_batches
        }