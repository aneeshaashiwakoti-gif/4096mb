"""
Person 2: Retrieval & Storage Module
------------------------------------
Owns: Turning stored embeddings into "here are the 5 most relevant chunks for this question."

Features:
- Fast vectorized cosine similarity search (numpy / pure Python fallback)
- Storage loader for JSON and SQLite formats (agreed with Person 1)
- Embedding integration that mirrors Person 1's embedder.py EXACTLY (same env vars,
  same Gemini model + endpoint, same local sentence-transformers model) so query
  vectors always land in the same vector space as the stored chunk embeddings in
  output/chunks.json. Falls back to a deterministic offline pseudo-embedding only
  when neither real backend is available (dev/testing only -- see warning below).
- Top-K retrieval returning clean chunks with file paths, line numbers, and similarity scores (ready for Person 3)
"""

import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Ensure paths are configured for both direct execution and package imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
for p in (CURRENT_DIR, PARENT_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PARENT_DIR, ".env"))
    load_dotenv()  # also check current dir
except ImportError:
    pass

try:
    # pyrefly: ignore [missing-import]
    import numpy as np  # type: ignore
    HAS_NUMPY = True
except (ImportError, ModuleNotFoundError):
    HAS_NUMPY = False
    np = None  # type: ignore

# ── Shared config: MUST match Person 1's embedder.py exactly ──────────────────
# Same env var names as embedder.py, so a single .env controls both sides and
# they can never silently drift onto different models/vector spaces again.
_DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")
_FALLBACK_GEMINI_MODEL = "models/gemini-embedding-2"
_GEMINI_ENDPOINT_TMPL = "https://generativelanguage.googleapis.com/v1beta/{model}:batchEmbedContents"


class EmbeddingDimensionMismatch(ValueError):
    """Raised when a query vector and a stored chunk vector have different
    dimensionality -- almost always a sign the query was embedded with a
    different model than the one used to build output/chunks.json."""


def _stable_hash(value: str) -> int:
    """
    Deterministic string hash that is stable across processes and Python
    runs (unlike the builtin hash(), which is salted per-process by
    PYTHONHASHSEED and therefore produces different results every run).
    """
    digest = hashlib.md5(value.encode("utf-8")).hexdigest()
    return int(digest, 16)


@dataclass
class CodeChunk:
    """Standard chunk structure agreed between Person 1, Person 2, and Person 3."""
    chunk_id: Union[str, int]
    file_path: str
    start_line: int
    end_line: int
    text: str
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self, include_embedding: bool = False) -> Dict[str, Any]:
        data = {
            "chunk_id": self.chunk_id,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "text": self.text,
            "metadata": self.metadata or {}
        }
        if include_embedding and self.embedding is not None:
            data["embedding"] = self.embedding
        return data


@dataclass
class SearchResult:
    """Format returned by Person 2's search function directly consumed by Person 3."""
    chunk_id: Union[str, int]
    file_path: str
    start_line: int
    end_line: int
    text: str
    similarity_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _pure_cosine_similarity(query_vec: List[float], doc_vec: List[float]) -> float:
    """Pure Python cosine similarity between two 1D vectors with strict dimension validation."""
    if not query_vec or not doc_vec:
        return 0.0
    if len(query_vec) != len(doc_vec):
        raise EmbeddingDimensionMismatch(
            f"Vector dimension mismatch: query vector has {len(query_vec)} dimensions, "
            f"but document vector has {len(doc_vec)} dimensions. "
            f"Both vectors must be embedded using the exact same model and backend. "
            f"Check GEMINI_EMBEDDING_MODEL / EMBEDDING_BACKEND match Person 1's .env."
        )
    dot = sum(q * d for q, d in zip(query_vec, doc_vec))
    q_norm = math.sqrt(sum(q * q for q in query_vec))
    d_norm = math.sqrt(sum(d * d for d in doc_vec))
    if q_norm == 0 or d_norm == 0:
        return 0.0
    return dot / (q_norm * d_norm)


