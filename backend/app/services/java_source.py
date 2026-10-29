"""Compatibility import for app.analysis.parsers.java."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module("app.analysis.parsers.java")
