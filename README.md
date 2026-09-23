# TruthArena

**Decentralized 1v1 debate arena where opposing debaters stake GEN on real-world claims, submit multi-round arguments with web citations, and an on-chain AI jury consensus reads the evidence directly to settle the match.**

- **Live dApp (Vercel):** [https://trutharena-gamma.vercel.app](https://trutharena-gamma.vercel.app) *(or your Vercel deployment URL)*
- **Network:** GenLayer Studionet (`chainId: 61999`, RPC: `https://studio.genlayer.com/api`)
- **Block Explorer:** [https://genlayer-explorer.vercel.app](https://genlayer-explorer.vercel.app)
- **Portal Builders Track:** [GenLayer Portal](https://portal.genlayer.foundation/#/builders/contributions)

---

## 1. Problem Statement

On the modern internet, debates on empirical claims—ranging from scientific disputes and technical roadmaps to breaking news—degenerate into unresolvable echo chambers. Centralized platforms (Twitter Community Notes, editorial fact-checkers) suffer from opacity, geographic bias, and slow editorial turnaround. Crucially, disputants have no mechanism to put skin in the game with verifiable, decentralized arbitration that actually inspects the evidence they cite.

**TruthArena solves this** by creating a structured 1v1 arena where:
1. Opposing debaters stake native GEN tokens on opposite sides of a claim (`PRO` vs `CON`).
2. Participants submit arguments across structured debate rounds, citing live URL evidence.
3. A decentralized jury of independent LLM validators fetches and reads the cited web sources on-chain.
4. The protocol evaluates logical rigor, evidence relevance, and counter-argument rebuttals to reach consensus on the winning side and distribute the escrow pool.

---

## 2. Why TruthArena Dies Without GenLayer

TruthArena is fundamentally impossible on traditional blockchains (like Ethereum or Solana) or off-chain AI oracle stacks:

- **Direct On-Chain Web Access**: Traditional smart contracts cannot access the web without centralized oracles. Oracles only relay static numeric values, but debate adjudication requires reading full-text articles and papers via `gl.nondet.web.render` directly in contract execution.
- **Subjective Natural-Language Reasoning**: Determining which debate argument is more persuasive and logically sound requires natural-language comprehension (`gl.nondet.exec_prompt`), which cannot be hard-coded into deterministic EVM bytecode.
- **Decentralized Multi-Model Consensus**: If a single off-chain AI judged the outcome, the losing side would simply claim the LLM was biased. GenLayer resolves this by having independent validators running diverse foundation models converge on consensus.
- **Semantic Equivalence Verification**: In `gl.vm.run_nondet`, validators verify the core semantic verdict (`PRO_WINS` vs `CON_WINS`), ignoring cosmetic wording differences in rationales to achieve mathematically sound decentralized finality.

---

## 3. System Architecture

TruthArena employs a modular 3-contract architecture deployed on GenLayer studionet:

```
                  ┌──────────────────────────────────────────────┐
                  │                 TruthArena                   │
                  └──────────────────────┬───────────────────────┘
                                         │
                 ┌───────────────────────┼───────────────────────┐
                 ▼                       ▼                       ▼
          ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
          │    Arena    │◄───────►│ AppealCourt │────────►│ Reputation  │
          └─────────────┘         └─────────────┘         └─────────────┘
          - 1v1 escrow            - Appellate review      - On-chain stats
          - Turn submission       - Cross-check URLs      - Win/loss/draw
          - AI Jury nondet        - Overturn/Uphold       - Tier badges
          - 95% winner payout
```

1. **`Arena` (`contracts/arena.py`)**: Central protocol contract managing match registration, stake escrow, turn enforcement, non-deterministic web rendering + LLM consensus, and payout distribution (with a 5% protocol fee).
2. **`AppealCourt` (`contracts/appeal_court.py`)**: Second-instance judicial contract. Defeated debaters can appeal with 2x stake deposit, or matches with low jury confidence (< 60%) auto-escalate here for strict appellate scrutiny with additional cross-check URLs.
3. **`Reputation` (`contracts/reputation.py`)**: Verifiable on-chain profile tracker that records matches, wins, losses, draws, win rates, and unlocks tier badges (`Novice`, `Rookie`, `Seasoned`, `Master`).

---

## 4. Deployed Contract Addresses on Studionet

| Contract | Address | Explorer Link |
|---|---|---|
| **Arena** | `0x2cB09dAb020f6Cb8E0cda650c42403063567664f` | [View on Explorer](https://genlayer-explorer.vercel.app/address/0x2cB09dAb020f6Cb8E0cda650c42403063567664f) |
| **AppealCourt** | `0x815E849a40423EeCa23e15dBF6Ace4DE90d701Db` | [View on Explorer](https://genlayer-explorer.vercel.app/address/0x815E849a40423EeCa23e15dBF6Ace4DE90d701Db) |
| **Reputation** | `0xbb9735ba2F2A6F3f88f716085b04B4C1D6f0bA40` | [View on Explorer](https://genlayer-explorer.vercel.app/address/0xbb9735ba2F2A6F3f88f716085b04B4C1D6f0bA40) |

---

## 4.1 Value-Bearing & Appellate Workflow (Judge Feedback Implementation)

1. **Fail-Safe Native Settlement**:
   - An arena reaches state `FINAL` only after native GEN payout transfers succeed.
   - If a transfer fails or needs retry, the arena remains in `SETTLED` state, allowing callers to execute `claim_payout(arena_id)`.
2. **Authenticated Appellate Workflow**:
   - `AppealCourt.file_appeal` pulls verified match state directly from `Arena` on-chain—preventing caller-supplied facts.
   - Only the authenticated defeated debater (`con_wallet` if `PRO_WINS`, `pro_wallet` if `CON_WINS`) can appeal with 2x stake deposit.
   - Low jury confidence (< 60%) automatically escalates via `file_auto_appeal`, locking escrow until appellate review.
   - Appellate rulings (`UPHOLD` / `OVERTURN`) update the original arena verdict, reason, and confidence, and trigger escrow settlement.
3. **Consensus Confidence Agreement**:
   - `validator_fn` in both `Arena` and `AppealCourt` enforces semantic verdict equality AND agreement on the confidence threshold (`>= 60` selecting settlement vs appeal) plus numerical proximity (`<= 15`).
4. **Interactive Appellate UI**:
   - Frontend includes an "Appellate Court" navigation tab with live auto-escalated and defeated-party appeals, in-context 2x stake appeal modal, and payout claim button.

---

## 5. Step-by-Step Deployment & Local Run

### Prerequisites
- Python 3.10+
- Node.js 18+ & npm
- MetaMask with GenLayer Studio Network added

### Step 1: Deploy Contracts to Studionet
```bash
# 1. Export deployer key from central keystore
source ~/.genlayer/env.sh

# 2. Deploy contracts in order (Reputation -> AppealCourt -> Arena)
python3 scripts/deploy_studionet.py

# 3. Seed demo data (creates 3 sample arenas on studionet)
python3 scripts/seed_demo_data.py
```

### Step 2: Run Frontend Locally
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` to interact with the live contract.

---

## 6. Demo Video
- **Walkthrough Video:** [YouTube / Loom Demo Placeholder](https://youtube.com)

---

## 7. Automated Tests
Run integration tests using `gltest`:
```bash
gltest tests/test_appeal_flow.py --network studionet
```
All contract interfaces and storage variables adhere strictly to GenVM specifications.
