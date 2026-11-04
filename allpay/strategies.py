"""Bidders see public pre-round state, never the opponent's sampled bid."""
from dataclasses import dataclass
import math
import random
from .graph import Graph
from .theory import probability, solve, shift_inverse


@dataclass(frozen=True)
class State:
    vertex: int
    budgets: tuple[float, float]  # common normalized monetary units
    round: int
    last_bids: tuple[float, float] = (0.0, 0.0)


class Strategy:
    deterministic = False

    def bid(self, state: State, rng: random.Random) -> float:
        raise NotImplementedError

    def move(self, vertex: int) -> int:
        return self.moves[vertex]

    def observe(self, state, bids, scale):
        pass


class Baseline(Strategy):
    def __init__(self, graph, player, name, mechanism, ratio, fraction=0.02):
        if name not in ("zero", "fixed", "uniform", "aggressive", "greedy"):
            raise ValueError(f"Unknown baseline: {name}")
        if not math.isfinite(fraction) or not 0 <= fraction <= 0.5:
            raise ValueError("Baseline fraction must be in [0, 0.5]")
        self.player, self.name, self.fraction = player, name, fraction
        self.deterministic = name != "uniform"
        reference = solve(graph, probability(mechanism, ratio))
        self.moves = reference.max_moves if player == 0 else reference.min_moves
        if name == "greedy":
            choose = max if player == 0 else min
            self.moves = tuple(choose(row, key=lambda u: graph.weights[u]) for row in graph.edges)

    def bid(self, state, rng):
        factor = {"zero": 0.0, "aggressive": 5.0}.get(self.name, 1.0)
        if self.name == "uniform":
            factor = 2 * rng.random()  # same mean spend fraction as fixed
        return state.budgets[self.player] * min(1.0, self.fraction * factor)


class PaperStrategy(Strategy):
    """Finite-epsilon constructions from Sections 2.4 and 3 of the paper.

    Poorman implements Lemma 31's virtual asymmetric budget A=C*B_tilde.
    A is updated in OLD common units, then renormalized with real budgets.
    It is not reset to B-W*C each turn (that would change the construction).
    """
    def __init__(self, graph, player, mechanism, ratio, kind="mixed", epsilon=0.05, slack=0.02):
        if player not in (0, 1) or mechanism not in ("richman", "poorman"):
            raise ValueError("Invalid player or mechanism")
        if kind not in ("pure", "mixed") or not 0 < slack < 1:
            raise ValueError("Require pure/mixed and 0 < slack < 1")
        probability(mechanism, ratio, kind)
        self.player, self.mechanism, self.kind = player, mechanism, kind
        self.deterministic = kind == "pure"
        self.alpha = shift_inverse(epsilon)
        self.epsilon, self.slack = epsilon, slack
        own = ratio if player == 0 else 1 - ratio
        self.W = (own / (1 - own)) * (1 - slack)
        self.virtual = own - self.W * (1 - own)
        if mechanism == "richman":
            if kind == "pure":
                raise ValueError("No paper pure Richman bidder; use fixed and the counterstrategy experiment")
            q = 1 / (2 + epsilon)
        elif kind == "pure":
            q = (self.W - 1) / (self.W + epsilon) if self.W > 1 else 0.0
        elif self.W > 1:
            q = (2 * self.W - 1) / (2 * self.W + epsilon)
        else:
            # Lemma's mixture probability must be positive.
            self.epsilon = min(epsilon, self.W / 2)
            if self.epsilon < 1e-6:
                raise ValueError("Budget ratio is too extreme for this numerical implementation")
            self.alpha = shift_inverse(self.epsilon)
            q = (self.W - self.epsilon) / 2
        self.target_p = q if player == 0 else 1 - q
        reference = solve(graph, self.target_p)
        self.target_value = reference.value
        self.moves = reference.max_moves if player == 0 else reference.min_moves
        maximum = max(reference.strengths)
        self.strength = tuple(s / maximum if maximum > 1e-14 else 0.0 for s in reference.strengths)

    def bid(self, state, rng):
        own, other = state.budgets[self.player], state.budgets[1 - self.player]
        s = self.strength[state.vertex]
        if own == 0:
            return 0.0
        if other == 0:
            return own * self.alpha  # legal positive bid beats a bankrupt opponent
        if self.mechanism == "richman":
            return rng.random() * self.alpha * own * s
        if self.kind == "pure":
            if self.W <= 1:
                return 0.0
            return self.alpha * self.virtual * s / max(1.0, self.W - 1)
        cap = self.alpha * self.virtual * s / max(1.0, self.W)
        threshold = 2 * max(1.0, self.W) * other
        if cap > threshold:
            return cap / 2
        if self.W <= 1 and rng.random() >= self.W - self.epsilon:
            return 0.0
        return rng.random() * cap

    def observe(self, state, bids, scale):
        if self.mechanism == "poorman":
            updated = math.fsum((self.virtual, -bids[self.player], self.W * bids[1 - self.player]))
            if updated < -1e-14 or not math.isfinite(updated):
                raise FloatingPointError("Virtual budget invariant failed")
            self.virtual = max(0.0, updated) / scale if scale else 0.0


class PredictableCounter(Strategy):
    """Lemma 17/32 counter to a KNOWN deterministic strategy, not bid peeking."""
    deterministic = True

    def __init__(self, graph, opponent):
        if not opponent.deterministic:
            raise ValueError("A counter cannot predict a mixed strategy's private randomness")
        self.opponent = opponent
        self.moves = solve(graph, 0.0).min_moves

    def bid(self, state, rng):
        predicted = self.opponent.bid(state, random.Random(0))
        return predicted if predicted <= state.budgets[1] else 0.0


def make_strategy(name, graph, player, mechanism, ratio, epsilon=0.05, slack=0.02, fraction=0.02):
    if name in ("paper-mixed", "paper-pure"):
        return PaperStrategy(graph, player, mechanism, ratio, name.split("-")[1], epsilon, slack)
    return Baseline(graph, player, name, mechanism, ratio, fraction)
