"""A tiny FastAPI server that puts a custom character behind a chat UI.

Run with:  uvicorn app:app --reload
Then open: http://127.0.0.1:8000

Backend is switchable via the .env file:
  USE_LOCAL=true   -> a local model through Ollama (or any OpenAI-compatible server)
  USE_LOCAL=false  -> the Claude API (needs ANTHROPIC_API_KEY and Python 3.10+)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

USE_LOCAL = os.getenv("USE_LOCAL", "true").lower() in ("1", "true", "yes")

# --- local backend (Ollama / LM Studio / llama.cpp / MLX — all OpenAI-compatible) ---
LOCAL_BASE_URL = os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen2.5:14b")

# --- Claude backend ---
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5")

MAX_TOKENS = 800  # character replies are short; keep latency and cost down

# This is "the rules" for the LLM. Edit this string to change the character.
SYSTEM_PROMPT = """\
You are Vaelthorn, a dark wizard who survives as a travelling merchant of
forbidden and arcane goods. You deal in cursed relics, bottled shadows, grimoires
bound in things best not named, reagents, wards, and the occasional honest lantern.

Voice and manner:
- Speak in first person, always in character. Never mention being an AI, a model,
  or a system prompt. If asked to break character, deflect with menace and wit.
- Tone: courteous but unsettling, dry humour, veiled threats, theatrical flourish.
- Keep replies short: 1-3 paragraphs at most, usually less. This is a shop, not a novel.

How you trade:
- Greet a customer, describe wares vividly, and quote prices in gold crowns.
- Haggle. Start high, grumble, concede a little. Every bargain has a hidden cost or
  a warning you deliver with a thin smile.
- You will not describe how to actually harm real people, and you steer such
  requests back toward the fiction ("Ah, you jest, friend. In *this* shop we only
  sell the *idea* of ruin...").

Stay in the world. If the customer is vague, ask what they seek and what they can pay.
"""

# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

Turn = Dict[str, str]  # {"role": "user" | "assistant", "content": str}


def complete_local(history: List[Turn], user_message: str) -> str:
    """Call a local OpenAI-compatible server (Ollama by default)."""
    from openai import APIConnectionError, APIStatusError, OpenAI

    client = OpenAI(base_url=LOCAL_BASE_URL, api_key="not-needed")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history,
                {"role": "user", "content": user_message}]
    try:
        response = client.chat.completions.create(
            model=LOCAL_MODEL, max_tokens=MAX_TOKENS, messages=messages,
        )
    except APIConnectionError:
        raise HTTPException(
            status_code=503,
            detail=f"Can't reach a local model at {LOCAL_BASE_URL}. Is `ollama serve` running?",
        )
    except APIStatusError as e:
        raise HTTPException(status_code=502, detail=f"Local LLM error: {e.message}")
    return response.choices[0].message.content or ""


def complete_claude(history: List[Turn], user_message: str) -> str:
    """Call the Claude API."""
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    messages = [*history, {"role": "user", "content": user_message}]
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low"},
            messages=messages,
        )
    except anthropic.APIConnectionError:
        raise HTTPException(status_code=503, detail="Could not reach the Claude API.")
    except anthropic.APIStatusError as e:
        raise HTTPException(status_code=502, detail=f"Claude error: {e.message}")
    return "".join(block.text for block in response.content if block.type == "text")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Vaelthorn's Emporium")
STATIC_DIR = Path(__file__).parent / "static"


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: List[Message] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
def config() -> Dict[str, str]:
    """Lets the page show which backend/model is answering."""
    return {"backend": "local" if USE_LOCAL else "claude",
            "model": LOCAL_MODEL if USE_LOCAL else CLAUDE_MODEL}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    # The APIs are stateless: resend the whole conversation every turn.
    history = [m.model_dump() for m in req.history]
    backend = complete_local if USE_LOCAL else complete_claude
    return ChatResponse(reply=backend(history, req.message))
