"""End-to-end integration test of the appeal flow."""

from pathlib import Path
import json
import pytest
from gltest import get_contract_factory


def test_appeal_initialization_and_linking(admin, debater_pro, debater_con):
    rep_factory = get_contract_factory("Reputation")
    rep = rep_factory.deploy(account=admin)

    arena_factory = get_contract_factory("Arena")
    arena = arena_factory.deploy(account=admin)

    appeal_factory = get_contract_factory("AppealCourt")
    appeal = appeal_factory.deploy(account=admin)

    # Link dependencies
    arena.connect(admin).set_dependencies(args=[rep.address, appeal.address]).transact()
    appeal.connect(admin).set_dependencies(args=[arena.address, rep.address]).transact()
    rep.connect(admin).set_authorized(args=[arena.address, True]).transact()
    rep.connect(admin).set_authorized(args=[appeal.address, True]).transact()

    # Initial count
    count = appeal.get_appeal_count().call()
    assert count == 0

    # List appeals when empty
    appeals_list = json.loads(appeal.list_appeals(args=[0, 10]).call())
    assert len(appeals_list) == 0
