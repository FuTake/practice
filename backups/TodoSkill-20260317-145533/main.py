from __future__ import annotations

import uvicorn

from app.config import settings


if __name__ == "__main__":
    uvicorn.run("app.web:app", host=settings.app_host, port=settings.app_port, reload=False)
