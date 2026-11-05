from __future__ import annotations

import json
from pathlib import Path

from .attainment_agent import AttainmentAgent
from .base import Context
from .data_agent import DataAgent
from .insights_agent import InsightsAgent
from .pacing_agent import PacingAgent
from .payout_agent import PayoutAgent
from .risk_agent import RiskAgent

ROOT = Path(__file__).resolve().parent.parent


class Orchestrator:
    """Runs the agents in dependency order over a shared context."""

    def __init__(self, agents=None):
        self.agents = agents or [DataAgent(), AttainmentAgent(), PacingAgent(),
                                 RiskAgent(), PayoutAgent(), InsightsAgent()]

    def run(self, config: dict, data_dir: str | Path) -> Context:
        ctx = Context(config=config, data_dir=str(data_dir))
        for agent in self.agents:
            agent(ctx)
        return ctx


def load_config(path: str | Path = ROOT / "comp_plan.json") -> dict:
    return json.loads(Path(path).read_text())


def run_pipeline(as_of_date: str | None = None, data_dir: str | Path = ROOT / "data",
                 config_path: str | Path = ROOT / "comp_plan.json") -> Context:
    cfg = load_config(config_path)
    if as_of_date:
        cfg["as_of_date"] = as_of_date
    return Orchestrator().run(cfg, data_dir)
