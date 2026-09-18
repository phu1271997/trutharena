from pathlib import Path
import json
import pytest
from gltest import get_contract_factory

CONTRACT_APPEAL = Path(__file__).resolve().parent.parent / "contracts" / "appeal_court.py"


def test_appeal_initialization(admin, debater_pro):
    factory = get_contract_factory("AppealCourt")
    appeal_court = factory.deploy(account=admin)

    count = appeal_court.get_appeal_count().call()
    assert count == 0
