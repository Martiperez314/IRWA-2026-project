"""
Part 4: baseline RAG vs improved RAG on the same queries (evidence for the report).

For every query it runs our search engine once and asks the LLM twice:
  - baseline: the template prompt with PID + title of the first 20 results (no grouping);
  - improved: our prompt with the metadata of the top 8 grouped results (myapp/generation/rag.py).
It writes project_progress/part_4/rag_comparison.md with both answers, what each prompt contained,
the PIDs each answer cites and whether any cited PID does not exist in the results (hallucination).

Needs a valid GROQ_API_KEY in .env. Run from the repository root:
    python project_progress/part_4/rag_comparison.py
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from myapp.generation.rag import PID_PATTERN, RAGGenerator  # noqa: E402
from myapp.search.search_engine import SearchEngine, SearchFilters  # noqa: E402

QUERIES = [
    # (query, what it tests)
    ("men running sports shoes", "gender: women's running shoes are also AND matches"),
    ("women cotton printed kurta", "product type: an unstitched kurta fabric matches every word"),
    ("men black polo tshirt under 500", "price limit written in the query"),
    ("women winter hooded jacket", "attributes: hooded, winter"),
    ("men slim jeans blue", "many identical listings (duplicates)"),
    ("red silk saree", "no good product: no sarees in the catalogue (partial match only)"),
    ("iphone case", "no good product: only the word 'case' matches (pillow cases...)"),
    ("smartwatch", "no results at all: the improved version does not call the LLM"),
]


def cited(text, pids):
    found = list(dict.fromkeys(PID_PATTERN.findall(text or "")))
    return found, [p for p in found if p not in pids]


def main():
    if not os.environ.get("GROQ_API_KEY", "").startswith("gsk_"):
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    if not os.environ.get("GROQ_API_KEY", "").startswith("gsk_"):
        sys.exit("Set a valid GROQ_API_KEY (starts with gsk_) in .env first: https://console.groq.com/keys")

    engine = SearchEngine.from_files(ROOT / "data" / "processed_corpus.pkl",
                                     ROOT / "data" / "fashion_products_dataset.json")
    rag = RAGGenerator()
    lines = ["# RAG comparison: baseline vs improved", "",
             f"Model: `{rag.model_name}` · generated {time.strftime('%Y-%m-%d %H:%M')}", ""]
    summary = []
    for query, purpose in QUERIES:
        print("Query:", query)
        baseline_results = engine.search(query, filters=SearchFilters(group_duplicates=False), page_size=20).results
        improved_response = engine.top_results(query, 8)

        t = time.time()
        baseline = rag.generate_response(query, baseline_results)
        t_base = time.time() - t
        t = time.time()
        improved = rag.generate_improved(query, improved_response, engine.get_document)
        t_imp = time.time() - t

        base_pids, base_bad = cited(baseline, [r.pid for r in baseline_results])
        distinct_titles = len({r.title for r in baseline_results})
        lines += [f"## {query}", "", f"*Tests:* {purpose}", "",
                  f"- Search: mode `{improved_response.mode}`, {improved_response.total} results after grouping"
                  + (f", price limit {improved_response.price_from_query}" if improved_response.price_from_query else ""),
                  f"- Baseline context: {len(baseline_results)} products (PID + title only), "
                  f"{distinct_titles} distinct titles",
                  f"- Improved context: {len(improved_response.results)} grouped products with metadata", "",
                  f"### Baseline ({t_base:.1f} s)", "", "```", (baseline or "").strip(), "```",
                  f"Cited PIDs: {len(base_pids)} · not in the results: {base_bad or 'none'}", "",
                  f"### Improved ({t_imp:.1f} s) - status `{improved['status']}`", "", "```",
                  improved["text"].strip(), "```",
                  f"Cited PIDs: {len(improved['pids'])} · removed as invented: {improved['invalid_pids'] or 'none'}", ""]
        summary.append((query, len(base_pids), len(base_bad), improved["status"], len(improved["invalid_pids"])))
        time.sleep(1)  # stay under the free-tier rate limit

    lines += ["## Summary", "", "| Query | Baseline PIDs | Baseline invented | Improved status | Improved invented |",
              "|---|---|---|---|---|"]
    lines += [f"| {q} | {b} | {bb} | {s} | {ib} |" for q, b, bb, s, ib in summary]
    out = Path(__file__).with_name("rag_comparison.md")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Written", out)


if __name__ == "__main__":
    main()
