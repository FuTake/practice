from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(slots=True)
class Settings:
    app_host: str = os.getenv("TODO_APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("TODO_APP_PORT", "8000"))
    db_path: Path = Path(
        os.getenv(
            "TODO_DB_PATH",
            "/Users/zhishikaishi/Desktop/temp/smallTools/TodoSkill/data/todo_agent.db",
        )
    )
    upload_dir: Path = Path(
        os.getenv(
            "TODO_UPLOAD_DIR",
            "/Users/zhishikaishi/Desktop/temp/smallTools/TodoSkill/uploads",
        )
    )
    llama_server_bin: Path = Path(
        os.getenv(
            "LLAMA_SERVER_BIN",
            "/Users/zhishikaishi/Desktop/temp/smallTools/llama/llama.cpp/build/bin/llama-server",
        )
    )
    llama_model_path: Path = Path(
        os.getenv(
            "LLAMA_MODEL_PATH",
            "/Users/zhishikaishi/.lmstudio/models/Jackrong/Qwen3.5-2B-Claude-4.6-Opus-Reasoning-Distilled-GGUF/Qwen3.5-2B.Q5_K_S.gguf",
        )
    )
    llama_mmproj_path: Path = Path(
        os.getenv(
            "LLAMA_MMPROJ_PATH",
            "/Users/zhishikaishi/.lmstudio/models/Jackrong/Qwen3.5-2B-Claude-4.6-Opus-Reasoning-Distilled-GGUF/mmproj-BF16.gguf",
        )
    )
    llama_server_url: str = os.getenv("LLAMA_SERVER_URL", "http://127.0.0.1:18080")
    llama_context_size: int = int(os.getenv("LLAMA_CONTEXT_SIZE", "8192"))
    llama_threads: int = int(os.getenv("LLAMA_THREADS", "8"))
    llama_gpu_layers: int = int(os.getenv("LLAMA_GPU_LAYERS", "99"))
    llama_batch_size: int = int(os.getenv("LLAMA_BATCH_SIZE", "512"))

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        (self.db_path.parent.parent / "logs").mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
