"""
Document Management API Endpoints
Clean, focused API routes for document operations
"""

from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from core.dependencies import get_document_service, get_current_user_optional
from models.requests import DocumentDeleteRequest
from models.responses import DocumentResponse, DocumentListResponse
from services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_service: DocumentService = Depends(get_document_service),
    current_user: str = Depends(get_current_user_optional)
) -> DocumentResponse:
    """
    Upload a single document
    
    - **file**: Document file to upload
    - Returns: Document metadata and upload status
    """
    try:
        result = await document_service.upload_single(file)
        return DocumentResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload/batch")
async def upload_documents_batch(
    files: List[UploadFile] = File(...),
    document_service: DocumentService = Depends(get_document_service),
    current_user: str = Depends(get_current_user_optional)
):
    """
    Upload multiple documents in batch
    
    - **files**: List of document files to upload
    - Returns: Batch upload results with individual file status
    """
    try:
        result = await document_service.upload_batch(files)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    document_service: DocumentService = Depends(get_document_service)
) -> DocumentListResponse:
    """
    Get list of all documents with enhanced display information
    
    - Returns: List of documents with processing status and metadata
    """
    try:
        result = await document_service.list_documents()
        return DocumentListResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    document_service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """
    Get specific document details
    
    - **document_id**: ID of the document to retrieve
    - Returns: Detailed document information
    """
    try:
        result = await document_service.get_document(document_id)
        if not result:
            raise HTTPException(status_code=404, detail="Document not found")
        return DocumentResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")


@router.post("/{document_id}/process")
async def process_document_manually(
    document_id: str,
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Manually trigger document processing
    
    - **document_id**: ID of the document to process
    - Returns: Processing status and task information
    """
    try:
        result = await document_service.start_processing(document_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")


@router.delete("", response_model=dict)
async def delete_documents(
    request: DocumentDeleteRequest,
    document_service: DocumentService = Depends(get_document_service)
) -> dict:
    """
    Delete multiple documents
    
    - **document_ids**: List of document IDs to delete
    - Returns: Deletion results with individual document status
    """
    try:
        result = await document_service.delete_documents(request.document_ids)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete documents: {str(e)}")


@router.delete("/clear")
async def clear_all_documents(
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Clear all documents and associated data
    
    - Returns: Cleanup results with detailed statistics
    """
    try:
        result = await document_service.clear_all_documents()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear documents: {str(e)}")