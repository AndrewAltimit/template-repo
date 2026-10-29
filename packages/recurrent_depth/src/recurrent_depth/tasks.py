"""Serial-depth task generators with verifiable answers.

Every generator takes a ``depth`` (the number of dependent sequential steps
the answer requires) and a seeded ``random.Random`` and returns a
:class:`TaskItem`. Prompts are built so that, within one task family, the
prompt length does not depend on ``depth``: the same number of lines and the
same fixed-width fields appear at every depth. That matters for the timing
probes, where prompt length is the largest confounder of time-to-first-token.

The tasks are standard probes from the expressivity literature (pointer
chasing / k-hop composition, permutation state tracking, parity, graph
reachability). They are asked in a "no chain of thought" format: the model is
told to answer with the final answer only, so any serial computation has to
happen inside the forward pass.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import random
import re
import string
from typing import Callable

NO_COT_SUFFIX = "Respond with only the final answer and nothing else. Do not explain or show any steps."


@dataclass(frozen=True)
class TaskItem:
    """One probe item with its ground truth."""

    task: str
    depth: int
    prompt: str
    answer: str
    chance: float
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[`*_\"'().,:;!?\[\]{}]", " ", text)
    return " ".join(text.split())


def check_answer(item: TaskItem, response: str) -> bool:
    """Return True if ``response`` states the expected answer.

    The first whitespace-separated token of the normalized response must equal
    the normalized answer. A leading "answer" label is tolerated. This is
    deliberately strict: a response that hedges between options is wrong.
    """
    norm = _normalize(response)
    if not norm:
        return False
    tokens = norm.split()
    if tokens[0] in ("answer", "final") and len(tokens) > 1:
        tokens = tokens[1:]
        if tokens and tokens[0] == "answer" and len(tokens) > 1:
            tokens = tokens[1:]
    return tokens[0] == _normalize(item.answer)


# ---------------------------------------------------------------------------
# Pointer chasing (k-hop function composition)
# ---------------------------------------------------------------------------


def pointer_chase(depth: int, rng: random.Random, n_nodes: int = 26) -> TaskItem:
    """Follow a random cyclic mapping ``depth`` times.

    The mapping is a single cycle over ``n_nodes`` letters, so f^k(x) differs
    from x for every 0 < k < n_nodes and there is no shortcut through short
    cycles. Requires ``1 <= depth < n_nodes``.
    """
    if not 1 <= depth < n_nodes:
        raise ValueError(f"depth must be in [1, {n_nodes - 1}]")
    if n_nodes > 26:
        raise ValueError("n_nodes must be <= 26")
    letters = list(string.ascii_uppercase[:n_nodes])
    order = letters[:]
    rng.shuffle(order)
    mapping = {order[i]: order[(i + 1) % n_nodes] for i in range(n_nodes)}
    start = rng.choice(letters)
    node = start
    for _ in range(depth):
        node = mapping[node]
    lines = [f"{k}->{mapping[k]}" for k in mapping]
    rng.shuffle(lines)
    prompt = (
        "Each line maps a letter to another letter.\n"
        + "\n".join(lines)
        + f"\nStart at {start}. Apply the mapping exactly {depth:02d} times in a row. "
        "Which letter do you end on?\n" + NO_COT_SUFFIX
    )
    return TaskItem("pointer_chase", depth, prompt, node, 1.0 / n_nodes, {"start": start})


# ---------------------------------------------------------------------------
# Permutation state tracking (word problem over S5)
# ---------------------------------------------------------------------------


def permutation_tracking(depth: int, rng: random.Random, n_ops: int = 24, n_boxes: int = 5) -> TaskItem:
    """Track items through ``n_ops`` swap instructions, ``depth`` of them real.

    Identity operations are written as ``swap i i`` so every instruction has
    the same surface form and the prompt length is constant across depths.
    The word problem over S5 is the canonical state-tracking task that a
    fixed-depth transformer cannot solve for unbounded length (Merrill et al.).
    """
    if not 0 <= depth <= n_ops:
        raise ValueError(f"depth must be in [0, {n_ops}]")
    items = list(string.ascii_lowercase[:n_boxes])
    boxes = items[:]
    real_positions = set(rng.sample(range(n_ops), depth))
    ops = []
    for i in range(n_ops):
        if i in real_positions:
            a, b = rng.sample(range(1, n_boxes + 1), 2)
            boxes[a - 1], boxes[b - 1] = boxes[b - 1], boxes[a - 1]
        else:
            a = b = rng.randint(1, n_boxes)
        ops.append(f"swap {a} {b}")
    query = rng.randint(1, n_boxes)
    prompt = (
        f"There are {n_boxes} boxes numbered 1 to {n_boxes}. "
        f"They start holding the items {' '.join(items)} in that order.\n"
        "Apply these operations in order (swap i j exchanges the contents of boxes i and j):\n"
        + "\n".join(ops)
        + f"\nWhich item is in box {query} at the end?\n"
        + NO_COT_SUFFIX
    )
    return TaskItem("permutation", depth, prompt, boxes[query - 1], 1.0 / n_boxes, {"query": query})


# ---------------------------------------------------------------------------
# Parity of a prefix
# ---------------------------------------------------------------------------


def prefix_parity(depth: int, rng: random.Random, width: int = 32) -> TaskItem:
    """Parity of the first ``depth`` characters of a fixed-width bit string."""
    if not 1 <= depth <= width:
        raise ValueError(f"depth must be in [1, {width}]")
    bits = "".join(rng.choice("01") for _ in range(width))
    ones = bits[:depth].count("1")
    answer = "even" if ones % 2 == 0 else "odd"
    prompt = (
        f"Here is a string of {width} binary digits:\n{bits}\n"
        f"Consider only the first {depth:02d} digits. Is the number of 1s among them even or odd?\n"
        "Answer with the single word even or odd.\n" + NO_COT_SUFFIX
    )
    return TaskItem("parity", depth, prompt, answer, 0.5, {})


# ---------------------------------------------------------------------------
# Directed graph reachability with a controlled shortest path
# ---------------------------------------------------------------------------


def reachability(depth: int, rng: random.Random, n_nodes: int = 40, n_edges: int = 40) -> TaskItem:
    """Is there a directed path from s to t? Yes items have shortest path ``depth``.

    The graph always contains two disjoint chains of length ``depth`` plus
    random distractor edges among the remaining nodes, so the edge count and
    the prompt length are the same at every depth and for both answers.
    """
    if depth < 1 or 2 * (depth + 1) + 2 > n_nodes or 2 * depth > n_edges:
        raise ValueError("depth too large for the configured graph size")
    nodes = [f"v{i:02d}" for i in range(n_nodes)]
    rng.shuffle(nodes)
    chain_a = nodes[: depth + 1]
    chain_b = nodes[depth + 1 : 2 * (depth + 1)]
    rest = nodes[2 * (depth + 1) :]
    edges = [(chain_a[i], chain_a[i + 1]) for i in range(depth)]
    edges += [(chain_b[i], chain_b[i + 1]) for i in range(depth)]
    seen = set(edges)
    while len(edges) < n_edges:
        u, v = rng.sample(rest, 2)
        if (u, v) not in seen:
            seen.add((u, v))
            edges.append((u, v))
    rng.shuffle(edges)
    positive = rng.random() < 0.5
    source = chain_a[0]
    target = chain_a[-1] if positive else chain_b[-1]
    prompt = (
        "Here is a list of directed edges (u -> v means you can move from u to v):\n"
        + "\n".join(f"{u} -> {v}" for u, v in edges)
        + f"\nCan you reach {target} starting from {source} by following edges? Answer yes or no.\n"
        + NO_COT_SUFFIX
    )
    return TaskItem("reachability", depth, prompt, "yes" if positive else "no", 0.5, {"positive": positive})


GENERATORS: dict[str, Callable[..., TaskItem]] = {
    "pointer_chase": pointer_chase,
    "permutation": permutation_tracking,
    "parity": prefix_parity,
    "reachability": reachability,
}


def generate(task: str, depth: int, rng: random.Random) -> TaskItem:
    """Generate one item of ``task`` at ``depth``."""
    try:
        gen = GENERATORS[task]
    except KeyError as exc:
        raise ValueError(f"unknown task {task!r}; choose from {sorted(GENERATORS)}") from exc
    return gen(depth, rng)


def build_suite(tasks: list[str], depths: list[int], reps: int, seed: int = 0) -> list[TaskItem]:
    """Build a balanced suite: ``reps`` items per (task, depth), in shuffled order."""
    rng = random.Random(seed)
    items = [generate(t, d, rng) for t in tasks for d in depths for _ in range(reps)]
    rng.shuffle(items)
    return items
