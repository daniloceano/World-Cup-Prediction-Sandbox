"""Bootstrap for the Streamlit app.

Ensures ``src/`` is importable without installing the package and without
fragile absolute paths. Every page imports this module first.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

PROJECT_ROOT = _ROOT
