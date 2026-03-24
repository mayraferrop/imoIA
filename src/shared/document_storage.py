"""Servico partilhado de armazenamento de documentos.

Versao actual: filesystem local (pasta storage/documents/).
Futuro: Supabase Storage (S3-compatible).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy.orm import Session

from src.database.models_v2 import Document, DueDiligenceItem

STORAGE_BASE = Path("storage/documents")


class DocumentStorageService:
    """Armazenamento de ficheiros no filesystem local."""

    def __init__(self, session: Session, base_path: Optional[str] = None) -> None:
        self.session = session
        self.base_path = Path(base_path) if base_path else STORAGE_BASE
        self.base_path.mkdir(parents=True, exist_ok=True)

    def upload_document(
        self,
        file_content: bytes,
        filename: str,
        tenant_id: str,
        deal_id: Optional[str] = None,
        dd_item_id: Optional[str] = None,
        document_type: str = "outro",
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[str] = None,
        uploaded_by: str = "system",
    ) -> Dict[str, Any]:
        """Upload de ficheiro. Returns dict with document metadata."""
        ext = Path(filename).suffix.lower()
        mime = self._guess_mime_type(ext)
        stored_name = f"{uuid4()}{ext}"

        subfolder = deal_id or "general"
        dest_dir = self.base_path / subfolder
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / stored_name

        dest_path.write_bytes(file_content)

        doc = Document(
            id=str(uuid4()),
            tenant_id=tenant_id,
            deal_id=deal_id,
            dd_item_id=dd_item_id,
            entity_type="due_diligence" if dd_item_id else ("deal" if deal_id else None),
            entity_id=dd_item_id or deal_id,
            filename=filename,
            stored_filename=stored_name,
            file_path=str(dest_path),
            file_size=len(file_content),
            mime_type=mime,
            file_extension=ext.lstrip("."),
            document_type=document_type,
            title=title or filename,
            description=description,
            tags=tags,
            uploaded_by=uploaded_by,
        )
        self.session.add(doc)

        # If linked to DD item, update that item
        if dd_item_id:
            dd_item = self.session.get(DueDiligenceItem, dd_item_id)
            if dd_item:
                dd_item.document_url = f"/api/v1/documents/{doc.id}/download"
                dd_item.document_date = datetime.now(timezone.utc)
                if dd_item.status == "pendente":
                    dd_item.status = "obtido"

        self.session.flush()
        logger.info(f"Documento uploaded: {filename} ({len(file_content)} bytes)")
        return self._doc_to_dict(doc)

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        doc = self.session.get(Document, document_id)
        return self._doc_to_dict(doc) if doc else None

    def get_file_content(self, document_id: str) -> tuple:
        """Returns (bytes, filename, mime_type)."""
        doc = self.session.get(Document, document_id)
        if not doc:
            raise ValueError("Documento nao encontrado")
        path = Path(doc.file_path)
        if not path.exists():
            raise FileNotFoundError(f"Ficheiro nao encontrado: {path}")
        return path.read_bytes(), doc.filename, doc.mime_type or "application/octet-stream"

    def list_documents(
        self,
        deal_id: Optional[str] = None,
        dd_item_id: Optional[str] = None,
        document_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        from sqlalchemy import select
        stmt = select(Document).where(Document.is_archived == False)
        if deal_id:
            stmt = stmt.where(Document.deal_id == deal_id)
        if dd_item_id:
            stmt = stmt.where(Document.dd_item_id == dd_item_id)
        if document_type:
            stmt = stmt.where(Document.document_type == document_type)
        stmt = stmt.order_by(Document.created_at.desc())
        docs = self.session.execute(stmt).scalars().all()
        return [self._doc_to_dict(d) for d in docs]

    def delete_document(self, document_id: str, hard_delete: bool = False) -> bool:
        doc = self.session.get(Document, document_id)
        if not doc:
            return False
        if hard_delete:
            path = Path(doc.file_path)
            if path.exists():
                path.unlink()
            if doc.dd_item_id:
                dd_item = self.session.get(DueDiligenceItem, doc.dd_item_id)
                if dd_item and dd_item.document_url and doc.id in (dd_item.document_url or ""):
                    dd_item.document_url = None
                    dd_item.status = "pendente"
            self.session.delete(doc)
        else:
            doc.is_archived = True
        self.session.flush()
        logger.info(f"Documento {'apagado' if hard_delete else 'arquivado'}: {doc.filename}")
        return True

    def replace_document(self, document_id: str, new_content: bytes, new_filename: Optional[str] = None) -> Dict[str, Any]:
        doc = self.session.get(Document, document_id)
        if not doc:
            raise ValueError("Documento nao encontrado")
        old_path = Path(doc.file_path)
        if old_path.exists():
            old_path.unlink()
        ext = Path(new_filename or doc.filename).suffix.lower()
        stored_name = f"{uuid4()}{ext}"
        dest_path = old_path.parent / stored_name
        dest_path.write_bytes(new_content)
        doc.stored_filename = stored_name
        doc.file_path = str(dest_path)
        doc.file_size = len(new_content)
        doc.mime_type = self._guess_mime_type(ext)
        doc.file_extension = ext.lstrip(".")
        if new_filename:
            doc.filename = new_filename
        self.session.flush()
        return self._doc_to_dict(doc)

    @staticmethod
    def _guess_mime_type(ext: str) -> str:
        mime_map = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".svg": "image/svg+xml",
            ".webp": "image/webp",
            ".ico": "image/x-icon",
            ".txt": "text/plain",
            ".csv": "text/csv",
            ".zip": "application/zip",
        }
        return mime_map.get(ext.lower(), "application/octet-stream")

    @staticmethod
    def _doc_to_dict(doc: Document) -> Dict[str, Any]:
        return {
            "id": doc.id,
            "tenant_id": doc.tenant_id,
            "deal_id": doc.deal_id,
            "dd_item_id": doc.dd_item_id,
            "entity_type": doc.entity_type,
            "filename": doc.filename,
            "stored_filename": doc.stored_filename,
            "file_path": doc.file_path,
            "file_size": doc.file_size,
            "mime_type": doc.mime_type,
            "file_extension": doc.file_extension,
            "document_type": doc.document_type,
            "title": doc.title,
            "description": doc.description,
            "tags": doc.tags,
            "uploaded_by": doc.uploaded_by,
            "is_archived": doc.is_archived,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }
