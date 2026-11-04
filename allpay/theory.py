"""Random-turn reference values, with a checked Bellman residual certificate."""
from dataclasses import dataclass
from functools import lru_cache
import math
import numpy as np
from .graph import Graph


def probability(mechanism: str, ratio: float, kind="mixed") -> float:
    """Max's RT bias. Pure is Max's sure guarantee, not a pure saddle point."""
    if mechanism not in ("richman", "poorman") or kind not in ("pure", "mixed"):
        raise ValueError("Unknown mechanism or strategy class")
    if not math.isfinite(ratio) or not 0 < ratio < 1:
        raise ValueError("The theorem assumes both players have positive budgets: 0 < r < 1")
    if mechanism == "richman":
        return 0.5 if kind == "mixed" else 0.0
    if kind == "pure":
        return max(0.0, 1 - (1 - ratio) / ratio)
    return ratio / (2 * (1 - ratio)) if ratio <= 0.5 else 1 - (1 - ratio) / (2 * ratio)


@dataclass(frozen=True)
class Reference:
    value: float
    lower: float
    upper: float
    potentials: tuple[float, ...]
    strengths: tuple[float, ...]
    max_moves: tuple[int, ...]
    min_moves: tuple[int, ...]
    iterations: int


@lru_cache(maxsize=4096)
def solve(graph: Graph, p: float, tolerance=1e-10, max_iterations=200000) -> Reference:
    """Lazy relative value iteration; laziness removes periodic oscillation.

    T(h)[v] = w[v] + p max h[u] + (1-p) min h[u].
    min(T(h)-h) <= value <= max(T(h)-h). Stop only when this
    interval is narrow. Laziness preserves gain, potentials and optimal moves.
    No unverified convergence claim is made if the iteration limit is reached.
    """
    if not math.isfinite(p) or not 0 <= p <= 1 or tolerance <= 0:
        raise ValueError("Require p in [0,1] and positive tolerance")
    h = np.zeros(len(graph.weights))
    w = np.asarray(graph.weights)
    for iteration in range(1, max_iterations + 1):
        hi = np.array([max(h[u] for u in row) for row in graph.edges])
        lo = np.array([min(h[u] for u in row) for row in graph.edges])
        t = w + p * hi + (1 - p) * lo
        delta = t - h
        lower, upper = float(delta.min()), float(delta.max())
        if upper - lower <= tolerance:
            max_moves = tuple(max(row, key=lambda u: h[u]) for row in graph.edges)
            min_moves = tuple(min(row, key=lambda u: h[u]) for row in graph.edges)
            return Reference((lower + upper) / 2, lower, upper, tuple(map(float, h)),
                             tuple(map(float, p * (1 - p) * (hi - lo))),
                             max_moves, min_moves, iteration)
        h = (h + t) / 2
        h -= h[0]
    raise RuntimeError(f"RT solver did not converge for {graph.name}, p={p}; residual={upper-lower:g}")


def shift_inverse(epsilon: float) -> float:
    """Solve -log(1-alpha)/log(1+alpha) = 1+epsilon (paper's shift function)."""
    if not math.isfinite(epsilon) or not 1e-6 <= epsilon <= 2:
        raise ValueError("Use epsilon in [1e-6, 2] for numerically stable strategies")
    low, high = 0.0, 1 - 1e-15
    for _ in range(70):
        mid = (low + high) / 2
        if -math.log1p(-mid) / math.log1p(mid) < 1 + epsilon:
            low = mid
        else:
            high = mid
    return (low + high) / 2
