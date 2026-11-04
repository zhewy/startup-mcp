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


BRAIN_INITIALIZATION_ID = "1bGVXeMqG899ScKLdADsyYtPP4tWOLyuA"
_LINK = re.compile(r"https://drive\.google\.com/file/d/([A-Za-z0-9_-]+)/view")


def _unique_link(content: str, label: str, pattern: str) -> str:
    matches = set()
    for line in content.splitlines():
        if re.search(pattern, line, re.IGNORECASE):
            # The first Drive link on a designation line is the current target;
            # later links are explicitly marked preserved or historical identities.
            links = _LINK.findall(line)
            if links:
                matches.add(links[0])
    if len(matches) != 1:
        raise ValueError(f"designation: {label} is {'missing' if not matches else 'ambiguous'}")
    return matches.pop()


def discover_sources(reader) -> list[dict]:
    """Follow explicit designations in Brain's initialization and routing documents."""
    bootstrap = reader.read(BRAIN_INITIALIZATION_ID)
    routing_id = _unique_link(bootstrap["content"], "routing", r"canonical routing guide|AI-canonicals — purpose and routing")
    routing = reader.read(routing_id)
    if not routing["content"].strip():
        raise ValueError("routing document is empty")
    base_id = _unique_link(routing["content"], "Base", r"Base \[Base Contract — Brain\]")
    bootstrap_base = _unique_link(bootstrap["content"], "Base", r"one designated Base Contract|Read Base \[Base Contract")
    if base_id != bootstrap_base:
        raise ValueError("designation: Base conflicts between initialization and routing")
    return [{"name": "initialization", "source_id": BRAIN_INITIALIZATION_ID},
            {"name": "routing", "source_id": routing_id},
            {"name": "base", "source_id": base_id}]


def _validate_cache(data: object) -> dict:
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("existing cache has invalid schema")
    if not isinstance(data.get("refreshed_at"), str) or not isinstance(data.get("verification"), str):
        raise ValueError("existing cache has missing metadata")
    datetime.fromisoformat(data["refreshed_at"].replace("Z", "+00:00"))
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("existing cache has invalid sources")
    names, ids = set(), set()
    for row in sources:
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k].strip()
            for k in ("name", "source_id", "title", "version", "modified_at", "content", "sha256")):
            raise ValueError("existing cache has missing source fields")
        if row["name"] in names or row["source_id"] in ids:
            raise ValueError("existing cache has duplicate identities")
        if row["sha256"] != _digest(row["content"]):
            raise ValueError("existing cache has invalid content hash")
        datetime.fromisoformat(row["modified_at"].replace("Z", "+00:00"))
        names.add(row["name"]); ids.add(row["source_id"])
    return data


def refresh_config(cache_path: Path, designation_path: Path | None = None, reader=None) -> dict:
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
        if designation_path is not None and cache_path.resolve() == designation_path.resolve():
            raise ValueError("cache path must differ from the designation file")
        if reader is None:
            from .auth import access_token, TOKEN
            reader = DriveReader(access_token(Path(os.environ.get("ZMCP_OAUTH_TOKEN", TOKEN))))
        entries = _designations(designation_path) if designation_path is not None else discover_sources(reader)
        receipt["sources"] = entries
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
        previous = _validate_cache(json.loads(cache_path.read_text(encoding="utf-8"))) if cache_path.exists() else None
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
        if _validate_cache(json.loads(temporary.read_text(encoding="utf-8"))) != candidate:
            raise ValueError("staged configuration did not validate")
        os.replace(temporary, cache_path)
        receipt.update(status="REFRESHED", cache_activated=True, refreshed_at=candidate["refreshed_at"])
    except Exception as exc:
        # Network exceptions can include sensitive transport information; report type only.
        safe = ("designation", "existing cache", "required designated", "invalid or empty source",
                "Drive authentication", "Install zmcp", "cache path", "source changed",
                "unsupported configuration", "staged configuration")
        message = str(exc) if isinstance(exc, ValueError) else ""
        receipt["errors"].append(message if message.startswith(safe) else type(exc).__name__)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                receipt["errors"].append("could not remove staged temporary file")
    return receipt
