"""VideoFactory — M7 Phase 3.

Gera projectos de video para listings imobiliarios com suporte a multiplos
formatos (landscape, portrait, square) e integracao com Remotion para
renderizacao programatica.

Suporta: property_showcase, instagram_reel, tiktok, before_after,
investor_pitch, slideshow.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy import func, select

from src.database.db import get_session
from src.database.models_v2 import (
    BrandKit,
    Deal,
    Listing,
    Property,
    Tenant,
    VideoProject,
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

VIDEO_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "property_showcase": {
        "label": "Showcase de Propriedade",
        "description": "Video panoramico completo da propriedade, ideal para portais e email",
        "width": 1920,
        "height": 1080,
        "orientation": "landscape",
        "duration_range": (30, 60),
        "fps": 30,
        "music_mood": "modern",
        "sections": [
            {
                "name": "intro",
                "duration": 5,
                "description": "Logo e nome da marca com animacao de entrada",
            },
            {
                "name": "exterior",
                "duration": 10,
                "description": "Fotos exteriores do imovel com efeito Ken Burns",
            },
            {
                "name": "interior",
                "duration": 20,
                "description": "Percurso pelos compartimentos principais",
            },
            {
                "name": "highlights",
                "duration": 10,
                "description": "Destaques e caracteristicas-chave com iconografia",
            },
            {
                "name": "cta",
                "duration": 5,
                "description": "Call to action com contactos e QR code",
            },
        ],
    },
    "instagram_reel": {
        "label": "Instagram Reel",
        "description": "Video vertical curto optimizado para Instagram Reels e Stories",
        "width": 1080,
        "height": 1920,
        "orientation": "portrait",
        "duration_range": (15, 30),
        "fps": 30,
        "music_mood": "upbeat",
        "sections": [
            {
                "name": "hook",
                "duration": 3,
                "description": "Gancho visual com preco e localizacao",
            },
            {
                "name": "photos",
                "duration": 20,
                "description": "Galeria rapida de fotos com transicoes dinamicas",
            },
            {
                "name": "cta",
                "duration": 5,
                "description": "CTA com link na bio e swipe up",
            },
        ],
    },
    "tiktok": {
        "label": "TikTok",
        "description": "Video vertical curto para TikTok com ritmo acelerado",
        "width": 1080,
        "height": 1920,
        "orientation": "portrait",
        "duration_range": (15, 30),
        "fps": 30,
        "music_mood": "upbeat",
        "sections": [
            {
                "name": "hook",
                "duration": 3,
                "description": "Gancho com texto em overlay e transicao rapida",
            },
            {
                "name": "tour",
                "duration": 20,
                "description": "Mini-tour rapido com cortes ao ritmo da musica",
            },
            {
                "name": "reveal",
                "duration": 5,
                "description": "Reveal do preco e contacto",
            },
        ],
    },
    "before_after": {
        "label": "Antes e Depois",
        "description": "Comparativo visual antes/apos renovacao, ideal para fix and flip",
        "width": 1080,
        "height": 1080,
        "orientation": "square",
        "duration_range": (15, 30),
        "fps": 30,
        "music_mood": "modern",
        "sections": [
            {
                "name": "before",
                "duration": 10,
                "description": "Estado original do imovel com legenda ANTES",
            },
            {
                "name": "transition",
                "duration": 3,
                "description": "Transicao com wipe ou split-screen",
            },
            {
                "name": "after",
                "duration": 12,
                "description": "Estado renovado com legenda DEPOIS",
            },
            {
                "name": "cta",
                "duration": 5,
                "description": "CTA com preco de venda e contactos",
            },
        ],
    },
    "investor_pitch": {
        "label": "Pitch para Investidores",
        "description": "Apresentacao profissional para investidores com metricas financeiras",
        "width": 1920,
        "height": 1080,
        "orientation": "landscape",
        "duration_range": (45, 90),
        "fps": 30,
        "music_mood": "corporate",
        "sections": [
            {
                "name": "intro",
                "duration": 10,
                "description": "Introducao com logotipo e visao geral do negocio",
            },
            {
                "name": "property",
                "duration": 20,
                "description": "Detalhes da propriedade e localizacao no mercado",
            },
            {
                "name": "financials",
                "duration": 25,
                "description": "Metricas financeiras: ROI, MAO, custos e projecoes",
            },
            {
                "name": "renovation",
                "duration": 20,
                "description": "Plano de renovacao e timeline",
            },
            {
                "name": "cta",
                "duration": 10,
                "description": "Proximo passo e contacto do gestor do deal",
            },
        ],
    },
    "slideshow": {
        "label": "Slideshow de Fotos",
        "description": "Slideshow simples com todas as fotos da propriedade",
        "width": 1920,
        "height": 1080,
        "orientation": "landscape",
        "duration_range": (30, 60),
        "fps": 30,
        "music_mood": "calm",
        "sections": [
            {
                "name": "cover",
                "duration": 5,
                "description": "Foto de capa com titulo e preco em overlay",
            },
            {
                "name": "gallery",
                "duration": 45,
                "description": "Galeria de todas as fotos com legenda de compartimento",
            },
            {
                "name": "map",
                "duration": 5,
                "description": "Localizacao no mapa e contactos",
            },
        ],
    },
}

MUSIC_LIBRARY: Dict[str, Dict[str, Any]] = {
    "modern": {
        "tracks": [
            {
                "name": "Urban Flow",
                "file": "music/modern/urban_flow.mp3",
                "duration": 120,
                "bpm": 110,
            },
            {
                "name": "City Lights",
                "file": "music/modern/city_lights.mp3",
                "duration": 90,
                "bpm": 105,
            },
        ],
    },
    "luxury": {
        "tracks": [
            {
                "name": "Grand Piano",
                "file": "music/luxury/grand_piano.mp3",
                "duration": 180,
                "bpm": 75,
            },
            {
                "name": "Elegant Strings",
                "file": "music/luxury/elegant_strings.mp3",
                "duration": 150,
                "bpm": 70,
            },
        ],
    },
    "upbeat": {
        "tracks": [
            {
                "name": "Summer Vibes",
                "file": "music/upbeat/summer_vibes.mp3",
                "duration": 60,
                "bpm": 128,
            },
            {
                "name": "Happy Days",
                "file": "music/upbeat/happy_days.mp3",
                "duration": 75,
                "bpm": 120,
            },
        ],
    },
    "calm": {
        "tracks": [
            {
                "name": "Peaceful Morning",
                "file": "music/calm/peaceful_morning.mp3",
                "duration": 180,
                "bpm": 80,
            },
            {
                "name": "Soft Breeze",
                "file": "music/calm/soft_breeze.mp3",
                "duration": 150,
                "bpm": 72,
            },
        ],
    },
    "corporate": {
        "tracks": [
            {
                "name": "Business Drive",
                "file": "music/corporate/business_drive.mp3",
                "duration": 120,
                "bpm": 95,
            },
            {
                "name": "Executive Suite",
                "file": "music/corporate/executive_suite.mp3",
                "duration": 130,
                "bpm": 90,
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Helpers de serializacao
# ---------------------------------------------------------------------------


def _video_to_dict(v: VideoProject) -> Dict[str, Any]:
    """Serializa VideoProject para dict."""
    return {
        "id": v.id,
        "tenant_id": v.tenant_id,
        "listing_id": v.listing_id,
        "video_type": v.video_type,
        "width": v.width,
        "height": v.height,
        "fps": v.fps,
        "duration_seconds": v.duration_seconds,
        "orientation": v.orientation,
        "language": v.language,
        "template_id": v.template_id,
        "template_props": v.template_props or {},
        "title_overlay": v.title_overlay,
        "photos_used": v.photos_used or [],
        "music_track": v.music_track,
        "music_mood": v.music_mood,
        "brand_name": v.brand_name,
        "logo_url": v.logo_url,
        "color_primary": v.color_primary,
        "color_accent": v.color_accent,
        "document_id": v.document_id,
        "file_url": v.file_url,
        "file_size": v.file_size,
        "format": v.format,
        "thumbnail_url": v.thumbnail_url,
        "status": v.status,
        "render_started_at": (
            v.render_started_at.isoformat() if v.render_started_at else None
        ),
        "render_completed_at": (
            v.render_completed_at.isoformat() if v.render_completed_at else None
        ),
        "render_duration_seconds": v.render_duration_seconds,
        "error_message": v.error_message,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }


# ---------------------------------------------------------------------------
# VideoFactory
# ---------------------------------------------------------------------------


class VideoFactory:
    """Fabrica de projectos de video para listings imobiliarios.

    Cria registos VideoProject na base de dados com os props necessarios
    para renderizacao via Remotion (ou outro motor de video programatico).
    A renderizacao efectiva e delegada ao motor externo (stub por omissao).

    Uso tipico
    ----------
    ::

        factory = VideoFactory()
        video = factory.create_video_project(listing_id, "instagram_reel")
        props = factory.prepare_remotion_props(video["id"])
        # Enviar props para Remotion e aguardar callback
    """

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def create_video_project(
        self,
        listing_id: str,
        video_type: str,
        language: str = "pt-PT",
    ) -> Dict[str, Any]:
        """Cria um projecto de video para um listing.

        Parametros
        ----------
        listing_id:
            ID do listing de origem.
        video_type:
            Tipo de video (ver VIDEO_TEMPLATES).
        language:
            Idioma do conteudo textual (ex: 'pt-PT', 'en').

        Retorna
        -------
        Dict com metadados do VideoProject criado.

        Raises
        ------
        ValueError
            Se o tipo de video for invalido ou o listing nao existir.
        """
        if video_type not in VIDEO_TEMPLATES:
            raise ValueError(
                f"Tipo de video invalido: '{video_type}'. "
                f"Opcoes: {list(VIDEO_TEMPLATES)}"
            )

        template = VIDEO_TEMPLATES[video_type]

        with get_session() as session:
            listing = session.get(Listing, listing_id)
            if not listing:
                raise ValueError(f"Listing nao encontrado: {listing_id}")

            deal: Optional[Deal] = None
            prop: Optional[Property] = None
            brand_kit: Optional[BrandKit] = None

            if listing.deal_id:
                deal = session.get(Deal, listing.deal_id)

            if deal and deal.property_id:
                prop = session.get(Property, deal.property_id)

            brand_kit = session.execute(
                select(BrandKit).where(BrandKit.tenant_id == listing.tenant_id)
            ).scalar_one_or_none()

            # --- Dados da marca ---
            brand_name = "ImoIA"
            color_primary = "#1E3A5F"
            color_accent = "#E76F51"
            logo_url: Optional[str] = None

            if brand_kit:
                brand_name = brand_kit.brand_name or brand_name
                color_primary = brand_kit.color_primary or color_primary
                color_accent = brand_kit.color_accent or color_accent
                website_url = brand_kit.website_url or ""
                contact_phone = brand_kit.contact_phone or ""
            else:
                website_url = ""
                contact_phone = ""

            # --- Titulo localizado ---
            lang_map = {
                "pt-PT": "pt",
                "pt": "pt",
                "en": "en",
                "fr": "fr",
                "pt-BR": "pt_br",
                "zh": "zh",
            }
            lang_key = lang_map.get(language, "pt")
            title = (
                getattr(listing, f"title_{lang_key}", None)
                or listing.title_pt
                or "Propriedade"
            )

            # --- Preco formatado ---
            currency = listing.currency or "EUR"
            price_value = listing.listing_price
            if currency == "EUR":
                price_formatted = f"{price_value:,.0f} €".replace(",", ".")
            elif currency == "BRL":
                price_formatted = f"R$ {price_value:,.0f}".replace(",", ".")
            else:
                price_formatted = f"{price_value:,.0f} {currency}"

            # --- Dados da property ---
            typology: Optional[str] = None
            area: Optional[str] = None
            bedrooms: Optional[int] = None
            bathrooms: Optional[int] = None
            location: Optional[str] = None

            if prop:
                typology = prop.typology or prop.property_type
                bedrooms = prop.bedrooms
                bathrooms = prop.bathrooms
                if prop.gross_area_m2:
                    area = f"{int(prop.gross_area_m2)} m²"
                elif prop.net_area_m2:
                    area = f"{int(prop.net_area_m2)} m²"
                loc_parts = [
                    p for p in [prop.parish, prop.municipality, prop.district] if p
                ]
                location = ", ".join(loc_parts[:2]) if loc_parts else None

            # --- Fotos ---
            photos: List[str] = []
            if listing.photos and isinstance(listing.photos, list):
                photos = listing.photos
            elif listing.cover_photo_url:
                photos = [listing.cover_photo_url]

            # --- Musica ---
            mood = template["music_mood"]
            music_tracks = MUSIC_LIBRARY.get(mood, {}).get("tracks", [])
            music_track = music_tracks[0]["name"] if music_tracks else None
            music_file = music_tracks[0]["file"] if music_tracks else None

            # --- CTA ---
            cta_url = website_url or f"https://imoia.pt/listing/{listing.id}"
            cta_text_map = {
                "pt-PT": "Saiba mais",
                "pt": "Saiba mais",
                "en": "Learn more",
                "fr": "En savoir plus",
                "pt-BR": "Saiba mais",
            }
            cta_text = cta_text_map.get(language, "Saiba mais")

            # --- Template props para Remotion ---
            template_props: Dict[str, Any] = {
                "title": title,
                "price": price_formatted,
                "typology": typology,
                "area": area,
                "bedrooms": bedrooms,
                "bathrooms": bathrooms,
                "location": location,
                "photos": photos,
                "brandName": brand_name,
                "colorPrimary": color_primary,
                "colorAccent": color_accent,
                "logoUrl": logo_url,
                "musicFile": music_file,
                "musicMood": mood,
                "language": language,
                "ctaText": cta_text,
                "ctaUrl": cta_url,
                "contactPhone": contact_phone,
                "sections": template["sections"],
            }

            # --- Duracao estimada (valor medio do intervalo) ---
            dur_min, dur_max = template["duration_range"]
            duration_seconds = (dur_min + dur_max) // 2

            video = VideoProject(
                id=str(uuid4()),
                tenant_id=listing.tenant_id,
                listing_id=listing_id,
                video_type=video_type,
                width=template["width"],
                height=template["height"],
                fps=template["fps"],
                duration_seconds=duration_seconds,
                orientation=template["orientation"],
                language=language,
                template_id=video_type,
                template_props=template_props,
                title_overlay=title,
                photos_used=photos,
                music_track=music_track,
                music_mood=mood,
                brand_name=brand_name,
                logo_url=logo_url,
                color_primary=color_primary,
                color_accent=color_accent,
                format="mp4",
                status="pending",
            )
            session.add(video)
            session.flush()

            logger.info(
                f"VideoFactory: projecto '{video_type}' criado para listing "
                f"{listing_id} (id={video.id})"
            )
            return _video_to_dict(video)

    def prepare_remotion_props(self, video_project_id: str) -> Dict[str, Any]:
        """Prepara as props para renderizacao com Remotion.

        Retorna o payload pronto a enviar ao servidor Remotion (Lambda ou local).

        Parametros
        ----------
        video_project_id:
            ID do VideoProject.

        Retorna
        -------
        Dict com ``compositionId`` e ``inputProps`` para o Remotion.

        Raises
        ------
        ValueError
            Se o projecto nao existir.
        """
        with get_session() as session:
            video = session.get(VideoProject, video_project_id)
            if not video:
                raise ValueError(
                    f"VideoProject nao encontrado: {video_project_id}"
                )
            return {
                "compositionId": video.template_id or video.video_type,
                "inputProps": video.template_props or {},
            }

    def render_video(self, video_project_id: str) -> Dict[str, Any]:
        """Renderiza o video (stub — integrar com Remotion em producao).

        Em producao, este metodo devera chamar a API Remotion Lambda
        e aguardar o callback de conclusao. Por agora define o estado
        como concluido com um URL de placeholder.

        Parametros
        ----------
        video_project_id:
            ID do VideoProject a renderizar.

        Retorna
        -------
        Dict actualizado do VideoProject.

        Raises
        ------
        ValueError
            Se o projecto nao existir.
        """
        with get_session() as session:
            video = session.get(VideoProject, video_project_id)
            if not video:
                raise ValueError(
                    f"VideoProject nao encontrado: {video_project_id}"
                )

            now = datetime.now(timezone.utc)
            video.status = "completed"
            video.render_completed_at = now
            video.file_url = "stub://placeholder.mp4"
            session.flush()

            logger.info(
                f"VideoFactory.render_video (stub): projecto {video_project_id} "
                "marcado como concluido"
            )
            return _video_to_dict(video)

    def generate_all_videos(
        self,
        listing_id: str,
        language: str = "pt-PT",
    ) -> List[Dict[str, Any]]:
        """Gera os videos principais para um listing.

        Tipos gerados: property_showcase, instagram_reel, before_after.

        Parametros
        ----------
        listing_id:
            ID do listing.
        language:
            Idioma do conteudo.

        Retorna
        -------
        Lista de dicts com metadados dos VideoProjects criados.
        """
        types = ["property_showcase", "instagram_reel", "before_after"]
        results: List[Dict[str, Any]] = []
        errors: List[str] = []

        for vtype in types:
            try:
                result = self.create_video_project(listing_id, vtype, language=language)
                results.append(result)
            except Exception as exc:
                logger.warning(
                    f"VideoFactory: erro ao criar '{vtype}' "
                    f"para listing {listing_id}: {exc}"
                )
                errors.append(f"{vtype}: {exc}")

        if errors:
            logger.warning(
                f"VideoFactory: {len(errors)} erros em generate_all_videos "
                f"para listing {listing_id}: {errors}"
            )

        logger.info(
            f"VideoFactory: {len(results)}/{len(types)} videos criados "
            f"para listing {listing_id}"
        )
        return results

    def get_video_project(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Obtem um VideoProject pelo id.

        Parametros
        ----------
        video_id:
            ID do VideoProject.

        Retorna
        -------
        Dict com metadados ou None se nao encontrado.
        """
        with get_session() as session:
            video = session.get(VideoProject, video_id)
            if not video:
                return None
            return _video_to_dict(video)

    def list_video_projects(
        self,
        listing_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista VideoProjects com filtros opcionais.

        Parametros
        ----------
        listing_id:
            Filtrar por listing (opcional).
        status:
            Filtrar por estado (ex: 'pending', 'completed') (opcional).

        Retorna
        -------
        Lista de dicts com metadados.
        """
        with get_session() as session:
            stmt = select(VideoProject)
            if listing_id:
                stmt = stmt.where(VideoProject.listing_id == listing_id)
            if status:
                stmt = stmt.where(VideoProject.status == status)
            stmt = stmt.order_by(VideoProject.created_at.desc())
            videos = session.execute(stmt).scalars().all()
            return [_video_to_dict(v) for v in videos]

    def delete_video_project(self, video_id: str) -> bool:
        """Elimina um VideoProject.

        Parametros
        ----------
        video_id:
            ID do VideoProject a eliminar.

        Retorna
        -------
        True se eliminado, False se nao encontrado.
        """
        with get_session() as session:
            video = session.get(VideoProject, video_id)
            if not video:
                logger.warning(
                    f"VideoFactory.delete_video_project: id nao encontrado: {video_id}"
                )
                return False

            session.delete(video)
            logger.info(f"VideoFactory: projecto de video {video_id} eliminado")
            return True

    def get_video_stats(self) -> Dict[str, Any]:
        """Calcula estatisticas agregadas dos VideoProjects.

        Retorna
        -------
        Dict com total_count, by_type e by_status.
        """
        with get_session() as session:
            # Total por tipo
            by_type_rows = session.execute(
                select(VideoProject.video_type, func.count(VideoProject.id))
                .group_by(VideoProject.video_type)
            ).all()
            by_type: Dict[str, int] = {row[0]: row[1] for row in by_type_rows}

            # Total por estado
            by_status_rows = session.execute(
                select(VideoProject.status, func.count(VideoProject.id))
                .group_by(VideoProject.status)
            ).all()
            by_status: Dict[str, int] = {row[0]: row[1] for row in by_status_rows}

            total_count = sum(by_status.values())

            return {
                "total_count": total_count,
                "by_type": by_type,
                "by_status": by_status,
            }
