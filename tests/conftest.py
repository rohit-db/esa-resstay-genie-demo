from __future__ import annotations

import json
from datetime import date

import pytest

TINY = dict(as_of_date=date(2026, 1, 31), story_anchor_date=date(2026, 1, 31), seed=7, scale_properties=30)


@pytest.fixture(scope="session")
def tiny_cfg():
    from esa_resstay_demo.data.config import GenConfig
    return GenConfig(**TINY)


@pytest.fixture(scope="session")
def tiny_world(tiny_cfg):
    """Reference data, portfolio, and simulated events for the first three tiny properties."""
    from esa_resstay_demo.data.portfolio import build_portfolio
    from esa_resstay_demo.data.reference import build_dim_crm_account, build_sim_reference
    from esa_resstay_demo.data.simulate import simulate_property

    accounts = build_dim_crm_account(tiny_cfg)
    sim = build_sim_reference(accounts)
    portfolio = build_portfolio(tiny_cfg)
    props = portfolio.sim_inputs.to_dict("records")[:3]
    events = {p["bk_property_id"]: simulate_property(p, tiny_cfg, sim) for p in props}
    return {"cfg": tiny_cfg, "sim": sim, "portfolio": portfolio, "props": props, "events": events}


@pytest.fixture(scope="session")
def tiny_days(tiny_cfg):
    from esa_resstay_demo.data.facts import DayLookup
    return DayLookup(tiny_cfg)


class FakeCli:
    """Stands in for tools.lib.dbcli.Cli. `handlers` maps an argument prefix to a response or callable."""

    def __init__(self, handlers=None, profile="esa-resstay-demo", host="https://fe-sandbox-esa-resstay-demo.cloud.databricks.com"):
        self.profile, self._host = profile, host
        self.handlers = dict(handlers or {})
        self.calls: list[tuple] = []

    def _answer(self, kind, args):
        self.calls.append((kind, tuple(args)))
        for prefix in sorted(self.handlers, key=len, reverse=True):
            if tuple(args[: len(prefix)]) == prefix:
                value = self.handlers[prefix]
                return value(args) if callable(value) else value
        raise AssertionError(f"unexpected CLI call: {kind} {args}")

    def run(self, args, *, timeout=600):
        return self._answer("run", args) or ""

    def json(self, args, *, timeout=600):
        return self._answer("json", args)

    def api(self, method, path, body=None, *, timeout=600):
        return self._answer("api", [method, path, json.dumps(body) if body is not None else ""])

    def host(self):
        return self._host

    def current_user(self):
        return "operator@example.com"


@pytest.fixture
def fake_cli():
    return FakeCli
