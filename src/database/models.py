"""Modelos SQLAlchemy legacy (READ-ONLY).

Define as tabelas: Group, Message, Opportunity, MarketData.
Todos os teammates devem respeitar este schema — é o contrato central.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Classe base para todos os modelos."""
    pass


class Group(Base):
    """Grupo de WhatsApp monitorizado."""

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    whatsapp_group_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    opportunity_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    messages: Mapped[List["Message"]] = relationship("Message", back_populates="group")


class Message(Base):
    """Mensagem recebida de um grupo de WhatsApp."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    whatsapp_message_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id"), nullable=False)
    group_name: Mapped[str] = mapped_column(Text, nullable=False)
    sender_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(Text, default="text")
    media_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    group: Mapped["Group"] = relationship("Group", back_populates="messages")
    opportunity: Mapped[Optional["Opportunity"]] = relationship("Opportunity", back_populates="message", uselist=False)


class Opportunity(Base):
    """Oportunidade imobiliária detetada pela IA."""

    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey("messages.id"), unique=True, nullable=False)
    is_opportunity: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    opportunity_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    property_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location_extracted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parish: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    municipality: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    district: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_mentioned: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="nova")
    deal_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deal_grade: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    message: Mapped["Message"] = relationship("Message", back_populates="opportunity")
    market_data: Mapped[Optional["MarketData"]] = relationship("MarketData", back_populates="opportunity", uselist=False)


class MarketData(Base):
    """Dados de mercado associados a uma oportunidade."""

    __tablename__ = "market_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(Integer, ForeignKey("opportunities.id"), unique=True, nullable=False)

    # INE (baseline nacional)
    ine_median_price_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ine_quarter: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Casafari (comparaveis e estatisticas)
    casafari_avg_price_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    casafari_median_price_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    casafari_comparables_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Infocasa (comparaveis e analise)
    infocasa_avg_price_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    infocasa_median_price_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    infocasa_comparables_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # SIR / Confidencial Imobiliario (transacoes reais)
    sir_median_price_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sir_market_position: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sir_price_vs_market_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sir_transactions_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Idealista (opcional — listings ativos)
    idealista_avg_price_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    idealista_listings_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    idealista_comparable_urls: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Valores estimados
    estimated_market_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_monthly_rent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Yield
    gross_yield_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_yield_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_vs_market_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Custos de aquisicao
    imt_estimate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stamp_duty_estimate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_acquisition_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    opportunity: Mapped["Opportunity"] = relationship("Opportunity", back_populates="market_data")
