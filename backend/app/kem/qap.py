"""Witness KEM for the silence relation as a quadratic arithmetic program.

Follows the structure of the QAP witness KEM of Chang, Wu, Liu, Hsu, Tso and
Mambo, ICISC 2025 (LNCS 16487), a Groth16-shaped construction over BN128,
specialised to one fixed relation:

    E - h - N = d,   d = sum_i 2^i b_i,   b_i in {0, 1},  i = 0..7

Variables (m = 12): [1, N | E, h, d, b0..b7]. Public: 1 and N (l = 1).
Constraints (n = 10): balance, eight bit checks, range.

Setup samples (tau, alpha, beta, delta) once, publishes the CRS below and
discards the secrets. The CRS is cached in backend/.qap-crs.json.

Encap(statement): r <- F. Publishes
    U_i = r*[u_i(tau)]_1,  V_i = r*[v_i(tau)]_2                        all i
    C_i = r*[(beta u_i + alpha v_i)(tau)/delta]_1 + r^2*[w_i(tau)/delta]_1   i > l
    H_k = r^2*[tau^k t(tau)/delta]_1                                    k < n-1
and derives the key from
    S = e([alpha]_1,[beta]_2) * e(r*U_pub, [beta]_2) * e([alpha]_1, r*V_pub) * e(r^2*W_pub, G2)
where U_pub = sum_{i<=l} a_i u_i etc. are the public-input combinations.

Decap(statement, ct, witness): with the full assignment a and quotient h,
    A = [alpha]_1 + sum a_i U_i,   B = [beta]_2 + sum a_i V_i,
    C = sum_{i>l} a_i C_i + sum_k h_k H_k,
    S' = e(A, B) / e(C, [delta]_2)
which equals S exactly when U_a V_a - W_a = h t, that is when the assignment
satisfies the QAP. Otherwise the derived key differs and the outer layer's
authenticated decryption fails.

No party holds a key or a trapdoor. This adapter covers the arithmetic of the
condition; binding the values E and h to Ethereum's finalized state is done by
the relation checker.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path

import cbor2
from py_ecc.optimized_bn128 import (G1, G2, Z1, Z2, add, curve_order, multiply, neg, normalize,
                                    pairing)
from py_ecc.optimized_bn128 import FQ, FQ2

from .base import WitnessKEM

P = curve_order  # scalar field of BN128
NBITS = 8
CRS_PATH = Path(__file__).resolve().parents[2] / ".qap-crs.json"

# ----------------------------------------------------------------- field ops


def finv(x: int) -> int:
    return pow(x % P, P - 2, P)


def poly_mul(a: list[int], b: list[int]) -> list[int]:
    out = [0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        if x == 0:
            continue
        for j, y in enumerate(b):
            out[i + j] = (out[i + j] + x * y) % P
    return out


def poly_add(a: list[int], b: list[int]) -> list[int]:
    n = max(len(a), len(b))
    return [((a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0)) % P for i in range(n)]


def poly_scale(a: list[int], s: int) -> list[int]:
    return [(x * s) % P for x in a]


def poly_eval(a: list[int], x: int) -> int:
    acc = 0
    for c in reversed(a):
        acc = (acc * x + c) % P
    return acc


def poly_divmod(num: list[int], den: list[int]) -> tuple[list[int], list[int]]:
    num = list(num)
    q = [0] * max(1, len(num) - len(den) + 1)
    inv_lead = finv(den[-1])
    for i in range(len(num) - len(den), -1, -1):
        coef = (num[i + len(den) - 1] * inv_lead) % P
        q[i] = coef
        if coef:
            for j, d in enumerate(den):
                num[i + j] = (num[i + j] - coef * d) % P
    rem = num[: len(den) - 1]
    while rem and rem[-1] == 0:
        rem.pop()
    return q, rem


def lagrange(points: list[int], values: list[int]) -> list[int]:
    """Coefficients of the polynomial through (points[j], values[j])."""
    n = len(points)
    result = [0] * n
    for j in range(n):
        if values[j] == 0:
            continue
        num = [1]
        den = 1
        for k in range(n):
            if k == j:
                continue
            num = poly_mul(num, [(-points[k]) % P, 1])
            den = (den * (points[j] - points[k])) % P
        result = poly_add(result, poly_scale(num, values[j] * finv(den) % P))
    return result


# ------------------------------------------------------------- the toy QAP

class SilenceQAP:
    """R1CS and QAP for E - h - N = d with an 8-bit range check on d."""

    def __init__(self):
        # variable indices
        self.ONE, self.N, self.E, self.H, self.D = 0, 1, 2, 3, 4
        self.B0 = 5
        self.m = self.B0 + NBITS  # 13 wires including the constant
        self.l = 1                 # public wires: 0 (constant one) and 1 (N)
        rows = []                  # (a, b, c) each a dict var -> coeff
        rows.append(({self.E: 1, self.H: P - 1, self.N: P - 1, self.D: P - 1}, {self.ONE: 1}, {}))
        for i in range(NBITS):
            rows.append(({self.B0 + i: 1}, {self.B0 + i: 1}, {self.B0 + i: 1}))
        rows.append(({self.B0 + i: pow(2, i, P) for i in range(NBITS)}, {self.ONE: 1}, {self.D: 1}))
        self.rows = rows
        self.n = len(rows)
        self.points = [j + 1 for j in range(self.n)]
        self.u = [lagrange(self.points, [r[0].get(i, 0) for r in rows]) for i in range(self.m)]
        self.v = [lagrange(self.points, [r[1].get(i, 0) for r in rows]) for i in range(self.m)]
        self.w = [lagrange(self.points, [r[2].get(i, 0) for r in rows]) for i in range(self.m)]
        t = [1]
        for x in self.points:
            t = poly_mul(t, [(-x) % P, 1])
        self.t = t

    def assignment(self, n_window: int, epoch: int, heartbeat: int) -> list[int]:
        d = epoch - heartbeat - n_window
        d_field = d % P
        bits = [(d >> i) & 1 if d >= 0 else 0 for i in range(NBITS)]
        return [1, n_window % P, epoch % P, heartbeat % P, d_field] + bits

    def satisfied(self, a: list[int]) -> bool:
        for ra, rb, rc in self.rows:
            lhs = sum(a[i] * c for i, c in ra.items()) % P * (sum(a[i] * c for i, c in rb.items()) % P) % P
            rhs = sum(a[i] * c for i, c in rc.items()) % P
            if lhs != rhs:
                return False
        return True

    def quotient(self, a: list[int]) -> tuple[list[int], bool]:
        """h with U_a V_a - W_a = h t. Returns (h, exact)."""
        ua = [0]
        va = [0]
        wa = [0]
        for i in range(self.m):
            ua = poly_add(ua, poly_scale(self.u[i], a[i]))
            va = poly_add(va, poly_scale(self.v[i], a[i]))
            wa = poly_add(wa, poly_scale(self.w[i], a[i]))
        num = poly_add(poly_mul(ua, va), poly_scale(wa, P - 1))
        h, rem = poly_divmod(num, self.t)
        h = (h + [0] * (self.n - 1))[: self.n - 1]
        return h, len(rem) == 0


# -------------------------------------------------------------- CRS and KEM

def g1(s: int):
    return multiply(G1, s % P)


def g2(s: int):
    return multiply(G2, s % P)


INF = ["inf"]


def is_inf(pt) -> bool:
    z = pt[2]
    return int(z) == 0 if isinstance(z, FQ) else all(int(c) == 0 for c in z.coeffs)


def ser_g1(pt) -> list[str]:
    if is_inf(pt):
        return INF
    x, y = normalize(pt)
    return [hex(int(x)), hex(int(y))]


def ser_g2(pt) -> list[str]:
    if is_inf(pt):
        return INF
    x, y = normalize(pt)
    return [hex(int(x.coeffs[0])), hex(int(x.coeffs[1])), hex(int(y.coeffs[0])), hex(int(y.coeffs[1]))]


def de_g1(v: list[str]):
    if v == INF:
        return Z1
    return (FQ(int(v[0], 16)), FQ(int(v[1], 16)), FQ(1))


def de_g2(v: list[str]):
    if v == INF:
        return Z2
    return (FQ2([int(v[0], 16), int(v[1], 16)]), FQ2([int(v[2], 16), int(v[3], 16)]), FQ2([1, 0]))


def gt_bytes(el) -> bytes:
    return b"".join(int(c).to_bytes(32, "big") for c in el.coeffs)


def msm1(points, scalars):
    acc = Z1
    for pt, s in zip(points, scalars):
        if s % P:
            acc = add(acc, multiply(pt, s % P))
    return acc


def msm2(points, scalars):
    acc = Z2
    for pt, s in zip(points, scalars):
        if s % P:
            acc = add(acc, multiply(pt, s % P))
    return acc


class QapKEM(WitnessKEM):
    name = "qap"

    def __init__(self, crs_path: Path = CRS_PATH):
        self.qap = SilenceQAP()
        self._trace: list[str] = []
        self.crs = self._load_or_setup(crs_path)

    # ------------------------------------------------------------- setup
    def _load_or_setup(self, path: Path) -> dict:
        if path.exists():
            return json.loads(path.read_text())
        q = self.qap
        tau, alpha, beta, delta = (secrets.randbelow(P - 1) + 1 for _ in range(4))
        dinv = finv(delta)
        crs = {
            "A0": ser_g1(g1(alpha)), "B0": ser_g2(g2(beta)), "D": ser_g2(g2(delta)),
            "U": [ser_g1(g1(poly_eval(q.u[i], tau))) for i in range(q.m)],
            "V": [ser_g2(g2(poly_eval(q.v[i], tau))) for i in range(q.m)],
            "K": [ser_g1(g1((beta * poly_eval(q.u[i], tau) + alpha * poly_eval(q.v[i], tau)) * dinv)) for i in range(q.m)],
            "Wd": [ser_g1(g1(poly_eval(q.w[i], tau) * dinv)) for i in range(q.m)],
            "Wpub": [ser_g1(g1(poly_eval(q.w[i], tau))) for i in range(q.l + 1)],
            "T": [ser_g1(g1(pow(tau, k, P) * poly_eval(q.t, tau) * dinv)) for k in range(q.n - 1)],
        }
        # tau, alpha, beta, delta go out of scope here and are never written anywhere
        path.write_text(json.dumps(crs))
        return crs

    # ------------------------------------------------------------- helpers
    def _public(self, statement: dict) -> list[int]:
        return [1, int(statement["predicate"]["window"]) % P]

    @staticmethod
    def _fp(key: bytes) -> str:
        return hashlib.sha256(key).hexdigest()[:16]

    # -------------------------------------------------------------- encap
    def encap(self, statement: dict) -> tuple[bytes, bytes]:
        q, crs = self.qap, self.crs
        a_pub = self._public(statement)
        r = secrets.randbelow(P - 1) + 1
        r2 = (r * r) % P
        U = [multiply(de_g1(crs["U"][i]), r) for i in range(q.m)]
        V = [multiply(de_g2(crs["V"][i]), r) for i in range(q.m)]
        C = [add(multiply(de_g1(crs["K"][i]), r), multiply(de_g1(crs["Wd"][i]), r2)) for i in range(q.l + 1, q.m)]
        H = [multiply(de_g1(crs["T"][k]), r2) for k in range(q.n - 1)]

        A0, B0 = de_g1(crs["A0"]), de_g2(crs["B0"])
        upub = msm1([U[i] for i in range(q.l + 1)], a_pub)
        vpub = msm2([V[i] for i in range(q.l + 1)], a_pub)
        wpub = multiply(msm1([de_g1(crs["Wpub"][i]) for i in range(q.l + 1)], a_pub), r2)
        S = pairing(B0, A0) * pairing(B0, upub) * pairing(vpub, A0) * pairing(G2, wpub)
        key = hashlib.sha256(gt_bytes(S)).digest()

        ct = cbor2.dumps({
            "U": [ser_g1(p) for p in U], "V": [ser_g2(p) for p in V],
            "C": [ser_g1(p) for p in C], "H": [ser_g1(p) for p in H],
        })
        self._trace = [
            f"qap encap: public input N = {a_pub[1]}, randomness r sampled, no witness used",
            f"qap encap: published {len(U)} U, {len(V)} V, {len(C)} C, {len(H)} H group elements, {len(ct)} bytes",
            f"qap encap: S = e(A0,B0)·e(rU_pub,B0)·e(A0,rV_pub)·e(r²W_pub,G2), key fingerprint {self._fp(key)}",
        ]
        return ct, key

    # -------------------------------------------------------------- decap
    def decap(self, statement: dict, kem_ct: bytes, witness: dict) -> bytes | None:
        q, crs = self.qap, self.crs
        n_window = int(statement["predicate"]["window"])
        epoch = int(witness["epoch"])
        hb = max(int(witness["heartbeat_epoch"]), int(statement["predicate"].get("from_epoch", 0)))
        a = q.assignment(n_window, epoch, hb)
        ok = q.satisfied(a)
        h, exact = q.quotient(a)
        self._trace = [
            f"qap decap: assignment N={n_window} E={epoch} h={hb} d={epoch - hb - n_window} bits={a[q.B0:]}",
            f"qap decap: QAP {'satisfied' if ok and exact else 'NOT satisfied, remainder nonzero'} over {q.n} constraints",
        ]
        ct = cbor2.loads(kem_ct)
        U = [de_g1(v) for v in ct["U"]]
        V = [de_g2(v) for v in ct["V"]]
        C = [de_g1(v) for v in ct["C"]]
        Hp = [de_g1(v) for v in ct["H"]]
        A = add(de_g1(crs["A0"]), msm1(U, a))
        B = add(de_g2(crs["B0"]), msm2(V, a))
        Cc = add(msm1(C, a[q.l + 1:]), msm1(Hp, h))
        S = pairing(B, A) * pairing(de_g2(crs["D"]), neg(Cc))
        key = hashlib.sha256(gt_bytes(S)).digest()
        self._trace.append(f"qap decap: S' = e(A,B)/e(C,D), key fingerprint {self._fp(key)}")
        if not (ok and exact):
            self._trace.append("qap decap: key does not match the encapsulated one, outer layer will not open")
        return key
