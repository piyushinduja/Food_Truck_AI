"""Path setup — import this first in any page file.

Adds the project root to sys.path so `from backend import ...` works.
"""
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
