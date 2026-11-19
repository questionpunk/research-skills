#!/usr/bin/env python3
"""MaxDiff design: build or check a balanced MaxDiff (best-worst) design.

Generate:  python3 scripts/maxdiff_design.py items.txt --per-set 4 --versions 10 --seed 1 --out design.csv
           python3 scripts/maxdiff_design.py --items 12 --per-set 4 --respondents 300
Check:     python3 scripts/maxdiff_design.py --check design.csv [items.txt]

The design is written as long CSV with the columns version,set,position,item (--item-id adds item_id;
--wide writes version,set,item1..itemk instead). --check reads both layouts.
Standard library only, Python 3.9+. No network. The same arguments and seed always give the same design.
Exit codes: 0 = design meets the criteria, 1 = a criterion failed, 2 = bad input.
The rules and their sources are in references/sources.md.
"""
import argparse
import csv
import io
import itertools
import json
import math
import random
import re
import sys

CSV_COLUMNS = ["version", "set", "position", "item"]
# Sawtooth: enough sets that each item appears three to five times per respondent; minimum 3K/k.
DEFAULT_EXPOSURES = 3
MAX_USEFUL_EXPOSURES = 5
WARN_EXPOSURES = 2  # Sawtooth's software warns below two exposures per respondent.
DEFAULT_PER_SET = 4  # Sawtooth: four or five items per set.
MAX_PER_SET = 5  # Orme 2005, Chrzan & Patterson 2006: little gain above five.
MIN_PER_SET = 3  # Best and worst need at least three items to differ from a paired comparison.
MIN_ITEMS_DEFAULT_PER_SET = 6  # Below this the script will not pick the items per set by itself.
MANY_ITEMS = 30  # Above this, Sawtooth advises larger samples or a sparse design.
PAPER_MIN_VERSIONS = 4  # Sawtooth: at least four versions on paper.
DEFAULT_VERSIONS = 10  # Displayr: 10 versions are enough to average out order and context effects.
SAWTOOTH_DEFAULT_VERSIONS = 300
DISCOVER_WARN_PER_SET = 7  # Sawtooth Discover warns above seven items per task.
CORRELATION_LIMIT = 0.5  # Displayr: item correlations between -0.5 and 0.5 are no concern.
SPARSE_MIN_EXPOSURES = 500  # Sawtooth: each item seen at least 500 times by the group analysed,
SPARSE_GOOD_EXPOSURES = 1000  # and preferably 1000 times (sparse designs, pooled analysis).
SMALL_SAMPLE = 400  # Discover: samples of 50 to 400 need 3 or more exposures per respondent.
LARGE_SAMPLE = 600  # Discover: at 600 or more, 1 to 2 exposures per respondent are typically enough.
DISCOVER_MIN_SAMPLE = 50  # Discover's guidance starts at samples of 50.
TOTAL_SAMPLE = 300  # Sawtooth sample-size post: at least 300 respondents in total,
SUBGROUP_SAMPLE = 200  # and at least 200 in each subgroup reported separately,
SAMPLE_ITEMS_BASE = 30  # raised in proportion above about 30 items (doubled at 60).
DEFAULT_SECONDS_PER_SET = 20  # Assumption for the length estimate, not a sourced figure.
AFFINE_MAX_ORDER = 7  # Script choice: largest affine plane built (49 items, 56 sets of 7).
SET_ALIASES = ("set", "task", "question")
# A per-respondent export names the version column after the respondent; each respondent is one version.
VERSION_ALIASES = ("version", "respondent", "respondent_id", "respondentid", "resp_id")
WIDE_PREFIXES = ("item", "alt", "alternative", "option")
DEFAULT_RESTARTS = 10  # Script choice (Sawtooth's designer repeats 1000 times).
DIFFERENCE_SET_NODE_LIMIT = 200000  # Script choice: bound on the cyclic BIBD search.
COMPLETE_DESIGN_MAX_SETS = 50  # Script choice: longest "all subsets" design it will build.


class InputError(Exception):
    """Bad input: reported on stderr, exit code 2."""


class Rng:
    """Seeded generator built only on random.random(), whose sequence Python keeps stable across versions."""

    def __init__(self, seed):
        self._r = random.Random(int(seed))

    def random(self):
        return self._r.random()

    def below(self, n):
        return min(int(self._r.random() * n), n - 1)

    def shuffle(self, seq):
        for i in range(len(seq) - 1, 0, -1):
            j = self.below(i + 1)
            seq[i], seq[j] = seq[j], seq[i]
        return seq


# ---------------------------------------------------------------- input


def read_items(path):
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            lines = [line.strip() for line in fh.read().splitlines()]
    except OSError as exc:
        raise InputError(f"cannot read items file {path}: {exc.strerror}")
    except UnicodeDecodeError:
        raise InputError(f"items file {path} is not UTF-8 text")
    items = [line for line in lines if line]
    if not items:
        raise InputError(f"items file {path} has no items (expected one item per line)")
    seen = {}
    for number, item in enumerate(items, 1):
        key = item.casefold()
        if key in seen:
            raise InputError(f"items file {path}: item {number} repeats item {seen[key]} ({item!r})")
        seen[key] = number
    return items


def _sniff_delimiter(first_line):
    """The delimiter among comma, semicolon and tab that splits the header into the most fields."""
    counts = {d: len(next(csv.reader([first_line], delimiter=d))) for d in (",", ";", "\t")}
    best = max(counts.values())
    return "," if counts[","] == best else max(counts, key=counts.get)


