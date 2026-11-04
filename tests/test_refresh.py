import json
from pathlib import Path

import pytest

from zmcp.refresh import DriveReader, refresh_config
from zmcp.server import mcp, startup


class FixtureReader:
    def __init__(self):
        self.content = "configuration text"
        self.missing = set()

    def read(self, sid):
        if sid in self.missing:
            raise FileNotFoundError(sid)
        return {"source_id": sid, "title": "Config", "version": "1",
                "modified_at": "2026-11-04T00:00:00Z", "content": self.content}


@pytest.fixture
def setup(tmp_path):
    designations = tmp_path / "designations.json"
    designations.write_text(json.dumps({"sources": [{"name": "initialization", "source_id": "brain-id"}]}))
    return tmp_path / "cache.json", designations, FixtureReader()


def test_create_current_change_and_receipts(setup):
    cache, sources, reader = setup
    first = refresh_config(cache, sources, reader)
    assert first["status"] == "REFRESHED"
    assert first["current"] is False
    assert first["cache_activated"]
    assert first["sources"][0]["source_id"] == "brain-id"
    assert first["refreshed_at"]
    assert not first["live_brain_verified"]
    assert first["verification"] == "fixture-or-test"
    original = cache.read_bytes()
    current = refresh_config(cache, sources, reader)
    assert current["status"] == "CURRENT"
    assert current["current"] is True
    assert current["refreshed_at"] == first["refreshed_at"]
    assert cache.read_bytes() == original
    reader.content = "updated text, same version"
    changed = refresh_config(cache, sources, reader)
    assert changed["status"] == "REFRESHED"
    assert changed["changes"][0]["kind"] == "changed"
    assert json.loads(cache.read_text())["sources"][0]["content"] == reader.content


@pytest.mark.parametrize("failure", ["missing", "empty", "invalid", "network", "replace", "stage"])
def test_failure_preserves_previous_cache(setup, monkeypatch, failure):
    cache, sources, reader = setup
    refresh_config(cache, sources, reader)
    original = cache.read_bytes()
    reader.content = "changed"
    if failure == "missing":
        reader.missing.add("brain-id")
    elif failure == "empty":
        reader.content = "  "
    elif failure == "invalid":
        sources.write_text('{"sources": []}')
    elif failure == "network":
        def broken(sid):
            raise ConnectionError("secret-token")
        reader.read = broken
    elif failure == "replace":
        def broken(*args):
            raise OSError("disk failure")
        monkeypatch.setattr("zmcp.refresh.os.replace", broken)
    else:
        monkeypatch.setattr("zmcp.refresh.os.fsync", lambda *a: (_ for _ in ()).throw(OSError()))
    result = refresh_config(cache, sources, reader)
    assert result["status"] == "FAILED"
    assert not result["cache_activated"]
    assert result["errors"]
    assert "secret-token" not in json.dumps(result)
    assert cache.read_bytes() == original
    assert sorted(p.name for p in cache.parent.iterdir()) == ["cache.json", "designations.json"]
    if failure == "missing":
        assert result["missing"][0]["source_id"] == "brain-id"


def test_unconfigured_and_no_cache(setup, monkeypatch):
    cache, sources, _ = setup
    monkeypatch.delenv("ZMCP_DRIVE_ACCESS_TOKEN", raising=False)
    assert refresh_config(cache, None)["status"] == "FAILED"
    assert refresh_config(cache, sources)["live_brain_verified"] is False
    assert not cache.exists()


def test_removed_designation_reported(setup):
    cache, sources, reader = setup
    refresh_config(cache, sources, reader)
    sources.write_text(json.dumps({"sources": [{"name": "base", "source_id": "base-id"}]}))
    result = refresh_config(cache, sources, reader)
    assert {c["kind"] for c in result["changes"]} == {"added", "removed"}


@pytest.mark.parametrize("native", [True, False])
def test_drive_reads_metadata_twice_and_content(monkeypatch, native):
    reader = DriveReader("test-secret")
    meta = {"id": "brain-id", "name": "Initialization", "version": "1",
            "modifiedTime": "2026-11-04T00:00:00Z", "trashed": False,
            "mimeType": "application/vnd.google-apps.document" if native else "text/plain"}
    calls = []
    def get(sid, query):
        calls.append((sid, query))
        return json.dumps(meta).encode() if "fields" in query else b"configuration"
    monkeypatch.setattr(reader, "_get", get)
    result = reader.read("brain-id")
    assert result["content"] == "configuration"
    assert calls[0] == calls[2]
    assert calls[1][0] == ("brain-id/export" if native else "brain-id")


def test_drive_racing_revision_rejected(monkeypatch):
    reader = DriveReader("test")
    responses = iter([json.dumps({"id": "x", "mimeType": "text/plain", "version": "1"}).encode(),
                      b"content", json.dumps({"id": "x", "version": "2"}).encode()])
    monkeypatch.setattr(reader, "_get", lambda *args: next(responses))
    with pytest.raises(ValueError, match="changed"):
        reader.read("x")


def test_startup_does_not_refresh(monkeypatch):
    def forbidden(*a, **kw):
        raise AssertionError("automatic refresh")
    monkeypatch.setattr("zmcp.server.run_refresh_config", forbidden)
    assert startup() == "to be defined"


def test_tool_registered():
    import asyncio
    tools = asyncio.run(mcp.list_tools())
    assert "refresh-config" in {tool.name for tool in tools}


def test_designation_file_cannot_be_cache(setup):
    _, sources, reader = setup
    original = sources.read_bytes()
    assert refresh_config(sources, sources, reader)["status"] == "FAILED"
    assert sources.read_bytes() == original


