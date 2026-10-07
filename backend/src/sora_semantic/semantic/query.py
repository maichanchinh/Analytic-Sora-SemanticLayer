"""Shared, validated query contract for API and MCP consumers."""

from __future__ import annotations

from dataclasses import dataclass
from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal
import logging
import math
import re
import time
from typing import Any, Mapping

from sora_semantic.data.silver import SilverReadError
from sora_semantic.semantic.dimensions import DimensionDefinition
from sora_semantic.semantic.registry import SemanticRegistry

_LOGGER = logging.getLogger(__name__)
QUERY_DIAGNOSTIC_ID: ContextVar[str] = ContextVar("query_diagnostic_id", default="-")


def safe_error_summary(error: Exception) -> str:
    summary = str(error)
    summary = re.sub(r"(?i)(access.?key|secret|token|password)(\s*[=:]\s*)[^\s&]+", r"\1\2<redacted>", summary)
    summary = re.sub(r"(https?://)[^/@\s]+:[^/@\s]+@", r"\1<redacted>@", summary)
    summary = re.sub(r"([?&](?:X-Amz-[^=]+|signature|credential)=)[^&\s]+", r"\1<redacted>", summary, flags=re.IGNORECASE)
    return summary[:500]


class QueryContractError(ValueError):
    """A request references unsupported semantic fields or values."""


@dataclass(frozen=True)
class DateRange:
    """Inclusive range applied to the model's time dimension."""

    from_: date | str
    to: date | str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DateRange:
        if set(value) != {"from", "to"}:
            raise QueryContractError("date_range must contain exactly 'from' and 'to'.")
        return cls(from_=value["from"], to=value["to"])


@dataclass(frozen=True)
class QueryRequest:
    """Consumer query expressed only in registered semantic names."""

    model: str
    metrics: tuple[str, ...] = ()
    dimensions: tuple[str, ...] = ()
    filters: Mapping[str, Any] | None = None
    date_range: DateRange | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> QueryRequest:
        allowed = {"model", "metrics", "dimensions", "filters", "date_range"}
        unknown = set(value) - allowed
        if unknown:
            raise QueryContractError(f"Unsupported request field(s): {', '.join(sorted(unknown))}.")
        if not isinstance(value.get("model"), str):
            raise QueryContractError("model must be a string.")
        for field in ("metrics", "dimensions"):
            raw = value.get(field, ())
            if not isinstance(raw, list | tuple) or any(not isinstance(item, str) for item in raw):
                raise QueryContractError(f"{field} must be a list of strings.")
        raw_filters = value.get("filters", {})
        if not isinstance(raw_filters, Mapping):
            raise QueryContractError("filters must be an object mapping dimensions to values.")
        raw_range = value.get("date_range")
        if raw_range is not None and not isinstance(raw_range, Mapping):
            raise QueryContractError("date_range must be an object with 'from' and 'to'.")
        return cls(
            model=value["model"],
            metrics=tuple(value.get("metrics", ())),
            dimensions=tuple(value.get("dimensions", ())),
            filters=raw_filters,
            date_range=DateRange.from_mapping(raw_range) if raw_range is not None else None,
        )


@dataclass(frozen=True)
class QueryResult:
    """Metadata and rows shared by API and MCP consumers."""

    model: str
    dimensions: tuple[dict[str, Any], ...]
    metrics: tuple[dict[str, Any], ...]
    rows: tuple[dict[str, Any], ...]


