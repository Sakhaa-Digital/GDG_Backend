# src/services/column_matcher.py
"""
Semantically matches CSV column names to rule field names.
Uses OpenAI embeddings + cosine similarity.
"""
import os
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
from difflib import SequenceMatcher

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SIMILARITY_THRESHOLD = 0.75  # tune this (0-1)


def cosine_similarity(a: list, b: list) -> float:
    a = np.array(a)
    b = np.array(b)
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def fuzzy_match(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


async def embed_texts(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts
    )
    return [item.embedding for item in response.data]


async def match_columns_to_fields(
    csv_columns: list[str],
    rule_fields: list[str]
) -> dict[str, str]:
    """
    Returns a mapping: { rule_field -> best_matching_csv_column }
    Only includes matches above threshold.
    """
    if not csv_columns or not rule_fields:
        return {}

    all_texts = csv_columns + rule_fields
    embeddings = await embed_texts(all_texts)

    col_embeddings = embeddings[:len(csv_columns)]
    field_embeddings = embeddings[len(csv_columns):]

    mapping = {}

    for fi, field in enumerate(rule_fields):
        best_col = None
        best_score = 0.0

        for ci, col in enumerate(csv_columns):
            # Semantic similarity
            sem_score = cosine_similarity(col_embeddings[ci], field_embeddings[fi])
            # Fuzzy string match
            fuz_score = fuzzy_match(col, field)
            # Combined score (weighted)
            score = 0.7 * sem_score + 0.3 * fuz_score

            if score > best_score:
                best_score = score
                best_col = col

        if best_score >= SIMILARITY_THRESHOLD and best_col:
            mapping[field] = best_col
            print(f"[ColumnMatcher] '{field}' → '{best_col}' (score: {best_score:.2f})")
        else:
            print(f"[ColumnMatcher] No match for '{field}' (best score: {best_score:.2f})")

    return mapping