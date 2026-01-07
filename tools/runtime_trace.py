from __future__ import annotations

import atexit
import json
import os
import sys
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_DIRS = {
    "application",
    "config",
    "domain",
    "infrastructure",
    "services",
    "ui",
}
DEFAULT_OUTPUT = ROOT / "tmp_blobs" / "runtime_trace.json"

_calls: Counter[tuple[str, int, str]] = Counter()
_lock = threading.Lock()
_path_cache: dict[str, bool] = {}


def _should_trace(filename: str) -> bool:
    if not filename:
        return False
    cached = _path_cache.get(filename)
    if cached is not None:
        return cached
    try:
        path = Path(filename).resolve()
    except Exception:
        _path_cache[filename] = False
        return False
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        _path_cache[filename] = False
        return False
    if not rel.parts:
        _path_cache[filename] = False
        return False
    if rel.parts[0] not in ALLOWED_DIRS:
        _path_cache[filename] = False
        return False
    if rel.parts[0] == "tools":
        _path_cache[filename] = False
        return False
    _path_cache[filename] = True
    return True


def _profile(frame, event: str, arg: Any) -> None:
    if event != "call":
        return
    filename = frame.f_code.co_filename
    if not _should_trace(filename):
        return
    try:
        rel = Path(filename).resolve().relative_to(ROOT)
    except Exception:
        return
    name = frame.f_code.co_name
    cls = ""
    if "self" in frame.f_locals:
        cls = frame.f_locals["self"].__class__.__name__
    elif "cls" in frame.f_locals and isinstance(frame.f_locals["cls"], type):
        cls = frame.f_locals["cls"].__name__
    qualname = f"{cls}.{name}" if cls else name
    key = (str(rel).replace("\\", "/"), frame.f_code.co_firstlineno, qualname)
    with _lock:
        _calls[key] += 1


def _write_report(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for (file_path, line, qualname), count in sorted(_calls.items()):
        records.append(
            {
                "file": file_path,
                "line": line,
                "qualname": qualname,
                "count": count,
            }
        )
    payload = {
        "root": str(ROOT),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "records": records,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def install_trace(output_path: str | Path | None = None) -> Path:
    path = Path(output_path) if output_path else Path(
        os.environ.get("FF_TRACE_PATH", str(DEFAULT_OUTPUT))
    )

    def _on_exit() -> None:
        _write_report(path)

    atexit.register(_on_exit)
    sys.setprofile(_profile)
    threading.setprofile(_profile)
    return path
