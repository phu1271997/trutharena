"""Tests covering authorization barriers across Arena, AppealCourt, and Reputation."""

import json
import pytest
from gltest import get_contract_factory


def test_authorization_checks(admin, debater_pro, debater_con):
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

    # Seed match where PRO won
    arena.connect(admin).admin_seed_arena(
        args=[
            "Authorization test claim",
            ["https://en.wikipedia.org"],
            pro_addr,
            con_addr,
            1000,
            "SETTLED",
            "PRO_WINS",
            "PRO prevailed.",
            85,
        ]
    ).transact()

    # 1. Non-defeated party (WINNER: debater_pro) attempts to appeal -> rejected, appeal count remains 0
    appeal.connect(debater_pro).file_appeal(
        args=["1", "Winner trying to appeal", []]
    ).transact(value=2000)
    assert appeal.get_appeal_count().call() == 0

    # 2. Defeated debater providing insufficient stake (< 2000) -> rejected, appeal count remains 0
    appeal.connect(debater_con).file_appeal(
        args=["1", "Insufficient stake", []]
    ).transact(value=1000)
    assert appeal.get_appeal_count().call() == 0

    # 3. Unauthorized caller attempts to call file_auto_appeal on AppealCourt -> rejected, count remains 0
    appeal.connect(debater_con).file_auto_appeal(args=["1"]).transact()
    assert appeal.get_appeal_count().call() == 0

    # 4. Unauthorized caller attempts to call settle_from_appeal directly on Arena -> rejected, verdict remains PRO_WINS
    arena.connect(debater_pro).settle_from_appeal(
        args=["1", "OVERTURN", "Unauthorized spoof", 90, pro_addr]
    ).transact()
    arena_data = json.loads(arena.get_arena(args=["1"]).call())
    assert arena_data["verdict"] == "PRO_WINS"

    # 5. Unauthorized caller attempts to record reputation directly on Reputation -> rejected, wins remain 0
    rep.connect(debater_con).record_result(args=[con_addr, "WIN"]).transact()
    rep_data = json.loads(rep.get_reputation(args=[con_addr]).call())
    assert rep_data["wins"] == 0
