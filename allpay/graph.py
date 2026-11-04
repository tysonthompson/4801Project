"""Validated finite, weighted, strongly connected directed graphs."""
from dataclasses import dataclass
import json
import math
from pathlib import Path
import random


@dataclass(frozen=True)
class Graph:
    name: str
    weights: tuple[float, ...]
    edges: tuple[tuple[int, ...], ...]

    def __post_init__(self):
        n = len(self.weights)
        if not n or len(self.edges) != n:
            raise ValueError("A graph needs weights and one adjacency list per vertex")
        if not all(math.isfinite(w) for w in self.weights):
            raise ValueError("Weights must be finite")
        if any(not row or len(set(row)) != len(row) or
               any(type(v) is not int or not 0 <= v < n for v in row) for row in self.edges):
            raise ValueError("Edges must be nonempty, unique lists of valid integer vertices")
        reverse = [[] for _ in range(n)]
        for v, row in enumerate(self.edges):
            for u in row:
                reverse[u].append(v)
        for adjacency in (self.edges, reverse):
            seen, stack = {0}, [0]
            while stack:
                for u in adjacency[stack.pop()]:
                    if u not in seen:
                        seen.add(u)
                        stack.append(u)
            if len(seen) != n:
                raise ValueError("The paper's mean-payoff results require a strongly connected graph")

    def to_dict(self):
        return {"name": self.name, "weights": self.weights, "edges": self.edges}

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(str(data["name"]), tuple(float(w) for w in data["weights"]),
                   tuple(tuple(row) for row in data["edges"]))


def random_graph(n=6, density=0.35, seed=4801):
    if n < 2 or not 0 <= density <= 1:
        raise ValueError("Require n >= 2 and density in [0, 1]")
    rng = random.Random(seed)
    # A directed Hamiltonian cycle guarantees strong connectivity.
    edges = tuple(tuple(sorted({(v + 1) % n} | {u for u in range(n) if rng.random() < density}))
                  for v in range(n))
    return Graph(f"random_{n}_{seed}", tuple(rng.randint(-3, 5) for _ in range(n)), edges)


def examples():
    return {
        "bowtie": Graph("bowtie", (1.0, 0.0), ((0, 1), (0, 1))),
        "cycle": Graph("cycle", (1.0, 0.0, -1.0), ((1,), (2,), (0,))),
        "fork": Graph("fork", (0.0, 2.0, -1.0, 0.5), ((1, 2), (0, 3), (0, 2), (0, 1))),
        "random": random_graph(),
    }
