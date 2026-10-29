"""Compatibility import for app.analysis.compilers.adapter."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module("app.analysis.compilers.adapter")
