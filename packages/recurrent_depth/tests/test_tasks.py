import random

import pytest

from recurrent_depth import tasks


@pytest.mark.parametrize(
    "task,depths",
    [
        ("pointer_chase", [1, 2, 4, 8, 12, 13]),
        ("permutation", [0, 1, 4, 8, 12, 24]),
        ("parity", [1, 2, 4, 8, 16, 32]),
        ("reachability", [1, 2, 4, 8, 12]),
    ],
)
def test_prompt_length_constant_across_depths(task, depths):
    rng = random.Random(1)
    lengths = {len(tasks.generate(task, d, rng).prompt) for d in depths for _ in range(5)}
    assert len(lengths) == 1, f"{task} prompt length varies with depth: {lengths}"


def _pointer_mapping(prompt):
    return dict(line.split("->") for line in prompt.splitlines() if "->" in line and len(line) == 4)


def _solve_pointer(prompt):
    mapping = _pointer_mapping(prompt)
    q = [line for line in prompt.splitlines() if line.startswith("Start at")][0]
    start = q.split()[2].rstrip(".")
    k = int(q.split("exactly ")[1].split()[0])
    node = start
    for _ in range(k):
        node = mapping[node]
    return node


def _solve_permutation(prompt):
    lines = prompt.splitlines()
    items = lines[0].split("holding the items ")[1].split(" in that order")[0].split()
    boxes = items[:]
    for line in lines:
        if line.startswith("swap "):
            a, b = int(line.split()[1]), int(line.split()[2])
            boxes[a - 1], boxes[b - 1] = boxes[b - 1], boxes[a - 1]
    q = int([line for line in lines if line.startswith("Which item")][0].split("box ")[1].split()[0])
    return boxes[q - 1]


def _solve_reach(prompt):
    edges = {}
    for line in prompt.splitlines():
        if " -> " in line and line.startswith("v"):
            u, v = line.split(" -> ")
            edges.setdefault(u, []).append(v)
    q = [line for line in prompt.splitlines() if line.startswith("Can you reach")][0]
    target = q.split()[3]
    source = q.split("starting from ")[1].split()[0]
    seen, frontier = {source}, [source]
    while frontier:
        nxt = []
        for u in frontier:
            for v in edges.get(u, []):
                if v not in seen:
                    seen.add(v)
                    nxt.append(v)
        frontier = nxt
    return "yes" if target in seen else "no"


def test_answers_match_independent_solvers():
    rng = random.Random(7)
    for d in (1, 3, 9, 13):
        item = tasks.pointer_chase(d, rng)
        assert _solve_pointer(item.prompt) == item.answer
    for d in (0, 2, 10, 24):
        item = tasks.permutation_tracking(d, rng)
        assert _solve_permutation(item.prompt) == item.answer
    for d in (1, 5, 12):
        for _ in range(4):
            item = tasks.reachability(d, rng)
            assert _solve_reach(item.prompt) == item.answer
    for d in (1, 7, 32):
        item = tasks.prefix_parity(d, rng)
        bits = item.prompt.splitlines()[1]
        assert ("even" if bits[:d].count("1") % 2 == 0 else "odd") == item.answer


def test_pointer_chase_mapping_is_a_single_cycle():
    rng = random.Random(3)
    item = tasks.pointer_chase(5, rng, n_nodes=26)
    mapping = _pointer_mapping(item.prompt)
    node, seen = "A", []
    for _ in range(26):
        seen.append(node)
        node = mapping[node]
    assert len(set(seen)) == 26 and node == "A"


def test_check_answer_normalization():
    item = tasks.TaskItem("t", 1, "p", "K", 0.1)
    assert tasks.check_answer(item, "K")
    assert tasks.check_answer(item, " **K**.")
    assert tasks.check_answer(item, "Answer: K")
    assert not tasks.check_answer(item, "J")
    assert not tasks.check_answer(item, "")
    assert not tasks.check_answer(item, "J or K")


