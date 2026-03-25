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
    lm_studio_base_url: str = os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234")
    lm_studio_model: str = os.getenv("LM_STUDIO_MODEL", "")
    lm_studio_timeout: float = float(os.getenv("LM_STUDIO_TIMEOUT", "120"))

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        (self.db_path.parent.parent / "logs").mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
