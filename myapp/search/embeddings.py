import zlib

import numpy as np
from gensim.models import Word2Vec

from myapp.search.algorithms import conjunctive_search
from myapp.search.preprocessing import preprocess_text


# 2. word2vec + cosine similarity

def stable_hash(text):
    """Hash that is the same in every run (Python's hash() changes between runs), for reproducible vectors."""
    return zlib.crc32(text.encode("utf-8"))


def train_word2vec(corpus, field="all_tokens", vector_size=100, window=5, min_count=2,
                   epochs=20, seed=42):
    """
    Train word2vec (skip-gram) on the processed products, so the word vectors use the same
    stems as the index and the queries ('sleev', 'jean').
    - Each distinct token list is used once: 42% of the products are copies of another one,
      and repeating them would only over-train those few listings.
    - workers=1 + a fixed seed + stable_hash -> the same vectors in every run.
    """
    sentences = [list(tokens) for tokens in sorted({tuple(tokens) for tokens in corpus[field]})]
    return Word2Vec(sentences, vector_size=vector_size, window=window, min_count=min_count,
                    sg=1, epochs=epochs, seed=seed, workers=1, hashfxn=stable_hash)


def text_vector(tokens, model):
    """
    One vector for a whole text = average of the vectors of its words (as in the statement).
    Words that word2vec does not know (seen fewer than min_count times) are skipped.
    """
    vectors = [model.wv[t] for t in tokens if t in model.wv.key_to_index]
    if not vectors:
        return np.zeros(model.wv.vector_size, dtype=np.float32)
    return np.mean(vectors, axis=0)


def compute_doc_vectors(corpus, model, field="all_tokens"):
    """Vector of every product: {pid: average of its word vectors}."""
    return {pid: text_vector(tokens, model) for pid, tokens in zip(corpus["pid"], corpus[field])}


def cosine(u, v):
    """Cosine similarity between two vectors (0 if one of them is all zeros)."""
    norm = np.linalg.norm(u) * np.linalg.norm(v)
    return float(np.dot(u, v) / norm) if norm > 0 else 0.0


def rank_word2vec(query_terms, docs, model, doc_vectors):
    """Cosine similarity between the query vector and each product vector, best first."""
    query_vector = text_vector(query_terms, model)
    scores = {pid: cosine(query_vector, doc_vectors[pid]) for pid in docs}
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def search_word2vec(query, index, model, doc_vectors, top_k=20):
    """Pre-process the query -> AND search -> word2vec + cosine ranking (top 20 by default)."""
    query_terms = preprocess_text(query)
    docs = conjunctive_search(query_terms, index)
    ranking = rank_word2vec(query_terms, docs, model, doc_vectors)
    return ranking[:top_k] if top_k else ranking
