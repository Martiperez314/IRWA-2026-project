from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import re


class Document(BaseModel):
    _id: str
    pid: str
    title: str
    description: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    product_details: Optional[Dict[str, Any]] = None
    seller: Optional[str] = None
    out_of_stock: bool = False
    selling_price: Optional[float] = None
    discount: Optional[float] = None
    actual_price: Optional[float] = None
    average_rating: Optional[float] = None
    url: Optional[str] = None
    images: Optional[List[str]] = None

    def to_json(self):
        return self.model_dump_json()

    # --- Validators ---

    @field_validator("selling_price", "actual_price", mode="before")
    def parse_price(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip().replace(",", "")
            if v == "":
                return None
            try:
                return float(v)
            except ValueError:
                return None
        return v

    @field_validator("average_rating", mode="before")
    def parse_rating(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
            try:
                return float(v)
            except ValueError:
                return None
        return v

    @field_validator("discount", mode="before")
    def parse_discount(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            match = re.search(r"(\d+(?:\.\d+)?)", v.replace(",", ""))
            if match:
                return float(match.group(1))
            return None
        return v

    @field_validator("product_details", mode="before")
    def normalize_product_details(cls, v):
        if isinstance(v, list):
            merged = {}
            for item in v:
                if isinstance(item, dict):
                    merged.update(item)
            return merged
        return v

    def __str__(self) -> str:
        return self.model_dump_json(indent=2)


class StatsDocument(BaseModel):
    """
    Original corpus data as an object
    """
    pid: str
    title: str
    description: Optional[str] = None
    url: Optional[str] = None
    count: Optional[int] = None

    def __str__(self) -> str:
        return self.model_dump_json(indent=2)
    
    def to_json(self):
        return self.model_dump_json()


class ResultItem(BaseModel):
    """One product in the results page (Part 4: the fields the statement asks for, and a few more)."""
    pid: str
    title: str
    description: Optional[str] = None
    url: Optional[str] = None               # original product page (Flipkart)
    ranking: Optional[float] = None         # score of our ranking
    rank: Optional[int] = None              # position in the results (1 = first)
    brand: Optional[str] = None
    sub_category: Optional[str] = None
    selling_price: Optional[float] = None
    actual_price: Optional[float] = None
    discount: Optional[float] = None
    average_rating: Optional[float] = None
    out_of_stock: bool = False
    image: Optional[str] = None
    duplicates: int = 0                     # other identical listings grouped under this result
    search_id: Optional[int] = None         # analytics id of the query that produced this result

    def __str__(self) -> str:
        return self.model_dump_json(indent=2)
    
    def to_json(self):
        return self.model_dump_json()
