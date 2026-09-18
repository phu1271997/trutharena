# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *

from dataclasses import dataclass
import json


def _run_nondet(leader_fn, validator_fn):
    fn = (
        getattr(gl.vm, "run_nondet_default", None)
        or getattr(gl.vm, "run_nondet", None)
        or gl.vm.run_nondet_unsafe
    )
    return fn(leader_fn, validator_fn)


def _addr_str(addr: Address) -> str:
    try:
        return addr.as_hex
    except Exception:
        return str(addr)


@allow_storage
@dataclass
class AppealCase:
    appeal_id: str
    arena_id: str
    appellant: str
    target_winner: str
    original_verdict: str
    claim: str
    stake: bigint
    extra_urls: DynArray[str]
    appellant_rationale: str
    state: str  # OPEN | RULED
    verdict: str  # UPHOLD | OVERTURN
    reason: str
    confidence: u8


class AppealCourt(gl.Contract):
    admin: Address
    arena_contract: Address
    reputation_contract: Address
    appeals: TreeMap[str, AppealCase]
    next_appeal_id: bigint

    def __init__(self):
        self.admin = gl.message.sender_address
        self.next_appeal_id = bigint(1)

    @gl.public.write
    def set_dependencies(self, arena: Address, reputation: Address) -> None:
        if gl.message.sender_address != self.admin:
            raise gl.vm.UserError("Only admin can set dependencies")
        self.arena_contract = arena
        self.reputation_contract = reputation

    @gl.public.write.payable
    def file_appeal(
        self,
        arena_id: str,
        claim: str,
        original_verdict: str,
        target_winner: str,
        appellant_rationale: str,
        extra_urls: DynArray[str],
    ) -> str:
        stake_val = bigint(gl.message.value)
        if stake_val <= bigint(0):
            raise gl.vm.UserError("Stake must be greater than zero")
        if len(extra_urls) > 3:
            raise gl.vm.UserError("Maximum 3 extra cross-check URLs allowed")

        appeal_id_int = int(self.next_appeal_id)
        self.next_appeal_id = bigint(appeal_id_int + 1)
        appeal_id_str = str(appeal_id_int)
        sender_str = _addr_str(gl.message.sender_address)

        record = AppealCase(
            appeal_id=appeal_id_str,
            arena_id=arena_id,
            appellant=sender_str,
            target_winner=target_winner,
            original_verdict=original_verdict,
            claim=claim,
            stake=stake_val,
            extra_urls=extra_urls,
            appellant_rationale=appellant_rationale,
            state="OPEN",
            verdict="",
            reason="",
            confidence=u8(0),
        )
        self.appeals[appeal_id_str] = record

        # Adjudicate immediately on-chain
        self._judge_appeal(appeal_id_str)
        return appeal_id_str

    def _judge_appeal(self, appeal_id: str) -> None:
        appeal = self.appeals[appeal_id]
        urls_snapshot = list(appeal.extra_urls)
        claim_snapshot = appeal.claim
        orig_verdict_snapshot = appeal.original_verdict
        rationale_snapshot = appeal.appellant_rationale

        def leader_fn():
            fetched = []
            for u in urls_snapshot:
                try:
                    body = gl.nondet.web.render(u, mode="text")
                    fetched.append({"url": u, "content": body[:4000]})
                except Exception as e:
                    fetched.append({"url": u, "error": str(e)[:200]})

            prompt = f"""You are the Decentralized Appellate Court for TruthArena.
A debate outcome is being appealed with newly submitted cross-check evidence.

CLAIM UNDER DEBATE:
{claim_snapshot}

ORIGINAL VERDICT APPEALED:
{orig_verdict_snapshot}

APPELLANT'S ARGUMENT TO OVERTURN:
{rationale_snapshot}

NEW CROSS-CHECK EVIDENCE FETCHED ON-CHAIN:
{json.dumps(fetched, indent=2)[:10000]}

Apply high-scrutiny appellate standards:
1. Does the new evidence demonstrate that the original verdict was clearly erroneous?
2. Did the original round rely on false factual assertions contradicted by the new evidence?
3. If new evidence clearly disproves the prior conclusion, rule OVERTURN. Otherwise, rule UPHOLD.

RESPOND WITH ONLY VALID JSON:
{{
  "verdict": "UPHOLD" | "OVERTURN",
  "confidence": 0-100,
  "reason": "Detailed legal-style appellate rationale citing cross-check evidence"
}}
"""
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            return raw

        def validator_fn(leader_res) -> bool:
            """Validator compares semantic VERDICT (UPHOLD vs OVERTURN)."""
            if not isinstance(leader_res, gl.vm.Return):
                return False
            leader = leader_res.calldata
            if not isinstance(leader, dict) or "verdict" not in leader:
                return False
            mine = leader_fn()
            if not isinstance(mine, dict) or "verdict" not in mine:
                return False
            return mine["verdict"] == leader["verdict"]

        result = _run_nondet(leader_fn, validator_fn)
        verdict = str(result.get("verdict", "UPHOLD")).upper()
        if verdict not in ["UPHOLD", "OVERTURN"]:
            verdict = "UPHOLD"

        reason = str(result.get("reason", ""))
        confidence = int(result.get("confidence", 80))

        appeal.verdict = verdict
        appeal.reason = reason
        appeal.confidence = u8(min(100, max(0, confidence)))
        appeal.state = "RULED"

        # Payout settlement
        self._settle_appeal_payout(appeal)

    def _settle_appeal_payout(self, appeal: AppealCase) -> None:
        total_stake = appeal.stake
        fee = total_stake * bigint(5) // bigint(100)
        payout = total_stake - fee

        if appeal.verdict == "OVERTURN":
            # Appellant prevailed: refund stake + payout
            try:
                gl.get_contract_at(Address(appeal.appellant)).emit_transfer(
                    value=u256(int(payout))
                )
            except Exception:
                pass
            # Update reputation
            try:
                rep = gl.get_contract_at(self.reputation_contract)
                rep.record_result(args=[appeal.appellant, "WIN"])
                if appeal.target_winner:
                    rep.record_result(args=[appeal.target_winner, "LOSE"])
            except Exception:
                pass
        else:
            # UPHOLD: Original winner receives payout
            if appeal.target_winner:
                try:
                    gl.get_contract_at(Address(appeal.target_winner)).emit_transfer(
                        value=u256(int(payout))
                    )
                except Exception:
                    pass
            try:
                rep = gl.get_contract_at(self.reputation_contract)
                rep.record_result(args=[appeal.appellant, "LOSE"])
            except Exception:
                pass

    @gl.public.view
    def get_appeal(self, appeal_id: str) -> str:
        if appeal_id not in self.appeals:
            raise gl.vm.UserError("Appeal not found")
        a = self.appeals[appeal_id]
        data = {
            "appeal_id": a.appeal_id,
            "arena_id": a.arena_id,
            "appellant": a.appellant,
            "target_winner": a.target_winner,
            "original_verdict": a.original_verdict,
            "claim": a.claim,
            "stake": str(a.stake),
            "extra_urls": list(a.extra_urls),
            "appellant_rationale": a.appellant_rationale,
            "state": a.state,
            "verdict": a.verdict,
            "reason": a.reason,
            "confidence": int(a.confidence),
        }
        return json.dumps(data)

    @gl.public.view
    def get_appeal_count(self) -> u256:
        return u256(int(self.next_appeal_id) - 1)
