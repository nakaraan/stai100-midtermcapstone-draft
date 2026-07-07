import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core import FAQBot, stream_text, load_handbook
from logging_middleware import traced_chat

app = FastAPI(title="Oakridge Academy FAQ Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def load_handbook_once() -> None:
    load_handbook() # ingest on startup

# Cache for repeat requests on same memory store
_bots: dict[str, FAQBot] = {}


def _get_bot(student_id: str) -> FAQBot:
    if student_id not in _bots:
        _bots[student_id] = FAQBot(student_id)
    return _bots[student_id]


class ChatRequest(BaseModel):
    message: str
    student_id: str = "api_user"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    bot = _get_bot(req.student_id)

    def event_stream():
        try:
            answer = traced_chat(bot, req.message)
        except ValueError:
            fallback = (
                "I can't help with that request. I can only answer questions "
                "about the student handbook (academic policies, code of conduct, "
                "dress code, and campus health & safety)."
            )
            yield f"data: {json.dumps({'chunk': fallback})}\n\n"
            yield "data: [DONE]\n\n"
            return

        for chunk in stream_text(answer):
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
