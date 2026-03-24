"""Excepcoes custom do ImoIA."""

from __future__ import annotations


class ImoIAError(Exception):
    """Excepcao base do ImoIA."""

    pass


class NotFoundError(ImoIAError):
    """Recurso nao encontrado."""

    def __init__(self, resource: str, resource_id: str | int) -> None:
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(f"{resource} {resource_id} nao encontrado")


class PipelineAlreadyRunningError(ImoIAError):
    """O pipeline ja esta a correr."""

    pass


class ValidationError(ImoIAError):
    """Erro de validacao de dados."""

    pass
