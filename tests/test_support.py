import warnings


def ignore_known_ibis_duckdb_deprecation() -> None:
    """Hide only Ibis' use of DuckDB's deprecated fetch_arrow_table API in tests."""
    warnings.filterwarnings(
        "ignore",
        message=r"fetch_arrow_table\(\) is deprecated, use to_arrow_table\(\) instead\.",
        category=DeprecationWarning,
    )
