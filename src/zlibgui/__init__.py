"""Z-Library desktop wrapper: a simple search-and-download GUI."""

# Must run before ANY submodule (and thus zlibrary) is imported, so that the
# bundled zlibrary's `EnumMeta | type` annotation doesn't crash on Python 3.9.
from .patches import apply_pre_import_patches as _pre

_pre()

__version__ = "1.0.0"
APP_NAME = "ZLibraryWrapper"
