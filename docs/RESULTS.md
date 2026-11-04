# Findings from the completed experiments

The standard experiment completed **3,600 bidding games** of 10,000 rounds, plus **480 independent random-turn control games**. Recording prefixes at 100, 1,000, and 10,000 rounds produced 10,800 bidding observations and 1,440 control observations. There were **zero unresolved numerical failures**. Seventy-two bidding games required the documented Decimal restart. The automated suite passes 58 tests, and the six distinct extreme-budget conditions agree at 80 and 120 digits.

The experiment uses four graphs, two payment mechanisms, five budget ratios, and twelve replicates per strategy condition. Results below come from [summary.csv](../results/standard/summary.csv); the full tables and figures are in the [generated report](../results/standard/REPORT.md). Parameters were epsilon=0.05, reserve slack=0.02, baseline bid fraction=0.02, and base seed=4801.

## How initial budgets affect payoff

On the paper's two-vertex graph, where the random-turn value equals its coin bias, the paper mixed strategies produce:

| Initial Max ratio | Richman observed | Richman limiting value | Poorman observed | Poorman limiting value |
|---:|---:|---:|---:|---:|
| 0.10 | 0.49843 | 0.50000 | 0.04320 | 0.05556 |
| 0.25 | 0.49762 | 0.50000 | 0.16073 | 0.16667 |
| 0.50 | 0.50070 | 0.50000 | 0.49900 | 0.50000 |
| 0.75 | 0.50174 | 0.50000 | 0.83873 | 0.83333 |
| 0.90 | 0.50056 | 0.50000 | 0.95768 | 0.94444 |

The Richman observations remain near 0.5 across initial ratios. Poorman gives a strong advantage to the player with more initial money. The fork and seeded six-vertex graph exhibit the same qualitative distinction, with payoffs transformed by their graph structures and weights.

These are approximate strategies at a finite horizon, so small differences from the limiting reference are expected. At ratio 0.75 under poorman, the observed 95% confidence interval is [0.83776, 0.83970], which excludes the exact limiting value 0.83333. That is not evidence against the theorem: the implemented finite-epsilon strategies have the wider asymptotic interval [0.82293, 0.86167]. Sampling uncertainty, strategy approximation, and horizon effects are different sources of error.

## How bidding and movement strategies compare

At equal budgets, identical fixed bidders remain tied. Since Min wins ties, the two-vertex payoff is 0.0001: only the initial reward of one contributes over 10,000 rounds. A deterministic matching counter also defeats fixed Richman bidding, consistent with the paper's impossibility result.

Generic random bidding is less reliable than the paper construction under poorman payments. At equal budgets on the two-vertex graph, `uniform` against `uniform` averages 0.52796 with a 95% interval [0.36160, 0.69431]. Paper mixed strategies average 0.49900 with interval [0.49700, 0.50100]. This illustrates that adding randomness alone does not give the paper's guarantee.

Deterministic strategies become useful to a richer poorman player. Against the matching counter, the paper pure Max strategy scores 0.6427 at ratio 0.75 and 0.8712 at ratio 0.90. Their limiting sure references are 0.66667 and 0.88889; their implemented finite-epsilon targets are 0.64883 and 0.88162. The remaining shortfall at 10,000 rounds illustrates transient effects; these bounds are asymptotic, not finite-prefix bounds. A matching counter is a valid opponent, not necessarily the worst opponent in every richer-Max case.

Graph movement also matters. On the seeded six-vertex graph at equal budgets, greedy Max movement against paper mixed Min averages 1.44563 under Richman and 1.49048 under poorman, below the mixed reference of 1.66667. The greedy baseline can choose locally attractive vertices without accounting for later losses. These comparisons concern the complete strategy pairs, not an isolated causal estimate of movement quality.

## Agreement improves with horizon, with qualifications

For paper mixed strategies on the two-vertex graph, mean absolute error across the five budget ratios decreases:

| Rounds | Richman error | Poorman error |
|---:|---:|---:|
| 100 | 0.07550 | 0.01772 |
| 1,000 | 0.01002 | 0.00946 |
| 10,000 | 0.00139 | 0.00759 |

The other two nontrivial graphs also show decreasing aggregate error over the tested horizons. Poorman retains a larger gap, consistent with the finite-epsilon approximation and reserve slack. More rounds alone need not remove a fixed strategy-approximation error.

The forced-cycle control has value zero, independent of strategies and budgets. Its measured averages are exactly 0.01, 0.001, and 0.0001 at the selected horizons because each horizon ends one vertex into the three-vertex cycle. This confirms both the graph constraint and the source-vertex payoff convention; it is not simulation noise.

## What can be concluded

The simulations reproduce the main qualitative predictions on the tested graphs: approximate budget independence under mixed Richman play, budget-sensitive mixed poorman values, vulnerability of deterministic Richman bidders, and useful deterministic poorman guarantees when Max is richer. They also expose why finite currency precision can produce misleading results.

The results do **not** prove almost-sure infinite-duration claims or establish performance on arbitrary strongly connected graphs. There is only one seeded random graph, twelve replicates per condition, fixed epsilon/slack, and one starting vertex. Intervals are approximate run-level Student-t intervals without multiplicity correction. Suitable extensions are larger graph ensembles, more seeds, longer trajectories, and explicit epsilon/slack and starting-vertex sweeps.

For the definitions and exact connection to the supplied paper, see [methodology](METHODOLOGY.md). For the numerical and reproducibility checks, see [validation](VALIDATION.md).