def cosine_similarity(query_vec: Any, doc_vecs: Any) -> Any:
    """
    Compute cosine similarity between a 1D query vector and doc vectors.
    Supports both Numpy ndarray and pure Python lists.
    Raises EmbeddingDimensionMismatch if vector lengths don't match, instead
    of silently truncating (a mismatch is always a real bug, never valid data).
    """
    if HAS_NUMPY and np is not None:
        q = np.array(query_vec, dtype=np.float32)
        docs = np.array(doc_vecs, dtype=np.float32)
        if docs.ndim == 1:
            docs = docs.reshape(1, -1)

        if q.shape[0] != docs.shape[1]:
            raise EmbeddingDimensionMismatch(
                f"Vector dimension mismatch: query vector has {q.shape[0]} dimensions, "
                f"but document vector has {docs.shape[1]} dimensions. "
                f"Both vectors must be embedded using the exact same model and backend. "
                f"Check GEMINI_EMBEDDING_MODEL / EMBEDDING_BACKEND match Person 1's .env."
            )

        query_norm = np.linalg.norm(q)
        if query_norm == 0:
            return np.zeros(docs.shape[0])

        doc_norms = np.linalg.norm(docs, axis=1)
        doc_norms[doc_norms == 0] = 1e-10

        dot_products = np.dot(docs, q)
        return dot_products / (doc_norms * query_norm)

    # Pure Python fallback
    if isinstance(doc_vecs, list) and len(doc_vecs) > 0 and isinstance(doc_vecs[0], (int, float)):
        doc_vecs = [doc_vecs]
    return [_pure_cosine_similarity(query_vec, doc) for doc in doc_vecs]


