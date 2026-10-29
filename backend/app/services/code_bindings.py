"""Compatibility import for app.analysis.bindings."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module("app.analysis.bindings")
