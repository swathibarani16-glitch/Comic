"""
api/index.py
------------
Vercel serverless entry point.
Re-exports the FastAPI ASGI app so Vercel's @vercel/python runtime can serve it.
"""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so all local imports resolve
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from main import app  # noqa: E402