def read_design(path, delimiter=None):
    """Read a design CSV. Returns (rows, layout); rows are (version, set, position, item).

    Long layout: version,set,position,item. Wide layout: version,set,item1..itemk (as Sawtooth and
    Displayr export it; the set column may be called task or question, the item columns alt1.., option1..).
    In the wide layout the number in the column name is the position; empty trailing columns pad a short set.
    Without a version column every row belongs to version 1; a respondent column (respondent, respondent_id,
    resp_id) is read as the version, one per respondent. The delimiter (comma, semicolon or tab) is read from
    the header unless given; an Excel "sep=;" first line sets it and is skipped.
    """
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            text = fh.read()
    except OSError as exc:
        raise InputError(f"cannot read design file {path}: {exc.strerror}")
    except UnicodeDecodeError:
        raise InputError(f"design file {path} is not UTF-8 text")
    if not text.strip():
        raise InputError(f"design file {path} is empty")
    first, _newline, rest = text.partition("\n")
    sep = re.fullmatch(r"\s*sep=(.)\s*", first)
    if sep:
        text = rest
        delimiter = delimiter or sep.group(1)
    if delimiter is None:
        delimiter = _sniff_delimiter(text.splitlines()[0])
    try:
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
        raw_header = next(reader)
        header = [(name or "").strip().lower() for name in raw_header]
        duplicates = sorted({name for name in header if name and header.count(name) > 1})
        if duplicates:
            raise InputError(f"design file {path}: duplicate column name(s) {', '.join(duplicates)} "
                             "(names are compared ignoring case and spaces)")
        column = {name: i for i, name in enumerate(header) if name}
        set_column = next((alias for alias in SET_ALIASES if alias in column), None)
        version_column = next((alias for alias in VERSION_ALIASES if alias in column), None)
        wide = []
        for name in header:
            match = re.fullmatch(r"(%s)[ _]?(\d+)" % "|".join(WIDE_PREFIXES), name)
            if match:
                wide.append((int(match.group(2)), name))
        wide.sort()
        slots = [number for number, _name in wide]
        if len(set(slots)) != len(slots):
            repeated = sorted({n for n in slots if slots.count(n) > 1})
            raise InputError(f"design file {path}: more than one item column for position(s) "
                             + ", ".join(str(n) for n in repeated))
        long_layout = "position" in column and "item" in column
        if set_column is None or not (long_layout or wide):
            raise InputError(
                f"design file {path} is not a design: expected the header {','.join(CSV_COLUMNS)} "
                "or the wide form version,set,item1,item2,... (comma, semicolon or tab separated; "
                "pass --delimiter if it is another character)"
            )
        layout = "long" if long_layout else "wide"

        def whole(text, name, line):
            try:
                number = int(text)
            except ValueError:
                raise InputError(f"design file {path} line {line}: {name} {text!r} is not a whole number")
            if number < 1:
                raise InputError(f"design file {path} line {line}: {name} must be 1 or more")
            return number

        rows = []
        wide_seen = {}
        for line, raw in enumerate(reader, 2):
            cell = lambda name: (raw[column[name]] if column[name] < len(raw) else "").strip()
            if not any(value.strip() for value in raw):
                continue
            version = whole(cell(version_column), version_column, line) if version_column else 1
            set_number = whole(cell(set_column), set_column, line)
            if long_layout:
                position = whole(cell("position"), "position", line)
                if not cell("item"):
                    raise InputError(f"design file {path} line {line}: item is empty")
                rows.append((version, set_number, position, cell("item")))
            else:
                # The column number is the position: an empty column before a filled one leaves a gap,
                # which the shape criterion reports, instead of moving later items forward.
                if (version, set_number) in wide_seen:
                    raise InputError(
                        f"design file {path} line {line}: set {set_number} appears more than once in version {version} "
                        f"(first on line {wide_seen[(version, set_number)]}); if each row is one respondent's set, "
                        "name the respondent column version or respondent")
                wide_seen[(version, set_number)] = line
                shown = [(number, cell(name)) for number, name in wide if cell(name)]
                if not shown:
                    raise InputError(f"design file {path} line {line}: the set has no items")
                for position, item in shown:
                    rows.append((version, set_number, position, item))
    except csv.Error as exc:
        raise InputError(f"design file {path} is not valid CSV: {exc}")
    if not rows:
        raise InputError(f"design file {path} has a header but no rows")
    return rows, layout


def ids_to_labels(rows, items, path):
    """When every item cell is a number and an items file is given, read the numbers as 1-based item ids."""
    if items is None or not all(row[3].isascii() and row[3].isdigit() for row in rows):
        return rows, False
    if all(row[3] in set(items) for row in rows):
        return rows, False
    for row in rows:
        if not 1 <= int(row[3]) <= len(items):
            raise InputError(f"design file {path}: item id {row[3]} is outside 1..{len(items)} (the items file has {len(items)} items)")
    return [(v, st, pos, items[int(item) - 1]) for v, st, pos, item in rows], True


# ---------------------------------------------------------------- recommendation


def recommended_sets(n_items, per_set, exposures=DEFAULT_EXPOSURES):
    """Sawtooth's minimum: sets = exposures * K / k, rounded up (3K/k by default)."""
    return math.ceil(exposures * n_items / per_set)


def default_per_set(n_items):
    if n_items < MIN_ITEMS_DEFAULT_PER_SET:
        raise InputError(
            f"with {n_items} items give --per-set yourself: under {MIN_ITEMS_DEFAULT_PER_SET} items even "
            f"{MIN_PER_SET} per set is more than half the list, and a ranking question may serve better"
        )
    # Four per set, unless that is more than half the items.
    return DEFAULT_PER_SET if DEFAULT_PER_SET * 2 <= n_items else MIN_PER_SET


# ---------------------------------------------------------------- exact constructions


def find_difference_set(v, k):
    """Smallest cyclic (v, k, lambda) difference set containing 0, or None. Bounded depth-first search."""
    if k < 2 or k >= v or (k * (k - 1)) % (v - 1):
        return None
    lam = k * (k - 1) // (v - 1)
    counts = [0] * v
    chosen = [0]
    nodes = [0]

    def extend(start):
        if len(chosen) == k:
            return True
        for candidate in range(start, v):
            nodes[0] += 1
            if nodes[0] > DIFFERENCE_SET_NODE_LIMIT:
                return False
            added = []
            ok = True
            for member in chosen:
                for diff in ((candidate - member) % v, (member - candidate) % v):
                    counts[diff] += 1
                    added.append(diff)
                    if counts[diff] > lam:
                        ok = False
            if ok:
                chosen.append(candidate)
                if extend(candidate + 1):
                    return True
                chosen.pop()
            for diff in added:
                counts[diff] -= 1
            if nodes[0] > DIFFERENCE_SET_NODE_LIMIT:
                return False
        return False

    return list(chosen) if extend(1) else None


def exact_construction(n_items, per_set, n_sets):
    """Return (method, base) when a simple exact BIBD has exactly n_sets sets, else None."""
    if n_sets == n_items:
        base = find_difference_set(n_items, per_set)
        if base:
            return "cyclic", base
    if affine_order(n_items, per_set) and n_sets == n_items + per_set:
        return "affine", per_set
    if n_sets <= COMPLETE_DESIGN_MAX_SETS and n_sets == math.comb(n_items, per_set):
        return "complete", None
    return None


def affine_order(n_items, per_set):
    """q when the items and set size fit the affine plane of prime order q (q*q items, q per set), else 0."""
    q = per_set
    prime = q >= 2 and all(q % d for d in range(2, int(q ** 0.5) + 1))
    return q if prime and q <= AFFINE_MAX_ORDER and n_items == q * q else 0


def affine_plane_sets(q):
    """The q*q + q lines of the affine plane over the integers mod a prime q. Point (x, y) is item x*q + y.

    Lines y = m*x + c (q*q of them) and x = c (q of them). Two points lie on exactly one line, so every
    pair of items shares exactly one set: a BIBD with r = q + 1 and lambda = 1.
    """
    sets = [{x * q + (m * x + c) % q for x in range(q)} for m in range(q) for c in range(q)]
    sets += [{c * q + y for y in range(q)} for c in range(q)]
    return sets


# ---------------------------------------------------------------- randomized search


def _pair_matrix(n_items, sets):
    matrix = [[0] * n_items for _ in range(n_items)]
    for members in sets:
        for a, b in itertools.combinations(sorted(members), 2):
            matrix[a][b] += 1
            matrix[b][a] += 1
    return matrix


def _components(n_items, sets):
    parent = list(range(n_items))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for members in sets:
        members = list(members)
        for other in members[1:]:
            ra, rb = find(members[0]), find(other)
            if ra != rb:
                parent[ra] = rb
    return len({find(i) for i in range(n_items)})


def _greedy_sets(n_items, per_set, n_sets, quota, cum_pair, rng):
    """Deal items into sets: largest remaining quota first, then the item that adds least pair imbalance."""
    remaining = list(quota)
    pair = [[0] * n_items for _ in range(n_items)]
    sets = []
    for _ in range(n_sets):
        chosen = []
        for _slot in range(per_set):
            best, best_key = None, None
            for item in range(n_items):
                if remaining[item] <= 0 or item in chosen:
                    continue
                within = sum(2 * pair[item][other] + 1 for other in chosen)
                overall = sum(2 * (pair[item][other] + cum_pair[item][other]) + 1 for other in chosen)
                key = (-remaining[item], within, overall, rng.random())
                if best_key is None or key < best_key:
                    best, best_key = item, key
            for other in chosen:
                pair[best][other] += 1
                pair[other][best] += 1
            chosen.append(best)
            remaining[best] -= 1
        sets.append(set(chosen))
    return sets, pair


