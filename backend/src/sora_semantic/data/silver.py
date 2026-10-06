"""Read Silver Parquet and build manifests from RustFS through DuckDB/Ibis."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

import ibis
from ibis.backends.duckdb import Backend
from ibis.expr.types import Table


class SilverReadError(RuntimeError):
    """A safe-to-display Silver connection or read error."""


@dataclass(frozen=True)
class SilverSettings:
    """S3-compatible RustFS connection settings loaded from runtime environment."""

    endpoint_url: str
    bucket: str
    region: str
    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)
    addressing_style: str
    verify_ssl: bool

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> SilverSettings:
        """Load required Silver settings without including values in errors."""
        env = os.environ if environ is None else environ
        prefix = "APP_CONFIG__S3__SILVER__"
        required = {
            "ENDPOINT_URL": "endpoint_url",
            "BUCKET": "bucket",
            "REGION_NAME": "region",
            "ACCESS_KEY_ID": "access_key_id",
            "SECRET_ACCESS_KEY": "secret_access_key",
            "ADDRESSING_STYLE": "addressing_style",
            "VERIFY_SSL": "verify_ssl",
        }
        values = {
            field: env.get(prefix + name, "").strip()
            for name, field in required.items()
        }
        missing = [prefix + name for name, field in required.items() if not values[field]]
        if missing:
            raise SilverReadError(
                "Missing required Silver environment setting(s): " + ", ".join(missing)
            )

        endpoint = values["endpoint_url"]
        try:
            parsed = urlsplit(endpoint)
            parsed.port
        except ValueError:
            raise SilverReadError(
                prefix + "ENDPOINT_URL must be a valid http(s) URL without credentials or a path"
            ) from None
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise SilverReadError(
                prefix + "ENDPOINT_URL must be an http(s) URL without credentials or a path"
            )

        bucket = values["bucket"]
        if re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket) is None:
            raise SilverReadError(prefix + "BUCKET must be a valid S3 bucket name")

        style = values["addressing_style"].lower()
        if style not in {"path", "virtual", "auto"}:
            raise SilverReadError(prefix + "ADDRESSING_STYLE must be path, virtual, or auto")

        raw_verify_ssl = values["verify_ssl"].lower()
        if raw_verify_ssl not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
            raise SilverReadError(prefix + "VERIFY_SSL must be a boolean value")

        return cls(
            endpoint_url=endpoint,
            bucket=bucket,
            region=values["region"],
            access_key_id=values["access_key_id"],
            secret_access_key=values["secret_access_key"],
            addressing_style=style,
            verify_ssl=raw_verify_ssl in {"true", "1", "yes", "on"},
        )


@dataclass(frozen=True)
class SilverDataset:
    """A production dataset path from the Silver Data Catalog."""

    name: str
    path: str
    partitioned_by_date: bool = False

    def object_pattern(self) -> str:
        if self.partitioned_by_date:
            return f"{self.path}/date=*/data.parquet"
        return self.path


SILVER_DATASETS: tuple[SilverDataset, ...] = (
    SilverDataset("dim_app", "dimensions/dim_app/data.parquet"),
    SilverDataset("dim_country", "dimensions/dim_country/data.parquet"),
    SilverDataset("dim_date", "dimensions/dim_date", True),
    SilverDataset("ga4_daily_overview", "ga4/ga4_daily_overview", True),
    SilverDataset("ga4_retention_cohort", "ga4/ga4_retention_cohort", True),
    SilverDataset("admob_mediation_daily", "admob/admob_mediation_daily", True),
    SilverDataset(
        "google_ads_campaign_geo_daily",
        "google_ads/google_ads_campaign_geo_daily",
        True,
    ),
    SilverDataset("fx_daily", "finance/fx_daily", True),
    SilverDataset("app_daily", "report/app_daily", True),
    SilverDataset("campaign_geo", "report/campaign_geo", True),
    SilverDataset("retention", "report/retention", True),
)
_DATASETS_BY_NAME = {dataset.name: dataset for dataset in SILVER_DATASETS}
DEFAULT_CACHE_TTL_SECONDS = 300.0


@dataclass(frozen=True)
class SilverManifest:
    """Parsed build manifest; source freshness statuses retain Sora's values."""

    business_date: date
    built_at: str
    trigger_sources: tuple[str, ...]
    failed_sources: tuple[str, ...]
    source_status: Mapping[str, object]


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class SilverDataSource:
    """Expose only catalog-bound reads from the configured Silver bucket."""

    def __init__(
        self,
        settings: SilverSettings,
        database_path: Path | None = None,
        *,
        cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        if cache_ttl_seconds <= 0:
            raise ValueError("cache_ttl_seconds must be positive")
        self._settings = settings
        self._database_path = database_path
        self._cache_ttl_seconds = cache_ttl_seconds
        self._backend: Backend | None = None
        self._tables: dict[str, Table] = {}
        self._cache_refreshed_at: dict[str, float] = {}

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        database_path: Path | None = None,
    ) -> SilverDataSource:
        """Create a source from the Sora Silver environment contract."""
        return cls(SilverSettings.from_env(environ), database_path=database_path)

    def connect(self) -> SilverDataSource:
        """Open DuckDB and install a temporary, bucket-scoped S3 secret."""
        if self._backend is not None:
            return self

        backend: Backend | None = None
        try:
            if self._database_path is not None:
                self._database_path.parent.mkdir(parents=True, exist_ok=True)
                backend = ibis.duckdb.connect(str(self._database_path), extensions=["httpfs"])
            else:
                backend = ibis.duckdb.connect(extensions=["httpfs"])
            endpoint = urlsplit(self._settings.endpoint_url)
            style = {"auto": "vhost", "virtual": "vhost"}.get(
                self._settings.addressing_style, self._settings.addressing_style
            )
            secret_sql = """CREATE OR REPLACE TEMPORARY SECRET sora_silver (
                TYPE S3,
                PROVIDER CONFIG,
                KEY_ID {key_id},
                SECRET {secret},
                REGION {region},
                ENDPOINT {endpoint},
                URL_STYLE {style},
                USE_SSL {use_ssl},
                VERIFY_SSL {verify_ssl},
                SCOPE {scope}
            )""".format(
                key_id=_sql_string(self._settings.access_key_id),
                secret=_sql_string(self._settings.secret_access_key),
                region=_sql_string(self._settings.region),
                endpoint=_sql_string(endpoint.netloc),
                style=_sql_string(style),
                use_ssl="true" if endpoint.scheme == "https" else "false",
                verify_ssl="true" if self._settings.verify_ssl else "false",
                scope=_sql_string(f"s3://{self._settings.bucket}/"),
            )
            backend.raw_sql(secret_sql)
        except Exception:
            try:
                if backend is not None:
                    backend.disconnect()
            except Exception:
                pass
            raise SilverReadError(
                "Could not initialize the DuckDB/Ibis Silver connection; "
                "check the S3-compatible settings and permissions"
            ) from None

        self._backend = backend
        return self

    @property
    def dataset_names(self) -> tuple[str, ...]:
        """Return the fixed set of production catalog datasets."""
        return tuple(_DATASETS_BY_NAME)

    def table(self, name: str) -> Table:
        """Return an Ibis table expression for one catalog dataset."""
        backend = self._require_backend()
        dataset = _DATASETS_BY_NAME.get(name)
        if dataset is None:
            raise KeyError(f"Unknown Silver catalog dataset: {name}")
        if self._database_path is not None:
            self.refresh_expired_cached_datasets()
        if name in self._tables:
            return self._tables[name]
        if self._database_path is not None:
            return self._refresh_cached_table(name)
        uri = f"s3://{self._settings.bucket}/{dataset.object_pattern()}"
        try:
            table = backend.read_parquet(
                uri,
                table_name=dataset.name,
                hive_partitioning=dataset.partitioned_by_date,
                union_by_name=True,
            )
            self._tables[name] = table
            return table
        except Exception as error:
            raise SilverReadError(
                f"Could not register Silver dataset {name!r} "
                f"(DuckDB {type(error).__name__}); verify Silver read access"
            ) from None

    def refresh_cached_datasets(self) -> None:
        """Refresh app metadata and datasets already materialized in the DuckDB file."""
        backend = self._require_backend()
        if self._database_path is None:
            return
        rows = backend.raw_sql(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        cached_names = {
            row[0][len("_sora_cache_") :]
            for row in rows
            if row[0].startswith("_sora_cache_")
            and row[0][len("_sora_cache_") :] in _DATASETS_BY_NAME
        }
        for name in sorted(cached_names | {"dim_app"}):
            self._refresh_cached_table(name)

    def refresh_expired_cached_datasets(self) -> None:
        """Refresh materialized Silver tables whose short cache TTL has elapsed."""
        if self._database_path is None:
            return
        backend = self._require_backend()
        rows = backend.raw_sql(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        now = time.monotonic()
        cached_names = sorted(
            row[0][len("_sora_cache_") :]
            for row in rows
            if row[0].startswith("_sora_cache_")
            and row[0][len("_sora_cache_") :] in _DATASETS_BY_NAME
        )
        for name in cached_names:
            refreshed_at = self._cache_refreshed_at.get(name)
            if refreshed_at is None or now - refreshed_at >= self._cache_ttl_seconds:
                self._refresh_cached_table(name)

    def _refresh_cached_table(self, name: str) -> Table:
        backend = self._require_backend()
        dataset = _DATASETS_BY_NAME.get(name)
        if dataset is None:
            raise KeyError(f"Unknown Silver catalog dataset: {name}")
        uri = f"s3://{self._settings.bucket}/{dataset.object_pattern()}"
        table_name = f"_sora_cache_{name}"
        try:
            backend.raw_sql(
                f"CREATE OR REPLACE TABLE {table_name} AS "
                f"SELECT * FROM read_parquet({_sql_string(uri)}, "
                f"hive_partitioning = {'true' if dataset.partitioned_by_date else 'false'}, "
                "union_by_name = true)"
            )
            table = backend.table(table_name)
            self._tables[name] = table
            self._cache_refreshed_at[name] = time.monotonic()
            return table
        except Exception as error:
            self._tables.pop(name, None)
            self._cache_refreshed_at.pop(name, None)
            raise SilverReadError(
                f"Could not refresh Silver dataset {name!r} "
                f"(DuckDB {type(error).__name__}); verify Silver read access"
            ) from None

    def manifest(self, business_date: date) -> SilverManifest:
        """Read the Silver build manifest for a business date."""
        backend = self._require_backend()
        iso_date = business_date.isoformat()
        uri = (
            f"s3://{self._settings.bucket}/metadata/silver_build/"
            f"date={iso_date}/manifest.json"
        )
        try:
            row = backend.raw_sql(f"SELECT content FROM read_blob({_sql_string(uri)})").fetchone()
            if row is None:
                raise ValueError("manifest object returned no content")
            payload = json.loads(bytes(row[0]))
            if not isinstance(payload, dict):
                raise ValueError("manifest root must be an object")
            actual_date = date.fromisoformat(str(payload["business_date"]))
            built_at = payload["built_at"]
            source_status = payload["source_status"]
            if (
                actual_date != business_date
                or not isinstance(built_at, str)
                or not isinstance(source_status, dict)
            ):
                raise ValueError("manifest fields do not match the catalog contract")
            return SilverManifest(
                business_date=actual_date,
                built_at=built_at,
                trigger_sources=tuple(str(item) for item in payload.get("trigger_sources", [])),
                failed_sources=tuple(str(item) for item in payload.get("failed_sources", [])),
                source_status=source_status,
            )
        except Exception as error:
            raise SilverReadError(
                f"Could not read Silver build manifest for {iso_date} "
                f"(DuckDB {type(error).__name__}); verify Silver read access"
            ) from None

    def close(self) -> None:
        """Close DuckDB and discard its temporary secret and table handles."""
        if self._backend is not None:
            self._backend.disconnect()
            self._backend = None
            self._tables.clear()

    def __enter__(self) -> SilverDataSource:
        return self.connect()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _require_backend(self) -> Backend:
        if self._backend is None:
            raise SilverReadError("SilverDataSource.connect() must be called before reading")
        return self._backend
