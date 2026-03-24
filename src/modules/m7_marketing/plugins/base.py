"""Base classes para plugins de criativos e vídeos.

Cada plugin implementa uma das interfaces:
- CreativePlugin: gera imagens estáticas
- VideoPlugin: gera vídeos
- TourPlugin: gera tours virtuais
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class CreativePlugin(ABC):
    """Interface base para plugins de criativos estáticos (imagens)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome único do plugin (ex: 'playwright', 'trolto', 'canva')."""
        ...

    @property
    @abstractmethod
    def label(self) -> str:
        """Label legível (ex: 'Playwright (interno)', 'Trolto AI')."""
        ...

    @property
    def is_available(self) -> bool:
        """Verifica se o plugin está configurado e funcional."""
        return True

    @property
    def supported_types(self) -> List[str]:
        """Tipos de criativos suportados pelo plugin."""
        return ["ig_post", "ig_story", "fb_post", "property_card", "flyer"]

    @abstractmethod
    def generate(
        self,
        creative_type: str,
        width: int,
        height: int,
        template_data: Dict[str, Any],
    ) -> Optional[bytes]:
        """Gera imagem e retorna bytes (PNG/JPG)."""
        ...

    def get_config_schema(self) -> Dict[str, Any]:
        """Retorna schema de configuração do plugin (para UI)."""
        return {}


class VideoPlugin(ABC):
    """Interface base para plugins de vídeo."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def label(self) -> str:
        ...

    @property
    def is_available(self) -> bool:
        return True

    @property
    def supported_types(self) -> List[str]:
        return ["property_showcase", "instagram_reel", "before_after"]

    @abstractmethod
    def generate(
        self,
        video_type: str,
        props: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Inicia geração de vídeo. Retorna {status, job_id, ...}."""
        ...

    def check_status(self, job_id: str) -> Dict[str, Any]:
        """Verifica status de um job assíncrono."""
        return {"status": "not_implemented"}

    def download(self, job_id: str) -> Optional[bytes]:
        """Download do ficheiro gerado."""
        return None


class TourPlugin(ABC):
    """Interface base para plugins de tour virtual."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def label(self) -> str:
        ...

    @property
    def is_available(self) -> bool:
        return True

    @abstractmethod
    def generate(
        self,
        photos: List[str],
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Gera tour virtual. Retorna {status, url, ...}."""
        ...
