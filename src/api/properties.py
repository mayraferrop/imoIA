"""Router para gestao de Properties — via Supabase REST API.

Todos os endpoints leem e escrevem directamente no Supabase PostgreSQL
via REST API (sem SQLAlchemy/SQLite).
"""

from __future__ import annotations

from pathlib import Path as _Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from loguru import logger
from pydantic import BaseModel, Field

# FIXME(jwt-refactor): migrar para JWT do utilizador quando tabelas tiverem policies 'authenticated'
from src.database import supabase_rest as supa

router = APIRouter()


def _as_list(value: Any) -> List[Dict[str, Any]]:
    """Normaliza campo photos (JSON/str/None) para lista."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


# ---------------------------------------------------------------------------
# Schemas Pydantic
# ---------------------------------------------------------------------------


class PropertyCreateSchema(BaseModel):
    """Schema para criacao manual de propriedade."""

    district: Optional[str] = None
    municipality: Optional[str] = None
    parish: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    property_type: Optional[str] = None
    typology: Optional[str] = None
    gross_area_m2: Optional[float] = None
    net_area_m2: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    floor: Optional[int] = None
    has_elevator: Optional[bool] = None
    has_parking: Optional[bool] = None
    construction_year: Optional[int] = None
    energy_certificate: Optional[str] = None
    asking_price: Optional[float] = None
    condition: Optional[str] = None
    is_off_market: bool = False
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class PropertyUpdateSchema(BaseModel):
    """Schema para actualizacao de propriedade."""

    district: Optional[str] = None
    municipality: Optional[str] = None
    parish: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    property_type: Optional[str] = None
    typology: Optional[str] = None
    gross_area_m2: Optional[float] = None
    net_area_m2: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    floor: Optional[int] = None
    has_elevator: Optional[bool] = None
    has_parking: Optional[bool] = None
    construction_year: Optional[int] = None
    energy_certificate: Optional[str] = None
    asking_price: Optional[float] = None
    condition: Optional[str] = None
    status: Optional[str] = None
    is_off_market: Optional[bool] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Endpoints — Supabase REST
# ---------------------------------------------------------------------------


@router.get("/", summary="Listar propriedades")
async def list_properties(
    status: Optional[str] = None,
    municipality: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Lista propriedades via Supabase REST."""
    params = "select=*&order=created_at.desc"
    if status:
        params += f"&status=eq.{status}"
    else:
        params += "&status=neq.descartado"
    if municipality:
        params += f"&municipality=eq.{municipality}"
    params += f"&limit={limit}&offset={offset}"

    items = supa._get("properties", params)

    # Contar total (query separada)
    count_params = "select=id"
    if status:
        count_params += f"&status=eq.{status}"
    else:
        count_params += "&status=neq.descartado"
    if municipality:
        count_params += f"&municipality=eq.{municipality}"
    supa._ensure_config()
    try:
        resp = httpx.get(
            f"{supa._SUPA_URL}/rest/v1/properties?{count_params}",
            headers={**supa._headers(), "Prefer": "count=exact", "Range": "0-0"},
            timeout=10,
        )
        # Extrair count do header Content-Range: 0-0/155
        cr = resp.headers.get("content-range", "")
        total = int(cr.split("/")[1]) if "/" in cr else len(items)
    except Exception:
        total = len(items)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.post("/", summary="Criar propriedade manualmente")
async def create_property(data: PropertyCreateSchema) -> Dict[str, Any]:
    """Cria uma nova propriedade no Supabase."""
    tenant_id = supa.ensure_tenant()
    row = {
        "id": str(uuid4()),
        "tenant_id": tenant_id,
        "source": "manual",
        "country": "PT",
        "status": "lead",
    }
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is not None:
            row[k] = v

    result = supa._post("properties", row)
    logger.info(f"Property criada: {row['id']}")
    return result[0] if result else row


@router.get("/{property_id}", summary="Detalhe de uma propriedade")
async def get_property(property_id: str) -> Dict[str, Any]:
    """Retorna detalhe completo de uma propriedade."""
    rows = supa._get("properties", f"id=eq.{property_id}&select=*&limit=1")
    if not rows:
        raise HTTPException(status_code=404, detail="Propriedade nao encontrada")
    return rows[0]


@router.patch("/{property_id}", summary="Actualizar propriedade")
async def update_property(
    property_id: str, data: PropertyUpdateSchema
) -> Dict[str, Any]:
    """Actualiza campos de uma propriedade no Supabase."""
    supa._ensure_config()
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum campo para actualizar")

    resp = httpx.patch(
        f"{supa._SUPA_URL}/rest/v1/properties?id=eq.{property_id}",
        headers=supa._headers(),
        json=update_data,
        timeout=10,
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    result = resp.json()
    if not result:
        raise HTTPException(status_code=404, detail="Propriedade nao encontrada")

    logger.info(f"Property {property_id} actualizada: {list(update_data.keys())}")
    return result[0]


# ---------------------------------------------------------------------------
# Fotos (M1) — armazenadas em Supabase Storage bucket `properties`
# Padrão espelhado do M7 (listing photos) para facilitar herança via deal.
# ---------------------------------------------------------------------------


_MIME_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
}


