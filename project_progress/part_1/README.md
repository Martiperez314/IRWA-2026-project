# Part 1 – Text Processing and Exploratory Data Analysis

## Contents of this folder

| File | What it is |
|---|---|
| `part_1.ipynb` | Notebook with the whole solution: data preparation (pre-processing, field decisions, check against the validation labels) and the exploratory data analysis |
| `figures/` | Figures produced by the notebook (used in the report) |
| `IRWA-2026-uXXXXXX-uXXXXXX-uXXXXXX-part-1.pdf` | Report *(added before delivery)* |

The reusable code is in **`myapp/search/preprocessing.py`** (repository root), so that Parts 2–4 use
exactly the same processing for documents and queries:

| Function | Purpose |
|---|---|
| `preprocess_text(text)` | normalize → tokenize → remove punctuation → remove stop words → stem; returns a list of terms |
| `normalize_text(text)` | HTML/URL removal, unicode → ASCII, split words glued by punctuation, unify "t-shirt", split hyphens, lowercase |
| `tokenize(text)` / `remove_stopwords(tokens)` / `stem(token)` | the individual steps of point 1 |
| `load_raw_corpus(path)` | reads the JSON dataset into a pandas DataFrame |
| `build_processed_corpus(df)` | parses numeric fields, flattens `product_details`, creates `*_tokens` columns and the merged `all_tokens` field |

## How to reproduce the results

1. Follow the environment set-up in the main `README.md` (virtualenv + `pip install -r requirements.txt`).
2. Install the spaCy English model (only needed for the named entity recognition section):
   ```bash
   python -m spacy download en_core_web_sm
   ```
3. Put `fashion_products_dataset.json` and `validation_labels.csv` in the `data/` folder at the root of the repository.
4. Open the notebook and run all cells (Kernel → Restart & Run All), e.g.
   ```bash
   jupyter notebook project_progress/part_1/part_1.ipynb
   ```
   or open it in VS Code and click **Run All**. A full run takes about 1 minute.
   The first run downloads the NLTK resources (`stopwords`, `punkt`, `punkt_tab`) automatically.

### Outputs
* `data/processed_corpus.pkl` – processed corpus (pandas DataFrame, one row per product, `pid` unchanged).
  Load it in Part 2 with `pd.read_pickle("data/processed_corpus.pkl")`. It is not committed to Git (the `data/` folder is ignored).
* `project_progress/part_1/figures/*.png` – EDA figures.

### Options
`preprocess_text(text, use_stopwords=True, use_stemming=True)` - stop word removal and stemming can be
switched off to compare results. The `product_details` keys that are indexed are listed in `USEFUL_DETAIL_KEYS`,
and the fields joined into `all_tokens` in `MERGED_FIELDS` (both at the top of `myapp/search/preprocessing.py`).
