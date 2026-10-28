import re
from functools import lru_cache

try:
    from rank_bm25 import BM25Okapi
    BM25_IMPLEMENTATION = "rank_bm25.OkapiBM25"
except ImportError:
    import math
    BM25_IMPLEMENTATION = "in-repository Okapi BM25 fallback (rank_bm25 unavailable)"

    class BM25Okapi:  # compact compatible fallback for offline evaluation installs
        def __init__(self, corpus: list[list[str]]):
            self.corpus = corpus
            self.avgdl = sum(map(len, corpus)) / max(len(corpus), 1)
            self.df = {term: sum(term in doc for doc in corpus) for doc in corpus for term in set(doc)}

        def get_scores(self, query: list[str]):
            output = []
            for doc in self.corpus:
                counts = {term: doc.count(term) for term in set(doc)}
                score = 0.0
                for term in query:
                    tf = counts.get(term, 0)
                    idf = math.log(1 + (len(self.corpus) - self.df.get(term, 0) + 0.5) / (self.df.get(term, 0) + 0.5))
                    score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(doc) / max(self.avgdl, 1)))
                output.append(score)
            return output

from evidencedesk.config import Settings


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\w'-]+", text.lower())


STOP_WORDS = {"a", "an", "and", "are", "at", "be", "by", "can", "do", "does", "for", "from", "how", "i", "in", "is", "it", "may", "of", "on", "or", "the", "their", "this", "to", "was", "what", "when", "where", "which", "who", "why", "with", "would", "your"}


@lru_cache(maxsize=2)
def _embedding_model(name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name)


def search(query: str, rows: list[dict], settings: Settings, top_k: int) -> list[dict]:
    if not rows:
        return []
    tokens = [tokenize(row["text"]) for row in rows]
    bm25 = BM25Okapi(tokens)
    raw = bm25.get_scores(tokenize(query))
    peak = max(raw) if len(raw) else 0
    query_terms = set(tokenize(query)) - STOP_WORDS
    lexical = []
    for row, score in zip(rows, raw):
        present = set(tokenize(row["text"]))
        coverage = len(query_terms & present) / max(len(query_terms), 1)
        lexical.append((float(score / peak) if peak > 0 else 0) * coverage)
    semantic = [0.0] * len(rows)
    if settings.embedding_provider == "local":
        try:
            import faiss
            import numpy as np

            model = _embedding_model(settings.embedding_model)
            vectors = model.encode([row["text"] for row in rows], normalize_embeddings=True)
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(np.asarray(vectors, dtype="float32"))
            q = model.encode([query], normalize_embeddings=True)
            scores, ids = index.search(np.asarray(q, dtype="float32"), len(rows))
            for score, idx in zip(scores[0], ids[0]):
                if idx >= 0:
                    semantic[int(idx)] = max(0.0, float(score))
        except Exception:
            # Missing model packages or weights: lexical search still works offline.
            semantic = lexical
    else:
        semantic = lexical
    if settings.retrieval_mode == "bm25":
        combined = lexical
    elif settings.retrieval_mode == "vector":
        combined = semantic
    else:
        denom = settings.vector_weight + settings.bm25_weight or 1
        combined = [(settings.vector_weight * v + settings.bm25_weight * b) / denom
                    for v, b in zip(semantic, lexical)]
    ranked = sorted(enumerate(combined), key=lambda item: item[1], reverse=True)
    return [dict(rows[i], score=float(score)) for i, score in ranked[:top_k] if score > 0]
