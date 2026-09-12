"""Canonical internal contract shared by scanning, structure, and reasoning.

These models deliberately supplement the existing public reasoning schemas;
adapters in ``ProjectIndex`` keep Person 1 and Person 2 implementations
compatible without changing their native chunk/retrieval formats.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ProjectRecord(BaseModel):
    project_id: str
    root: str
    files: int
    languages: list[str] = Field(default_factory=list)


class FileRecord(BaseModel):
    path: str
    language: str
    status: Literal["created", "modified", "deleted", "renamed", "unchanged"]
    lines: int = 0


class ChangeRecord(BaseModel):
    path: str
    change_type: Literal["created", "modified", "deleted", "renamed", "unchanged"]
    old_path: Optional[str] = None
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    changed_lines: list[int] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SymbolRecord(BaseModel):
    symbol_id: str
    file: str
    name: str
    type: str
    parent: Optional[str] = None
    start_line: int
    end_line: int


class RelationshipRecord(BaseModel):
    source: str
    target: str
    relationship_type: str


class RetrievalRecord(BaseModel):
    chunk_id: str
    file: str
    symbol: Optional[str] = None
    start_line: int
    end_line: int
    content: str
    score: float
    source: Literal["vector", "deterministic"]


class AuditRequest(BaseModel):
    project_id: Optional[str] = None
    diff: str = Field(..., min_length=1)
    changed_files: list[str] = Field(default_factory=list)
    pr_number: Optional[str] = None
    title: Optional[str] = None


class AuditFinding(BaseModel):
    finding_id: str
    category: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    title: str
    description: str
    affected_file: str
    affected_symbol: Optional[str] = None
    line_range: Optional[str] = None
    evidence: list[dict] = Field(default_factory=list)
    dependency_path: list[str] = Field(default_factory=list)
    recommendation: str
    confidence: Literal["HIGH", "MEDIUM", "LOW"]


class AuditResponse(BaseModel):
    project_id: str
    findings: list[AuditFinding]
    summary: str


class DriftPoint(BaseModel):
    commit: str
    timestamp: str
    duplication_score: Optional[float] = None
    affected_files: list[str] = Field(default_factory=list)


class DriftResponse(BaseModel):
    timeline: list[DriftPoint]
    biggest_positive_jump: Optional[dict] = None
    source: str
