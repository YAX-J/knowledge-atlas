"""Compatibility import for app.analysis.parsers.tree_sitter."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module("app.analysis.parsers.tree_sitter")
