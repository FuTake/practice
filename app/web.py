from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.agent import run_agent
from app.config import settings
from app.todo_tools import init_db, repo


app = FastAPI(title="TodoSkill LangGraph Web")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent.parent / "static")), name="static")


def save_upload(file: UploadFile | None) -> str | None:
    if not file or not file.filename:
        return None
    suffix = Path(file.filename).suffix or ".bin"
    target = settings.upload_dir / f"{uuid4().hex}{suffix}"
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    return str(target)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    history = repo.list_chat_logs(limit=20)
    return templates.TemplateResponse("index.html", {"request": request, "history": history})


@app.get("/history")
async def history() -> JSONResponse:
    return JSONResponse({"items": repo.list_chat_logs(limit=50)})


@app.get("/tasks")
async def tasks() -> JSONResponse:
    result = repo.list_tasks()
    return JSONResponse(result.payload or {"tasks": []})


@app.post("/chat")
async def chat(
    message: str = Form(...),
    image: UploadFile | None = File(default=None),
) -> JSONResponse:
    image_path = save_upload(image)
    result = run_agent(message, image_path=image_path)
    return JSONResponse(
        {
            "title": result["chat_title"],
            "assistant_message": result["assistant_message"],
            "intent": result.get("intent"),
            "vision_summary": result.get("vision_summary"),
            "image_path": image_path,
            "parse_error": result.get("parse_error"),
        }
    )
