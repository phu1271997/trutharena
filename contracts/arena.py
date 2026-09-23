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


def _now_epoch() -> bigint:
    try:
        return bigint(int(gl.vm.get_timestamp().timestamp()))
    except Exception:
        return bigint(0)


@gl.contract_interface
class IAppealCourt:
    class View:
        def get_appeal(self, appeal_id: str) -> str: ...
        def get_appeal_count(self) -> u256: ...

    class Write:
        def file_auto_appeal(self, arena_id: str) -> str: ...


@gl.contract_interface
class IReputation:
    class View:
        def get_reputation(self, debater: str) -> str: ...

    class Write:
        def record_result(self, debater: str, outcome: str) -> None: ...


@allow_storage
@dataclass
class Argument:
    submitter: str
    text: str
    evidence_urls: DynArray[str]
    round_number: u8
    submitted_at_epoch: bigint


@allow_storage
@dataclass
class ArenaCase:
    creator: str
    claim: str
    context_urls: DynArray[str]
    pro_wallet: str
    con_wallet: str
    stake_per_side: bigint
    state: str  # OPEN | LOCKED | JUDGING | SETTLED | APPEALED | FINAL
    current_round: u8  # 1..3
    verdict: str  # "" | "PRO_WINS" | "CON_WINS" | "DRAW"
    reason: str
    confidence: u8
    reputation_contract: str
    appeal_contract: str
    payout_done: bool


