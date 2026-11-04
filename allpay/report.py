"""Standalone figures and a report generated from actual experiment outputs."""
from pathlib import Path
import math
import statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from .experiments import confidence


def create_report(output, config, summary, controls, failures, retries=()):
    output = Path(output)
    horizon = max(config["horizons"])
    final = [r for r in summary if r["rounds"] == horizon]
    graph_names = list(dict.fromkeys(r["graph"] for r in final))
    mechanisms = config["mechanisms"]
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "figure.dpi": 130, "savefig.bbox": "tight"})

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(output / f"{name}.png")
        fig.savefig(output / f"{name}.pdf")
        plt.close(fig)

    fig, axes = plt.subplots(len(graph_names), len(mechanisms), squeeze=False,
                             figsize=(6 * len(mechanisms), 3.3 * len(graph_names)))
    for i, graph in enumerate(graph_names):
        for j, mechanism in enumerate(mechanisms):
            ax = axes[i, j]
            group = sorted((r for r in final if r["graph"] == graph and r["mechanism"] == mechanism
                            and r["max_strategy"] == r["min_strategy"] == "paper-mixed"), key=lambda r: r["ratio"])
            if group:
                x = [r["ratio"] for r in group]
                ax.plot(x, [r["mixed_theory"] for r in group], "--", color="#333333", label="Infinite mixed value")
                ax.fill_between(x, [r["paper_lower"] for r in group], [r["paper_upper"] for r in group],
                                alpha=.18, color="#177f84", label="Finite-epsilon asymptotic bounds")
                ax.errorbar(x, [r["mean_payoff"] for r in group],
                            yerr=[max(0, r["ci95_high"] - r["mean_payoff"]) for r in group],
                            fmt="o-", capsize=3, color="#177f84", label="Bidding runs, 95% CI")
            ax.set(title=f"{graph} / {mechanism}", xlabel="Initial Max budget ratio", ylabel="Mean payoff")
            ax.grid(alpha=.2)
            if i == 0 and j == 0:
                ax.legend(fontsize=8)
    save(fig, "budget_sweep")

    fig, axes = plt.subplots(1, len(mechanisms), squeeze=False, figsize=(6 * len(mechanisms), 4))
    for j, mechanism in enumerate(mechanisms):
        ax = axes[0, j]
        for graph in graph_names:
            ys, lows, highs = [], [], []
            for h in sorted(config["horizons"]):
                group = [r for r in summary if r["graph"] == graph and r["mechanism"] == mechanism and r["rounds"] == h
                         and r["max_strategy"] == r["min_strategy"] == "paper-mixed"]
                ys.append(statistics.mean(abs(r["difference_from_mixed_theory"]) for r in group) if group else math.nan)
            ax.plot(sorted(config["horizons"]), ys, "o-", label=graph)
        ax.set(xscale="log", title=mechanism, xlabel="Rounds", ylabel="Mean absolute error across ratios")
        ax.grid(alpha=.2)
        ax.legend()
    save(fig, "convergence")

    # Fixed ratio: compare actual strategy pairs without implying they are minimax equilibria.
    display_ratio = min(config["ratios"], key=lambda r: abs(r - .5))
    fig, axes = plt.subplots(len(graph_names), len(mechanisms), squeeze=False,
                             figsize=(6 * len(mechanisms), 3.8 * len(graph_names)))
    for i, graph in enumerate(graph_names):
        for j, mechanism in enumerate(mechanisms):
            ax = axes[i, j]
            group = [r for r in final if r["graph"] == graph and r["mechanism"] == mechanism and r["ratio"] == display_ratio]
            ax.barh([r["max_strategy"] + " vs " + r["min_strategy"] for r in group],
                    [r["mean_payoff"] for r in group], color="#4a719b",
                    xerr=[max(0, r["ci95_high"] - r["mean_payoff"]) for r in group], capsize=2)
            if group:
                ax.axvline(group[0]["mixed_theory"], linestyle="--", color="#333333", label="Mixed value")
            ax.set(title=f"{graph} / {mechanism}, r={display_ratio}", xlabel="Mean payoff to Max")
    save(fig, "strategy_comparison")

    lines = ["# Simulation results", "", f"Generated from `{len(summary)}` aggregate groups; {config['replicates']} seeded replicates per condition, up to {horizon:,} rounds.",
             "", "## Model and interpretation", "",
             "Both players pay every bid. Richman transfers payments to the opponent; poorman removes them. Min wins exact ties. Rewards are the weights of vertices before each move. The statistic is the full-prefix mean, with no discarded warm-up. All graphs are strongly connected.",
             "", "The dashed reference is the infinite-duration optimal mixed value, computed through the paper's random-turn equivalence. The shaded band uses the actual epsilon and reserve slack of the implemented strategies. These are asymptotic guarantees, not finite-horizon confidence bands. Error bars are 95% Student-t intervals over independent run means; rounds within a trajectory are not treated as independent samples. No multiplicity correction is applied.",
             "", "Finite runs can support or fail to show predicted trends; they cannot prove an almost-sure infinite-horizon theorem. Heuristic matchups need not attain the minimax value. The pure-strategy value is Max's worst-case guarantee and is not the expected payoff of any arbitrary deterministic matchup.",
             "", "## Budget sweep", "", "![Budget sweep](budget_sweep.png)", "",
             "| Graph | Rule | Max ratio | Observed mean | 95% CI | Mixed value | Finite-epsilon asymptotic interval |", "|---|---|---:|---:|---|---:|---|"]
    for r in final:
        if r["max_strategy"] == r["min_strategy"] == "paper-mixed":
            lines.append(f"| {r['graph']} | {r['mechanism']} | {r['ratio']:.2f} | {r['mean_payoff']:.5f} | [{r['ci95_low']:.5f}, {r['ci95_high']:.5f}] | {r['mixed_theory']:.5f} | [{r['paper_lower']:.5f}, {r['paper_upper']:.5f}] |")
    lines += ["", "## Horizon sensitivity", "", "![Convergence](convergence.png)", "",
              "Points use prefixes of the same trajectories, so estimates at different horizons are correlated. The plotted error is averaged over tested ratios and is descriptive, not a convergence proof.", "",
              "## Strategy comparisons", "", "![Strategies](strategy_comparison.png)", "",
              "`fixed` bids a constant fraction of remaining funds; `uniform` samples from zero to twice that amount; `greedy` uses immediate vertex weights for moves; other baselines use random-turn potential-based moves. `counter` predicts only a known deterministic bid from public state, matches it if affordable, and otherwise bids zero. It never reads a mixed strategy's realized bid.", "",
              "## Random-turn controls", "", "These independently simulated controls check the solved reference and its movement policies. They are not all-pay bidding runs.", "",
              "| Graph | Rule | Ratio | Control mean | 95% CI | Reference |", "|---|---|---:|---:|---|---:|"]
    groups = {}
    for row in controls:
        if row["rounds"] == horizon:
            groups.setdefault((row["graph"], row["mechanism"], row["ratio"]), []).append(row)
    for (graph, mechanism, ratio), group in groups.items():
        mean, sd, low, high = confidence([r["mean_payoff"] for r in group])
        lines.append(f"| {graph} | {mechanism} | {ratio:.2f} | {mean:.5f} | [{low:.5f}, {high:.5f}] | {group[0]['theory']:.5f} |")
    lines += ["", "## Deterministic guarantees and counterstrategies", "",
              "A matching counter defeats fixed deterministic Richman bids after at most finitely many Max wins. Under poorman payments, a richer Max can still obtain a positive guarantee. Matching is an admissible opponent, but need not be the worst counterstrategy when Max is richer; a payoff above the sure reference does not contradict it.", "",
              "| Graph | Rule | Ratio | Max strategy | Observed mean | Pure reference | Implemented lower target |",
              "|---|---|---:|---|---:|---:|---|"]
    for r in final:
        if r["min_strategy"] == "counter":
            target = f"{r['paper_lower']:.5f}" if r["paper_lower"] != "" else "baseline"
            lines.append(f"| {r['graph']} | {r['mechanism']} | {r['ratio']:.2f} | {r['max_strategy']} | {r['mean_payoff']:.5f} | {r['pure_max_theory']:.5f} | {target} |")
    lines += ["", "## Numerical checks and limitations", "",
              f"Unresolved numerical failures: **{len(failures)}**. High-precision restarts: **{len(retries)}**. Float range failures trigger a complete restart with 80-digit Decimal monetary arithmetic and the same seed; `precision_retries.csv` records why. `runs.csv` records precision and log budgets. Only unresolved failures are omitted, in full; any such omissions must be investigated before drawing conclusions.", "",
              "Budgets are rescaled by a common factor after every round, preserving bid comparisons for the included scale-invariant strategies. The natural log of the physical total tracks poorman depletion without adding money. No bid floor, rounded cents, horizon-based spending schedule, or budget replenishment is used. Decimal fallback greatly extends monetary range; its precision, potential calculations, and random samples are still finite approximations.", "",
              "The Bellman solver stops only when its lower/upper value bounds differ by at most 1e-10. All graph weights and strategies are recorded. The RNG seed and parameters of every replicate are in `runs.csv`; package versions and source hashes are in `manifest.json`.", "",
              "## Files", "", "- `runs.csv`: individual bidding runs at each horizon.",
              "- `summary.csv`: run-mean statistics and theory comparisons.", "- `traces.csv`: sampled round-level trajectories for the first paper-strategy replicate at ratio 0.5.",
              "- `random_turn_controls.csv`: independent control simulations.", "- `config.json`, `graphs.json`, `manifest.json`: reproduction metadata.",
              "- Figures are available as PNG and vector PDF.", "",
              "## Reference", "",
              "Guy Avni, Ismaël Jecker, and Đorđe Žikelić. *Infinite-Duration All-Pay Bidding Games*. SODA 2021, pp. 617–636. [Published paper](https://doi.org/10.1137/1.9781611976465.38); [full preprint](https://arxiv.org/abs/2005.06636). See `docs/METHODOLOGY.md` in the project for equations and implementation mapping.", ""]
    (output / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
