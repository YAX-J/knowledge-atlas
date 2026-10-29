"""Compatibility import for app.analysis.languages."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module("app.analysis.languages")
