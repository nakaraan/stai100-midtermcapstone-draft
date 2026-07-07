"""FastAPI REST API for AGENT P — a thin HTTP wrapper around src/agent.py.

Mirrors the shape of sample_app.py (CORS middleware, a Pydantic request body, a
`/health` endpoint, one chat endpoint) but returns a single structured JSON
response instead of a server-sent stream, since src/agent.py's ReAct loop makes
several LLM round-trips internally and only has one final answer to hand back
per turn — there's no token stream to forward.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config.settings import get_settings
from src.agent import handle_query

app = FastAPI(
    title="AGENT P API",
    description="Predictive & Parametric Solar Analytics Assistant — NREL/NSRDB agentic backend.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def validate_config_on_startup() -> None:
    """Fail fast on a missing NREL key/email rather than on the first user request."""
    get_settings()


class ChatRequest(BaseModel):
    query: str
    session_id: str = "api_user"


class LocationOut(BaseModel):
    latitude: float
    longitude: float
    name: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    needs_clarification: bool = False
    location: Optional[LocationOut] = None
    year: Optional[int] = None
    start_month: Optional[int] = None
    end_month: Optional[int] = None
    attributes: Optional[list[str]] = None
    monthly_metrics: Optional[dict[int, dict[str, Optional[float]]]] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")

    try:
        result = handle_query(req.query, session_id=req.session_id)
    except Exception:
        # Never bubble a raw exception (which may include request internals) to the client.
        raise HTTPException(
            status_code=502,
            detail="AGENT P couldn't complete that request right now. Please try again shortly.",
        )

    return ChatResponse(
        answer=result.answer,
        session_id=result.session_id,
        needs_clarification=result.needs_clarification,
        location=LocationOut(**result.location) if result.location else None,
        year=result.year,
        start_month=result.start_month,
        end_month=result.end_month,
        attributes=result.attributes,
        monthly_metrics=result.monthly_metrics,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
