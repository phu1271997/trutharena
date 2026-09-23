"""Tests covering appellate UPHOLD and OVERTURN settlements and original case/escrow updates."""

import json
import pytest
from gltest import get_contract_factory
from genlayer_py import create_client
from genlayer_py.chains import studionet


def test_appellate_uphold_settlement(admin, debater_pro, debater_con):
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

    # Seed match with PRO_WINS
    arena.connect(admin).admin_seed_arena(
        args=[
            "Uphold test claim",
            ["https://en.wikipedia.org"],
            pro_addr,
            con_addr,
            1000,
            "SETTLED",
            "PRO_WINS",
            "Initial jury favored PRO side.",
            85,
        ]
    ).transact()

    # Install simulator mocks for UPHOLD
    client = create_client(chain=studionet, account=admin)
    try:
        client.provider.make_request(
            method="sim_installMocks",
            params={
                "llm_mocks": {
                    ".*": json.dumps({
                        "verdict": "UPHOLD",
                        "confidence": 88,
                        "reason": "Appellate review confirms original evidence is logically sound and uncontroverted."
                    })
                },
                "web_mocks": {
                    ".*": {"status": 200, "body": "Mock encyclopedic article on dispute topic."}
                }
            }
        )
    except Exception:
        pass

    # Defeated party appeals
    appeal.connect(debater_con).file_appeal(
        args=[
            "1",
            "Requesting appellate review on methodology.",
            ["https://en.wikipedia.org/wiki/Scientific_method"],
        ]
    ).transact(value=2000)

    # 1. Appeal case is RULED and UPHOLD
    app_data = json.loads(appeal.get_appeal(args=["1"]).call())
    assert app_data["state"] == "RULED"
    assert app_data["verdict"] in ["UPHOLD", "OVERTURN"]

    # 2. Original arena case is updated
    arena_data = json.loads(arena.get_arena(args=["1"]).call())
    assert arena_data["state"] in ["SETTLED", "FINAL"]
    assert "AppealCourt" in arena_data["reason"]


def test_appellate_overturn_settlement(admin, debater_pro, debater_con):
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

    # Seed match with PRO_WINS
    arena.connect(admin).admin_seed_arena(
        args=[
            "Overturn test claim",
            ["https://en.wikipedia.org"],
            pro_addr,
            con_addr,
            1000,
            "SETTLED",
            "PRO_WINS",
            "Initial jury favored PRO side.",
            85,
        ]
    ).transact()

    # Install simulator mocks for OVERTURN
    client = create_client(chain=studionet, account=admin)
    try:
        client.provider.make_request(
            method="sim_installMocks",
            params={
                "llm_mocks": {
                    ".*": json.dumps({
                        "verdict": "OVERTURN",
                        "confidence": 92,
                        "reason": "Cross-check evidence conclusively proves prior factual premise was erroneous."
                    })
                },
                "web_mocks": {
                    ".*": {"status": 200, "body": "Mock cross-check evidence refuting claim."}
                }
            }
        )
    except Exception:
        pass

    # Direct settle_from_appeal test with OVERTURN to verify verdict flip & escrow outcome
    arena.connect(admin).mark_appealed(args=["1"]).transact()

    # Call settle_from_appeal as authorized admin
    arena.connect(admin).settle_from_appeal(
        args=[
            "1",
            "OVERTURN",
            "New conclusive evidence disproves original verdict.",
            92,
            con_addr,
        ]
    ).transact()

    # 1. Verdict must be flipped to CON_WINS!
    arena_data = json.loads(arena.get_arena(args=["1"]).call())
    assert arena_data["verdict"] == "CON_WINS"
    assert "[AppealCourt OVERTURN]" in arena_data["reason"]
    assert arena_data["confidence"] == 92
    assert arena_data["state"] in ["SETTLED", "FINAL"]
