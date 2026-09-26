"""Thin web3 wrapper: artifacts, contract calls, transactions, Anvil controls."""
from __future__ import annotations

import json
from pathlib import Path

from eth_account import Account
from web3 import Web3

TEXT_ABI = [{
    "type": "function", "name": "text", "stateMutability": "view",
    "inputs": [{"name": "node", "type": "bytes32"}, {"name": "key", "type": "string"}],
    "outputs": [{"name": "", "type": "string"}],
}]
# ENSIP-10 read. The ENSv2 permissioned resolver has no bare text() getter,
# every read goes through resolve(name, data) and the node comes from the name.
RESOLVE_ABI = [{
    "type": "function", "name": "resolve", "stateMutability": "view",
    "inputs": [{"name": "name", "type": "bytes"}, {"name": "data", "type": "bytes"}],
    "outputs": [{"name": "", "type": "bytes"}],
}]
UNIVERSAL_RESOLVER_ABI = [{
    "type": "function", "name": "resolve", "stateMutability": "view",
    "inputs": [{"name": "name", "type": "bytes"}, {"name": "data", "type": "bytes"}],
    "outputs": [{"name": "result", "type": "bytes"}, {"name": "resolver", "type": "address"}],
}, {
    "type": "function", "name": "findResolver", "stateMutability": "view",
    "inputs": [{"name": "name", "type": "bytes"}],
    "outputs": [{"name": "resolver", "type": "address"}, {"name": "node", "type": "bytes32"}, {"name": "offset", "type": "uint256"}],
}]


class Chain:
    def __init__(self, rpc_url: str, artifacts: Path):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 90}))
        self.artifacts = Path(artifacts)
        self.chain_id = self.w3.eth.chain_id

    # ---------------------------------------------------------------- artifacts
    def _artifact(self, name: str) -> dict:
        return json.loads((self.artifacts / f"{name}.sol" / f"{name}.json").read_text())

    def abi(self, name: str) -> list:
        return self._artifact(name)["abi"]

    def contract(self, name: str, address: str):
        return self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=self.abi(name))

    # ------------------------------------------------------------------- reads
    def block_number(self) -> int:
        return self.w3.eth.block_number

    def block(self, ident) -> dict:
        b = self.w3.eth.get_block(ident)
        return {
            "number": int(b["number"]),
            "hash": Web3.to_hex(b["hash"]),
            "state_root": Web3.to_hex(b["stateRoot"]),
            "timestamp": int(b["timestamp"]),
        }

    def _text_calldata(self, node: bytes, key: str) -> bytes:
        c = self.w3.eth.contract(abi=TEXT_ABI)
        return bytes.fromhex(c.encode_abi("text", args=[node, key])[2:])

    def text_at(self, resolver: str, dns_name: bytes, node: bytes, key: str, block_identifier) -> str:
        """Read a text record the way ENS clients do, resolve(name, text(node, key)),
        at a given block. Falls back to the bare text(node, key) getter for
        resolvers that predate ENSIP-10."""
        addr = Web3.to_checksum_address(resolver)
        try:
            rc = self.w3.eth.contract(address=addr, abi=RESOLVE_ABI)
            out = rc.functions.resolve(dns_name, self._text_calldata(node, key)).call(block_identifier=block_identifier)
            return self.w3.codec.decode(["string"], out)[0]
        except Exception:
            tc = self.w3.eth.contract(address=addr, abi=TEXT_ABI)
            return tc.functions.text(node, key).call(block_identifier=block_identifier)

    def text_via_universal(self, universal_resolver: str, dns_name: bytes, node: bytes, key: str,
                           block_identifier="latest") -> tuple[str, str]:
        """Resolve through UniversalResolverV2, which finds the name's resolver first.
        Returns (value, resolver)."""
        ur = self.w3.eth.contract(address=Web3.to_checksum_address(universal_resolver), abi=UNIVERSAL_RESOLVER_ABI)
        out, resolver = ur.functions.resolve(dns_name, self._text_calldata(node, key)).call(block_identifier=block_identifier)
        return self.w3.codec.decode(["string"], out)[0], resolver

    # ------------------------------------------------------------------ writes
    def send(self, fn, key_hex: str, value: int = 0):
        acct = Account.from_key(key_hex)
        tx = fn.build_transaction({
            "from": acct.address,
            "nonce": self.w3.eth.get_transaction_count(acct.address),
            "chainId": self.chain_id,
            "value": value,
        })
        # the estimate is taken one block before mining; a heartbeat that crosses an epoch boundary in between
        # writes a new value where the estimate saw the old one and runs out of gas, so keep a margin
        tx["gas"] = int(tx["gas"] * 1.25) + 60_000
        signed = acct.sign_transaction(tx)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        rcpt = self.w3.eth.wait_for_transaction_receipt(h, timeout=180)
        if rcpt["status"] != 1:
            raise RuntimeError(f"tx reverted: {Web3.to_hex(h)}")
        return rcpt

    def deploy(self, name: str, key_hex: str, *args) -> str:
        art = self._artifact(name)
        C = self.w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"]["object"])
        rcpt = self.send(C.constructor(*args), key_hex)
        return rcpt["contractAddress"]

    # ------------------------------------------------------------------- anvil
    def rpc(self, method: str, params: list):
        return self.w3.provider.make_request(method, params)

    def mine(self, blocks: int):
        self.rpc("anvil_mine", [hex(blocks)])

    def increase_time(self, seconds: int):
        self.rpc("evm_increaseTime", [seconds])
        self.rpc("anvil_mine", ["0x1"])

    def set_balance(self, address: str, wei: int):
        self.rpc("anvil_setBalance", [Web3.to_checksum_address(address), hex(wei)])

    def is_anvil(self) -> bool:
        try:
            return "anvil" in self.w3.client_version.lower()
        except Exception:
            return False
