"""Schemas Pydantic para o modulo M7 — Marketing."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class BrandKitSchema(BaseModel):
    """Schema para criacao/actualizacao de brand kit."""

    brand_name: str
    tagline: Optional[str] = None
    website_url: Optional[str] = None
    color_primary: str = "#1E3A5F"
    color_secondary: str = "#F4A261"
    color_accent: str = "#E76F51"
    font_heading: str = "Montserrat"
    font_body: str = "Inter"
    voice_tone: str = "profissional"
    voice_description: Optional[str] = None
    voice_forbidden_words: List[str] = Field(default_factory=list)
    voice_preferred_words: List[str] = Field(default_factory=list)
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    contact_whatsapp: Optional[str] = None
    social_instagram: Optional[str] = None
    social_facebook: Optional[str] = None
    social_linkedin: Optional[str] = None
    active_languages: List[str] = Field(default_factory=lambda: ["pt-PT"])


class ListingCreateSchema(BaseModel):
    """Schema para criacao de listing."""

    listing_type: str = Field(pattern="^(venda|arrendamento)$")
    listing_price: float = Field(gt=0)
    floor_price: Optional[float] = None
    price_negotiable: bool = True
    auto_generate: bool = True
    languages: Optional[List[str]] = None
    notes: Optional[str] = None


class ListingUpdateSchema(BaseModel):
    """Schema para actualizacao de listing."""

    listing_price: Optional[float] = None
    title_pt: Optional[str] = None
    description_pt: Optional[str] = None
    short_description_pt: Optional[str] = None
    highlights: Optional[List[str]] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    slug: Optional[str] = None
    photos: Optional[List[Dict]] = None
    cover_photo_url: Optional[str] = None
    video_url: Optional[str] = None
    virtual_tour_url: Optional[str] = None
    content_whatsapp: Optional[str] = None
    notes: Optional[str] = None


class GenerateContentSchema(BaseModel):
    """Schema para geracao de conteudo."""

    languages: Optional[List[str]] = None
    channels: Optional[List[str]] = None


class RegenerateFieldSchema(BaseModel):
    """Schema para regeneracao de campo especifico."""

    field: str
    language: str = "pt-PT"
    channel: str = "website"
    instructions: Optional[str] = None


class ChangePriceSchema(BaseModel):
    """Schema para alteracao de preco."""

    new_price: float = Field(gt=0)
    reason: Optional[str] = None
    changed_by: str = "system"


class WhatsAppSendSchema(BaseModel):
    """Schema para envio WhatsApp."""

    group_ids: Optional[List[str]] = None
    language: str = "pt-PT"
    custom_message: Optional[str] = None
