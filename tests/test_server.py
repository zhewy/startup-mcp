import copy
import json
import shutil
from pathlib import Path

from startup_mcp.config import Config
from startup_mcp.server import STARTUP_PAYLOAD, handle_ground, startup
from startup_mcp.sources.fixture import FixtureSourceProvider

DEFAULT_FIXTURE_ROOT = (
    Path(__file__).parent.parent / "src" / "startup_mcp" / "fixtures" / "default"
)


def _copy_fixture(tmp_path: Path) -> Path:
    dest = tmp_path / "fixture"
    shutil.copytree(DEFAULT_FIXTURE_ROOT, dest)
    return dest


def _provider(root: Path) -> FixtureSourceProvider:
    return FixtureSourceProvider(root)


def _config(root: Path, budget: int = 100_000) -> Config:
    return Config(fixture_root=root, context_budget_chars=budget)


def test_devotions_purpose_produces_relevant_grounding(tmp_path):
    root = _copy_fixture(tmp_path)
    result = handle_ground(_provider(root), _config(root), purpose="devotions")

    assert result["status"] == "READY"
    purpose_ids = {entry["source_id"] for entry in result["grounding"]["purpose_context"]}
    assert "purpose_devotions" in purpose_ids
    assert result["grounding"]["role_contract"]["resolved_role"] == "chaplain"


def test_devotionals_purpose_advises_devotional(tmp_path):
    root = _copy_fixture(tmp_path)
    result = handle_ground(_provider(root), _config(root), purpose="devotionals")

    assert result["status"] == "READY"
    purpose_contents = [entry["content"] for entry in result["grounding"]["purpose_context"]]
    assert "this is devotional purpose" in purpose_contents
    assert result["grounding"]["role_contract"]["resolved_role"] == "chaplain"


def test_librarian_purpose_advises_librarian(tmp_path):
    root = _copy_fixture(tmp_path)
    result = handle_ground(_provider(root), _config(root), purpose="librarian")

    assert result["status"] == "READY"
    purpose_contents = [entry["content"] for entry in result["grounding"]["purpose_context"]]
    assert "this is librarian" in purpose_contents
    assert result["grounding"]["role_contract"]["resolved_role"] == "librarian"


def test_unmapped_purpose_does_not_fully_activate(tmp_path):
    root = _copy_fixture(tmp_path)
    result = handle_ground(_provider(root), _config(root), purpose="some-unmapped-purpose")

    # No purpose knowledge and no role mapping exist for this purpose, so it degrades rather
    # than silently pretending to be grounded for a purpose the fixture knows nothing about.
    assert result["status"] == "DEGRADED"
    assert result["grounding"]["purpose_context"] == []
    assert result["grounding"]["role_contract"] is None
    assert any("no purpose-specific knowledge indexed" in w for w in result["warnings"])
    assert any("no canonical role mapping found" in w for w in result["warnings"])


def test_determinism_across_identical_calls(tmp_path):
    root = _copy_fixture(tmp_path)
    provider = _provider(root)
    config = _config(root)

    first = handle_ground(provider, config, purpose="devotions")
    second = handle_ground(provider, config, purpose="devotions")

    first_stable = copy.deepcopy(first)
    second_stable = copy.deepcopy(second)
    del first_stable["receipt"]["generated_at"]
    del second_stable["receipt"]["generated_at"]

    assert first_stable == second_stable


def test_missing_mandatory_source_blocks(tmp_path):
    root = _copy_fixture(tmp_path)
    (root / "sources" / "base_contract.json").unlink()

    result = handle_ground(_provider(root), _config(root), purpose="devotions")

    assert result["status"] == "BLOCKED"
    assert any("base_contract" in item for item in result["unresolved"])
    # A BLOCKED result must not silently proceed with mandatory grounding missing.
    assert result["grounding"]["base_contract"] is None


def test_optional_source_missing_degrades_not_blocks(tmp_path):
    root = _copy_fixture(tmp_path)
    (root / "sources" / "continuity_001.json").unlink()

    result = handle_ground(_provider(root), _config(root), purpose="devotions")

    assert result["status"] == "DEGRADED"
    assert result["unresolved"] == []
    assert any("continuity_001" in warning for warning in result["warnings"])


def test_sources_retain_provenance(tmp_path):
    root = _copy_fixture(tmp_path)
    result = handle_ground(_provider(root), _config(root), purpose="devotions")

    assert result["sources"], "expected at least one consulted source"
    for entry in result["sources"]:
        assert entry["source_id"]
        assert entry["version"]
        assert entry["fetched_at"]
        assert isinstance(entry["mandatory"], bool)


def test_role_hint_is_advisory_only(tmp_path):
    root = _copy_fixture(tmp_path)
    result = handle_ground(
        _provider(root), _config(root), purpose="devotions", role="not-the-real-role"
    )

    # The resolved role comes from canonical data, not the caller-supplied hint.
    assert result["grounding"]["role_contract"]["resolved_role"] == "chaplain"
    assert any("role hint" in warning for warning in result["warnings"])
    assert result["status"] == "READY"


def test_write_authority_floor_overrides_source_data(tmp_path):
    root = _copy_fixture(tmp_path)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["write_authority"] = True
    manifest_path.write_text(json.dumps(manifest))

    result = handle_ground(_provider(root), _config(root), purpose="devotions")

    assert result["permissions"]["write_authority"] is False
    assert any("write_authority" in warning for warning in result["warnings"])


def test_conflicting_mandatory_sources_block(tmp_path):
    root = _copy_fixture(tmp_path)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["mandatory_source_ids"].append("conflict_a")
    manifest_path.write_text(json.dumps(manifest))

    (root / "sources" / "conflict_a.json").write_text(
        json.dumps(
            {
                "id": "conflict_a",
                "title": "Conflicting designation (test fixture)",
                "version": "v1",
                "fetched_at": "2026-10-01T00:00:00+00:00",
                "mandatory": True,
                "conflicts_with": ["base_contract"],
                "content": "This source deliberately conflicts with base_contract.",
            }
        )
    )

    result = handle_ground(_provider(root), _config(root), purpose="devotions")

    assert result["status"] == "BLOCKED"
    assert any("conflict" in item.lower() for item in result["unresolved"])


def test_budget_truncation_drops_lowest_priority_content_first(tmp_path):
    root = _copy_fixture(tmp_path)
    continuity_path = root / "sources" / "continuity_001.json"
    data = json.loads(continuity_path.read_text())
    data["content"] = "x" * 10_000
    continuity_path.write_text(json.dumps(data))

    result = handle_ground(_provider(root), _config(root, budget=200), purpose="devotions")

    assert result["grounding"]["continuity"] == []
    assert any("dropped continuity entry" in warning for warning in result["warnings"])
    # The source is still listed in the provenance ledger even though its content was dropped.
    assert any(entry["source_id"] == "continuity_001" for entry in result["sources"])


def test_startup_returns_versioned_guidance():
    result = startup()

    assert result == STARTUP_PAYLOAD
    assert result["version"] == "v1"
    assert "ground" in result["guidance"]
    assert result["next_action"] == "ground(purpose, role?)"


def test_startup_is_static_and_deterministic():
    # No provider/fixture argument exists on this tool's signature at all — this is the
    # structural guarantee that it can't retrieve canonical content, not just an observed
    # behavior.
    first = startup()
    second = startup()

    assert first == second
