import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta
from json import JSONEncoder
from urllib.parse import urlencode

from dotenv import load_dotenv
from flask import (Flask, Response, abort, g, jsonify, redirect, render_template, request, session,
                   url_for)
from markupsafe import Markup, escape

from myapp.analytics.analytics_data import AnalyticsData
from myapp.generation.rag import RAGGenerator
from myapp.search.search_engine import SORT_OPTIONS, SearchEngine, SearchFilters

load_dotenv()  # take environment variables from .env


# *** for using method to_json in objects ***
def _default(self, obj):
    return getattr(obj.__class__, "to_json", _default.default)(obj)
_default.default = JSONEncoder().default
JSONEncoder.default = _default
# end lines ***for using method to_json in objects ***


# instantiate the Flask application
app = Flask(__name__)

# random 'secret_key' is used for persisting data in secure cookie
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(16)
# open browser dev tool to see the cookies
app.config["SESSION_COOKIE_NAME"] = (os.getenv("SESSION_COOKIE_NAME") or "IRWA_SEARCH_ENGINE").strip('"')
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=365)  # the visitor id survives browser restarts

# load the processed corpus (Part 1) and build the search engine once
ROOT = os.path.dirname(os.path.realpath(__file__))
RAW_PATH = os.path.join(ROOT, (os.getenv("DATA_FILE_PATH") or "data/fashion_products_dataset.json").strip('"'))
PROCESSED_PATH = os.path.join(ROOT, "data", "processed_corpus.pkl")
start = time.time()
search_engine = SearchEngine.from_files(PROCESSED_PATH, RAW_PATH)
print(f"\nSearch engine ready in {time.time() - start:.1f} s: {search_engine.n_docs} products, "
      f"{len(search_engine.index)} terms")

# instantiate our in memory persistence
analytics_data = AnalyticsData()
# instantiate RAG generator
rag_generator = RAGGenerator()

PAGE_SIZE = 20
UNTRACKED = {"static", "track_dwell", "favicon"}  # requests that are not stored as page requests


# ---------------------------------------------------------------------------------------------- helpers
def read_filters(args) -> SearchFilters:
    """Filters of the results page, from the URL (?stock=1&max_price=500&min_rating=4&sort=price_asc)."""
    def number(name):
        try:
            value = float(args.get(name, ""))
            return value if value >= 0 else None
        except ValueError:
            return None
    sort = args.get("sort", "relevance")
    return SearchFilters(in_stock_only=args.get("stock") == "1", min_price=number("min_price"),
                         max_price=number("max_price"), min_rating=number("min_rating"),
                         sort=sort if sort in SORT_OPTIONS else "relevance",
                         group_duplicates=args.get("group", "1") != "0")


def search_url(**changes):
    """URL of the current results page with some parameters changed (pagination, filters)."""
    params = {k: v for k, v in request.args.items() if v != ""}
    params.update({k: v for k, v in changes.items() if v is not None})
    for k in [k for k, v in changes.items() if v is None]:
        params.pop(k, None)
    return url_for("search") + "?" + urlencode(params)


@app.template_filter("price")
def price_filter(value):
    return "" if value is None else f"₹{value:,.0f}"


@app.template_filter("datetime_fmt")
def datetime_fmt(timestamp):
    return datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d %H:%M:%S")


@app.template_filter("summary_html")
def summary_html(text):
    """LLM answer -> safe HTML: escape everything, keep line breaks, bold labels, link cited PIDs."""
    html = str(escape(text or ""))
    html = re.sub(r"^(Summary|Best pick|Alternatives|Note):", r"<strong>\1:</strong>", html, flags=re.M)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    qid = request.args.get("qid", "")
    html = re.sub(r"\[([A-Z0-9]{16})\]",
                  lambda m: f'<a href="{url_for("doc_details", pid=m.group(1), qid=qid, src="summary")}">[{m.group(1)}]</a>',
                  html)
    return Markup(html.replace("\n", "<br>"))


# ---------------------------------------------------------------------------------------------- analytics hooks
@app.before_request
def track_start():
    """Every request: identify the visitor and the physical session (cookie) before handling it."""
    g.start = time.perf_counter()
    # static files and automatic browser probes (e.g. Chrome DevTools asks /.well-known/...) are not visits
    if request.endpoint in UNTRACKED or request.path.startswith(("/static", "/.well-known")):
        return
    session.permanent = True
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    g.analytics_session = analytics_data.get_or_create_session(
        session, ip, request.headers.get("User-Agent", ""),
        simulated=request.headers.get("X-Simulated-Traffic") == "1",
        force_new=request.headers.get("X-Simulated-New-Session") == "1")


@app.after_request
def track_end(response):
    """Every request: store it in the requests table (with its status and response time)."""
    s = getattr(g, "analytics_session", None)
    if s is not None:
        analytics_data.save_request(s.session_id, request.method, request.full_path.rstrip("?"),
                                    request.endpoint, response.status_code,
                                    (time.perf_counter() - g.start) * 1000, request.referrer)
    return response


# ---------------------------------------------------------------------------------------------- pages
@app.route('/')
def index():
    return render_template('index.html', page_title="Welcome", examples=search_engine.suggestions())


@app.route('/favicon.ico')
def favicon():
    return app.send_static_file("logo.png")


