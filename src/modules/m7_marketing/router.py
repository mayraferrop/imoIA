"""Endpoints M7 — Marketing Engine.

Brand kit, conteudo IA multilingue, publicacao multicanal, SEO.

# FIXME(jwt-refactor): imports inline de supabase_rest usam SERVICE_ROLE_KEY.
# Migrar para JWT do utilizador quando tabelas tiverem policies 'authenticated'.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from loguru import logger

from src.modules.m7_marketing.schemas import (
    BrandKitSchema,
    ChangePriceSchema,
    GenerateContentSchema,
    ListingCreateSchema,
    ListingUpdateSchema,
    RegenerateFieldSchema,
    WhatsAppSendSchema,
)
from src.modules.m7_marketing.service import MarketingService
from src.modules.m7_marketing.languages import SUPPORTED_LANGUAGES, CHANNEL_SPECS

router = APIRouter()
service = MarketingService()


# ---------------------------------------------------------------------------
# Brand Kit
# ---------------------------------------------------------------------------


@router.get("/brand-kit", summary="Obter brand kit")
async def get_brand_kit() -> Dict[str, Any]:
    """Retorna brand kit do tenant default."""
    result = service.get_brand_kit()
    if not result:
        return {"message": "Brand kit nao configurado"}
    return result


@router.post("/brand-kit", summary="Criar/actualizar brand kit")
async def create_or_update_brand_kit(data: BrandKitSchema) -> Dict[str, Any]:
    """Cria ou actualiza brand kit."""
    try:
        return service.create_or_update_brand_kit(data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------


@router.post("/deals/{deal_id}/listing", summary="Criar listing")
async def create_listing(
    deal_id: str, data: ListingCreateSchema
) -> Dict[str, Any]:
    """Cria listing para um deal."""
    try:
        return service.create_listing(deal_id, data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/deals/{deal_id}/listing", summary="Obter listing de um deal")
async def get_deal_listing(deal_id: str) -> Dict[str, Any]:
    """Retorna listing associada a um deal."""
    result = service.get_listing_by_deal(deal_id)
    if not result:
        raise HTTPException(status_code=404, detail="Listing nao encontrada")
    return result


@router.get("/listings", summary="Listar listings")
async def list_listings(
    status: Optional[str] = None,
    listing_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Lista listings com filtros."""
    return service.list_listings(status, listing_type, limit, offset)


@router.get("/listings/{listing_id}", summary="Obter listing")
async def get_listing(listing_id: str) -> Dict[str, Any]:
    """Retorna listing completa."""
    result = service.get_listing(listing_id)
    if not result:
        raise HTTPException(status_code=404, detail="Listing nao encontrada")
    return result


@router.patch("/listings/{listing_id}", summary="Actualizar listing")
async def update_listing(
    listing_id: str, data: ListingUpdateSchema
) -> Dict[str, Any]:
    """Actualiza campos de uma listing."""
    try:
        result = service.update_listing(
            listing_id, data.model_dump(exclude_unset=True)
        )
        if not result:
            raise HTTPException(status_code=404, detail="Listing nao encontrada")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Conteudo IA
# ---------------------------------------------------------------------------


