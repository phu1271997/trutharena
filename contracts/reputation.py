# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *

import json


def _addr_str(addr: Address) -> str:
    try:
        return addr.as_hex
    except Exception:
        return str(addr)


class Reputation(gl.Contract):
    admin: Address
    authorized_callers: TreeMap[str, bool]
    wins: TreeMap[str, u256]
    losses: TreeMap[str, u256]
    draws: TreeMap[str, u256]

    def __init__(self):
        self.admin = gl.message.sender_address

    @gl.public.write
    def set_authorized(self, caller: Address, allowed: bool) -> None:
        if gl.message.sender_address != self.admin:
            raise gl.vm.UserError("Only admin can authorize callers")
        self.authorized_callers[_addr_str(caller)] = allowed

    @gl.public.write
    def record_result(self, wallet: str, result: str) -> None:
        sender_str = _addr_str(gl.message.sender_address)
        is_auth = self.authorized_callers.get(sender_str, False)
        if not is_auth and gl.message.sender_address != self.admin:
            raise gl.vm.UserError("Unauthorized caller")

        w = wallet.lower()
        if result == "WIN":
            prev = int(self.wins.get(w, u256(0)))
            self.wins[w] = u256(prev + 1)
        elif result == "LOSE":
            prev = int(self.losses.get(w, u256(0)))
            self.losses[w] = u256(prev + 1)
        elif result == "DRAW":
            prev = int(self.draws.get(w, u256(0)))
            self.draws[w] = u256(prev + 1)
        else:
            raise gl.vm.UserError("Invalid result type")

    @gl.public.view
    def get_reputation(self, wallet: str) -> str:
        w = wallet.lower()
        w_cnt = int(self.wins.get(w, u256(0)))
        l_cnt = int(self.losses.get(w, u256(0)))
        d_cnt = int(self.draws.get(w, u256(0)))
        total = w_cnt + l_cnt + d_cnt
        win_rate = (w_cnt * 100 // total) if total > 0 else 0

        # Tier badges per spec: Novice < 5, Rookie 5-19, Seasoned 20+, Master 50+ with win rate > 60%
        if total >= 50 and win_rate >= 60:
            tier = "Master"
        elif total >= 20:
            tier = "Seasoned"
        elif total >= 5:
            tier = "Rookie"
        else:
            tier = "Novice"

        data = {
            "wallet": wallet,
            "wins": w_cnt,
            "losses": l_cnt,
            "draws": d_cnt,
            "total_matches": total,
            "win_rate": win_rate,
            "tier": tier,
        }
        return json.dumps(data)
