"""StoneReader services package — log watcher, parser, engine, and detection helpers.

This package is intentionally headless: no wxPython, no presenter, no view.
Public API is added by later phase-2 plans (`GameTracker`, `Watcher`, etc.).
The current contents are the building blocks consumed by those modules.
"""

from __future__ import annotations
