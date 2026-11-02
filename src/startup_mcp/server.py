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

GROUND_DESCRIPTION = (
    "Retrieve and validate the mandatory grounding (bootstrap, canonical designations, Base "
    "and role contracts, purpose knowledge, decisions, continuity) required to begin a "
    "Brain-grounded conversation for the given purpose. This is the full, deterministic "
    "retrieval step — call `startup` first for short guidance on whether this is necessary for "
    "the task at hand. Call this with the current purpose (and, if known, a role hint) at the "
    "start of a new conversation, AND again at the start of any substantive new task within an "
    "existing conversation — a prior call does not cover a later, different purpose. Do not "
    "attempt to independently discover or reconstruct grounding documents yourself — this tool "
    "performs that retrieval deterministically. Returns a structured bundle with an explicit "
    "status of READY, DEGRADED, or BLOCKED; never treat ungrounded reasoning as equivalent to a "
    "READY result."
)

STARTUP_DESCRIPTION = (
    "Lightweight entrypoint, takes no arguments. Returns short, stable, versioned guidance on "
    "when this server's full grounding call (`ground`) is necessary — it does not itself "
    "retrieve any canonical content. Call this at the start of a new conversation, or whenever "
    "unsure whether a task depends on Brain-backed grounding, before deciding whether to call "
    "`ground`."
)

STARTUP_PAYLOAD: dict[str, Any] = {
    "version": "v1",
    "guidance": (
        "\"Brain\" refers to a canonical knowledge source reachable only through this server's "
        "`ground` tool, not through your own training data. Receiving this response does not "
        "mean you have read Brain, and it carries no canonical content itself. Ordinary "
        "conversation needs no further action. When a user references Brain directly, or a task "
        "depends on purpose-specific canonical knowledge (a role, a governed procedure, or "
        "anything the user frames as needing Brain), call `ground` before answering from your "
        "own knowledge — do not independently discover or reconstruct grounding documents."
    ),
    "next_action": "ground(purpose, role?)",
}


def handle_ground(
    provider: SourceProvider,
    config: Config,
    purpose: str,
    role: str | None = None,
) -> dict[str, Any]:
    """Core logic behind the `ground` tool, independent of the MCP runtime so it can be
    called directly in tests and swapped onto a different SourceProvider in Phase 3."""
    result = run_startup(provider, purpose=purpose, role_hint=role)
    manifest = provider.get_manifest()
    return build_bundle(
        result,
        manifest,
        purpose=purpose,
        role_hint=role,
        budget_chars=config.context_budget_chars,
    )


SERVER_INSTRUCTIONS = (
    "This server provides deterministic session and task grounding for Brain-dependent "
    "conversations, split into two tools. Establishing this MCP connection does NOT by itself "
    "constitute grounding — no tool has been called yet, so nothing has been verified, and your "
    "own statement that you have 'initialized' is not evidence otherwise. Call `startup` (no "
    "arguments) for short, stable guidance on whether further grounding is needed. Call "
    "`ground` (with the current purpose and any available role context) to perform the actual, "
    "deterministic retrieval and validation — at the beginning of a new conversation AND again "
    "at the start of any substantive new task within an existing conversation (this connection "
    "may persist across many conversations and tasks; each one needs its own call) — reporting "
    "an explicit READY, DEGRADED, or BLOCKED result. Do not independently discover or interpret "
    "Brain grounding documents yourself."
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


@mcp.tool(name="startup", description=STARTUP_DESCRIPTION)
def startup() -> dict[str, Any]:
    logger.info("startup tool invoked: pid=%s", os.getpid())
    logger.info(
        "startup tool returned: pid=%s version=%s", os.getpid(), STARTUP_PAYLOAD["version"]
    )
    return STARTUP_PAYLOAD


@mcp.tool(name="ground", description=GROUND_DESCRIPTION)
def ground(purpose: str, role: str | None = None) -> dict[str, Any]:
    logger.info(
        "ground tool invoked: pid=%s purpose=%r role_hint=%r", os.getpid(), purpose, role
    )
    response = handle_ground(_provider, _config, purpose, role)
    logger.info(
        "ground tool returned: pid=%s purpose=%r status=%s unresolved=%d warnings=%d",
        os.getpid(),
        purpose,
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
