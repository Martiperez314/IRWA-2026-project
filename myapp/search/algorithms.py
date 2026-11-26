import math
import re
from collections import Counter, defaultdict

from myapp.search.preprocessing import preprocess_text


# 1.1. Build inverted index

def create_index(corpus, field="all_tokens"):
    """
    Inverted index: for every term, the products that contain it and how many times (tf).
    {'sweatshirt': {'SWSFFVKBCQG5FHPF': 2, 'SWSFJY5ZFHQ7HXKW': 1, ...}, ...}
    """
    index = defaultdict(dict)
    for pid, tokens in zip(corpus["pid"], corpus[field]):
        for term, tf in Counter(tokens).items():
            index[term][pid] = tf
    return dict(index)


def conjunctive_search(query_terms, index):
    """
    AND query: only the products that contain ALL the query terms.
    ['men', 'slim', 'jean'] -> products in the lists of 'men' AND 'slim' AND 'jean'
    """
    if not query_terms:
        return set()
    postings = [set(index.get(term, {})) for term in query_terms]
    return set.intersection(*postings)


# 1.3. Rank your results: TF-IDF

def tf_weight(tf):
    """Log-scaled term frequency: 1 occurrence -> 1, 10 occurrences -> 3.3 (not 10)."""
    return 1 + math.log(tf) if tf > 0 else 0.0


def compute_idf(index, n_docs):
    """idf(t) = log(N / df(t)): rare terms get a high weight, very common terms a low one."""
    return {term: math.log(n_docs / len(postings)) for term, postings in index.items()}


def compute_doc_norms(index, idf):
    """Length of each product's TF-IDF vector (used to normalise the cosine similarity)."""
    norms = defaultdict(float)
    for term, postings in index.items():
        for pid, tf in postings.items():
            norms[pid] += (tf_weight(tf) * idf[term]) ** 2
    return {pid: math.sqrt(value) for pid, value in norms.items()}


def rank_tfidf(query_terms, docs, index, idf, doc_norms):
    """
    Cosine similarity between the query and each product (both as TF-IDF vectors).
    Returns [(pid, score), ...] sorted from best to worst.
    """
    query_counts = Counter(t for t in query_terms if t in index)
    query_weights = {t: tf_weight(c) * idf[t] for t, c in query_counts.items()}
    query_norm = math.sqrt(sum(w ** 2 for w in query_weights.values()))

    scores = {}
    for pid in docs:
        dot = sum(w * tf_weight(index[t][pid]) * idf[t] for t, w in query_weights.items())
        denominator = query_norm * doc_norms.get(pid, 0.0)
        scores[pid] = dot / denominator if denominator > 0 else 0.0

    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def search_in_corpus(query, index, idf, doc_norms, top_k=None):
    """
    Full search: pre-process the query (same function as the documents) -> AND search -> TF-IDF ranking.
    Returns [(pid, score), ...]; top_k=None returns all the matching products.
    """
    query_terms = preprocess_text(query)
    docs = conjunctive_search(query_terms, index)
    ranking = rank_tfidf(query_terms, docs, index, idf, doc_norms)
    return ranking[:top_k] if top_k else ranking


# =============================================================================
# Part 3: Ranking & Filtering
# The AND search (conjunctive_search) is the same for every ranking method:
# only the order of the matching products changes.
# =============================================================================

# 1.b BM25

def compute_doc_lengths(corpus, field="all_tokens"):
    """|d| = number of terms of each product (BM25 compares it with the average length)."""
    return dict(zip(corpus["pid"], corpus[field].map(len)))


def compute_bm25_idf(index, n_docs):
    """
    BM25 idf: log(1 + (N - df + 0.5) / (df + 0.5)).
    Same idea as log(N / df), but the +1 keeps it positive even for terms in almost every product.
    """
    return {term: math.log(1 + (n_docs - len(postings) + 0.5) / (len(postings) + 0.5))
            for term, postings in index.items()}


def rank_bm25(query_terms, docs, index, bm25_idf, doc_lengths, k1=1.2, b=0.75, avg_len=None):
    """
    BM25 (Okapi): score(q, d) = sum over query terms of idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * |d| / avg|d|))
    - k1 limits how much repeating a term helps (tf saturates).
    - b controls how much long products are penalised (b = 0: no length normalisation, b = 1: full).
    Each distinct query term is counted once. Returns [(pid, score), ...] from best to worst.
    avg_len: average product length; pass it precomputed (web app) to avoid summing 28k lengths per query.
    """
    if avg_len is None:
        avg_len = sum(doc_lengths.values()) / len(doc_lengths)
    terms = [t for t in dict.fromkeys(query_terms) if t in index]
    scores = {}
    for pid in docs:
        length_norm = k1 * (1 - b + b * doc_lengths[pid] / avg_len)
        score = 0.0
        for t in terms:
            tf = index[t].get(pid, 0)
            score += bm25_idf[t] * tf * (k1 + 1) / (tf + length_norm)
        scores[pid] = score
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def search_bm25(query, index, bm25_idf, doc_lengths, top_k=None, k1=1.2, b=0.75):
    """Pre-process the query -> AND search -> BM25 ranking."""
    query_terms = preprocess_text(query)
    docs = conjunctive_search(query_terms, index)
    ranking = rank_bm25(query_terms, docs, index, bm25_idf, doc_lengths, k1, b)
    return ranking[:top_k] if top_k else ranking


def search_tfidf(query, index, idf, doc_norms, top_k=None):
    """Same as search_in_corpus (Part 2): AND search -> TF-IDF + cosine. New name for symmetry."""
    return search_in_corpus(query, index, idf, doc_norms, top_k)


