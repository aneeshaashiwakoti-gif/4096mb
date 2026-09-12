"""Person 3 PR audit and historical drift endpoints.

Findings are based on connected-project structure first.  They are intentionally
conservative: an absent graph edge produces no blast-radius claim.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.indexing.service import project_index
from app.models.intelligence import AuditFinding, AuditRequest, AuditResponse, DriftPoint, DriftResponse

router = APIRouter(tags=["Audit"])
_DIFF_FILE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)
_DIFF_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def _finding_id(category: str, file_path: str, symbol: str | None) -> str:
    return hashlib.sha1(f"{category}:{file_path}:{symbol or ''}".encode()).hexdigest()[:12]


@router.post("/pr/audit", response_model=AuditResponse)
def audit_pull_request(payload: AuditRequest) -> AuditResponse:
    if not project_index.connected:
        raise HTTPException(status_code=400, detail="No active project")
    diff_files = [path for path in _DIFF_FILE.findall(payload.diff) if path != "/dev/null"]
    files = list(dict.fromkeys(payload.changed_files + diff_files))
    if not files:
        raise HTTPException(status_code=422, detail="Malformed PR diff: no changed files were found.")
    findings: list[AuditFinding] = []
    for file_path in files:
        if file_path not in project_index.chunks_by_file:
            continue
        chunks = project_index.chunks_by_file[file_path]
        hunk = _DIFF_HUNK.search(payload.diff)
        changed_line = int(hunk.group(1)) if hunk else chunks[0].start_line
        impacted = project_index.impact(file_path)
        if impacted.impacted_components:
            evidence = [item.model_dump() for item in impacted.evidence]
            findings.append(AuditFinding(
                finding_id=_finding_id("dependency_blast_radius", file_path, impacted.change.symbol),
                category="dependency/blast-radius issue", severity="MEDIUM",
                title="Changed code has indexed downstream dependents",
                description=f"Structural analysis found {len(impacted.impacted_components)} dependent component(s).",
                affected_file=file_path, affected_symbol=impacted.change.symbol,
                line_range=f"{changed_line}-{changed_line}", evidence=evidence,
                dependency_path=impacted.impact_chain,
                recommendation="Review the listed callers and run their focused tests before merging.", confidence="HIGH",
            ))
        # Compare added code against existing indexed chunks. This is a signal,
        # not a claim of a defect, and excludes the edited file itself.
        additions = "\n".join(line[1:] for line in payload.diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
        if additions.strip():
            matches = [item for item in project_index.search(additions, 5) if item["file_path"] != file_path and item["score"] >= 0.45]
            if matches:
                match = matches[0]
                findings.append(AuditFinding(
                    finding_id=_finding_id("duplicate_logic", file_path, impacted.change.symbol),
                    category="duplicate logic", severity="LOW", title="Similar indexed implementation exists",
                    description="The added code overlaps a separately indexed chunk; review whether shared logic is preferable.",
                    affected_file=file_path, affected_symbol=impacted.change.symbol,
                    line_range=f"{changed_line}-{changed_line}", evidence=[match], dependency_path=[],
                    recommendation=f"Compare with {match['file_path']}:{match['start_line']}-{match['end_line']} before duplicating behavior.",
                    confidence="MEDIUM",
                ))
        if any(token in file_path.lower() for token in ("api", "config", "public")):
            docs = [path for path in project_index.chunks_by_file if path.lower().endswith((".md", ".rst"))]
            if docs:
                findings.append(AuditFinding(
                    finding_id=_finding_id("documentation_drift", file_path, None), category="documentation drift",
                    severity="LOW", title="Public-facing code changed while documentation exists",
                    description="This is a review prompt, not proof that documentation is stale.", affected_file=file_path,
                    line_range=f"{changed_line}-{changed_line}", evidence=[], dependency_path=[],
                    recommendation="Confirm whether the relevant documentation needs an update.", confidence="LOW",
                ))
    return AuditResponse(project_id=payload.project_id or project_index.root.name,
        findings=findings, summary=f"Audited {len(files)} changed file(s); produced {len(findings)} evidence-backed finding(s).")


@router.get("/drift-trend", response_model=DriftResponse)
def drift_trend() -> DriftResponse:
    manifest = Path(settings.HISTORICAL_SNAPSHOTS_MANIFEST)
    if not manifest.exists():
        return DriftResponse(timeline=[], biggest_positive_jump=None, source="historical snapshots are not available locally")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Unable to read historical snapshots: {exc}")
    timeline = [DriftPoint(commit=str(item.get("commit_hash", item.get("commit", "unknown"))),
        timestamp=str(item.get("timestamp", item.get("date", ""))),
        duplication_score=item.get("duplication_score"), affected_files=item.get("affected_files", []))
        for item in data.get("snapshots", [])]
    timeline.sort(key=lambda item: item.timestamp)
    jump = None
    for previous, current in zip(timeline, timeline[1:]):
        if previous.duplication_score is None or current.duplication_score is None:
            continue
        delta = round(current.duplication_score - previous.duplication_score, 6)
        if delta > 0 and (jump is None or delta > jump["increase"]):
            jump = {"commit": current.commit, "increase": delta, "previous_score": previous.duplication_score,
                    "new_score": current.duplication_score, "affected_files": current.affected_files}
    return DriftResponse(timeline=timeline, biggest_positive_jump=jump, source=str(manifest))
