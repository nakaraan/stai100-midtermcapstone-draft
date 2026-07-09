#Utilizes Fast API to create a REST API structure.
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config.settings import get_settings
from src.agent import handle_query

#Initialize FastAPI app with title, description, and version.
app = FastAPI(
    title="AGENT P API",
    description="Predictive & Parametric Solar Analytics Assistant — NREL/NSRDB agentic backend.",
    version="0.1.0",
)

#Add CORS middleware to allow cross-origin requests from any origin, with any method and headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Validate configuration on startup to ensure that the necessary settings are present.
# Will fail on missing NREL key instead of waiting for the first user request, providing a fail-fast mechanism.
@app.on_event("startup")
def validate_config_on_startup() -> None:
    get_settings()

# Chat Request class for query and session_id, with default session_id set to "api_user".
class ChatRequest(BaseModel):
    query: str
    session_id: str = "api_user"

# Location output class for latitude, longitude, and optional name.To locate the location inputted by the user.
class LocationOut(BaseModel):
    latitude: float
    longitude: float
    name: Optional[str] = None

# Chat Response class for structured response from the chat endpoint, including answer, session_id, 
# and optional fields for clarification, location, year, months, attributes, and monthly metrics.
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

# Health check endpoint to verify that the API is running and responsive.
@app.get("/health")
def health():
    return {"status": "ok"}

# Chat endpoint to handle user queries. Validates the query, processes it using the handle_query function, 
# and returns a structured response.
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

# Run the FastAPI app using Uvicorn when the script is executed directly.
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
