"""Catalog-backed Boring Semantic Layer definitions for Silver datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ibis
from boring_semantic_layer import SemanticTable, to_semantic_table

from sora_semantic.semantic.dimensions import DimensionDefinition
from sora_semantic.semantic.metrics import MetricDefinition


@dataclass(frozen=True)
class SilverSemanticDefinition:
    """Semantic contract for one production Silver dataset."""

    name: str
    grain: tuple[str, ...]
    dimensions: tuple[DimensionDefinition, ...]
    metrics: tuple[MetricDefinition, ...]
    description: str

    def build(self, table: Any) -> SemanticTable:
        semantic_table = to_semantic_table(
            table,
            name=self.name,
            description=self.description,
        )
        if self.dimensions:
            semantic_table = semantic_table.with_dimensions(
                **{
                    item.name: item.as_bsl_dimension(self.name)
                    for item in self.dimensions
                }
            )
        if self.metrics:
            semantic_table = semantic_table.with_measures(
                **{
                    item.name: item.as_bsl_measure(self.name, self.grain)
                    for item in self.metrics
                }
            )
        return semantic_table

    def metadata(self) -> dict[str, Any]:
        """Return a JSON-ready description of the supported fields."""
        return {
            "name": self.name,
            "source": self.name,
            "grain": list(self.grain),
            "description": self.description,
            "dimensions": [
                {
                    "name": item.name,
                    "source_column": item.source_column,
                    "grain": item.grain,
                    "description": item.description,
                }
                for item in self.dimensions
            ],
            "metrics": [
                {
                    "name": item.name,
                    "source_column": item.source_column,
                    "grain": list(self.grain),
                    "unit": item.unit,
                    "aggregation": item.aggregation,
                    "currency_column": item.currency_column,
                    "paired_currency_column": item.paired_currency_column,
                    "guard_column": item.guard_column,
                    "numerator_column": item.numerator_column,
                    "denominator_column": item.denominator_column,
                    "null_behavior": item.null_behavior,
                    "description": item.description,
                }
                for item in self.metrics
            ],
        }


def _dim(
    name: str,
    grain: str | None = None,
    *,
    entity: bool | None = None,
    time: bool = False,
):
    if entity is None:
        entity = name in {"app_id", "country_code"}
    return DimensionDefinition(
        name=name,
        source_column=name,
        description=f"Silver {name} dimension.",
        grain=grain or name,
        entity=entity,
        time=time,
    )


def _metric(
    name: str,
    unit: str,
    *,
    source_column: str | None = None,
    aggregation: str = "sum",
    currency_column: str | None = None,
    paired_currency_column: str | None = None,
    guard_column: str | None = None,
    numerator_column: str | None = None,
    denominator_column: str | None = None,
    multiplier: float = 1.0,
    null_behavior: str | None = None,
    description: str | None = None,
):
    return MetricDefinition(
        name=name,
        source_column=source_column or name,
        description=description or f"Silver {source_column or name} metric.",
        unit=unit,
        aggregation=aggregation,
        currency_column=currency_column,
        paired_currency_column=paired_currency_column,
        guard_column=guard_column,
        numerator_column=numerator_column,
        denominator_column=denominator_column,
        multiplier=multiplier,
        null_behavior=null_behavior,
    )
