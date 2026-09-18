"""Shared fixtures for TruthArena tests."""

import os
import sys
from pathlib import Path
import pytest
from gltest import create_account
from gltest.artifacts.contract import get_general_config

cfg = get_general_config()
cfg.set_contracts_dir((Path(__file__).resolve().parent.parent / "contracts").resolve())


def clear_known_contracts():
    for name, module in list(sys.modules.items()):
        if "genlayer" in name and hasattr(module, "__known_contract__"):
            setattr(module, "__known_contract__", None)


@pytest.fixture(autouse=True)
def cleanup():
    clear_known_contracts()
    yield
    clear_known_contracts()


@pytest.fixture
def admin():
    key = os.environ.get("GENLAYER_PRIVATE_KEY")
    if key and "REPLACE_ME" not in key:
        return create_account(key)
    return create_account()


@pytest.fixture
def debater_pro():
    key = os.environ.get("GENLAYER_PRIVATE_KEY_2") or os.environ.get("GENLAYER_PRIVATE_KEY")
    if key and "REPLACE_ME" not in key:
        return create_account(key)
    return create_account()


@pytest.fixture
def debater_con():
    key = os.environ.get("GENLAYER_PRIVATE_KEY_3") or os.environ.get("GENLAYER_PRIVATE_KEY")
    if key and "REPLACE_ME" not in key:
        return create_account(key)
    return create_account()
