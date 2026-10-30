from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from .bundle import build_bundle
from .config import Config
from .procedure import run_startup
from .sources.base import SourceProvider
from .sources.fixture import FixtureSourceProvider

TOOL_DESCRIPTION = (
    "Retrieve and validate the mandatory grounding (bootstrap, canonical designations, Base "
    "and role contracts, topic knowledge, decisions, continuity) required to begin a "
    "Brain-grounded conversation on the given topic. Call this once, before any other "
    "reasoning about the topic, at the start of a new conversation. Do not attempt to "
    "independently discover or reconstruct grounding documents yourself — this tool performs "
    "that retrieval deterministically. Returns a structured bundle with an explicit status of "
    "READY, DEGRADED, or BLOCKED; never treat ungrounded reasoning as equivalent to a READY "
    "result."
)


def handle_startup(
    provider: SourceProvider,
    config: Config,
    topic: str,
    role: str | None = None,
) -> dict[str, Any]:
    """Core logic behind the `startup` tool, independent of the MCP runtime so it can be
    called directly in tests and swapped onto a different SourceProvider in Phase 3."""
    result = run_startup(provider, topic=topic, role_hint=role)
    manifest = provider.get_manifest()
    return build_bundle(
        result,
        manifest,
        topic=topic,
        role_hint=role,
        budget_chars=config.context_budget_chars,
    )


mcp = MCPServer(
    name="startup-mcp",
    instructions=(
        "Call the `startup` tool once, at the beginning of any Brain-dependent conversation, "
        "before reasoning about the requested topic yourself. Do not independently discover or "
        "interpret Brain grounding documents — this server performs that retrieval and "
        "validation deterministically and returns a READY/DEGRADED/BLOCKED result."
    ),
)

_config = Config.from_env()
_provider = FixtureSourceProvider(_config.fixture_root)


@mcp.tool(name="startup", description=TOOL_DESCRIPTION)
def startup(topic: str, role: str | None = None) -> dict[str, Any]:
    return handle_startup(_provider, _config, topic, role)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
