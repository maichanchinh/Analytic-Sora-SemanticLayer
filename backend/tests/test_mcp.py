import asyncio
import os
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
import uvicorn

from mcp_test_support import REPORT_DATE, make_source
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

    async def test_report_tools_default_date_filter_and_rank_apps(self):
        source = make_source()
        server = create_mcp_server(source_factory=lambda: source)

        with patch("sora_semantic.mcp._yesterday_report_date", return_value=REPORT_DATE):
            async with Client(server) as client:
                tools = await client.list_tools()
                apps = await client.call_tool("list_apps")
                summary = await client.call_tool("get_business_summary")
                app_summary = await client.call_tool(
                    "get_business_summary",
                    {
                        "date_range": {"from": "2026-10-06", "to": "2026-10-06"},
                        "app_id": "app.a",
                    },
                )
                top_revenue = await client.call_tool(
                    "get_top_apps", {"sort_by": "revenue"}
                )
                top_roas = await client.call_tool("get_top_apps", {"sort_by": "roas"})

        self.assertEqual(
            {tool.name for tool in tools},
            {"list_apps", "get_business_summary", "get_top_apps"},
        )
        self.assertEqual(
            len(result_data(apps)["apps"]), 6
        )
        summary_data = result_data(summary)
        self.assertEqual(summary_data["date_range"], {"from": "2026-10-06", "to": "2026-10-06"})
        self.assertEqual(summary_data["currency"], "VND")
        self.assertAlmostEqual(summary_data["revenue_vnd"], 685.0)
        self.assertAlmostEqual(summary_data["cost_vnd"], 150.0)
        self.assertAlmostEqual(summary_data["roas_vnd"], 685 / 150)
        self.assertEqual(summary_data["active_users"], 33)
        self.assertEqual(summary_data["new_users"], 14)
        self.assertEqual(len(summary_data["notes"]), 2)
        self.assertIn("không đảm bảo", summary_data["notes"][1])
        self.assertIn("AdMob", summary_data["notes"][0])

        app_data = result_data(app_summary)
        self.assertEqual(app_data["app_id"], "app.a")
        self.assertAlmostEqual(app_data["revenue_vnd"], 150.0)
        self.assertAlmostEqual(app_data["cost_vnd"], 30.0)
        self.assertAlmostEqual(app_data["roas_vnd"], 5.0)
        self.assertEqual(app_data["active_users"], 15)
        self.assertEqual(app_data["new_users"], 5)

        revenue_apps = result_data(top_revenue)["apps"]
        roas_apps = result_data(top_roas)["apps"]
        self.assertEqual(
            [row["app_id"] for row in revenue_apps],
            ["app.c", "app.b", "app.a", "app.d", "app.e"],
        )
        self.assertEqual(
            [row["app_id"] for row in roas_apps],
            ["app.a", "app.b", "app.d", "app.e", "app.f"],
        )
        self.assertEqual(len(revenue_apps), 5)
        self.assertEqual(len(roas_apps), 5)
        self.assertNotIn("app.c", {row["app_id"] for row in roas_apps})
        self.assertEqual([row["app_id"] for row in roas_apps[1:4]], ["app.b", "app.d", "app.e"])
        self.assertEqual(revenue_apps[1]["display_name"], "Beta")
        self.assertTrue(source.connected)
        self.assertTrue(source.closed)

    async def test_report_tools_reject_invalid_date_range(self):
        server = create_mcp_server(source_factory=make_source)
        async with Client(server) as client:
            result = await client.call_tool(
                "get_business_summary",
                {"date_range": {"from": "2026-10-07", "to": "2026-10-06"}},
                raise_on_error=False,
            )

        self.assertTrue(result.is_error)
        self.assertIn("date_range.from must be on or before", result.content[0].text)

    async def test_stdio_transport_smoke(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            item for item in (str(TESTS), env.get("PYTHONPATH", "")) if item
        )
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "mcp_stdio_runner"],
            cwd=str(ROOT.parent),
            env=env,
        )
        async with Client(transport) as client:
            result = await client.call_tool("list_apps")

        self.assertEqual(
            [item["app_id"] for item in result_data(result)["apps"]],
            ["app.a", "app.b", "app.d", "app.e", "app.f", "app.c"],
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
                ["app.a", "app.b", "app.d", "app.e", "app.f", "app.c"],
            )
            self.assertTrue(source.connected)
        finally:
            uvicorn_server.should_exit = True
            await serve_task
        self.assertTrue(source.closed)


if __name__ == "__main__":
    unittest.main()
