from pathlib import Path
import json
import pytest
from gltest import get_contract_factory

CONTRACT_REP = Path(__file__).resolve().parent.parent / "contracts" / "reputation.py"


def test_reputation_recording(admin, debater_pro):
    factory = get_contract_factory("Reputation")
    rep = factory.deploy(account=admin)

    addr = str(getattr(debater_pro, "address", debater_pro))

    # Initial reputation
    initial_raw = rep.get_reputation(args=[addr]).call()
    initial = json.loads(initial_raw)
    assert initial["wins"] == 0
    assert initial["losses"] == 0
    assert initial["tier"] == "Novice"

    # Record WIN by admin
    rep.connect(admin).record_result(args=[addr, "WIN"]).transact()
    rep.connect(admin).record_result(args=[addr, "WIN"]).transact()
    rep.connect(admin).record_result(args=[addr, "LOSE"]).transact()

    updated_raw = rep.get_reputation(args=[addr]).call()
    updated = json.loads(updated_raw)
    assert updated["wins"] == 2
    assert updated["losses"] == 1
    assert updated["total_matches"] == 3
    assert updated["win_rate"] == 66
