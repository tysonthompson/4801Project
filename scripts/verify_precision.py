"""Check recovered deterministic conditions at two monetary precisions.

Run from the project root: python scripts/verify_precision.py
Requires the package installed with pip install -e .
"""
import json
from pathlib import Path

from allpay.graph import examples
from allpay.simulation import simulate
from allpay.strategies import make_strategy, PredictableCounter


def main():
    checks = []
    for name in ("bowtie", "fork", "random"):
        graph = examples()[name]
        for ratio in (.75, .9):
            values = []
            for precision in (80, 120):
                left = make_strategy("paper-pure", graph, 0, "poorman", ratio)
                right = PredictableCounter(graph, left)
                result = simulate(graph, left, right, mechanism="poorman", ratio=ratio,
                                  rounds=10000, seed=4801, precision=precision).samples[-1]
                values.append({"precision": precision, "mean_payoff": result.mean_payoff,
                               "max_win_rate": result.max_win_rate,
                               "log_min_budget": result.log_min_budget})
            difference = abs(values[0]["mean_payoff"] - values[1]["mean_payoff"])
            if difference > 1e-9:
                raise AssertionError(f"Precision sensitivity in {name}, ratio={ratio}: {values}")
            checks.append({"graph": graph.name, "ratio": ratio, "runs": values, "payoff_difference": difference})
    path = Path("results/precision-validation.json")
    path.write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    print(f"All {len(checks)} conditions agree at 80 and 120 digits; saved {path}")


if __name__ == "__main__":
    main()
