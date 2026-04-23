"""Router partilhado para gestao de documentos.

Upload, download, listagem e remocao de ficheiros.
Usado pelo M5 e futuramente por M4, M6, M9.

Tenant lookup migrado para Supabase REST.
DocumentStorageService ainda usa SQLAlchemy (filesystem + ORM Document).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import RedirectResponse, Response
from loguru import logger

from src.database.db import get_session
from src.database.models_v2 import Document
# FIXME(jwt-refactor): migrar para JWT do utilizador quando tabelas tiverem policies 'authenticated'
from src.database import supabase_rest as db
from src.shared.document_storage import DocumentStorageService
from src.shared.storage_provider import get_signed_url

router = APIRouter()
# Router público (sem auth) para download via <img> tag — signed URL serve de autorização.
# Registado em main.py como "/api/v1/documents" sem auth_deps, ANTES do router principal.
public_router = APIRouter()


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


@public_router.get("/{document_id}/download", summary="Download de documento")
def download_document(document_id: str):
    """Retorna o ficheiro para download.

    Endpoint PÚBLICO (sem auth) porque `<img>` não envia Authorization header.
    Segurança: UUID v4 inadivinhavel + signed URL com TTL de 1h.

    - Documentos em bucket (file_path = `bucket:path`) → redirect (302) para
      signed URL com TTL 1h. Permite `<img src>` sem header Authorization.
    - Documentos legacy em filesystem → stream directo (comportamento antigo).
    """
    with get_session() as session:
        doc = session.get(Document, document_id)
        if not doc or not doc.file_path:
            raise HTTPException(status_code=404, detail="Documento nao encontrado")

        # Formato bucket: "{bucket}:{path}" — nao comeca com "/"
        if ":" in doc.file_path and not doc.file_path.startswith("/"):
            bucket, bucket_path = doc.file_path.split(":", 1)
            try:
                signed = get_signed_url(bucket, bucket_path, expires_in=3600)
            except Exception as exc:
                logger.error(f"Signed URL falhou para doc={document_id}: {exc}")
                raise HTTPException(status_code=500, detail="Erro a gerar URL")
            return RedirectResponse(url=signed, status_code=302)

        # Legacy filesystem
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
def get_document(document_id: str) -> Dict[str, Any]:
    """Retorna metadados de um documento."""
    with get_session() as session:
        storage = DocumentStorageService(session)
        doc = storage.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Documento nao encontrado")
        return doc


@router.get("/", summary="Listar documentos")
def list_documents(
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
def delete_document(
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
