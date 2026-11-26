"""
Part 4: RAG (retrieval-augmented generation) summary of the search results, with a Groq LLM.

Two versions, so they can be compared (project_progress/part_4/rag_comparison.py):
  - generate_response(): the BASELINE given in the template (unchanged prompt, PID + title of 20 results).
  - generate_improved(): our improved version, with three improvements:
      1. Richer, cleaner context: the top 8 results AFTER grouping duplicates, each with brand, price,
         discount, rating, stock, the key product details and the start of the description.
      2. Grounded, query-aware prompt: use only the listed products, cite their PIDs, never invent
         facts, respect the constraints of the query (gender, colour, type, price), short fixed format,
         low temperature.
      3. "No good products" handling: no LLM call when the search found nothing; tell the model when
         the results are only a partial match; a NO_MATCH answer becomes a clear message; every PID the
         model cites is checked against the products it received (hallucination guard).
"""
import os
import re

from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env

PID_PATTERN = re.compile(r"\b[A-Z0-9]{16}\b")
DETAIL_KEYS = ["Fabric", "Color", "Ideal For", "Fit", "Sleeve", "Pattern", "Type", "Occasion",
               "Neck Type", "Closure", "Pack of"]


class RAGGenerator:

    PROMPT_TEMPLATE = """
        You are an expert product advisor helping users choose the best option from retrieved e-commerce products.

        ## Instructions:
        1. Identify the single best product that matches the user's request.
        2. Present the recommendation clearly in this format:
        - Best Product: [Product PID] [Product Name]
        - Why: [Explain in plain language why this product is the best fit, referring to specific attributes like price, features, quality, or fit to user’s needs.]
        3. If there is another product that could also work, mention it briefly as an alternative.
        4. If no product is a good fit, return ONLY this exact phrase:
        "There are no good products that fit the request based on the retrieved results."

        ## Retrieved Products:
        {retrieved_results}

        ## User Request:
        {user_query}

        ## Output Format:
        - Best Product: ...
        - Why: ...
        - Alternative (optional): ...
    """

    IMPROVED_SYSTEM = """You are a shopping assistant for a fashion e-commerce search engine.
You summarise the search results for the user and recommend products, using ONLY the products listed by
the user message. Rules:
- Never invent products, prices, ratings, materials or any other fact that is not in the list.
- Always cite a product with its PID in square brackets, e.g. [TSHFDCH4EHXXBRRC].
- Respect what the query asks for: gender (men/women), product type, colour, material and price limits.
  A product that breaks one of them is NOT a good match, even if it is in the list.
- Prefer products that are in stock and well rated; mention it when a product is out of stock or has no rating.
- If none of the products fits the query, answer exactly: NO_MATCH: <one short sentence saying why>.
- Be brief: at most 120 words, plain text, no markdown tables."""

    IMPROVED_USER = """User query: "{query}"
{match_note}
Products found (best ranked first, identical listings already grouped):
{products}

Answer in this format:
Summary: <one sentence: what kind of products were found and how well they match the query>
Best pick: [PID] <title> - <why, with price and rating>
Alternatives: [PID] <short reason>; [PID] <short reason> (only if they also fit)
Note: <only if useful: out of stock, missing sizes or words, a cheaper option...>"""

    NO_RESULTS_MESSAGE = ("No products match your search, so there is nothing to summarise. "
                          "Try fewer or more general words (for example \"men jeans\" instead of a full sentence).")
    NO_MATCH_MESSAGE = "None of the products found really fits your request"
    DEFAULT_ANSWER = "RAG is not available. Check your credentials (.env file) or account limits."

    def __init__(self, client=None, model_name=None):
        """client: an object with chat.completions.create (Groq by default; a fake one in the tests)."""
        self._client = client
        self.model_name = model_name or os.environ.get("GROQ_MODEL") or "openai/gpt-oss-20b"

    @property
    def client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=os.environ.get("GROQ_API_KEY"), timeout=20)
        return self._client

    # ------------------------------------------------------------------ baseline (template)
    def generate_response(self, user_query: str, retrieved_results: list, top_N: int = 20) -> str:
        """BASELINE from the template: PID and title of the first 20 results, generic prompt."""
        try:
            formatted_results = "\n".join(
                [f"- PID: {res.pid}, Title: {res.title}" for res in retrieved_results[:top_N]])
            prompt = self.PROMPT_TEMPLATE.format(retrieved_results=formatted_results, user_query=user_query)
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], model=self.model_name)
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Error during RAG generation: {e}")
            return self.DEFAULT_ANSWER

    # ------------------------------------------------------------------ improved
    def generate_improved(self, user_query: str, response, get_document=None, top_n: int = 8) -> dict:
        """
        IMPROVED summary.
        response: the SearchResponse of the search engine (already filtered and grouped)
        get_document: function pid -> Document, to add the product details to the context
        Returns {"status", "text", "pids", "invalid_pids", "prompt"}; status is one of
        ok / no_results / no_match / error.
        """
        results = list(response.results)[:top_n]
        # Improvement 3: nothing found -> no LLM call (no cost, no invented answer)
        if response.mode == "none" or not results:
            return {"status": "no_results", "text": self.NO_RESULTS_MESSAGE, "pids": [], "invalid_pids": [],
                    "prompt": None}

        # Improvement 1: metadata of each product
        products = "\n".join(self.describe_product(item, get_document(item.pid) if get_document else None)
                             for item in results)
        # Improvement 3: tell the model when the products do not contain every word of the query,
        # with the words as the user typed them ("saree", not the stem "sare")
        match_note = ""
        if response.mode == "partial":
            lacking = self.typed_words(user_query, response.unknown_terms + response.missing_terms)
            match_note = (f"Warning: no product contains every word of the query (missing: "
                          f"{', '.join(lacking) or 'some of the words'}). These are only partial matches. "
                          "If a missing word is the KIND of product the user wants (e.g. saree, watch, phone case), "
                          "none of these products fits: answer NO_MATCH.")
        prompt = self.IMPROVED_USER.format(query=user_query, match_note=match_note, products=products)
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name, temperature=0.2, messages=[{"role": "system", "content": self.IMPROVED_SYSTEM},
                                                                {"role": "user", "content": prompt}],
                **self._length_options(350))
            text = (completion.choices[0].message.content or "").strip()
        except Exception as e:
            print(f"Error during RAG generation: {e}")
            return {"status": "error", "text": self.DEFAULT_ANSWER, "pids": [], "invalid_pids": [],
                    "prompt": prompt}
        return self.check_answer(text, [item.pid for item in results], prompt)

    def _length_options(self, answer_tokens):
        """
        Token limit of the answer. Reasoning models (gpt-oss, qwen) first write a hidden reasoning that also
        counts against max_tokens, so they get low reasoning effort and room for it; others get the plain limit.
        """
        if self.model_name.startswith(("openai/gpt-oss", "qwen/")):
            return {"max_tokens": answer_tokens + 1500, "extra_body": {"reasoning_effort": "low"}}
        return {"max_tokens": answer_tokens}

    def check_answer(self, text: str, allowed_pids: list, prompt=None) -> dict:
        """Improvement 3: NO_MATCH answers and hallucinated PIDs."""
        if text.upper().startswith("NO_MATCH"):
            reason = text.split(":", 1)[1].strip() if ":" in text else ""
            message = self.NO_MATCH_MESSAGE + (f": {reason}" if reason else ".")
            return {"status": "no_match", "text": message, "pids": [], "invalid_pids": [], "prompt": prompt}
        cited = list(dict.fromkeys(PID_PATTERN.findall(text)))
        invalid = [pid for pid in cited if pid not in allowed_pids]
        for pid in invalid:  # never link to a product the model made up
            text = text.replace(f"[{pid}]", "[unknown product]").replace(pid, "[unknown product]")
        return {"status": "ok", "text": text, "pids": [p for p in cited if p in allowed_pids],
                "invalid_pids": invalid, "prompt": prompt}

    @staticmethod
    def typed_words(user_query, stems):
        """The words of the query whose pre-processed form is one of the given stems ('sare' -> 'saree')."""
        from myapp.search.preprocessing import preprocess_text
        stems = set(stems)
        return [w for w in user_query.split() if stems & set(preprocess_text(w))]

    @staticmethod
    def describe_product(item, document=None) -> str:
        """One line of context for the LLM: everything a shopper needs to compare products."""
        parts = [f"[{item.pid}] {item.title}"]
        if item.brand:
            parts.append(f"brand: {item.brand}")
        if item.selling_price is not None:
            price = f"price: {item.selling_price:.0f} Rs"
            if item.discount and item.actual_price:
                price += f" ({item.discount:.0f}% off, was {item.actual_price:.0f})"
            parts.append(price)
        parts.append(f"rating: {item.average_rating:.1f}/5" if item.average_rating is not None else "rating: none")
        parts.append("OUT OF STOCK" if item.out_of_stock else "in stock")
        details = (document.product_details or {}) if document is not None else {}
        details = [f"{k}: {details[k]}" for k in DETAIL_KEYS if details.get(k)]
        if details:
            parts.append("; ".join(details))
        if item.description:
            parts.append("description: " + " ".join(item.description.split())[:160])
        if item.duplicates:
            parts.append(f"{item.duplicates} identical listings grouped")
        return "- " + " | ".join(parts)
