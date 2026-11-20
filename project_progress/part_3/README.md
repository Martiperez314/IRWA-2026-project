# Part 3 – Ranking & Filtering

## Contents of this folder

| File | What it is |
|---|---|
| `part_3.ipynb` | Notebook with the whole solution: TF-IDF, BM25 and our score, their comparison, and word2vec + cosine |
| `IRWA-2026-u232620-u232621-u232628-part-3.tex` | Source of the report (compile it to the PDF) |
| `IRWA-2026-u232620-u232621-u232628-part-3.pdf` | Report *(added before delivery)* |

The reusable code is in `myapp/search/` (repository root):

| File | Functions |
|---|---|
| `algorithms.py` | 1.a `search_tfidf` (Part 2 TF-IDF + cosine) · 1.b `compute_doc_lengths`, `compute_bm25_idf`, `rank_bm25`, `search_bm25` · 1.c `build_product_features`, `our_score_components`, `rank_our_score`, `search_our_score`, `OUR_SCORE_WEIGHTS` · filtering `deduplicate` |
| `embeddings.py` | 2. `train_word2vec`, `text_vector`, `compute_doc_vectors`, `rank_word2vec`, `search_word2vec` |
| `preprocessing.py`, `evaluation.py` | Parts 1 and 2 (query processing and metrics), unchanged |

All methods use the same AND search as Part 2 (`conjunctive_search`); they only change the order of the results.

## How to reproduce the results

1. Follow the environment set-up in the main `README.md`, then install the new dependency (word2vec):
   ```bash
   pip install -r requirements.txt      # or only: pip install gensim==4.4.0
   ```
2. Put `fashion_products_dataset.json` and `validation_labels.csv` in the `data/` folder at the root of the repository.
   The notebook also reads our Part 2 labels from `project_progress/part_2/our_queries_labels.csv`.
3. Open `project_progress/part_3/part_3.ipynb` (VS Code or `jupyter notebook`) and click **Run All** (about 1–2 minutes;
   training word2vec takes most of it). It loads `data/processed_corpus.pkl` from Part 1, or rebuilds it if it is missing.

### Options
* BM25 parameters: `search_bm25(..., k1=1.2, b=0.75)`.
* Weights of our score: `OUR_SCORE_WEIGHTS` in `algorithms.py`, or `search_our_score(..., weights={"title": 0.5})`.
* word2vec settings: `train_word2vec(corpus, vector_size=100, window=5, min_count=2, epochs=20, seed=42)`.
* Optional extra labels (section 4): fill `our_queries_labels_part3_template.csv`, save it as
  `our_queries_labels_part3.csv` and run the notebook again; the metrics then also use these labels.