def test_all_missing_sources_reported_without_first_cache(setup):
    cache, sources, reader = setup
    sources.write_text(json.dumps({"sources": [{"name": sid, "source_id": sid} for sid in ("a", "b")]}))
    reader.missing = {"a", "b"}
    result = refresh_config(cache, sources, reader)
    assert {e["source_id"] for e in result["missing"]} == {"a", "b"}
    assert not cache.exists()
    assert not result["live_brain_verified"]


@pytest.mark.parametrize("field,value", [("source_id", "wrong"), ("version", ""), ("modified_at", "invalid")])
def test_invalid_record_rejected(setup, field, value):
    cache, sources, reader = setup
    original_read = reader.read
    def read(sid):
        return {**original_read(sid), field: value}
    reader.read = read
    assert refresh_config(cache, sources, reader)["status"] == "FAILED"
    assert not cache.exists()


def test_duplicate_designation_rejected(setup):
    cache, sources, reader = setup
    entry = {"name": "a", "source_id": "a"}
    sources.write_text(json.dumps({"sources": [entry, entry]}))
    assert refresh_config(cache, sources, reader)["status"] == "FAILED"
    assert not cache.exists()


def test_invalid_json_source_rejected(monkeypatch):
    reader = DriveReader("test")
    meta = {"id": "x", "mimeType": "application/json"}
    monkeypatch.setattr(reader, "_get", lambda sid, query: json.dumps(meta).encode() if "fields" in query else b"{invalid")
    with pytest.raises(ValueError):
        reader.read("x")

class RoutingReader(FixtureReader):
    def __init__(self, *, conflict=False, missing=False):
        super().__init__()
        self.conflict, self.missing_route = conflict, missing

    def read(self, sid):
        from zmcp.refresh import BRAIN_INITIALIZATION_ID
        route = "https://drive.google.com/file/d/routing123/view"
        base = "https://drive.google.com/file/d/base123/view"
        if sid == BRAIN_INITIALIZATION_ID:
            content = ("Read the canonical routing guide " + ("" if self.missing_route else route) + "\n"
                       "The one designated Base Contract is " + base)
        elif sid == "routing123":
            content = "Base [Base Contract — Brain](https://drive.google.com/file/d/" + ("other123" if self.conflict else "base123") + "/view)"
        else:
            content = "contract"
        return {"source_id": sid, "title": sid, "version": "1", "modified_at": "2026-11-04T00:00:00Z", "content": content}


def test_discovery_from_brain_route(tmp_path):
    from zmcp.refresh import BRAIN_INITIALIZATION_ID
    cache = tmp_path / "cache.json"
    result = refresh_config(cache, reader=RoutingReader())
    assert result["status"] == "REFRESHED"
    assert [x["source_id"] for x in result["sources"]] == [BRAIN_INITIALIZATION_ID, "routing123", "base123"]
    assert refresh_config(cache, reader=RoutingReader())["status"] == "CURRENT"


@pytest.mark.parametrize("reader,error", [(RoutingReader(missing=True), "designation: routing is missing"),
                                          (RoutingReader(conflict=True), "conflicts")])
def test_discovery_fails_closed(tmp_path, reader, error):
    result = refresh_config(tmp_path / "cache.json", reader=reader)
    assert result["status"] == "FAILED"
    assert error in result["errors"][0]


@pytest.mark.parametrize("damage", ["schema", "field", "duplicate", "hash"])
def test_corrupt_cache_is_preserved(setup, damage):
    cache, sources, reader = setup
    refresh_config(cache, sources, reader)
    data = json.loads(cache.read_text())
    if damage == "schema":
        data["schema_version"] = 99
    elif damage == "field":
        del data["sources"][0]["title"]
    elif damage == "duplicate":
        data["sources"].append(data["sources"][0].copy())
    else:
        data["sources"][0]["sha256"] = "0" * 64
    cache.write_text(json.dumps(data))
    evidence = cache.read_bytes()
    reader.content = "new"
    result = refresh_config(cache, sources, reader)
    assert result["status"] == "FAILED"
    assert cache.read_bytes() == evidence


def test_missing_credentials_do_not_leak(setup, monkeypatch):
    cache, _, _ = setup
    monkeypatch.setattr("zmcp.auth.access_token", lambda *a: (_ for _ in ()).throw(ValueError("Drive authentication required: run zmcp-auth once locally")))
    result = refresh_config(cache)
    assert result["status"] == "FAILED"
    assert not cache.exists()

def test_oauth_renewal_failure_is_sanitized(tmp_path, monkeypatch):
    from zmcp import auth
    token_file = tmp_path / "token.json"
    token_file.write_text("private credential")
    class Credentials:
        valid = False
        refresh_token = "secret-refresh-token"
        @staticmethod
        def from_authorized_user_file(*args):
            return Credentials()
        def has_scopes(self, scopes):
            return True
        def refresh(self, request):
            raise RuntimeError("secret-refresh-token")
    monkeypatch.setattr(auth, "_dependencies", lambda: (Credentials, object, object))
    with pytest.raises(ValueError, match="Drive authentication failed") as error:
        auth.access_token(token_file)
    assert "secret-refresh-token" not in str(error.value)
    assert token_file.read_text() == "private credential"


def test_ambiguous_routing_designation(tmp_path):
    reader = RoutingReader()
    original = reader.read
    def read(sid):
        row = original(sid)
        if row["source_id"] == "1bGVXeMqG899ScKLdADsyYtPP4tWOLyuA":
            row["content"] += "\nRead the canonical routing guide https://drive.google.com/file/d/another123/view"
        return row
    reader.read = read
    result = refresh_config(tmp_path / "cache.json", reader=reader)
    assert result["status"] == "FAILED"
    assert "ambiguous" in result["errors"][0]