@router.post("/{property_id}/photos", summary="Upload fotos da propriedade")
async def upload_property_photos(
    property_id: str,
    files: List[UploadFile] = File(...),
) -> Dict[str, Any]:
    """Upload de fotos para uma propriedade. Grava em Supabase Storage e cria
    Documents. Actualiza properties.photos + cover_photo_url."""
    from src.database.db import get_session
    from src.database.models_v2 import Document
    from src.shared.storage_provider import BUCKET_PROPERTIES, upload_file

    prop = supa.get_by_id("properties", property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Propriedade nao encontrada")

    tid = supa.ensure_tenant()

    with get_session() as session:
        uploaded: List[Dict[str, Any]] = []
        photos = _as_list(prop.get("photos"))

        for i, file in enumerate(files):
            content = await file.read()
            ext = _Path(file.filename or "photo.jpg").suffix.lower() or ".jpg"
            mime = _MIME_MAP.get(ext, "application/octet-stream")

            doc_id = str(uuid4())
            bucket_path = f"tenants/{tid}/properties/{property_id}/{doc_id}{ext}"
            upload_file(BUCKET_PROPERTIES, bucket_path, content, mime)

            doc = Document(
                id=doc_id,
                tenant_id=tid,
                entity_type="property",
                entity_id=property_id,
                filename=file.filename or f"photo_{i}{ext}",
                stored_filename=f"{doc_id}{ext}",
                file_path=f"{BUCKET_PROPERTIES}:{bucket_path}",
                file_size=len(content),
                mime_type=mime,
                file_extension=ext.lstrip("."),
                document_type="property_photo",
                title=f"Foto {len(photos) + i + 1}",
                uploaded_by="system",
            )
            session.add(doc)
            session.flush()

            photo_entry = {
                "document_id": doc_id,
                "url": f"/api/v1/documents/{doc_id}/download",
                "filename": file.filename,
                "order": len(photos) + i,
                "is_cover": len(photos) == 0 and i == 0,
            }
            photos.append(photo_entry)
            uploaded.append(photo_entry)

    patch: Dict[str, Any] = {"photos": photos}
    if not prop.get("cover_photo_url") and uploaded:
        patch["cover_photo_url"] = uploaded[0]["url"]
    supa.update("properties", property_id, patch)

    logger.info(
        f"Property {property_id}: {len(uploaded)} fotos adicionadas "
        f"(total={len(photos)})"
    )
    return {"uploaded": len(uploaded), "total_photos": len(photos), "photos": uploaded}


@router.get("/{property_id}/photos", summary="Listar fotos da propriedade")
async def list_property_photos(property_id: str) -> List[Dict[str, Any]]:
    prop = supa.get_by_id("properties", property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Propriedade nao encontrada")
    return _as_list(prop.get("photos"))


@router.post(
    "/{property_id}/photos/set-cover", summary="Definir foto de capa"
)
async def set_property_cover(
    property_id: str,
    document_id: str = Query(...),
) -> Dict[str, Any]:
    prop = supa.get_by_id("properties", property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Propriedade nao encontrada")

    photos = _as_list(prop.get("photos"))
    if not any(p.get("document_id") == document_id for p in photos):
        raise HTTPException(status_code=404, detail="Foto nao encontrada")

    for p in photos:
        p["is_cover"] = p.get("document_id") == document_id

    cover_url = f"/api/v1/documents/{document_id}/download"
    supa.update("properties", property_id, {
        "photos": photos,
        "cover_photo_url": cover_url,
    })
    return {"cover_photo_url": cover_url}


@router.delete(
    "/{property_id}/photos/{document_id}", summary="Remover foto"
)
async def delete_property_photo(
    property_id: str, document_id: str
) -> Dict[str, Any]:
    from src.database.db import get_session
    from src.database.models_v2 import Document
    from src.shared.storage_provider import delete_file

    prop = supa.get_by_id("properties", property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Propriedade nao encontrada")

    photos = _as_list(prop.get("photos"))
    target = next((p for p in photos if p.get("document_id") == document_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Foto nao encontrada")

    was_cover = bool(target.get("is_cover")) or (
        prop.get("cover_photo_url")
        and document_id in str(prop.get("cover_photo_url"))
    )

    with get_session() as session:
        doc = session.get(Document, document_id)
        if doc and doc.file_path and ":" in doc.file_path:
            bucket, bucket_path = doc.file_path.split(":", 1)
            try:
                delete_file(bucket, bucket_path)
            except Exception as exc:
                logger.warning(
                    f"delete_file falhou bucket={bucket} path={bucket_path}: {exc}"
                )
        if doc:
            session.delete(doc)

    new_photos = [p for p in photos if p.get("document_id") != document_id]
    for i, p in enumerate(new_photos):
        p["order"] = i

    patch: Dict[str, Any] = {"photos": new_photos}
    if was_cover:
        if new_photos:
            new_cover = new_photos[0]
            new_cover["is_cover"] = True
            patch["cover_photo_url"] = new_cover["url"]
        else:
            patch["cover_photo_url"] = None
    supa.update("properties", property_id, patch)

    return {"deleted": document_id, "remaining": len(new_photos)}
