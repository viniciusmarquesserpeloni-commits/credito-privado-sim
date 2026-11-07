"""Preço, taxa, duration, convexidade e DV01 (metodologia 4.1 e 4.5) e retorno no horizonte (4.7).

Fluxos como sequência de (t, FC): t em anos (du/252 na convenção brasileira) e FC em qualquer
unidade (o PU sai na mesma unidade). Sem scipy (decisão da Fase 0): raiz por Brent em Python puro.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

Flows = Sequence[tuple[float, float]]


def price(flows: Flows, y: float) -> float:
    """PU = Σ FC_i / (1 + y)^t_i (metodologia 4.1)."""
    return sum(fc / (1.0 + y) ** t for t, fc in flows)


def macaulay_duration(flows: Flows, y: float) -> float:
    pu = price(flows, y)
    return sum(t * fc / (1.0 + y) ** t for t, fc in flows) / pu


def modified_duration(flows: Flows, y: float) -> float:
    return macaulay_duration(flows, y) / (1.0 + y)


def convexity(flows: Flows, y: float) -> float:
    """C = 1/(PU (1+y)²) Σ t(t+1) FC/(1+y)^t (metodologia 4.5)."""
    pu = price(flows, y)
    return sum(t * (t + 1.0) * fc / (1.0 + y) ** t for t, fc in flows) / (pu * (1.0 + y) ** 2)


def dv01(flows: Flows, y: float) -> float:
    """DV01 = D_mod × PU × 0,0001."""
    return modified_duration(flows, y) * price(flows, y) * 1e-4


def price_change_approx(dmod: float, conv: float, dy: float) -> float:
    """ΔPU/PU ≈ −D_mod Δy + ½ C Δy² (metodologia 4.5)."""
    return -dmod * dy + 0.5 * conv * dy * dy


# ----------------------------------------------------------------------------- raízes
def brent(f: Callable[[float], float], a: float, b: float, tol: float = 1e-12,
          maxiter: int = 200) -> float:
    """Método de Brent (bisseção + secante + interpolação quadrática inversa)."""
    fa, fb = f(a), f(b)
    if fa == 0:
        return a
    if fb == 0:
        return b
    if fa * fb > 0:
        raise ValueError("a raiz não está no intervalo")
    if abs(fa) < abs(fb):
        a, b, fa, fb = b, a, fb, fa
    c, fc, mflag, d = a, fa, True, 0.0
    for _ in range(maxiter):
        if fa != fc and fb != fc:
            s = (a * fb * fc / ((fa - fb) * (fa - fc)) + b * fa * fc / ((fb - fa) * (fb - fc))
                 + c * fa * fb / ((fc - fa) * (fc - fb)))
        else:
            s = b - fb * (b - a) / (fb - fa)
        cond = (
            not ((3 * a + b) / 4 < s < b or b < s < (3 * a + b) / 4)
            or (mflag and abs(s - b) >= abs(b - c) / 2)
            or (not mflag and abs(s - b) >= abs(c - d) / 2)
            or (mflag and abs(b - c) < tol)
            or (not mflag and abs(c - d) < tol)
        )
        if cond:
            s = (a + b) / 2
            mflag = True
        else:
            mflag = False
        fs = f(s)
        d, c, fc = c, b, fb
        if fa * fs < 0:
            b, fb = s, fs
        else:
            a, fa = s, fs
        if abs(fa) < abs(fb):
            a, b, fa, fb = b, a, fb, fa
        if fb == 0 or abs(b - a) < tol:
            return b
    return b


def yield_from_price(flows: Flows, pu: float, lo: float = -0.5, hi: float = 5.0) -> float:
    """Taxa y tal que price(flows, y) = pu."""
    if not flows:
        raise ValueError("sem fluxos")
    return brent(lambda y: price(flows, y) - pu, lo, hi)


# ----------------------------------------------------------------------------- horizonte
def expected_return_approx(
    carry: float,
    *,
    dmod: float = 0.0,
    rolldown_dy: float = 0.0,
    dr: float = 0.0,
    spread_duration: float = 0.0,
    ds: float = 0.0,
    conv: float = 0.0,
    dy: float = 0.0,
    expected_loss: float = 0.0,
    costs: float = 0.0,
) -> float:
    """Decomposição do retorno no horizonte h (metodologia 4.7):

    E[R_h] ≈ carrego + D_mod·[y(T) − y(T−h)] − D_mod·Δr − D_s·Δs + ½·C·Δy² − PD×LGD − custos

    `carry` já é o carrego no horizonte (ex.: y·h, ou (1+CDI)(1+s) − 1 para CDI+ em 12 meses).
    Δr e Δs vêm de cenários, não de previsão pontual."""
    return (carry + dmod * rolldown_dy - dmod * dr - spread_duration * ds
            + 0.5 * conv * dy * dy - expected_loss - costs)


def annual_flows(coupon: float, years: int, face: float = 100.0) -> list[tuple[float, float]]:
    """Fluxo de um título com cupom anual e principal no vencimento (útil para testes)."""
    if years < 1 or not math.isfinite(coupon):
        raise ValueError("prazo/cupom inválidos")
    return [(float(t), face * coupon + (face if t == years else 0.0)) for t in range(1, years + 1)]