@app.route('/search', methods=['GET', 'POST'])
def search():
    """Results page. GET /search?q=... (bookmarkable; the form also works with POST as in the template)."""
    if request.method == 'POST':  # old form of the template -> same page with GET
        return redirect(url_for("search", q=request.form.get("search-query", "")))
    query = request.args.get("q", "").strip()
    if not query:
        return redirect(url_for("index"))
    filters = read_filters(request.args)
    page = request.args.get("page", "1")
    page = int(page) if page.isdigit() else 1

    # a NEW query only when the text changes; pages and filters of the same query keep its id
    qid = request.args.get("qid", "")
    known = analytics_data.queries.get(int(qid)) if qid.isdigit() else None
    is_new = known is None or known.text != query or known.session_id != g.analytics_session.session_id
    if is_new:
        terms = search_engine.query_terms(query)
        qid = analytics_data.save_query(g.analytics_session, query, terms)
    else:
        qid = known.query_id

    response = search_engine.search(query, qid, filters, page=page, page_size=PAGE_SIZE)
    analytics_data.update_query(qid, n_results=response.total if is_new else None,
                                mode=response.mode if is_new else None,
                                took_ms=response.took_ms if is_new else None,
                                filters=filters.active(), new_page=not is_new)
    session['last_search_url'] = search_url(qid=qid)
    return render_template('results.html', page_title=f"{query} - Results", response=response, query=query,
                           qid=qid, filters=filters, sort_options=SORT_OPTIONS, search_url=search_url,
                           summary_params=urlencode({**request.args, "qid": qid}))


@app.route('/summary')
def summary():
    """AI summary of the results (RAG), loaded by the results page after it is shown (it takes 1-3 s)."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"status": "no_results", "html": ""})
    filters = read_filters(request.args)
    if request.args.get("version") == "baseline":
        # baseline of the template: first 20 results, without grouping identical listings
        filters.group_duplicates = False
        results = search_engine.search(query, filters=filters, page_size=20).results
        answer = {"status": "ok", "text": rag_generator.generate_response(query, results)}
    else:
        answer = rag_generator.generate_improved(query, search_engine.top_results(query, 8, filters),
                                                 search_engine.get_document)
    if answer["text"] == rag_generator.DEFAULT_ANSWER:
        answer["status"] = "error"
    return jsonify({"status": answer["status"], "html": str(summary_html(answer["text"])),
                    "invalid_pids": answer.get("invalid_pids", [])})


@app.route('/doc_details', methods=['GET'])
def doc_details():
    """Product page: all the information of the product. A visit from the results page is a click."""
    pid = request.args.get("pid", "")
    document = search_engine.get_document(pid)
    if document is None:
        abort(404)
    qid = request.args.get("qid", "")
    rank = request.args.get("rank", "")
    click_id = None
    if request.args.get("src") in ("results", "summary"):
        click_id = analytics_data.save_click(g.analytics_session.session_id, int(qid) if qid.isdigit() else None,
                                             pid, int(rank) if rank.isdigit() else None, "details")
    return render_template('doc_details.html', page_title=document.title, doc=document, click_id=click_id,
                           back_url=session.get('last_search_url'), qid=qid, rank=rank,
                           clicks=analytics_data.fact_clicks.get(pid, 0))


@app.route('/out')
def external_link():
    """Click on the link to the original website: store it, then redirect (only to the product's own URL)."""
    pid = request.args.get("pid", "")
    document = search_engine.get_document(pid)
    if document is None or not document.url:
        abort(404)
    qid, rank = request.args.get("qid", ""), request.args.get("rank", "")
    analytics_data.save_click(g.analytics_session.session_id, int(qid) if qid.isdigit() else None,
                              pid, int(rank) if rank.isdigit() else None, "external")
    return redirect(document.url)


@app.route('/track/dwell', methods=['POST'])
def track_dwell():
    """Dwell time sent by the product page (navigator.sendBeacon) when the user leaves it."""
    try:
        data = json.loads(request.get_data(as_text=True) or "{}")
        ok = analytics_data.save_dwell(int(data.get("click_id")), session.get("session_id"),
                                       float(data.get("ms")))
    except (TypeError, ValueError):
        ok = False
    return ("", 204) if ok else ("", 400)


@app.route('/dashboard', methods=['GET'])
def dashboard():
    include_simulated = request.args.get("real_only") != "1"
    data = analytics_data.dashboard_data(titles=_title, include_simulated=include_simulated)
    return render_template('dashboard.html', page_title="Dashboard", data=data,
                           include_simulated=include_simulated)


@app.route('/stats', methods=['GET'])
def stats():
    """The analytics tables themselves (data model), last rows of each."""
    tables = analytics_data.export()
    return render_template('stats.html', page_title="Analytics data", tables=tables, titles=_title)


@app.route('/analytics/export')
def analytics_export():
    """Download all the analytics tables as JSON."""
    body = json.dumps(analytics_data.export(), indent=1, default=str)
    name = f"irwa_analytics_{datetime.now():%Y%m%d_%H%M}.json"
    return Response(body, mimetype="application/json",
                    headers={"Content-Disposition": f"attachment; filename={name}"})


def _title(pid):
    document = search_engine.get_document(pid)
    return document.title if document else pid


if __name__ == "__main__":
    debug = str(os.getenv("DEBUG", "False")).strip().lower() in ("1", "true", "yes")
    app.run(port=8088, host="0.0.0.0", threaded=False, debug=debug)
