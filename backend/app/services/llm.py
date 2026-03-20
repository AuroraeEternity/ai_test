from __future__ import annotations

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from ..config import Settings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: genai.Client | None = None

    @property
    # 使用 @property 将方法伪装成属性
    def client(self) -> genai.Client:
        if self._client is None:
            if not self.settings.llm_api_key:
                raise RuntimeError("未配置 LLM_API_KEY。")
            self._client = genai.Client(api_key=self.settings.llm_api_key)
        return self._client

    @property
    def model(self) -> str:
        if not self.settings.llm_model:
            raise RuntimeError("未配置 LLM_MODEL。")
        return self.settings.llm_model

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """调用 Gemini 生成结构化 JSON 输出。"""
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature if temperature is not None else self.settings.llm_temperature,
                response_mime_type="application/json",
                response_json_schema=json_schema,
            ),
        )
        return self._parse_json_response(response)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _parse_json_response(self, response: types.GenerateContentResponse) -> dict[str, Any]:
        text = (response.text or "").strip()

        if not text:
            raise ValueError("Gemini 返回内容为空")

        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Gemini 返回 JSON 解析失败: {e}; 原文前 200 字: {text[:200]}"
            ) from e
