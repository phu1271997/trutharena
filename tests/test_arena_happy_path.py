from pathlib import Path
import json
import pytest
from gltest import get_contract_factory

CONTRACT_ARENA = Path(__file__).resolve().parent.parent / "contracts" / "arena.py"


def test_arena_happy_path_scaffold(admin, debater_pro, debater_con):
    factory = get_contract_factory("Arena")
    arena = factory.deploy(account=admin)

    # 1. Create Arena
    arena.connect(debater_pro).create_arena(
        args=["TruthArena claim", ["https://en.wikipedia.org"], 1000, "PRO"]
    ).transact(value=1000)

    count = arena.get_arena_count().call()
    assert count == 1

    arena_json = json.loads(arena.get_arena(args=["1"]).call())
    assert arena_json["state"] == "OPEN"
    assert arena_json["claim"] == "TruthArena claim"

    # 2. Opponent joins CON
    arena.connect(debater_con).join_side(args=["1", "CON"]).transact(value=1000)

    arena_json_locked = json.loads(arena.get_arena(args=["1"]).call())
    assert arena_json_locked["state"] == "LOCKED"
    assert arena_json_locked["current_round"] == 1

    # 3. Round 1 submission
    arena.connect(debater_pro).submit_argument(
        args=["1", "Pro argument round 1", ["https://en.wikipedia.org"]]
    ).transact()

    arena.connect(debater_con).submit_argument(
        args=["1", "Con argument round 1", ["https://en.wikipedia.org"]]
    ).transact()

    # Advances to round 2
    arena_json_r2 = json.loads(arena.get_arena(args=["1"]).call())
    assert arena_json_r2["current_round"] == 2
