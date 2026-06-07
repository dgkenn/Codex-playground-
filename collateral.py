"""ROADMAP #1: mint/merge collateral primitive (Polygon CTF / neg-risk adapter).

Mint/merge is NOT a CLOB order -- it's an on-chain ConditionalTokens call, so it needs web3 +
the user's key + MATIC gas and can only run on the user's infra (never in this sandbox; no key
here). This module is split into:
  * DECISION LOGIC (pure, testable): when/how-much to split vs merge given inventory + a target
    quoting buffer. `plan()` below.
  * ON-CHAIN EXECUTION (guarded, live-only): `MintMerge.split/merge` via web3; no-ops + prints
    in dry-run. Addresses are Polygon mainnet.

Why it matters (mintmerge.py): it makes posted-collateral a function of NET DELTA (~$cap), not
of cumulative gross turnover -- the capacity unlock, with no model risk (exact $1 conservation).

split:  $X USDC  -> X Up + X Down   (source inventory to quote both sides)
merge:  X Up + X Down -> $X USDC    (reclaim collateral from matched pairs)
"""
from __future__ import annotations

import os

# Polygon mainnet
USDC = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"               # ConditionalTokens
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"  # for negRisk markets
# minimal ABI fragments
CTF_ABI = [
    {"name": "splitPosition", "type": "function", "inputs": [
        {"name": "collateralToken", "type": "address"}, {"name": "parentCollectionId", "type": "bytes32"},
        {"name": "conditionId", "type": "bytes32"}, {"name": "partition", "type": "uint256[]"},
        {"name": "amount", "type": "uint256"}], "outputs": []},
    {"name": "mergePositions", "type": "function", "inputs": [
        {"name": "collateralToken", "type": "address"}, {"name": "parentCollectionId", "type": "bytes32"},
        {"name": "conditionId", "type": "bytes32"}, {"name": "partition", "type": "uint256[]"},
        {"name": "amount", "type": "uint256"}], "outputs": []},
]
NEG_RISK_ABI = [
    {"name": "splitPosition", "type": "function",
     "inputs": [{"name": "conditionId", "type": "bytes32"}, {"name": "amount", "type": "uint256"}], "outputs": []},
    {"name": "mergePositions", "type": "function",
     "inputs": [{"name": "conditionId", "type": "bytes32"}, {"name": "amount", "type": "uint256"}], "outputs": []},
]
ZERO32 = "0x" + "00" * 32


def plan(up_held, dn_held, buffer_sets):
    """Pure decision logic. Keep ~buffer_sets of BOTH tokens on hand to quote from; merge the
    matched excess back to collateral. Returns ('merge', n) | ('split', n) | ('hold', 0).
      * matched excess = min(up_held, dn_held) - buffer  -> MERGE (reclaim collateral)
      * either side below buffer -> SPLIT enough to refill the short side
    """
    matched = min(up_held, dn_held)
    if matched > buffer_sets:
        return ("merge", matched - buffer_sets)
    short = buffer_sets - min(up_held, dn_held)
    if short > 0:
        return ("split", short)
    return ("hold", 0.0)


class MintMerge:
    """On-chain executor. live=False -> prints intent, touches nothing."""

    def __init__(self, live, neg_risk=False):
        self.live = live; self.neg_risk = neg_risk; self._w3 = None; self._c = None

    def _contract(self):
        if self._c is not None:
            return self._c
        from web3 import Web3
        rpc = os.environ.get("POLYGON_RPC", "https://polygon-rpc.com")
        self._w3 = Web3(Web3.HTTPProvider(rpc))
        addr = NEG_RISK_ADAPTER if self.neg_risk else CTF
        abi = NEG_RISK_ABI if self.neg_risk else CTF_ABI
        self._c = self._w3.eth.contract(address=self._w3.to_checksum_address(addr), abi=abi)
        return self._c

    def _send(self, fn):
        pk = os.environ["PRIVATE_KEY"]; acct = self._w3.eth.account.from_key(pk)
        tx = fn.build_transaction({"from": acct.address,
                                   "nonce": self._w3.eth.get_transaction_count(acct.address)})
        signed = acct.sign_transaction(tx)
        h = self._w3.eth.send_raw_transaction(signed.raw_transaction)
        return self._w3.eth.wait_for_transaction_receipt(h, timeout=120)

    def split(self, condition_id, sets):
        """Mint `sets` complete sets ($sets USDC -> sets Up + sets Down)."""
        amt = int(round(sets * 1_000_000))                       # USDC 6 decimals
        if not self.live:
            print(f"  [DRY split] {sets:.2f} sets on {condition_id[:10]} "
                  f"({'negRisk' if self.neg_risk else 'CTF'})"); return None
        c = self._contract()
        fn = (c.functions.splitPosition(condition_id, amt) if self.neg_risk
              else c.functions.splitPosition(USDC, ZERO32, condition_id, [1, 2], amt))
        return self._send(fn)

    def merge(self, condition_id, sets):
        """Merge `sets` matched Up+Down pairs back to $sets USDC."""
        amt = int(round(sets * 1_000_000))
        if not self.live:
            print(f"  [DRY merge] {sets:.2f} sets on {condition_id[:10]} "
                  f"({'negRisk' if self.neg_risk else 'CTF'})"); return None
        c = self._contract()
        fn = (c.functions.mergePositions(condition_id, amt) if self.neg_risk
              else c.functions.mergePositions(USDC, ZERO32, condition_id, [1, 2], amt))
        return self._send(fn)


if __name__ == "__main__":  # tiny self-check of the decision logic
    assert plan(10, 8, 2) == ("merge", 6)      # matched 8, keep 2, merge 6
    assert plan(1, 0, 2) == ("split", 2)       # short side empty, refill to 2
    assert plan(3, 3, 3) == ("hold", 0.0)      # exactly buffered
    print("collateral.plan() self-check OK")
