"""Explicit, read-only Brain comparison and transactional configuration snapshots."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_lock = Lock()


class DriveReader:
    """Read only specifically designated Drive files; never discover or write Brain."""

    verification = "live-brain"

    def __init__(self, token: str):
        self.token = token

    def _get(self, file_id: str, query: dict) -> bytes:
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?{urlencode(query)}"
        try:
            with urlopen(Request(url, headers={"Authorization": f"Bearer {self.token}"}), timeout=30) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code == 404:
                raise FileNotFoundError(file_id) from None
            # Do not propagate credentials, HTTP response bodies or URLs into receipts.
            raise ValueError(f"Drive read failed (HTTP {exc.code})") from None

    def read(self, file_id: str) -> dict:
        fields = "id,name,mimeType,version,modifiedTime,trashed"
        before = json.loads(self._get(file_id, {"fields": fields}))
        if before.get("trashed"):
            raise FileNotFoundError(file_id)
        mime = before["mimeType"]
        if mime == "application/vnd.google-apps.document":
            # export has a different path but the same fixed Google endpoint.
            content = self._get(file_id + "/export", {"mimeType": "text/plain"})
        elif mime in {"text/plain", "text/markdown", "application/json"}:
            content = self._get(file_id, {"alt": "media"})
        else:
            raise ValueError("unsupported configuration source type")
        if mime == "application/json":
            json.loads(content)
        after = json.loads(self._get(file_id, {"fields": fields}))
        if before != after or before.get("id") != file_id:
            raise ValueError("source changed during retrieval or identity mismatch")
        return {"source_id": file_id, "title": before["name"],
                "version": before["version"], "modified_at": before["modifiedTime"],
                "content": content.decode("utf-8")}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _designations(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data["sources"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("sources must be a nonempty list")
    names, ids = set(), set()
    for entry in entries:
        name, sid = entry["name"], entry["source_id"]
        if not isinstance(name, str) or not name.strip() or not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", sid):
            raise ValueError("invalid source identity")
        if name in names or sid in ids:
            raise ValueError("duplicate designation")
        names.add(name)
        ids.add(sid)
    return [{"name": e["name"], "source_id": e["source_id"]} for e in entries]


def refresh_config(cache_path: Path, designation_path: Path | None, reader=None) -> dict:
    """Stage every designated source, validate, then atomically replace a single snapshot.

    Every designated item is required. A fixture reader may exercise the transaction but
    its receipt can never assert live Brain verification.
    """
    with _lock:
        return _refresh(cache_path, designation_path, reader)


def _refresh(cache_path: Path, designation_path: Path | None, reader) -> dict:
    receipt = {"operation": "refresh-config", "status": "FAILED", "current": None,
               "checked_at": datetime.now(timezone.utc).isoformat(), "refreshed_at": None,
               "verification": "unverified", "live_brain_verified": False,
               "sources": [], "changes": [], "missing": [], "errors": [],
               "cache_activated": False}
    temporary = None
    try:
        if designation_path is None:
            raise ValueError("ZMCP_CONFIG_SOURCES is not configured")
        if cache_path.resolve() == designation_path.resolve():
            raise ValueError("cache path must differ from the designation file")
        entries = _designations(designation_path)
        receipt["sources"] = entries
        if reader is None:
            token = os.environ.get("ZMCP_DRIVE_ACCESS_TOKEN")
            if not token:
                raise ValueError("ZMCP_DRIVE_ACCESS_TOKEN is not configured")
            reader = DriveReader(token)
        records = []
        for entry in entries:
            try:
                record = reader.read(entry["source_id"])
            except FileNotFoundError:
                receipt["missing"].append(entry)
                continue
            if (record["source_id"] != entry["source_id"] or
                    not all(isinstance(record.get(k), str) and record[k].strip()
                            for k in ("title", "version", "modified_at", "content"))):
                raise ValueError(f"invalid or empty source: {entry['name']}")
            datetime.fromisoformat(record["modified_at"].replace("Z", "+00:00"))
            records.append({**record, "name": entry["name"], "sha256": _digest(record["content"])})
        if receipt["missing"]:
            raise ValueError("required designated material is missing")
        # Successful fixture retrieval must never be reported as a live check.
        live = type(reader) is DriveReader
        receipt["verification"] = "live-brain" if live else "fixture-or-test"
        receipt["live_brain_verified"] = live
        receipt["sources"] = [{k: v for k, v in r.items() if k != "content"} for r in records]
        previous = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else None
        old = {r["name"]: r for r in previous["sources"]} if previous else {}
        new = {r["name"]: r for r in records}
        for name in sorted(old.keys() | new.keys()):
            if old.get(name) != new.get(name):
                receipt["changes"].append({"name": name, "kind": "added" if name not in old else "removed" if name not in new else "changed",
                                           "previous": old.get(name, {}).get("sha256"), "replacement": new.get(name, {}).get("sha256")})
        receipt["current"] = not bool(receipt["changes"])
        if receipt["current"]:
            receipt.update(status="CURRENT", refreshed_at=previous["refreshed_at"])
            return receipt
        candidate = {"schema_version": 1, "refreshed_at": receipt["checked_at"],
                     "verification": receipt["verification"], "sources": records}
        encoded = json.dumps(candidate, ensure_ascii=False, indent=2)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=cache_path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if json.loads(temporary.read_text(encoding="utf-8")) != candidate:
            raise ValueError("staged configuration did not validate")
        os.replace(temporary, cache_path)
        receipt.update(status="REFRESHED", cache_activated=True, refreshed_at=candidate["refreshed_at"])
    except Exception as exc:
        # Network exceptions can include sensitive transport information; report type only.
        receipt["errors"].append(str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                receipt["errors"].append("could not remove staged temporary file")
    return receipt
