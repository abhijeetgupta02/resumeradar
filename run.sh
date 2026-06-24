#!/usr/bin/env bash
# One-command launcher for the Hiring Agent Streamlit UI (macOS / Linux).
# Creates a virtual environment, installs dependencies, and starts the app.
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 not found. Install Python 3.11+ first (https://www.python.org/downloads/)."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "📦 Creating virtual environment (.venv)…"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "⬇️  Installing dependencies…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if ! grep -q "OPENROUTER_API_KEY=..*" .env 2>/dev/null; then
  echo ""
  echo "⚠️  No OpenRouter API key detected in .env."
  echo "    Open .env and paste your key after OPENROUTER_API_KEY="
  echo "    (You can still launch the app, but scoring will fail until the key is set.)"
  echo ""
fi

echo "🚀 Launching UI at http://localhost:8501  (press Ctrl+C to stop)"
streamlit run app.py