@router.post("/listings/{listing_id}/generate", summary="Gerar conteudo IA")
async def generate_content(
    listing_id: str, data: GenerateContentSchema
) -> Dict[str, Any]:
    """Gera conteudo multilingue com IA."""
    try:
        return service.generate_content(
            listing_id, data.languages, data.channels
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/listings/{listing_id}/regenerate", summary="Regenerar campo")
async def regenerate_field(
    listing_id: str, data: RegenerateFieldSchema
) -> Dict[str, Any]:
    """Regenera campo especifico com instrucoes opcionais."""
    try:
        return service.regenerate_field(
            listing_id, data.field, data.language, data.channel,
            data.instructions,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/listings/{listing_id}/approve", summary="Aprovar conteudo")
async def approve_content(listing_id: str) -> Dict[str, Any]:
    """Marca conteudo como aprovado."""
    try:
        return service.approve_content(listing_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Media (fotos do imóvel)
# ---------------------------------------------------------------------------


@router.post("/listings/{listing_id}/photos", summary="Upload fotos")
async def upload_listing_photos(
    listing_id: str,
    files: List[UploadFile] = File(...),
) -> Dict[str, Any]:
    """Upload de fotos para uma listing. Grava em Supabase Storage bucket
    `properties` e cria Document com file_path em formato bucket."""
    from uuid import uuid4
    from pathlib import Path as _Path
    from src.database import supabase_rest as db
    from src.database.db import get_session
    from src.database.models_v2 import Document
    from src.shared.storage_provider import BUCKET_PROPERTIES, upload_file

    listing = db.get_by_id("listings", listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing nao encontrada")

    tid = db.ensure_tenant()
    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }

    with get_session() as session:
        uploaded = []
        photos = list(listing.get("photos") or [])

        for i, file in enumerate(files):
            content = await file.read()
            ext = _Path(file.filename or "photo.jpg").suffix.lower() or ".jpg"
            mime = mime_map.get(ext, "application/octet-stream")

            doc_id = str(uuid4())
            bucket_path = f"tenants/{tid}/listings/{listing_id}/{doc_id}{ext}"
            upload_file(BUCKET_PROPERTIES, bucket_path, content, mime)

            doc = Document(
                id=doc_id,
                tenant_id=tid,
                deal_id=listing.get("deal_id"),
                entity_type="listing",
                entity_id=listing_id,
                filename=file.filename or f"photo_{i}{ext}",
                stored_filename=f"{doc_id}{ext}",
                file_path=f"{BUCKET_PROPERTIES}:{bucket_path}",
                file_size=len(content),
                mime_type=mime,
                file_extension=ext.lstrip("."),
                document_type="listing_photo",
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

    # Actualizar listing via REST
    patch: Dict[str, Any] = {"photos": photos}
    if not listing.get("cover_photo_url") and uploaded:
        patch["cover_photo_url"] = uploaded[0]["url"]
    db.update("listings", listing_id, patch)

    return {"uploaded": len(uploaded), "total_photos": len(photos), "photos": uploaded}


@router.post("/listings/{listing_id}/photos/set-cover", summary="Definir foto de capa")
async def set_cover_photo(
    listing_id: str,
    document_id: str = Query(...),
) -> Dict[str, Any]:
    """Define uma foto como capa da listing."""
    from src.database import supabase_rest as db

    listing = db.get_by_id("listings", listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing nao encontrada")

    photos = list(listing.get("photos") or [])
    for p in photos:
        p["is_cover"] = p.get("document_id") == document_id

    cover_url = f"/api/v1/documents/{document_id}/download"
    db.update("listings", listing_id, {
        "photos": photos,
        "cover_photo_url": cover_url,
    })

    return {"cover_photo_url": cover_url}


@router.get("/listings/{listing_id}/photos", summary="Listar fotos")
async def list_listing_photos(listing_id: str) -> List[Dict[str, Any]]:
    """Lista fotos de uma listing."""
    from src.database import supabase_rest as db

    listing = db.get_by_id("listings", listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing nao encontrada")
    return list(listing.get("photos") or [])


# ---------------------------------------------------------------------------
# Brand Kit logo upload
# ---------------------------------------------------------------------------


_MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB
_LOGO_MIMES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}
_LOGO_FIELDS = {
    "primary": "logo_primary_url",
    "white": "logo_white_url",
    "icon": "logo_icon_url",
}


@router.post("/brand-kit/logo", summary="Upload logo")
async def upload_brand_logo(
    file: UploadFile = File(...),
    logo_type: str = Query("primary", description="primary, white, icon"),
) -> Dict[str, Any]:
    """Upload de logo para o brand kit (bucket brand-assets, publico)."""
    from src.database import supabase_rest as db
    from src.shared.storage_provider import (
        BUCKET_BRAND_ASSETS,
        get_public_url,
        upload_file,
    )

    field = _LOGO_FIELDS.get(logo_type)
    if not field:
        raise HTTPException(
            status_code=400, detail=f"logo_type invalido: {logo_type}"
        )

    content_type = (file.content_type or "").lower()
    ext = _LOGO_MIMES.get(content_type)
    if not ext:
        raise HTTPException(
            status_code=400,
            detail=f"Formato nao suportado: {content_type}. Aceita: png, jpg, webp, svg",
        )

    content = await file.read()
    if len(content) > _MAX_LOGO_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Logo excede 2MB ({len(content) / 1024 / 1024:.2f}MB)",
        )

    tid = db.ensure_tenant()
    bk_rows = db._get("brand_kits", f"tenant_id=eq.{tid}&limit=1")
    if not bk_rows:
        raise HTTPException(status_code=400, detail="Brand kit nao configurado")
    bk = bk_rows[0]

    bucket_path = f"tenants/{tid}/logo_{logo_type}.{ext}"
    upload_file(BUCKET_BRAND_ASSETS, bucket_path, content, content_type)
    url = get_public_url(BUCKET_BRAND_ASSETS, bucket_path)

    db.update("brand_kits", bk["id"], {field: url})
    return {"logo_type": logo_type, "url": url}


@router.delete("/brand-kit/logo", summary="Remover logo")
async def delete_brand_logo(
    logo_type: str = Query(..., description="primary, white, icon"),
) -> Dict[str, Any]:
    """Remove logo do brand kit (apaga do bucket e limpa BrandKit.logo_*_url)."""
    from src.database import supabase_rest as db
    from src.shared.storage_provider import BUCKET_BRAND_ASSETS, delete_file

    field = _LOGO_FIELDS.get(logo_type)
    if not field:
        raise HTTPException(
            status_code=400, detail=f"logo_type invalido: {logo_type}"
        )

    tid = db.ensure_tenant()
    bk_rows = db._get("brand_kits", f"tenant_id=eq.{tid}&limit=1")
    if not bk_rows:
        raise HTTPException(status_code=400, detail="Brand kit nao configurado")
    bk = bk_rows[0]

    # Tenta apagar todas as extensoes conhecidas (o formato original pode variar)
    for ext in _LOGO_MIMES.values():
        delete_file(BUCKET_BRAND_ASSETS, f"tenants/{tid}/logo_{logo_type}.{ext}")

    db.update("brand_kits", bk["id"], {field: None})
    return {"logo_type": logo_type, "removed": True}


# ---------------------------------------------------------------------------
# Publicacao
# ---------------------------------------------------------------------------


@router.post(
    "/listings/{listing_id}/publish/habta", summary="Publicar no habta.eu"
)
async def publish_to_habta(listing_id: str) -> Dict[str, Any]:
    """Publica ou actualiza no habta.eu."""
    try:
        return service.publish_to_habta(listing_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/listings/{listing_id}/whatsapp/send", summary="Enviar por WhatsApp"
)
async def send_to_whatsapp(
    listing_id: str, data: WhatsAppSendSchema
) -> Dict[str, Any]:
    """Envia listing para grupos WhatsApp."""
    try:
        return service.send_to_whatsapp(
            listing_id, data.group_ids, data.language
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/listings/{listing_id}/publish-all", summary="Publicar em tudo"
)
async def publish_all(listing_id: str) -> Dict[str, Any]:
    """Publica em todos os canais disponiveis."""
    try:
        habta = service.publish_to_habta(listing_id)
        whatsapp = service.send_to_whatsapp(listing_id)
        return {"habta": habta, "whatsapp": whatsapp}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Preco
# ---------------------------------------------------------------------------


@router.post("/listings/{listing_id}/price", summary="Alterar preco")
async def change_price(
    listing_id: str, data: ChangePriceSchema
) -> Dict[str, Any]:
    """Altera preco e regista historico."""
    try:
        return service.change_price(
            listing_id, data.new_price, data.reason, data.changed_by
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/listings/{listing_id}/price-history", summary="Historico de precos"
)
async def get_price_history(listing_id: str) -> List[Dict[str, Any]]:
    """Retorna historico de alteracoes de preco."""
    return service.get_price_history(listing_id)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.post("/listings/{listing_id}/sold", summary="Marcar como vendido")
async def mark_as_sold(
    listing_id: str,
    sale_price: Optional[float] = Query(None),
) -> Dict[str, Any]:
    """Marca listing como vendida."""
    try:
        return service.mark_as_sold(listing_id, sale_price)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/listings/{listing_id}/rented", summary="Marcar como arrendado")
async def mark_as_rented(listing_id: str) -> Dict[str, Any]:
    """Marca listing como arrendada."""
    try:
        return service.mark_as_rented(listing_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Creatives (M7b)
# ---------------------------------------------------------------------------


@router.post(
    "/listings/{listing_id}/creatives/generate-all",
    summary="Gerar todas as pecas visuais",
)
async def generate_all_creatives(
    listing_id: str,
    language: str = Query("pt-PT"),
) -> List[Dict[str, Any]]:
    """Gera todas as pecas visuais de uma vez (Playwright + foto real)."""
    from src.modules.m7_marketing.creative_service import CreativeService
    svc = CreativeService()
    return svc.generate_all_creatives(listing_id, language)


@router.post(
    "/listings/{listing_id}/creatives/generate",
    summary="Gerar peca visual",
)
async def generate_creative(
    listing_id: str,
    creative_type: str = Query(...),
    language: str = Query("pt-PT"),
) -> Dict[str, Any]:
    """Gera uma peca visual especifica."""
    from src.modules.m7_marketing.creative_service import CreativeService
    svc = CreativeService()
    method_map = {
        "ig_post": svc.generate_ig_post,
        "ig_story": svc.generate_ig_story,
        "fb_post": svc.generate_fb_post,
        "property_card": svc.generate_property_card,
        "flyer": svc.generate_flyer_pdf,
    }
    gen_fn = method_map.get(creative_type)
    if not gen_fn:
        raise HTTPException(status_code=400, detail=f"Tipo invalido: {creative_type}")
    return gen_fn(listing_id, language)


@router.get(
    "/listings/{listing_id}/creatives", summary="Listar pecas visuais"
)
async def list_creatives(
    listing_id: str,
    creative_type: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """Lista pecas visuais de uma listing."""
    from src.modules.m7_marketing.creative_service import CreativeService
    svc = CreativeService()
    return svc.list_creatives(listing_id=listing_id, creative_type=creative_type)


@router.delete("/creatives/{creative_id}", summary="Remover peca visual")
async def delete_creative(creative_id: str) -> Dict[str, Any]:
    """Remove peca visual."""
    from src.modules.m7_marketing.creative_service import CreativeService
    svc = CreativeService()
    return {"success": svc.delete_creative(creative_id)}


# ---------------------------------------------------------------------------
# Email (M7h)
# ---------------------------------------------------------------------------


@router.post(
    "/listings/{listing_id}/email", summary="Gerar campanha email"
)
async def generate_email(
    listing_id: str,
    campaign_type: str = Query("new_property"),
    language: str = Query("pt-PT"),
) -> Dict[str, Any]:
    """Gera campanha de email para uma listing."""
    from src.modules.m7_marketing.email_service import EmailService
    es = EmailService()
    return es.generate_email(listing_id, campaign_type, language)


@router.post("/email/{campaign_id}/send", summary="Enviar campanha")
async def send_email_campaign(
    campaign_id: str,
    recipients: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Envia campanha de email via Resend.

    Body opcional: lista de emails destinatarios.
    """
    from src.modules.m7_marketing.email_service import EmailService
    es = EmailService()
    return await es.send_campaign(campaign_id, recipients)


@router.get("/listings/{listing_id}/emails", summary="Listar campanhas")
async def list_email_campaigns(
    listing_id: str,
) -> List[Dict[str, Any]]:
    """Lista campanhas de email de uma listing."""
    from src.modules.m7_marketing.email_service import EmailService
    es = EmailService()
    return es.list_campaigns(listing_id)


@router.get("/email/{campaign_id}", summary="Detalhe campanha")
async def get_email_campaign(campaign_id: str) -> Dict[str, Any]:
    """Retorna detalhe de uma campanha."""
    from src.modules.m7_marketing.email_service import EmailService
    es = EmailService()
    result = es.get_campaign(campaign_id)
    if not result:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada")
    return result


@router.get("/email/stats", summary="Estatisticas de email")
async def get_email_stats() -> Dict[str, Any]:
    """Retorna metricas de email marketing."""
    from src.modules.m7_marketing.email_service import EmailService
    return EmailService().get_email_stats()


# ---------------------------------------------------------------------------
# Print (M7j)
# ---------------------------------------------------------------------------


@router.post("/listings/{listing_id}/flyer", summary="Gerar flyer A4")
async def generate_flyer(
    listing_id: str, language: str = Query("pt-PT")
) -> Dict[str, Any]:
    """Gera flyer A4 em PDF."""
    from src.modules.m7_marketing.creative_studio import CreativeStudio
    return CreativeStudio().generate_creative(listing_id, "flyer_a4", language)


# ---------------------------------------------------------------------------
# Videos (M7c)
# ---------------------------------------------------------------------------


@router.post("/listings/{listing_id}/videos", summary="Criar video")
async def create_video(
    listing_id: str,
    video_type: str = Query(...),
    language: str = Query("pt-PT"),
) -> Dict[str, Any]:
    """Cria projecto de video."""
    from src.modules.m7_marketing.video_factory import VideoFactory
    try:
        return VideoFactory().create_video_project(listing_id, video_type, language)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/listings/{listing_id}/videos/generate-all", summary="Gerar todos os videos")
async def generate_all_videos(
    listing_id: str, language: str = Query("pt-PT")
) -> List[Dict[str, Any]]:
    """Gera todos os tipos de video."""
    from src.modules.m7_marketing.video_factory import VideoFactory
    return VideoFactory().generate_all_videos(listing_id, language)


@router.get("/listings/{listing_id}/videos", summary="Listar videos")
async def list_videos(listing_id: str) -> List[Dict[str, Any]]:
    """Lista videos de uma listing."""
    from src.modules.m7_marketing.video_factory import VideoFactory
    return VideoFactory().list_video_projects(listing_id)


@router.get("/videos/{video_id}", summary="Obter video")
async def get_video(video_id: str) -> Dict[str, Any]:
    """Retorna projecto de video."""
    from src.modules.m7_marketing.video_factory import VideoFactory
    result = VideoFactory().get_video_project(video_id)
    if not result:
        raise HTTPException(status_code=404, detail="Video nao encontrado")
    return result


@router.get("/videos/{video_id}/props", summary="Remotion props")
async def get_remotion_props(video_id: str) -> Dict[str, Any]:
    """Retorna props JSON para o Remotion."""
    from src.modules.m7_marketing.video_factory import VideoFactory
    try:
        return VideoFactory().prepare_remotion_props(video_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/videos/{video_id}/render", summary="Renderizar video")
async def render_video(video_id: str) -> Dict[str, Any]:
    """Dispara renderizacao (stub)."""
    from src.modules.m7_marketing.video_factory import VideoFactory
    try:
        return VideoFactory().render_video(video_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/videos/{video_id}", summary="Remover video")
async def delete_video(video_id: str) -> Dict[str, Any]:
    """Remove projecto de video."""
    from src.modules.m7_marketing.video_factory import VideoFactory
    return {"success": VideoFactory().delete_video_project(video_id)}


@router.get("/videos/templates", summary="Templates de video")
async def get_video_templates() -> Dict[str, Any]:
    """Lista templates de video disponiveis."""
    from src.modules.m7_marketing.video_factory import VIDEO_TEMPLATES
    return {k: {"label": v["label"], "width": v["width"], "height": v["height"],
                "orientation": v["orientation"], "duration_range": v["duration_range"]}
            for k, v in VIDEO_TEMPLATES.items()}


# ---------------------------------------------------------------------------
# Social Media (M7e)
# ---------------------------------------------------------------------------


@router.get("/social/accounts", summary="Listar contas")
async def list_social_accounts(
    platform: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """Lista contas de redes sociais."""
    from src.modules.m7_marketing.social_media import SocialMediaManager
    return SocialMediaManager().list_accounts(platform)


@router.post("/social/accounts", summary="Adicionar conta")
async def add_social_account(data: Dict[str, Any]) -> Dict[str, Any]:
    """Adiciona conta de rede social."""
    from src.modules.m7_marketing.social_media import SocialMediaManager
    try:
        return SocialMediaManager().add_account(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/social/accounts/{account_id}", summary="Remover conta")
async def remove_social_account(account_id: str) -> Dict[str, Any]:
    """Remove conta de rede social."""
    from src.modules.m7_marketing.social_media import SocialMediaManager
    return {"success": SocialMediaManager().remove_account(account_id)}


@router.post("/listings/{listing_id}/social", summary="Criar post")
async def create_social_post(
    listing_id: str,
    platform: str = Query(...),
    language: str = Query("pt-PT"),
) -> Dict[str, Any]:
    """Cria post de rede social."""
    from src.modules.m7_marketing.social_media import SocialMediaManager
    try:
        return SocialMediaManager().create_post(listing_id, platform, language)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/listings/{listing_id}/social/create-all", summary="Criar todos os posts")
async def create_all_social_posts(
    listing_id: str, language: str = Query("pt-PT")
) -> List[Dict[str, Any]]:
    """Cria posts para todas as plataformas."""
    from src.modules.m7_marketing.social_media import SocialMediaManager
    return SocialMediaManager().create_all_posts(listing_id, language)


@router.get("/listings/{listing_id}/social", summary="Listar posts")
async def list_social_posts(listing_id: str) -> List[Dict[str, Any]]:
    """Lista posts de uma listing."""
    from src.modules.m7_marketing.social_media import SocialMediaManager
    return SocialMediaManager().list_posts(listing_id)


@router.post("/social/posts/{post_id}/publish", summary="Publicar post")
async def publish_social_post(post_id: str) -> Dict[str, Any]:
    """Publica post (stub)."""
    from src.modules.m7_marketing.social_media import SocialMediaManager
    try:
        return SocialMediaManager().publish_post(post_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/social/posts/{post_id}/schedule", summary="Agendar post")
async def schedule_social_post(
    post_id: str, scheduled_at: str = Query(...)
) -> Dict[str, Any]:
    """Agenda post para publicacao futura."""
    from src.modules.m7_marketing.social_media import SocialMediaManager
    try:
        return SocialMediaManager().schedule_post(post_id, scheduled_at)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/social/calendar", summary="Calendario editorial")
async def get_content_calendar(
    days_ahead: int = Query(30, ge=1, le=90)
) -> Dict[str, Any]:
    """Retorna calendario editorial."""
    from src.modules.m7_marketing.social_media import SocialMediaManager
    return SocialMediaManager().get_content_calendar(days_ahead)


@router.get("/social/stats", summary="Estatisticas redes sociais")
async def get_social_stats() -> Dict[str, Any]:
    """Retorna metricas de redes sociais."""
    from src.modules.m7_marketing.social_media import SocialMediaManager
    return SocialMediaManager().get_social_stats()


# ---------------------------------------------------------------------------
# Stats e idiomas
# ---------------------------------------------------------------------------


@router.get("/stats", summary="Estatisticas de marketing")
async def get_stats() -> Dict[str, Any]:
    """Retorna metricas globais de marketing."""
    return service.get_marketing_stats()


@router.get("/languages", summary="Idiomas suportados")
async def get_languages() -> Dict[str, Any]:
    """Retorna idiomas suportados com labels e flags."""
    return {
        k: {"label": v["label"], "flag": v["flag"]}
        for k, v in SUPPORTED_LANGUAGES.items()
    }


@router.get("/channels", summary="Canais de publicacao")
async def get_channels() -> Dict[str, Any]:
    """Retorna canais com especificacoes."""
    return {k: {"label": v.get("label", k)} for k, v in CHANNEL_SPECS.items()}


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------


@router.get("/plugins/creative-engines", summary="Listar engines de criativos")
async def list_creative_engines() -> List[Dict[str, Any]]:
    """Retorna engines disponíveis para geração de criativos."""
    from src.modules.m7_marketing.plugins.registry import get_plugin_registry
    return get_plugin_registry().list_creative_engines()


@router.get("/plugins/video-engines", summary="Listar engines de vídeo")
async def list_video_engines() -> List[Dict[str, Any]]:
    """Retorna engines disponíveis para geração de vídeos."""
    from src.modules.m7_marketing.plugins.registry import get_plugin_registry
    return get_plugin_registry().list_video_engines()
