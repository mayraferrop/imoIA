"""M7 — Gerador de conteudo de marketing com IA (Claude).

Gera textos multilingues e multi-canal a partir dos dados do deal/property
e do brand kit do tenant, usando a API Anthropic.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy import select

from src.config import get_settings
from src.database.db import get_session
from src.database.models_v2 import (
    BrandKit,
    Deal,
    Listing,
    ListingContent,
    Property,
    Tenant,
)
from src.modules.m7_marketing.languages import CHANNEL_SPECS, SUPPORTED_LANGUAGES

_DEFAULT_TENANT_SLUG = "default"


class ContentGenerator:
    """Gerador de conteudo de marketing com IA.

    Usa o Claude (Anthropic) para gerar textos multilingues e multi-canal
    a partir dos dados do deal/property e do brand kit do tenant.
    """

    # --- Metodo principal ---

    def generate_all_content(
        self,
        listing_id: str,
        languages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Gera conteudo de marketing para todos os idiomas solicitados.

        Para cada idioma: constroi o prompt com dados do deal/property/brand_kit,
        chama a API Claude, guarda o resultado nos campos do Listing e cria
        registos ListingContent para rastreabilidade.

        Parametros
        ----------
        listing_id:
            ID do Listing para o qual gerar conteudo.
        languages:
            Lista de codigos de idioma (ex: ['pt-PT', 'en']). Se None, usa
            os idiomas activos do brand kit ou ['pt-PT'] como fallback.

        Retorna
        -------
        Dict com conteudo gerado por idioma.
        """
        settings = get_settings()

        with get_session() as session:
            listing = session.get(Listing, listing_id)
            if not listing:
                raise ValueError(f"Listing nao encontrado: {listing_id}")

            deal = session.get(Deal, listing.deal_id) if listing.deal_id else None
            prop = (
                session.get(Property, deal.property_id)
                if deal
                else None
            )

            # Obter brand kit
            brand_kit = self._get_brand_kit(session, listing.tenant_id)

            # Determinar idiomas a gerar
            active_languages = languages or (
                brand_kit.get("active_languages") if brand_kit else None
            ) or ["pt-PT"]

            # Filtrar apenas idiomas suportados
            active_languages = [
                lang for lang in active_languages if lang in SUPPORTED_LANGUAGES
            ]
            if not active_languages:
                active_languages = ["pt-PT"]

            results: Dict[str, Any] = {}

            for lang_key in active_languages:
                logger.info(
                    f"A gerar conteudo para listing {listing_id}, idioma: {lang_key}"
                )

                try:
                    prompt = self._build_prompt(
                        deal=deal,
                        prop=prop,
                        listing=listing,
                        brand_kit=brand_kit,
                        language_key=lang_key,
                        channel_specs=CHANNEL_SPECS,
                    )

                    # Chamar API Claude
                    content_json = self._call_claude_api(prompt, settings)

                    # Guardar nos campos do Listing
                    self._apply_content_to_listing(session, listing, lang_key, content_json)

                    # Criar registos ListingContent por canal
                    version = self._get_next_version(session, listing_id, lang_key)
                    self._save_listing_content_records(
                        session, listing_id, lang_key, content_json, version, settings
                    )

                    results[lang_key] = content_json
                    logger.info(
                        f"Conteudo gerado com sucesso: listing {listing_id}, "
                        f"idioma {lang_key}"
                    )

                except Exception as exc:
                    logger.error(
                        f"Erro ao gerar conteudo para {lang_key} "
                        f"(listing {listing_id}): {exc}"
                    )
                    # Conteudo placeholder para nao bloquear o fluxo
                    results[lang_key] = self._placeholder_content(
                        listing, lang_key
                    )

            session.flush()
            logger.info(
                f"Geracao de conteudo concluida: listing {listing_id}, "
                f"{len(results)} idioma(s)"
            )
            return results

    # --- Construcao do prompt ---

    def _build_prompt(
        self,
        deal: Optional[Deal],
        prop: Optional[Property],
        listing: Listing,
        brand_kit: Optional[Dict[str, Any]],
        language_key: str,
        channel_specs: Dict[str, Any],
    ) -> str:
        """Constroi o prompt completo para a API Claude.

        Inclui contexto da marca, dados da propriedade, instrucoes de idioma
        e especificacoes de cada canal.

        Parametros
        ----------
        deal:
            Deal associado ao listing (pode ser None).
        prop:
            Property associada ao deal (pode ser None).
        listing:
            Listing para o qual gerar conteudo.
        brand_kit:
            Dados do brand kit do tenant.
        language_key:
            Codigo do idioma (ex: 'pt-PT').
        channel_specs:
            Especificacoes de cada canal de marketing.

        Retorna
        -------
        String com o prompt completo.
        """
        lang_info = SUPPORTED_LANGUAGES.get(language_key, SUPPORTED_LANGUAGES["pt-PT"])

        # --- Contexto da marca ---
        brand_section = ""
        if brand_kit:
            brand_section = f"""
## MARCA
- Nome: {brand_kit.get('brand_name', 'ImoIA')}
- Tagline: {brand_kit.get('tagline', '')}
- Tom de voz: {brand_kit.get('voice_tone', 'profissional')}
- Descricao do tom: {brand_kit.get('voice_description', '')}
- Palavras preferidas: {', '.join(brand_kit.get('voice_preferred_words') or [])}
- Palavras a evitar: {', '.join(brand_kit.get('voice_forbidden_words') or [])}
- Website: {brand_kit.get('website_url', '')}
- Contacto: {brand_kit.get('contact_phone', '')} | {brand_kit.get('contact_email', '')}
- WhatsApp: {brand_kit.get('contact_whatsapp', '')}
- Instagram: {brand_kit.get('social_instagram', '')}
"""
        else:
            brand_section = "\n## MARCA\n- Nome: ImoIA\n- Tom: profissional\n"

        # --- Dados da propriedade ---
        prop_section = "\n## IMOVEL\n"
        if prop:
            prop_section += f"""- Tipo: {prop.property_type or 'Apartamento'}
- Tipologia: {prop.typology or ''}
- Localizacao: {', '.join(filter(None, [prop.address, prop.parish, prop.municipality, prop.district, prop.country]))}
- Area bruta: {prop.gross_area_m2 or ''} m\u00b2
- Area util: {prop.net_area_m2 or ''} m\u00b2
- Quartos: {prop.bedrooms or ''}
- Casas-de-banho: {prop.bathrooms or ''}
- Piso: {prop.floor or ''}
- Elevador: {'Sim' if prop.has_elevator else 'Nao' if prop.has_elevator is not None else 'N/D'}
- Estacionamento: {'Sim' if prop.has_parking else 'Nao' if prop.has_parking is not None else 'N/D'}
- Ano de construcao: {prop.construction_year or ''}
- Certificado energetico: {prop.energy_certificate or ''}
- Estado: {prop.condition or ''}
- Notas adicionais: {prop.notes or ''}
"""
        else:
            prop_section += "- Dados da propriedade nao disponiveis\n"

        # --- Dados do deal ---
        deal_section = "\n## NEGOCIO\n"
        if deal:
            deal_section += f"""- Preco de listagem: {listing.listing_price} {listing.currency}
- Tipo de listagem: {listing.listing_type}
- Preco negociavel: {'Sim' if listing.price_negotiable else 'Nao'}
- Preco a pedido: {'Sim' if listing.price_on_request else 'Nao'}
- Preco piso: {listing.floor_price or 'N/D'} {listing.currency}
- Estrategia de investimento: {deal.investment_strategy or ''}
- Notas do deal: {deal.notes or ''}
"""
            if deal.target_sale_price:
                deal_section += f"- Preco alvo de venda: {deal.target_sale_price} EUR\n"
            if deal.monthly_rent:
                deal_section += f"- Renda mensal: {deal.monthly_rent} EUR\n"
        else:
            deal_section += f"- Preco de listagem: {listing.listing_price} {listing.currency}\n"
            deal_section += f"- Tipo: {listing.listing_type}\n"

        # --- Destaques existentes ---
        highlights_section = ""
        if listing.highlights:
            highlights_section = (
                "\n## DESTAQUES JA IDENTIFICADOS\n"
                + "\n".join(f"- {h}" for h in listing.highlights)
                + "\n"
            )

        # --- Instrucoes de idioma ---
        lang_instruction = lang_info.get("claude_instruction") or lang_info.get("instruction", "")
        lang_section = f"""
## IDIOMA E TOM
{lang_instruction}
"""

        # --- Instrucoes por canal ---
        channels_section = "\n## CONTEUDO A GERAR\n"
        channels_section += (
            "Gera conteudo para os seguintes canais. "
            "Responde APENAS com um objecto JSON valido, sem texto adicional, "
            "com a estrutura exacta indicada abaixo:\n\n"
        )
        channels_section += """```json
{
  "portal": {
    "title": "titulo do anuncio (max 120 caracteres)",
    "description": "descricao completa",
    "short_description": "resumo curto (max 160 caracteres)",
    "highlights": ["destaque 1", "destaque 2", "destaque 3"],
    "meta_title": "titulo SEO (max 60 caracteres)",
    "meta_description": "descricao SEO (max 160 caracteres)",
    "keywords": ["palavra-chave 1", "palavra-chave 2"]
  },
  "whatsapp": {
    "message": "mensagem formatada para whatsapp com *negrito* e emojis"
  },
  "instagram": {
    "caption": "legenda para instagram",
    "hashtags": ["#hashtag1", "#hashtag2"]
  },
  "facebook": {
    "post": "texto do post para facebook"
  },
  "linkedin": {
    "post": "texto do post para linkedin"
  },
  "email": {
    "subject": "assunto do email (max 60 caracteres)",
    "body": "corpo do email completo"
  }
}
```

"""
        # Adicionar instrucoes especificas de cada canal
        for channel_key, channel_info in channel_specs.items():
            channels_section += (
                f"### {channel_info.get('label') or channel_info.get('name', channel_key)}\n"
                f"{channel_info.get('instruction') or channel_info.get('instructions', '')}\n\n"
            )

        prompt = (
            "Actua como especialista em marketing imobiliario. "
            "Gera conteudo de marketing profissional e apelativo para o seguinte imovel.\n\n"
            + brand_section
            + prop_section
            + deal_section
            + highlights_section
            + lang_section
            + channels_section
            + "Responde APENAS com o JSON. Sem comentarios, sem markdown extra fora do JSON."
        )

        return prompt

    # --- Chamada API Claude ---

    def _call_claude_api(
        self, prompt: str, settings: Any
    ) -> Dict[str, Any]:
        """Chama a API Anthropic Claude e retorna o conteudo gerado como dict.

        Se a API nao estiver configurada, retorna conteudo placeholder.
        """
        if not settings.anthropic_api_key:
            logger.warning("ANTHROPIC_API_KEY nao configurada — conteudo placeholder")
            return {}

        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=settings.anthropic_api_key)
            response = client.messages.create(
                model=settings.ai_model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            raw_text = response.content[0].text.strip()

            # Remover possivel markdown code block
            if raw_text.startswith("```"):
                lines = raw_text.splitlines()
                raw_text = "\n".join(
                    line for line in lines
                    if not line.startswith("```")
                )

            content = json.loads(raw_text)
            logger.debug(
                f"Claude gerou conteudo: "
                f"{response.usage.input_tokens} input tokens, "
                f"{response.usage.output_tokens} output tokens"
            )
            return content

        except json.JSONDecodeError as exc:
            logger.error(f"Erro ao parsear JSON da resposta Claude: {exc}")
            return {}
        except Exception as exc:
            logger.error(f"Erro na chamada API Claude: {exc}")
            return {}

    # --- Aplicar conteudo ao Listing ---

    def _apply_content_to_listing(
        self,
        session: Any,
        listing: Listing,
        language_key: str,
        content: Dict[str, Any],
    ) -> None:
        """Aplica o conteudo gerado aos campos do Listing conforme o idioma."""
        lang_info = SUPPORTED_LANGUAGES.get(language_key, {})
        suffix = lang_info.get("field_suffix", "pt")

        portal = content.get("portal", {})
        whatsapp = content.get("whatsapp", {})
        instagram = content.get("instagram", {})
        facebook = content.get("facebook", {})
        linkedin = content.get("linkedin", {})
        email = content.get("email", {})

        # Campos de conteudo por idioma
        if portal.get("title"):
            setattr(listing, f"title_{suffix}", portal["title"])
        if portal.get("description"):
            setattr(listing, f"description_{suffix}", portal["description"])
        if portal.get("short_description") and suffix in ("pt", "en"):
            setattr(listing, f"short_description_{suffix}", portal["short_description"])

        # Campos globais (apenas PT-PT como idioma primario)
        if language_key == "pt-PT":
            if portal.get("highlights"):
                listing.highlights = portal["highlights"]
            if portal.get("meta_title"):
                listing.meta_title = portal["meta_title"]
            if portal.get("meta_description"):
                listing.meta_description = portal["meta_description"]
            if portal.get("keywords"):
                listing.keywords = portal["keywords"]
            if whatsapp.get("message"):
                listing.content_whatsapp = whatsapp["message"]
            if instagram.get("caption"):
                caption = instagram["caption"]
                hashtags = instagram.get("hashtags", [])
                if hashtags:
                    caption += "\n\n" + " ".join(hashtags)
                listing.content_instagram_post = caption
            if facebook.get("post"):
                listing.content_facebook_post = facebook["post"]
            if linkedin.get("post"):
                listing.content_linkedin = linkedin["post"]
            if email.get("subject"):
                listing.content_email_subject = email["subject"]
            if email.get("body"):
                listing.content_email_body = email["body"]

            # Conteudo de portal em PT
            if portal.get("description"):
                listing.content_portal = portal["description"]

    # --- Guardar registos ListingContent ---

    def _save_listing_content_records(
        self,
        session: Any,
        listing_id: str,
        language_key: str,
        content: Dict[str, Any],
        version: int,
        settings: Any,
    ) -> None:
        """Cria registos ListingContent para cada canal gerado."""
        channel_map = {
            "portal": ("portal", "description"),
            "whatsapp": ("whatsapp", "message"),
            "instagram": ("instagram", "caption"),
            "facebook": ("facebook", "post"),
            "linkedin": ("linkedin", "post"),
            "email_subject": ("email", "subject"),
            "email_body": ("email", "body"),
        }

        for content_type, (channel_key, field) in channel_map.items():
            channel_data = content.get(channel_key, {})
            text = channel_data.get(field)
            if not text:
                continue

            # Para email, concatena subject + body em "email"
            if content_type == "email_body":
                subject = content.get("email", {}).get("subject", "")
                text = f"Assunto: {subject}\n\n{text}" if subject else text

            record = ListingContent(
                id=str(uuid4()),
                listing_id=listing_id,
                version=version,
                language=language_key,
                channel=channel_key,
                content_type=content_type,
                content=text,
                is_active=True,
                model_used=settings.ai_model if settings.anthropic_api_key else "placeholder",
            )
            session.add(record)

    # --- Helpers ---

    def _get_brand_kit(
        self, session: Any, tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """Obtem o brand kit do tenant como dict."""
        from src.database.models_v2 import BrandKit

        bk = session.execute(
            select(BrandKit).where(BrandKit.tenant_id == tenant_id)
        ).scalar_one_or_none()

        if not bk:
            return None

        return {
            "brand_name": bk.brand_name,
            "tagline": bk.tagline,
            "website_url": bk.website_url,
            "voice_tone": bk.voice_tone,
            "voice_description": bk.voice_description,
            "voice_forbidden_words": bk.voice_forbidden_words or [],
            "voice_preferred_words": bk.voice_preferred_words or [],
            "contact_phone": bk.contact_phone,
            "contact_email": bk.contact_email,
            "contact_whatsapp": bk.contact_whatsapp,
            "social_instagram": bk.social_instagram,
            "social_facebook": bk.social_facebook,
            "social_linkedin": bk.social_linkedin,
            "active_languages": bk.active_languages or ["pt-PT"],
        }

    def _get_next_version(
        self, session: Any, listing_id: str, language_key: str
    ) -> int:
        """Calcula o proximo numero de versao para um listing/idioma."""
        from sqlalchemy import func

        max_version = session.execute(
            select(func.max(ListingContent.version)).where(
                ListingContent.listing_id == listing_id,
                ListingContent.language == language_key,
            )
        ).scalar()

        return (max_version or 0) + 1

    def _placeholder_content(
        self, listing: Listing, language_key: str
    ) -> Dict[str, Any]:
        """Retorna conteudo placeholder quando a API nao esta disponivel."""
        price_str = f"{listing.listing_price:,.0f} {listing.currency}"
        return {
            "portal": {
                "title": f"[PLACEHOLDER] {listing.listing_type.capitalize()} — {price_str}",
                "description": "[Conteudo a gerar — API nao configurada]",
                "short_description": f"{listing.listing_type.capitalize()} por {price_str}",
                "highlights": [],
                "meta_title": "",
                "meta_description": "",
                "keywords": [],
            },
            "whatsapp": {
                "message": f"[PLACEHOLDER] {listing.listing_type.capitalize()} — {price_str}"
            },
            "instagram": {"caption": "", "hashtags": []},
            "facebook": {"post": ""},
            "linkedin": {"post": ""},
            "email": {"subject": "", "body": ""},
        }

    # --- Metodos especializados ---

    def generate_whatsapp_message(
        self, listing_id: str, language: str = "pt-PT"
    ) -> str:
        """Gera mensagem formatada para WhatsApp com negrito, emoji, preco, link e contacto.

        Parametros
        ----------
        listing_id:
            ID do Listing.
        language:
            Codigo do idioma (default: 'pt-PT').

        Retorna
        -------
        Mensagem formatada para WhatsApp.
        """
        settings = get_settings()

        with get_session() as session:
            listing = session.get(Listing, listing_id)
            if not listing:
                raise ValueError(f"Listing nao encontrado: {listing_id}")

            deal = session.get(Deal, listing.deal_id) if listing.deal_id else None
            prop = (
                session.get(Property, deal.property_id)
                if deal
                else None
            )
            brand_kit = self._get_brand_kit(session, listing.tenant_id)

            # Construir prompt especifico para WhatsApp
            prompt = self._build_whatsapp_prompt(listing, deal, prop, brand_kit, language)
            content = self._call_claude_api(prompt, settings)

            message = content.get("whatsapp", {}).get("message", "")

            if not message:
                # Fallback manual
                price_str = f"{listing.listing_price:,.0f} {listing.currency}"
                location = ""
                if prop:
                    location = ", ".join(
                        filter(None, [prop.parish, prop.municipality, prop.district])
                    )
                area = f"{prop.gross_area_m2:.0f}m\u00b2" if prop and prop.gross_area_m2 else ""
                contact = ""
                if brand_kit:
                    contact = brand_kit.get("contact_whatsapp") or brand_kit.get("contact_phone") or ""

                parts = [
                    f"\U0001f3e0 *{listing.listing_type.capitalize()}*",
                    f"\U0001f4cd {location}" if location else "",
                    f"\U0001f4cf {area}" if area else "",
                    f"\U0001f4b6 *{price_str}*",
                    f"\U0001f4de {contact}" if contact else "",
                ]
                message = "\n".join(p for p in parts if p)

            # Guardar no listing
            listing.content_whatsapp = message
            session.flush()

            return message

    def _build_whatsapp_prompt(
        self,
        listing: Listing,
        deal: Optional[Deal],
        prop: Optional[Property],
        brand_kit: Optional[Dict[str, Any]],
        language_key: str,
    ) -> str:
        """Constroi prompt especifico para mensagem WhatsApp."""
        lang_info = SUPPORTED_LANGUAGES.get(language_key, SUPPORTED_LANGUAGES["pt-PT"])
        price_str = f"{listing.listing_price:,.0f} {listing.currency}"
        location = ""
        if prop:
            location = ", ".join(
                filter(None, [prop.parish, prop.municipality, prop.district])
            )
        area = f"{prop.gross_area_m2:.0f}m\u00b2" if prop and prop.gross_area_m2 else ""
        contact = ""
        link = ""
        if brand_kit:
            contact = brand_kit.get("contact_whatsapp") or brand_kit.get("contact_phone") or ""
            link = brand_kit.get("website_url") or ""

        return (
            f"Gera uma mensagem de WhatsApp para partilha em grupos imobiliarios.\n\n"
            f"Imovel: {listing.listing_type} em {location}\n"
            f"Area: {area}\n"
            f"Preco: {price_str}\n"
            f"Quartos: {prop.bedrooms if prop else ''}\n"
            f"Estado: {prop.condition if prop else ''}\n"
            f"Contacto: {contact}\n"
            f"Link: {link}\n\n"
            f"Instrucoes de idioma: {lang_info.get('claude_instruction') or lang_info.get('instruction', '')}\n\n"
            f"Regras:\n"
            f"- Usa *negrito* para dados-chave\n"
            f"- Inclui emojis relevantes\n"
            f"- Max 600 caracteres\n"
            f"- Termina com link e contacto\n\n"
            f"Responde APENAS com JSON: "
            + '{"whatsapp": {"message": "..."}}'
        )

    def regenerate_field(
        self,
        listing_id: str,
        field: str,
        language: str,
        instructions: Optional[str] = None,
    ) -> str:
        """Regenera um campo especifico de um listing com instrucoes personalizadas.

        Parametros
        ----------
        listing_id:
            ID do Listing.
        field:
            Nome do campo a regenerar (ex: 'title_pt', 'description_en').
        language:
            Codigo do idioma (ex: 'pt-PT').
        instructions:
            Instrucoes adicionais para a geracao (opcional).

        Retorna
        -------
        Novo valor do campo gerado.
        """
        settings = get_settings()

        with get_session() as session:
            listing = session.get(Listing, listing_id)
            if not listing:
                raise ValueError(f"Listing nao encontrado: {listing_id}")

            deal = session.get(Deal, listing.deal_id) if listing.deal_id else None
            prop = (
                session.get(Property, deal.property_id)
                if deal
                else None
            )
            brand_kit = self._get_brand_kit(session, listing.tenant_id)
            lang_info = SUPPORTED_LANGUAGES.get(language, SUPPORTED_LANGUAGES["pt-PT"])

            # Valor actual do campo
            current_value = getattr(listing, field, None)

            prompt = (
                f"Regenera o campo '{field}' de um anuncio imobiliario.\n\n"
                f"Valor actual: {current_value or '(vazio)'}\n\n"
            )

            # Contexto da propriedade
            if prop:
                prompt += (
                    f"Imovel: {prop.property_type} em "
                    f"{prop.municipality}, {prop.district}\n"
                    f"Area: {prop.gross_area_m2} m\u00b2\n"
                    f"Quartos: {prop.bedrooms}\n"
                    f"Preco: {listing.listing_price} {listing.currency}\n"
                )

            if brand_kit:
                prompt += f"\nMarca: {brand_kit.get('brand_name', 'ImoIA')}\n"
                prompt += f"Tom: {brand_kit.get('voice_tone', 'profissional')}\n"

            prompt += f"\nIdioma: {lang_info.get('claude_instruction') or lang_info.get('instruction', '')}\n"

            if instructions:
                prompt += f"\nInstrucoes especificas: {instructions}\n"

            prompt += (
                f"\nGera um novo valor para o campo '{field}'. "
                f"Responde APENAS com o texto do campo, sem JSON, sem formatacao extra."
            )

            if not settings.anthropic_api_key:
                logger.warning("ANTHROPIC_API_KEY nao configurada — campo nao regenerado")
                return current_value or ""

            try:
                from anthropic import Anthropic

                client = Anthropic(api_key=settings.anthropic_api_key)
                response = client.messages.create(
                    model=settings.ai_model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )
                new_value = response.content[0].text.strip()

                # Guardar no listing
                setattr(listing, field, new_value)
                session.flush()

                # Criar registo ListingContent
                version = self._get_next_version(session, listing_id, language)
                record = ListingContent(
                    id=str(uuid4()),
                    listing_id=listing_id,
                    version=version,
                    language=language,
                    channel="portal",
                    content_type=field,
                    content=new_value,
                    is_active=True,
                    model_used=settings.ai_model,
                )
                session.add(record)
                session.flush()

                logger.info(
                    f"Campo '{field}' regenerado para listing {listing_id} "
                    f"(idioma: {language})"
                )
                return new_value

            except Exception as exc:
                logger.error(
                    f"Erro ao regenerar campo '{field}' "
                    f"(listing {listing_id}): {exc}"
                )
                return current_value or ""
