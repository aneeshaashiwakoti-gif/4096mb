"""Project connection, local index, and live-change API.

Both `/project` and `/projects` are retained: the former was introduced by the
local-agent route and the latter is already used by the shipped frontend.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.indexing.service import IGNORED_DIRECTORIES, project_index

router = APIRouter(tags=["Projects"])
active_connections: list[WebSocket] = []
event_loop: asyncio.AbstractEventLoop | None = None
observer = None


class ProjectSetRequest(BaseModel):
    path: str = Field(..., min_length=1)


class ImpactRequest(BaseModel):
    file: str
    symbol: Optional[str] = None
    change_type: str = "UNKNOWN"


def _http_error(error: Exception) -> HTTPException:
    message = str(error)
    return HTTPException(status_code=400 if "outside" not in message else 403, detail=message)


async def broadcast_file_change(file_path: str, change_type: str = "modified") -> None:
    """Tell clients only after the local index has been incrementally updated."""
    if project_index.connected and change_type != "deleted":
        try:
            project_index.update_file(project_index.resolve(file_path))
        except (ValueError, OSError):
            return
    elif change_type == "deleted":
        project_index.remove_file(file_path)
    try:
        impact = project_index.impact(file_path).model_dump(mode="json") if change_type != "deleted" else None
    except ValueError:
        impact = None
    message = json.dumps({"type": "file_event", "file": file_path, "change_type": change_type,
                          "index_status": project_index.index_status(), "impact": impact})
    stale = []
    for connection in active_connections:
        try:
            await connection.send_text(message)
        except Exception:
            stale.append(connection)
    for connection in stale:
        if connection in active_connections:
            active_connections.remove(connection)


try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    class ProjectWatcher(FileSystemEventHandler):
        def _notify(self, src_path: str, kind: str) -> None:
            if not event_loop or not project_index.root:
                return
            try:
                relative = project_index._relative(Path(src_path))
            except ValueError:
                return
            if any(part in IGNORED_DIRECTORIES for part in Path(relative).parts):
                return
            asyncio.run_coroutine_threadsafe(broadcast_file_change(relative, kind), event_loop)

        def on_modified(self, event):
            if not event.is_directory:
                self._notify(event.src_path, "modified")

        def on_created(self, event):
            if not event.is_directory:
                self._notify(event.src_path, "created")

        def on_deleted(self, event):
            if not event.is_directory:
                self._notify(event.src_path, "deleted")
except ImportError:
    Observer = None
    ProjectWatcher = None


class PollingProjectWatcher:
    """Dependency-free local watcher used only when watchdog is unavailable."""
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._snapshot: dict[str, tuple[int, int]] = {}
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        def run() -> None:
            while not self._stop.wait(0.5):
                current: dict[str, tuple[int, int]] = {}
                for path in project_index.scan_files():
                    try:
                        relative = project_index._relative(path)
                        stat = path.stat()
                        current[relative] = (stat.st_mtime_ns, stat.st_size)
                    except OSError:
                        continue
                for relative, fingerprint in current.items():
                    if relative not in self._snapshot:
                        kind = "created"
                    elif self._snapshot[relative] != fingerprint:
                        kind = "modified"
                    else:
                        continue
                    if event_loop:
                        asyncio.run_coroutine_threadsafe(broadcast_file_change(relative, kind), event_loop)
                for relative in set(self._snapshot) - set(current):
                    if event_loop:
                        asyncio.run_coroutine_threadsafe(broadcast_file_change(relative, "deleted"), event_loop)
                self._snapshot = current
        self._thread = threading.Thread(target=run, name="sentinel-project-watch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)


def _start_watcher() -> bool:
    global observer
    if observer:
        observer.stop()
        observer.join(timeout=2)
        observer = None
    if not project_index.root:
        return False
    if Observer and ProjectWatcher:
        observer = Observer()
        observer.schedule(ProjectWatcher(), str(project_index.root), recursive=True)
    else:
        observer = PollingProjectWatcher()
    observer.start()
    return True


async def _connect(req: ProjectSetRequest) -> dict:
    global event_loop
    try:
        event_loop = asyncio.get_running_loop()
        state = project_index.connect(req.path)
    except ValueError as error:
        raise _http_error(error)
    return {"status": "connected", "project": str(project_index.root), "index": state,
            "watcher_active": _start_watcher()}


@router.post("/project/connect")
@router.post("/projects/connect")
async def connect_project(req: ProjectSetRequest):
    return await _connect(req)


@router.get("/project/files")
@router.get("/projects/files")
def list_files(dir_path: Optional[str] = None):
    try:
        return {"files": project_index.tree(dir_path or "")}
    except ValueError as error:
        raise _http_error(error)


@router.get("/project/file/content")
@router.get("/projects/file/content")
def read_file(path: str = Query(..., min_length=1)):
    try:
        target = project_index.resolve(path)
        if not target.is_file() or not project_index.is_indexable(target):
            raise HTTPException(status_code=404, detail="Source file not found or not available for indexing.")
        relative = project_index._relative(target)
        chunks = project_index.chunks_by_file.get(relative, [])
        return {"path": relative, "content": target.read_text(encoding="utf-8", errors="replace"),
                "language": chunks[0].language if chunks else None}
    except HTTPException:
        raise
    except (ValueError, OSError) as error:
        raise _http_error(error)


@router.get("/project/index/status")
@router.get("/projects/index/status")
def index_status():
    return project_index.index_status()


@router.get("/project/search")
@router.get("/projects/search")
def search(query: str = Query(..., min_length=1), limit: int = Query(8, ge=1, le=50)):
    if not project_index.connected:
        raise HTTPException(status_code=400, detail="No active project")
    return {"query": query, "results": project_index.search(query, limit)}


@router.get("/project/dependencies")
@router.get("/projects/dependencies")
def dependencies(target: str = Query(..., min_length=1)):
    if not project_index.connected:
        raise HTTPException(status_code=400, detail="No active project")
    return project_index.dependencies(target)


@router.post("/project/impact")
@router.post("/projects/impact")
def analyze_local_impact(payload: ImpactRequest):
    try:
        return project_index.impact(payload.file, payload.symbol, payload.change_type)
    except ValueError as error:
        raise _http_error(error)


async def _websocket(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)


@router.websocket("/project/ws")
@router.websocket("/projects/ws")
async def websocket_endpoint(websocket: WebSocket):
    await _websocket(websocket)
