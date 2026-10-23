import html
import re
import unicodedata

import numpy as np
import pandas as pd
import nltk
from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer
from nltk.tokenize import word_tokenize

# NLTK needs two data files: the stop word list and the tokenizer model.
nltk.download("stopwords", quiet=True)
nltk.download("punkt_tab", quiet=True)

STOP_WORDS = set(stopwords.words("english"))
STEMMER = SnowballStemmer("english")

# 1.1. Text pre-processing (title, description)

def remove_stopwords(tokens):
    """
    Removing stop words (NLTK English list) and 1-letter leftovers like the 's' of "men's".
    ['made', 'from', '100', 'cotton', 'men', 's'] -> ['made', '100', 'cotton', 'men']
    """
    return [t for t in tokens if t not in STOP_WORDS and (len(t) > 1 or t.isdigit())]


def tokenize(text):
    """
    Tokenization + removing punctuation marks.
    'made from 100% cotton, men's' -> ['made', 'from', '100', 'cotton', 'men', 's']
    """
    tokens = []
    for token in word_tokenize(text):
        token = re.sub(r"[^a-z0-9]", "", token) # remove punctuation
        if token:
            tokens.append(token)
    return tokens


def stem(token):
    """Stemming with Snowball (Porter2): 'sleeves' -> 'sleev', 'jeans' -> 'jean'."""
    return STEMMER.stem(token)


def normalize_text(text):
    """
    Bonus step: clean the raw text before tokenizing.
    'Full-Sleeve T-Shirt &amp; cotton.Designed' -> 'full sleeve  tshirt  & cotton. designed'
    """
    if not isinstance(text, str):
        return ""
    text = html.unescape(text) # &amp; -> &
    text = re.sub(r"<[^>]+>|https?://\S+", " ", text) # HTML tags and URLs
    text = re.sub(r"/|\\n", " ", text) # Calf/Crew -> Calf Crew, '\n' -> ' '
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode() # ‘ ’ é -> ' ' e
    text = re.sub(r"([a-zA-Z])([.,;:!?])([a-zA-Z])", r"\1\2 \3", text) # look.Designed -> look. Designed
    text = re.sub(r"\bt[\s-]?shirts?\b", " tshirt ", text, flags=re.IGNORECASE) # T-Shirt -> tshirt
    text = text.lower() # lowercase
    text = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", text) # full-sleeve -> full sleeve
    return text


def preprocess_text(text, use_stopwords=True, use_stemming=True):
    """
    Full pipeline, used for documents now and for queries in Part 2:
    normalize -> tokenize (+ remove punctuation) -> remove stop words -> stem

    >>> preprocess_text("Full Sleeve Women's Sweatshirts")
    ['full', 'sleev', 'women', 'sweatshirt']
    """
    tokens = tokenize(normalize_text(text))
    if use_stopwords:
        tokens = remove_stopwords(tokens)
    if use_stemming:
        tokens = [stem(t) for t in tokens]
    return tokens


# 1.2. Fields returned for every result (to be considered for future parts)
OUTPUT_FIELDS = ["pid", "title", "description", "brand", "category", "sub_category",
                 "product_details", "seller", "out_of_stock", "selling_price", "discount",
                 "actual_price", "average_rating", "url"]


# 1.3. Product_details

# product_details keys worth indexing (codes like "Style Code" are left out)
USEFUL_DETAIL_KEYS = ["Fabric", "Pattern", "Sleeve", "Sleeve Type", "Type", "Ideal For", "Fit",
                      "Brand Fit", "Color", "Brand Color", "Secondary Color", "Neck Type", "Neck",
                      "Occasion", "Closure", "Collar", "Hooded", "Generic Name", "Suitable For",
                      "Pockets", "Rise", "Length", "Fabric Type", "Pack of"]

# fields joined into one merged text field (all_tokens)
MERGED_FIELDS = ["title", "description", "brand", "category", "sub_category", "details"]

def details_to_dict(details):
    """[{'Fabric': 'Cotton'}, {'Color': 'Blue'}] -> {'Fabric': 'Cotton', 'Color': 'Blue'}"""
    result = {}
    for item in details:
        result.update(item)
    return result


def details_to_text(details):
    """Keep only the values of the useful keys: {'Fabric': 'Cotton', 'Style Code': 'X1'} -> 'Cotton'"""
    return " ".join(str(details[k]) for k in USEFUL_DETAIL_KEYS if k in details)



# 1.4. Numeric fields (stored as numbers, NOT indexed as text)

def to_number(value):
    """'2,999' -> 2999.0 | '69% off' -> 69.0 | '3.9' -> 3.9 | '' -> NaN"""
    match = re.search(r"\d+(\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else np.nan


# =============================================================================
# Put everything together
# =============================================================================

def load_raw_corpus(path):
    """Read the JSON dataset into a table (one row per product)."""
    return pd.read_json(path, dtype={"pid": str})


def build_processed_corpus(raw):
    """
    Apply points 1, 3 and 4 to every product. Original columns are kept for display;
    new columns: details_dict, details_text, has_rating, <field>_tokens, all_tokens.
    """
    df = raw.copy()

    # Empty strings ("") become missing values (NaN)
    for col in ["title", "description", "brand", "category", "sub_category", "seller"]:
        df[col] = df[col].replace("", np.nan)

    # 1.4. Numeric fields
    for col in ["selling_price", "actual_price", "discount", "average_rating"]:
        df[col] = df[col].map(to_number)
    df["has_rating"] = df["average_rating"].notna()
    df["actual_price"] = df["actual_price"].fillna(df["selling_price"])  # no actual price -> no discount
    df["discount"] = df["discount"].fillna(0)

    # 1.3 Product_details as dict and as text
    df["details_dict"] = df["product_details"].map(details_to_dict)
    df["details_text"] = df["details_dict"].map(details_to_text)

    # 1.1. One token column per text field
    for col in ["title", "description", "brand", "category", "sub_category", "seller"]:
        df[col + "_tokens"] = df[col].map(preprocess_text)
    df["details_tokens"] = df["details_text"].map(preprocess_text)

    # one merged field
    df["all_tokens"] = df[[f + "_tokens" for f in MERGED_FIELDS]].sum(axis=1)
    return df
