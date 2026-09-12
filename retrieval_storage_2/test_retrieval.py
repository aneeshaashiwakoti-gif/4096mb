"""
Tests for Person 2: Retrieval & Storage
Run with: pytest test_retrieval.py or python test_retrieval.py
"""

import math
import os
import sys
import tempfile

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
for path in (CURRENT_DIR, PARENT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    import pytest
except (ImportError, ModuleNotFoundError):
    pytest = None

try:
    from retrieval import (
        CodeChunk,
        CodebaseRetriever,
        EmbeddingProvider,
        SearchResult,
        StorageLoader,
        _pure_cosine_similarity,
        cosine_similarity,
        init_retriever,
        search,
    )
except ImportError:
    from person2_retrieval.retrieval import (
        CodeChunk,
        CodebaseRetriever,
        EmbeddingProvider,
        SearchResult,
        StorageLoader,
        _pure_cosine_similarity,
        cosine_similarity,
        init_retriever,
        search,
    )


def test_cosine_similarity_math():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    score = cosine_similarity(v1, v2)
    val = score[0] if isinstance(score, (list, tuple)) or hasattr(score, "__getitem__") else score
    assert math.isclose(float(val), 1.0, rel_tol=1e-5)

    v3 = [0.0, 1.0, 0.0]
    score_ortho = cosine_similarity(v1, v3)
    val_ortho = score_ortho[0] if isinstance(score_ortho, (list, tuple)) or hasattr(score_ortho, "__getitem__") else score_ortho
    assert math.isclose(float(val_ortho), 0.0, abs_tol=1e-5)

    v4 = [-1.0, 0.0, 0.0]
    score_opp = cosine_similarity(v1, v4)
    val_opp = score_opp[0] if isinstance(score_opp, (list, tuple)) or hasattr(score_opp, "__getitem__") else score_opp
    assert math.isclose(float(val_opp), -1.0, rel_tol=1e-5)


def test_vector_dimension_mismatch_raises_error():
    """Verify that comparing vectors of different dimensions raises a ValueError instead of silently truncating."""
    v_3072 = [0.1] * 3072
    v_768 = [0.1] * 768

    # Pure Python check
    try:
        _pure_cosine_similarity(v_768, v_3072)
        assert False, "Expected ValueError on dimension mismatch in _pure_cosine_similarity"
    except ValueError as exc:
        assert "dimension mismatch" in str(exc).lower()

    # Vectorized / Numpy check
    try:
        cosine_similarity(v_768, [v_3072])
        assert False, "Expected ValueError on dimension mismatch in cosine_similarity"
    except ValueError as exc:
        assert "dimension mismatch" in str(exc).lower()


def test_storage_json_roundtrip():
    chunks = [
        CodeChunk("c1", "src/auth.py", 1, 10, "def login(): pass", [0.1, 0.2]),
        CodeChunk("c2", "src/db.py", 1, 15, "def connect(): pass", [0.3, 0.4]),
    ]
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        StorageLoader.save_to_json(chunks, tmp_path)
        loaded = StorageLoader.load_from_json(tmp_path)
        assert len(loaded) == 2
        assert loaded[0].chunk_id == "c1"
        assert loaded[0].file_path == "src/auth.py"
        assert loaded[0].text == "def login(): pass"
        assert loaded[0].embedding == [0.1, 0.2]
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_storage_sqlite_roundtrip():
    chunks = [
        CodeChunk("c1", "src/auth.py", 1, 10, "def login(): pass", [0.1, 0.2]),
        CodeChunk("c2", "src/db.py", 1, 15, "def connect(): pass", [0.3, 0.4]),
    ]
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        StorageLoader.save_to_sqlite(chunks, tmp_path)
        loaded = StorageLoader.load_from_sqlite(tmp_path)
        assert len(loaded) == 2
        assert loaded[0].chunk_id == "c1"
        assert loaded[0].file_path == "src/auth.py"
        assert loaded[1].text == "def connect(): pass"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_retriever_search_ranking():
    mock_file = os.path.join(CURRENT_DIR, "mock_chunks.json")
    retriever = CodebaseRetriever()
    retriever.load_storage(mock_file)

    results_auth = retriever.search("where is authentication and jwt token handled?", top_k=2)
    assert len(results_auth) == 2
    assert "auth" in results_auth[0].file_path

    results_db = retriever.search("how does the database connection work?", top_k=1)
    assert len(results_db) == 1
    assert "database" in results_db[0].file_path

    results_pay = retriever.search("how is stripe charge and payment processed?", top_k=1)
    assert len(results_pay) == 1
    assert "stripe" in results_pay[0].file_path or "billing" in results_pay[0].file_path


def test_search_output_contract_for_person_3():
    mock_file = os.path.join(CURRENT_DIR, "mock_chunks.json")
    init_retriever(mock_file)

    results = search("what would break if I change user registration?", top_k=5)
    assert isinstance(results, list)
    assert len(results) <= 5

    for item in results:
        assert "chunk_id" in item
        assert "file_path" in item
        assert "start_line" in item
        assert "end_line" in item
        assert "text" in item
        assert "similarity_score" in item
        assert isinstance(item["file_path"], str)
        assert isinstance(item["start_line"], int)
        assert isinstance(item["end_line"], int)
        assert isinstance(item["text"], str)
        assert isinstance(item["similarity_score"], float)


if __name__ == "__main__":
    test_cosine_similarity_math()
    test_vector_dimension_mismatch_raises_error()
    test_storage_json_roundtrip()
    test_storage_sqlite_roundtrip()
    test_retriever_search_ranking()
    test_search_output_contract_for_person_3()
    print("All Person 2 tests passed successfully!")

