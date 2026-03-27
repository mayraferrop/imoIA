"""Router partilhado para gestao de documentos.

Upload, download, listagem e remocao de ficheiros.
Usado pelo M5 e futuramente por M4, M6, M9.

Tenant lookup migrado para Supabase REST.
DocumentStorageService ainda usa SQLAlchemy (filesystem + ORM Document).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import Response
from loguru import logger

from src.database.db import get_session
from src.database import supabase_rest as db
from src.shared.document_storage import DocumentStorageService

router = APIRouter()


@router.post("/upload", summary="Upload de documento")
async def upload_document(
    file: UploadFile = File(...),
    deal_id: Optional[str] = Form(None),
    dd_item_id: Optional[str] = Form(None),
    document_type: str = Form("outro"),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    uploaded_by: str = Form("system"),
) -> Dict[str, Any]:
    """Upload de ficheiro para o storage."""
    content = await file.read()
    tenant_id = db.ensure_tenant()
    with get_session() as session:
        storage = DocumentStorageService(session)
        return storage.upload_document(
            file_content=content,
            filename=file.filename or "document",
            tenant_id=tenant_id,
            deal_id=deal_id,
            dd_item_id=dd_item_id,
            document_type=document_type,
            title=title,
            description=description,
            tags=tags,
            uploaded_by=uploaded_by,
        )


@router.get("/{document_id}/download", summary="Download de documento")
async def download_document(document_id: str) -> Response:
    """Retorna o ficheiro para download."""
    with get_session() as session:
        storage = DocumentStorageService(session)
        try:
            content, filename, mime_type = storage.get_file_content(document_id)
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(status_code=404, detail=str(e))

        return Response(
            content=content,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )


@router.get("/{document_id}", summary="Metadados de documento")
async def get_document(document_id: str) -> Dict[str, Any]:
    """Retorna metadados de um documento."""
    with get_session() as session:
        storage = DocumentStorageService(session)
        doc = storage.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Documento nao encontrado")
        return doc


@router.get("/", summary="Listar documentos")
async def list_documents(
    deal_id: Optional[str] = Query(None),
    dd_item_id: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """Lista documentos com filtros."""
    with get_session() as session:
        storage = DocumentStorageService(session)
        return storage.list_documents(deal_id, dd_item_id, document_type)


@router.put("/{document_id}", summary="Substituir documento")
async def replace_document(
    document_id: str,
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """Substitui ficheiro de um documento existente."""
    content = await file.read()
    with get_session() as session:
        storage = DocumentStorageService(session)
        try:
            return storage.replace_document(
                document_id, content, file.filename
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{document_id}", summary="Remover documento")
async def delete_document(
    document_id: str,
    hard: bool = Query(False, description="Hard delete (apaga ficheiro do disco)"),
) -> Dict[str, Any]:
    """Remove documento (soft ou hard delete)."""
    with get_session() as session:
        storage = DocumentStorageService(session)
        result = storage.delete_document(document_id, hard_delete=hard)
        if not result:
            raise HTTPException(status_code=404, detail="Documento nao encontrado")
        return {"success": True, "hard_delete": hard}
