"""Cliente WhatsApp para o ImoIA.

Suporta dois backends:
- Baileys Bridge (local, gratuito) — http://localhost:3000
- Whapi.Cloud (pago) — https://gate.whapi.cloud

O backend e escolhido automaticamente:
- Se WHAPI_TOKEN estiver configurado, usa Whapi.Cloud
- Caso contrario, usa o Baileys Bridge local
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import get_settings


class WhatsAppClient:
    """Cliente WhatsApp com suporte a Baileys Bridge e Whapi.Cloud.

    Attributes:
        base_url: URL base da API.
        backend: Tipo de backend ('baileys' ou 'whapi').
    """

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """Inicializa o cliente WhatsApp.

        Deteta automaticamente qual backend usar com base na configuracao.

        Args:
            token: Token da API Whapi.Cloud. Se None, usa a config.
            base_url: URL base da API. Se None, deteta automaticamente.
        """
        settings = get_settings()

        if base_url:
            # Override manual (ex: testes). Respeita WHATSAPP_BACKEND se definido;
            # caso contrario usa heuristica (localhost/127.0.0.1 -> baileys).
            self.base_url = base_url.rstrip("/")
            if settings.whatsapp_backend in ("baileys", "whapi"):
                self.backend = settings.whatsapp_backend
            else:
                self.backend = "baileys" if "localhost" in base_url or "127.0.0.1" in base_url else "whapi"
            self.token = token or (settings.whatsapp_api_token if self.backend == "baileys" else settings.whapi_token)
        elif settings.whatsapp_backend == "baileys" and settings.whatsapp_api_base:
            # Baileys Bridge self-hosted (Fly.io, etc)
            self.backend = "baileys"
            self.base_url = settings.whatsapp_api_base.rstrip("/")
            self.token = token or settings.whatsapp_api_token
        elif settings.whatsapp_backend == "baileys":
            # Baileys local (dev)
            self.backend = "baileys"
            self.base_url = "http://localhost:3000"
            self.token = token or settings.whatsapp_api_token
        else:
            # Whapi.cloud (legacy default)
            self.backend = "whapi"
            self.base_url = settings.whapi_base_url.rstrip("/")
            self.token = token or settings.whapi_token

        self._headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.token:
            self._headers["Authorization"] = f"Bearer {self.token}"

        logger.info(f"WhatsApp client inicializado: backend={self.backend}, url={self.base_url}")

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Faz um pedido HTTP a API com retry e backoff exponencial.

        Args:
            method: Metodo HTTP (GET, PATCH, PUT, POST, etc.).
            endpoint: Endpoint da API.
            params: Parametros de query string.
            json_body: Body JSON para enviar.

        Returns:
            Resposta JSON como dicionario.
        """
        return self._do_request(method, endpoint, params, json_body)

    def _do_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Executa o pedido HTTP (sem retry)."""
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"Pedido {method} {url}")

        with httpx.Client(timeout=60.0) as http_client:
            response = http_client.request(
                method=method,
                url=url,
                headers=self._headers,
                params=params,
                json=json_body,
            )
            response.raise_for_status()
            return response.json()

    def get_status(self) -> Dict[str, Any]:
        """Verifica o estado da conexao com o WhatsApp.

        Returns:
            Dicionario com estado da conexao e QR code se disponivel.
        """
        if self.backend == "baileys":
            try:
                return self._request("GET", "/status")
            except Exception as e:
                logger.warning(f"Bridge nao disponivel: {e}")
                return {"status": "offline", "connected": False, "qr": None}

        try:
            data = self._request("GET", "/health")
            status_code = data.get("status", {}).get("code", 0)
            connected = status_code in (1, 4)  # 1=CONNECTED, 4=AUTH (operational)
            return {
                "status": "connected" if connected else "disconnected",
                "connected": connected,
                "qr": None,
                "user": data.get("user"),
            }
        except Exception as e:
            logger.warning(f"Whapi nao disponivel: {e}")
            return {"status": "offline", "connected": False, "qr": None}

    def list_active_groups(self) -> List[Dict[str, Any]]:
        """Lista todos os grupos de WhatsApp ativos.

        Returns:
            Lista de dicionarios com informacao dos grupos.
        """
        logger.info("A buscar lista de grupos ativos")

        if self.backend == "whapi":
            return self._list_groups_whapi()

        data = self._request("GET", "/groups")
        groups = data.get("groups", [])
        logger.info(f"Encontrados {len(groups)} grupos no bridge (archive do device ignorado — filtro por is_active na BD)")
        return groups

    def _list_groups_whapi(self) -> List[Dict[str, Any]]:
        """Lista grupos via Whapi.Cloud usando /chats (inclui sub-grupos de comunidades).

        O endpoint /groups nao retorna sub-grupos de comunidades WhatsApp.
        Usa /chats e filtra por @g.us para apanhar todos os grupos.
        Tenta varios tamanhos de pagina se a API estiver instavel.
        """
        # Tentar com page sizes diferentes — a API pode rejeitar counts altos
        for page_size in [500, 100, 50, 20, 10, 5]:
            groups = self._fetch_all_group_chats(page_size)
            if groups:
                logger.info(f"Encontrados {len(groups)} grupos (Whapi, page_size={page_size})")
                return groups
            logger.warning(f"0 grupos com page_size={page_size}, a tentar menor...")

        logger.error("Nao foi possivel obter grupos da API Whapi")
        return []

    def _fetch_all_group_chats(self, page_size: int) -> List[Dict[str, Any]]:
        """Busca todos os chats de grupo com paginacao.

        Args:
            page_size: Numero de chats por pagina.

        Returns:
            Lista de grupos normalizados.
        """
        all_groups: List[Dict[str, Any]] = []
        seen_ids: set = set()
        offset = 0
        empty_pages = 0

        while True:
            try:
                data = self._do_request(
                    "GET",
                    "/chats",
                    params={"count": page_size, "offset": offset},
                )
            except Exception as e:
                logger.warning(f"Erro ao buscar chats (offset={offset}): {e}")
                break

            chats = data.get("chats", [])
            total = data.get("total", 0)

            if not chats:
                empty_pages += 1
                # Se a API reporta total > 0 mas retorna 0 chats, avancar offset
                if total > 0 and empty_pages <= 3:
                    offset += page_size
                    continue
                break

            empty_pages = 0
            for chat in chats:
                chat_id = chat.get("id", "")
                if "@g.us" not in chat_id:
                    continue
                if chat_id in seen_ids:
                    continue
                seen_ids.add(chat_id)
                is_archived = bool(chat.get("archive"))
                last_msg = chat.get("last_message", {})
                all_groups.append({
                    "id": chat_id,
                    "name": chat.get("name", "Desconhecido"),
                    "is_archived": is_archived,
                    "unread": chat.get("unread", 0) or 0,
                    "last_message_ts": last_msg.get("timestamp", 0) if isinstance(last_msg, dict) else 0,
                })

            offset += len(chats)
            if len(chats) < page_size:
                break

        return all_groups

    def fetch_unread_messages(
        self,
        group_id: str,
        since: datetime,
    ) -> List[Dict[str, Any]]:
        """Busca mensagens de texto de um grupo desde uma data.

        Args:
            group_id: ID do grupo de WhatsApp.
            since: Data minima das mensagens.

        Returns:
            Lista de dicionarios com as mensagens normalizadas.
        """
        logger.info(f"A buscar mensagens do grupo {group_id} desde {since}")

        if self.backend == "baileys":
            return self._fetch_baileys(group_id, since)
        return self._fetch_whapi(group_id, since)

    def _fetch_baileys(
        self, group_id: str, since: datetime
    ) -> List[Dict[str, Any]]:
        """Busca mensagens via Baileys Bridge local."""
        since_ts = int(since.timestamp()) if since.tzinfo else int(since.replace(tzinfo=timezone.utc).timestamp())

        data = self._request(
            "GET",
            f"/messages/{group_id}",
            params={"count": 100, "since": since_ts},
        )

        messages: List[Dict[str, Any]] = []
        for msg in data.get("messages", []):
            if msg.get("type") != "text":
                continue
            body = msg.get("body", "")
            if not body:
                continue

            ts = msg.get("timestamp", 0)
            msg_dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(tz=timezone.utc)

            messages.append({
                "whatsapp_message_id": msg.get("id", ""),
                "sender_id": msg.get("from", ""),
                "sender_name": msg.get("pushName", ""),
                "content": body,
                "message_type": "text",
                "timestamp": msg_dt,
            })

        logger.info(f"Grupo {group_id}: {len(messages)} mensagens de texto via Baileys")
        return messages

    def _fetch_whapi(
        self, group_id: str, since: datetime
    ) -> List[Dict[str, Any]]:
        """Busca mensagens via Whapi.Cloud com paginacao e filtro por data."""
        since_ts = int(since.timestamp()) if since.tzinfo else int(since.replace(tzinfo=timezone.utc).timestamp())
        all_messages: List[Dict[str, Any]] = []
        page_count = 0
        max_pages = 10
        offset = 0

        while page_count < max_pages:
            page_count += 1
            data = self._request(
                "GET",
                f"/messages/list/{group_id}",
                params={"count": 100, "offset": offset},
            )
            raw_messages = data.get("messages", [])

            if not raw_messages:
                break

            reached_old = False
            for msg in raw_messages:
                parsed = self._parse_whapi_message(msg, since)
                if parsed is not None:
                    all_messages.append(parsed)

                # Whapi retorna mensagens por ordem decrescente
                # Se o timestamp e anterior ao since, podemos parar
                ts = msg.get("timestamp", 0)
                if ts and ts < since_ts:
                    reached_old = True

            if reached_old or len(raw_messages) < 100:
                break

            offset += len(raw_messages)

        logger.info(
            f"Grupo {group_id}: {len(all_messages)} mensagens de texto via Whapi "
            f"({page_count} paginas)"
        )
        return all_messages

    def _parse_whapi_message(
        self,
        raw: Dict[str, Any],
        since: datetime,
    ) -> Optional[Dict[str, Any]]:
        """Parseia uma mensagem raw da API Whapi.Cloud.

        Aceita mensagens de texto e imagens com legenda.
        """
        msg_type = raw.get("type")

        ts = raw.get("timestamp", 0)
        msg_dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None

        if msg_dt and msg_dt < since:
            return None

        # Extrair corpo da mensagem
        body = ""
        if msg_type == "text":
            text_obj = raw.get("text", {})
            body = text_obj.get("body", "") if isinstance(text_obj, dict) else ""
        elif msg_type == "image":
            image_obj = raw.get("image", {})
            body = image_obj.get("caption", "") if isinstance(image_obj, dict) else ""

        if not body:
            return None

        return {
            "whatsapp_message_id": raw.get("id", ""),
            "sender_id": raw.get("from", ""),
            "sender_name": raw.get("from_name", ""),
            "content": body,
            "message_type": "text",
            "timestamp": msg_dt or datetime.now(tz=timezone.utc),
        }

    def mark_as_read(self, message_id: str) -> bool:
        """Marca uma mensagem como lida.

        Args:
            message_id: ID da mensagem a marcar como lida.

        Returns:
            True se marcada com sucesso.
        """
        if self.backend == "baileys":
            return False

        try:
            self._do_request(
                "PUT",
                f"/messages/{message_id}",
                json_body={"status": "read"},
            )
            return True
        except Exception as e:
            logger.warning(f"Erro ao marcar mensagem como lida: {e}")
            return False

    def mark_messages_as_read(self, messages: List[Dict[str, Any]]) -> int:
        """Marca uma lista de mensagens como lidas (read receipts individuais).

        Usa PUT /messages/{id} para cada mensagem. Nao falha se uma
        mensagem individual falhar — continua com as restantes.

        Args:
            messages: Lista de dicts com chave 'whatsapp_message_id'.

        Returns:
            Numero de mensagens marcadas com sucesso.
        """
        if self.backend == "baileys":
            return 0

        count = 0
        for msg in messages:
            msg_id = msg.get("whatsapp_message_id", "")
            if not msg_id:
                continue
            if self.mark_as_read(msg_id):
                count += 1

        if count > 0:
            logger.info(f"{count}/{len(messages)} mensagens marcadas como lidas (read receipts)")

        return count

    def mark_group_as_read_light(self, chat_id: str) -> bool:
        """Marca grupo como lido marcando apenas a ÚLTIMA mensagem.

        Mais leve que mark_group_as_read (1 PUT em vez de 50).
        Suficiente para limpar o badge de unread no device.
        """
        if self.backend == "baileys":
            return False

        try:
            data = self._do_request(
                "GET",
                f"/messages/list/{chat_id}",
                params={"count": 1},
            )
        except Exception as e:
            logger.warning(f"Falha fetch última msg para mark_as_read {chat_id}: {e}")
            return self._patch_chat_read(chat_id)

        messages = data.get("messages", [])
        if not messages:
            return True

        msg = messages[0]
        if not msg.get("from_me"):
            msg_id = msg.get("id", "")
            if msg_id:
                self.mark_as_read(msg_id)

        self._patch_chat_read(chat_id)
        logger.info(f"Grupo {chat_id} marcado como lido (light)")
        return True

    def mark_group_as_read(self, chat_id: str) -> bool:
        """Marca grupo como lido marcando TODAS as mensagens recentes.

        Marca todas as mensagens que nao sao nossas (from_me=False),
        independentemente do tipo (text, image, unknown/revoked, action, etc.).
        A Whapi precisa de receber PUT em cada mensagem para sincronizar
        o read receipt com o dispositivo.

        Args:
            chat_id: ID do chat/grupo.

        Returns:
            True se marcado com sucesso.
        """
        if self.backend == "baileys":
            return False

        try:
            data = self._do_request(
                "GET",
                f"/messages/list/{chat_id}",
                params={"count": 50},
            )
        except Exception as e:
            logger.warning(f"Falha fetch msgs para mark_as_read {chat_id}: {e}")
            return self._patch_chat_read(chat_id)

        messages = data.get("messages", [])
        if not messages:
            return True

        # Marcar TODAS as mensagens (qualquer tipo, desde que nao seja from_me)
        marked = 0
        for msg in messages:
            if not msg.get("from_me"):
                msg_id = msg.get("id", "")
                if msg_id and self.mark_as_read(msg_id):
                    marked += 1

        # PATCH o chat para limpar o contador
        self._patch_chat_read(chat_id)

        if marked > 0:
            logger.info(f"Grupo {chat_id} marcado como lido ({marked} msgs)")
        else:
            logger.warning(f"Grupo {chat_id}: 0 msgs marcadas. Apenas PATCH.")

        return True

    def _patch_chat_read(self, chat_id: str) -> bool:
        """Marca chat como lido via PATCH (sincroniza com device)."""
        try:
            self._do_request(
                "PATCH",
                f"/chats/{chat_id}",
                json_body={"read": True},
            )
            return True
        except Exception as e:
            logger.warning(f"PATCH read falhou para {chat_id}: {e}")
            return False

    def ensure_chat_read(self, chat_id: str) -> bool:
        """Garante que um chat esta marcado como lido.

        Usa mark_group_as_read (busca ultima msg real) com fallback para
        PATCH /chats/{id}. Nunca falha com excecao.

        Args:
            chat_id: ID do chat/grupo.

        Returns:
            True se marcado com sucesso.
        """
        try:
            return self.mark_group_as_read(chat_id)
        except Exception as e:
            logger.warning(f"Erro ao marcar chat {chat_id} como lido: {e}")
            return False

    def mark_chat_as_read(self, chat_id: str) -> bool:
        """Marca todas as mensagens de um chat como lidas.

        Usa PATCH /chats/{id} com {"read": true} para sincronizar
        com o device principal.

        Args:
            chat_id: ID do chat/grupo.

        Returns:
            True se marcado com sucesso.
        """
        if self.backend == "baileys":
            return False

        try:
            self._do_request(
                "PATCH",
                f"/chats/{chat_id}",
                json_body={"read": True},
            )
            logger.info(f"Chat {chat_id} marcado como lido (PATCH read=true)")
            return True
        except Exception as e:
            logger.warning(f"Erro ao marcar chat {chat_id} como lido: {e}")
            return False

    def mark_group_read(self, group_id: str) -> bool:
        """Marca um grupo de WhatsApp como lido no device.

        Archive foi removido — o companion mode do Whapi/Baileys não
        arquiva no device primário de forma fiável. Apenas mark-as-read
        é garantido via chatModify (buffer) ou fallback sem lastMessages.

        Args:
            group_id: ID do grupo a marcar.

        Returns:
            True se mark-as-read foi aceite pelo bridge.
        """
        if self.backend == "whapi":
            return self._patch_chat_read(group_id)

        try:
            self._request("PATCH", f"/groups/{group_id}")
            logger.info(f"Grupo {group_id} marcado como lido")
            return True
        except (httpx.HTTPStatusError, httpx.ConnectError) as e:
            logger.error(f"Erro ao marcar grupo {group_id} como lido: {e}")
            return False

    def set_presence_offline(self) -> bool:
        """Define presença como offline para restaurar notificações push no device.

        Quando a API Whapi conecta, o device para de receber notificações push.
        Chamar este método no final de cada ciclo força o status offline,
        permitindo que as notificações voltem a funcionar.
        """
        if self.backend == "baileys":
            return False

        try:
            self._do_request(
                "PUT",
                "/presences/me",
                json_body={"presence": "offline"},
            )
            logger.info("Presença definida como offline (notificações push restauradas)")
            return True
        except Exception as e:
            logger.warning(f"Falha ao definir presença offline: {e}")
            return False

