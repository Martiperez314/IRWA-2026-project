"""
Part 4: the search engine used by the web application.

The engine is built ONCE when the app starts (index, BM25 statistics, product features), and
search() is called for every query. The ranking is "our score" from Part 3 (BM25 + title, rating,
discount, stock and gender), with the changes that a real user needs:
  - AND first; if no product has all the words, fall back to the products that have most of them
    (Part 2 problem: AND is too strict) and tell the user which words were missing or unknown;
  - identical listings grouped into one result (Part 1: 42% duplicates);
  - filters (in stock, price, rating) and sorting chosen by the user;
  - the full ranking of a query is cached, so changing page or filters does not search again.
"""
import difflib
import re
import time
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import pandas as pd

from myapp.search.algorithms import (
    build_product_features, compute_bm25_idf, compute_doc_lengths, conjunctive_search,
    create_index, gender_mismatch, our_score_components, query_gender)
from myapp.search.objects import Document, ResultItem
from myapp.search.preprocessing import build_processed_corpus, load_raw_corpus, preprocess_text

# "under 500", "below rs 1,000", "less than ₹800", "upto 700" -> max price; "over 1000", "above 500" -> min price
PRICE_MAX = re.compile(r"\b(?:under|below|less than|cheaper than|upto|up to|max(?:imum)?)\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)\s*(?:rs|inr|rupees)?\b", re.I)
PRICE_MIN = re.compile(r"\b(?:over|above|more than|min(?:imum)?)\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)\s*(?:rs|inr|rupees)?\b", re.I)


def parse_price(query):
    """
    Price limits written in the query. Returns (query without them, min_price, max_price).
    "men black polo tshirt under 500" -> ("men black polo tshirt", None, 500.0)
    """
    min_price = max_price = None
    m = PRICE_MAX.search(query)
    if m:
        max_price = float(m.group(1).replace(",", ""))
        query = query[:m.start()] + " " + query[m.end():]
    m = PRICE_MIN.search(query)
    if m:
        min_price = float(m.group(1).replace(",", ""))
        query = query[:m.start()] + " " + query[m.end():]
    return " ".join(query.split()), min_price, max_price


SORT_OPTIONS = {
    "relevance": "Relevance",
    "price_asc": "Price: low to high",
    "price_desc": "Price: high to low",
    "rating": "Best rated",
    "discount": "Biggest discount",
}


@dataclass
class SearchFilters:
    """Options the user can choose on the results page (all optional)."""
    in_stock_only: bool = False
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_rating: Optional[float] = None
    sort: str = "relevance"
    group_duplicates: bool = True

    def active(self):
        """Names of the filters that are on (for the analytics)."""
        names = []
        if self.in_stock_only:
            names.append("in_stock_only")
        if self.min_price is not None:
            names.append("min_price")
        if self.max_price is not None:
            names.append("max_price")
        if self.min_rating is not None:
            names.append("min_rating")
        if self.sort != "relevance":
            names.append(f"sort:{self.sort}")
        if not self.group_duplicates:
            names.append("no_grouping")
        return names


@dataclass
class SearchResponse:
    """Everything the results page needs to know about one search."""
    query: str
    terms: List[str] = field(default_factory=list)          # processed query terms
    unknown_terms: List[str] = field(default_factory=list)  # terms that no product contains
    missing_terms: List[str] = field(default_factory=list)  # known terms the shown products may lack
    mode: str = "none"        # "all": every result has all the terms | "partial": fallback | "none": nothing found
    total: int = 0            # results after filters and grouping
    total_before_filters: int = 0
    results: List[ResultItem] = field(default_factory=list)  # the current page
    page: int = 1
    pages: int = 0
    page_size: int = 20
    took_ms: float = 0.0
    suggestion: Optional[str] = None  # "did you mean" query when a word looks misspelled
    price_from_query: Optional[str] = None  # e.g. "under ₹500", when the query had a price limit


