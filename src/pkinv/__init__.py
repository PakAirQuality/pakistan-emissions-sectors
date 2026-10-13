"""Pakistan emissions inventory.

__version__ is the single source of truth for the release version, and
pyproject.toml derives its own version from this attribute rather than repeating
it. That direction matters: reading the version from installed package metadata
instead would report whatever was last `pip install`-ed, so a source tree could
stamp a stale version into the release manifest - which is precisely the class of
drift this release exists to eliminate.
"""

__version__ = "1.0.0rc67"

__all__ = ["__version__"]