def _swap_delta(pair, cum_pair, set_a, set_b, a, b):
    """Change in (within-version, cumulative) sums of squared pair counts if a (in A) and b (in B) trade places."""
    change = {}
    for x in set_a:
        if x != a:
            change[(a, x)] = change.get((a, x), 0) - 1
            change[(b, x)] = change.get((b, x), 0) + 1
    for x in set_b:
        if x != b:
            change[(b, x)] = change.get((b, x), 0) - 1
            change[(a, x)] = change.get((a, x), 0) + 1
    within = overall = 0
    for (p, q), c in change.items():
        if c:
            now = pair[p][q]
            within += (now + c) ** 2 - now ** 2
            total = now + cum_pair[p][q]
            overall += (total + c) ** 2 - total ** 2
    return within, overall, change


def _improve_sets(sets, pair, cum_pair, rng, max_passes=12):
    """Trade items between sets while that lowers pair imbalance. Item frequencies do not change."""
    order = list(range(len(sets)))
    for _ in range(max_passes):
        improved = False
        rng.shuffle(order)
        for ia in range(len(order)):
            for ib in range(ia + 1, len(order)):
                set_a, set_b = sets[order[ia]], sets[order[ib]]
                found = True
                while found:
                    found = False
                    for a in sorted(set_a - set_b):
                        for b in sorted(set_b - set_a):
                            within, overall, change = _swap_delta(pair, cum_pair, set_a, set_b, a, b)
                            if (within, overall) < (0, 0):
                                for (p, q), c in change.items():
                                    pair[p][q] += c
                                    pair[q][p] += c
                                set_a.remove(a)
                                set_a.add(b)
                                set_b.remove(b)
                                set_b.add(a)
                                found = improved = True
                                break
                        if found:
                            break
        if not improved:
            break


def _repeated_sets(sets):
    return len(sets) - len({frozenset(members) for members in sets})


def _remove_repeated_sets(sets, pair, cum_pair):
    """Trade one item between a repeated set and another set until no set of the version repeats.

    Each step takes the trade that leaves every set distinct at the smallest cost in pair imbalance; item
    frequencies do not change. Stops when no trade can remove a repeat.
    """
    for _ in range(len(sets) * len(sets)):
        seen, repeat = set(), None
        for index, members in enumerate(sets):
            key = frozenset(members)
            if key in seen:
                repeat = index
                break
            seen.add(key)
        if repeat is None:
            return
        set_a = sets[repeat]
        others = {}
        for index, members in enumerate(sets):
            if index != repeat:
                key = frozenset(members)
                others[key] = others.get(key, 0) + 1
        best = None
        for ib, set_b in enumerate(sets):
            if ib == repeat:
                continue
            for a in sorted(set_a - set_b):
                for b in sorted(set_b - set_a):
                    new_a = frozenset(set_a - {a} | {b})
                    new_b = frozenset(set_b - {b} | {a})
                    remaining = dict(others)
                    remaining[frozenset(set_b)] -= 1
                    if remaining.get(new_a) or remaining.get(new_b) or new_a == new_b:
                        continue
                    within, overall, change = _swap_delta(pair, cum_pair, set_a, set_b, a, b)
                    key = (within, overall, ib, a, b)
                    if best is None or key < best[0]:
                        best = (key, set_b, a, b, change)
        if best is None:
            return
        _key, set_b, a, b, change = best
        for (p, q), c in change.items():
            pair[p][q] += c
            pair[q][p] += c
        set_a.remove(a)
        set_a.add(b)
        set_b.remove(b)
        set_b.add(a)


def _search_version(n_items, per_set, n_sets, cum_item, cum_pair, rng, restarts):
    slots = n_sets * per_set
    base, extra = divmod(slots, n_items)
    # The items that appear one more time are the ones shown least so far, so versions even out.
    order = sorted(range(n_items), key=lambda i: (cum_item[i], rng.random()))
    quota = [base] * n_items
    for item in order[:extra]:
        quota[item] += 1
    best, best_key = None, None
    for _ in range(restarts):
        sets, pair = _greedy_sets(n_items, per_set, n_sets, quota, cum_pair, rng)
        _improve_sets(sets, pair, cum_pair, rng)
        _remove_repeated_sets(sets, pair, cum_pair)
        within = sum(pair[a][b] ** 2 for a in range(n_items) for b in range(a + 1, n_items))
        overall = sum((pair[a][b] + cum_pair[a][b]) ** 2 for a in range(n_items) for b in range(a + 1, n_items))
        # A version that shows the same set twice ranks below any version without repeats.
        key = (_components(n_items, sets), _repeated_sets(sets), within, overall)
        if best_key is None or key < best_key:
            best, best_key = sets, key
    return best


def _order_sets(sets, rng):
    """Order the sets so consecutive sets share as few items as possible."""
    pending = list(sets)
    rng.shuffle(pending)
    ordered = [pending.pop()]
    while pending:
        scored = [(len(ordered[-1] & candidate), rng.random(), index) for index, candidate in enumerate(pending)]
        ordered.append(pending.pop(min(scored)[2]))
    return ordered


def _assign_positions(sets, n_items, per_set, cum_pos, rng, max_passes=60):
    """Order the items inside each set so every item sits in every position about equally often."""
    orders = [rng.shuffle(sorted(members)) for members in sets]
    pos = [[0] * per_set for _ in range(n_items)]
    for members in orders:
        for p, item in enumerate(members):
            pos[item][p] += 1

    def delta(x, y, p, q):
        within = overall = 0
        for item, src, dst in ((x, p, q), (y, q, p)):
            for cell, c in ((src, -1), (dst, 1)):
                now = pos[item][cell]
                within += (now + c) ** 2 - now ** 2
                total = now + cum_pos[item][cell]
                overall += (total + c) ** 2 - total ** 2
        return within, overall

    for _ in range(max_passes):
        improved = False
        for members in orders:
            for p in range(per_set):
                for q in range(p + 1, per_set):
                    x, y = members[p], members[q]
                    change = delta(x, y, p, q)
                    # Take every improvement, and sideways moves half the time to leave plateaus.
                    if change < (0, 0) or (change == (0, 0) and rng.random() < 0.5):
                        members[p], members[q] = y, x
                        pos[x][p] -= 1
                        pos[x][q] += 1
                        pos[y][q] -= 1
                        pos[y][p] += 1
                        improved = improved or change < (0, 0)
        if not improved and all(
            max(a + b for a, b in zip(pos[i], cum_pos[i])) - min(a + b for a, b in zip(pos[i], cum_pos[i])) <= 1
            for i in range(n_items)
        ):
            break
    return orders


