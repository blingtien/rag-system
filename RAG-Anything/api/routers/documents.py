"""
文档管理路由
处理文档上传、处理、删除等相关的API端点
"""
from typing import List, Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from pydantic import BaseModel

from config.dependencies import (
    get_current_user_optional,
    get_document_service
)
from services.document_service import DocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


# 请求/响应模型
class DocumentDeleteRequest(BaseModel):
    document_ids: List[str]


class BatchUploadResponse(BaseModel):
    success: bool
    uploaded_count: int
    failed_count: int
    total_files: int
    results: List[dict]
    message: str


class ScanFolderResponse(BaseModel):
    success: bool
    scanned_files: int
    unprocessed_files: int
    unprocessed_file_list: List[dict]
    message: str


class BatchProcessUnprocessedRequest(BaseModel):
    parser: Optional[str] = "mineru" 
    parse_method: Optional[str] = "auto"


@router.post("/upload") 
async def upload_document(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user_optional),
    document_service: DocumentService = Depends(get_document_service)
):
    """单文档上传端点"""
    try:
        result = await document_service.upload_single_document(file, current_user)
        return result.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/batch", response_model=BatchUploadResponse)
async def upload_documents_batch(
    files: List[UploadFile] = File(...),
    current_user: str = Depends(get_current_user_optional),
    document_service: DocumentService = Depends(get_document_service)
):
    """批量文档上传端点"""
    try:
        result = await document_service.upload_batch_documents(files, current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/process")
async def process_document_manually(
    document_id: str,
    document_service: DocumentService = Depends(get_document_service)
):
    """手动触发文档处理端点"""
    try:
        result = await document_service.trigger_document_processing(document_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_documents(
    document_service: DocumentService = Depends(get_document_service)
):
    """获取文档列表"""
    try:
        result = await document_service.get_document_list()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/")
async def delete_documents(
    request: DocumentDeleteRequest,
    document_service: DocumentService = Depends(get_document_service)
):
    """删除文档"""
    try:
        success_count, deletion_results = await document_service.delete_documents(request.document_ids)
        
        return {
            "success": success_count > 0,
            "message": f"成功删除 {success_count}/{len(request.document_ids)} 个文档",
            "deleted_count": success_count,
            "deletion_results": [result.dict() for result in deletion_results]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_documents(
    document_service: DocumentService = Depends(get_document_service)
):
    """清空所有文档"""
    try:
        result = await document_service.clear_all_documents()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan-uploads-folder", response_model=ScanFolderResponse)
async def scan_uploads_folder(
    document_service: DocumentService = Depends(get_document_service)
):
    """扫描uploads文件夹，发现未处理的文件"""
    try:
        result = await document_service.scan_uploads_folder()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-unprocessed-files")
async def process_unprocessed_files(
    request: BatchProcessUnprocessedRequest,
    document_service: DocumentService = Depends(get_document_service)
):
    """批量处理uploads文件夹中未处理的文件"""
    try:
        result = await document_service.process_unprocessed_files(
            parser=request.parser,
            parse_method=request.parse_method
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

