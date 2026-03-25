from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

import httpx

from app.config import settings


def local_httpx_get(url: str, timeout: float) -> httpx.Response:
    return httpx.get(url, timeout=timeout, trust_env=False)


def local_httpx_post(url: str, json_data: dict[str, Any], timeout: float) -> httpx.Response:
    return httpx.post(url, json=json_data, timeout=timeout, trust_env=False)


class LlamaServerManager:
    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._log_handle = None

    def ensure_server(self) -> None:
        if self._is_healthy():
            return
        if self._process and self._process.poll() is None:
            self._wait_until_ready()
            return
        self._start_server()
        self._wait_until_ready()

    def _is_healthy(self) -> bool:
        try:
            response = local_httpx_get(f"{settings.llama_server_url}/health", timeout=2.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def _start_server(self) -> None:
        parsed = urlparse(settings.llama_server_url)
        host = parsed.hostname or "127.0.0.1"
        port = str(parsed.port or 18080)
        log_path = settings.db_path.parent.parent / "logs" / "llama-server.log"
        self._log_handle = log_path.open("a", encoding="utf-8")
        cmd = [
            str(settings.llama_server_bin),
            "-m",
            str(settings.llama_model_path),
            "--mmproj",
            str(settings.llama_mmproj_path),
            "--host",
            host,
            "--port",
            port,
            "-c",
            str(settings.llama_context_size),
            "-t",
            str(settings.llama_threads),
            "-ub",
            str(settings.llama_batch_size),
        ]
        if settings.llama_gpu_layers > 0:
            cmd.extend(["-ngl", str(settings.llama_gpu_layers)])
        else:
            cmd.extend(["--device", "none", "--no-mmproj-offload", "-ngl", "0"])
        self._process = subprocess.Popen(
            cmd,
            stdout=self._log_handle,
            stderr=self._log_handle,
            text=True,
        )

    def _wait_until_ready(self) -> None:
        deadline = time.time() + 180
        while time.time() < deadline:
            if self._is_healthy():
                return
            if self._process and self._process.poll() is not None:
                raise RuntimeError("llama-server 启动失败，请检查模型路径和 mmproj 配置。")
            time.sleep(1.0)
        raise RuntimeError("llama-server 启动超时。")


class LlamaClient:
    def __init__(self, server_manager: LlamaServerManager) -> None:
        self.server_manager = server_manager

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        image_path: Path | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> str:
        self.server_manager.ensure_server()
        content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
        if image_path:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image_path.resolve().as_uri()},
                }
            )

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        response = local_httpx_post(
            f"{settings.llama_server_url}/v1/chat/completions",
            json_data=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

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


server_manager = LlamaServerManager()
llama_client = LlamaClient(server_manager)