def _repair_positions(orders, n_items, per_set):
    """Finish positional balance over the whole design: no item ends more than 1 apart between two positions.

    For an item used at least 2 more often in position p than in q, follow a trail of sets (item in p -> the
    item in q of the same set -> a set with that item in p ...) until it reaches an item that is short in p,
    then swap p and q in every set of the trail. Items inside the trail keep their counts, the first item
    loses one p and the last gains one, so the imbalance strictly falls and the loop ends.
    """
    pos = [[0] * per_set for _ in range(n_items)]
    for members in orders:
        for p, item in enumerate(members):
            pos[item][p] += 1
    while True:
        target = None
        for item in range(n_items):
            high = max(range(per_set), key=lambda c: (pos[item][c], -c))
            low = min(range(per_set), key=lambda c: (pos[item][c], c))
            if pos[item][high] - pos[item][low] >= 2:
                target = (item, high, low)
                break
        if target is None:
            return
        start, p, q = target
        at_p = {}
        for number, members in enumerate(orders):
            at_p.setdefault(members[p], []).append(number)
        trail, current = [], start
        while True:
            number = at_p[current].pop()
            trail.append(number)
            current = orders[number][q]
            if pos[current][p] - pos[current][q] <= -1:
                break
        for number in trail:
            members = orders[number]
            x, y = members[p], members[q]
            members[p], members[q] = y, x
            pos[x][p] -= 1
            pos[x][q] += 1
            pos[y][q] -= 1
            pos[y][p] += 1


def generate(items, per_set, n_sets, versions, seed, restarts=DEFAULT_RESTARTS):
    """Return (rows, method, detail). rows are (version, set, position, item label)."""
    n_items = len(items)
    exact = exact_construction(n_items, per_set, n_sets)
    cum_item = [0] * n_items
    cum_pair = [[0] * n_items for _ in range(n_items)]
    cum_pos = [[0] * per_set for _ in range(n_items)]
    rows = []
    all_orders = []
    for version in range(1, versions + 1):
        rng = Rng(int(seed) * 1000003 + version)
        if exact and exact[0] == "cyclic":
            relabel = rng.shuffle(list(range(n_items)))
            # Developing the base block keeps each item once in every position.
            blocks = [[relabel[(d + shift) % n_items] for d in exact[1]] for shift in range(n_items)]
            by_members = {frozenset(block): block for block in blocks}
            orders = [by_members[frozenset(s)] for s in _order_sets([set(b) for b in blocks], rng)]
        else:
            if exact and exact[0] == "affine":
                relabel = rng.shuffle(list(range(n_items)))
                sets = [{relabel[i] for i in line} for line in affine_plane_sets(exact[1])]
            elif exact:
                sets = [set(c) for c in itertools.combinations(range(n_items), per_set)]
            else:
                sets = _search_version(n_items, per_set, n_sets, cum_item, cum_pair, rng, restarts)
            orders = _assign_positions(_order_sets(sets, rng), n_items, per_set, cum_pos, rng)
        for members in orders:
            for a, b in itertools.combinations(members, 2):
                cum_pair[a][b] += 1
                cum_pair[b][a] += 1
            for position, item in enumerate(members):
                cum_item[item] += 1
                cum_pos[item][position] += 1
        all_orders.append(orders)
    if not (exact and exact[0] == "cyclic"):
        _repair_positions([members for orders in all_orders for members in orders], n_items, per_set)
    for version, orders in enumerate(all_orders, 1):
        for set_number, members in enumerate(orders, 1):
            for position, item in enumerate(members, 1):
                rows.append((version, set_number, position, items[item]))
    if exact and exact[0] == "cyclic":
        lam = per_set * (per_set - 1) // (n_items - 1)
        base = ",".join(str(d) for d in exact[1])
        return rows, "cyclic-bibd", (
            f"exact BIBD from the cyclic difference set {{{base}}} mod {n_items} "
            f"(lambda = {lam}); items relabelled at random in each version"
        )
    if exact and exact[0] == "affine":
        return rows, "affine-bibd", (
            f"exact BIBD: the {n_sets} lines of the affine plane of order {per_set} "
            f"(each item {per_set + 1} times, lambda = 1); items relabelled at random in each version"
        )
    if exact:
        return rows, "complete-bibd", f"exact BIBD: all {n_sets} subsets of {per_set} items from {n_items}"
    return rows, "randomized-search", (
        f"seeded randomized search ({restarts} restarts per version): item frequencies fixed within 1, "
        "then swaps that lower pair imbalance"
    )


def bibd_conditions(n_items, per_set, n_sets):
    """(r, lambda) when the counting conditions for a BIBD hold (bk = vr, lambda(v-1) = r(k-1), b >= v), else None.

    The conditions are necessary, not sufficient: when they hold a BIBD may or may not exist.
    """
    if not 2 <= per_set < n_items or (n_sets * per_set) % n_items:
        return None
    r = n_sets * per_set // n_items
    if (r * (per_set - 1)) % (n_items - 1) or n_sets < n_items:
        return None
    return r, r * (per_set - 1) // (n_items - 1)


def search_outcome(n_items, per_set, n_sets, found_exact):
    """What the randomized search result says about exact designs, from its own diagnostics."""
    if found_exact:
        return "; every version came out as an exact BIBD (pair counts all equal)"
    conditions = bibd_conditions(n_items, per_set, n_sets)
    if conditions is None:
        return "; no BIBD has these parameters (the counting conditions bk = vr and lambda(v-1) = r(k-1) fail)"
    return (f"; the counting conditions for a BIBD hold (r = {conditions[0]}, lambda = {conditions[1]}) but the "
            "search did not find one: that is not proof none exists (a published construction, such as a Steiner "
            "triple system for k = 3, may give one)")


# ---------------------------------------------------------------- diagnostics


def _criterion(name, status, detail):
    return {"name": name, "status": status, "detail": detail}


