"""Configuração central do ImoScout.

Carrega variáveis de ambiente e define constantes partilhadas por todos os módulos.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Carregar .env da raiz do projeto
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Configurações globais do ImoScout."""

    # Whapi.Cloud
    whapi_token: str = field(default_factory=lambda: os.getenv("WHAPI_TOKEN", ""))
    whapi_base_url: str = "https://gate.whapi.cloud"

    # Anthropic
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    ai_model: str = "claude-haiku-4-5-20251001"
    ai_max_tokens: int = 4096
    ai_temperature: float = 0.1

    # Idealista (opcional)
    idealista_client_id: str = field(default_factory=lambda: os.getenv("IDEALISTA_CLIENT_ID", ""))
    idealista_client_secret: str = field(default_factory=lambda: os.getenv("IDEALISTA_CLIENT_SECRET", ""))
    idealista_base_url: str = "https://api.idealista.com/3.5/"

    # Casafari (API Token — obter em app.casafari.com > Settings > API)
    casafari_api_token: str = field(default_factory=lambda: os.getenv("CASAFARI_API_TOKEN", ""))

    # Casafari (credenciais legacy — deprecated, usar API Token)
    casafari_username: str = field(default_factory=lambda: os.getenv("CASAFARI_USERNAME", ""))
    casafari_password: str = field(default_factory=lambda: os.getenv("CASAFARI_PASSWORD", ""))
    casafari_base_url: str = "https://api.casafari.com"

    # SIR / Confidencial Imobiliario
    sir_username: str = field(default_factory=lambda: os.getenv("SIR_USERNAME", ""))
    sir_password: str = field(default_factory=lambda: os.getenv("SIR_PASSWORD", ""))
    sir_base_url: str = "https://sir.confidencialimobiliario.com/api/v3"

    # Infocasa
    infocasa_username: str = field(default_factory=lambda: os.getenv("INFOCASA_USERNAME", ""))
    infocasa_password: str = field(default_factory=lambda: os.getenv("INFOCASA_PASSWORD", ""))
    infocasa_base_url: str = "https://www.infocasa.pt"

    # INE
    ine_base_url: str = "https://www.ine.pt/ine/json_indicador/pindica.jsp"

    # Base de dados
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{_PROJECT_ROOT / 'data' / 'imoscout.db'}")
    )

    # Pipeline
    min_confidence: float = field(
        default_factory=lambda: float(os.getenv("MIN_CONFIDENCE", "0.6"))
    )
    batch_size: int = field(
        default_factory=lambda: int(os.getenv("BATCH_SIZE", "20"))
    )
    timezone: str = field(
        default_factory=lambda: os.getenv("TIMEZONE", "Europe/Lisbon")
    )

    # Retry
    max_retries: int = 3
    retry_base_delay: float = 2.0

    # Filtros de ruído
    min_message_length: int = 15
    noise_patterns: List[str] = field(default_factory=lambda: [
        "bom dia", "boa tarde", "boa noite", "boas",
        "obrigad", "parabéns", "feliz", "😀", "🙏",
        "alguém conhece", "alguém sabe", "alguém recomenda",
        "simulação gratuita", "crédito habitação", "taxa de juro",
        "oferta de crédito",
    ])


def get_settings() -> Settings:
    """Retorna a instância de configuração."""
    return Settings()
