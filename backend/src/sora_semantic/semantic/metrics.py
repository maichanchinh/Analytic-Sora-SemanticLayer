"""Metric metadata for the verified Silver catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ibis
from boring_semantic_layer import Measure


@dataclass(frozen=True)
class MetricDefinition:
    """A queryable metric with its Silver column, aggregation, and unit."""

    name: str
    source_column: str
    description: str
    unit: str
    aggregation: str = "sum"
    currency_column: str | None = None
    paired_currency_column: str | None = None
    guard_column: str | None = None
    numerator_column: str | None = None
    denominator_column: str | None = None
    multiplier: float = 1.0
    null_behavior: str | None = None

    def as_bsl_measure(
        self,
        dataset: str,
        grain: tuple[str, ...],
        *,
        source_column_override: str | None = None,
    ) -> Measure:
        measure_source_column = source_column_override or self.source_column
        metadata: dict[str, Any] = {
            "source": dataset,
            "source_column": self.source_column,
            "grain": list(grain),
            "unit": self.unit,
            "aggregation": self.aggregation,
        }
        if self.currency_column:
            metadata["currency_column"] = self.currency_column
            metadata["currency_grouping"] = "required_for_additive_result"
        if self.paired_currency_column:
            metadata["paired_currency_column"] = self.paired_currency_column
        if self.guard_column:
            metadata["guard_column"] = self.guard_column
        if self.numerator_column:
            metadata["numerator_column"] = self.numerator_column
        if self.denominator_column:
            metadata["denominator_column"] = self.denominator_column
        if self.null_behavior:
            metadata["null_behavior"] = self.null_behavior

        if self.aggregation == "sum":
            expression = lambda table: table[measure_source_column].sum()
        elif self.aggregation == "sum_preserve_null":
            expression = self._sum_preserve_null
        elif self.aggregation == "difference_preserve_null":
            expression = self._difference_preserve_null
        elif self.aggregation == "difference":
            expression = lambda table: table[self.source_column].sum() - table[self.denominator_column].sum()
        elif self.aggregation == "sum_by_currency":
            expression = self._sum_by_currency
        elif self.aggregation == "sum_by_group_column":
            expression = self._sum_by_group_column
        elif self.aggregation == "scaled_sum":
            expression = self._scaled_sum
        elif self.aggregation == "ratio":
            expression = self._ratio
        elif self.aggregation == "ratio_preserve_null":
            expression = self._ratio_preserve_null
        elif self.aggregation == "ratio_by_currency":
            expression = self._ratio_by_currency
        elif self.aggregation == "roas":
            expression = self._roas
        elif self.aggregation == "non_additive":
            expression = lambda table: table[self.source_column].max()
        else:
            raise ValueError(f"Unsupported semantic aggregation: {self.aggregation}")

        return Measure(expr=expression, description=self.description, metadata=metadata)

    def _sum_by_currency(self, table):
        source_has_value = table[self.source_column].notnull()
        currency = ibis.ifelse(source_has_value, table[self.currency_column], None)
        value = table[self.source_column].sum()
        has_single_currency = (currency.nunique() == 1) & ~(
            source_has_value & table[self.currency_column].isnull()
        ).any()
        return ibis.ifelse(has_single_currency, value, None)

    def _sum_by_group_column(self, table):
        value = table[self.source_column].sum()
        grouping_value = table[self.guard_column]
        has_single_value = (grouping_value.nunique() == 1) & ~grouping_value.isnull().any()
        return ibis.ifelse(has_single_value, value, None)

    def _sum_preserve_null(self, table):
        value = table[self.source_column].sum()
        has_null = table[self.source_column].isnull().any()
        return ibis.ifelse(has_null, None, value)

    def _difference_preserve_null(self, table):
        left = table[self.source_column]
        right = table[self.denominator_column]
        has_null = left.isnull().any() | right.isnull().any()
        difference = left.sum() - right.sum()
        return ibis.ifelse(has_null, None, difference)

    def _scaled_sum(self, table):
        value = table[self.source_column].sum() * self.multiplier
        currency = table[self.currency_column]
        has_single_currency = (currency.nunique() == 1) & ~currency.isnull().any()
        return ibis.ifelse(has_single_currency, value, None)

    def _ratio(self, table):
        numerator = table[self.numerator_column].sum()
        denominator = table[self.denominator_column].sum()
        value = numerator / denominator * self.multiplier
        return ibis.ifelse(denominator > 0, value, None)

    def _ratio_preserve_null(self, table):
        numerator_values = table[self.numerator_column]
        denominator_values = table[self.denominator_column]
        numerator = numerator_values.sum()
        denominator = denominator_values.sum()
        has_null = numerator_values.isnull().any() | denominator_values.isnull().any()
        value = numerator / denominator * self.multiplier
        return ibis.ifelse((denominator > 0) & ~has_null, value, None)

    def _ratio_by_currency(self, table):
        numerator = table[self.numerator_column].sum()
        denominator = table[self.denominator_column].sum()
        currency = table[self.currency_column]
        has_single_currency = (currency.nunique() == 1) & ~currency.isnull().any()
        valid = (denominator > 0) & has_single_currency
        value = numerator / denominator * self.multiplier
        return ibis.ifelse(valid, value, None)

    def _roas(self, table):
        revenue_currency = table[self.currency_column]
        cost_currency = table[self.paired_currency_column]
        has_one_matching_currency = (
            (revenue_currency.nunique() == 1)
            & (cost_currency.nunique() == 1)
            & ~revenue_currency.isnull().any()
            & ~cost_currency.isnull().any()
            & (revenue_currency.max() == cost_currency.max())
        )
        revenue = table[self.numerator_column].sum()
        cost = table[self.denominator_column].sum()
        return ibis.ifelse((cost > 0) & has_one_matching_currency, revenue / cost, None)