def diagnose(rows, items=None, respondents=None):
    """Diagnostics and criteria for a design given as (version, set, position, item) rows."""
    by_version = {}
    for version, set_number, position, item in rows:
        by_version.setdefault(version, {}).setdefault(set_number, []).append((position, item))
    seen_order = list(dict.fromkeys(item for _v, _s, _p, item in rows))
    unknown = []
    if items is None:
        items = seen_order
    else:
        known = set(items)
        unknown = [item for item in seen_order if item not in known]
        items = list(items) + unknown
    index = {item: i for i, item in enumerate(items)}
    n_items = len(items)

    set_sizes, sets_per_version = {}, {}
    repeats = bad_positions = 0
    for version, sets in by_version.items():
        sets_per_version[len(sets)] = sets_per_version.get(len(sets), 0) + 1
        for cells in sets.values():
            set_sizes[len(cells)] = set_sizes.get(len(cells), 0) + 1
            repeats += len(cells) - len({item for _p, item in cells})
            if sorted(p for p, _item in cells) != list(range(1, len(cells) + 1)):
                bad_positions += 1
    per_set = max(set_sizes, key=lambda size: (set_sizes[size], size))
    n_sets = max(sets_per_version, key=lambda count: (sets_per_version[count], count))
    n_versions = len(by_version)

    item_total = [0] * n_items
    pair_total = [[0] * n_items for _ in range(n_items)]
    pos_total = [[0] * per_set for _ in range(n_items)]
    worst_item_range = worst_pair_range = 0
    connected_versions = 0
    all_sets = []
    every_version_bibd = True
    adjacent_repeats = adjacent_gaps = 0
    missing_by_version = {}
    repeated_sets = 0
    worst_version_spread = 0
    for version in sorted(by_version):
        item_v = [0] * n_items
        pos_v = [[0] * per_set for _ in range(n_items)]
        version_sets = []
        previous = None
        for set_number in sorted(by_version[version]):
            cells = sorted(by_version[version][set_number])
            members = {index[item] for _p, item in cells}
            version_sets.append(members)
            for slot, (_position, item) in enumerate(cells):
                item_v[index[item]] += 1
                if slot < per_set:
                    pos_total[index[item]][slot] += 1
                    pos_v[index[item]][slot] += 1
            if previous is not None:
                adjacent_repeats += len(previous & members)
                adjacent_gaps += 1
            previous = members
        repeated_sets += len(version_sets) - len({frozenset(members) for members in version_sets})
        worst_version_spread = max(worst_version_spread, max(max(row) - min(row) for row in pos_v if any(row)))
        missing = sum(1 for count in item_v if count == 0)
        if missing:
            missing_by_version[version] = missing
        pair_v = _pair_matrix(n_items, version_sets)
        pair_values = [pair_v[a][b] for a in range(n_items) for b in range(a + 1, n_items)]
        item_range = max(item_v) - min(item_v)
        pair_range = max(pair_values) - min(pair_values) if pair_values else 0
        worst_item_range = max(worst_item_range, item_range)
        worst_pair_range = max(worst_pair_range, pair_range)
        if item_range or pair_range or (pair_values and pair_values[0] == 0):
            every_version_bibd = False
        if _components(n_items, version_sets) == 1:
            connected_versions += 1
        for i in range(n_items):
            item_total[i] += item_v[i]
            for j in range(n_items):
                pair_total[i][j] += pair_v[i][j]
        all_sets.extend(version_sets)

    pair_values = [pair_total[a][b] for a in range(n_items) for b in range(a + 1, n_items)]
    pair_mean = sum(pair_values) / len(pair_values) if pair_values else 0.0
    pair_sd = math.sqrt(sum((v - pair_mean) ** 2 for v in pair_values) / len(pair_values)) if pair_values else 0.0
    never = sum(1 for v in pair_values if v == 0)
    item_range = max(item_total) - min(item_total)
    pair_range = max(pair_values) - min(pair_values) if pair_values else 0
    spreads = [max(row) - min(row) for row in pos_total]
    components = _components(n_items, all_sets)
    # Correlation between the 0/1 "item is in this set" indicators of two items, over every set.
    n_all = len(all_sets)
    shown_in = [sum(1 for members in all_sets if i in members) for i in range(n_items)]
    correlations = []
    undefined = 0
    for a in range(n_items):
        for b in range(a + 1, n_items):
            spread = shown_in[a] * (n_all - shown_in[a]) * shown_in[b] * (n_all - shown_in[b])
            if spread == 0:
                undefined += 1
                continue
            together = pair_total[a][b]
            correlations.append((n_all * together - shown_in[a] * shown_in[b]) / math.sqrt(spread))
    corr_min = round(min(correlations), 4) if correlations else None
    corr_max = round(max(correlations), 4) if correlations else None
    structure_ok = len(set_sizes) == 1 and len(sets_per_version) == 1 and bad_positions == 0 and repeats == 0
    exposures = sum(item_total) / n_items / n_versions
    smallest_set = min(len({item for _p, item in cells}) for sets in by_version.values() for cells in sets.values())
    largest_set = max(len({item for _p, item in cells}) for sets in by_version.values() for cells in sets.values())
    # A balanced incomplete block design needs 2 <= k < v: a set of one item has no choice, and a set holding
    # every item is a complete block (it identifies only the overall best and worst).
    is_bibd = structure_ok and every_version_bibd and not unknown and 2 <= per_set < n_items

    criteria = []
    choice_problems = []
    if smallest_set < 2:
        choice_problems.append("a set shows fewer than 2 different items, so there is nothing to choose between")
    elif largest_set >= n_items:
        choice_problems.append(f"a set shows all {n_items} items, so it identifies only the overall best and worst "
                               "and the design is not an incomplete (MaxDiff) design")
    criteria.append(_criterion(
        "each set offers a choice", "fail" if choice_problems else "pass",
        "; ".join(choice_problems) if choice_problems
        else f"every set shows {smallest_set} to {largest_set} different items, fewer than the {n_items} in the list"))
    criteria.append(_criterion(
        "no item repeated within a set", "fail" if repeats else "pass",
        f"{repeats} repeated item(s) inside sets" if repeats else "no set shows an item twice"))
    shape_problems = []
    if len(set_sizes) > 1:
        shape_problems.append("set sizes differ (" + ", ".join(f"{n} sets of {s}" for s, n in sorted(set_sizes.items())) + ")")
    if len(sets_per_version) > 1:
        shape_problems.append("versions have different numbers of sets")
    if bad_positions:
        shape_problems.append(f"{bad_positions} set(s) whose positions are not 1..n without gaps or repeats")
    if unknown:
        shape_problems.append(f"{len(unknown)} item(s) not in the items file: " + ", ".join(unknown[:5]))
    criteria.append(_criterion(
        "same shape in every set and version", "fail" if shape_problems else "pass",
        "; ".join(shape_problems) if shape_problems else f"{n_versions} version(s) x {n_sets} sets x {per_set} items"))
    criteria.append(_criterion(
        "one-way balance within each version", "pass" if worst_item_range <= 1 else "fail",
        f"item frequencies differ by at most {worst_item_range} inside a version (criterion: 1 or less)"))
    criteria.append(_criterion(
        "one-way balance overall", "pass" if item_range <= 1 else ("fail" if n_versions == 1 else "warn"),
        f"item frequencies run from {min(item_total)} to {max(item_total)} over all versions (criterion: within 1)"))
    if not pair_values:
        pair_detail = "not defined: the design has fewer than 2 items"
    elif is_bibd and pair_range == 0:
        pair_detail = f"exact: every pair appears together {pair_values[0] // n_versions if pair_values else 0} time(s) in each version"
    else:
        pair_detail = (f"pair counts differ by at most {worst_pair_range} inside a version (criterion: 1 or less); "
                       f"overall min {min(pair_values)}, max {max(pair_values)}, mean {pair_mean:.2f}")
        if worst_pair_range == 2:
            pair_detail += "; some item and set counts allow nothing better than 2: try another seed or number of sets"
    criteria.append(_criterion("two-way balance within each version", "pass" if worst_pair_range <= 1 else "warn", pair_detail))
    criteria.append(_criterion(
        "every pair of items appears together", "pass" if never == 0 else "warn",
        "all pairs meet at least once over the whole design" if never == 0
        else f"{never} of {len(pair_values)} pairs never share a set; they are compared only through other items"))
    criteria.append(_criterion(
        "positional balance", "pass" if max(spreads) <= 1 else "warn",
        f"largest gap between an item's most and least used position: {max(spreads)} (criterion: 1 or less); "
        f"largest gap inside one version: {worst_version_spread}"))
    if components > 1:
        connectivity = _criterion("connectivity", "fail",
                                  f"the items split into {components} groups that are never compared; scores cannot share one scale")
    elif connected_versions < n_versions:
        connectivity = _criterion(
            "connectivity", "warn",
            f"connected overall, but only {connected_versions} of {n_versions} versions are connected on their own; "
            "use pooled (aggregate or latent class) scores, not individual-level ones")
    else:
        connectivity = _criterion("connectivity", "pass", f"all {n_versions} version(s) connected")
    criteria.append(connectivity)
    if exposures >= DEFAULT_EXPOSURES:
        exposure = _criterion("times each item is shown per respondent", "pass",
                              f"{exposures:.2f} (criterion: {DEFAULT_EXPOSURES} or more for individual-level scores)")
    else:
        if respondents is not None and respondents >= LARGE_SAMPLE and exposures >= 1:
            exposure = _criterion(
                "times each item is shown per respondent", "pass",
                f"{exposures:.2f}: under 3, but with {respondents} respondents (600 or more) 1 to 2 exposures are "
                "typically enough (Sawtooth Discover); individual-level scores lean on the pooled data")
        else:
            note = ("under 2, where Sawtooth's tools warn: plan pooled (aggregate or latent class) scores or a "
                    "sample of 600 or more" if exposures < WARN_EXPOSURES
                    else "under 3: individual-level scores will be less precise unless the sample is 600 or more")
            exposure = _criterion("times each item is shown per respondent", "warn",
                                  f"{exposures:.2f}, {note}; {recommended_sets(n_items, per_set)} sets would give 3")
    criteria.append(exposure)
    size_notes = []
    if per_set * 2 > n_items:
        size_notes.append(f"{per_set} per set is more than half of {n_items} items")
    if per_set > MAX_PER_SET:
        size_notes.append(
            f"more than {MAX_PER_SET} per set adds fatigue for little precision (Lighthouse advises 4 or 5, Discover 3 to 5"
            + (f"; Discover warns above {DISCOVER_WARN_PER_SET})" if per_set > DISCOVER_WARN_PER_SET else ")"))
    if per_set < MIN_PER_SET:
        size_notes.insert(0, f"{per_set} per set is under the minimum of {MIN_PER_SET}: with two items the best and "
                             "worst choice are the same choice (a paired comparison, not MaxDiff)")
    criteria.append(_criterion("items per set",
                               "fail" if per_set < MIN_PER_SET else ("warn" if size_notes else "pass"),
                               "; ".join(size_notes) if size_notes else f"{per_set} per set, at most half of {n_items} items"))
    possible_sets = math.comb(n_items, per_set) if per_set <= n_items else 0
    if repeated_sets and n_sets <= possible_sets:
        criteria.append(_criterion(
            "no set repeated within a version", "warn",
            f"{repeated_sets} set(s) repeat an earlier set of the same version: the respondent sees the same items "
            "together twice; regenerate with another seed or fewer sets"))
    else:
        criteria.append(_criterion(
            "no set repeated within a version", "pass",
            "every set of a version is different" if not repeated_sets
            else f"{repeated_sets} repeated set(s), unavoidable: only {possible_sets} different sets of {per_set} exist"))

    if missing_by_version:
        worst = max(missing_by_version.values())
        criteria.append(_criterion(
            "every item in every version", "warn",
            f"{len(missing_by_version)} of {n_versions} version(s) leave out up to {worst} item(s); a respondent "
            "gives no information on items they never see, so only pooled (aggregate or latent class) scores "
            "cover every item"))
    else:
        criteria.append(_criterion("every item in every version", "pass", "each version shows every item"))
    if correlations and (corr_min < -CORRELATION_LIMIT or corr_max > CORRELATION_LIMIT):
        detail = f"item correlations run from {corr_min:.2f} to {corr_max:.2f}; outside -0.5..0.5 two items are confounded"
        if corr_min <= -1 + 1e-9:
            detail += "; -1.00 means two items split the sets between them and never meet"
        if corr_max >= 1 - 1e-9:
            detail += "; 1.00 means two items are always shown together and never apart"
        criteria.append(_criterion("item correlations", "warn", detail))
    else:
        criteria.append(_criterion(
            "item correlations", "pass",
            f"from {corr_min:.2f} to {corr_max:.2f} (criterion: within -0.5..0.5)" if correlations
            else "not defined (an item is in every set or in none)"))

    sample = None
    if respondents is not None:
        per_item = respondents * min(item_total) / n_versions
        needed = TOTAL_SAMPLE * max(1.0, n_items / SAMPLE_ITEMS_BASE)
        subgroup = SUBGROUP_SAMPLE * max(1.0, n_items / SAMPLE_ITEMS_BASE)
        scaled = f" ({n_items} items: raised in proportion above {SAMPLE_ITEMS_BASE})" if n_items > SAMPLE_ITEMS_BASE else ""
        total_verdict = (f"{'at or above' if respondents >= needed else 'under'} the {needed:.0f} in total "
                         f"and {subgroup:.0f} per reported subgroup that Sawtooth asks for{scaled}")
        if exposures >= WARN_EXPOSURES:
            verdict = ("not a sparse design (2 or more exposures per respondent), so the 500 to 1000 exposures rule "
                       "for pooled analysis does not apply")
        elif per_item >= SPARSE_GOOD_EXPOSURES:
            verdict = "at or above the preferred 1000 for a sparse design"
        elif per_item >= SPARSE_MIN_EXPOSURES:
            verdict = "above the minimum of 500, under the preferred 1000 for a sparse design"
        else:
            verdict = "under the minimum of 500 for pooled analysis of a sparse design"
        if respondents < DISCOVER_MIN_SAMPLE:
            rule = f"fewer than {DISCOVER_MIN_SAMPLE} respondents is below every sample Discover's guidance covers"
        elif exposures >= DEFAULT_EXPOSURES:
            rule = "3 or more exposures per respondent: meets Discover's guidance at this sample size"
        elif exposures < 1:
            rule = ("under 1 exposure per respondent: below Discover's 1 to 2 even at 600 or more respondents; "
                    "only pooled (aggregate or latent class) scores are possible")
        elif respondents >= LARGE_SAMPLE:
            rule = "1 to 3 exposures per respondent, acceptable at 600 or more respondents (Discover)"
        elif respondents <= SMALL_SAMPLE:
            rule = "under 3 exposures per respondent with 400 or fewer respondents: Discover asks for 3 or more"
        else:
            rule = "under 3 exposures per respondent; Discover's guidance covers up to 400 and from 600 respondents, not between"
        sample = {
            "respondents": respondents,
            "exposures_per_item": round(per_item, 1),
            "total_verdict": total_verdict,
            "exposures_verdict": verdict,
            "per_respondent_rule": rule,
        }

    diagnostics = {
        "times_shown_per_respondent": round(exposures, 4),
        "item_frequency": {
            "overall": {items[i]: item_total[i] for i in range(n_items)},
            "min": min(item_total), "max": max(item_total),
            "mean": round(sum(item_total) / n_items, 4),
            "worst_version_range": worst_item_range,
        },
        "pair_frequency": {
            "pairs": len(pair_values), "min": min(pair_values) if pair_values else 0,
            "max": max(pair_values) if pair_values else 0, "mean": round(pair_mean, 4), "sd": round(pair_sd, 4),
            "pairs_never_together": never, "worst_version_range": worst_pair_range,
        },
        "position_frequency": {
            "overall": {items[i]: pos_total[i] for i in range(n_items)},
            "max_spread": max(spreads),
            "worst_version_spread": worst_version_spread,
        },
        "connectivity": {"overall_components": components, "versions_connected": connected_versions, "versions": n_versions},
        "versions_missing_items": len(missing_by_version),
        "item_correlation": {"min": corr_min, "max": corr_max, "undefined_pairs": undefined},
        "repeats_within_set": repeats,
        "repeated_sets_within_versions": repeated_sets,
        "adjacent_set_repeats_mean": round(adjacent_repeats / adjacent_gaps, 4) if adjacent_gaps else 0.0,
    }
    return {
        "parameters": {"items": n_items, "items_per_set": per_set, "sets_per_version": n_sets, "versions": n_versions},
        "is_bibd": is_bibd,
        "sample": sample,
        "diagnostics": diagnostics,
        "criteria": criteria,
        "meets_criteria": all(c["status"] != "fail" for c in criteria),
        "warnings": sum(1 for c in criteria if c["status"] == "warn"),
    }


