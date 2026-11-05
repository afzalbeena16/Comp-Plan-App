from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraceEntry:
    agent: str
    status: str
    seconds: float
    summary: str


@dataclass
class Context:
    """Shared blackboard the agents read from and write to."""
    config: dict
    data_dir: str
    frames: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    trace: list[TraceEntry] = field(default_factory=list)


class Agent:
    """An agent owns one responsibility and records what it did in the trace."""
    name = "Agent"
    role = ""

    def run(self, ctx: Context) -> str:  # returns a one-line summary
        raise NotImplementedError

    def __call__(self, ctx: Context) -> Context:
        start = time.perf_counter()
        try:
            summary = self.run(ctx)
            status = "ok"
        except Exception as exc:  # surface failures in the trace instead of crashing the app
            summary, status = f"{type(exc).__name__}: {exc}", "error"
            ctx.trace.append(TraceEntry(self.name, status, time.perf_counter() - start, summary))
            raise
        ctx.trace.append(TraceEntry(self.name, status, time.perf_counter() - start, summary))
        return ctx
