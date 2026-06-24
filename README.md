# ResumeRadar

Instant, explainable resume scoring. Upload a resume PDF and get a 0–100 score across
**open-source contributions, projects, production experience, and technical skills** —
with the exact fixes to rank higher. Results in ~60 seconds.

Built as a Streamlit front end over the open-source
**[hiring-agent](https://github.com/interviewstreet/hiring-agent)** scoring engine
(MIT, by HackerRank).

## What it does

- Parses the PDF and extracts structured resume sections
- Enriches with GitHub signals (profile + classified repositories)
- Produces an **explainable** score: a category breakdown with evidence, a
  "what's helping vs. hurting" view, and prioritized fixes

## Privacy

Resumes are processed in memory and are not retained. If a visitor opts in, only their
**name and email** are stored. See the in-app Privacy note.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then add your OpenRouter key
streamlit run app.py
```

Configure via `.env` locally, or Streamlit secrets in deployment:

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | LLM access (the key's credit limit is the hard cost ceiling) |
| `LLM_PROVIDER=openrouter`, `DEFAULT_MODEL=qwen/qwen3.6-plus` | provider + model |
| `SUPABASE_URL`, `SUPABASE_KEY` | *(optional)* opt-in name+email storage |
| `GITHUB_TOKEN` | *(optional)* higher GitHub API rate limits |
| `CONTACT_EMAIL` | shown in the privacy note for deletion requests |

## Credits

Scoring engine: **[hiring-agent](https://github.com/interviewstreet/hiring-agent)** (MIT).
This project is also released under the MIT License.
