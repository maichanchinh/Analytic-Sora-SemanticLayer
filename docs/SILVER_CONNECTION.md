# Silver RustFS Connection

SemanticLayer reads Silver Parquet from the Sora RustFS bucket through DuckDB's
`httpfs` extension and Ibis. The source owns the Silver objects; this package
registers only the production paths listed in [Silver Data Catalog](SILVER_DATA_CATALOG.md).

## Runtime settings

Supply these variables to the process running SemanticLayer. Their names follow
Sora's `APP_CONFIG__S3__SILVER__*` contract. Copy only the Silver connection
values; do not copy Bronze, API, account, or Prefect provisioning secrets.

| Variable | Required | Meaning |
| --- | --- | --- |
| `APP_CONFIG__S3__SILVER__ENDPOINT_URL` | Yes | RustFS HTTP(S) endpoint, without credentials or a URL path |
| `APP_CONFIG__S3__SILVER__BUCKET` | Yes | Silver bucket name |
| `APP_CONFIG__S3__SILVER__REGION_NAME` | Yes | S3 signing region |
| `APP_CONFIG__S3__SILVER__ACCESS_KEY_ID` | Yes | Dedicated read-only RustFS key |
| `APP_CONFIG__S3__SILVER__SECRET_ACCESS_KEY` | Yes | Secret for the read-only key |
| `APP_CONFIG__S3__SILVER__ADDRESSING_STYLE` | Yes | `path`, `virtual`, or `auto` |
| `APP_CONFIG__S3__SILVER__VERIFY_SSL` | Yes | `true` or `false` |

`backend/.env.example` contains placeholders. For local use, copy it to
`backend/.env`. The API launcher reads root `.env` first and `backend/.env`
second, so app-specific values override shared defaults. Never commit populated
environment files.

The read-only key needs `ListBucket` on the Silver bucket for partition
globbing and `GetObject` for Silver data and manifests. It must not have put,
delete, or bucket-configuration permissions. DuckDB receives the credentials
as a temporary, bucket-scoped secret; it does not persist them in a database
or DuckDB's stored-secrets directory.

## Read API

```python
from datetime import date

from sora_semantic.data import SilverDataSource

with SilverDataSource.from_env() as silver:
    ga4 = silver.table("ga4_daily_overview")
    rows = ga4.filter(ga4.business_date >= date(2026, 10, 1)).execute()
    manifest = silver.manifest(date(2026, 10, 3))
```

`table()` accepts only the fixed catalog names. Snapshot datasets resolve to
their single catalog object; date-partitioned datasets read
`date=*/data.parquet` with Hive partitioning enabled. No production path points
at `staging/`. `manifest()` returns the build date, timestamp, failed/trigger
sources, and per-source freshness statuses from the matching Silver build
manifest.

Connection and manifest errors include the relevant setting name, dataset,
date, or DuckDB error type without including credential values or raw DuckDB
exception text.
