# 🔎 Entity Scraper

A bilingual (English / العربية) web application that takes a search request about
**companies, institutions, schools, academies, universities, or any other
entity** (e.g. *real estate companies in Riyadh*), finds the relevant websites,
and automatically extracts:

- Entity / organisation **name**
- **Phone numbers** (Saudi `+966` and international formats)
- **Emails**
- **People** and their **positions** (CEO, Director, Founder, مدير, …)
- **Address**, **description**, and **social media** links

Results are stored in a local **SQLite database** *and* exported as **JSON files**.

---

## ✨ Features

| | |
|---|---|
| 🌐 Web UI | Clean, professional Flask interface — runs in your browser |
| 🗣️ Bilingual | Full English / Arabic UI with automatic RTL layout |
| 🔍 Smart search | Query-aware relevance scoring, safety filtering, free **DuckDuckGo**, optional **Google API** / **SerpAPI** keys |
| 🤖 Optional LLM assist | Uses an OpenAI-compatible model when a key is supplied; otherwise stays fully rule-based |
| 🕷️ Deep scrape | Visits the homepage **plus** contact / about / team pages |
| 🧠 Extraction | schema.org JSON-LD + heuristics for people, phones, emails |
| 💾 Storage | SQLite database (`data/entities.db`) + JSON (`data/json/`) |
| 📊 History | Browse, re-open, export, and delete past searches |
| ⚡ Live progress | Real-time progress bar while sites are scraped |

---

## 🚀 Quick start (Windows)

```powershell
# 1. From the project folder, create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) copy the config template
copy .env.example .env

# 4. Run the app
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

> Tip: you can also just double-click **`run.bat`** — it does steps 1–4 for you.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

---

## 🔑 Optional: better search results with API keys

Out of the box the app uses **free DuckDuckGo search** (no key needed).
For higher-quality / higher-volume results, add keys to a `.env` file:

```ini
# Use Google Programmable Search
SEARCH_BACKEND=google
GOOGLE_API_KEY=your_key
GOOGLE_CSE_ID=your_cse_id

# ...or SerpAPI
SEARCH_BACKEND=serpapi
SERPAPI_KEY=your_key
```

If a configured backend fails for any reason, the app automatically falls back
to DuckDuckGo.

---

## 🤖 Optional: LLM assist at each useful stage

The core pipeline works without any LLM key. If you provide an OpenAI-compatible
API key, the app adds LLM help after the deterministic steps:

| Stage | What the LLM can do |
|---|---|
| Search | Rank/filter raw search results and generate backup search queries if the first search is weak |
| Scrape | Pick useful internal pages when keyword matching misses contact/about/team links |
| Extract | Read visible page text as a fallback to find names, positions, phones, emails, addresses, and social links |
| Normalize | Clean the final merged record, remove duplicates, and standardize people/position fields |

Add this to `.env`:

```ini
LLM_ENABLED=true
OPENAI_API_KEY=your_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
```

For another OpenAI-compatible provider, set `LLM_API_KEY`, `LLM_BASE_URL`, and
`LLM_MODEL`. If no key is present or a model call fails, the app silently keeps
the normal rule-based result.

---

## 🗂️ How it works

```
        ┌──────────┐     ┌───────────┐     ┌─────────────┐     ┌────────────┐
query → │  search  │ →   │  scraper  │ →   │  extractor  │ →   │  storage   │
        │ + LLM?   │     │ + LLM?    │     │ + LLM?      │     │ DB + JSON  │
        └──────────┘     └───────────┘     └─────────────┘     └────────────┘
```

1. **search** (`core/search.py`, `core/safety.py`) — generates precise
   official-site query variants, searches configured backends, blocks unsafe
   content, scores candidates against the actual query, and de-duplicates by
   domain.
2. **scraper** (`core/scraper.py`) — fetches the homepage and discovers
   contact / about / team pages (English + Arabic keywords). Respects
   `robots.txt` by default.
3. **extractor** (`core/extractor.py`) — pulls out name, emails, phones,
   address, social links, and people + positions. Optional LLM extraction fills
   gaps from visible text only.
4. **validation + storage** (`core/pipeline.py`, `core/database.py`,
   `core/exporter.py`) — rejects low-relevance scraped records, optionally asks
   the LLM for a semantic relevance check, saves accepted records to SQLite, and
   writes a JSON file per search under `data/json/`.

The whole pipeline runs in a background thread so the UI stays responsive and
shows live progress.

---

## ⚙️ Configuration reference (`.env`)

| Variable | Default | Description |
|---|---|---|
| `SEARCH_BACKEND` | `duckduckgo` | `duckduckgo` \| `google` \| `serpapi` |
| `GOOGLE_API_KEY` / `GOOGLE_CSE_ID` | — | Google Programmable Search |
| `SERPAPI_KEY` | — | SerpAPI key |
| `LLM_ENABLED` | `true` | Enables LLM assist when a key is present |
| `OPENAI_API_KEY` / `LLM_API_KEY` | — | Optional OpenAI-compatible model key |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API base URL |
| `LLM_MODEL` | `gpt-4.1-mini` | Model used for optional assists |
| `LLM_MAX_PAGE_CHARS` | `9000` | Max visible page text sent per page |
| `DEFAULT_REGION` | `SA` | ISO country for phone parsing & search bias |
| `MAX_PAGES_PER_SITE` | `6` | Pages crawled per website |
| `REQUEST_TIMEOUT` | `15` | HTTP timeout (seconds) |
| `REQUEST_DELAY` | `0.5` | Delay between requests to one site |
| `RESPECT_ROBOTS` | `true` | Obey `robots.txt` |

---

## 📦 Project layout

```
entity-scraper/
├── app.py                 # Flask app + routes
├── config.py              # Settings (env-driven)
├── requirements.txt
├── .env.example
├── core/
│   ├── search.py          # Web search backends
│   ├── scraper.py         # Page fetching + crawling
│   ├── extractor.py       # Data extraction (people, phones, emails…)
│   ├── llm.py             # Optional OpenAI-compatible LLM assist layer
│   ├── database.py        # SQLite layer
│   ├── exporter.py        # JSON export
│   └── pipeline.py        # Orchestration (search→scrape→store)
├── templates/             # HTML (base, index, results, history)
├── static/                # CSS + JS (bilingual UI)
└── data/                  # SQLite DB + JSON exports (auto-created)
```

---

## ⚠️ Responsible use

This tool is for collecting **publicly available** business contact
information. Please:

- Respect each website's `robots.txt` and terms of service (enabled by default).
- Keep request volume polite (`REQUEST_DELAY`).
- Comply with applicable data-protection / privacy laws when storing and using
  personal data (names, emails, phone numbers).