# ---------------------------------------------------------------- output


def design_csv(rows, items=None, wide=False, item_id=False):
    """Long CSV (version,set,position,item[,item_id]) or, with wide, version,set,item1..itemk."""
    ids = {item: number for number, item in enumerate(items or [], 1)}
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    if not wide:
        writer.writerow(CSV_COLUMNS + (["item_id"] if item_id else []))
        for row in rows:
            writer.writerow(list(row) + ([ids[row[3]]] if item_id else []))
        return buffer.getvalue()
    sets = {}
    for version, set_number, position, item in rows:
        sets.setdefault((version, set_number), []).append((position, ids[item] if item_id else item))
    size = max(len(cells) for cells in sets.values())
    writer.writerow(["version", "set"] + [f"item{n}" for n in range(1, size + 1)])
    for (version, set_number), cells in sorted(sets.items()):
        writer.writerow([version, set_number] + [value for _p, value in sorted(cells)])
    return buffer.getvalue()


def render(report, rows, items):
    p, d = report["parameters"], report["diagnostics"]
    lines = []
    title = "MaxDiff design: generated" if report["mode"] == "generate" else f"MaxDiff design: check of {report['source']}"
    lines.append(title)
    seed = f"   Seed: {p['seed']}" if p.get("seed") is not None else ""
    lines.append(f"Items: {p['items']}   Items per set: {p['items_per_set']}   Sets per respondent: {p['sets_per_version']}"
                 f"   Versions: {p['versions']}{seed}")
    rec = report["recommendation"]
    lines.append(f"Sets rule: {rec['rule']}")
    lines.append(f"Each item is shown {d['times_shown_per_respondent']:.2f} times per respondent")
    lines.append(f"Versions rule: {report['versions_rule']}")
    length = report["length_estimate"]
    lines.append(f"Length: about {length['minutes']:.1f} minutes ({p['sets_per_version']} sets x {length['seconds_per_set']} s; "
                 f"{length['basis']})")
    if report.get("sample"):
        sample = report["sample"]
        lines.append(f"Sample: {sample['respondents']} respondents, {sample['total_verdict']}; each item shown about "
                     f"{sample['exposures_per_item']:.0f} times in total, {sample['exposures_verdict']}; "
                     f"{sample['per_respondent_rule']}")
    if report.get("method"):
        lines.append(f"Method: {report['method_detail']}")
    lines.append(f"Exact BIBD in every version: {'yes' if report['is_bibd'] else 'no'}")
    for note in report.get("notes", []):
        lines.append(f"Note: {note}")
    lines.append("")
    f, q, c = d["item_frequency"], d["pair_frequency"], d["connectivity"]
    lines.append(f"Item frequency (all versions): min {f['min']}, max {f['max']}, mean {f['mean']:.2f}; "
                 f"largest range inside a version {f['worst_version_range']}")
    lines.append(f"Pair frequency (all versions): min {q['min']}, max {q['max']}, mean {q['mean']:.2f}, sd {q['sd']:.2f}; "
                 f"{q['pairs_never_together']} of {q['pairs']} pairs never together; "
                 f"largest range inside a version {q['worst_version_range']}")
    lines.append(f"Position frequency: largest gap for one item {d['position_frequency']['max_spread']}")
    lines.append(f"Connectivity: {c['versions_connected']} of {c['versions']} versions connected; "
                 f"{'connected' if c['overall_components'] == 1 else str(c['overall_components']) + ' separate groups'} overall")
    corr = d["item_correlation"]
    undefined = (f"; {corr['undefined_pairs']} pairs have no correlation (an item is in every set or in none)"
                 if corr["undefined_pairs"] else "")
    if corr["min"] is not None:
        lines.append(f"Item correlation (0/1 item-in-set indicators): min {corr['min']:.2f}, max {corr['max']:.2f}{undefined}")
    elif undefined:
        lines.append("Item correlation:" + undefined[1:])
    lines.append(f"Adjacent sets: {d['adjacent_set_repeats_mean']:.2f} items repeated from the previous set on average")
    lines.append("")
    lines.append("Criteria")
    for crit in report["criteria"]:
        lines.append(f"  {crit['status'].upper():4}  {crit['name']}: {crit['detail']}")
    if not report["meets_criteria"]:
        result = "DOES NOT meet the balance criteria (see FAIL lines)"
    elif report["warnings"]:
        result = f"meets the balance criteria, with {report['warnings']} WARN line(s) to fix or accept with a reason"
    else:
        result = "meets the balance criteria"
    lines.append("Result: " + result)
    lines.append("")
    width = max(len("item"), max(len(item) for item in items))
    k = p["items_per_set"]
    lines.append("Item frequencies and positions (all versions)")
    lines.append("  " + "item".ljust(width) + "  shown  " + "  ".join(f"pos{n}" for n in range(1, k + 1)))
    for item in items:
        positions = "  ".join(str(n).rjust(4) for n in d["position_frequency"]["overall"][item])
        lines.append("  " + item.ljust(width) + f"  {f['overall'][item]:5}  " + positions)
    lines.append("")
    first = min(row[0] for row in rows)
    lines.append(f"Sets of version {first}" + (f" (of {p['versions']}; the CSV has them all)" if p["versions"] > 1 else ""))
    sets = {}
    for version, set_number, position, item in rows:
        if version == first:
            sets.setdefault(set_number, []).append((position, item))
    for set_number in sorted(sets):
        lines.append(f"  set {set_number}: " + " | ".join(item for _p, item in sorted(sets[set_number])))
    return "\n".join(lines) + "\n"


