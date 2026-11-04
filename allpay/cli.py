import argparse
from dataclasses import asdict
import json
from pathlib import Path
from .graph import Graph, examples, random_graph
from .theory import probability, solve
from .strategies import make_strategy, PredictableCounter
from .simulation import simulate
from .experiments import run_suite, write_csv


def get_graph(name):
    return examples()[name] if name in examples() else Graph.load(name)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Infinite-duration all-pay bidding: finite-prefix experiments")
    sub = parser.add_subparsers(dest="command", required=True)
    suite = sub.add_parser("experiment", help="Run a reproducible experiment suite and generate a report")
    suite.add_argument("--config", default="configs/standard.json")
    suite.add_argument("--output", default="results/standard")
    single = sub.add_parser("simulate", help="Run one all-pay game")
    single.add_argument("--graph", default="bowtie", help="bowtie, cycle, fork, random, or a graph JSON file")
    single.add_argument("--mechanism", choices=("richman", "poorman"), default="poorman")
    single.add_argument("--ratio", type=float, default=.75)
    single.add_argument("--max-strategy", default="paper-mixed")
    single.add_argument("--min-strategy", default="paper-mixed")
    single.add_argument("--rounds", type=int, default=10000)
    single.add_argument("--seed", type=int, default=4801)
    single.add_argument("--start", type=int, default=0)
    single.add_argument("--epsilon", type=float, default=.05)
    single.add_argument("--slack", type=float, default=.02)
    single.add_argument("--fraction", type=float, default=.02)
    single.add_argument("--total-budget", type=float, default=1.0)
    single.add_argument("--precision", type=int, default=0, help="0 for floats; >=30 for Decimal monetary arithmetic")
    single.add_argument("--trace", type=Path, help="Optional full round-level CSV")
    theory = sub.add_parser("theory", help="Compute a paper reference with numerical bounds")
    theory.add_argument("--graph", default="bowtie")
    theory.add_argument("--mechanism", choices=("richman", "poorman"), default="poorman")
    theory.add_argument("--ratio", type=float, default=.75)
    theory.add_argument("--kind", choices=("pure", "mixed"), default="mixed")
    generate = sub.add_parser("graph", help="Generate a seeded strongly connected graph")
    generate.add_argument("--vertices", type=int, default=6)
    generate.add_argument("--density", type=float, default=.35)
    generate.add_argument("--seed", type=int, default=4801)
    generate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "experiment":
            return 2 if run_suite(args.config, args.output) else 0
        if args.command == "graph":
            graph = random_graph(args.vertices, args.density, args.seed)
            if args.output.exists():
                raise ValueError("Graph output already exists")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(graph.to_dict(), indent=2) + "\n", encoding="utf-8")
            return 0
        graph = get_graph(args.graph)
        if args.command == "theory":
            p = probability(args.mechanism, args.ratio, args.kind)
            print(json.dumps({"p": p, **asdict(solve(graph, p))}, indent=2))
            return 0
        params = {k: getattr(args, k) for k in ("epsilon", "slack", "fraction")}
        max_s = make_strategy(args.max_strategy, graph, 0, args.mechanism, args.ratio, **params)
        min_s = (PredictableCounter(graph, max_s) if args.min_strategy == "counter" else
                 make_strategy(args.min_strategy, graph, 1, args.mechanism, args.ratio, **params))
        if args.trace and args.trace.exists():
            raise ValueError("Trace output already exists")
        result = simulate(graph, max_s, min_s, mechanism=args.mechanism, ratio=args.ratio,
                          rounds=args.rounds, seed=args.seed, start=args.start, total_budget=args.total_budget,
                          trace_every=1 if args.trace else 0, precision=args.precision)
        if args.trace:
            args.trace.parent.mkdir(parents=True, exist_ok=True)
            write_csv(args.trace, result.trace)
        print(json.dumps({**asdict(result.samples[-1]),
                          "mixed_reference": solve(graph, probability(args.mechanism, args.ratio)).value,
                          "paper_lower": getattr(max_s, "target_value", None),
                          "paper_upper": getattr(min_s, "target_value", None)}, indent=2))
        return 0
    except (ValueError, RuntimeError, FloatingPointError, OSError, KeyError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