class QueryService:
    """Validate requests against Registry definitions and execute with BSL."""

    def __init__(self, registry: SemanticRegistry) -> None:
        self._registry = registry

    def query(self, request: QueryRequest) -> QueryResult:
        definition = self._definition(request.model)
        semantic_definition = getattr(definition, "definition", definition)
        dimensions = {item.name: item for item in semantic_definition.dimensions}
        metrics = {item.name: item for item in semantic_definition.metrics}

        if not request.metrics and not request.dimensions:
            raise QueryContractError("At least one metric or dimension is required.")
        if len(set(request.metrics)) != len(request.metrics):
            raise QueryContractError("metrics must not contain duplicates.")
        if len(set(request.dimensions)) != len(request.dimensions):
            raise QueryContractError("dimensions must not contain duplicates.")
        self._validate_names("dimension", request.dimensions, dimensions)
        self._validate_names("metric", request.metrics, metrics)
        filters = request.filters or {}
        self._validate_names("filter", tuple(filters), dimensions)

        filter_functions = [
            self._filter_function(dimensions[name], value)
            for name, value in filters.items()
        ]
        if request.date_range is not None:
            time_dimensions = [item for item in dimensions.values() if item.time]
            if not time_dimensions:
                raise QueryContractError(
                    f"Model {request.model!r} has no time dimension for date_range."
                )
            if len(time_dimensions) != 1:
                raise QueryContractError(
                    f"Model {request.model!r} has multiple time dimensions; date_range is ambiguous."
                )
            start = self._parse_date(request.date_range.from_, "date_range.from")
            end = self._parse_date(request.date_range.to, "date_range.to")
            if start > end:
                raise QueryContractError("date_range.from must be on or before date_range.to.")
            source_column = time_dimensions[0].source_column
            filter_functions.append(
                lambda table, column=source_column, lower=start: table[column] >= lower
            )
            filter_functions.append(
                lambda table, column=source_column, upper=end: table[column] <= upper
            )

        started_at = time.perf_counter()
        try:
            result = self._registry.get(request.model).query(
                dimensions=list(request.dimensions),
                measures=list(request.metrics),
                filters=filter_functions,
            )
        except (KeyError, ValueError) as error:
            raise QueryContractError(f"Invalid query contract: {error}") from None

        try:
            rows = tuple(
                {name: self._output_value(value) for name, value in row.items()}
                for row in result.to_pyarrow().to_pylist()
            )
        except Exception as error:
            _LOGGER.error(
                "Silver query execution failed: request_id=%s model=%s date_from=%s date_to=%s duration_ms=%.1f error_type=%s cause=%s",
                QUERY_DIAGNOSTIC_ID.get(),
                request.model,
                request.date_range.from_ if request.date_range else None,
                request.date_range.to if request.date_range else None,
                (time.perf_counter() - started_at) * 1000,
                type(error).__name__,
                safe_error_summary(error),
            )
            raise SilverReadError(
                f"Could not execute query against Silver (DuckDB {type(error).__name__})."
            ) from None
        _LOGGER.debug(
            "Silver query completed: request_id=%s model=%s date_from=%s date_to=%s duration_ms=%.1f row_count=%s",
            QUERY_DIAGNOSTIC_ID.get(),
            request.model,
            request.date_range.from_ if request.date_range else None,
            request.date_range.to if request.date_range else None,
            (time.perf_counter() - started_at) * 1000,
            len(rows),
        )
        metadata = definition.metadata()
        dimension_metadata = {item["name"]: item for item in metadata["dimensions"]}
        metric_metadata = {item["name"]: item for item in metadata["metrics"]}
        return QueryResult(
            model=request.model,
            dimensions=tuple(dimension_metadata[name] for name in request.dimensions),
            metrics=tuple(metric_metadata[name] for name in request.metrics),
            rows=rows,
        )

    def _definition(self, name: str):
        try:
            return next(item for item in self._registry.definitions if item.name == name)
        except StopIteration:
            raise QueryContractError(f"Unsupported semantic model: {name!r}.") from None

    @staticmethod
    def _validate_names(kind: str, names: tuple[str, ...], available: Mapping[str, Any]) -> None:
        unknown = [name for name in names if name not in available]
        if unknown:
            raise QueryContractError(
                f"Unsupported {kind}(s): {', '.join(repr(name) for name in unknown)}. "
                f"Available: {', '.join(sorted(available))}."
            )

    @staticmethod
    def _parse_date(value: date | str, field: str) -> date:
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            raise QueryContractError(f"{field} must be an ISO date (YYYY-MM-DD).") from None

    @staticmethod
    def _filter_function(dimension: DimensionDefinition, value: Any):
        column = dimension.source_column
        if isinstance(value, list | tuple):
            values = tuple(value)
            if any(not QueryService._is_scalar(item) for item in values):
                raise QueryContractError(
                    f"Filter values for {dimension.name!r} must be scalar values."
                )
            return lambda table, name=column, items=values: table[name].isin(items)
        if not QueryService._is_scalar(value):
            raise QueryContractError(
                f"Filter for {dimension.name!r} must be a scalar or a list of scalars."
            )
        return lambda table, name=column, expected=value: table[name] == expected

    @staticmethod
    def _is_scalar(value: Any) -> bool:
        return (
            isinstance(value, (str, int, float, bool))
            and not (isinstance(value, float) and not math.isfinite(value))
        )

    @staticmethod
    def _output_value(value: Any) -> Any:
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return int(value) if value == value.to_integral_value() else float(value)
        return value
