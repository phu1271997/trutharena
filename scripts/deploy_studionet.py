#!/usr/bin/env python3
"""Deploy TruthArena contracts (Reputation, AppealCourt, Arena) to GenLayer studionet.

Usage:
    source ~/.genlayer/env.sh
    python3 scripts/deploy_studionet.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from genlayer_py import create_account, create_client
from genlayer_py.chains import studionet

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"


def get_address_from_receipt(receipt):
    if not receipt:
        return None
    addr = None
    if isinstance(receipt, dict):
        addr = (
            receipt.get("data", {}).get("contract_address")
            or receipt.get("contract_address")
            or receipt.get("contractAddress")
            or receipt.get("tx_data_decoded", {}).get("contract_address")
        )
    else:
        addr = getattr(receipt, "contract_address", None) or getattr(
            receipt, "contractAddress", None
        )
    return addr


def deploy_contract(client, account, contract_path: Path, name: str):
    code = contract_path.read_text()
    print(f"\n[+] Deploying {name} ({contract_path.name})...")

    # Schema pre-flight
    try:
        client.get_contract_schema_for_code(code.encode())
        print(f"    Schema check: PASSED")
    except Exception as e:
        print(f"    Schema check FAILED: {e}", file=sys.stderr)
        raise

    tx_hash = client.deploy_contract(code=code, account=account)
    print(f"    Tx hash: {tx_hash}")

    # Wait for finalized/accepted
    receipt = client.wait_for_transaction_receipt(
        transaction_hash=tx_hash, status="FINALIZED", interval=3000, retries=60
    )
    addr = get_address_from_receipt(receipt)
    if not addr:
        raise RuntimeError(f"Could not extract deployed address for {name}")

    print(f"    --> {name} deployed at: {addr}")
    return addr, tx_hash


def main() -> int:
    key = os.environ.get("GENLAYER_PRIVATE_KEY")
    if not key or "REPLACE_ME" in key:
        print(
            "ERROR: GENLAYER_PRIVATE_KEY not set. Run: source ~/.genlayer/env.sh",
            file=sys.stderr,
        )
        return 1

    account = create_account(key)
    client = create_client(chain=studionet, account=account)

    print("==================================================")
    print("TruthArena Deployment - GenLayer Studionet")
    print(f"Deployer: {account.address}")
    print(f"Chain:    {studionet.name} (id={studionet.id})")
    print("==================================================")

    # 1. Deploy Reputation
    rep_addr, rep_tx = deploy_contract(
        client, account, CONTRACTS / "reputation.py", "Reputation"
    )

    # 2. Deploy AppealCourt
    appeal_addr, appeal_tx = deploy_contract(
        client, account, CONTRACTS / "appeal_court.py", "AppealCourt"
    )

    # 3. Deploy Arena
    arena_addr, arena_tx = deploy_contract(
        client, account, CONTRACTS / "arena.py", "Arena"
    )

    print("\n[+] Linking contract permissions & dependencies...")

    try:
        # Authorize Arena and AppealCourt on Reputation
        tx1 = client.write_contract(
            address=rep_addr,
            function_name="set_authorized",
            args=[arena_addr, True],
            account=account,
        )
        client.wait_for_transaction_receipt(
            tx1, status="FINALIZED", interval=3000, retries=30
        )
        print("    Authorized Arena on Reputation.")

        tx2 = client.write_contract(
            address=rep_addr,
            function_name="set_authorized",
            args=[appeal_addr, True],
            account=account,
        )
        client.wait_for_transaction_receipt(
            tx2, status="FINALIZED", interval=3000, retries=30
        )
        print("    Authorized AppealCourt on Reputation.")

        # Set dependencies on AppealCourt
        tx3 = client.write_contract(
            address=appeal_addr,
            function_name="set_dependencies",
            args=[arena_addr, rep_addr],
            account=account,
        )
        client.wait_for_transaction_receipt(
            tx3, status="FINALIZED", interval=3000, retries=30
        )
        print("    Linked dependencies on AppealCourt.")

        # Set dependencies on Arena
        tx4 = client.write_contract(
            address=arena_addr,
            function_name="set_dependencies",
            args=[rep_addr, appeal_addr],
            account=account,
        )
        client.wait_for_transaction_receipt(
            tx4, status="FINALIZED", interval=3000, retries=30
        )
        print("    Linked dependencies on Arena.")
    except Exception as e:
        print(f"    Warning during linking: {e}", file=sys.stderr)

    deployments = {
        "network": "studionet",
        "chainId": studionet.id,
        "deployer": account.address,
        "contracts": {
            "Reputation": {
                "address": rep_addr,
                "tx": rep_tx,
                "explorer": f"https://genlayer-explorer.vercel.app/address/{rep_addr}",
            },
            "AppealCourt": {
                "address": appeal_addr,
                "tx": appeal_tx,
                "explorer": f"https://genlayer-explorer.vercel.app/address/{appeal_addr}",
            },
            "Arena": {
                "address": arena_addr,
                "tx": arena_tx,
                "explorer": f"https://genlayer-explorer.vercel.app/address/{arena_addr}",
            },
        },
    }

    dep_file = ROOT / "deployments.json"
    dep_file.write_text(json.dumps(deployments, indent=2))
    print(f"\n[v] Saved deployments to {dep_file}")

    # Write frontend .env
    frontend_env = ROOT / "frontend" / ".env"
    frontend_env.parent.mkdir(parents=True, exist_ok=True)
    env_content = f"""VITE_ARENA_CONTRACT={arena_addr}
VITE_APPEAL_CONTRACT={appeal_addr}
VITE_REPUTATION_CONTRACT={rep_addr}
VITE_STUDIO_RPC=https://studio.genlayer.com/api
VITE_CHAIN_ID=61999
"""
    frontend_env.write_text(env_content)
    (ROOT / "frontend" / ".env.example").write_text(
        env_content.replace(arena_addr, "0x...").replace(appeal_addr, "0x...").replace(rep_addr, "0x...")
    )
    print(f"[v] Updated {frontend_env}")

    # Write frontend/src/lib/addresses.ts fallback constants
    addr_ts = ROOT / "frontend" / "src" / "lib" / "addresses.ts"
    addr_content = f"""export const ARENA_CONTRACT = (import.meta.env.VITE_ARENA_CONTRACT || '{arena_addr}') as `0x${{string}}`;
export const APPEAL_CONTRACT = (import.meta.env.VITE_APPEAL_CONTRACT || '{appeal_addr}') as `0x${{string}}`;
export const REPUTATION_CONTRACT = (import.meta.env.VITE_REPUTATION_CONTRACT || '{rep_addr}') as `0x${{string}}`;
export const RPC_URL = import.meta.env.VITE_STUDIO_RPC || 'https://studio.genlayer.com/api';
"""
    addr_ts.write_text(addr_content)
    print(f"[v] Updated {addr_ts}")

    print("\n==================================================")
    print("DEPLOYMENT COMPLETE!")
    print(f"Arena:        {arena_addr}")
    print(f"AppealCourt:  {appeal_addr}")
    print(f"Reputation:   {rep_addr}")
    print("==================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
