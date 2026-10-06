from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

import ibis

from sora_semantic.data.silver import SilverDataSource, SilverSettings


class SilverDataSourceTests(TestCase):
    def make_source(self) -> SilverDataSource:
        return SilverDataSource(
            SilverSettings(
                endpoint_url="https://rustfs.example",
                bucket="silver-bucket",
                region="us-east-1",
                access_key_id="key",
                secret_access_key="secret",
                addressing_style="path",
                verify_ssl=True,
            )
        )

    def test_connect_uses_in_memory_duckdb(self) -> None:
        source = self.make_source()
        backend = Mock()
        with patch(
            "sora_semantic.data.silver.ibis.duckdb.connect",
            return_value=backend,
        ) as connect:
            source.connect()

        connect.assert_called_once_with(extensions=["httpfs"])
        executed_sql = [call.args[0] for call in backend.raw_sql.call_args_list]
        self.assertIn("SET enable_external_file_cache = false", executed_sql)
        self.assertIn("SET parquet_metadata_cache = false", executed_sql)
        self.assertIn("SET enable_http_metadata_cache = false", executed_sql)
        self.assertFalse(hasattr(source, "refresh_cached_datasets"))
        self.assertFalse(hasattr(source, "refresh_expired_cached_datasets"))

    def test_long_lived_connection_sees_new_parquet_partition(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first_partition = root / "date=2026-10-05"
            second_partition = root / "date=2026-10-06"
            first_partition.mkdir()
            second_partition.mkdir()
            first_file = first_partition / "data.parquet"
            second_file = second_partition / "data.parquet"

            backend = ibis.duckdb.connect()
            try:
                backend.raw_sql("SET enable_external_file_cache = false")
                backend.raw_sql("SET parquet_metadata_cache = false")
                backend.raw_sql("SET enable_http_metadata_cache = false")
                backend.raw_sql(
                    f"COPY (SELECT 1 AS value) TO '{first_file}' (FORMAT PARQUET)"
                )
                backend.raw_sql(
                    f"CREATE VIEW silver_scan AS "
                    f"SELECT * FROM read_parquet('{root}/date=*/data.parquet', "
                    "hive_partitioning = true)"
                )
                self.assertEqual(
                    backend.raw_sql("SELECT sum(value) FROM silver_scan").fetchone()[0],
                    1,
                )

                backend.raw_sql(
                    f"COPY (SELECT 2 AS value) TO '{second_file}' (FORMAT PARQUET)"
                )

                self.assertEqual(
                    backend.raw_sql("SELECT sum(value) FROM silver_scan").fetchone()[0],
                    3,
                )
            finally:
                backend.disconnect()

    def test_table_registers_direct_silver_parquet_scan(self) -> None:
        source = self.make_source()
        backend = Mock()
        table_expression = Mock()
        backend.read_parquet.return_value = table_expression
        source._backend = backend

        result = source.table("google_ads_campaign_geo_daily")

        self.assertIs(result, table_expression)
        backend.read_parquet.assert_called_once_with(
            "s3://silver-bucket/google_ads/google_ads_campaign_geo_daily/date=*/data.parquet",
            table_name="google_ads_campaign_geo_daily",
            hive_partitioning=True,
            union_by_name=True,
        )
        backend.raw_sql.assert_not_called()

    def test_startup_read_check_executes_silver_table(self) -> None:
        source = self.make_source()
        backend = Mock()
        table_expression = Mock()
        backend.read_parquet.return_value = table_expression
        source._backend = backend

        source.validate_read_access()

        backend.read_parquet.assert_called_once()
        table_expression.limit.assert_called_once_with(1)
        table_expression.limit.return_value.execute.assert_called_once_with()


if __name__ == "__main__":
    import unittest

    unittest.main()
