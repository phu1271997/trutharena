# TruthArena Smart Contracts Architecture

TruthArena uses a multi-contract architecture designed for decentralized, high-integrity adjudication on GenLayer studionet.

## 1. Contracts Overview

| Contract | File | Role & Authority |
|---|---|---|
| **Arena** | `arena.py` | Main debate protocol: creates 1v1 debate matches, locks GEN stakes, collects 3 rounds of arguments with URL citations, invokes decentralized AI jury consensus via `gl.vm.run_nondet`, and settles payouts (5% protocol fee). |
| **AppealCourt** | `appeal_court.py` | Appellate jurisdiction: allows defeated debaters or auto-escalated low-confidence matches (< 60%) to be reviewed under strict appellate standards with cross-check URLs. |
| **Reputation** | `reputation.py` | On-chain debater record keeper: tracks wins, losses, draws, win rates, and assigns merit tiers (`Novice`, `Rookie`, `Seasoned`, `Master`). Accessible only by authorized contracts. |

## 2. Cross-Contract Coordination Flow

```
User (Creator) ────> Arena.create_arena (stakes GEN)
                       │
User (Opponent) ───> Arena.join_side (matches stake, state = LOCKED)
                       │
Debaters ──────────> Arena.submit_argument (Rounds 1, 2, 3 + Evidence URLs)
                       │
                       ▼ (After Round 3)
                     Arena._judge()
                       │
                       ├─ gl.nondet.web.render (fetches all cited URLs directly on-chain)
                       ├─ gl.nondet.exec_prompt (LLM jury reviews logic & evidence)
                       └─ gl.vm.run_nondet (Consensus: validators compare VERDICT, ignoring text style)
                             │
            ┌────────────────┴────────────────┐
            ▼ (Confidence >= 60%)              ▼ (Confidence < 60%)
      Arena._settle_stakes()           Auto-escalate to AppealCourt
            │                                  │
            ├─ 95% payout to winner            └─ Strict appellate review with cross-check URLs
            └─ Calls Reputation.record_result      │
                                                   ▼
                                        Calls Reputation.record_result
```

## 3. Storage & Determinism Guarantees
- Strictly adheres to GenLayer GenVM storage rules: `TreeMap[str, T]`, `DynArray[T]`, `bigint`, `u256`, `u8`.
- No bare `int` or standard python `dict`/`list` in persistent storage.
- Non-deterministic blocks are isolated; validators verify semantic verdicts rather than brittle textual schema equality.
