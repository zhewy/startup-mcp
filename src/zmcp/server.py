from __future__ import annotations

import logging
import os
import sys
from typing import Any

from mcp.server.mcpserver import MCPServer

from .bundle import build_bundle
from .config import Config
from .procedure import run_startup
from .refresh import refresh_config as run_refresh_config
from .sources.base import SourceProvider
from .sources.fixture import FixtureSourceProvider

# stdout is reserved for the MCP JSON-RPC stream over stdio; all diagnostics go to stderr,
# which desktop clients typically capture into their own MCP server log files. This exists so
# the initialization/invocation experiment in docs/08 produces inspectable evidence instead of
# relying on the model's own account of what it did.
logging.basicConfig(
    level=os.environ.get("ZMCP_LOG_LEVEL", "INFO").upper(),
    stream=sys.stderr,
    format="%(asctime)s zmcp %(levelname)s %(message)s",
)
logger = logging.getLogger("zmcp")

BRAIN_ROUTE = (
    "Brain initialization: https://drive.google.com/file/d/1bGVXeMqG899ScKLdADsyYtPP4tWOLyuA/view\n"
    "Use your own authorized Drive connection to read that current source. Follow its "
    "current canonical routing guide to find the applicable guidance and source IDs; "
    "do not infer paths or IDs from this tool. No role is the default unless the user "
    "has explicitly assigned a standing role. Read the current designated No role profile "
    "or assigned role definition, Base, and task-applicable guidance at the scope Brain "
    "requires. Report missing, inaccessible, or conflicting designations rather than guessing. "
    "This server has not read Brain or verified freshness. It does not use the configuration "
    "cache for this route, and refresh-config is a separate, manual operation."
)

TOOL_DESCRIPTION = (
    "Give the caller Brain's initialization entry point and instructions to resolve its "
    "own current role guidance through authoritative routing. No Drive read, cache use, "
    "role assignment, or grounding claim is performed by this tool."
)


def handle_ground(
    provider: SourceProvider,
    config: Config,
    purpose: str,
    role: str | None = None,
) -> dict[str, Any]:
    """Retained fixture pipeline behind the legacy ground tool, separate from startup."""
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
    "Brain is z’s shared knowledge, context and AI-governance store.\n"
    + BRAIN_ROUTE
)


mcp = MCPServer(
    name="zmcp",
    instructions=SERVER_INSTRUCTIONS,
)

_config = Config.from_env()
logger.info(
    "zmcp process starting: pid=%s fixture_root=%s context_budget_chars=%s",
    os.getpid(),
    _config.fixture_root,
    _config.context_budget_chars,
)


@mcp.tool(name="startup", description=TOOL_DESCRIPTION)
def startup(purpose: str | None = None, role: str | None = None) -> str:
    """Return a static route; compatibility hints do not select or authorize a role."""
    logger.info("startup route invoked: pid=%s", os.getpid())
    return BRAIN_ROUTE


@mcp.tool(
    name="ground",
    description=(
        "Legacy grounding prototype backed by local fixture data, not live Brain content. "
        "Returns a structured test bundle with READY, DEGRADED, or BLOCKED status. "
        "It does not establish live canonical grounding. Calling startup first is unnecessary."
    ),
)
def ground(purpose: str, role: str | None = None) -> dict[str, Any]:
    logger.info("ground tool invoked: pid=%s purpose=%r role_hint=%r", os.getpid(), purpose, role)
    provider = FixtureSourceProvider(_config.fixture_root)
    response = handle_ground(provider, _config, purpose, role)
    logger.info("ground tool returned: pid=%s status=%s", os.getpid(), response["status"])
    return response


@mcp.tool(
    name="refresh-config",
    description=(
        "Manually compare cached configuration with explicitly designated Brain sources and "
        "refresh changed content after validation. Returns source identities, timestamps, "
        "changes and missing material. Failure preserves the previous cache. "
        "Never runs automatically at startup; fixtures are not live Brain verification."
    ),
)
def refresh_config() -> dict[str, Any]:
    return run_refresh_config(_config.config_cache, _config.config_sources)


def main() -> None:
    logger.info("zmcp entering stdio serve loop: pid=%s", os.getpid())
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
