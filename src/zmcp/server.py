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
    level=os.environ.get("ZMCP_LOG_LEVEL", "INFO").upper(),
    stream=sys.stderr,
    format="%(asctime)s zmcp %(levelname)s %(message)s",
)
logger = logging.getLogger("zmcp")

TOOL_DESCRIPTION = (
    "Placeholder for future startup guidance. Returns only 'to be defined'. "
    "No grounding is retrieved or validated. There is no need to call this tool."
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
    "Folder: https://drive.google.com/drive/folders/1F3IchT4CKGqTSEj1CSpMpj7GdqTkxy54\n"
    "Initialization: https://drive.google.com/file/d/1bGVXeMqG899ScKLdADsyYtPP4tWOLyuA/view\n\n"
    "The startup tool is currently a placeholder returning 'to be defined'; "
    "there is no need to call it. Connecting provides these links but does not "
    "retrieve or validate Brain content."
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
    """Accept previous arguments for compatibility; no retrieval is performed."""
    logger.info(
        "startup tool invoked: pid=%s purpose=%r role_hint=%r", os.getpid(), purpose, role
    )
    logger.info("startup tool returned: pid=%s placeholder='to be defined'", os.getpid())
    return "to be defined"


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


def main() -> None:
    logger.info("zmcp entering stdio serve loop: pid=%s", os.getpid())
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
