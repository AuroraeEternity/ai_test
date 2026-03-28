from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from google import genai
from google.genai import types

from .config import Settings

logger = logging.getLogger(__name__)

# LLM 单次调用的超时时间（秒）
LLM_TIMEOUT_SECONDS = 120


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
        actual_temperature = temperature if temperature is not None else self.settings.llm_temperature
        logger.info("LLM 请求开始 | model=%s temperature=%s", self.model, actual_temperature)
        logger.debug("system_prompt=%s", system_prompt)
        logger.debug("user_prompt=%s", user_prompt)

        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=actual_temperature,
                        response_mime_type="application/json",
                        response_json_schema=json_schema,
                    ),
                ),
                timeout=LLM_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.error("LLM 请求超时 | timeout=%ds", LLM_TIMEOUT_SECONDS)
            raise TimeoutError(f"LLM 请求超时（{LLM_TIMEOUT_SECONDS}s），请稍后重试。")

        usage = getattr(response, "usage_metadata", None)
        if usage:
            logger.info(
                "LLM 请求完成 | input_tokens=%s output_tokens=%s total_tokens=%s",
                getattr(usage, "prompt_token_count", "?"),
                getattr(usage, "candidates_token_count", "?"),
                getattr(usage, "total_token_count", "?"),
            )
        else:
            logger.info("LLM 请求完成")

        return self._parse_json_response(response)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _parse_json_response(self, response: types.GenerateContentResponse) -> dict[str, Any]:
        text = (response.text or "").strip()

        if not text:
            logger.error("Gemini 返回内容为空")
            raise ValueError("Gemini 返回内容为空")

        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            result = json.loads(text)
            logger.debug("JSON 解析成功 | keys=%s", list(result.keys()) if isinstance(result, dict) else type(result).__name__)
            return result
        except json.JSONDecodeError as e:
            logger.error("JSON 解析失败 | error=%s | 原文前 200 字=%s", e, text[:200])
            raise ValueError(
                f"Gemini 返回 JSON 解析失败: {e}; 原文前 200 字: {text[:200]}"
            ) from e