def test_build_suite_balanced_and_deterministic():
    a = tasks.build_suite(["parity", "pointer_chase"], [1, 4], reps=3, seed=5)
    b = tasks.build_suite(["parity", "pointer_chase"], [1, 4], reps=3, seed=5)
    assert [x.prompt for x in a] == [x.prompt for x in b]
    assert len(a) == 12
    counts = {}
    for x in a:
        counts[(x.task, x.depth)] = counts.get((x.task, x.depth), 0) + 1
    assert set(counts.values()) == {3}


def test_invalid_depth_and_task():
    rng = random.Random(0)
    with pytest.raises(ValueError):
        tasks.pointer_chase(26, rng)
    with pytest.raises(ValueError, match="backward"):
        tasks.pointer_chase(14, rng)  # 14 forward on a 26-cycle is 12 back
    with pytest.raises(ValueError):
        tasks.reachability(30, rng)
    with pytest.raises(ValueError):
        tasks.generate("nope", 1, rng)


def _pointer_mapping_any(prompt):
    return dict(line.split("->") for line in prompt.splitlines() if "->" in line and " " not in line)


def _solve_pointer_any(prompt):
    mapping = _pointer_mapping_any(prompt)
    q = [line for line in prompt.splitlines() if line.startswith("Start at")][0]
    node = q.split()[2].rstrip(".")
    for _ in range(int(q.split("exactly ")[1].split()[0])):
        node = mapping[node]
    return node


@pytest.mark.parametrize(
    "task,depths,solver",
    [
        ("pointer_chase_long", [1, 4, 32, 64, 128], _solve_pointer_any),
        ("permutation_long", [0, 4, 32, 64, 128], _solve_permutation),
        ("reachability_long", [1, 4, 32, 64, 128], _solve_reach),
    ],
)
def test_long_generators_constant_length_and_correct(task, depths, solver):
    rng = random.Random(3)
    items = [tasks.generate(task, d, rng) for d in depths for _ in range(3)]
    assert len({len(i.prompt) for i in items}) == 1
    assert all(i.task == task for i in items)
    for item in items:
        assert solver(item.prompt) == item.answer


def test_pointer_chase_long_limits():
    rng = random.Random(0)
    assert len(_pointer_mapping_any(tasks.generate("pointer_chase_long", 4, rng).prompt)) == 256
    with pytest.raises(ValueError, match="backward"):
        tasks.generate("pointer_chase_long", 129, rng)
    with pytest.raises(ValueError):
        tasks.pointer_chase(4, rng, n_nodes=677)


def test_default_pointer_chase_prompt_unchanged():
    item = tasks.pointer_chase(3, random.Random(1))
    assert "Each line maps a letter to another letter." in item.prompt and "exactly 03 times" in item.prompt


def test_alias_answers():
    item = tasks.TaskItem("twohop", 2, "", "Motihari", 0.0, {"aliases": ["Motihari", "Motihari, Bihar"]})
    assert tasks.check_answer(item, "Motihari")
    assert tasks.check_answer(item, "The city of Motihari.")
    assert not tasks.check_answer(item, "Mumbai")
    assert not tasks.check_answer(item, "")
    long_tail = " ".join(["word"] * tasks.ALIAS_WINDOW) + " Motihari"
    assert not tasks.check_answer(item, long_tail)


def _solve_arith(prompt):
    lines = prompt.splitlines()
    x = int(lines[0].split("number ")[1].split(".")[0])
    for line in lines[1:]:
        parts = line.split()
        if line.startswith("add "):
            x += int(parts[1])
        elif line.startswith("subtract "):
            x -= int(parts[1])
        elif line.startswith("multiply by "):
            x *= int(parts[2])
    return str(x)


def test_arithmetic_chain_answers_and_line_count():
    rng = random.Random(4)
    for d in (0, 1, 5, 12):
        for _ in range(5):
            item = tasks.generate("arithmetic_chain", d, rng)
            assert _solve_arith(item.prompt) == item.answer
            ops = [ln for ln in item.prompt.splitlines() if ln.split()[0] in ("add", "subtract", "multiply")]
            assert len(ops) == 12 and sum(ln != "add 0" for ln in ops) == d
    with pytest.raises(ValueError):
        tasks.arithmetic_chain(13, rng)
    assert tasks.check_answer(tasks.TaskItem("arithmetic_chain", 1, "", "-12", 0.0), "-12")
