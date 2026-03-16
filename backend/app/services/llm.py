import json
from typing import Any

import httpx

from ..config import Settings


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        self._ensure_configured()

        system_prompt = self._build_system_prompt(system_prompt, json_schema)

        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": self._build_response_format(json_schema),
            "temperature": self.settings.llm_temperature,
        }

        if self.settings.llm_provider == "gemini":
            body["reasoning_effort"] = "none"

        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            response = await client.post(
                f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
            return self._extract_json_content(payload)

    def _ensure_configured(self) -> None:
        if not self.settings.llm_provider:
            raise RuntimeError("未配置 LLM_PROVIDER。")
        if not self.settings.llm_api_key:
            raise RuntimeError("未配置 LLM_API_KEY。")
        if not self.settings.llm_base_url:
            raise RuntimeError("未配置 LLM_BASE_URL。")
        if not self.settings.llm_model:
            raise RuntimeError("未配置 LLM_MODEL。")

    def _build_response_format(self, json_schema: dict[str, Any]) -> dict[str, Any]:
        if self.settings.llm_provider == "gemini":
            return {"type": "json_object"}
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "workflow_output",
                "strict": True,
                "schema": json_schema,
            },
        }

    def _build_system_prompt(self, system_prompt: str, json_schema: dict[str, Any]) -> str:
        if self.settings.llm_provider != "gemini":
            return system_prompt

        schema_text = json.dumps(json_schema, ensure_ascii=False)
        return (
            f"{system_prompt}\n"
            "你当前通过 Gemini OpenAI 兼容接口返回内容。\n"
            "请只输出一个合法 JSON object，不要输出 Markdown 代码块，不要输出解释。\n"
            f"输出必须尽量符合以下 JSON Schema：{schema_text}"
        )

    def _extract_json_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = payload["choices"][0]["message"]
        content = message.get("content", "")

        if isinstance(content, list):
            text = "".join(item.get("text", "") for item in content if item.get("type") == "text")
            return json.loads(text)

        if isinstance(content, str):
            return json.loads(content)

        if isinstance(content, dict):
            return content

        raise ValueError("LLM 返回内容无法解析为 JSON。")
