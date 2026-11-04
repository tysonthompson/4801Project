from dataclasses import asdict
from decimal import Decimal, localcontext
import json
import math
import random

import pytest

from allpay.graph import Graph, examples, random_graph
from allpay.theory import probability, solve, shift_inverse
from allpay.strategies import Baseline, PaperStrategy, PredictableCounter, State, Strategy, make_strategy
from allpay.simulation import settle, simulate, random_turn
from allpay.experiments import confidence, derive_seed, run_suite


@pytest.mark.parametrize("mechanism,expected", [("richman", (.4, .6)), ("poorman", (.3, .3))])
def test_both_players_pay_even_the_loser(mechanism, expected):
    assert settle((.6, .4), (.3, .1), mechanism) == pytest.approx(expected)


def test_equal_bids_pay_both_players():
    assert settle((.7, .3), (.2, .2), "richman") == pytest.approx((.7, .3))
    assert settle((.7, .3), (.2, .2), "poorman") == pytest.approx((.5, .1))


@pytest.mark.parametrize("bids", [(-.1, 0), (.6, 0), (math.nan, 0), (math.inf, 0)])
def test_illegal_bids_rejected(bids):
    with pytest.raises(ValueError):
        settle((.5, .5), bids, "richman")


def test_payment_conservation_random_inputs():
    rng = random.Random(10)
    for _ in range(500):
        b, c = rng.random(), rng.random()
        x, y = b * rng.random(), c * rng.random()
        assert sum(settle((b, c), (x, y), "richman")) == pytest.approx(b + c)
        assert sum(settle((b, c), (x, y), "poorman")) == pytest.approx(b + c - x - y)


@pytest.mark.parametrize("weights,edges", [((1, 0), ((0,), (1,))), ((1,), ((),)),
                                        ((math.nan,), ((0,),)), ((1,), ((1,),))])
def test_bad_graphs(weights, edges):
    with pytest.raises(ValueError):
        Graph("invalid", weights, edges)


def test_seeded_graph_is_reproducible_and_connected():
    assert random_graph(seed=5) == random_graph(seed=5)
    assert random_graph(seed=5) != random_graph(seed=6)
    Graph("cycle", (1, 2, 3), ((1,), (2,), (0,)))


@pytest.mark.parametrize("r,p", [(.1, 1 / 18), (.25, 1 / 6), (.5, .5), (.75, 5 / 6), (.9, 17 / 18)])
def test_paper_poorman_mixed_formula(r, p):
    assert probability("poorman", r) == pytest.approx(p)
    assert probability("poorman", 1 - r) == pytest.approx(1 - p)


def test_sure_values_are_not_mixed_values():
    assert probability("richman", .99, "pure") == 0
    assert probability("richman", .01, "mixed") == .5
    assert probability("poorman", .5, "pure") == 0
    assert probability("poorman", .75, "pure") == pytest.approx(2 / 3)


@pytest.mark.parametrize("r", [0, 1, -.1, math.nan])
def test_theory_excludes_zero_budgets(r):
    with pytest.raises(ValueError):
        probability("richman", r)


@pytest.mark.parametrize("p", [0, .01, .2, .5, .83, 1])
def test_rt_exact_bowtie_and_periodic_cycle(p):
    ref = solve(examples()["bowtie"], p)
    assert ref.value == pytest.approx(p, abs=1e-9)
    assert ref.lower - 1e-12 <= p <= ref.upper + 1e-12
    assert solve(examples()["cycle"], p).value == pytest.approx(0, abs=1e-9)


def test_moves_look_beyond_immediate_reward():
    graph = Graph("trap", (0, 2, 1, -10), ((1, 2), (3,), (0, 2), (0,)))
    ref = solve(graph, 1)
    assert ref.value == pytest.approx(1, abs=1e-9)
    assert ref.max_moves[0] == 2  # immediate reward 2 leads through a -10 vertex


def test_nonconvergence_is_explicit():
    with pytest.raises(RuntimeError):
        solve(examples()["fork"], .37, max_iterations=1)


