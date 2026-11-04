# Infinite-Duration All-Pay Bidding Games

COMP 4801A research simulator for the project proposed by Daniel Ferrante and Tyson Thompson. Implements finite prefixes of the mean-payoff games studied by Avni, Jecker, and Žikelić (SODA 2021), including both all-pay **Richman** and **poorman** payments.

## Start here

- [Completed experiment report](results/standard/REPORT.md): actual results, plots, theory comparisons, and limitations.
- [Findings](docs/RESULTS.md): answers to the proposal's research questions using the completed runs.
- [Methodology](docs/METHODOLOGY.md): equations, strategy construction, numerical choices, and correspondence to the paper.
- [Validation](docs/VALIDATION.md): automated checks and the monetary-precision audit.
- [Standard experiment configuration](configs/standard.json): all parameters used for the report.

Requires Python 3.10 or later. Run commands from this directory.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

On macOS/Linux, substitute `.venv/bin/python` for `.\.venv\Scripts\python.exe`.

For the exact tested Python 3.12 dependency versions, install `requirements-lock.txt` before installing this package: `python -m pip install -r requirements-lock.txt` followed by `python -m pip install -e . --no-deps` (using the virtual environment's interpreter).

For the exact tested Python 3.12 dependency versions, install `requirements-lock.txt` before installing this package: `python -m pip install -r requirements-lock.txt` followed by `python -m pip install -e . --no-deps` (using the virtual environment's interpreter).

### Run a game

```powershell
.\.venv\Scripts\python.exe -m allpay simulate --mechanism poorman --ratio 0.75 --rounds 10000
.\.venv\Scripts\python.exe -m allpay simulate --graph fork --mechanism richman --max-strategy uniform --min-strategy fixed --trace results/my-trace.csv
```

The first command runs the paper's mixed strategies on its two-vertex example. Max maximizes the mean vertex weight; Min minimizes it. The JSON result includes the measured mean, win/tie rates, remaining budget ratio, and theoretical reference. `--trace` saves every round, including bids, moves, budget updates, and running payoff. `--total-budget 100` changes physical monetary units without changing the included strategies' play.

### Reproduce the experiments

```powershell
.\.venv\Scripts\python.exe -m allpay experiment --config configs/quick.json --output results/my-quick-run
.\.venv\Scripts\python.exe -m allpay experiment --config configs/standard.json --output results/my-standard-run
```

Use a new output directory on each run; existing results are preserved. The quick configuration is a smoke experiment. The standard configuration runs four graphs, two mechanisms, five initial ratios, twelve replicates, and several strategy matchups, with checkpoints at 100, 1,000, and 10,000 rounds. It can take several minutes depending on hardware. All statistics are generated from completed simulations, not invented or populated from the reference formulas.

Outputs include `REPORT.md`, raw `runs.csv`, aggregated `summary.csv`, sampled `traces.csv`, independent `random_turn_controls.csv`, `precision_retries.csv`, `failures.csv`, PNG/PDF figures, copied configuration/graphs, and a provenance manifest with seeds, versions, and source hashes. A floating-point range failure triggers a fresh 80-digit Decimal run with the same seed. An unresolved numerical failure is recorded and produces exit code 2 rather than being silently counted as a result. For a single game, select Decimal directly with `--precision 80`.

### Query theory or add a graph

```powershell
.\.venv\Scripts\python.exe -m allpay theory --mechanism poorman --ratio 0.75 --kind mixed
.\.venv\Scripts\python.exe -m allpay graph --vertices 8 --density 0.3 --seed 42 --output graphs/my-graph.json
.\.venv\Scripts\python.exe -m allpay simulate --graph graphs/my-graph.json --rounds 20000
```

The theory query returns Max's random-turn probability (5/6 here), the numerical value and certified interval, potentials, strengths, and movement policies. The solver raises an error if its tolerance is not achieved.

Custom graphs use the format in [graphs/example.json](graphs/example.json): a finite weight for each zero-indexed vertex and a nonempty list of outgoing neighbors. Strong connectivity is checked. In suite configurations, built-in names are `bowtie`, `cycle`, `fork`, and `random`; other graph paths are relative to the configuration file.

## Strategies

| Name | Bidding rule | Move rule |
|---|---|---|
| `paper-mixed` | Paper's strength-scaled mixed strategy; virtual asymmetric reduction for poorman | Potential-optimal for its finite-epsilon target |
| `paper-pure` | Paper's deterministic poorman construction when its reserved budget ratio exceeds one; zero bids otherwise | Potential-optimal for its sure target |
| `fixed` | Fraction of remaining budget (default 0.02) | Optimal for mixed-value random-turn reference |
| `uniform` | Uniform in [0, 2 × fraction × budget] | Same reference moves |
| `aggressive` | Five times the fixed fraction, capped at own budget | Same reference moves |
| `greedy` | Fixed fraction | Highest/lowest immediate successor weight |
| `zero` | Zero | Same reference moves |
| `counter` | Min predicts a known deterministic opponent, matches its bid if affordable, else bids zero | Minimum-cycle policy |

`counter` is available only as Min and rejects mixed opponents. It recomputes a public deterministic strategy, rather than inspecting a sampled private bid. There is no `paper-pure` Richman bidder: the paper proves Max cannot deterministically guarantee more than the minimum-cycle value, and the counterstrategy experiments demonstrate why.

Parameters `--epsilon`, `--slack`, and `--fraction` control the paper approximation and baseline aggressiveness. Smaller epsilon/slack approach theoretical guarantees but generally require longer runs. Parameters are fixed for the entire trajectory; strategies are not told the chosen simulation horizon.

## What the results mean

The infinite payoff is a **liminf of prefix averages**. This program measures finite prefix averages; no finite simulation establishes an almost-sure theorem. It distinguishes:

1. The paper's theoretical optimal sure/almost-sure values.
2. The finite-epsilon asymptotic bounds of the implemented paper strategies.
3. Observed finite trajectories, including baselines that need not achieve either reference.
4. Random-turn controls, which test the reference solver and are not bidding experiments.

The sure value is Max's guarantee against a counterstrategy, not the payoff of a deterministic equilibrium. Confidence intervals use independent run means, not dependent rounds. All exact bid ties favor Min. No minimum bid or rounded currency is introduced. See the methodology for numerical limitations.

## Project layout

```text
allpay/graph.py         graph validation and reproducible examples
allpay/theory.py        reference formulas and Bellman solver
allpay/strategies.py    paper constructions, heuristics, deterministic counter
allpay/simulation.py    simultaneous auction engine and random-turn controls
allpay/experiments.py   seeded experiment grid, statistics, provenance
allpay/report.py        generated report and publication-ready plots
allpay/cli.py           command-line interface
tests/                 model, numerical, and end-to-end verification
configs/               quick and standard experiment designs
docs/                  methodology and results discussion
results/standard/      completed standard experiment artifacts
```

## Reference

Guy Avni, Ismaël Jecker, and Đorđe Žikelić. *Infinite-Duration All-Pay Bidding Games*. Proceedings of the 2021 ACM-SIAM Symposium on Discrete Algorithms, pp. 617–636. [DOI: 10.1137/1.9781611976465.38](https://doi.org/10.1137/1.9781611976465.38). [Author preprint](https://arxiv.org/abs/2005.06636). The supplied ACM PDF is the primary context; the expanded preprint supplies the detailed poorman constructions. The source PDF is not redistributed in this repository.
