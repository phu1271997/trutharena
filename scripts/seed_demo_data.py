#!/usr/bin/env python3
"""Seed TruthArena with diverse demo arenas on GenLayer studionet:
1. OPEN match (awaiting opponent)
2. FINAL match (PRO_WINS with complete native payout)
3. FINAL match (CON_WINS with complete native payout)
4. APPEALED match (Auto-escalated due to low confidence < 60% with AppealCourt case)

Usage:
    source ~/.genlayer/env.sh
    python3 scripts/seed_demo_data.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from genlayer_py import create_account, create_client
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionStatus

ROOT = Path(__file__).resolve().parent.parent
DEPLOYMENTS_PATH = ROOT / "deployments.json"


def retry_call(fn, max_retries=5, delay=3):
    for i in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if i == max_retries - 1:
                raise
            print(f"    [!] Network glitch ({e}). Retrying in {delay}s...")
            time.sleep(delay)


def main() -> int:
    key = os.environ.get("GENLAYER_PRIVATE_KEY")
    if not key:
        print("ERROR: GENLAYER_PRIVATE_KEY not set. Run: source ~/.genlayer/env.sh", file=sys.stderr)
        return 1

    if not DEPLOYMENTS_PATH.exists():
        print("ERROR: deployments.json not found. Run scripts/deploy_studionet.py first.", file=sys.stderr)
        return 1

    dep = json.loads(DEPLOYMENTS_PATH.read_text())
    arena_addr = dep["contracts"]["Arena"]["address"]
    appeal_addr = dep["contracts"]["AppealCourt"]["address"]
    account = create_account(key)
    client = create_client(chain=studionet, account=account)

    print("==================================================")
    print(f"Seeding TruthArena Demo Data on Studionet")
    print(f"Arena Address:       {arena_addr}")
    print(f"AppealCourt Address: {appeal_addr}")
    print(f"Admin Account:       {account.address}")
    print("==================================================")

    p1 = account.address
    p2 = "0xFdc45874126A0580d9A9d034F2AA20d9bdad8235"
    p3 = "0xCd8bE5b63AAb48E65AD9c2f64a9768Cbc923Df81"

    # Check existing count
    cnt_res = retry_call(lambda: client.read_contract(address=arena_addr, function_name="get_arena_count"))
    current_cnt = int(cnt_res) if cnt_res is not None else 0
    print(f"Current arena count: {current_cnt}")

    if current_cnt < 1:
        # 1. Seed OPEN Arena
        print("\n[+] Seeding Arena 1 (OPEN - Nuclear Energy)...")
        tx1 = retry_call(lambda: client.write_contract(
            address=arena_addr,
            function_name="admin_seed_arena",
            args=[
                "Nuclear energy is indispensable for achieving net-zero global emissions by 2050.",
                ["https://en.wikipedia.org/wiki/Nuclear_power", "https://ourworldindata.org/nuclear-energy"],
                p1,
                "",
                500000000000000000,  # 0.5 GEN
                "OPEN",
                "",
                "",
                0
            ],
            account=account,
        ))
        retry_call(lambda: client.wait_for_transaction_receipt(tx1, status=TransactionStatus.ACCEPTED, interval=3000, retries=30))
        print(f"    Arena 1 created (tx: {tx1})")

        try:
            tx1_arg = retry_call(lambda: client.write_contract(
                address=arena_addr,
                function_name="admin_add_argument",
                args=[
                    "1",
                    p1,
                    "Nuclear power provides zero-carbon baseload electricity with the highest capacity factor (>92%) of any energy source, making grid stability without fossil fuels practically achievable.",
                    ["https://ourworldindata.org/nuclear-energy"],
                    1
                ],
                account=account,
            ))
            retry_call(lambda: client.wait_for_transaction_receipt(tx1_arg, status=TransactionStatus.ACCEPTED, interval=3000, retries=30))
        except Exception as e:
            print(f"    Note on arg 1: {e}")

    # 2. Seed FINAL PRO_WINS Arena if needed
    cnt_res = retry_call(lambda: client.read_contract(address=arena_addr, function_name="get_arena_count"))
    if int(cnt_res) < 2:
        print("\n[+] Seeding Arena 2 (FINAL: PRO_WINS - Autonomous AI Agents)...")
        tx2 = retry_call(lambda: client.write_contract(
            address=arena_addr,
            function_name="admin_seed_arena",
            args=[
                "Autonomous AI agents will execute more than 30% of production software refactoring tasks by 2027.",
                ["https://en.wikipedia.org/wiki/Software_engineering"],
                p1,
                p2,
                1000000000000000000,  # 1.0 GEN
                "FINAL",
                "PRO_WINS",
                "The PRO side provided verifiable empirical benchmarks from modern multi-agent coding systems showing rapid acceleration in complex AST transformations. The CON side relied on skepticism regarding edge cases without countering empirical velocity.",
                88
            ],
            account=account,
        ))
        retry_call(lambda: client.wait_for_transaction_receipt(tx2, status=TransactionStatus.ACCEPTED, interval=3000, retries=30))
        print(f"    Arena 2 created (tx: {tx2})")

        args_case_2 = [
            (p1, "Empirical developer studies reveal AI assisted tools already generate 40%+ of boilerplate code. Refactoring is fundamentally graph transformation on ASTs, where agentic models excel.", ["https://en.wikipedia.org/wiki/Abstract_syntax_tree"], 1),
            (p2, "Enterprise software relies on legacy domain knowledge and undocumented architectural constraints that generic LLMs hallucinate on, making autonomous commits too risky for core banking and medical infra.", ["https://en.wikipedia.org/wiki/Legacy_system"], 1),
            (p1, "Agentic frameworks with static analysis tools and automated sandboxed test suites eliminate hallucinations before PR submission, resolving the risk argument.", ["https://en.wikipedia.org/wiki/Static_program_analysis"], 2),
            (p2, "Regulatory compliance (e.g. EU AI Act) will mandate human-in-the-loop verification, preventing fully autonomous refactoring deployments.", ["https://en.wikipedia.org/wiki/Artificial_Intelligence_Act"], 3),
        ]
        for submitter, text, urls, rnd in args_case_2:
            time.sleep(1)
            try:
                tx_a = retry_call(lambda: client.write_contract(
                    address=arena_addr,
                    function_name="admin_add_argument",
                    args=["2", submitter, text, urls, rnd],
                    account=account,
                ))
                retry_call(lambda: client.wait_for_transaction_receipt(tx_a, status=TransactionStatus.ACCEPTED, interval=2000, retries=30))
            except Exception:
                pass
        print("    Added arguments for Arena 2.")

    # 3. Seed FINAL CON_WINS Arena if needed
    cnt_res = retry_call(lambda: client.read_contract(address=arena_addr, function_name="get_arena_count"))
    if int(cnt_res) < 3:
        print("\n[+] Seeding Arena 3 (FINAL: CON_WINS - Zero Knowledge Prover Scaling)...")
        tx3 = retry_call(lambda: client.write_contract(
            address=arena_addr,
            function_name="admin_seed_arena",
            args=[
                "Zero-Knowledge proofs are computationally ready to replace all optimistic rollups within 12 months.",
                ["https://ethereum.org/en/developers/docs/scaling/zk-rollups/"],
                p2,
                p3,
                2000000000000000000,  # 2.0 GEN
                "FINAL",
                "CON_WINS",
                "CON convincingly demonstrated with current ASIC and FPGA prover latency curves that proving Ethereum L1 execution at scale within 12 months entails prohibitive cost and hardware scarcity barriers that Optimistic fraud proofs currently avoid.",
                84
            ],
            account=account,
        ))
        retry_call(lambda: client.wait_for_transaction_receipt(tx3, status=TransactionStatus.ACCEPTED, interval=3000, retries=30))
        print(f"    Arena 3 created (tx: {tx3})")

        args_case_3 = [
            (p2, "ZK-SNARK proof generation speeds have improved 100x over the past two years, making real-time EVM block proving within immediate reach.", ["https://ethereum.org/en/developers/docs/scaling/zk-rollups/"], 1),
            (p3, "Proof generation for complex EVM transactions still requires massive clusters costing 10-50x more in hardware and electrical cost than optimistic verification.", ["https://en.wikipedia.org/wiki/Zero-knowledge_proof"], 1),
            (p2, "Specialized hardware (ZK-ASICs) slated for production in Q4 will bring proving costs down to parity with centralized sequencers.", ["https://en.wikipedia.org/wiki/Application-specific_integrated_circuit"], 2),
            (p3, "Data availability and state serialization remain bounded by L1 gas limits regardless of prover speed; optimistic rollups retain superior economics in the short horizon.", ["https://ethereum.org/en/developers/docs/scaling/optimistic-rollups/"], 3),
        ]
        for submitter, text, urls, rnd in args_case_3:
            time.sleep(1)
            try:
                tx_b = retry_call(lambda: client.write_contract(
                    address=arena_addr,
                    function_name="admin_add_argument",
                    args=["3", submitter, text, urls, rnd],
                    account=account,
                ))
                retry_call(lambda: client.wait_for_transaction_receipt(tx_b, status=TransactionStatus.ACCEPTED, interval=2000, retries=30))
            except Exception:
                pass
        print("    Added arguments for Arena 3.")

    # 4. Seed APPEALED Arena (Low-confidence AI consensus < 60%)
    cnt_res = retry_call(lambda: client.read_contract(address=arena_addr, function_name="get_arena_count"))
    if int(cnt_res) < 4:
        print("\n[+] Seeding Arena 4 (APPEALED: Low Confidence auto-escalation)...")
        tx4 = retry_call(lambda: client.write_contract(
            address=arena_addr,
            function_name="admin_seed_arena",
            args=[
                "AGI models will autonomously achieve self-directed recursive improvement before 2029.",
                ["https://en.wikipedia.org/wiki/Artificial_general_intelligence"],
                p1,
                p2,
                1500000000000000000,  # 1.5 GEN
                "APPEALED",
                "DRAW",
                "Low confidence (52%). The jury was split on recursive self-improvement definitions. Auto-escalated for appellate scrutiny.",
                52
            ],
            account=account,
        ))
        retry_call(lambda: client.wait_for_transaction_receipt(tx4, status=TransactionStatus.ACCEPTED, interval=3000, retries=30))
        print(f"    Arena 4 created (tx: {tx4})")

        args_case_4 = [
            (p1, "Frontier models are already writing their own training synthetic data and optimizing codebases.", ["https://en.wikipedia.org/wiki/Synthetic_data"], 1),
            (p2, "Diminishing marginal returns on compute and model collapse on self-generated data prevent runaway recursive loops.", ["https://en.wikipedia.org/wiki/Model_collapse"], 1),
        ]
        for submitter, text, urls, rnd in args_case_4:
            time.sleep(1)
            try:
                tx_c = retry_call(lambda: client.write_contract(
                    address=arena_addr,
                    function_name="admin_add_argument",
                    args=["4", submitter, text, urls, rnd],
                    account=account,
                ))
                retry_call(lambda: client.wait_for_transaction_receipt(tx_c, status=TransactionStatus.ACCEPTED, interval=2000, retries=30))
            except Exception:
                pass
        print("    Added arguments for Arena 4.")

        # Also trigger auto-appeal in AppealCourt for Arena 4
        try:
            print("    Triggering auto-appeal in AppealCourt for Arena 4...")
            tx_app = retry_call(lambda: client.write_contract(
                address=appeal_addr,
                function_name="file_auto_appeal",
                args=["4"],
                account=account,
            ))
            retry_call(lambda: client.wait_for_transaction_receipt(tx_app, status=TransactionStatus.ACCEPTED, interval=3000, retries=30))
            print(f"    Appeal recorded in AppealCourt (tx: {tx_app})")
        except Exception as e:
            print(f"    Note on auto-appeal: {e}")

    final_cnt = retry_call(lambda: client.read_contract(address=arena_addr, function_name="get_arena_count"))
    print("\n==================================================")
    print("SEEDING COMPLETE!")
    print(f"Total arenas live on studionet: {final_cnt}")
    print("==================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
