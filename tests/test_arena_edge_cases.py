from pathlib import Path
import json
import pytest
from gltest import get_contract_factory

CONTRACT_ARENA = Path(__file__).resolve().parent.parent / "contracts" / "arena.py"


def test_arena_edge_cases(admin, debater_pro, debater_con):
    factory = get_contract_factory("Arena")
    arena = factory.deploy(account=admin)

    # Edge case 1: Zero stake
    with pytest.raises(Exception):
        arena.connect(debater_pro).create_arena(
            args=["Claim with zero stake", [], 0, "PRO"]
        ).transact(value=0)

    # Edge case 2: Empty claim
    with pytest.raises(Exception):
        arena.connect(debater_pro).create_arena(
            args=["", [], 1000, "PRO"]
        ).transact(value=1000)

    # Edge case 3: Value mismatch
    with pytest.raises(Exception):
        arena.connect(debater_pro).create_arena(
            args=["Valid claim", [], 1000, "PRO"]
        ).transact(value=500)

    # Create valid arena
    arena.connect(debater_pro).create_arena(
        args=["Valid claim", ["https://example.com"], 1000, "PRO"]
    ).transact(value=1000)

    # Edge case 4: Same user joining both sides
    with pytest.raises(Exception):
        arena.connect(debater_pro).join_side(args=["1", "CON"]).transact(value=1000)

    # Valid opponent joins
    arena.connect(debater_con).join_side(args=["1", "CON"]).transact(value=1000)

    # Edge case 5: Joining already locked arena
    with pytest.raises(Exception):
        arena.connect(debater_pro).join_side(args=["1", "CON"]).transact(value=1000)
