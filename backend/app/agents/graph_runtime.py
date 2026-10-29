"""Compile per-run graphs without uploading source-bearing state to external tracing."""
from langsmith import tracing_context


def invoke(builder,state,**config):
    with tracing_context(enabled=False):
        return builder.compile().invoke(state,config={'callbacks':[],**config})
