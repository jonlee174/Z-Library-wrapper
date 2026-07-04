"""Frozen-app entry point.

PyInstaller runs the given script as the top-level module, which breaks the
package's relative imports if we point it straight at zlibgui/__main__.py. This
thin launcher imports the package properly so `from .` imports resolve.
"""

from zlibgui.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
