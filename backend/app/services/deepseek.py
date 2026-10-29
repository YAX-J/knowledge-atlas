"""Compatibility import for app.llm.providers.deepseek."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module("app.llm.providers.deepseek")
