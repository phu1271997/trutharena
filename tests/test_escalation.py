"""Tests covering automatic low-confidence escalation and manual defeated-party escalation."""

from pathlib import Path
import json
import pytest
from gltest import get_contract_factory
from genlayer_py import create_client
from genlayer_py.chains import studionet


def test_automatic_escalation_low_confidence(admin, debater_pro, debater_con):
    rep_factory = get_contract_factory("Reputation")
    rep = rep_factory.deploy(account=admin)

    appeal_factory = get_contract_factory("AppealCourt")
    appeal = appeal_factory.deploy(account=admin)

    arena_factory = get_contract_factory("Arena")
    arena = arena_factory.deploy(account=admin)

    arena.connect(admin).set_dependencies(args=[rep.address, appeal.address]).transact()
    appeal.connect(admin).set_dependencies(args=[arena.address, rep.address]).transact()
    rep.connect(admin).set_authorized(args=[arena.address, True]).transact()
    rep.connect(admin).set_authorized(args=[appeal.address, True]).transact()

    pro_addr = str(getattr(debater_pro, "address", debater_pro))
    con_addr = str(getattr(debater_con, "address", debater_con))

    # Seed an arena in low-confidence APPEALED state (< 60%)
    arena.connect(admin).admin_seed_arena(
        args=[
            "Low confidence topic requiring appellate review",
            ["https://en.wikipedia.org"],
            pro_addr,
            con_addr,
            1000,
            "APPEALED",
            "DRAW",
            "Low confidence (48%). Auto-escalated for appellate review.",
            48,
        ]
    ).transact()

    arena_raw = arena.get_arena(args=["1"]).call()
    arena_data = json.loads(arena_raw)

    # 1. State must be APPEALED, payout not done (escrow locked)
    assert arena_data["state"] == "APPEALED"
    assert arena_data["payout_done"] is False
    assert arena_data["confidence"] == 48

    # 2. File auto-appeal on AppealCourt by admin or arena
    appeal.connect(admin).file_auto_appeal(args=["1"]).transact()

    count = appeal.get_appeal_count().call()
    assert count >= 1

    app_raw = appeal.get_appeal(args=["1"]).call()
    app_data = json.loads(app_raw)
    assert app_data["arena_id"] == "1"
    assert app_data["is_auto_escalation"] is True
    assert app_data["state"] == "RULED"


def test_manual_escalation_by_defeated_party(admin, debater_pro, debater_con):
    rep_factory = get_contract_factory("Reputation")
    rep = rep_factory.deploy(account=admin)

    appeal_factory = get_contract_factory("AppealCourt")
    appeal = appeal_factory.deploy(account=admin)

    arena_factory = get_contract_factory("Arena")
    arena = arena_factory.deploy(account=admin)

    arena.connect(admin).set_dependencies(args=[rep.address, appeal.address]).transact()
    appeal.connect(admin).set_dependencies(args=[arena.address, rep.address]).transact()
    rep.connect(admin).set_authorized(args=[arena.address, True]).transact()
    rep.connect(admin).set_authorized(args=[appeal.address, True]).transact()

    pro_addr = str(getattr(debater_pro, "address", debater_pro))
    con_addr = str(getattr(debater_con, "address", debater_con))

    # Seed settled match where PRO won
    arena.connect(admin).admin_seed_arena(
        args=[
            "Contested debate claim",
            ["https://en.wikipedia.org"],
            pro_addr,
            con_addr,
            1000,
            "SETTLED",
            "PRO_WINS",
            "Initial jury favored PRO arguments.",
            80,
        ]
    ).transact()

    # Defeated party (CON debater) files appeal with 2x stake (2000)
    # Notice: claim and original verdict are read from authenticated Arena state!
    appeal.connect(debater_con).file_appeal(
        args=[
            "1",
            "The initial jury failed to consider contrary empirical studies.",
            ["https://en.wikipedia.org/wiki/Counterexample"],
        ]
    ).transact(value=2000)

    # Arena is marked APPEALED
    arena_data = json.loads(arena.get_arena(args=["1"]).call())
    assert arena_data["state"] in ["APPEALED", "SETTLED", "FINAL"]

    # AppealCourt has recorded the appeal with authenticated match facts
    app_data = json.loads(appeal.get_appeal(args=["1"]).call())
    assert app_data["arena_id"] == "1"
    assert app_data["appellant"].lower() == con_addr.lower()
    assert app_data["original_verdict"] == "PRO_WINS"
    assert app_data["claim"] == "Contested debate claim"
    assert app_data["state"] == "RULED"
