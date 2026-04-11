# schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class ToolName(str, Enum):
    web_search = "web_search"
    fetch_page = "fetch_page"
    done = "DONE"


class ResearchPlan(BaseModel):
    question: str = Field(..., description="The original user question")
    steps: List[str] = Field(..., description="Ordered list of steps to answer the question")
    tools_needed: List[ToolName] = Field(..., description="Tools required to execute the plan")
    reasoning: str = Field(..., description="Why this plan will answer the question")


class ToolDecision(BaseModel):
    action: ToolName = Field(..., description="Which tool to call next, or DONE if enough info gathered")
    query: Optional[str] = Field(None, description="Search query — required if action is web_search")
    url: Optional[str] = Field(None, description="URL to fetch — required if action is fetch_page")
    reasoning: str = Field(..., description="Why this tool call is the right next step")


class Source(BaseModel):
    url: str = Field(..., description="URL of the source")
    title: str = Field(..., description="Title or best-guess label for this source")
    snippet: str = Field(..., description="Relevant excerpt or summary from this source")
    relevance_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="How relevant this source is to the question, 0 to 1"
    )


class ConfidenceLevel(str, Enum):
    high = "High"
    medium = "Medium"
    low = "Low"


class FinalAnswer(BaseModel):
    question: str = Field(..., description="The original user question")
    short_answer: str = Field(..., description="1-2 sentence direct answer to the question")
    key_findings: List[str] = Field(..., description="Bullet-style findings, each a single clear sentence")
    sources: List[Source] = Field(..., description="All sources used, filtered to only relevant ones")
    confidence_level: ConfidenceLevel = Field(..., description="Overall confidence in the answer")
    confidence_reasoning: str = Field(..., description="Why this confidence level was assigned")
    limitations: List[str] = Field(..., description="What this answer cannot cover or may get wrong")
    assumptions: List[str] = Field(..., description="Assumptions made while researching")
    suggested_next_steps: List[str] = Field(..., description="What a reader should do or investigate next")


class AgentState(BaseModel):
    question: str
    plan: Optional[ResearchPlan] = None
    gathered_info: List[dict] = Field(default_factory=list)
    iterations: int = 0
    final_answer: Optional[FinalAnswer] = None
    errors: List[str] = Field(default_factory=list)