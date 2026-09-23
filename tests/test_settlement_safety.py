"""Tests for value-bearing fail-safe arena settlement.

Ensures that an arena reaches state 'FINAL' ONLY after the required native payouts
succeed, and remains in 'SETTLED' if payouts need to be claimed or retried.
"""

from pathlib import Path
import json
import pytest
from gltest import get_contract_factory


def test_payout_success_and_finality(admin, debater_pro, debater_con):
    rep_factory = get_contract_factory("Reputation")
    rep = rep_factory.deploy(account=admin)

    arena_factory = get_contract_factory("Arena")
    arena = arena_factory.deploy(account=admin)

    appeal_factory = get_contract_factory("AppealCourt")
    appeal = appeal_factory.deploy(account=admin)

    arena.connect(admin).set_dependencies(args=[rep.address, appeal.address]).transact()
    rep.connect(admin).set_authorized(args=[arena.address, True]).transact()

    pro_addr = str(getattr(debater_pro, "address", debater_pro))
    con_addr = str(getattr(debater_con, "address", debater_con))

    # 1. Seed settled arena with completed payout
    arena.connect(admin).admin_seed_arena(
        args=[
            "Settlement test claim",
            ["https://en.wikipedia.org"],
            pro_addr,
            con_addr,
            1000,
            "FINAL",
            "PRO_WINS",
            "Pro presented comprehensive empirical evidence.",
            90,
        ]
    ).transact()

    raw_data = arena.get_arena(args=["1"]).call()
    data = json.loads(raw_data)
    assert data["state"] == "FINAL"
    assert data["payout_done"] is True
    assert data["verdict"] == "PRO_WINS"

    # Reputation was updated on FINAL settlement
    rep_raw = rep.get_reputation(args=[pro_addr]).call()
    rep_data = json.loads(rep_raw)
    assert rep_data["wins"] >= 1


def test_payout_fail_safe_retains_settled_until_claimed(admin, debater_pro, debater_con):
    rep_factory = get_contract_factory("Reputation")
    rep = rep_factory.deploy(account=admin)

    arena_factory = get_contract_factory("Arena")
    arena = arena_factory.deploy(account=admin)

    appeal_factory = get_contract_factory("AppealCourt")
    appeal = appeal_factory.deploy(account=admin)

    arena.connect(admin).set_dependencies(args=[rep.address, appeal.address]).transact()
    rep.connect(admin).set_authorized(args=[arena.address, True]).transact()

    pro_addr = str(getattr(debater_pro, "address", debater_pro))
    con_addr = str(getattr(debater_con, "address", debater_con))

    # 1. Seed arena in SETTLED state without completed payout (simulating transient payout requirement)
    arena.connect(admin).admin_seed_arena(
        args=[
            "Fail-safe recovery claim",
            ["https://en.wikipedia.org"],
            pro_addr,
            con_addr,
            1000,
            "SETTLED",
            "PRO_WINS",
            "Pro won but native payout has not yet finalized.",
            85,
        ]
    ).transact()

    raw_data = arena.get_arena(args=["1"]).call()
    data = json.loads(raw_data)
    # Crucial: Must be in SETTLED, NOT FINAL
    assert data["state"] == "SETTLED"
    assert data["payout_done"] is False

    # 2. Debater or caller claims payout to retry and complete settlement
    arena.connect(debater_pro).claim_payout(args=["1"]).transact()

    # 3. After payout execution, state advances to FINAL
    final_data = json.loads(arena.get_arena(args=["1"]).call())
    assert final_data["state"] == "FINAL"
    assert final_data["payout_done"] is True
