"""SocialMediaManager — M7 Phase 3.

Gere posts e contas de redes sociais para listings imobiliarios.
Suporta criacao, agendamento, publicacao (stub) e calendario de conteudo.

Plataformas: instagram_post, facebook_post, linkedin_post.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy import func, select

from src.database.db import get_session
from src.database.models_v2 import (
    Deal,
    Listing,
    ListingCreative,
    SocialMediaAccount,
    SocialMediaPost,
    Tenant,
    VideoProject,
)

# ---------------------------------------------------------------------------
# Helpers de serializacao
# ---------------------------------------------------------------------------


def _post_to_dict(p: SocialMediaPost) -> Dict[str, Any]:
    """Serializa SocialMediaPost para dict."""
    return {
        "id": p.id,
        "tenant_id": p.tenant_id,
        "listing_id": p.listing_id,
        "platform": p.platform,
        "caption": p.caption,
        "hashtags": p.hashtags,
        "link_url": p.link_url,
        "media_type": p.media_type,
        "media_urls": p.media_urls or [],
        "creative_id": p.creative_id,
        "video_project_id": p.video_project_id,
        "language": p.language,
        "status": p.status,
        "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else None,
        "published_at": p.published_at.isoformat() if p.published_at else None,
        "external_post_id": p.external_post_id,
        "external_url": p.external_url,
        "account_id": p.account_id,
        "account_name": p.account_name,
        "likes": p.likes,
        "comments": p.comments,
        "shares": p.shares,
        "views": p.views,
        "reach": p.reach,
        "clicks": p.clicks,
        "engagement_rate": p.engagement_rate,
        "error_message": p.error_message,
        "notes": p.notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _account_to_dict(a: SocialMediaAccount) -> Dict[str, Any]:
    """Serializa SocialMediaAccount para dict (sem tokens)."""
    return {
        "id": a.id,
        "tenant_id": a.tenant_id,
        "platform": a.platform,
        "account_name": a.account_name,
        "account_id": a.account_id,
        "account_type": a.account_type,
        "is_active": a.is_active,
        "token_expires_at": (
            a.token_expires_at.isoformat() if a.token_expires_at else None
        ),
        "last_used_at": a.last_used_at.isoformat() if a.last_used_at else None,
        "last_error": a.last_error,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


# ---------------------------------------------------------------------------
# SocialMediaManager
# ---------------------------------------------------------------------------


class SocialMediaManager:
    """Gestor de posts e contas de redes sociais para listings imobiliarios.

    Cria, agenda e publica posts nas plataformas configuradas.
    A publicacao efectiva requer integracao com as APIs de cada plataforma
    (stub por omissao — regista o post e simula a publicacao).

    Uso tipico
    ----------
    ::

        manager = SocialMediaManager()
        posts = manager.create_all_posts(listing_id)
        manager.schedule_post(posts[0]["id"], "2026-03-25T10:00:00")
    """

    # ------------------------------------------------------------------
    # Gestao de contas
    # ------------------------------------------------------------------

    def add_account(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Regista uma conta de rede social.

        Parametros
        ----------
        data:
            Dict com campos da conta: tenant_id, platform, account_name,
            account_id (opcional), account_type (opcional),
            access_token (opcional), refresh_token (opcional),
            token_expires_at (opcional, ISO string).

        Retorna
        -------
        Dict com metadados da conta criada.

        Raises
        ------
        ValueError
            Se tenant_id, platform ou account_name estiverem ausentes.
        """
        for field in ("tenant_id", "platform", "account_name"):
            if not data.get(field):
                raise ValueError(f"Campo obrigatorio em falta: '{field}'")

        token_expires_at: Optional[datetime] = None
        if data.get("token_expires_at"):
            token_expires_at = datetime.fromisoformat(data["token_expires_at"])

        with get_session() as session:
            account = SocialMediaAccount(
                id=str(uuid4()),
                tenant_id=data["tenant_id"],
                platform=data["platform"],
                account_name=data["account_name"],
                account_id=data.get("account_id"),
                account_type=data.get("account_type"),
                access_token=data.get("access_token"),
                refresh_token=data.get("refresh_token"),
                token_expires_at=token_expires_at,
                is_active=data.get("is_active", True),
            )
            session.add(account)
            session.flush()

            logger.info(
                f"SocialMediaManager: conta '{account.platform}' "
                f"adicionada (id={account.id})"
            )
            return _account_to_dict(account)

    def list_accounts(
        self,
        platform: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista contas de redes sociais configuradas.

        Parametros
        ----------
        platform:
            Filtrar por plataforma (opcional).

        Retorna
        -------
        Lista de dicts com metadados das contas.
        """
        with get_session() as session:
            stmt = select(SocialMediaAccount).where(
                SocialMediaAccount.is_active == True  # noqa: E712
            )
            if platform:
                stmt = stmt.where(SocialMediaAccount.platform == platform)
            stmt = stmt.order_by(SocialMediaAccount.created_at.desc())
            accounts = session.execute(stmt).scalars().all()
            return [_account_to_dict(a) for a in accounts]

    def remove_account(self, account_id: str) -> bool:
        """Remove uma conta de rede social (desactiva em vez de eliminar).

        Parametros
        ----------
        account_id:
            ID da SocialMediaAccount.

        Retorna
        -------
        True se desactivada, False se nao encontrada.
        """
        with get_session() as session:
            account = session.get(SocialMediaAccount, account_id)
            if not account:
                logger.warning(
                    f"SocialMediaManager.remove_account: id nao encontrado: {account_id}"
                )
                return False

            account.is_active = False
            session.flush()
            logger.info(
                f"SocialMediaManager: conta {account_id} desactivada"
            )
            return True

    # ------------------------------------------------------------------
    # Criacao de posts
    # ------------------------------------------------------------------

    def create_post(
        self,
        listing_id: str,
        platform: str,
        language: str = "pt-PT",
        media_type: str = "image",
        creative_id: Optional[str] = None,
        video_project_id: Optional[str] = None,
        custom_caption: Optional[str] = None,
        schedule_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cria um post de rede social para um listing.

        Parametros
        ----------
        listing_id:
            ID do listing de origem.
        platform:
            Plataforma de destino: 'instagram_post', 'facebook_post', 'linkedin_post'.
        language:
            Idioma do conteudo (ex: 'pt-PT', 'en').
        media_type:
            Tipo de media: 'image', 'video', 'carousel'.
        creative_id:
            ID de um ListingCreative especifico a usar (opcional).
        video_project_id:
            ID de um VideoProject especifico a usar (opcional).
        custom_caption:
            Legenda personalizada (sobrepoe o conteudo gerado automaticamente).
        schedule_at:
            Data/hora de agendamento em formato ISO (opcional).

        Retorna
        -------
        Dict com metadados do SocialMediaPost criado.

        Raises
        ------
        ValueError
            Se o listing nao existir.
        """
        with get_session() as session:
            listing = session.get(Listing, listing_id)
            if not listing:
                raise ValueError(f"Listing nao encontrado: {listing_id}")

            # --- Legenda ---
            caption: Optional[str] = custom_caption

            if not caption:
                caption_map = {
                    "instagram_post": listing.content_instagram_post,
                    "facebook_post": listing.content_facebook_post,
                    "linkedin_post": listing.content_linkedin,
                }
                caption = caption_map.get(platform)

            # Fallback: use whatsapp or description if no channel-specific content
            if not caption:
                caption = (
                    listing.content_whatsapp
                    or listing.short_description_pt
                    or listing.description_pt
                    or listing.title_pt
                )

            # --- Criativo a usar ---
            resolved_creative_id: Optional[str] = creative_id
            resolved_video_id: Optional[str] = video_project_id
            media_urls: List[str] = []

            if video_project_id:
                # Prioridade: video especificado
                pass
            elif creative_id:
                # Criativo especificado
                pass
            else:
                # Procurar criativo mais recente compativel com a plataforma
                platform_to_creative: Dict[str, str] = {
                    "instagram_post": "ig_post",
                    "facebook_post": "fb_post",
                    "linkedin_post": "property_card",
                }
                creative_type = platform_to_creative.get(platform)
                if creative_type:
                    creative = session.execute(
                        select(ListingCreative)
                        .where(
                            ListingCreative.listing_id == listing_id,
                            ListingCreative.creative_type == creative_type,
                        )
                        .order_by(ListingCreative.created_at.desc())
                    ).scalar_one_or_none()
                    if creative:
                        resolved_creative_id = creative.id
                        if creative.file_url:
                            media_urls = [creative.file_url]

            # Fotos do listing como fallback
            if not media_urls and listing.photos and isinstance(listing.photos, list):
                media_urls = listing.photos[:1]

            # --- Data de agendamento ---
            scheduled_at_dt: Optional[datetime] = None
            status = "draft"
            if schedule_at:
                scheduled_at_dt = datetime.fromisoformat(schedule_at)
                status = "scheduled"

            # --- Conta activa da plataforma ---
            # Mapeamento plataforma -> nome base da conta de rede social
            platform_base = platform.replace("_post", "").replace("_reel", "")
            account = session.execute(
                select(SocialMediaAccount)
                .where(
                    SocialMediaAccount.platform == platform_base,
                    SocialMediaAccount.tenant_id == listing.tenant_id,
                    SocialMediaAccount.is_active == True,  # noqa: E712
                )
                .order_by(SocialMediaAccount.last_used_at.desc())
            ).scalar_one_or_none()

            account_id_val: Optional[str] = None
            account_name_val: Optional[str] = None
            if account:
                account_id_val = account.account_id
                account_name_val = account.account_name

            # --- Link ---
            link_url: Optional[str] = None
            if hasattr(listing, "habta_url") and listing.habta_url:
                link_url = listing.habta_url

            post = SocialMediaPost(
                id=str(uuid4()),
                tenant_id=listing.tenant_id,
                listing_id=listing_id,
                platform=platform,
                caption=caption,
                link_url=link_url,
                media_type=media_type,
                media_urls=media_urls,
                creative_id=resolved_creative_id,
                video_project_id=resolved_video_id,
                language=language,
                status=status,
                scheduled_at=scheduled_at_dt,
                account_id=account_id_val,
                account_name=account_name_val,
            )
            session.add(post)
            session.flush()

            logger.info(
                f"SocialMediaManager: post '{platform}' criado para listing "
                f"{listing_id} (id={post.id}, status={status})"
            )
            return _post_to_dict(post)

    def create_all_posts(
        self,
        listing_id: str,
        language: str = "pt-PT",
    ) -> List[Dict[str, Any]]:
        """Cria posts para todas as plataformas principais.

        Plataformas: instagram_post, facebook_post, linkedin_post.

        Parametros
        ----------
        listing_id:
            ID do listing.
        language:
            Idioma do conteudo.

        Retorna
        -------
        Lista de dicts com metadados dos posts criados.
        """
        platforms = ["instagram_post", "facebook_post", "linkedin_post"]
        results: List[Dict[str, Any]] = []
        errors: List[str] = []

        for platform in platforms:
            try:
                result = self.create_post(
                    listing_id=listing_id,
                    platform=platform,
                    language=language,
                )
                results.append(result)
            except Exception as exc:
                logger.warning(
                    f"SocialMediaManager: erro ao criar post '{platform}' "
                    f"para listing {listing_id}: {exc}"
                )
                errors.append(f"{platform}: {exc}")

        if errors:
            logger.warning(
                f"SocialMediaManager: {len(errors)} erros em create_all_posts "
                f"para listing {listing_id}: {errors}"
            )

        logger.info(
            f"SocialMediaManager: {len(results)}/{len(platforms)} posts criados "
            f"para listing {listing_id}"
        )
        return results

    # ------------------------------------------------------------------
    # Publicacao e agendamento
    # ------------------------------------------------------------------

    def publish_post(self, post_id: str) -> Dict[str, Any]:
        """Publica um post numa rede social (stub).

        Em producao, este metodo devera chamar a API da plataforma
        e registar o external_post_id e external_url retornados.

        Parametros
        ----------
        post_id:
            ID do SocialMediaPost a publicar.

        Retorna
        -------
        Dict com metadados actualizados e resultado da publicacao.

        Raises
        ------
        ValueError
            Se o post nao existir.
        """
        with get_session() as session:
            post = session.get(SocialMediaPost, post_id)
            if not post:
                raise ValueError(f"Post nao encontrado: {post_id}")

            now = datetime.now(timezone.utc)
            post.status = "published"
            post.published_at = now
            session.flush()

            logger.info(
                f"SocialMediaManager.publish_post (stub): post {post_id} "
                f"marcado como publicado em '{post.platform}'"
            )
            return {
                **_post_to_dict(post),
                "publish_result": {
                    "status": "stub",
                    "message": "API nao configurada",
                },
            }

    def schedule_post(self, post_id: str, scheduled_at: str) -> Dict[str, Any]:
        """Agenda um post para publicacao numa data/hora especifica.

        Parametros
        ----------
        post_id:
            ID do SocialMediaPost a agendar.
        scheduled_at:
            Data/hora de publicacao em formato ISO (ex: '2026-03-25T10:00:00').

        Retorna
        -------
        Dict com metadados actualizados do post.

        Raises
        ------
        ValueError
            Se o post nao existir ou a data for invalida.
        """
        scheduled_dt = datetime.fromisoformat(scheduled_at)

        with get_session() as session:
            post = session.get(SocialMediaPost, post_id)
            if not post:
                raise ValueError(f"Post nao encontrado: {post_id}")

            post.status = "scheduled"
            post.scheduled_at = scheduled_dt
            session.flush()

            logger.info(
                f"SocialMediaManager: post {post_id} agendado para {scheduled_at}"
            )
            return _post_to_dict(post)

    # ------------------------------------------------------------------
    # Calendario e estatisticas
    # ------------------------------------------------------------------

    def get_content_calendar(self, days_ahead: int = 30) -> Dict[str, List[Dict[str, Any]]]:
        """Retorna o calendario de conteudo agrupado por data.

        Inclui posts agendados e publicados nas proximas ``days_ahead`` dias.

        Parametros
        ----------
        days_ahead:
            Numero de dias a incluir no calendario (a partir de hoje).

        Retorna
        -------
        Dict com chaves no formato 'YYYY-MM-DD' e valores listas de posts.
        """
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=days_ahead)

        with get_session() as session:
            stmt = (
                select(SocialMediaPost)
                .where(
                    SocialMediaPost.status.in_(["scheduled", "published"]),
                    SocialMediaPost.scheduled_at >= now,
                    SocialMediaPost.scheduled_at <= end_date,
                )
                .order_by(SocialMediaPost.scheduled_at)
            )
            posts = session.execute(stmt).scalars().all()

            calendar: Dict[str, List[Dict[str, Any]]] = {}
            for post in posts:
                if post.scheduled_at:
                    date_key = post.scheduled_at.strftime("%Y-%m-%d")
                    if date_key not in calendar:
                        calendar[date_key] = []
                    calendar[date_key].append(_post_to_dict(post))

            return calendar

    def get_social_stats(self) -> Dict[str, Any]:
        """Calcula estatisticas agregadas dos SocialMediaPosts.

        Retorna
        -------
        Dict com total_posts, by_platform, by_status e total_engagement.
        """
        with get_session() as session:
            # Total por plataforma
            by_platform_rows = session.execute(
                select(SocialMediaPost.platform, func.count(SocialMediaPost.id))
                .group_by(SocialMediaPost.platform)
            ).all()
            by_platform: Dict[str, int] = {row[0]: row[1] for row in by_platform_rows}

            # Total por estado
            by_status_rows = session.execute(
                select(SocialMediaPost.status, func.count(SocialMediaPost.id))
                .group_by(SocialMediaPost.status)
            ).all()
            by_status: Dict[str, int] = {row[0]: row[1] for row in by_status_rows}

            # Engagement total (likes + comments + shares)
            engagement_row = session.execute(
                select(
                    func.coalesce(func.sum(SocialMediaPost.likes), 0),
                    func.coalesce(func.sum(SocialMediaPost.comments), 0),
                    func.coalesce(func.sum(SocialMediaPost.shares), 0),
                )
            ).one()
            total_engagement = (
                int(engagement_row[0])
                + int(engagement_row[1])
                + int(engagement_row[2])
            )

            total_posts = sum(by_status.values())

            return {
                "total_posts": total_posts,
                "by_platform": by_platform,
                "by_status": by_status,
                "total_engagement": total_engagement,
            }

    # ------------------------------------------------------------------
    # Listagem
    # ------------------------------------------------------------------

    def list_posts(
        self,
        listing_id: Optional[str] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista SocialMediaPosts com filtros opcionais.

        Parametros
        ----------
        listing_id:
            Filtrar por listing (opcional).
        platform:
            Filtrar por plataforma (opcional).
        status:
            Filtrar por estado (opcional).

        Retorna
        -------
        Lista de dicts com metadados dos posts.
        """
        with get_session() as session:
            stmt = select(SocialMediaPost)
            if listing_id:
                stmt = stmt.where(SocialMediaPost.listing_id == listing_id)
            if platform:
                stmt = stmt.where(SocialMediaPost.platform == platform)
            if status:
                stmt = stmt.where(SocialMediaPost.status == status)
            stmt = stmt.order_by(SocialMediaPost.created_at.desc())
            posts = session.execute(stmt).scalars().all()
            return [_post_to_dict(p) for p in posts]
