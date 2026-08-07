"""Ensure the project root is importable and tests run from it.

Tests reference the bundled catalogs by the relative path
``control_coverage/catalogs``, so pytest must be invoked from the project root.
This file's location pins that root for import resolution.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