def build_parser():
    parser = argparse.ArgumentParser(
        description="Build a balanced MaxDiff (best-worst) design, or check an existing one.",
        epilog="CSV layout: version,set,position,item. Exit codes: 0 meets criteria, 1 a criterion failed, 2 bad input.")
    parser.add_argument("items_file", nargs="?", help="text file with one item per line (UTF-8)")
    parser.add_argument("--items", type=int, metavar="N", help="number of items, when there is no items file (labels Item 1..N)")
    parser.add_argument("--per-set", type=int, metavar="k", help="items shown per set (default 4, or 3 for 6-7 items)")
    parser.add_argument("--sets", type=int, metavar="S", help="sets per respondent (default: 3 x items / per-set, rounded up)")
    parser.add_argument("--exposures", type=int, default=DEFAULT_EXPOSURES, metavar="E",
                        help="target times each item is shown per respondent when --sets is not given (default 3)")
    parser.add_argument("--versions", type=int, default=DEFAULT_VERSIONS, metavar="V",
                        help=f"questionnaire versions to generate (default {DEFAULT_VERSIONS}; use 1 for one fixed design, "
                             f"up to {SAWTOOTH_DEFAULT_VERSIONS} when the survey tool assigns versions)")
    parser.add_argument("--respondents", type=int, metavar="N",
                        help="planned sample size: adds total exposures per item and the sample-size rules to the report")
    parser.add_argument("--seconds-per-set", type=int, default=None, metavar="SEC",
                        help=f"seconds a respondent needs per set, for the length estimate (assumed {DEFAULT_SECONDS_PER_SET} if not given)")
    parser.add_argument("--wide", action="store_true", help="write the CSV as version,set,item1..itemk")
    parser.add_argument("--item-id", action="store_true",
                        help="add an item_id column (1-based position in the item list); with --wide, write ids instead of labels")
    parser.add_argument("--seed", type=int, default=1, help="random seed (default 1); the same seed gives the same design")
    parser.add_argument("--restarts", type=int, default=DEFAULT_RESTARTS, metavar="R",
                        help=f"search restarts per version (default {DEFAULT_RESTARTS})")
    parser.add_argument("--check", metavar="DESIGN_CSV",
                        help="validate an existing design CSV (long, or wide version,set,item1..itemk) instead of generating")
    parser.add_argument("--delimiter", metavar="CHAR",
                        help="field separator of the --check file (default: comma, semicolon or tab, read from the header)")
    parser.add_argument("--out", metavar="FILE", help="write the design CSV to FILE")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="print the report and the design as JSON")
    output.add_argument("--csv", action="store_true", help="print only the design CSV")
    return parser


