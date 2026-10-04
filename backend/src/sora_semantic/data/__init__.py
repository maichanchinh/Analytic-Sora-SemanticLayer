"""Read-only access to upstream data sources."""

from sora_semantic.data.silver import SilverDataSource, SilverManifest, SilverReadError

__all__ = ["SilverDataSource", "SilverManifest", "SilverReadError"]
