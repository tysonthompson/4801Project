"""Seeded budget sweeps, strategy comparisons, controls, and exported analysis."""
import csv
from dataclasses import asdict
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import statistics
import sys
from datetime import datetime, timezone
from importlib.metadata import version

from scipy.stats import t as student_t
from .graph import Graph, examples
from .simulation import simulate, random_turn
from .strategies import make_strategy, PredictableCounter
from .theory import solve, probability


def write_csv(path, rows):
    if not rows:
        Path(path).write_text("", encoding="utf-8")
        return
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def derive_seed(base, *parts):
    payload = json.dumps([base, *parts], separators=(",", ":"))
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big")


def confidence(values):
    mean = statistics.mean(values)
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    half = float(student_t.ppf(0.975, len(values) - 1)) * sd / math.sqrt(len(values)) if len(values) > 1 else math.nan
    return mean, sd, mean - half, mean + half


def aggregate(rows):
    keys = ("graph", "mechanism", "ratio", "max_strategy", "min_strategy", "rounds")
    groups = {}
    for row in rows:
        groups.setdefault(tuple(row[k] for k in keys), []).append(row)
    result = []
    for key, group in sorted(groups.items()):
        mean, sd, low, high = confidence([r["mean_payoff"] for r in group])
        result.append(dict(zip(keys, key)) | {
            "replicates": len(group), "mean_payoff": mean, "std_dev": sd,
            "decimal_replicates": sum(r.get("precision", 0) > 0 for r in group),
            "ci95_low": low, "ci95_high": high,
            "mixed_theory": group[0]["mixed_theory"], "pure_max_theory": group[0]["pure_max_theory"],
            "paper_lower": group[0]["paper_lower"], "paper_upper": group[0]["paper_upper"],
            "difference_from_mixed_theory": mean - group[0]["mixed_theory"],
            "mean_max_win_rate": statistics.mean(r["max_win_rate"] for r in group),
            "mean_tie_rate": statistics.mean(r["tie_rate"] for r in group)})
    return result


