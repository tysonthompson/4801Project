"""Finite prefixes of infinite games; payments and rewards follow the paper."""
from dataclasses import dataclass, asdict
from decimal import Decimal, localcontext
import math
import random
from .strategies import State


@dataclass
class Sample:
    rounds: int
    mean_payoff: float
    max_win_rate: float
    tie_rate: float
    max_budget_ratio: float
    log_total_budget: float
    vertex: int
    log_max_budget: float
    log_min_budget: float


@dataclass
class Result:
    samples: list[Sample]
    trace: list[dict]


def settle(budgets, bids, mechanism):
    """Both bids are paid, including on ties. No currency rounding or bid floor."""
    if mechanism not in ("richman", "poorman"):
        raise ValueError("Unknown mechanism")
    if any(not math.isfinite(b) or b < 0 for b in budgets):
        raise ValueError("Budgets must be finite and nonnegative")
    if any(not math.isfinite(bid) or not 0 <= bid <= budget for bid, budget in zip(bids, budgets)):
        raise ValueError(f"Illegal bid: {bids} with budgets {budgets}")
    left, right = budgets[0] - bids[0], budgets[1] - bids[1]
    if mechanism == "richman":
        left += bids[1]
        right += bids[0]
    return left, right


def simulate(graph, max_strategy, min_strategy, *, mechanism="richman", ratio=0.5,
             rounds=10000, seed=4801, start=0, checkpoints=(), trace_every=0, total_budget=1.0,
             precision=0):
    """precision=0 uses floats; >=30 uses Decimal money with a wide exponent range.

    Fresh strategy instances are required for each run, including a precision retry.
    Potentials and random samples remain doubles; Decimal protects monetary range.
    """
    if type(precision) is not int or precision != 0 and precision < 30:
        raise ValueError("Precision must be 0 (float) or at least 30 decimal digits")
    with localcontext() as context:
        if precision:
            context.prec = precision
            context.Emax, context.Emin = 999999999, -999999999
        return _simulate(graph, max_strategy, min_strategy, mechanism, ratio, rounds, seed, start,
                         checkpoints, trace_every, total_budget, precision)


def _log(value):
    if not value:
        return -math.inf
    return float(value.ln()) if isinstance(value, Decimal) else math.log(value)


def _simulate(graph, max_strategy, min_strategy, mechanism, ratio, rounds, seed, start,
              checkpoints, trace_every, total_budget, precision):
    if mechanism not in ("richman", "poorman") or not 0 < ratio < 1:
        raise ValueError("Require valid mechanism and 0 < ratio < 1")
    if type(rounds) is not int or rounds <= 0 or not 0 <= start < len(graph.weights):
        raise ValueError("Require a positive integer horizon and valid start vertex")
    if not math.isfinite(total_budget) or total_budget <= 0 or trace_every < 0:
        raise ValueError("Require positive finite total budget and nonnegative trace interval")
    points = set(checkpoints) | {rounds}
    if any(type(p) is not int or not 1 <= p <= rounds for p in points):
        raise ValueError("Checkpoints must be integer rounds within the horizon")
    # Independent random streams prevent either player consuming the other's draws.
    master = random.Random(seed)
    rngs = [random.Random(master.getrandbits(128)) for _ in range(2)]
    strategies = (max_strategy, min_strategy)
    budgets = (Decimal(str(ratio)), 1 - Decimal(str(ratio))) if precision else (ratio, 1 - ratio)
    if precision:
        for strategy in strategies:
            if hasattr(strategy, "virtual"):
                i = strategy.player
                strategy.virtual = budgets[i] - Decimal.from_float(strategy.W) * budgets[1 - i]
    vertex, energy, wins, ties = start, 0.0, 0, 0
    log_total = math.log(total_budget)
    samples, trace = [], []
    previous_bids = (0.0, 0.0)
    for turn in range(rounds):
        state = State(vertex, budgets, turn, previous_bids)
        bids = tuple(strategy.bid(state, rng) for strategy, rng in zip(strategies, rngs))
        if precision:
            bids = tuple(b if isinstance(b, Decimal) else Decimal.from_float(b) for b in bids)
        updated = settle(budgets, bids, mechanism)
        winner = 0 if bids[0] > bids[1] else 1  # paper: Min wins all ties
        next_vertex = strategies[winner].move(vertex)
        if next_vertex not in graph.edges[vertex]:
            raise ValueError(f"Strategy selected illegal edge {vertex}->{next_vertex}")
        # Definition 6: sum w(v_0), ..., w(v_(n-1)); not destination rewards.
        energy += graph.weights[vertex]
        wins += winner == 0
        ties += bids[0] == bids[1]
        scale = sum(updated) if precision else math.fsum(updated)
        if scale:
            budgets = (updated[0] / scale, updated[1] / scale)
            if mechanism == "poorman":
                log_total += _log(scale)
            previous_bids = (bids[0] / scale, bids[1] / scale)
        else:
            zero = Decimal(0) if precision else 0.0
            budgets, log_total, previous_bids = (zero, zero), -math.inf, (zero, zero)
        # Never treat numerical starvation as a genuine bankrupt player.
        for before, bid, after in zip(state.budgets, bids, budgets):
            if not precision and before > bid and after < 1e-280:
                raise FloatingPointError(f"Budget dynamic range exhausted at round {turn+1}; reduce horizon/fraction")
        for strategy in strategies:
            strategy.observe(state, bids, scale)
        if trace_every and (turn % trace_every == 0 or turn == rounds - 1):
            trace.append({"round": turn + 1, "vertex": vertex, "next_vertex": next_vertex,
                          "reward": graph.weights[vertex], "winner": "Max" if winner == 0 else "Min",
                          "max_bid_normalized": bids[0], "min_bid_normalized": bids[1],
                          "max_budget_before": state.budgets[0], "min_budget_before": state.budgets[1],
                          "max_budget_after": budgets[0], "min_budget_after": budgets[1],
                          "log_total_after": log_total, "running_mean": energy / (turn + 1)})
        vertex = next_vertex
        if turn + 1 in points:
            samples.append(Sample(turn + 1, energy / (turn + 1), wins / (turn + 1),
                                  ties / (turn + 1), float(budgets[0]) if scale else 0.0, log_total, vertex,
                                  log_total + _log(budgets[0]), log_total + _log(budgets[1])))
    return Result(samples, trace)


def random_turn(graph, reference, p, rounds, seed, checkpoints=(), start=0):
    if not 0 <= p <= 1 or rounds <= 0 or not 0 <= start < len(graph.weights):
        raise ValueError("Invalid random-turn parameters")
    rng = random.Random(seed)
    points = set(checkpoints) | {rounds}
    vertex, energy = start, 0.0
    rows = []
    for turn in range(1, rounds + 1):
        energy += graph.weights[vertex]
        vertex = reference.max_moves[vertex] if rng.random() < p else reference.min_moves[vertex]
        if turn in points:
            rows.append({"rounds": turn, "mean_payoff": energy / turn})
    return rows