def run(args):
    notes = []
    if args.respondents is not None and args.respondents < 1:
        raise InputError("--respondents must be 1 or more")
    if args.seconds_per_set is not None and args.seconds_per_set < 1:
        raise InputError("--seconds-per-set must be 1 or more")
    if args.check:
        if args.items is not None or args.per_set is not None or args.sets is not None:
            raise InputError("--check reads the design from the CSV; do not combine it with --items, --per-set or --sets")
        items = read_items(args.items_file) if args.items_file else None
        rows, layout = read_design(args.check, args.delimiter)
        rows, mapped = ids_to_labels(rows, items, args.check)
        if layout == "wide":
            notes.append("wide layout read: positions taken from the numbers in the item column names")
        if mapped:
            notes.append("item cells are numbers: read as 1-based ids into the items file")
        report = diagnose(rows, items, args.respondents)
        report["mode"], report["source"] = "check", args.check
        report["parameters"]["seed"] = None
        report["method"] = None
    else:
        if args.items_file and args.items is not None:
            raise InputError("give an items file or --items N, not both")
        if args.items_file:
            items = read_items(args.items_file)
        elif args.items is not None:
            if args.items < 1:
                raise InputError("--items must be a positive number")
            items = [f"Item {n}" for n in range(1, args.items + 1)]
        else:
            raise InputError("give an items file (one item per line), --items N, or --check DESIGN_CSV")
        n_items = len(items)
        if n_items < 3:
            raise InputError(f"a MaxDiff design needs at least 3 items; got {n_items}")
        if args.per_set is None:
            per_set = default_per_set(n_items)
            notes.append(f"--per-set not given: using {per_set}")
        else:
            per_set = args.per_set
        if per_set < MIN_PER_SET:
            raise InputError(f"--per-set must be at least {MIN_PER_SET}: with 2 the best and worst choice are one "
                             "choice (a paired comparison)")
        if per_set >= n_items:
            raise InputError(f"--per-set ({per_set}) must be smaller than the number of items ({n_items}); "
                             "a set with every item only identifies the best and the worst")
        if not 1 <= args.exposures:
            raise InputError("--exposures must be 1 or more")
        if args.exposures > MAX_USEFUL_EXPOSURES:
            notes.append(f"--exposures {args.exposures} is above the usual range of {DEFAULT_EXPOSURES} to {MAX_USEFUL_EXPOSURES}")
        n_sets = recommended_sets(n_items, per_set, args.exposures) if args.sets is None else args.sets
        if n_sets < 1:
            raise InputError("--sets must be 1 or more")
        if args.versions < 1:
            raise InputError("--versions must be 1 or more")
        if args.restarts < 1:
            raise InputError("--restarts must be 1 or more")
        rows, method, detail = generate(items, per_set, n_sets, args.versions, args.seed, args.restarts)
        report = diagnose(rows, items, args.respondents)
        report["mode"] = "generate"
        report["parameters"]["seed"] = args.seed
        if method == "randomized-search":
            detail += search_outcome(n_items, per_set, n_sets, report["is_bibd"])
        report["method"], report["method_detail"] = method, detail
        if args.sets is None and method == "randomized-search" and per_set <= MAX_PER_SET:
            if find_difference_set(n_items, per_set):
                notes.append(f"an exact BIBD exists with --sets {n_items} (each item shown {per_set} times)")
            elif affine_order(n_items, per_set):
                notes.append(f"an exact BIBD exists with --sets {n_items + per_set} (each item shown {per_set + 1} times)")
        if n_items > MANY_ITEMS:
            notes.append(f"more than {MANY_ITEMS} items: plan a larger sample or a sparse design (see references/design-guide.md)")
        if args.versions < PAPER_MIN_VERSIONS:
            notes.append(f"fewer than {PAPER_MIN_VERSIONS} versions: order and context effects are not averaged out")
        items = list(items)
    p = report["parameters"]
    minimum = recommended_sets(p["items"], p["items_per_set"])
    report["recommendation"] = {
        "rule": (f"3 x {p['items']} items / {p['items_per_set']} per set = {minimum} sets or more, so each item is shown "
                 f"about 3 times per respondent (Sawtooth); this design has {p['sets_per_version']}"),
        "minimum_sets_for_3_exposures": minimum,
        "sets_for_5_exposures": recommended_sets(p["items"], p["items_per_set"], MAX_USEFUL_EXPOSURES),
    }
    report["notes"] = notes
    report["versions_rule"] = (
        f"{p['versions']} in this design. Default {DEFAULT_VERSIONS}: enough to average out order and context effects "
        f"(Displayr); Sawtooth generates {SAWTOOTH_DEFAULT_VERSIONS} by default and asks for at least {PAPER_MIN_VERSIONS} "
        "on paper. When respondents will be segmented or compared, choose: Displayr prefers 1 version (versions add "
        "differences that are not preference), Sawtooth fields many and scores individuals with HB; 1 version leaves "
        "order and context effects and some pairs never shown together")
    seconds = args.seconds_per_set or DEFAULT_SECONDS_PER_SET
    report["length_estimate"] = {
        "seconds_per_set": seconds,
        "minutes": round(p["sets_per_version"] * seconds / 60, 1),
        "basis": "your figure" if args.seconds_per_set else "assumed, not a sourced figure: time a pilot",
    }
    listed = items if items is not None else list(report["diagnostics"]["item_frequency"]["overall"])
    listed = list(report["diagnostics"]["item_frequency"]["overall"]) if args.check else listed
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8", newline="") as fh:
                fh.write(design_csv(rows, listed, args.wide, args.item_id))
        except OSError as exc:
            raise InputError(f"cannot write {args.out}: {exc.strerror}")
    if args.json:
        ordered = {key: report[key] for key in ("mode", "parameters", "recommendation", "versions_rule", "length_estimate",
                                                "sample", "method", "is_bibd", "notes", "diagnostics", "criteria",
                                                "meets_criteria", "warnings")}
        if report.get("method_detail"):
            ordered["method_detail"] = report["method_detail"]
        if args.check:
            ordered["source"] = args.check
        ordered["design"] = [dict(zip(CSV_COLUMNS, row)) for row in rows]
        sys.stdout.write(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n")
    elif args.csv:
        sys.stdout.write(design_csv(rows, listed, args.wide, args.item_id))
    else:
        sys.stdout.write(render(report, rows, listed))
        if args.out:
            sys.stdout.write(f"\nDesign written to {args.out} ({len(rows)} rows)\n")
    return 0 if report["meets_criteria"] else 1


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except InputError as exc:
        sys.stderr.write(f"maxdiff-design: {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