class Arena(gl.Contract):
    admin: Address
    reputation_contract: Address
    appeal_contract: Address
    arenas: TreeMap[str, ArenaCase]
    arguments: TreeMap[str, DynArray[Argument]]
    next_id: bigint

    def __init__(self):
        self.admin = gl.message.sender_address
        self.next_id = bigint(1)

    @gl.public.write
    def set_dependencies(self, rep_contract: Address, appeal_contract: Address) -> None:
        if gl.message.sender_address != self.admin:
            raise gl.vm.UserError("Only admin can set dependencies")
        self.reputation_contract = rep_contract
        self.appeal_contract = appeal_contract

    @gl.public.write.payable
    def create_arena(
        self,
        claim: str,
        context_urls: DynArray[str],
        stake_per_side: int,
        creator_side: str,
    ) -> str:
        if stake_per_side <= 0:
            raise gl.vm.UserError("Stake must be positive")
        if gl.message.value != u256(stake_per_side):
            raise gl.vm.UserError("Message value does not match stake amount")
        if not claim or len(claim.strip()) == 0:
            raise gl.vm.UserError("Claim cannot be empty")
        if len(claim) > 400:
            raise gl.vm.UserError("Claim exceeds 400 characters")
        if len(context_urls) > 3:
            raise gl.vm.UserError("Maximum 3 context URLs allowed")
        side_clean = creator_side.upper().strip()
        if side_clean not in ["PRO", "CON"]:
            raise gl.vm.UserError("Creator side must be PRO or CON")

        sender_str = _addr_str(gl.message.sender_address)
        arena_id_int = int(self.next_id)
        self.next_id = bigint(arena_id_int + 1)
        arena_id_str = str(arena_id_int)

        pro = sender_str if side_clean == "PRO" else ""
        con = sender_str if side_clean == "CON" else ""

        case = ArenaCase(
            creator=sender_str,
            claim=claim.strip(),
            context_urls=context_urls,
            pro_wallet=pro,
            con_wallet=con,
            stake_per_side=bigint(stake_per_side),
            state="OPEN",
            current_round=u8(1),
            verdict="",
            reason="",
            confidence=u8(0),
            reputation_contract=_addr_str(self.reputation_contract),
            appeal_contract=_addr_str(self.appeal_contract),
            payout_done=False,
        )
        self.arenas[arena_id_str] = case
        return arena_id_str

    @gl.public.write.payable
    def join_side(self, arena_id: str, side: str) -> None:
        if arena_id not in self.arenas:
            raise gl.vm.UserError("Arena not found")
        case = self.arenas[arena_id]
        if case.state != "OPEN":
            raise gl.vm.UserError("Arena is not open for joining")
        if gl.message.value != u256(int(case.stake_per_side)):
            raise gl.vm.UserError("Message value does not match stake_per_side")

        sender_str = _addr_str(gl.message.sender_address)
        side_clean = side.upper().strip()
        if side_clean not in ["PRO", "CON"]:
            raise gl.vm.UserError("Side must be PRO or CON")

        if side_clean == "PRO":
            if case.pro_wallet != "":
                raise gl.vm.UserError("PRO side is already taken")
            if case.con_wallet.lower() == sender_str.lower():
                raise gl.vm.UserError("Cannot join both sides")
            case.pro_wallet = sender_str
        else:
            if case.con_wallet != "":
                raise gl.vm.UserError("CON side is already taken")
            if case.pro_wallet.lower() == sender_str.lower():
                raise gl.vm.UserError("Cannot join both sides")
            case.con_wallet = sender_str

        # Lock once both sides are present
        if case.pro_wallet != "" and case.con_wallet != "":
            case.state = "LOCKED"
            case.current_round = u8(1)

    @gl.public.write
    def submit_argument(
        self, arena_id: str, text: str, evidence_urls: DynArray[str]
    ) -> None:
        if arena_id not in self.arenas:
            raise gl.vm.UserError("Arena not found")
        case = self.arenas[arena_id]
        if case.state != "LOCKED":
            raise gl.vm.UserError("Arena is not in debate state")
        if len(text.strip()) == 0:
            raise gl.vm.UserError("Argument text cannot be empty")
        if len(text) > 800:
            raise gl.vm.UserError("Argument exceeds 800 characters")
        if len(evidence_urls) > 3:
            raise gl.vm.UserError("Maximum 3 evidence URLs allowed")

        sender_str = _addr_str(gl.message.sender_address)
        is_pro = sender_str.lower() == case.pro_wallet.lower()
        is_con = sender_str.lower() == case.con_wallet.lower()
        if not is_pro and not is_con:
            raise gl.vm.UserError("Only active debaters can submit arguments")

        cur_round = int(case.current_round)

        if arena_id not in self.arguments:
            arg_list = []
        else:
            arg_list = list(self.arguments[arena_id])

        for existing in arg_list:
            if (
                int(existing.round_number) == cur_round
                and existing.submitter.lower() == sender_str.lower()
            ):
                raise gl.vm.UserError("Round already submitted by this debater")

        new_arg = Argument(
            submitter=sender_str,
            text=text.strip(),
            evidence_urls=evidence_urls,
            round_number=u8(cur_round),
            submitted_at_epoch=_now_epoch(),
        )
        arg_list.append(new_arg)
        self.arguments[arena_id] = DynArray[Argument](arg_list)

        pro_done = any(
            int(a.round_number) == cur_round
            and a.submitter.lower() == case.pro_wallet.lower()
            for a in arg_list
        )
        con_done = any(
            int(a.round_number) == cur_round
            and a.submitter.lower() == case.con_wallet.lower()
            for a in arg_list
        )

        if pro_done and con_done:
            if cur_round < 3:
                case.current_round = u8(cur_round + 1)
            else:
                case.state = "JUDGING"
                self._judge(arena_id)

    def _judge(self, arena_id: str) -> None:
        case = self.arenas[arena_id]
        args_snapshot = (
            list(self.arguments[arena_id]) if arena_id in self.arguments else []
        )
        ctx_snapshot = list(case.context_urls)
        claim_snapshot = case.claim
        pro_wallet = case.pro_wallet
        con_wallet = case.con_wallet

        def leader_fn():
            fetched = []
            for a in args_snapshot:
                for url in a.evidence_urls:
                    try:
                        res = gl.nondet.web.get(url)
                        body = (
                            res.body.decode("utf-8", errors="replace")
                            if hasattr(res, "body")
                            else str(res)
                        )
                        fetched.append(
                            {
                                "url": url,
                                "submitter": a.submitter,
                                "round": int(a.round_number),
                                "content": body[:3000],
                            }
                        )
                    except Exception:
                        try:
                            body = gl.nondet.web.render(url, mode="text")
                            fetched.append(
                                {
                                    "url": url,
                                    "submitter": a.submitter,
                                    "round": int(a.round_number),
                                    "content": body[:3000],
                                }
                            )
                        except Exception as e:
                            fetched.append({"url": url, "error": str(e)[:200]})

            for url in ctx_snapshot:
                try:
                    res = gl.nondet.web.get(url)
                    body = (
                        res.body.decode("utf-8", errors="replace")
                        if hasattr(res, "body")
                        else str(res)
                    )
                    fetched.append(
                        {
                            "url": url,
                            "submitter": "context",
                            "content": body[:3000],
                        }
                    )
                except Exception:
                    try:
                        body = gl.nondet.web.render(url, mode="text")
                        fetched.append(
                            {
                                "url": url,
                                "submitter": "context",
                                "content": body[:3000],
                            }
                        )
                    except Exception as e:
                        fetched.append({"url": url, "error": str(e)[:200]})

            pro_args = [
                a
                for a in args_snapshot
                if a.submitter.lower() == pro_wallet.lower()
            ]
            con_args = [
                a
                for a in args_snapshot
                if a.submitter.lower() == con_wallet.lower()
            ]

            prompt = f"""You are a decentralized AI jury judging a 1v1 debate on GenLayer.

CLAIM UNDER DEBATE:
{claim_snapshot}

PRO ARGUMENTS (arguing the claim is TRUE):
{json.dumps([{"round": int(a.round_number), "text": a.text} for a in pro_args], indent=2)}

CON ARGUMENTS (arguing the claim is FALSE):
{json.dumps([{"round": int(a.round_number), "text": a.text} for a in con_args], indent=2)}

EVIDENCE FETCHED ON-CHAIN FROM EVIDENCE URLS:
{json.dumps(fetched, indent=2)[:12000]}

Judge which side made the stronger case:
1. Does the URL evidence actually support what the submitter claimed it supports?
2. Which side addressed the other's counter-arguments better?
3. Are there logical fallacies or unsupported claims?
4. Did either side cite dead or irrelevant URLs?

RESPOND WITH ONLY VALID JSON:
{{
  "verdict": "PRO_WINS" | "CON_WINS" | "DRAW",
  "confidence": 0-100,
  "reason": "2-4 sentence rationale citing specific arguments and evidence"
}}
"""
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            return raw

        def validator_fn(leader_res) -> bool:
            """
            CRITICAL CONSENSUS RULE: Validator compares VERDICT (semantic meaning)
            AND confidence tier (selecting settlement vs appeal threshold at 60%).
            """
            if not isinstance(leader_res, gl.vm.Return):
                return False
            leader = leader_res.calldata
            if not isinstance(leader, dict) or "verdict" not in leader or "confidence" not in leader:
                return False
            mine = leader_fn()
            if not isinstance(mine, dict) or "verdict" not in mine or "confidence" not in mine:
                return False

            # 1. Semantic verdict must agree
            if mine["verdict"] != leader["verdict"]:
                return False

            # 2. Both must agree on the threshold selecting settlement vs appeal (confidence >= 60)
            mine_conf = int(mine["confidence"])
            leader_conf = int(leader["confidence"])
            mine_settles = mine_conf >= 60
            leader_settles = leader_conf >= 60
            if mine_settles != leader_settles:
                return False

            # 3. Numeric confidence scores must be in close agreement (tolerance <= 15)
            if abs(mine_conf - leader_conf) > 15:
                return False

            return True

        result = _run_nondet(leader_fn, validator_fn)
        verdict = str(result.get("verdict", "DRAW")).upper()
        if verdict not in ["PRO_WINS", "CON_WINS", "DRAW"]:
            verdict = "DRAW"

        reason = str(result.get("reason", ""))
        confidence = int(result.get("confidence", 70))

        # Low confidence (< 60%) auto-escalates to AppealCourt without distributing escrow
        if confidence < 60:
            case.state = "APPEALED"
            case.verdict = verdict
            case.reason = f"Low confidence ({confidence}%). Auto-escalated for appellate review. {reason}"
            case.confidence = u8(max(0, min(100, confidence)))
            case.payout_done = False

            if self.appeal_contract:
                try:
                    ac = IAppealCourt(self.appeal_contract)
                    ac.emit(on="accepted").file_auto_appeal(arena_id)
                except Exception:
                    pass
            return

        case.verdict = verdict
        case.reason = reason
        case.confidence = u8(max(0, min(100, confidence)))
        case.state = "SETTLED"
        case.payout_done = False

        # Settle stakes: arena reaches FINAL only if required native payouts succeed!
        self._settle_stakes(arena_id, verdict)

    def _settle_stakes(self, arena_id: str, verdict: str) -> bool:
        """
        Fail-safe settlement: transfers native GEN payouts.
        The arena reaches state 'FINAL' ONLY after the required payouts succeed.
        If any payout transfer fails, the arena remains in 'SETTLED' state so it can be retried.
        """
        case = self.arenas[arena_id]
        pool = case.stake_per_side * bigint(2)
        fee = pool * bigint(5) // bigint(100)
        payout = pool - fee

        payout_success = False

        if verdict == "PRO_WINS":
            winner = case.pro_wallet
            loser = case.con_wallet
            try:
                gl.get_contract_at(Address(winner)).emit_transfer(
                    value=u256(int(payout))
                )
                payout_success = True
            except Exception:
                payout_success = False

        elif verdict == "CON_WINS":
            winner = case.con_wallet
            loser = case.pro_wallet
            try:
                gl.get_contract_at(Address(winner)).emit_transfer(
                    value=u256(int(payout))
                )
                payout_success = True
            except Exception:
                payout_success = False

        else:  # DRAW
            winner = ""
            loser = ""
            half_payout = (case.stake_per_side * bigint(95)) // bigint(100)
            try:
                gl.get_contract_at(Address(case.pro_wallet)).emit_transfer(
                    value=u256(int(half_payout))
                )
                gl.get_contract_at(Address(case.con_wallet)).emit_transfer(
                    value=u256(int(half_payout))
                )
                payout_success = True
            except Exception:
                payout_success = False

        if payout_success:
            case.payout_done = True
            case.state = "FINAL"

            # Record reputation on final settlement
            try:
                if self.reputation_contract:
                    rep = IReputation(self.reputation_contract)
                    if winner and loser:
                        rep.emit(on="finalized").record_result(winner, "WIN")
                        rep.emit(on="finalized").record_result(loser, "LOSE")
                    else:
                        rep.emit(on="finalized").record_result(case.pro_wallet, "DRAW")
                        rep.emit(on="finalized").record_result(case.con_wallet, "DRAW")
            except Exception:
                pass
            return True
        else:
            # Payout did not succeed: remain in SETTLED, do not transition to FINAL
            case.payout_done = False
            case.state = "SETTLED"
            return False

    @gl.public.write
    def claim_payout(self, arena_id: str) -> None:
        """Retry / claim settlement payout for an arena in SETTLED state."""
        if arena_id not in self.arenas:
            raise gl.vm.UserError("Arena not found")
        case = self.arenas[arena_id]
        if case.state != "SETTLED":
            raise gl.vm.UserError("Arena is not in SETTLED state awaiting payout")
        if case.payout_done:
            raise gl.vm.UserError("Payout already completed")

        success = self._settle_stakes(arena_id, case.verdict)
        if not success:
            raise gl.vm.UserError("Payout transfer failed")

    @gl.public.write
    def mark_appealed(self, arena_id: str) -> None:
        """Hook called by AppealCourt to mark arena as APPEALED upon valid appeal."""
        sender_str = _addr_str(gl.message.sender_address)
        is_appeal = sender_str.lower() == _addr_str(self.appeal_contract).lower()
        if not is_appeal and gl.message.sender_address != self.admin:
            raise gl.vm.UserError("Only AppealCourt can mark arena as appealed")

        if arena_id not in self.arenas:
            raise gl.vm.UserError("Arena not found")
        case = self.arenas[arena_id]
        if case.state not in ["SETTLED", "FINAL", "LOCKED", "JUDGING"]:
            raise gl.vm.UserError("Cannot appeal arena in this state")

        case.state = "APPEALED"

    @gl.public.write
    def settle_from_appeal(
        self,
        arena_id: str,
        appellate_verdict: str,
        appellate_reason: str,
        appellate_confidence: int,
        appellant: str,
    ) -> None:
        """
        Appellate result hook: updates the original case verdict, reason, confidence,
        and triggers escrow payout settlement. Reaches FINAL only after payout succeeds.
        """
        sender_str = _addr_str(gl.message.sender_address)
        is_appeal = sender_str.lower() == _addr_str(self.appeal_contract).lower()
        if not is_appeal and gl.message.sender_address != self.admin:
            raise gl.vm.UserError("Only AppealCourt can settle appeal")

        if arena_id not in self.arenas:
            raise gl.vm.UserError("Arena not found")

        case = self.arenas[arena_id]
        if case.state not in ["APPEALED", "SETTLED"]:
            raise gl.vm.UserError("Arena is not in an appealed state")

        app_v = appellate_verdict.upper().strip()
        if app_v not in ["UPHOLD", "OVERTURN"]:
            raise gl.vm.UserError("Invalid appellate verdict")

        prior_verdict = case.verdict
        if app_v == "UPHOLD":
            final_verdict = prior_verdict
            case.reason = f"{case.reason} | [AppealCourt UPHOLD]: {appellate_reason}"
        else:
            if prior_verdict == "PRO_WINS":
                final_verdict = "CON_WINS"
            elif prior_verdict == "CON_WINS":
                final_verdict = "PRO_WINS"
            else:
                final_verdict = "PRO_WINS" if appellant.lower() == case.pro_wallet.lower() else "CON_WINS"

            case.verdict = final_verdict
            case.reason = f"[AppealCourt OVERTURN]: {appellate_reason}"

        case.confidence = u8(max(0, min(100, appellate_confidence)))
        case.state = "SETTLED"
        case.payout_done = False

        # Execute safe escrow payout to the upheld / overturned winner
        self._settle_stakes(arena_id, final_verdict)

    @gl.public.write.payable
    def request_appeal(self, arena_id: str) -> None:
        """Manual appeal requested on the Arena contract by the defeated debater."""
        if arena_id not in self.arenas:
            raise gl.vm.UserError("Arena not found")
        case = self.arenas[arena_id]
        if case.state not in ["SETTLED", "FINAL"]:
            raise gl.vm.UserError("Only settled arenas can be appealed")

        required_stake = case.stake_per_side * bigint(2)
        if bigint(gl.message.value) < required_stake:
            raise gl.vm.UserError("Appeal stake must equal double the match stake")

        sender_str = _addr_str(gl.message.sender_address)
        if case.verdict == "PRO_WINS" and sender_str.lower() != case.con_wallet.lower():
            raise gl.vm.UserError("Only the defeated debater can appeal")
        if case.verdict == "CON_WINS" and sender_str.lower() != case.pro_wallet.lower():
            raise gl.vm.UserError("Only the defeated debater can appeal")

        case.state = "APPEALED"

    @gl.public.write
    def admin_seed_arena(
        self,
        claim: str,
        context_urls: DynArray[str],
        pro_wallet: str,
        con_wallet: str,
        stake: int,
        state: str,
        verdict: str,
        reason: str,
        confidence: int,
    ) -> str:
        if gl.message.sender_address != self.admin:
            raise gl.vm.UserError("Only admin can seed demo arenas")

        arena_id_int = int(self.next_id)
        self.next_id = bigint(arena_id_int + 1)
        arena_id_str = str(arena_id_int)

        case = ArenaCase(
            creator=pro_wallet if pro_wallet else con_wallet,
            claim=claim,
            context_urls=context_urls,
            pro_wallet=pro_wallet,
            con_wallet=con_wallet,
            stake_per_side=bigint(stake),
            state=state,
            current_round=u8(3 if state in ["SETTLED", "FINAL", "APPEALED"] else 1),
            verdict=verdict,
            reason=reason,
            confidence=u8(confidence),
            reputation_contract=_addr_str(self.reputation_contract),
            appeal_contract=_addr_str(self.appeal_contract),
            payout_done=(state == "FINAL"),
        )
        self.arenas[arena_id_str] = case

        # Update reputation for settled seeded cases
        if verdict in ["PRO_WINS", "CON_WINS"] and self.reputation_contract and state == "FINAL":
            try:
                rep = IReputation(self.reputation_contract)
                w = pro_wallet if verdict == "PRO_WINS" else con_wallet
                l = con_wallet if verdict == "PRO_WINS" else pro_wallet
                rep.emit(on="finalized").record_result(w, "WIN")
                rep.emit(on="finalized").record_result(l, "LOSE")
            except Exception:
                pass

        return arena_id_str

    @gl.public.write
    def admin_add_argument(
        self,
        arena_id: str,
        submitter: str,
        text: str,
        evidence_urls: DynArray[str],
        round_number: int,
    ) -> None:
        if gl.message.sender_address != self.admin:
            raise gl.vm.UserError("Only admin can seed arguments")

        if arena_id not in self.arguments:
            arg_list = []
        else:
            arg_list = list(self.arguments[arena_id])

        arg_list.append(
            Argument(
                submitter=submitter,
                text=text,
                evidence_urls=evidence_urls,
                round_number=u8(round_number),
                submitted_at_epoch=_now_epoch(),
            )
        )
        self.arguments[arena_id] = DynArray[Argument](arg_list)

    @gl.public.view
    def get_arena(self, arena_id: str) -> str:
        if arena_id not in self.arenas:
            raise gl.vm.UserError("Arena not found")
        c = self.arenas[arena_id]
        args_data = []
        if arena_id in self.arguments:
            for a in self.arguments[arena_id]:
                args_data.append(
                    {
                        "submitter": a.submitter,
                        "text": a.text,
                        "evidence_urls": list(a.evidence_urls),
                        "round_number": int(a.round_number),
                        "submitted_at_epoch": int(a.submitted_at_epoch),
                    }
                )

        data = {
            "arena_id": arena_id,
            "creator": c.creator,
            "claim": c.claim,
            "context_urls": list(c.context_urls),
            "pro_wallet": c.pro_wallet,
            "con_wallet": c.con_wallet,
            "stake_per_side": str(c.stake_per_side),
            "state": c.state,
            "current_round": int(c.current_round),
            "verdict": c.verdict,
            "reason": c.reason,
            "confidence": int(c.confidence),
            "reputation_contract": c.reputation_contract,
            "appeal_contract": c.appeal_contract,
            "payout_done": c.payout_done,
            "arguments": args_data,
        }
        return json.dumps(data)

    @gl.public.view
    def get_arguments(self, arena_id: str) -> str:
        if arena_id not in self.arguments:
            return json.dumps([])
        res = []
        for a in self.arguments[arena_id]:
            res.append(
                {
                    "submitter": a.submitter,
                    "text": a.text,
                    "evidence_urls": list(a.evidence_urls),
                    "round_number": int(a.round_number),
                    "submitted_at_epoch": int(a.submitted_at_epoch),
                }
            )
        return json.dumps(res)

    @gl.public.view
    def get_arena_count(self) -> u256:
        return u256(int(self.next_id) - 1)

    @gl.public.view
    def list_arenas(self, state_filter: str, offset: int, limit: int) -> str:
        total = int(self.next_id) - 1
        results = []
        filter_clean = state_filter.upper().strip()

        start = max(1, offset + 1)
        end = min(total + 1, start + limit)

        for i in range(start, end):
            key = str(i)
            if key in self.arenas:
                c = self.arenas[key]
                if not filter_clean or filter_clean == "ALL" or c.state == filter_clean:
                    results.append(
                        {
                            "arena_id": key,
                            "creator": c.creator,
                            "claim": c.claim,
                            "pro_wallet": c.pro_wallet,
                            "con_wallet": c.con_wallet,
                            "stake_per_side": str(c.stake_per_side),
                            "state": c.state,
                            "current_round": int(c.current_round),
                            "verdict": c.verdict,
                            "confidence": int(c.confidence),
                            "payout_done": c.payout_done,
                        }
                    )
        return json.dumps(results)