def run_suite(config_path, output):
    config_path, output = Path(config_path), Path(output)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output directory is not empty: {output}. Choose a new directory to preserve results.")
    ratios, horizons = config["ratios"], sorted(set(config["horizons"]))
    replicates = config["replicates"]
    if type(replicates) is not int or replicates < 2 or not horizons or any(type(h) is not int or h <= 0 for h in horizons):
        raise ValueError("Require >=2 replicates and positive integer horizons")
    if not ratios or any(not 0 < r < 1 for r in ratios):
        raise ValueError("Ratios must lie strictly between 0 and 1")
    builtins = examples()
    graphs = [builtins[name] if name in builtins else Graph.load(config_path.parent / name) for name in config["graphs"]]
    if not graphs or len({g.name for g in graphs}) != len(graphs):
        raise ValueError("Graph names must be nonempty and unique")
    output.mkdir(parents=True, exist_ok=True)
    params = {k: config.get(k, default) for k, default in (("epsilon", .05), ("slack", .02), ("fraction", .02))}
    rows, controls, failures, traces, retries = [], [], [], [], []
    total = len(graphs) * len(config["mechanisms"])
    for index, (graph, mechanism) in enumerate(itertools.product(graphs, config["mechanisms"]), 1):
        print(f"[{index}/{total}] {graph.name}: {mechanism}", flush=True)
        for ratio in ratios:
            mixed = solve(graph, probability(mechanism, ratio))
            pure = solve(graph, probability(mechanism, ratio, "pure"))
            pairs = list(config["pairs"])
            if config.get("counterstrategies", True):
                pairs.append(["fixed", "counter"])
            if mechanism == "poorman" and config.get("pure_poorman", True):
                pairs.append(["paper-pure", "counter"])
            for max_name, min_name in pairs:
                for replicate in range(replicates):
                    seed = derive_seed(config["seed"], graph.name, mechanism, ratio, max_name, min_name, replicate)
                    max_s = make_strategy(max_name, graph, 0, mechanism, ratio, **params)
                    min_s = (PredictableCounter(graph, max_s) if min_name == "counter" else
                             make_strategy(min_name, graph, 1, mechanism, ratio, **params))
                    metadata = {"graph": graph.name, "mechanism": mechanism, "ratio": ratio,
                                "max_strategy": max_name, "min_strategy": min_name,
                                "replicate": replicate, "seed": seed}
                    trace_every = max(1, horizons[-1] // 100) if replicate == 0 and ratio == .5 and max_name == min_name == "paper-mixed" else 0
                    precision = 0
                    try:
                        result = simulate(graph, max_s, min_s, mechanism=mechanism, ratio=ratio,
                                          rounds=horizons[-1], seed=seed, checkpoints=horizons,
                                          trace_every=trace_every)
                    except FloatingPointError as exc:
                        precision = 80
                        retries.append(metadata | {"float_error": str(exc), "retry_precision": precision})
                        # Restart from round zero with fresh strategy state and the same seed.
                        max_s = make_strategy(max_name, graph, 0, mechanism, ratio, **params)
                        min_s = (PredictableCounter(graph, max_s) if min_name == "counter" else
                                 make_strategy(min_name, graph, 1, mechanism, ratio, **params))
                        try:
                            result = simulate(graph, max_s, min_s, mechanism=mechanism, ratio=ratio,
                                              rounds=horizons[-1], seed=seed, checkpoints=horizons,
                                              trace_every=trace_every, precision=precision)
                        except (FloatingPointError, ArithmeticError) as retry_error:
                            failures.append(metadata | {"error": str(retry_error)})
                            continue
                    metadata["precision"] = precision
                    for sample in result.samples:
                        rows.append(metadata | asdict(sample) | {"mixed_theory": mixed.value, "pure_max_theory": pure.value,
                                    "paper_lower": getattr(max_s, "target_value", ""),
                                    "paper_upper": getattr(min_s, "target_value", "")})
                    traces.extend(metadata | trace for trace in result.trace)
            # Independent random-turn control: checks the reference and movement policies,
            # but is NEVER counted as evidence about a bidding strategy.
            p = probability(mechanism, ratio)
            for replicate in range(replicates):
                seed = derive_seed(config["seed"], graph.name, mechanism, ratio, "RT", replicate)
                for sample in random_turn(graph, mixed, p, horizons[-1], seed, horizons):
                    controls.append({"graph": graph.name, "mechanism": mechanism, "ratio": ratio,
                                     "p": p, "replicate": replicate, "seed": seed, **sample,
                                     "theory": mixed.value, "solver_lower": mixed.lower, "solver_upper": mixed.upper})
    summary = aggregate(rows)
    write_csv(output / "runs.csv", rows)
    write_csv(output / "summary.csv", summary)
    write_csv(output / "random_turn_controls.csv", controls)
    write_csv(output / "traces.csv", traces)
    write_csv(output / "failures.csv", failures)
    write_csv(output / "precision_retries.csv", retries)
    (output / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (output / "graphs.json").write_text(json.dumps([g.to_dict() for g in graphs], indent=2) + "\n", encoding="utf-8")
    root = Path(__file__).resolve().parent.parent
    source_hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root / "allpay").glob("*.py"))}
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
                "platform": platform.platform(), "packages": {p: version(p) for p in ("numpy", "scipy", "matplotlib")},
                "source_sha256": source_hashes, "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
                "failed_runs": len(failures), "successful_run_prefixes": len(rows),
                "decimal_retries": len(retries),
                "tie_rule": "Min wins exact ties", "reward": "source vertex before each move",
                "budget_units": "common normalized units; natural log tracks physical total"}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    from .report import create_report
    create_report(output, config, summary, controls, failures, retries)
    print(f"Saved {len(rows)} bidding prefixes and {len(controls)} RT controls to {output}; {len(failures)} numerical failures", flush=True)
    return len(failures)
