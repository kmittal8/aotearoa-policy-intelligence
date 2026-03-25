# Aotearoa Policy Intelligence

A plain-English interface to New Zealand's national statistics — powered by the **Anthropic Claude API** and the **Stats NZ NZ.Stat SDMX API**.

Ask questions like:
- *"What is the median income for Māori women in Wellington?"*
- *"How has Auckland's population changed across the three censuses?"*
- *"Compare home ownership rates between Māori and European in 2023."*

The assistant translates your question into live API calls against Stats NZ's 914 published dataflows and returns the answer with the actual numbers — no pre-loaded datasets, no stale snapshots.

---

## Architecture

```
User (browser)
    │
    ▼
Streamlit UI  (streamlit-ui/)
    │  Anthropic Claude API — function-calling loop
    ▼
FastAPI Tool Server  (fastapi-tool/)
    │  HTTP calls
    ▼
Stats NZ NZ.Stat SDMX API  (api.stats.govt.nz/opendata/v1)
914 live dataflows — Census, Business Demography, Income,
Housing, Iwi, Justice, LEED, and more
```

---

## Quick Start

### 1. Clone
```bash
git clone https://github.com/kmittal8/aotearoa-policy-intelligence.git
cd aotearoa-policy-intelligence
```

### 2. Start the FastAPI tool server
```bash
cd fastapi-tool
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 3. Start the Streamlit UI
```bash
cd streamlit-ui
pip install -r requirements.txt

# Optional: set your API key via env var (or enter it in the sidebar)
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY=sk-ant-...

streamlit run app.py
```

### 4. Open your browser
Go to `http://localhost:8501` and enter your **Anthropic API key** in the sidebar (if not set via `.env`).

Get your key at [console.anthropic.com](https://console.anthropic.com).

---

## Running with Docker (FastAPI tool only)
```bash
cd fastapi-tool
docker build -t aotearoa-fastapi .
docker run -p 8000:8000 aotearoa-fastapi
```

---

## Configuration

| Variable | Where | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | `streamlit-ui/.env` or sidebar | Your Anthropic API key |

No other configuration is required — Stats NZ's API is public and requires no authentication.

---

## Data Sources

- **Stats NZ NZ.Stat SDMX API** — `https://api.stats.govt.nz/opendata/v1`
  - 914 dataflows covering Census 2013/2018/2023, Business Demography, Income, Housing Tenure, Iwi, Justice, LEED, and more
  - No API key required
  - Full documentation: [stats.govt.nz/tools/api](https://www.stats.govt.nz/tools/api)

---

## Model

Uses **Claude Haiku 4.5** (`claude-haiku-4-5`) via the Anthropic API.
- Lightweight, fast, cost-effective
- Function-calling loop: the model searches dataflows, resolves dimension codes, and fetches live observations in a single conversational turn
- Pre-loaded with known dataflow IDs for the most-queried datasets (Census income, population, housing tenure) — skips search for these, keeping response times under 10 seconds

---

## Cost

- **Stats NZ API**: free, no auth
- **Anthropic API**: pay-per-token — a typical query costs ~0.01–0.05 NZD with Haiku
- **Hosting**: any cloud VM with ~1 GB RAM is sufficient; FastAPI and Streamlit run as two lightweight processes