@pytest.mark.parametrize("eps", [.001, .05, .5, 2])
def test_inverse_shift(eps):
    alpha = shift_inverse(eps)
    assert -math.log1p(-alpha) / math.log1p(alpha) == pytest.approx(1 + eps)


def run_pair(mechanism="poorman", ratio=.75, max_name="paper-mixed", min_name="paper-mixed", **kwargs):
    graph = examples()["bowtie"]
    left = make_strategy(max_name, graph, 0, mechanism, ratio)
    right = PredictableCounter(graph, left) if min_name == "counter" else make_strategy(min_name, graph, 1, mechanism, ratio)
    return simulate(graph, left, right, mechanism=mechanism, ratio=ratio, **kwargs)


def test_reward_is_source_and_min_wins_zero_ties():
    result = run_pair(max_name="zero", min_name="zero", rounds=4, trace_every=1)
    assert result.samples[-1].mean_payoff == .25  # initial vertex has reward 1
    assert result.samples[-1].max_win_rate == 0
    assert result.samples[-1].tie_rate == 1
    assert all(r["winner"] == "Min" for r in result.trace)


def test_reproducible_independent_streams_and_prefixes():
    first = run_pair(rounds=1000, seed=30, checkpoints=(100,))
    assert first == run_pair(rounds=1000, seed=30, checkpoints=(100,))
    assert first.samples[0] == run_pair(rounds=100, seed=30).samples[0]
    assert first != run_pair(rounds=1000, seed=31, checkpoints=(100,))


def test_total_budget_scale_invariance():
    a = run_pair(rounds=500, seed=8, total_budget=1)
    b = run_pair(rounds=500, seed=8, total_budget=1000000)
    assert a.samples[-1].mean_payoff == b.samples[-1].mean_payoff
    assert b.samples[-1].log_total_budget - a.samples[-1].log_total_budget == pytest.approx(math.log(1000000))


def test_poorman_renormalization_matches_decimal_physical_budgets():
    graph = examples()["bowtie"]
    left = Baseline(graph, 0, "fixed", "poorman", .75, fraction=.125)
    right = Baseline(graph, 1, "fixed", "poorman", .75, fraction=.25)
    result = simulate(graph, left, right, mechanism="poorman", ratio=.75, rounds=100, trace_every=1)
    with localcontext() as context:
        context.prec = 60
        b, c = Decimal(".75"), Decimal(".25")
        for row in result.trace:
            x, y = b / 8, c / 4
            assert row["winner"] == ("Max" if x > y else "Min")
            b, c = b - x, c - y
            assert row["max_budget_after"] == pytest.approx(float(b / (b + c)))
            assert row["log_total_after"] == pytest.approx(float((b + c).ln()))


@pytest.mark.parametrize("ratio", [.1, .5, .9])
def test_richman_deterministic_counter_lemma(ratio):
    result = run_pair(mechanism="richman", ratio=ratio, max_name="fixed", min_name="counter", rounds=2000)
    assert result.samples[-1].max_win_rate * 2000 <= math.ceil(ratio / (1 - ratio)) + 1


@pytest.mark.parametrize("ratio", [.1, .25, .5])
def test_poorman_poor_deterministic_counter(ratio):
    result = run_pair(ratio=ratio, max_name="fixed", min_name="counter", rounds=2000)
    assert result.samples[-1].max_win_rate == 0


def test_counter_rejects_private_random_bid_prediction():
    graph = examples()["bowtie"]
    with pytest.raises(ValueError):
        PredictableCounter(graph, make_strategy("paper-mixed", graph, 0, "richman", .5))


