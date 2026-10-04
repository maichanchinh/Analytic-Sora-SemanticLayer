"""Dimension metadata for the verified Silver catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from boring_semantic_layer import Dimension, entity_dimension


@dataclass(frozen=True)
class DimensionDefinition:
    """A queryable dimension with its Silver column and catalog grain."""

    name: str
    source_column: str
    description: str
    grain: str
    entity: bool = False
    time: bool = False

    def as_bsl_dimension(self, dataset: str) -> Dimension:
        metadata: dict[str, Any] = {
            "source": dataset,
            "source_column": self.source_column,
            "grain": self.grain,
        }
        if self.entity:
            dimension = entity_dimension(
                lambda table: table[self.source_column], self.description
            )
            return Dimension(
                expr=dimension.expr,
                description=dimension.description,
                is_entity=True,
                metadata=metadata,
            )
        if self.time:
            return Dimension(
                expr=lambda table: table[self.source_column],
                description=self.description,
                is_time_dimension=True,
                smallest_time_grain="TIME_GRAIN_DAY",
                metadata=metadata,
            )
        return Dimension(
            expr=lambda table: table[self.source_column],
            description=self.description,
            metadata=metadata,
        )
