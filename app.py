# app.py
import json
import logging
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.orchestrator import run_agent

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
    with open("templates/index.html", "r") as f:
        return f.read()


@app.post("/research")
async def research(req: QuestionRequest):
    """
    Runs the agent and returns the full structured answer as JSON.
    """
    answer = run_agent(req.question)
    return answer.model_dump()