class EmbeddingProvider:
    """
    Generates QUERY embeddings using the exact same backend/model Person 1's
    embedder.py used to generate the DOCUMENT embeddings in output/chunks.json.

    Backend selection mirrors embedder.py precisely:
      - EMBEDDING_BACKEND=gemini (default): Gemini REST batchEmbedContents,
        model from GEMINI_EMBEDDING_MODEL (default "models/gemini-embedding-001"),
        with the same 429/daily-quota fallback to "models/gemini-embedding-2".
      - EMBEDDING_BACKEND=local: sentence-transformers "all-MiniLM-L6-v2",
        the same local model embedder.py uses (384-dim).

    Primary path: delegates to embedder.embed_query() for 100% byte-for-byte
    vector space consistency with stored chunks. Falls back to direct Gemini
    REST / local embedding if embedder.py is not importable, and finally to a
    deterministic offline pseudo-embedding.

    IMPORTANT: the offline fallback is for isolated dev/testing only. Its
    vectors are NOT in the same space as real Gemini or MiniLM embeddings, so
    it must never be used to search real output/chunks.json data -- only
    against chunks that were also embedded with the same fallback.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        backend: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.backend = backend or os.getenv("EMBEDDING_BACKEND", "gemini")
        # model_name is only used for the "gemini" backend; local backend has
        # a fixed model to match embedder.py's _embed_local().
        self.model_name = model_name or _DEFAULT_GEMINI_MODEL
        self._local_model = None  # lazy-loaded sentence-transformers model

    # ── Gemini backend (mirrors embedder.py's _embed_gemini, single-text) ──
    def _embed_gemini_query(self, text: str) -> List[float]:
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        session = requests.Session()
        model = self.model_name
        payload = {
            "requests": [{
                "model": model,
                "content": {"parts": [{"text": text}]},
                # Queries use RETRIEVAL_QUERY; Person 1 embeds chunks with
                # RETRIEVAL_DOCUMENT -- both are required by Gemini's
                # asymmetric retrieval task types and are expected to differ.
                "taskType": "RETRIEVAL_QUERY",
            }]
        }
        url = _GEMINI_ENDPOINT_TMPL.format(model=model)

        for attempt in range(5):
            try:
                resp = session.post(url, params={"key": self.api_key}, json=payload, timeout=30)
                if resp.status_code == 429:
                    err_text = resp.text
                    if model != _FALLBACK_GEMINI_MODEL and (
                        "PerDay" in err_text or "limit: 1000" in err_text
                    ):
                        model = _FALLBACK_GEMINI_MODEL
                        url = _GEMINI_ENDPOINT_TMPL.format(model=model)
                        payload["requests"][0]["model"] = model
                        continue
                    time.sleep(min(30, (2 ** attempt) * 2 + 2))
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["embeddings"][0]["values"]
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(min(15, 2 ** attempt))
        raise RuntimeError("Gemini query embedding failed after retries")

    # ── Local backend (mirrors embedder.py's _embed_local exactly) ─────────
    def _embed_local_query(self, text: str) -> List[float]:
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer("all-MiniLM-L6-v2")
        vec = self._local_model.encode([text], show_progress_bar=False, convert_to_numpy=True)[0]
        return vec.tolist()

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding vector for a single query string."""
        # 1. Primary path: Use Person 1's embed_query for 100% byte-for-byte vector space consistency
        try:
            from embedder import embed_query
            return embed_query(text, backend=self.backend)
        except Exception as exc:
            logger.debug("Primary embed_query failed: %s; trying secondary path", exc)

        # 2. Secondary path: direct Gemini REST or local model
        try:
            if self.backend == "gemini" and self.api_key:
                return self._embed_gemini_query(text)
            if self.backend == "local":
                return self._embed_local_query(text)
        except Exception as exc:
            logger.debug("Secondary direct embed failed: %s; using offline fallback", exc)

        # 3. Offline / fallback deterministic embedding matching active model dimensions
        dim = 384 if self.backend == "local" else 3072
        logger.warning(
            "Generating deterministic fallback embedding (dim=%d) for query. "
            "Set GEMINI_API_KEY to enable neural semantic embeddings.", dim
        )
        return self._generate_deterministic_embedding(text, dim=dim)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple strings."""
        return [self.embed_text(t) for t in texts]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """
        Splits code/text into lowercase word tokens, stripping punctuation and
        splitting snake_case/camelCase so identifiers like DATABASE_URL become
        independently matchable tokens ("database", "url"). Only used by the
        offline dev fallback below.
        """
        raw = re.sub(r"[^0-9a-zA-Z]+", " ", text)
        raw = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", raw)
        return [w for w in raw.lower().split() if w]

    @staticmethod
    def _generate_deterministic_embedding(text: str, dim: int = 3072) -> List[float]:
        """
        Deterministic pseudo-embedding for offline development and testing
        ONLY -- not compatible with real Gemini or MiniLM vectors of any
        dimension. Uses a stable (hashlib-based) hash so results are
        reproducible across separate Python processes/runs.
        Defaults to 3072 dimensions to match Gemini vector dimensions.
        """
        vec = [0.0] * dim
        words = EmbeddingProvider._tokenize(text)
        if not words:
            return vec

        for word in words:
            h = _stable_hash(word)
            idx = h % dim
            sign = 1.0 if (h // dim) % 2 == 0 else -1.0
            vec[idx] += sign

            for i in range(len(word) - 1):
                bg_hash = _stable_hash(word[i:i+2])
                bg_idx = bg_hash % dim
                vec[bg_idx] += 0.5

        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec


class StorageLoader:
    """Handles loading and saving chunks to JSON files or SQLite databases."""

    @staticmethod
    def load_from_json(json_path: str) -> List[CodeChunk]:
        """Loads chunks from a JSON file (agreed storage format with Person 1)."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        chunks_data = data if isinstance(data, list) else data.get("chunks", [])
        chunks = []
        for idx, item in enumerate(chunks_data):
            chunk = CodeChunk(
                chunk_id=item.get("chunk_id", idx),
                file_path=item.get("file_path", "unknown"),
                start_line=item.get("start_line", 1),
                end_line=item.get("end_line", 1),
                text=item.get("text", item.get("chunk_text", "")),
                embedding=item.get("embedding"),
                metadata=item.get("metadata")
            )
            chunks.append(chunk)
        return chunks

    @staticmethod
    def save_to_json(chunks: List[CodeChunk], json_path: str):
        """Saves chunks to a JSON file."""
        os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
        data = [chunk.to_dict(include_embedding=True) for chunk in chunks]
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load_from_sqlite(db_path: str, table_name: str = "chunks") -> List[CodeChunk]:
        """Loads chunks from an SQLite database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT chunk_id, file_path, start_line, end_line, text, embedding, metadata FROM {table_name}")
        rows = cursor.fetchall()
        chunks = []
        for row in rows:
            embedding = json.loads(row[5]) if row[5] else None
            metadata = json.loads(row[6]) if row[6] else None
            chunks.append(CodeChunk(
                chunk_id=row[0],
                file_path=row[1],
                start_line=row[2],
                end_line=row[3],
                text=row[4],
                embedding=embedding,
                metadata=metadata
            ))
        conn.close()
        return chunks

    @staticmethod
    def save_to_sqlite(chunks: List[CodeChunk], db_path: str, table_name: str = "chunks"):
        """Saves chunks to an SQLite database."""
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                chunk_id TEXT PRIMARY KEY,
                file_path TEXT,
                start_line INTEGER,
                end_line INTEGER,
                text TEXT,
                embedding TEXT,
                metadata TEXT
            )
        """)
        for c in chunks:
            cursor.execute(
                f"INSERT OR REPLACE INTO {table_name} VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(c.chunk_id),
                    c.file_path,
                    c.start_line,
                    c.end_line,
                    c.text,
                    json.dumps(c.embedding) if c.embedding else None,
                    json.dumps(c.metadata) if c.metadata else None
                )
            )
        conn.commit()
        conn.close()


