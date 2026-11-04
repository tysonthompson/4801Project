# Validation

The automated suite passes **58 tests** on Python 3.12.10. Run it with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Checks include:

- All-pay payments for winners, losers, and ties; Richman conservation and poorman loss.
- Legal bids, strongly connected graphs, finite weights, and valid edges.
- Analytical random-turn values for the paper's two-vertex example and a periodic forced cycle.
- Potential-based movement that avoids a locally attractive but globally harmful successor.
- Explicit failure when the reference solver cannot certify convergence.
- The paper's piecewise budget-to-probability formulas and inverse shift function.
- Source-vertex reward accounting and Min's tie advantage.
- Repeatable private random streams, prefix consistency, and monetary scale invariance.
- Independent Decimal reconstruction of a deterministic physical-budget trajectory.
- Richman and low-budget poorman deterministic counterstrategy claims.
- The exact virtual asymmetric recurrence and its legal-budget invariant.
- Explicit detection of float dynamic-range exhaustion and successful Decimal continuation.
- Agreement of float and Decimal trajectories at ordinary scales.
- Report generation, protected output directories, provenance, and automatic Decimal restart.

## Monetary precision check

```powershell
.\.venv\Scripts\python.exe scripts/verify_precision.py
```

This runs the six extreme conditions (three nontrivial graphs, initial Max ratios 0.75 and 0.90, pure poorman strategy against the deterministic matching counter) for 10,000 rounds each, at both 80 and 120 digits. All six pairs produced exactly the same finite payoff and auction-win rate. The recorded results are in [precision-validation.json](../results/precision-validation.json).

For example, the two-vertex game at ratio 0.75 produces payoff 0.6427 at both precisions, while Min's final log budget is approximately -16,104. Representing that budget as an ordinary double would incorrectly turn it into zero. Decimal preserves its positive value and the ongoing auctions.

This checks stability for those conditions; it does not establish exact real arithmetic for arbitrary graphs, parameters, or infinite trajectories.

## Reproducibility

The package was installed successfully in editable mode. `requirements-lock.txt` records the tested dependency versions. Each suite's `manifest.json` records the Python/platform versions, parameter-file digest, and SHA-256 hashes of the simulator modules. Every run has a deterministic condition-derived seed. The independent RT control data are kept separate from actual bidding data.

The earlier float-only diagnostic run is preserved under `results/float-audit/`; use `results/standard/` for the completed experiment results.
