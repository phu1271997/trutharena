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


@gl.contract_interface
class IArena:
    class View:
        def get_arena(self, arena_id: str) -> str: ...

    class Write:
        def mark_appealed(self, arena_id: str) -> None: ...
        def settle_from_appeal(
            self,
            arena_id: str,
            appellate_verdict: str,
            appellate_reason: str,
            appellate_confidence: int,
            appellant: str,
        ) -> None: ...


@gl.contract_interface
class IReputation:
    class View:
        def get_reputation(self, debater: str) -> str: ...

    class Write:
        def record_result(self, debater: str, outcome: str) -> None: ...


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
    is_auto_escalation: bool


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
        appellant_rationale: str,
        extra_urls: DynArray[str],
    ) -> str:
        """
        Defeated-party appeal. Fetches authenticated match facts directly from the
        Arena contract rather than relying on caller-supplied facts.
        """
        if not self.arena_contract:
            raise gl.vm.UserError("Arena contract not configured")
        if len(extra_urls) > 3:
            raise gl.vm.UserError("Maximum 3 extra cross-check URLs allowed")
        if len(appellant_rationale.strip()) == 0:
            raise gl.vm.UserError("Appellant rationale cannot be empty")

        # Query authenticated match state from Arena contract via typed view
        try:
            arena = IArena(self.arena_contract)
            raw_arena = arena.view().get_arena(arena_id)
            arena_data = json.loads(raw_arena)
        except Exception as e:
            raise gl.vm.UserError(f"Could not load authenticated arena state: {e}")

        orig_verdict = arena_data.get("verdict", "")
        if orig_verdict not in ["PRO_WINS", "CON_WINS"]:
            raise gl.vm.UserError("Only settled arenas with a definitive verdict can be appealed")

        stake_per_side = int(arena_data.get("stake_per_side", 0))
        required_stake = stake_per_side * 2
        stake_val = bigint(gl.message.value)
        if stake_val < bigint(required_stake):
            raise gl.vm.UserError(f"Appeal stake must equal double the match stake ({required_stake})")

        sender_str = _addr_str(gl.message.sender_address)
        pro_wallet = arena_data.get("pro_wallet", "")
        con_wallet = arena_data.get("con_wallet", "")

        # Authenticate that caller is indeed the defeated party
        # target_winner stores the original match winner
        if orig_verdict == "PRO_WINS":
            if sender_str.lower() != con_wallet.lower():
                raise gl.vm.UserError("Only the defeated debater can appeal")
            original_winner = pro_wallet
        else:
            if sender_str.lower() != pro_wallet.lower():
                raise gl.vm.UserError("Only the defeated debater can appeal")
            original_winner = con_wallet

        # Mark arena state as APPEALED in Arena contract
        try:
            arena.emit(on="accepted").mark_appealed(arena_id)
        except Exception:
            pass

        appeal_id_int = int(self.next_appeal_id)
        self.next_appeal_id = bigint(appeal_id_int + 1)
        appeal_id_str = str(appeal_id_int)

        record = AppealCase(
            appeal_id=appeal_id_str,
            arena_id=arena_id,
            appellant=sender_str,
            target_winner=original_winner,
            original_verdict=orig_verdict,
            claim=arena_data.get("claim", ""),
            stake=stake_val,
            extra_urls=extra_urls,
            appellant_rationale=appellant_rationale.strip(),
            state="OPEN",
            verdict="",
            reason="",
            confidence=u8(0),
            is_auto_escalation=False,
        )
        self.appeals[appeal_id_str] = record

        # Adjudicate immediately on-chain with appellate LLM scrutiny
        self._judge_appeal(appeal_id_str)
        return appeal_id_str

    @gl.public.write
    def file_auto_appeal(self, arena_id: str) -> str:
        """
        Automatic escalation hook: called when Arena jury confidence < 60%.
        Authenticated through Arena contract address.
        """
        sender_str = _addr_str(gl.message.sender_address)
        is_arena = sender_str.lower() == _addr_str(self.arena_contract).lower()
        if not is_arena and gl.message.sender_address != self.admin:
            raise gl.vm.UserError("Only Arena contract can initiate auto-appeal")

        try:
            arena = IArena(self.arena_contract)
            raw_arena = arena.view().get_arena(arena_id)
            arena_data = json.loads(raw_arena)
        except Exception as e:
            raise gl.vm.UserError(f"Could not load arena data: {e}")

        appeal_id_int = int(self.next_appeal_id)
        self.next_appeal_id = bigint(appeal_id_int + 1)
        appeal_id_str = str(appeal_id_int)

        context_urls = DynArray[str](list(arena_data.get("context_urls", [])))

        record = AppealCase(
            appeal_id=appeal_id_str,
            arena_id=arena_id,
            appellant=arena_data.get("creator", ""),
            target_winner="",
            original_verdict=arena_data.get("verdict", "DRAW"),
            claim=arena_data.get("claim", ""),
            stake=bigint(0),
            extra_urls=context_urls,
            appellant_rationale="Automatic appellate review triggered due to low jury confidence (< 60%). High-scrutiny evaluation required.",
            state="OPEN",
            verdict="",
            reason="",
            confidence=u8(0),
            is_auto_escalation=True,
        )
        self.appeals[appeal_id_str] = record

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
                    res = gl.nondet.web.get(u)
                    body = (
                        res.body.decode("utf-8", errors="replace")
                        if hasattr(res, "body")
                        else str(res)
                    )
                    fetched.append({"url": u, "content": body[:3000]})
                except Exception:
                    try:
                        body = gl.nondet.web.render(u, mode="text")
                        fetched.append({"url": u, "content": body[:3000]})
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
            """
            Validator compares semantic VERDICT (UPHOLD vs OVERTURN)
            AND confidence agreement.
            """
            if not isinstance(leader_res, gl.vm.Return):
                return False
            leader = leader_res.calldata
            if not isinstance(leader, dict) or "verdict" not in leader or "confidence" not in leader:
                return False
            mine = leader_fn()
            if not isinstance(mine, dict) or "verdict" not in mine or "confidence" not in mine:
                return False

            if mine["verdict"] != leader["verdict"]:
                return False

            if abs(int(mine["confidence"]) - int(leader["confidence"])) > 15:
                return False

            return True

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

        # Update original arena case and settle escrow outcome
        self._settle_appeal_payout(appeal)

    def _settle_appeal_payout(self, appeal: AppealCase) -> None:
        """
        Updates the original arena case and escrow outcome,
        and distributes appeal stakes if manual appeal.
        """
        # 1. Update the original Arena case and trigger escrow settlement
        try:
            if self.arena_contract:
                arena = IArena(self.arena_contract)
                arena.emit(on="finalized").settle_from_appeal(
                    appeal.arena_id,
                    appeal.verdict,
                    appeal.reason,
                    int(appeal.confidence),
                    appeal.appellant,
                )
        except Exception:
            pass

        # 2. Settle manual appeal stake (if applicable)
        if appeal.stake > bigint(0):
            total_stake = appeal.stake
            fee = total_stake * bigint(5) // bigint(100)
            payout = total_stake - fee

            if appeal.verdict == "OVERTURN":
                # Appellant prevailed: return appeal stake + reward
                try:
                    gl.get_contract_at(Address(appeal.appellant)).emit_transfer(
                        value=u256(int(payout))
                    )
                except Exception:
                    pass
                try:
                    if self.reputation_contract:
                        rep = IReputation(self.reputation_contract)
                        rep.emit(on="finalized").record_result(appeal.appellant, "WIN")
                        if appeal.target_winner:
                            rep.emit(on="finalized").record_result(appeal.target_winner, "LOSE")
                except Exception:
                    pass
            else:
                # UPHOLD: Original winner receives appeal stake payout
                if appeal.target_winner:
                    try:
                        gl.get_contract_at(Address(appeal.target_winner)).emit_transfer(
                            value=u256(int(payout))
                        )
                    except Exception:
                        pass
                try:
                    if self.reputation_contract:
                        rep = IReputation(self.reputation_contract)
                        rep.emit(on="finalized").record_result(appeal.appellant, "LOSE")
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
            "is_auto_escalation": a.is_auto_escalation,
        }
        return json.dumps(data)

    @gl.public.view
    def get_appeal_count(self) -> u256:
        return u256(int(self.next_appeal_id) - 1)

    @gl.public.view
    def list_appeals(self, offset: int, limit: int) -> str:
        total = int(self.next_appeal_id) - 1
        results = []
        start = max(1, offset + 1)
        end = min(total + 1, start + limit)

        for i in range(start, end):
            key = str(i)
            if key in self.appeals:
                a = self.appeals[key]
                results.append(
                    {
                        "appeal_id": a.appeal_id,
                        "arena_id": a.arena_id,
                        "appellant": a.appellant,
                        "target_winner": a.target_winner,
                        "original_verdict": a.original_verdict,
                        "claim": a.claim,
                        "stake": str(a.stake),
                        "state": a.state,
                        "verdict": a.verdict,
                        "confidence": int(a.confidence),
                        "is_auto_escalation": a.is_auto_escalation,
                    }
                )
        return json.dumps(results)