class SearchEngine:
    """Class that implements the search engine logic (built once, used for every query)."""

    def __init__(self, corpus_df: pd.DataFrame, cache_size: int = 256):
        start = time.time()
        self.corpus = corpus_df.set_index("pid", drop=False)
        self.index = create_index(corpus_df, field="all_tokens")
        self.n_docs = len(corpus_df)
        self.bm25_idf = compute_bm25_idf(self.index, self.n_docs)
        self.doc_lengths = compute_doc_lengths(corpus_df)
        self.avg_len = sum(self.doc_lengths.values()) / len(self.doc_lengths)
        self.features = build_product_features(corpus_df)
        self.price = {pid: (None if p != p else float(p)) for pid, p in
                      zip(corpus_df["pid"], corpus_df["selling_price"])}  # NaN -> None
        # key of "identical listing" groups (same title, brand and description), computed once
        self.group_key = {pid: (str(t), str(b), str(d)) for pid, t, b, d in
                          zip(corpus_df["pid"], corpus_df["title"], corpus_df["brand"], corpus_df["description"])}
        # vocabulary for "did you mean": words of titles and product details (product words, not the
        # everyday English of descriptions), most frequent first
        product_words = {t for col in ("title_tokens", "details_tokens") for tokens in corpus_df[col] for t in tokens}
        self.vocabulary = sorted(product_words, key=lambda t: -len(self.index.get(t, {})))
        self._cache = OrderedDict()
        self._cache_size = cache_size
        self.build_seconds = time.time() - start

    @classmethod
    def from_files(cls, processed_path, raw_path):
        """Load the Part 1 processed corpus (or rebuild it from the raw JSON if missing/unreadable)."""
        try:
            corpus_df = pd.read_pickle(processed_path)
        except Exception:
            print("Processed corpus not found or unreadable: rebuilding it from the JSON (about 30 s)...")
            corpus_df = build_processed_corpus(load_raw_corpus(raw_path))
            Path(processed_path).parent.mkdir(parents=True, exist_ok=True)
            corpus_df.to_pickle(processed_path)
        return cls(corpus_df)

    # ------------------------------------------------------------------ ranking
    def rank(self, query: str):
        """
        Full ranking of a query, before filters: (terms, unknown, missing, mode, [(pid, score), ...]).
        Cached by the processed terms, so "Men's T-shirts" and "men tshirt" share the same entry.
        """
        terms = list(dict.fromkeys(preprocess_text(query)))  # distinct terms, in query order
        key = tuple(terms)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        known = [t for t in terms if t in self.index]
        unknown = [t for t in terms if t not in self.index]
        missing, ranking = [], []
        if not known:
            mode = "none"
        else:
            docs = conjunctive_search(known, self.index)
            if docs and not unknown:
                mode = "all"
                rows = our_score_components(known, docs, self.index, self.bm25_idf, self.doc_lengths,
                                            self.features, avg_len=self.avg_len)
                ranking = [(r["pid"], r["score"]) for r in rows]
            else:
                # Fallback: no product has every word. Keep the products with the most query words
                # (plus the next level if that gives fewer than 10), and multiply the score by the
                # share of words matched, so products with more of the words stay on top.
                mode = "partial"
                counts = Counter(pid for t in known for pid in self.index[t])
                best = max(counts.values())
                need = best if sum(c >= best for c in counts.values()) >= 10 or best == 1 else best - 1
                candidates = {pid for pid, c in counts.items() if c >= need}
                rows = our_score_components(known, candidates, self.index, self.bm25_idf, self.doc_lengths,
                                            self.features, avg_len=self.avg_len)
                ranking = sorted(((r["pid"], r["score"] * counts[r["pid"]] / len(terms)) for r in rows),
                                 key=lambda item: (-item[1], item[0]))
                # words that the best results do not contain
                top = [pid for pid, _ in ranking[:20]]
                missing = [t for t in known if any(pid not in self.index[t] for pid in top)]

        result = (terms, unknown, missing, mode, ranking)
        self._cache[key] = result
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return result

    # ------------------------------------------------------------------ search
    def search(self, search_query: str, search_id=None, filters: Optional[SearchFilters] = None,
               page: int = 1, page_size: int = 20) -> SearchResponse:
        """
        General search function called by the web app.
        search_query: text typed by the user | search_id: id of the query in the analytics
        filters: SearchFilters chosen on the results page | page, page_size: pagination.
        """
        start = time.time()
        filters = filters or SearchFilters()
        # price limits typed in the query become filters (a filter chosen on the page wins)
        text_query, q_min, q_max = parse_price(search_query)
        price_note = None
        if (q_min is not None or q_max is not None) and text_query:
            filters = SearchFilters(**{**filters.__dict__,
                                       "min_price": filters.min_price if filters.min_price is not None else q_min,
                                       "max_price": filters.max_price if filters.max_price is not None else q_max})
            used_min = q_min is not None and filters.min_price == q_min
            used_max = q_max is not None and filters.max_price == q_max
            price_note = " and ".join(p for p in [f"over ₹{q_min:,.0f}" if used_min else None,
                                                   f"under ₹{q_max:,.0f}" if used_max else None] if p) or None
        else:
            text_query = search_query
        terms, unknown, missing, mode, ranking = self.rank(text_query)
        response = SearchResponse(query=search_query, terms=terms, unknown_terms=unknown,
                                  missing_terms=missing, mode=mode, page_size=page_size,
                                  total_before_filters=len(ranking), suggestion=self.suggest(terms),
                                  price_from_query=price_note)

        # 1. filters chosen by the user
        kept = [(pid, score) for pid, score in ranking if self._passes(pid, filters)]

        # 2. one result per group of identical listings (the best-ranked one), counting the others
        group_sizes = Counter(self.group_key[pid] for pid, _ in kept)
        if filters.group_duplicates:
            seen, grouped = set(), []
            for pid, score in kept:
                key = self.group_key[pid]
                if key not in seen:
                    seen.add(key)
                    grouped.append((pid, score))
            kept = grouped

        # 3. sorting chosen by the user (stable: ties keep the relevance order). Out-of-stock and
        #    wrong-gender products stay after the others, as in our score (demoted, not removed).
        kept = self._sort(kept, filters.sort, query_gender(terms))

        # 4. page
        response.total = len(kept)
        response.pages = max(1, -(-len(kept) // page_size))
        response.page = min(max(1, page), response.pages)
        first = (response.page - 1) * page_size
        response.results = [
            self._result_item(pid, score, first + i + 1, search_id,
                              group_sizes[self.group_key[pid]] - 1 if filters.group_duplicates else 0)
            for i, (pid, score) in enumerate(kept[first:first + page_size])]
        response.took_ms = (time.time() - start) * 1000
        return response

    def query_terms(self, search_query: str):
        """The terms search() uses for this query (price limits removed, pre-processed, distinct)."""
        text_query = parse_price(search_query)[0] or search_query
        return self.rank(text_query)[0]

    def suggest(self, terms, rare=3):
        """
        "Did you mean": replace each unknown or very rare term (in fewer than `rare` products) by the most
        similar term of the product vocabulary that is at least 20 times more frequent and at most 1 edit
        away (2 for words longer than 5 letters). None if nothing changes.
        'jeen' (1 product) -> 'jean' (2,430); 'tshrt' (unknown) -> 'tshirt'.
        """
        corrected, changed = [], False
        for t in terms:
            df = len(self.index.get(t, {}))
            if df < rare and len(t) > 2:
                max_edits = 1 if len(t) <= 5 else 2
                options = [w for w in difflib.get_close_matches(t, self.vocabulary, n=5, cutoff=0.75)
                           if len(self.index.get(w, {})) >= max(20, 20 * df) and edit_distance(t, w) <= max_edits]
                if options:
                    best = max(options, key=lambda w: (difflib.SequenceMatcher(None, t, w).ratio(),
                                                        len(self.index[w])))
                    corrected.append(best)
                    changed = True
                    continue
            corrected.append(t)
        return " ".join(corrected) if changed else None

    def top_results(self, search_query: str, k: int = 10, filters: Optional[SearchFilters] = None):
        """The first k results (for the RAG summary), with the same filters as the results page."""
        return self.search(search_query, filters=filters, page=1, page_size=k)

    # ------------------------------------------------------------------ helpers
    def _passes(self, pid, f: SearchFilters):
        row = self.features[pid]
        price = self.price[pid]
        if f.in_stock_only and row["out_of_stock"]:
            return False
        if f.min_price is not None and (price is None or price < f.min_price):
            return False
        if f.max_price is not None and (price is None or price > f.max_price):
            return False
        if f.min_rating is not None and (row["rating"] is None or row["rating"] < f.min_rating):
            return False
        return True

    def _sort(self, ranking, sort, q_gender):
        if sort not in SORT_OPTIONS or sort == "relevance":
            return ranking

        def demoted(pid):
            f = self.features[pid]
            return f["out_of_stock"] or gender_mismatch(q_gender, f["gender"])

        def value(pid):
            f, price = self.features[pid], self.price[pid]
            if sort == "price_asc":
                return price if price is not None else float("inf")
            if sort == "price_desc":
                return -price if price is not None else float("inf")
            if sort == "rating":
                return -(f["rating"] or 0)
            return -f["discount"]  # "discount"

        return sorted(ranking, key=lambda r: (demoted(r[0]), value(r[0])))

    def _result_item(self, pid, score, rank, search_id, duplicates):
        row = self.corpus.loc[pid]
        images = row["images"] if isinstance(row["images"], list) else []
        return ResultItem(
            pid=pid, title=str(row["title"]).replace("\xa0", " "),
            description=_text(row["description"]), brand=_text(row["brand"]),
            sub_category=_text(row["sub_category"]), selling_price=_num(row["selling_price"]),
            actual_price=_num(row["actual_price"]), discount=_num(row["discount"]),
            average_rating=_num(row["average_rating"]), out_of_stock=bool(row["out_of_stock"]),
            url=_text(row["url"]), image=images[0] if images else None,
            ranking=round(float(score), 4), rank=rank, duplicates=duplicates, search_id=search_id)

    def get_document(self, pid) -> Optional[Document]:
        """All the information of one product (details page), or None if the pid does not exist."""
        if pid not in self.corpus.index:
            return None
        row = self.corpus.loc[pid]
        data = {k: row[k] for k in ["pid", "title", "description", "brand", "category",
                                     "sub_category", "product_details", "seller", "out_of_stock",
                                     "selling_price", "discount", "actual_price", "average_rating",
                                     "url", "images"]}
        data = {k: (None if _is_missing(v) else v) for k, v in data.items()}
        data["title"] = str(data["title"]).replace("\xa0", " ")
        return Document(**data)

    def suggestions(self, limit=8):
        """A few example queries for the home page (most common product types)."""
        return ["men slim jeans blue", "women cotton printed kurta", "men black polo tshirt",
                "women winter hooded jacket", "men running sports shoes", "men formal trousers"][:limit]


def edit_distance(a, b):
    """Levenshtein distance: letters to add, remove or change to turn a into b."""
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def _is_missing(v):
    return v is None or (isinstance(v, float) and v != v)


def _num(v):
    return None if _is_missing(v) else float(v)


def _text(v):
    return None if _is_missing(v) or v == "" else str(v)

