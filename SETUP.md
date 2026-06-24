# Hiring Agent — UI Setup Guide

This folder is HackerRank's open-source **Hiring Agent** (a resume-to-score
pipeline) with two additions wired in for you:

1. **A Streamlit web UI** (`app.py`) so you can upload a resume PDF in the
   browser instead of using the command line.
2. **OpenRouter support** so you can run it with your OpenRouter API key
   (the original repo only supported Ollama or Google Gemini).

---

## What you need

| Requirement | Why | Notes |
|---|---|---|
| **Python 3.11+** | Runs the whole pipeline | Check with `python3 --version` |
| **An OpenRouter API key** | Powers the LLM that parses + scores the resume | Get one at https://openrouter.ai/keys |
| **Internet connection** | Calls OpenRouter + the GitHub API | — |
| **A text-based resume PDF** | Input to score | Scanned/image-only PDFs won't parse well |
| *(optional)* **GITHUB_TOKEN** | Higher GitHub API rate limits for the enrichment step | Set in your shell env |

> Prefer to run a model **locally and free**? Install [Ollama](https://ollama.com/),
> run `ollama serve`, `ollama pull gemma3:4b`, then set `LLM_PROVIDER=ollama`
> and `DEFAULT_MODEL=gemma3:4b` in `.env`. No API key needed.

---

## Setup (3 steps)

### 1. Add your API key
Open the **`.env`** file in this folder and paste your key:

```
OPENROUTER_API_KEY=sk-or-your-key-here
```

(Optionally change `DEFAULT_MODEL` — see https://openrouter.ai/models. Append
`:free` to a model id, e.g. `google/gemini-2.0-flash-exp:free`, to avoid charges.)

### 2. Launch

**Easiest — one command:**
```bash
cd ~/Desktop/hiring-agent
./run.sh
```

**Or manually:**
```bash
cd ~/Desktop/hiring-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### 3. Use it
Your browser opens at **http://localhost:8501**. Upload a resume PDF, click
**Score resume**, and read the breakdown.

---

## How scoring works
The agent (1) extracts text from the PDF, (2) uses the LLM to parse it into
structured sections, (3) if a GitHub profile is found on the resume it fetches
repos and picks the top projects, then (4) scores four categories —
**Open Source (35)**, **Self Projects (30)**, **Production (25)**,
**Technical Skills (10)** — plus bonus points and deductions, out of 100 (+20 bonus).

In development mode (`config.py: DEVELOPMENT_MODE = True`) it also caches parsed
data under `cache/` and appends a row to `resume_evaluations.csv`.

---

## What was changed from the original repo
- `models.py` — added an `OpenRouterProvider` class + `OPENROUTER` to the provider enum.
- `prompt.py` — reads `OPENROUTER_API_KEY` / `OPENROUTER_BASE_URL`.
- `llm_utils.py` — provider selection now honors `LLM_PROVIDER` (so `openrouter` works).
- `app.py` — **new** Streamlit upload UI.
- `requirements.txt` — added `streamlit`.
- `.env` / `.env.example` — OpenRouter config.
- `run.sh` — one-command launcher.

Nothing in the original scoring logic or prompts was modified.

---

## Troubleshooting
- **Sidebar says "No API key"** → paste your key in `.env`, then restart the app.
- **"Scoring failed"** → usually a wrong `DEFAULT_MODEL` id or an out-of-credit
  OpenRouter account. Try a `:free` model or check https://openrouter.ai/models.
- **"Could not parse resume"** → the PDF is likely scanned/image-only. Use a
  text-based PDF.
- **GitHub step is slow / rate-limited** → set `GITHUB_TOKEN` in your shell.
