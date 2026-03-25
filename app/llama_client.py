from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.time_utils import now_str


def local_httpx_get(url: str, timeout: float) -> httpx.Response:
    return httpx.get(url, timeout=timeout, trust_env=False)


def local_httpx_post(url: str, json_data: dict[str, Any], timeout: float) -> httpx.Response:
    return httpx.post(url, json=json_data, timeout=timeout, trust_env=False)


def append_llm_io_log(
    *,
    system_prompt: str,
    user_prompt: str,
    image_path: Path | None,
    temperature: float,
    max_tokens: int,
    model_name: str,
    response_text: str | None = None,
    error_text: str | None = None,
) -> None:
    log_path = settings.db_path.parent.parent / "logs" / "llm-io.log"
    image_value = str(image_path) if image_path else ""
    sections = [
        f"[{now_str()}] LLM_CALL",
        "[system_prompt]",
        system_prompt,
        "[user_prompt]",
        user_prompt,
        "[image_path]",
        image_value,
        "[options]",
        f"model={model_name}, temperature={temperature}, max_tokens={max_tokens}",
    ]
    if response_text is not None:
        sections.extend(["[response]", response_text])
    if error_text is not None:
        sections.extend(["[error]", error_text])
    sections.append("-" * 80)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(sections) + "\n")


class LMStudioClient:
    def __init__(self) -> None:
        self._resolved_model: str | None = None

    def _base_url(self) -> str:
        return settings.lm_studio_base_url.rstrip("/")

    def _list_models(self) -> list[str]:
        response = local_httpx_get(
            f"{self._base_url()}/v1/models",
            timeout=min(settings.lm_studio_timeout, 10.0),
        )
        response.raise_for_status()
        data = response.json()
        models = [str(item.get("id") or "").strip() for item in data.get("data", [])]
        return [model for model in models if model]

    def resolve_model(self) -> str:
        if self._resolved_model:
            return self._resolved_model

        configured_model = settings.lm_studio_model.strip()
        models = self._list_models()
        if configured_model:
            if configured_model not in models:
                raise RuntimeError(
                    f"LM Studio 未加载模型 `{configured_model}`。当前可用模型：{', '.join(models) or '无'}"
                )
            self._resolved_model = configured_model
            return self._resolved_model

        if not models:
            raise RuntimeError("LM Studio 当前没有可用模型，请先在 LM Studio 中加载模型。")

        self._resolved_model = models[0]
        return self._resolved_model

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        image_path: Path | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> str:
        model_name = ""
        try:
            model_name = self.resolve_model()
            content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
            if image_path:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": image_path.resolve().as_uri()},
                    }
                )

            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            response = local_httpx_post(
                f"{self._base_url()}/v1/chat/completions",
                json_data=payload,
                timeout=settings.lm_studio_timeout,
            )
            response.raise_for_status()
            response_text = response.text
            data = response.json()
            raw_content = str(data["choices"][0]["message"]["content"]).strip()
            content_text = self.strip_thinking_content(raw_content)
            append_llm_io_log(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                image_path=image_path,
                temperature=temperature,
                max_tokens=max_tokens,
                model_name=model_name,
                response_text=response_text,
            )
            return content_text
        except Exception as exc:
            append_llm_io_log(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                image_path=image_path,
                temperature=temperature,
                max_tokens=max_tokens,
                model_name=model_name or settings.lm_studio_model.strip() or "<unresolved>",
                error_text=str(exc),
            )
            raise

    @staticmethod
    def strip_thinking_content(text: str) -> str:
        cleaned = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()
        return cleaned or text.strip()

    @staticmethod
    def extract_json_block(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.split("\n", maxsplit=1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("模型没有返回 JSON")
        return json.loads(cleaned[start : end + 1])


llama_client = LMStudioClient()
