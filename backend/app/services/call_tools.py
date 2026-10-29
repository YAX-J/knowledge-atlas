"""Compatibility import for the bounded code-agent graph."""
import sys
from app.agents.code_analysis import graph
sys.modules[__name__] = graph