@pytest.mark.parametrize("ratio", [.1, .5, .9])
def test_virtual_budget_reduction_invariant(ratio):
    graph = examples()["fork"]

    class CheckedPaper(PaperStrategy):
        def observe(self, state, bids, scale):
            c = state.budgets[1 - self.player]
            virtual_before = self.virtual / c
            virtual_expected = virtual_before - bids[self.player] / c + self.W * bids[1 - self.player] / c
            super().observe(state, bids, scale)
            after = settle(state.budgets, bids, "poorman")
            spare = (after[self.player] - self.W * after[1 - self.player]) / scale
            assert 0 <= self.virtual <= spare + 1e-10
            assert self.virtual / (after[1 - self.player] / scale) == pytest.approx(virtual_expected, rel=1e-12)

    left = CheckedPaper(graph, 0, "poorman", ratio)
    right = CheckedPaper(graph, 1, "poorman", ratio)
    simulate(graph, left, right, mechanism="poorman", ratio=ratio, rounds=10000, seed=4)


def test_numerical_starvation_is_not_reported_as_real_bankruptcy():
    graph = examples()["bowtie"]
    left = Baseline(graph, 0, "fixed", "poorman", .5, fraction=.5)
    right = Baseline(graph, 1, "zero", "poorman", .5)
    with pytest.raises(FloatingPointError):
        simulate(graph, left, right, mechanism="poorman", rounds=2000)


def test_both_players_can_exhaust_budgets_and_game_continues():
    result = simulate(examples()["bowtie"],
                      Baseline(examples()["bowtie"], 0, "aggressive", "poorman", .5, .5),
                      Baseline(examples()["bowtie"], 1, "aggressive", "poorman", .5, .5),
                      mechanism="poorman", rounds=10)
    assert result.samples[-1].log_total_budget == -math.inf
    assert result.samples[-1].tie_rate == 1


def test_decimal_finishes_extreme_pure_counter_without_bankruptcy():
    result = run_pair(ratio=.75, max_name="paper-pure", min_name="counter", rounds=2000, precision=80)
    sample = result.samples[-1]
    assert math.isfinite(sample.log_min_budget) and sample.log_min_budget < -1000
    assert .60 < sample.mean_payoff < .75


@pytest.mark.parametrize("mechanism", ["richman", "poorman"])
def test_decimal_and_float_agree_at_ordinary_scales(mechanism):
    a = run_pair(mechanism=mechanism, rounds=100, seed=42)
    b = run_pair(mechanism=mechanism, rounds=100, seed=42, precision=80)
    assert a.samples[-1].mean_payoff == b.samples[-1].mean_payoff
    assert a.samples[-1].max_budget_ratio == pytest.approx(b.samples[-1].max_budget_ratio)


def test_decimal_preserves_very_small_bids_against_zero():
    graph = examples()["bowtie"]
    left = Baseline(graph, 0, "fixed", "poorman", .5, .5)
    right = Baseline(graph, 1, "zero", "poorman", .5)
    result = simulate(graph, left, right, mechanism="poorman", rounds=2000, precision=80)
    assert result.samples[-1].max_win_rate == 1
    assert result.samples[-1].log_max_budget < -1000


def test_rt_monte_carlo_control():
    graph = examples()["bowtie"]
    result = random_turn(graph, solve(graph, .3), .3, 30000, 99)
    assert result[0]["mean_payoff"] == pytest.approx(.3, abs=.015)


def test_confidence_uses_runs_and_seed_is_stable():
    mean, sd, low, high = confidence([1, 2, 3, 4])
    assert mean == 2.5 and low < mean < high
    assert derive_seed(4801, "a", 0) == derive_seed(4801, "a", 0)
    assert derive_seed(4801, "a", 0) != derive_seed(4801, "a", 1)


def test_end_to_end_suite(tmp_path):
    config = {"seed": 10, "graphs": ["bowtie"], "mechanisms": ["richman", "poorman"],
              "ratios": [.5, .75], "horizons": [10, 2000], "replicates": 2,
              "pairs": [["paper-mixed", "paper-mixed"]]}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    output = tmp_path / "output"
    assert run_suite(path, output) == 0
    for name in ("REPORT.md", "runs.csv", "summary.csv", "budget_sweep.pdf", "convergence.png", "manifest.json"):
        assert (output / name).stat().st_size > 0
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["failed_runs"] == 0
    assert manifest["decimal_retries"] == 2
    with pytest.raises(ValueError, match="not empty"):
        run_suite(path, output)
