# TruthArena Architecture & Design Specification

## System Overview

TruthArena is an autonomous 1v1 dispute adjudication protocol on GenLayer. It allows two parties with polarized convictions to stake native GEN on opposite sides of an empirical claim, submit multi-round structured arguments with URL citations, and have an AI jury of diverse decentralized validators fetch and evaluate the evidence on-chain.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             TRUTHARENA PROTOCOL                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Debater (PRO) ───[create_arena / stake]───┐                               │
│                                             ▼                               │
│   Debater (CON) ───[join_side / stake]────> Arena (State: LOCKED)           │
│                                             │                               │
│   Both debaters submit 3 rounds of arguments│                               │
│   with evidence URLs                        ▼                               │
│                                       Arena._judge()                        │
│                                             │                               │
│                ┌────────────────────────────┴────────────────────────────┐  │
│                ▼                                                         ▼  │
│        gl.nondet.web.render                                      gl.nondet.exec_prompt
│        (Reads raw text from                                      (Multi-criteria jury
│         evidence URLs directly)                                   evaluation)       │
│                │                                                         │  │
│                └────────────────────────────┬────────────────────────────┘  │
│                                             ▼                               │
│                                    gl.vm.run_nondet                         │
│                           (Validator Consensus on VERDICT)                  │
│                                             │                               │
│               ┌─────────────────────────────┴─────────────────────────────┐ │
│               ▼ (Confidence >= 60%)                                       ▼ (Confidence < 60%)
│       Arena._settle_stakes()                                      Auto-Escalate
│       - 95% payout to winner                                      State: APPEALED
│       - 5% protocol reserve                                               │
│       - Calls Reputation.record_result                                    ▼
│                                                                   AppealCourt.file_appeal
│                                                                   - High-scrutiny appellate
│                                                                   - Cross-check URL analysis
│                                                                   - Overturn or Uphold
│                                                                           │
│                                                                           ▼
│                                                              Calls Reputation.record_result
└─────────────────────────────────────────────────────────────────────────────┘
```

## Contract Responsibilities

### 1. `Arena` (`contracts/arena.py`)
- **Authority**: Primary debate orchestrator and escrow vault.
- **State Machine**:
  - `OPEN`: Arena created by one debater, awaiting opponent.
  - `LOCKED`: Both debaters locked, turn-based argument phase (rounds 1-3).
  - `JUDGING`: Round 3 complete, non-deterministic consensus in progress.
  - `SETTLED`: Jury reached consensus; funds distributed (or auto-escalated).
  - `APPEALED`: Escalated to appellate review.
  - `FINAL`: Closed and archived.

### 2. `AppealCourt` (`contracts/appeal_court.py`)
- **Authority**: High-scrutiny appellate chamber.
- **Trigger**: Defeated party appeals with 2x stake deposit or auto-escalation on low confidence (< 60%).
- **Verification**: Evaluates original arguments against newly supplied cross-check URLs using strict appellate standards (`UPHOLD` vs `OVERTURN`).

### 3. `Reputation` (`contracts/reputation.py`)
- **Authority**: Verifiable record keeper for debaters across all arenas and appeals.
- **Metrics**: Wins, losses, draws, win rate percentage.
- **Tiers**: `Novice` (< 5), `Rookie` (5-19), `Seasoned` (20+), `Master` (50+ with > 60% win rate).

## Consensus Integrity Guarantees

In strict accordance with GenLayer builder guidelines:
1. **Semantic Equivalence**: The validator function compares the semantic `verdict` (`PRO_WINS`, `CON_WINS`, `DRAW`), ignoring stylistic differences in the generated rationale.
2. **Deterministic State Transition**: Storage writes and payout transfers occur only after consensus is finalized.
3. **Storage Correctness**: Fully typed GenVM collections (`TreeMap`, `DynArray`, `bigint`, sized integers) ensure zero runtime serialization failures.
