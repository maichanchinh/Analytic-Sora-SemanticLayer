from fastmcp import FastMCP

from mcp_test_support import make_source
from sora_semantic.mcp import create_mcp_server


mcp: FastMCP = create_mcp_server(source_factory=make_source)
mcp.run(transport="stdio", show_banner=False)
