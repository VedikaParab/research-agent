# app.py
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.orchestrator import run_agent
from sanitization import sanitize_question, is_safe_question
from config import validate_or_raise
import asyncio

validate_or_raise()

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Research Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QuestionRequest(BaseModel):
    question: str


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/research")
async def research(req: QuestionRequest):
    # sanitize_question returns (is_safe: bool, clean_question: str)
    is_safe, clean_question = sanitize_question(req.question)
    
    if not is_safe:
        raise HTTPException(status_code=400, detail="Unsafe query detected")

    # run agent in a thread so it doesn't block the async event loop
    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(None, run_agent, clean_question)

    return answer.model_dump()

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)