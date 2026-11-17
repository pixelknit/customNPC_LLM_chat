# Some cool character — your custom NPC chat app



https://github.com/user-attachments/assets/49017c1e-17db-496a-8f59-75c4d49c2b4b



A minimal FastAPI server that serves a one-page chat UI. You type, press Send, and a
custom NPC replies in character. The LLM behind the counter can be a
**local model (via Ollama)** or the **Claude API** — flip one line in `.env`.

```
repo_directory/
├── app.py              FastAPI server, the two backends, and the system prompt ("the rules")
├── static/index.html   The entire UI (HTML + CSS + JS in one file) it's all under 1 file for now
├── requirements.txt
└── .env.example        Template — copy to .env
```

## Setup

```bash
cd <cloned_repo_dir>

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
```

Then pick a backend below.

---

### Option A — local model with Ollama (default)

No API key, nothing leaves your machine.

```bash
brew install ollama
ollama serve                 # leave running in its own terminal
ollama pull qwen2.5:14b      # ~9 GB. Be mindful of your vram 
```

Other models worth trying (set `LOCAL_MODEL` in `.env` to match what you pulled):

| Model         | Size  | Notes |
| `llama3.1:8b` | ~5 GB | fastest, still solid |
| `qwen2.5:14b` | ~9 GB | default — good balance |
| `gemma3:27b` / `qwen2.5:32b` | ~18–20 GB | noticeably better writing, comfortable on 64-ish GB |

`.env` stays at its defaults (`USE_LOCAL=true`).

Any OpenAI-compatible server works — LM Studio, `llama-server`, `mlx_lm.server`. Just
point `LOCAL_BASE_URL` at it.

---

### Option B — Claude API

Needs **Python 3.10+** and an API key from https://console.anthropic.com/

```bash
# uncomment the `anthropic>=1.0` line in requirements.txt, then:
pip install -r requirements.txt
```

In `.env` set:

```
USE_LOCAL=false
ANTHROPIC_API_KEY=sk-ant-...your real key...
```

---

## Run

```bash
uvicorn app:app --reload
```

Open http://127.0.0.1:8000. The subtitle shows which model is answering.

## How it works

1. The browser keeps the whole conversation in a JavaScript array (`history`).
2. On Send it POSTs `{ message, history }` to `/api/chat`.
3. `app.py` prepends `SYSTEM_PROMPT` (the character rules) and calls whichever backend
   `USE_LOCAL` selects — `complete_local()` (OpenAI SDK → Ollama) or `complete_claude()`.
4. The page appends the reply and adds both turns to `history`.

Both APIs are stateless, so the full history is resent every turn — that's how the
character "remembers" your earlier offers.

## Customising

- **Change the character:** edit `SYSTEM_PROMPT` in `app.py`.
- **Change the local model:** `ollama pull <name>`, then set `LOCAL_MODEL` in `.env`.
- **Longer replies:** raise `MAX_TOKENS` in `app.py`.

## Possible next steps

- **Stream the reply token-by-token** for a live "typing" effect (`stream=True` on the
  OpenAI call / `client.messages.stream(...)` for Claude, plus a `StreamingResponse`).
- **Persist conversations** server-side (SQLite) instead of in the browser.
- **Deploy:** `uvicorn app:app --host 0.0.0.0 --port 8000`.
