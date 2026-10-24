"""Opt-in experiment request budget and numeric usage; never stores content."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class UsageMeter:
    limit: int
    calls: list[dict] = field(default_factory=list)

    def summary(self):
        return {"limit": self.limit, "attempted": len(self.calls),
                "usage_reported": sum(item.get("usage_reported", False) for item in self.calls),
                "prompt_tokens": sum(item.get("prompt_tokens", 0) for item in self.calls),
                "completion_tokens": sum(item.get("completion_tokens", 0) for item in self.calls),
                "calls": self.calls}


_meter: ContextVar[UsageMeter | None] = ContextVar("model_usage_meter", default=None)


def begin_call(kind: str):
    meter = _meter.get()
    if meter is not None:
        if len(meter.calls) >= meter.limit:
            raise RuntimeError("Experiment provider request budget exhausted")
        meter.calls.append({"kind": kind, "usage_reported": False})


def record_usage(payload: dict):
    meter = _meter.get()
    if meter is None or not meter.calls:
        return
    usage = payload.get("usage", {})
    if isinstance(usage, dict):
        values = {key: usage[key] for key in ("prompt_tokens", "completion_tokens")
                  if isinstance(usage.get(key), int) and not isinstance(usage[key], bool) and usage[key] >= 0}
        meter.calls[-1].update(values, usage_reported=len(values) == 2)


@contextmanager
def usage_budget(limit: int):
    meter = UsageMeter(limit)
    token = _meter.set(meter)
    try:
        yield meter
    finally:
        _meter.reset(token)
