# Part 4 – RAG, User Interface and Web Analytics

The web application is at the root of the repository (`web_app.py`, `templates/`, `static/`, `myapp/`).
This folder has the scripts and results that support the report.

| File | What it is |
|---|---|
| `simulate_traffic.py` | Sends simulated visits (real HTTP requests) to the running app, to fill the dashboard |
| `rag_comparison.py` | Runs the baseline and the improved RAG on the same queries and writes `rag_comparison.md` |
| `rag_comparison.md` | Output of `rag_comparison.py` *(created when you run it)* |

## How to run the web app

1. Environment set-up of the main `README.md` (virtualenv + `pip install -r requirements.txt`). No new packages
   are needed for Part 4.
2. Put `fashion_products_dataset.json` in `data/`. The app loads `data/processed_corpus.pkl` from Part 1, or
   rebuilds it from the JSON the first time (about 30 s).
3. Create the file `.env` at the root of the repository (it is git-ignored):
   ```
   SECRET_KEY = "any-long-random-text"
   DEBUG = True
   SESSION_COOKIE_NAME = "IRWA_SEARCH_ENGINE"
   DATA_FILE_PATH = "data/fashion_products_dataset.json"
   GROQ_API_KEY = "gsk_..."              # free key: https://console.groq.com/keys
   GROQ_MODEL = "openai/gpt-oss-20b"
   ```
   Without a valid `GROQ_API_KEY` everything works except the AI summary, which shows a "RAG is not available" message.
4. From the root of the repository:
   ```bash
   python web_app.py
   ```
   and open <http://localhost:8088>. The search engine is ready in about 1–2 seconds.
5. Optional, to fill the dashboard with simulated visits (with the app running, in a second terminal):
   ```bash
   python project_progress/part_4/simulate_traffic.py --visitors 40
   ```
   Simulated sessions are marked as such; the dashboard can hide them ("Show only real visits").
   It sends its requests to `http://127.0.0.1:8088` (on Windows, `localhost` first tries IPv6 and waits about
   2 s per request, so use the numeric address).
6. Optional, the RAG comparison for the report (needs the Groq key; about 1 minute):
   ```bash
   python project_progress/part_4/rag_comparison.py
   ```

All the analytics are kept **in memory**: they are lost when the app stops. `/analytics/export` downloads them as JSON.

## Pages

| URL | Page |
|---|---|
| `/` | Search page: central search box and example queries |
| `/search?q=...` | Results: filters, AI summary, results with title, description, price, discount, rating, stock, brand, link to the original website, pagination |
| `/doc_details?pid=...` | Product page: every field of the corpus (all `product_details`, seller, category, images...) |
| `/dashboard` | Analytics dashboard: key indicators and explained charts |
| `/stats` | The analytics tables themselves (data model), last rows of each |
| `/analytics/export` | All analytics tables as a JSON file |
| `/summary`, `/out`, `/track/dwell` | Internal: AI summary (loaded by the results page), click on the original website, dwell time |

## What is where

| Statement point | Where | What |
|---|---|---|
| Search function | `myapp/search/search_engine.py` · `SearchEngine.search(query, search_id, filters, page, page_size)` | Built once at start-up; returns a `SearchResponse` |
| Algorithms (optimised for the web) | same file + `algorithms.py` | Our Part 3 score; AND with a **fallback** to the products with most of the words; **grouping of identical listings**; **"did you mean"** for misspelled words; **price limits read from the query** ("under 500"); filters and sorting; ranking cached per query; precomputed average length (BM25) |
| Results / details pages | `templates/results.html`, `templates/doc_details.html` | |
| RAG | `myapp/generation/rag.py` | `generate_response` = template baseline; `generate_improved` = our version (3 improvements, see the module docstring) |
| Analytics | `myapp/analytics/analytics_data.py`, hooks in `web_app.py` | Star schema in memory, dashboard data |
| Dashboard charts | `templates/dashboard.html`, `static/js/charts.js` | Small SVG charts, no external library (works offline) |

## Analytics: data model and definitions

Star schema (in memory): three **fact** tables point to the **sessions** dimension; clicks also point to the
query and to the product (the corpus is the product dimension).

| Table | One row per | Main columns |
|---|---|---|
| `sessions` (dimension) | physical session of a visitor | session_id, visitor_id, start, last_seen, ip, browser, os, device, country/city (local network), simulated, counters |
| `requests` (fact) | HTTP request (static files excluded) | session_id, time, method, path, endpoint, status, response time, referrer |
| `queries` (fact) | new search (pages and filters of the same query keep its id) | session_id, text, words, processed terms, results, mode (all/partial/none), search time, order in the session, mission, research mission, filters used, pages viewed |
| `clicks` (fact) | click on a result | session_id, query_id, pid, rank, time, kind (details/external), dwell time and how it was measured |

* **Visitor**: a random id in a permanent cookie (one year), so a returning browser is recognised.
* **Physical session (sit-down)**: ends after 30 minutes without requests.
* **Mission (logical session)**: a query continues the mission of the previous query of the session if they share a
  term (gender words such as *men*/*women* are ignored); otherwise it starts a new mission.
* **Research mission**: a mission that continues a mission of the same visitor from an *earlier* session (shared term).
* **Dwell time**: the product page measures how long it was visible and sends it with `navigator.sendBeacon` when the
  user leaves it (back to the results, another tab, closing). If the beacon does not arrive, the time until the next
  page request of the session is used.
* **Clicks on the original website** go through `/out`, which stores the click and redirects (only to the product's own URL).
* **Country/city** (optional bonus): local IPs are labelled "Local network"; a lookup function for public IPs can be
  passed to `AnalyticsData(geo_lookup=...)` (not enabled, because it needs an external service).
