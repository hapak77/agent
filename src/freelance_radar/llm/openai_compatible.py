"""OpenAI-compatible chat completions client."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from freelance_radar.llm.base import LLMClient
from freelance_radar.llm.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from freelance_radar.logging_setup import get_logger
from freelance_radar.schemas import LLMOrderAnalysis

logger = get_logger(__name__)
JSON_BLOCK_RE = re.compile(r"\{.*\}", re.S)


class OpenAICompatibleClient(LLMClient):
    def __init__(
        self,
        *,
        api_base: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model_name = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.prompt_version = PROMPT_VERSION

    async def analyze_order(self, *, title: str | None, text: str) -> LLMOrderAnalysis:
        payload = {
            "model": self.model_name,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(title=title, text=text)},
            ],
        }
        data = await self._chat(payload)
        content = self._extract_content(data)
        parsed = self._parse_json(content)
        return LLMOrderAnalysis.model_validate(parsed)

    def _extract_content(self, data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("LLM response has no choices")
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return str(content)

    def _parse_json(self, content: str) -> dict[str, Any]:
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = JSON_BLOCK_RE.search(content)
            if not match:
                raise
            return json.loads(match.group(0))

    async def _chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        @retry(
            stop=stop_after_attempt(max(1, self.max_retries + 1)),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            reraise=True,
        )
        async def _do() -> dict[str, Any]:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code == 429:
                    logger.warning("llm_rate_limited")
                    resp.raise_for_status()
                resp.raise_for_status()
                return resp.json()

        return await _do()
