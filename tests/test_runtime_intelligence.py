"""Runtime contracts joining Person 1 scanning, Person 2 retrieval, and Person 3 APIs."""
from pathlib import Path
import json

from app.config import settings
from app.indexing.service import redact_secrets


PROJECT = Path("sentinel_demo_project").resolve()


def _connect(client):
    response = client.post("/projects/connect", json={"path": str(PROJECT)})
    assert response.status_code == 200
    return response.json()


def test_project_index_uses_person2_search_and_exposes_symbols(client):
    connected = _connect(client)
    assert connected["index"]["status"] == "ready"
    assert connected["index"]["embedding_status"] == "ready"

    results = client.get("/projects/search", params={"query": "calculate_total"}).json()["results"]
    assert results and results[0]["retrieval"] == "vector"
    assert {item["symbol"] for item in results} & {"calculate_total", "process_checkout"}

    symbols = client.get("/projects/symbols", params={"file": "src/payment.py"}).json()["symbols"]
    assert symbols[0]["name"] == "calculate_total"


def test_pr_audit_drift_and_secret_redaction(client):
    _connect(client)
    audit = client.post("/pr/audit", json={
        "diff": "diff --git a/src/payment.py b/src/payment.py\n--- a/src/payment.py\n+++ b/src/payment.py\n@@ -1,2 +1,2 @@\n-def calculate_total(items):\n+def calculate_total(items, tax=0):",
    })
    assert audit.status_code == 200
    findings = audit.json()["findings"]
    assert findings and findings[0]["category"] == "dependency/blast-radius issue"
    assert client.get("/drift-trend").status_code == 200
    assert "[REDACTED]" in redact_secrets("API_KEY=not-for-llm")


def test_drift_trend_reports_largest_commit_jump(client):
    manifest = Path("tests/.drift_manifest.json")
    original_path = settings.HISTORICAL_SNAPSHOTS_MANIFEST
    try:
        manifest.write_text(json.dumps({"snapshots": [
            {"commit_hash": "a", "date": "2026-01-01", "duplication_score": 0.10},
            {"commit_hash": "b", "date": "2026-01-02", "duplication_score": 0.42, "affected_files": ["src/a.py"]},
            {"commit_hash": "c", "date": "2026-01-03", "duplication_score": 0.50},
        ]}), encoding="utf-8")
        settings.HISTORICAL_SNAPSHOTS_MANIFEST = str(manifest)
        from app.api.audit import drift_trend
        response = drift_trend()
        assert response.biggest_positive_jump["commit"] == "b"
        assert response.biggest_positive_jump["increase"] == 0.32
    finally:
        settings.HISTORICAL_SNAPSHOTS_MANIFEST = original_path
        manifest.unlink(missing_ok=True)


def test_real_change_reindexes_and_notifies_websocket(client):
    _connect(client)
    target = PROJECT / "src" / "payment.py"
    original = target.read_bytes()
    with client.websocket_connect("/projects/ws") as websocket:
        try:
            target.write_bytes(original.replace(b"return total", b"return total + 1"))
            event = websocket.receive_json()
            assert event["type"] == "file_event"
            assert event["change"]["change_type"] == "modified"
            content = client.get("/projects/file/content", params={"path": "src/payment.py"}).json()["content"]
            assert "return total + 1" in content
        finally:
            target.write_bytes(original)


def test_polling_watcher_reports_rename(client):
    _connect(client)
    source = PROJECT / "watch_rename_source.py"
    destination = PROJECT / "watch_rename_destination.py"
    source.unlink(missing_ok=True)
    destination.unlink(missing_ok=True)
    with client.websocket_connect("/projects/ws") as websocket:
        try:
            source.write_text("def rename_probe():\n    return True\n", encoding="utf-8")
            assert websocket.receive_json()["change_type"] == "created"
            source.rename(destination)
            event = websocket.receive_json()
            assert event["change_type"] == "renamed"
            assert event["change"]["old_path"] == "watch_rename_source.py"
        finally:
            source.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
