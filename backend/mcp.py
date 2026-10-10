"""Run the local MCP server over Streamable HTTP or stdio."""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


backend_dir = Path(__file__).resolve().parent
repo_dir = backend_dir.parent


def main() -> None:
    load_dotenv(repo_dir / ".env")
    load_dotenv(backend_dir / ".env.local", override=True)
    load_dotenv(backend_dir / ".env", override=True)

    # Running this file directly puts its directory on sys.path, where this
    # launcher would otherwise shadow the third-party `mcp` package.
    sys.path[:] = [
        entry
        for entry in sys.path
        if Path(entry or ".").resolve() != backend_dir
    ]

    from sora_semantic.mcp import mcp

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="streamable-http",
        help="MCP transport to use (default: streamable-http)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="Streamable HTTP bind host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8001")),
        help="Streamable HTTP bind port (default: 8001)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            path="/mcp",
        )


if __name__ == "__main__":
    main()
