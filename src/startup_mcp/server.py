from __future__ import annotations

import logging
import os
import sys
from typing import Any

from mcp.server.mcpserver import MCPServer

from .bundle import build_bundle
from .config import Config
from .procedure import run_startup
from .sources.base import SourceProvider
from .sources.fixture import FixtureSourceProvider

# stdout is reserved for the MCP JSON-RPC stream over stdio; all diagnostics go to stderr,
# which desktop clients typically capture into their own MCP server log files. This exists so
# the initialization/invocation experiment in docs/08 produces inspectable evidence instead of
# relying on the model's own account of what it did.
logging.basicConfig(
    level=os.environ.get("STARTUP_MCP_LOG_LEVEL", "INFO").upper(),
    stream=sys.stderr,
    format="%(asctime)s startup-mcp %(levelname)s %(message)s",
)
logger = logging.getLogger("startup_mcp")

TOOL_DESCRIPTION = (
    "Retrieve and validate the mandatory grounding (bootstrap, canonical designations, Base "
    "and role contracts, topic knowledge, decisions, continuity) required to begin a "
    "Brain-grounded conversation on the given topic. Call this with the current topic (and, if "
    "known, a role hint) at the start of a new conversation, AND again at the start of any "
    "substantive new task within an existing conversation — a prior call does not cover a "
    "later, different task. Do not attempt to independently discover or reconstruct grounding "
    "documents yourself — this tool performs that retrieval deterministically. Returns a "
    "structured bundle with an explicit status of READY, DEGRADED, or BLOCKED; never treat "
    "ungrounded reasoning as equivalent to a READY result."
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


SERVER_INSTRUCTIONS = (
    "This server provides deterministic session and task grounding for Brain-dependent "
    "conversations. Establishing this MCP connection does NOT by itself constitute grounding — "
    "no tool has been called yet, so nothing has been verified. Call the `startup` tool, with "
    "the current topic and any available role context, at the beginning of a new conversation "
    "AND again at the start of any substantive new task within an existing conversation (this "
    "connection may persist across many conversations and tasks; each one needs its own call). "
    "Do not independently discover or interpret Brain grounding documents — this server "
    "performs that retrieval and validation deterministically and reports an explicit READY, "
    "DEGRADED, or BLOCKED result. Do not treat a successful connection, or your own statement "
    "that you have 'initialized', as evidence of grounding."
)

mcp = MCPServer(
    name="startup-mcp",
    instructions=SERVER_INSTRUCTIONS,
)

_config = Config.from_env()
_provider = FixtureSourceProvider(_config.fixture_root)
logger.info(
    "startup-mcp process starting: pid=%s fixture_root=%s context_budget_chars=%s",
    os.getpid(),
    _config.fixture_root,
    _config.context_budget_chars,
)


@mcp.tool(name="startup", description=TOOL_DESCRIPTION)
def startup(topic: str, role: str | None = None) -> dict[str, Any]:
    logger.info("startup tool invoked: pid=%s topic=%r role_hint=%r", os.getpid(), topic, role)
    response = handle_startup(_provider, _config, topic, role)
    logger.info(
        "startup tool returned: pid=%s topic=%r status=%s unresolved=%d warnings=%d",
        os.getpid(),
        topic,
        response["status"],
        len(response["unresolved"]),
        len(response["warnings"]),
    )
    return response


def main() -> None:
    logger.info("startup-mcp entering stdio serve loop: pid=%s", os.getpid())
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
