"""Run the local MCP server over stdio or Streamable HTTP."""

import argparse
from pathlib import Path

from dotenv import load_dotenv


backend_dir = Path(__file__).resolve().parent
repo_dir = backend_dir.parent


def main() -> None:
    load_dotenv(repo_dir / ".env")
    load_dotenv(backend_dir / ".env.local", override=True)
    load_dotenv(backend_dir / ".env", override=True)
    from sora_semantic.mcp import mcp

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport to use (default: stdio)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=8001,
            path="/mcp",
        )


if __name__ == "__main__":
    main()