# 1.c Our score: text relevance (BM25) + title match + numeric fields + stock + gender

# Words that tell who a product is for (already pre-processed: "boys" -> "boy").
GENDER_TERMS = {"men": "men", "women": "women", "boy": "boy", "boys": "boy",
                "girl": "girl", "girls": "girl", "unisex": "unisex"}

# Weights of our score (see rank_our_score). Text relevance has weight 1.
OUR_SCORE_WEIGHTS = {
    "title": 0.3,             # bonus for query terms that appear in the title
    "rating": 0.1,            # bonus / penalty for a good / bad average rating
    "discount": 0.05,         # small bonus for a bigger discount
    "out_of_stock": 0.5,      # the score is multiplied by this if the product is out of stock
    "gender_mismatch": 0.5,   # ... and by this if the product is for another gender than the query
}


def product_gender(title_tokens, ideal_for):
    """
    Who the product is for, from the 'Ideal For' detail and the title.
    ['solid', 'women', 'track', 'pant'], 'Women, Girls' -> {'women', 'girl'}
    """
    words = set(title_tokens) | set(re.findall(r"[a-z]+", str(ideal_for).lower()))
    return {GENDER_TERMS[w] for w in words if w in GENDER_TERMS}


def query_gender(query_terms):
    """Gender asked for in the query: ['men', 'run', 'sport', 'shoe'] -> {'men'} (empty if none)."""
    return {GENDER_TERMS[t] for t in query_terms if t in ("men", "women")}


def gender_mismatch(q_gender, p_gender):
    """True if the query asks for a gender and the product is clearly for another one (not unisex)."""
    return bool(q_gender and p_gender and "unisex" not in p_gender and not (q_gender & p_gender))


def build_product_features(corpus):
    """The fields our score needs, for every product (read once from the processed corpus)."""
    features = {}
    columns = ["pid", "average_rating", "discount", "out_of_stock", "title_tokens", "details_dict"]
    for pid, rating, discount, out_of_stock, title_tokens, details in corpus[columns].itertuples(index=False):
        features[pid] = {
            "rating": None if math.isnan(rating) else float(rating),   # NaN = no rating (has_rating False)
            "discount": float(discount),
            "out_of_stock": bool(out_of_stock),
            "title_terms": set(title_tokens),
            "gender": product_gender(title_tokens, details.get("Ideal For", "")),
        }
    return features


def our_score_components(query_terms, docs, index, bm25_idf, doc_lengths, features, weights=None, avg_len=None):
    """
    Every part of our score for each matching product (useful to explain a ranking):
      text     = BM25 / best BM25 of this query, in (0, 1]
      title    = share of the (distinct) query terms that appear in the title, in [0, 1]
      rating   = (rating - 3) / 2, in [-1, 1]; 0 (neutral) when the product has no rating
      discount = discount / 100, in [0, 0.87]
      score    = (text + w_title*title + w_rating*rating + w_discount*discount)
                 * w_out_of_stock (if out of stock) * w_gender_mismatch (if the gender does not match)
    """
    w = {**OUR_SCORE_WEIGHTS, **(weights or {})}
    bm25 = rank_bm25(query_terms, docs, index, bm25_idf, doc_lengths, avg_len=avg_len)
    if not bm25:
        return []
    best = bm25[0][1] or 1.0
    q_terms = set(query_terms)
    q_gender = query_gender(query_terms)

    rows = []
    for pid, bm25_score in bm25:
        f = features[pid]
        text = bm25_score / best
        title = len(q_terms & f["title_terms"]) / len(q_terms)
        rating = (f["rating"] - 3) / 2 if f["rating"] is not None else 0.0
        discount = f["discount"] / 100
        mismatch = gender_mismatch(q_gender, f["gender"])
        score = text + w["title"] * title + w["rating"] * rating + w["discount"] * discount
        if f["out_of_stock"]:
            score *= w["out_of_stock"]
        if mismatch:
            score *= w["gender_mismatch"]
        rows.append({"pid": pid, "score": score, "text": text, "title": title, "rating": rating,
                     "discount": discount, "out_of_stock": f["out_of_stock"], "gender_mismatch": mismatch})
    return sorted(rows, key=lambda r: (-r["score"], r["pid"]))


def rank_our_score(query_terms, docs, index, bm25_idf, doc_lengths, features, weights=None):
    """Our score as a ranking: [(pid, score), ...] from best to worst."""
    rows = our_score_components(query_terms, docs, index, bm25_idf, doc_lengths, features, weights)
    return [(r["pid"], r["score"]) for r in rows]


def search_our_score(query, index, bm25_idf, doc_lengths, features, top_k=None, weights=None):
    """Pre-process the query -> AND search -> our score."""
    query_terms = preprocess_text(query)
    docs = conjunctive_search(query_terms, index)
    ranking = rank_our_score(query_terms, docs, index, bm25_idf, doc_lengths, features, weights)
    return ranking[:top_k] if top_k else ranking


# Filtering: one result per group of identical products

def deduplicate(ranking, corpus_by_pid, keys=("title", "brand", "description")):
    """
    Keep only the best-ranked product of each group of identical products (same title, brand
    and description: the same item listed several times). The order is not changed.
    """
    seen, result = set(), []
    for pid, score in ranking:
        key = tuple(str(corpus_by_pid.at[pid, k]) for k in keys)
        if key not in seen:
            seen.add(key)
            result.append((pid, score))
    return result
