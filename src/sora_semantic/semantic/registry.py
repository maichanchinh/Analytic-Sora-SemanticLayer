"""Registry for Boring Semantic Layer tables."""

from boring_semantic_layer import SemanticTable


class SemanticRegistry:
    """Hold named Boring Semantic Layer tables for later query integration."""

    def __init__(self) -> None:
        self._tables: dict[str, SemanticTable] = {}

    def register(self, name: str, table: SemanticTable) -> None:
        """Register a semantic table under a project-level name."""
        self._tables[name] = table

    def get(self, name: str) -> SemanticTable:
        """Return a registered table; raise ``KeyError`` when absent."""
        return self._tables[name]

    @property
    def names(self) -> tuple[str, ...]:
        """Return registered names in insertion order."""
        return tuple(self._tables)
