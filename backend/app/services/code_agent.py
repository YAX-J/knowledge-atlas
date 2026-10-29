"""Compatibility import for the code-analysis engine."""
import sys
from app.agents.code_analysis import engine
sys.modules[__name__] = engine
