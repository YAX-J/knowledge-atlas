"""Compatibility import for app.analysis.parsers.markdown."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module("app.analysis.parsers.markdown")
