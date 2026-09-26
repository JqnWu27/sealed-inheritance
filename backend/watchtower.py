"""Watchtower: anyone can run this. It has no permission others lack.

Polls the backend for the live window, and when the four opening conditions
hold on the finalized chain it opens the envelope and records the disclosure.

    ~/eth-tokyo/venv/bin/python backend/watchtower.py [--api http://127.0.0.1:8000] [--every 5]
"""
from __future__ import annotations

import argparse
import time

import httpx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--every", type=float, default=5.0)
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    client = httpx.Client(base_url=a.api, timeout=120)
    print(f"watchtower watching {a.api} every {a.every}s")
    while True:
        try:
            rec = client.get("/records").json()
            disclosed = rec["records"].get("disclosure") or ""
            disclosed_window = int(disclosed.split("window=")[1].split(";")[0]) if "window=" in disclosed else None
            if disclosed_window is not None and disclosed_window == int(rec["window"]):
                print(f"[{time.strftime('%H:%M:%S')}] {rec['name']} window {rec['window']} already disclosed")
                if a.once:
                    return
                time.sleep(a.every)
                continue
            w = client.get("/witness").json()
            state = "OPENABLE" if w.get("ok") else "sealed"
            details = "; ".join(f"{c['name']} {'ok' if c['ok'] else 'no'}" for c in w.get("checks", []))
            print(f"[{time.strftime('%H:%M:%S')}] {rec['name']} window {w.get('window')} epoch {rec['epoch']} finalized {rec['finalized_epoch']} -> {state} ({details})")
            if w.get("ok"):
                out = client.post("/decrypt").json()
                print(f"[{time.strftime('%H:%M:%S')}] decrypt -> {out['status']}")
                for line in out.get("trace", []):
                    print("    " + line)
                if a.once:
                    return
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] error {e}")
        if a.once:
            return
        time.sleep(a.every)


if __name__ == "__main__":
    main()
