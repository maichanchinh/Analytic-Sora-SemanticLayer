# Sora Semantic Layer

Read-only analytics layer over Sora Silver Parquet on RustFS. Python Core exposes registered semantic metrics and dimensions through FastAPI and FastMCP. See [architecture](docs/ARCHITECTURE.md), [Silver catalog](docs/SILVER_DATA_CATALOG.md), [connection setup](docs/SILVER_CONNECTION.md), and [API/MCP usage](docs/API.md).

## Development

Use Python 3.14 and `uv`:

```sh
uv sync --all-groups
uv run python -m unittest discover -s tests -v
```

Configure Silver environment variables from `.env.example` before running API or MCP against RustFS. Local server commands and MCP transports are documented in [docs/API.md](docs/API.md).
