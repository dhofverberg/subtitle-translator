from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.platform.startswith("win") and "PYTEST_DEBUG_TEMPROOT" not in os.environ:
    os.environ["PYTEST_DEBUG_TEMPROOT"] = str(Path(__file__).resolve().parent / ".pytest-tmp")
