import numpy as np

# Every metric receives `rels`: the relevance labels (1 / 0) of the results, in ranking order.
# e.g. rels = [1, 0, 1, 1, 0]  ->  1st result relevant, 2nd not, 3rd relevant, ...
# `total_relevant` = number of relevant products for the query (in the ground truth).


def ranked_labels(ranked_pids, labels):
    """
    Turn a ranking of pids into relevance labels using the ground truth {pid: 1/0}.
    Products without a label are skipped (we cannot know if they are relevant).
    """
    return [labels[pid] for pid in ranked_pids if pid in labels]


# 2.1. Evaluation metrics

def precision_at_k(rels, k):
    """P@K: fraction of the first K results that are relevant."""
    return sum(rels[:k]) / k


def recall_at_k(rels, k, total_relevant):
    """R@K: fraction of ALL relevant products that appear in the first K results."""
    return sum(rels[:k]) / total_relevant if total_relevant > 0 else 0.0


def avg_precision_at_k(rels, k, total_relevant):
    """
    AP@K: average of P@i at every position i <= K where a relevant product appears,
    divided by min(total_relevant, K). Rewards putting the relevant products first.
    """
    hits, score = 0, 0.0
    for i, rel in enumerate(rels[:k], start=1):
        if rel:
            hits += 1
            score += hits / i
    denominator = min(total_relevant, k)
    return score / denominator if denominator > 0 else 0.0


def f1_at_k(rels, k, total_relevant):
    """F1@K: harmonic mean of P@K and R@K."""
    p, r = precision_at_k(rels, k), recall_at_k(rels, k, total_relevant)
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def mean_average_precision(queries, k):
    """MAP@K: mean of AP@K over several queries. queries = [(rels, total_relevant), ...]"""
    return float(np.mean([avg_precision_at_k(rels, k, total) for rels, total in queries]))


def reciprocal_rank(rels, k):
    """RR@K: 1 / position of the first relevant result (0 if none in the first K)."""
    for i, rel in enumerate(rels[:k], start=1):
        if rel:
            return 1 / i
    return 0.0


def mean_reciprocal_rank(queries, k):
    """MRR@K: mean of RR@K over several queries. queries = [rels, ...]"""
    return float(np.mean([reciprocal_rank(rels, k) for rels in queries]))


def dcg_at_k(rels, k):
    """DCG@K: sum of rel_i / log2(i + 1) -> a relevant product counts less the lower it is."""
    return float(sum(rel / np.log2(i + 1) for i, rel in enumerate(rels[:k], start=1)))


def ndcg_at_k(rels, k, total_relevant):
    """NDCG@K: DCG of our ranking / DCG of the perfect ranking (all relevant products first)."""
    ideal = dcg_at_k([1] * total_relevant, k)
    return dcg_at_k(rels, k) / ideal if ideal > 0 else 0.0


def evaluate_query(rels, k, total_relevant):
    """All the per-query metrics in one dictionary."""
    return {
        f"P@{k}": precision_at_k(rels, k),
        f"R@{k}": recall_at_k(rels, k, total_relevant),
        f"AP@{k}": avg_precision_at_k(rels, k, total_relevant),
        f"F1@{k}": f1_at_k(rels, k, total_relevant),
        f"RR@{k}": reciprocal_rank(rels, k),
        f"NDCG@{k}": ndcg_at_k(rels, k, total_relevant),
    }
