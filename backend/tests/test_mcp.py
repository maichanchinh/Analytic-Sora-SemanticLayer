import asyncio
import logging
import os
from pathlib import Path
import socket
import sys
import unittest

from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
import uvicorn

from mcp_test_support import make_source
from sora_semantic.mcp import create_mcp_server
from test_support import ignore_known_ibis_duckdb_deprecation


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"


def result_data(result):
    if result.structured_content is not None:
        return result.structured_content
    return result.data


class McpToolTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ignore_known_ibis_duckdb_deprecation()

    async def test_tools_expose_apps_metrics_and_shared_query_contract(self):
        source = make_source()
        server = create_mcp_server(source_factory=lambda: source)

        async with Client(server) as client:
            tools = await client.list_tools()
            apps = await client.call_tool("list_apps")
            metrics = await client.call_tool("list_metrics")
            query = await client.call_tool(
                "query_metrics",
                {
                    "model": "dim_app",
                    "dimensions": ["app_id", "display_name"],
                    "filters": {"app_id": "app.a"},
                },
            )
            date_query = await client.call_tool(
                "query_metrics",
                {
                    "model": "dim_date",
                    "dimensions": ["date"],
                    "date_range": {"from": "2026-10-02", "to": "2026-10-03"},
                },
            )

        self.assertEqual(
            {tool.name for tool in tools},
            {"list_apps", "list_metrics", "query_metrics"},
        )
        self.assertEqual(
            [item["app_id"] for item in result_data(apps)["apps"]],
            ["app.a", "app.b"],
        )
        metric_models = {item["model"] for item in result_data(metrics)["models"]}
        self.assertIn("finance_daily", metric_models)
        self.assertEqual(result_data(query)["rows"], [{"app_id": "app.a", "display_name": "Alpha"}])
        self.assertEqual(
            [row["date"] for row in result_data(date_query)["rows"]],
            ["2026-10-02", "2026-10-03"],
        )
        self.assertTrue(source.connected)
        self.assertTrue(source.closed)

    async def test_query_metrics_returns_contract_errors_for_unregistered_model(self):
        server = create_mcp_server(source_factory=make_source)
        async with Client(server) as client:
            with self.assertLogs("fastmcp.server.server", level="DEBUG") as captured:
                result = await client.call_tool(
                    "query_metrics",
                    {"model": "unregistered", "metrics": ["value"]},
                    raise_on_error=False,
                )

        self.assertTrue(result.is_error)
        self.assertIn("Unsupported semantic model", result.content[0].text)
        self.assertEqual(len(captured.records), 1)
        self.assertEqual(captured.records[0].levelno, logging.DEBUG)
        self.assertNotIn("Traceback", captured.output[0])
        self.assertNotIn("QueryContractError", captured.output[0])

    async def test_stdio_transport_smoke(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            item for item in (str(TESTS), env.get("PYTHONPATH", "")) if item
        )
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "mcp_stdio_runner"],
            cwd=str(ROOT),
            env=env,
        )
        async with Client(transport) as client:
            result = await client.call_tool("list_apps")

        self.assertEqual(
            [item["app_id"] for item in result_data(result)["apps"]],
            ["app.a", "app.b"],
        )

    async def test_streamable_http_transport_smoke(self):
        source = make_source()
        server = create_mcp_server(source_factory=lambda: source)
        app = server.http_app(transport="streamable-http", path="/mcp")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        uvicorn_server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        )
        serve_task = asyncio.create_task(uvicorn_server.serve())
        try:
            for _ in range(100):
                if uvicorn_server.started:
                    break
                if serve_task.done():
                    await serve_task
                await asyncio.sleep(0.05)
            self.assertTrue(uvicorn_server.started)

            async with Client(StreamableHttpTransport(f"http://127.0.0.1:{port}/mcp")) as client:
                result = await client.call_tool("list_apps")

            self.assertEqual(
                [item["app_id"] for item in result_data(result)["apps"]],
                ["app.a", "app.b"],
            )
            self.assertTrue(source.connected)
        finally:
            uvicorn_server.should_exit = True
            await serve_task
        self.assertTrue(source.closed)


if __name__ == "__main__":
    unittest.main()
