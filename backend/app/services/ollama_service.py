import asyncio
import json
import logging
import httpx
from ..config import settings

logger = logging.getLogger(__name__)


class OllamaService:
    def __init__(self) -> None:
        self.chat_url = f"{settings.ollama_base_url}/api/chat"
        self.tags_url = f"{settings.ollama_base_url}/api/tags"

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(self.tags_url)
                resp.raise_for_status()
                data = resp.json()
            return [m.get("name") for m in data.get("models", []) if m.get("name")]
        except Exception:
            return ["llama3.2", "mistral", "gemma3"]

    async def chat_once(self, payload: dict, retries: int = 2) -> dict:
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                    resp = await client.post(self.chat_url, json=payload)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as exc:
                logger.warning("ollama chat_once failed attempt=%s error=%s", attempt + 1, exc)
                if attempt >= retries:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))

    async def stream_chat(self, payload: dict):
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            async with client.stream("POST", self.chat_url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
