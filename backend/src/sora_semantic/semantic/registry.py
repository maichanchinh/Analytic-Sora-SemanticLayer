"""Build Boring Semantic Layer tables from the verified Silver catalog."""

from __future__ import annotations

from typing import Any

from boring_semantic_layer import SemanticTable

from sora_semantic.data.silver import SilverDataSource
from sora_semantic.semantic.models import (
    FINANCE_DAILY_DEFINITION,
    SILVER_SEMANTIC_DEFINITIONS,
    FinanceDailyDefinition,
    SilverSemanticDefinition,
)


class SemanticRegistry:
    """Expose only catalog-backed Boring Semantic Layer definitions.

    Definitions can be listed without connecting to Silver. To build a BSL
    table, supply a connected ``SilverDataSource``; its Parquet scan remains
    lazy until query execution. Arbitrary and staging datasets cannot be
    registered.
    """

    def __init__(self, source: SilverDataSource | None = None) -> None:
        self._source = source
        self._finance_definition = FINANCE_DAILY_DEFINITION
        self._definitions: dict[str, SilverSemanticDefinition] = {
            definition.name: definition for definition in SILVER_SEMANTIC_DEFINITIONS
        }
        self._tables: dict[str, SemanticTable] = {}

    def get(self, name: str) -> SemanticTable:
        """Return a registered BSL table; raise ``KeyError`` when absent."""
        if name not in self._definitions and name != self._finance_definition.name:
            raise KeyError(name)
        if self._source is None:
            raise RuntimeError("SemanticRegistry.get() requires a connected SilverDataSource")
        if name not in self._tables:
            if name == self._finance_definition.name:
                self._tables[name] = self._finance_definition.build(
                    self._source.table("admob_mediation_daily"),
                    self._source.table("google_ads_campaign_geo_daily"),
                    self._source.table("fx_daily"),
                )
            else:
                definition = self._definitions[name]
                self._tables[name] = definition.build(self._source.table(name))
        return self._tables[name]

    def describe(self, name: str | None = None) -> dict[str, Any] | tuple[dict[str, Any], ...]:
        """Return source, grain, unit, currency, and supported field metadata."""
        if name is not None:
            if name == self._finance_definition.name:
                return self._finance_definition.metadata()
            return self._definitions[name].metadata()
        return tuple(definition.metadata() for definition in self.definitions)

    @property
    def names(self) -> tuple[str, ...]:
        """Return supported production dataset names in catalog order."""
        return (*self._definitions, self._finance_definition.name)

    @property
    def definitions(self) -> tuple[SilverSemanticDefinition | FinanceDailyDefinition, ...]:
        """Return the immutable catalog-backed semantic definitions."""
        return (*self._definitions.values(), self._finance_definition)