class CodebaseRetriever:
    """
    Main Person 2 Engine.
    Stores chunks, computes cosine similarity, and retrieves top matches for any question.
    """

    def __init__(self, embedding_provider: Optional[EmbeddingProvider] = None):
        self.embedder = embedding_provider or EmbeddingProvider()
        self.chunks: List[CodeChunk] = []

    def add_chunks(self, chunks: List[CodeChunk]):
        """Add chunks in-memory and ensure all have embeddings."""
        for c in chunks:
            if c.embedding is None:
                c.embedding = self.embedder.embed_text(c.text)
        self.chunks.extend(chunks)

    def load_storage(self, file_path: str):
        """Loads chunks from JSON or SQLite file."""
        if file_path.endswith(".json"):
            loaded = StorageLoader.load_from_json(file_path)
        elif file_path.endswith(".db") or file_path.endswith(".sqlite"):
            loaded = StorageLoader.load_from_sqlite(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path}. Expected .json or .sqlite/.db")

        # Fill any missing embeddings
        for c in loaded:
            if c.embedding is None:
                c.embedding = self.embedder.embed_text(c.text)

        self.chunks = loaded

    def search(self, question: str, top_k: int = 5) -> List[SearchResult]:
        """
        The core Person 2 contract function:
        Embeds question, computes cosine similarity against all chunks,
        and returns top K matches.
        """
        if not self.chunks:
            return []

        query_vec = self.embedder.embed_text(question)

        # Calculate scores using vectorized cosine similarity
        valid_pairs = [(i, c) for i, c in enumerate(self.chunks) if c.embedding is not None]
        if not valid_pairs:
            return []

        doc_vecs = [c.embedding for _, c in valid_pairs]
        scores = cosine_similarity(query_vec, doc_vecs)

        scored_items = []
        for (i, chunk), score in zip(valid_pairs, scores):
            scored_items.append((float(score), chunk))

        # Sort descending by score
        scored_items.sort(key=lambda x: x[0], reverse=True)

        k = min(top_k, len(scored_items))
        results = []
        for i in range(k):
            score, chunk = scored_items[i]
            results.append(SearchResult(
                chunk_id=chunk.chunk_id,
                file_path=chunk.file_path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                text=chunk.text,
                similarity_score=round(float(score), 4)
            ))

        return results

    def search_as_dicts(self, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Convenience method returning standard dicts ready for Person 3 prompt interpolation."""
        return [r.to_dict() for r in self.search(question, top_k=top_k)]


# Global default instance
_default_retriever = CodebaseRetriever()

def init_retriever(storage_path: Optional[str] = None) -> CodebaseRetriever:
    """Initialize global retriever with a storage file."""
    global _default_retriever
    _default_retriever = CodebaseRetriever()
    if storage_path and os.path.exists(storage_path):
        _default_retriever.load_storage(storage_path)
    return _default_retriever

def search(question: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Standard Person 2 function export:
    Calling search("some question") returns a list of the 5 most relevant chunks.
    """
    return _default_retriever.search_as_dicts(question, top_k=top_k)
