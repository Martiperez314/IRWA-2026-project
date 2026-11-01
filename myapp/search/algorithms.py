import math
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
