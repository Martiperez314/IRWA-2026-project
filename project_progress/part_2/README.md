# Part 2 – Indexing and Evaluation

## Contents of this folder

| File | What it is |
|---|---|
| `part_2.ipynb` | Notebook with the whole solution: inverted index, AND search, test queries, TF-IDF ranking and evaluation |
| `our_queries_labels_template.csv` | Top 20 results of each of our test queries, written by the notebook (section 2.3.a) to be labelled |
| `our_queries_labels.csv` | Our relevance judgements (1 / 0) for the test queries, same format as `validation_labels.csv` |
| `IRWA-2026-uXXXXXX-uXXXXXX-uXXXXXX-part-2.pdf` | Report *(added before delivery)* |

The reusable code is in `myapp/search/` (repository root):

| File | Functions |
|---|---|
| `algorithms.py` | 1.1 `create_index`, `conjunctive_search` · 1.3 `compute_idf`, `compute_doc_norms`, `rank_tfidf`, `search_in_corpus` |
| `evaluation.py` | 2.1 `precision_at_k`, `recall_at_k`, `avg_precision_at_k`, `f1_at_k`, `mean_average_precision`, `reciprocal_rank`, `mean_reciprocal_rank`, `dcg_at_k`, `ndcg_at_k`, `evaluate_query` |
| `preprocessing.py` | Part 1: `preprocess_text` is applied to the queries too |

## How to reproduce the results

1. Follow the environment set-up in the main `README.md` (virtualenv + `pip install -r requirements.txt`).
2. Put `fashion_products_dataset.json` and `validation_labels.csv` in the `data/` folder at the root of the repository.
3. Open `project_progress/part_2/part_2.ipynb` (VS Code or `jupyter notebook`) and click **Run All** (about 1 minute).
   It loads `data/processed_corpus.pkl` from Part 1, or rebuilds it from the raw JSON if it is missing.

### Options
* Indexed field: `create_index(corpus, field="all_tokens")` – any `*_tokens` column of Part 1 can be used.
* Number of results: `search_in_corpus(query, index, idf, doc_norms, top_k=10)`; `top_k=None` returns all matches.
* Cut-off of the metrics: `K = 10` in section 2.2.
* Test queries: the `TEST_QUERIES` dictionary in section 1.2.
