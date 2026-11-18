#!/usr/bin/env python3
"""MaxDiff analysis: counting scores and an aggregate multinomial logit from a best-worst CSV.

Standard library only, Python 3.9+. No network. Deterministic for a given --seed.

Usage:
  python3 scripts/maxdiff_analysis.py RESPONSES.csv [--design DESIGN.csv] [options]

Input shapes (see references/input-formats.md):
  long        one row per respondent x set x shown item: respondent,set,item,best,worst (best/worst 0/1)
  wide        one row per respondent x set: respondent,set,best,worst plus the shown items, either in
              columns (--shown-cols, or item1..itemN), in one delimited cell (--shown-col), or in a
              design file (--design, columns version,set,position,item, version column in the responses)
  respondent  one row per respondent: version plus a best and a worst column per set (b1,w1,b2,w2,...),
              joined to a design file
  In the wide and respondent shapes best/worst hold item labels, or with --choice-coding position the
  position of the chosen item in the set.

What is computed (formulas and citations in references/sources.md and references/method.md):
  counts   best rate B/shown, worst rate W/shown, best-minus-worst score (B - W)/shown
  logit    sequential best-then-worst multinomial logit (default), the marginal variant or a best-only
           logit, by Newton-Raphson, reported zero-centred with standard errors from the inverse
           information matrix
  shares   100 * exp(u) / sum(exp(u)) (default) or the probability scale exp(u) / (exp(u) + a - 1)
  CIs      percentile bootstrap over respondents (not over sets), seeded; also for the difference between
           adjacent items and between segments
  fit      root likelihood (RLH) with its chance level, McFadden pseudo-R2, likelihood-ratio chi-square

Hierarchical Bayes (individual-level utilities) is not implemented.

Exit codes: 0 success, 2 bad input or arguments, 3 the logit has no finite estimate or did not converge.
"""
import argparse
import csv
import json
import math
import random
import re
import sys

VERSION = "0.1.0"

# Thresholds and defaults. Each one is listed with its source in references/sources.md.
MIN_BASE = 200  # respondents per reported group (Sawtooth guideline)
BOOTSTRAP_REPLICATES = 1000  # percentile-interval convention
SEED = 12345  # arbitrary fixed default so runs repeat
CI_LEVEL = 95.0
MAX_ITERATIONS = 50  # Newton-Raphson cap (implementation constant)
STEP_TOLERANCE = 1e-8  # largest Newton step at convergence (implementation constant)
GRADIENT_TOLERANCE = 1e-6  # largest score per choice task at convergence (implementation constant)
MAX_HALVINGS = 30  # step-halving cap (implementation constant)
# Above this share of bootstrap replicates without a finite logit estimate, the utility and share
# intervals are withheld as unreliable. A convention of this script, not a published threshold.
MAX_FAILED_REPLICATE_SHARE = 0.05

EXCLUSION_REASONS = [
    ("set_not_in_design", "the (version, set) is not in the design file"),
    ("duplicate_set", "the same respondent and set appears on more than one row (wide format)"),
    ("invalid_value", "a best/worst cell is not 0 or 1 (long format) or not a number (position coding)"),
    ("duplicate_item", "the same item is listed twice in the set"),
    ("fewer_than_two_items", "the set shows fewer than two items"),
    ("best_not_exactly_one", "no best choice, or more than one"),
    ("worst_not_exactly_one", "no worst choice, or more than one"),
    ("choice_not_shown", "the best or worst item is not among the items shown"),
    ("best_equals_worst", "the same item is marked best and worst"),
]
SHOWN_COLUMN_RE = re.compile(r"^(item|shown|option)[ _-]?\d+$", re.IGNORECASE)
NOT_SHOWN = "\x00not shown"  # stands in for a position that does not exist in the set


class InputError(Exception):
    """The files or arguments cannot be analysed as given (exit code 2)."""


class EstimationError(Exception):
    """The logit has no finite maximum-likelihood estimate or did not converge (exit code 3)."""


# --------------------------------------------------------------------------------------------------
# Reading and validating
# --------------------------------------------------------------------------------------------------


def _read_csv(path, delimiter):
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            rows = [row for row in reader]
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}")
    except UnicodeDecodeError:
        raise InputError(f"{path} is not UTF-8 text; re-export it as UTF-8 CSV")
    if not rows:
        raise InputError(f"{path} is empty")
    header = [h.strip() for h in rows[0]]
    if len(set(header)) != len(header):
        dupes = sorted({h for h in header if header.count(h) > 1})
        raise InputError(f"{path}: duplicate column name(s): {', '.join(dupes)}")
    records = []
    for number, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue  # a fully blank line
        if len(row) > len(header):
            raise InputError(f"{path} line {number}: {len(row)} cells but the header has {len(header)} columns")
        cells = [cell.strip() for cell in row] + [""] * (len(header) - len(row))
        records.append((number, dict(zip(header, cells))))
    if not records:
        raise InputError(f"{path} has a header but no data rows")
    return header, records


def _require(header, columns, path):
    missing = [c for c in columns if c not in header]
    if missing:
        raise InputError(
            f"{path}: missing column(s) {', '.join(missing)}. Found: {', '.join(header)}. "
            "Name your columns with --respondent-col, --set-col, --item-col, --best-col, --worst-col."
        )


def _read_design(path, args):
    header, records = _read_csv(path, args.delimiter)
    _require(header, [args.set_col, args.position_col, args.item_col], path)
    has_version = args.version_col in header
    cells = {}
    for number, rec in records:
        version = rec[args.version_col] if has_version else ""
        set_id, position, item = rec[args.set_col], rec[args.position_col], rec[args.item_col]
        if not set_id or not item or (has_version and not version):
            raise InputError(f"{path} line {number}: blank version, set or item")
        try:
            order = float(position)
        except ValueError:
            raise InputError(f"{path} line {number}: position {position!r} is not a number")
        key = (version, set_id)
        slot = cells.setdefault(key, {})
        if order in slot:
            raise InputError(f"{path} line {number}: position {position} is used twice in version {version!r} set {set_id!r}")
        slot[order] = item
    design = {}
    for key, slot in cells.items():
        slots = [(order, slot[order]) for order in sorted(slot)]
        items = [item for _, item in slots]
        if len(set(items)) != len(items):
            raise InputError(f"{path}: version {key[0]!r} set {key[1]!r} lists the same item twice")
        design[key] = slots
    versions = sorted({key[0] for key in design})
    return design, versions, has_version


def _task_columns(header, best_prefix, worst_prefix):
    """Column pairs of the one-row-per-respondent layout: [(set id, best column, worst column)]."""
    found = {}
    for kind, prefix in (("best", best_prefix), ("worst", worst_prefix)):
        pattern = re.compile("^" + re.escape(prefix) + r"[ _-]?(\d+)$", re.IGNORECASE)
        for column in header:
            match = pattern.match(column)
            if match:
                found.setdefault(int(match.group(1)), {})[kind] = column
    pairs = []
    for number in sorted(found):
        if len(found[number]) == 2:
            pairs.append((str(number), found[number]["best"], found[number]["worst"]))
    return pairs


def load_sets(args):
    """Return (sets, items, meta). Each set: dict(respondent, set, items, best, worst)."""
    header, records = _read_csv(args.input, args.delimiter)
    fmt = args.format
    task_columns = _task_columns(header, args.best_prefix, args.worst_prefix)
    if fmt == "auto":
        if args.set_col not in header and task_columns:
            fmt = "respondent"
        elif args.design or args.shown_cols or args.shown_col or args.item_col not in header:
            fmt = "wide"
        else:
            fmt = "long"
    if fmt == "long" and (args.design or args.choice_coding == "position"):
        raise InputError("--design and --choice-coding position apply to the wide and respondent formats, not to long")
    if fmt == "respondent":
        _require(header, [args.respondent_col], args.input)
        if not args.design:
            raise InputError("one row per respondent (--format respondent) needs --design to know what each set showed")
        if not task_columns:
            raise InputError(
                f"{args.input}: no best/worst column pairs like {args.best_prefix}1, {args.worst_prefix}1 found; "
                "set --best-prefix and --worst-prefix"
            )
    else:
        _require(header, [args.respondent_col, args.set_col, args.best_col, args.worst_col], args.input)
    if args.segment_col and args.segment_col not in header:
        raise InputError(f"{args.input}: segment column {args.segment_col!r} not found. Found: {', '.join(header)}")

    notes = []
    excluded = {reason: 0 for reason, _ in EXCLUSION_REASONS}
    examples = {}
    segments = {}
    seen_respondents = []
    seen = set()
    sets = []
    item_order = []
    item_seen = set()

    def note_item(label):
        if label not in item_seen:
            item_seen.add(label)
            item_order.append(label)

    def identify(number, rec, set_id=None):
        respondent = rec[args.respondent_col]
        set_id = rec[args.set_col] if set_id is None else set_id
        if not respondent or not set_id:
            raise InputError(f"{args.input} line {number}: blank respondent or set id")
        if respondent not in seen:
            seen.add(respondent)
            seen_respondents.append(respondent)
        if args.segment_col:
            value = rec[args.segment_col] or "(blank)"
            if segments.setdefault(respondent, value) != value:
                raise InputError(
                    f"{args.input} line {number}: respondent {respondent!r} has two segment values "
                    f"({segments[respondent]!r} and {value!r}); a respondent belongs to one segment"
                )
        return respondent, set_id

    def exclude(reason, respondent, set_id):
        excluded[reason] += 1
        examples.setdefault(reason, f"respondent {respondent}, set {set_id}")

    def accept(respondent, set_id, items, bests, worsts):
        """Apply the set rules in a fixed order; keep the set or count one exclusion reason."""
        if len(set(items)) != len(items):
            return exclude("duplicate_item", respondent, set_id)
        if len(items) < 2:
            return exclude("fewer_than_two_items", respondent, set_id)
        if len(bests) != 1:
            return exclude("best_not_exactly_one", respondent, set_id)
        if len(worsts) != 1:
            return exclude("worst_not_exactly_one", respondent, set_id)
        if bests[0] not in items or worsts[0] not in items:
            return exclude("choice_not_shown", respondent, set_id)
        if bests[0] == worsts[0]:
            return exclude("best_equals_worst", respondent, set_id)
        sets.append({"respondent": respondent, "set": set_id, "items": list(items), "best": bests[0], "worst": worsts[0]})

    if fmt == "long":
        _require(header, [args.item_col], args.input)
        grouped = {}
        for number, rec in records:
            respondent, set_id = identify(number, rec)
            if not rec[args.item_col]:
                raise InputError(f"{args.input} line {number}: blank item")
            note_item(rec[args.item_col])
            grouped.setdefault((respondent, set_id), []).append(rec)
        for (respondent, set_id), rows in grouped.items():
            if any(r[args.best_col] not in ("0", "1") or r[args.worst_col] not in ("0", "1") for r in rows):
                exclude("invalid_value", respondent, set_id)
                continue
            items = [r[args.item_col] for r in rows]
            bests = [r[args.item_col] for r in rows if r[args.best_col] == "1"]
            worsts = [r[args.item_col] for r in rows if r[args.worst_col] == "1"]
            accept(respondent, set_id, items, bests, worsts)
    else:
        design, versions, design_has_version, join_on_version = None, [], False, False
        shown_cols = []
        if args.design:
            design, versions, design_has_version = _read_design(args.design, args)
            for slots in design.values():
                for _, label in slots:
                    note_item(label)
            join_on_version = design_has_version and args.version_col in header
            if design_has_version and not join_on_version:
                if len(versions) > 1:
                    raise InputError(
                        f"{args.design} has {len(versions)} versions but {args.input} has no "
                        f"{args.version_col!r} column, so sets cannot be matched to what was shown"
                    )
                notes.append(f"The design has one version ({versions[0]}); every respondent is matched to it.")
        elif args.shown_col:
            _require(header, [args.shown_col], args.input)
            notes.append(f"Shown items read from column {args.shown_col!r}, split on {args.shown_sep!r}.")
        elif args.shown_cols:
            shown_cols = [c.strip() for c in args.shown_cols.split(",") if c.strip()]
            _require(header, shown_cols, args.input)
        else:
            shown_cols = [c for c in header if SHOWN_COLUMN_RE.match(c)]
            if len(shown_cols) < 2:
                raise InputError(
                    f"{args.input}: no {args.item_col!r} column (long format) and no shown-item columns "
                    "(wide format). Pass --shown-cols col1,col2,..., --shown-col CELL or --design DESIGN.csv."
                )
            notes.append(f"Shown items read from columns: {', '.join(shown_cols)}.")
        if args.choice_coding == "position":
            notes.append("Best and worst were read as positions in the set and translated to items.")

        # One task per respondent and set: (respondent, set, record, best cell, worst cell).
        tasks = []
        if fmt == "respondent":
            notes.append(
                f"One row per respondent: {len(task_columns)} sets read from column pairs "
                f"{task_columns[0][1]}/{task_columns[0][2]} to {task_columns[-1][1]}/{task_columns[-1][2]}."
            )
            for number, rec in records:
                for set_id, best_col, worst_col in task_columns:
                    respondent, _ = identify(number, rec, set_id)
                    tasks.append((respondent, set_id, rec, rec[best_col], rec[worst_col]))
        else:
            for number, rec in records:
                respondent, set_id = identify(number, rec)
                tasks.append((respondent, set_id, rec, rec[args.best_col], rec[args.worst_col]))
        used, duplicated = set(), set()
        for respondent, set_id, _, _, _ in tasks:
            key = (respondent, set_id)
            (duplicated if key in used else used).add(key)
        reported = set()
        for respondent, set_id, rec, best_cell, worst_cell in tasks:
            key = (respondent, set_id)
            if key in duplicated:
                if key not in reported:
                    reported.add(key)
                    exclude("duplicate_set", respondent, set_id)
                continue
            # slots: (position, item label) for every position of the set, in order.
            if design is not None:
                version = rec[args.version_col] if join_on_version else (versions[0] if design_has_version else "")
                slots = design.get((version, set_id))
                if slots is None:
                    exclude("set_not_in_design", respondent, set_id)
                    continue
            elif args.shown_col:
                parts = [part.strip() for part in rec[args.shown_col].split(args.shown_sep)]
                slots = [(float(n), part) for n, part in enumerate(parts, start=1)]
            else:
                slots = [(float(n), rec[c]) for n, c in enumerate(shown_cols, start=1)]
            items = [label for _, label in slots if label]
            if design is None:
                for label in items:
                    note_item(label)
            choices, bad_number = [], False
            for cell in (best_cell, worst_cell):
                if not cell:
                    choices.append([])
                elif args.choice_coding == "label":
                    choices.append([cell])
                else:
                    try:
                        wanted = float(cell)
                    except ValueError:
                        bad_number = True
                        break
                    match = [label for position, label in slots if position == wanted and label]
                    choices.append(match or [NOT_SHOWN])
            if bad_number:
                exclude("invalid_value", respondent, set_id)
                continue
            accept(respondent, set_id, items, choices[0], choices[1])

    total_sets = len(sets) + sum(excluded.values())
    if not sets:
        detail = "; ".join(f"{reason}: {count}" for reason, count in excluded.items() if count)
        raise InputError(f"no valid sets left after validation ({detail}). Check the column names and the 0/1 coding.")
    used_items = set()
    for s in sets:
        used_items.update(s["items"])
    never_valid = [label for label in item_order if label not in used_items]
    # Item order: the design's order when there is a design, otherwise natural label order (item2 before
    # item10). The last item is the reference item of the reference-coded utilities.
    items = [label for label in item_order if label in used_items]
    if not args.design:
        items.sort(key=lambda label: [(0, int(part), "") if part.isdigit() else (1, 0, part.lower())
                                      for part in re.split(r"(\d+)", label) if part] + [(2, 0, label)])
    if len(items) < 2:
        raise InputError("fewer than two items appear in valid sets; nothing to compare")
    valid_respondents = {s["respondent"] for s in sets}
    dropped = [r for r in seen_respondents if r not in valid_respondents]
    if "segment" in header and not args.segment_col:
        notes.append("A column named 'segment' exists; pass --segment-col segment to cut by it.")
    meta = {
        "format": fmt,
        "sets_read": total_sets,
        "sets_valid": len(sets),
        "sets_excluded": sum(excluded.values()),
        "excluded_by_reason": {reason: count for reason, count in excluded.items() if count},
        "excluded_examples": examples,
        "respondents_read": len(seen_respondents),
        "respondents_without_valid_sets": dropped,
        "items_without_valid_sets": never_valid,
        "notes": notes,
    }
    return sets, items, segments, meta


# --------------------------------------------------------------------------------------------------
# Sufficient statistics per respondent
# --------------------------------------------------------------------------------------------------


def respondent_stats(sets, items):
    """Per respondent: shown/best/worst counts per item, and the set patterns the logit needs.

    The sequential log-likelihood depends on the data only through B - W per item, how often each
    shown set S occurred, and how often each remaining set R = S minus the best item occurred
    (references/method.md, section 3). The marginal model uses the full
    shown set for the worst choice instead of R. The "beats" edges feed the separation check (section 5).
    """
    index = {label: i for i, label in enumerate(items)}
    k = len(items)
    stats = {}
    for s in sets:
        st = stats.get(s["respondent"])
        if st is None:
            st = stats[s["respondent"]] = {
                "sets": 0, "shown": [0] * k, "best": [0] * k, "worst": [0] * k,
                "best_sets": {}, "worst_sets": {}, "worst_sets_full": {}, "edges_seq": set(), "edges_best": set(),
            }
        shown = tuple(sorted(index[label] for label in s["items"]))
        b, w = index[s["best"]], index[s["worst"]]
        st["sets"] += 1
        for i in shown:
            st["shown"][i] += 1
        st["best"][b] += 1
        st["worst"][w] += 1
        st["best_sets"][shown] = st["best_sets"].get(shown, 0) + 1
        rest = tuple(i for i in shown if i != b)
        st["worst_sets"][rest] = st["worst_sets"].get(rest, 0) + 1
        st["worst_sets_full"][shown] = st["worst_sets_full"].get(shown, 0) + 1
        for j in shown:
            if j != b:
                st["edges_best"].add(b * k + j)  # best task: b is ranked above every other shown item
                st["edges_seq"].add(b * k + j)
        for j in rest:
            if j != w:
                st["edges_seq"].add(j * k + w)  # worst task: every remaining item is ranked above w
    return stats


def pool(stats, respondents, k, model):
    """Sum the per-respondent statistics over a list of respondents (repeats allowed)."""
    shown, best, worst = [0] * k, [0] * k, [0] * k
    best_sets, worst_sets, edges = {}, {}, set()
    n_sets = 0
    edge_key = "edges_best" if model == "best-only" else "edges_seq"
    worst_key = {"sequential": "worst_sets", "marginal": "worst_sets_full"}.get(model)
    for r in respondents:
        st = stats[r]
        n_sets += st["sets"]
        for i in range(k):
            shown[i] += st["shown"][i]
            best[i] += st["best"][i]
            worst[i] += st["worst"][i]
        for key, n in st["best_sets"].items():
            best_sets[key] = best_sets.get(key, 0) + n
        if worst_key:
            for key, n in st[worst_key].items():
                worst_sets[key] = worst_sets.get(key, 0) + n
        edges |= st[edge_key]
    return {"n_sets": n_sets, "shown": shown, "best": best, "worst": worst,
            "best_sets": best_sets, "worst_sets": worst_sets, "edges": edges}


# --------------------------------------------------------------------------------------------------
# Multinomial logit
# --------------------------------------------------------------------------------------------------


def cholesky(matrix):
    """Lower-triangular L with L L^T = matrix, or None when the matrix is not positive definite."""
    n = len(matrix)
    lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            total = matrix[i][j] - sum(lower[i][m] * lower[j][m] for m in range(j))
            if i == j:
                if total <= 1e-12:
                    return None
                lower[i][i] = math.sqrt(total)
            else:
                lower[i][j] = total / lower[j][j]
    return lower


def cholesky_solve(lower, rhs):
    """Solve (L L^T) x = rhs by forward then back substitution."""
    n = len(lower)
    y = [0.0] * n
    for i in range(n):
        y[i] = (rhs[i] - sum(lower[i][m] * y[m] for m in range(i))) / lower[i][i]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (y[i] - sum(lower[m][i] * x[m] for m in range(i + 1, n))) / lower[i][i]
    return x


def separation_groups(k, edges):
    """Strongly connected components of the 'ranked above' graph, as lists of item indexes.

    A finite, unique maximum-likelihood estimate exists exactly when there is one component
    (references/method.md, section 5).
    """
    forward = [[] for _ in range(k)]
    backward = [[] for _ in range(k)]
    for code in edges:
        a, b = divmod(code, k)
        forward[a].append(b)
        backward[b].append(a)
    order, visited = [], [False] * k
    for start in range(k):  # Kosaraju, pass 1: finishing order, iteratively
        if visited[start]:
            continue
        visited[start] = True
        stack = [(start, 0)]
        while stack:
            node, pos = stack.pop()
            if pos < len(forward[node]):
                stack.append((node, pos + 1))
                nxt = forward[node][pos]
                if not visited[nxt]:
                    visited[nxt] = True
                    stack.append((nxt, 0))
            else:
                order.append(node)
    component = [-1] * k
    groups = []
    for start in reversed(order):  # pass 2 on the reversed graph
        if component[start] != -1:
            continue
        component[start] = len(groups)
        members, stack = [start], [start]
        while stack:
            node = stack.pop()
            for nxt in backward[node]:
                if component[nxt] == -1:
                    component[nxt] = len(groups)
                    members.append(nxt)
                    stack.append(nxt)
        groups.append(sorted(members))
    return groups


def _evaluate(u, d, best_sets, worst_sets, derivatives):
    """Log-likelihood, and with derivatives=True the score and information for items 0..K-2."""
    k = len(u)
    p = k - 1
    loglik = sum(d[i] * u[i] for i in range(k))
    grad = [float(d[i]) for i in range(p)] if derivatives else None
    info = [[0.0] * p for _ in range(p)] if derivatives else None
    for sign, patterns in ((1.0, best_sets), (-1.0, worst_sets)):
        for members, n in patterns:
            values = [sign * u[i] for i in members]
            top = max(values)
            weights = [math.exp(v - top) for v in values]
            total = sum(weights)
            loglik -= n * (top + math.log(total))
            if not derivatives:
                continue
            probs = [w / total for w in weights]
            for a, i in enumerate(members):
                if i >= p:
                    continue
                pa = probs[a]
                grad[i] -= sign * n * pa
                info[i][i] += n * pa * (1.0 - pa)
                for c in range(a):
                    j = members[c]
                    if j < p:
                        cross = n * pa * probs[c]
                        info[i][j] -= cross
                        info[j][i] -= cross
    return loglik, grad, info


def fit_logit(k, pooled, model, start=None):
    """Maximum-likelihood utilities with the last item fixed at 0 (Newton-Raphson, step halving).

    Returns dict(u, cov, loglik, loglik_null, iterations). Raises EstimationError.
    """
    groups = separation_groups(k, pooled["edges"])
    if len(groups) > 1:
        raise EstimationError(("separation", groups))
    if model == "best-only":
        d = list(pooled["best"])
        tasks = pooled["n_sets"]
    else:
        d = [pooled["best"][i] - pooled["worst"][i] for i in range(k)]
        tasks = 2 * pooled["n_sets"]
    best_sets = list(pooled["best_sets"].items())
    worst_sets = list(pooled["worst_sets"].items())
    p = k - 1
    loglik_null = _evaluate([0.0] * k, d, best_sets, worst_sets, False)[0]
    u = list(start) if start else [0.0] * k
    u[k - 1] = 0.0
    loglik, grad, info = _evaluate(u, d, best_sets, worst_sets, True)
    for iteration in range(1, MAX_ITERATIONS + 1):
        lower = cholesky(info)
        if lower is None:
            raise EstimationError(("singular", None))
        step = cholesky_solve(lower, grad)
        scale = 1.0
        for _ in range(MAX_HALVINGS):
            trial = [u[i] + scale * step[i] for i in range(p)] + [0.0]
            trial_loglik = _evaluate(trial, d, best_sets, worst_sets, False)[0]
            if trial_loglik >= loglik - 1e-12 * abs(loglik):
                break
            scale /= 2.0
        else:
            raise EstimationError(("no_ascent", None))
        u = trial
        loglik, grad, info = _evaluate(u, d, best_sets, worst_sets, True)
        if max(abs(scale * s) for s in step) < STEP_TOLERANCE and max(abs(g) for g in grad) < GRADIENT_TOLERANCE * tasks:
            lower = cholesky(info)
            if lower is None:
                raise EstimationError(("singular", None))
            cov = []
            for i in range(p):
                unit = [1.0 if m == i else 0.0 for m in range(p)]
                cov.append(cholesky_solve(lower, unit))
            return {"u": u, "cov": cov, "loglik": loglik, "loglik_null": loglik_null,
                    "iterations": iteration, "tasks": tasks}
    raise EstimationError(("no_convergence", None))


def zero_centre(u, cov):
    """Zero-centred utilities and their standard errors (delta method; the map is linear)."""
    k = len(u)
    mean = sum(u) / k
    centred = [v - mean for v in u]
    if cov is None:
        return centred, None
    full = [[cov[i][j] if i < k - 1 and j < k - 1 else 0.0 for j in range(k)] for i in range(k)]
    row_sums = [sum(row) for row in full]
    grand = sum(row_sums)
    errors = []
    for i in range(k):
        variance = full[i][i] - 2.0 * row_sums[i] / k + grand / (k * k)
        errors.append(math.sqrt(max(variance, 0.0)))
    return centred, errors


def shares(centred, scale, items_per_set):
    """Scores that sum to 100. 'preference': exp(u)/sum exp(u). 'probability': exp(u)/(exp(u)+a-1), rescaled."""
    top = max(centred)
    if scale == "preference":
        raw = [math.exp(v - top) for v in centred]
    else:
        raw = [math.exp(v) / (math.exp(v) + items_per_set - 1.0) for v in centred]
    total = sum(raw)
    return [100.0 * r / total for r in raw]


def describe_estimation_error(exc, items):
    kind, groups = exc.args[0]
    if kind == "not_shown":
        return f"items never shown in this group cannot be estimated: {', '.join(groups)}"
    if kind == "separation":
        names = [", ".join(items[i] for i in g) for g in groups]
        first, last = names[0], names[-1]
        return (
            "no finite maximum-likelihood estimate (separation). The answers never rank any item of the group "
            f"[{last}] above an item outside it, and never rank any item outside the group [{first}] above an item "
            f"inside it, so the utilities run off to infinity ({len(groups)} groups in all). "
            "Counting scores are still valid: rerun with --no-logit, or collect more answers."
        )
    if kind == "singular":
        return "the information matrix is not positive definite, so the utilities are not identified"
    if kind == "no_ascent":
        return "Newton-Raphson could not increase the likelihood (step halving exhausted)"
    return f"Newton-Raphson did not converge in {MAX_ITERATIONS} iterations"


# --------------------------------------------------------------------------------------------------
# Analysis of one group of respondents
# --------------------------------------------------------------------------------------------------


def percentile(sorted_values, q):
    """Linear-interpolation percentile (the 'type 7' definition) of an ascending list; q in 0..100."""
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * q / 100.0
    low = int(math.floor(position))
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def bw_scores(pooled):
    return [
        (pooled["best"][i] - pooled["worst"][i]) / pooled["shown"][i] if pooled["shown"][i] else None
        for i in range(len(pooled["shown"]))
    ]


def analyse_group(stats, respondents, items, args, items_per_set, rng, fail_on_logit_error):
    k = len(items)
    pooled = pool(stats, respondents, k, args.model)
    warnings = []
    result = {"n_respondents": len(respondents), "n_sets": pooled["n_sets"]}
    if len(respondents) < args.min_base:
        result["below_min_base"] = True
        warnings.append(
            f"Base of {len(respondents)} respondents is below {args.min_base}; treat the scores as directional."
        )
    not_shown = [items[i] for i in range(k) if pooled["shown"][i] == 0]
    if not_shown:
        warnings.append(f"Never shown in this group, so not scored: {', '.join(not_shown)}.")
    shown_counts = [c for c in pooled["shown"] if c]
    if min(shown_counts) != max(shown_counts):
        warnings.append(
            f"Items were not shown equally often ({min(shown_counts)} to {max(shown_counts)} times); "
            "counting scores assume a balanced design, so prefer the logit columns."
        )
    scores = bw_scores(pooled)

    logit = {"status": "skipped", "model": args.model}
    centred = errors = share = None
    fit = None
    if not args.no_logit:
        try:
            if not_shown:
                raise EstimationError(("not_shown", not_shown))
            fit = fit_logit(k, pooled, args.model)
        except EstimationError as exc:
            message = describe_estimation_error(exc, items)
            if fail_on_logit_error:
                raise EstimationError(message)
            logit = {"status": "not_estimated", "model": args.model, "reason": message}
            warnings.append(f"Logit not estimated: {message}")
        else:
            centred, errors = zero_centre(fit["u"], fit["cov"])
            share = shares(centred, args.share_scale, items_per_set)
            ref_se = [math.sqrt(max(fit["cov"][i][i], 0.0)) for i in range(k - 1)] + [0.0]
            logit = {
                "status": "ok",
                "model": args.model,
                "identification": "zero-centred (sum of utilities = 0)",
                "reference_item": items[k - 1],
                "iterations": fit["iterations"],
                "log_likelihood": fit["loglik"],
                "log_likelihood_null": fit["loglik_null"],
                "choice_tasks": fit["tasks"],
                "rlh": math.exp(fit["loglik"] / fit["tasks"]),
                "rlh_chance": math.exp(fit["loglik_null"] / fit["tasks"]),
                "mcfadden_r2": 1.0 - fit["loglik"] / fit["loglik_null"] if fit["loglik_null"] else None,
                "lr_chi_square": 2.0 * (fit["loglik"] - fit["loglik_null"]),
                "lr_degrees_of_freedom": k - 1,
                "share_scale": args.share_scale,
                "reference_coded": {
                    items[i]: {"utility": fit["u"][i], "se": ref_se[i]} for i in range(k)
                },
            }

    # Percentile bootstrap over respondents. Replicates are kept whole so that differences between
    # items, and between segments, can be formed replicate by replicate.
    rep_scores, rep_utils, rep_shares = [], [], []  # one list per replicate; None when not available
    failed = 0
    n = len(respondents)
    for _ in range(args.bootstrap):
        draw = [respondents[int(rng.random() * n)] for _ in range(n)]
        replicate = pool(stats, draw, k, args.model)
        rep_scores.append(bw_scores(replicate))
        if fit is None:
            continue
        try:
            if any(c == 0 for c in replicate["shown"]):
                raise EstimationError(("separation", None))
            refit = fit_logit(k, replicate, args.model, start=fit["u"])
        except EstimationError:
            failed += 1
            rep_utils.append(None)
            rep_shares.append(None)
            continue
        rep_centred, _ = zero_centre(refit["u"], None)
        rep_utils.append(rep_centred)
        rep_shares.append(shares(rep_centred, args.share_scale, items_per_set))
    lower_q = (100.0 - args.ci) / 2.0
    upper_q = 100.0 - lower_q

    def interval(values):
        values = [v for v in values if v is not None]
        if not values:
            return None
        ordered = sorted(values)
        return [percentile(ordered, lower_q), percentile(ordered, upper_q)]

    def column(replicates, i):
        return [vector[i] for vector in replicates if vector is not None]

    logit_intervals_ok = fit is not None and args.bootstrap > 0
    if args.bootstrap:
        result["bootstrap"] = {"replicates": args.bootstrap, "level": args.ci, "unit": "respondent"}
        if fit is not None:
            failed_share = failed / args.bootstrap
            result["bootstrap"]["logit_replicates_failed"] = failed
            result["bootstrap"]["logit_replicates_failed_share"] = failed_share
            result["bootstrap"]["logit_intervals"] = "ok"
            if failed_share > MAX_FAILED_REPLICATE_SHARE:
                logit_intervals_ok = False
                result["bootstrap"]["logit_intervals"] = "unreliable"
                warnings.append(
                    f"{failed} of {args.bootstrap} bootstrap replicates ({100 * failed_share:.1f}%) had no finite "
                    f"logit estimate, above the {100 * MAX_FAILED_REPLICATE_SHARE:g}% limit this script uses. Utility and "
                    "share intervals are unreliable and are not shown; use the counting-score intervals."
                )
            elif failed:
                warnings.append(
                    f"{failed} of {args.bootstrap} bootstrap replicates ({100 * failed_share:.1f}%) had no finite "
                    "logit estimate and were left out, so the utility and share intervals are somewhat too narrow."
                )
    result["_replicates"] = {"bw_score": rep_scores, "share": rep_shares if logit_intervals_ok else None}

    rows = []
    for i in range(k):
        row = {
            "item": items[i],
            "shown": pooled["shown"][i],
            "best": pooled["best"][i],
            "worst": pooled["worst"][i],
            "best_rate": pooled["best"][i] / pooled["shown"][i] if pooled["shown"][i] else None,
            "worst_rate": pooled["worst"][i] / pooled["shown"][i] if pooled["shown"][i] else None,
            "bw_score": scores[i],
            "bw_score_ci": interval(column(rep_scores, i)),
            "utility": centred[i] if centred else None,
            "utility_se": errors[i] if errors else None,
            "utility_ci": interval(column(rep_utils, i)) if logit_intervals_ok else None,
            "share": share[i] if share else None,
            "share_ci": interval(column(rep_shares, i)) if logit_intervals_ok else None,
        }
        rows.append(row)
    key = "share" if share else "bw_score"
    ranked = sorted(rows, key=lambda r: (-(r[key] if r[key] is not None else float("-inf")), items.index(r["item"])))
    previous, rank = None, 0
    for position, row in enumerate(ranked, start=1):
        if row[key] is None:
            row["rank"] = None
            continue
        if previous is None or abs(row[key] - previous) > 1e-12:
            rank = position
        row["rank"] = rank
        previous = row[key]
    result["ranked_by"] = key
    if share:
        result["average_share"] = 100.0 / k
    result["items"] = ranked

    # Adjacent items in the ranking: is the gap between them established by this sample?
    metric = "share" if share and logit_intervals_ok else "bw_score"
    replicates = result["_replicates"][metric] if args.bootstrap else []
    pairs = []
    scored = [row for row in ranked if row[key] is not None]
    for upper, lower in zip(scored, scored[1:]):
        a, b = items.index(upper["item"]), items.index(lower["item"])
        if upper[metric] is None or lower[metric] is None:
            continue
        gaps = [vector[a] - vector[b] for vector in replicates
                if vector is not None and vector[a] is not None and vector[b] is not None]
        pair = {
            "higher": upper["item"], "lower": lower["item"], "metric": metric,
            "difference": upper[metric] - lower[metric],
            "difference_ci": interval(gaps),
            "prob_higher_above": (
                (sum(1 for g in gaps if g > 0) + 0.5 * sum(1 for g in gaps if g == 0)) / len(gaps) if gaps else None
            ),
        }
        pairs.append(pair)
    result["adjacent_pairs"] = pairs
    result["logit"] = logit
    result["warnings"] = warnings
    return result


# --------------------------------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------------------------------


def segment_differences(groups, items, args):
    """Share (or counting-score) differences between every pair of segments, with bootstrap intervals.

    Segments are resampled independently, so replicate b of one segment is paired with replicate b of
    the other (references/method.md, section 7).
    """
    lower_q = (100.0 - args.ci) / 2.0
    names = list(groups)
    out = []
    for x in range(len(names)):
        for y in range(x + 1, len(names)):
            first, second = groups[names[x]], groups[names[y]]
            metric = "share"
            if first["_replicates"]["share"] is None or second["_replicates"]["share"] is None:
                metric = "bw_score"
            if first["logit"]["status"] != "ok" or second["logit"]["status"] != "ok":
                metric = "bw_score"
            rows_a = {row["item"]: row for row in first["items"]}
            rows_b = {row["item"]: row for row in second["items"]}
            reps_a, reps_b = first["_replicates"][metric], second["_replicates"][metric]
            rows = []
            for i, label in enumerate(items):
                va, vb = rows_a[label][metric], rows_b[label][metric]
                if va is None or vb is None:
                    rows.append({"item": label, "difference": None, "difference_ci": None, "excludes_zero": None})
                    continue
                gaps = sorted(
                    ra[i] - rb[i] for ra, rb in zip(reps_a or [], reps_b or [])
                    if ra is not None and rb is not None and ra[i] is not None and rb[i] is not None
                )
                ci = [percentile(gaps, lower_q), percentile(gaps, 100.0 - lower_q)] if gaps else None
                rows.append({
                    "item": label, "difference": va - vb, "difference_ci": ci,
                    "excludes_zero": (ci[0] > 0 or ci[1] < 0) if ci else None,
                })
            out.append({"segments": [names[x], names[y]], "metric": metric, "items": rows})
    return out


def _fmt(value, pattern):
    return "-" if value is None else pattern.format(value)


def _fmt_ci(ci, pattern):
    return "" if ci is None else " [" + pattern.format(ci[0]) + ", " + pattern.format(ci[1]) + "]"


def render_table(group):
    header = ["Rank", "Item", "Shown", "Best", "Worst", "B-W score", "Utility", "SE", "Share %"]
    lines = [header]
    for row in group["items"]:
        lines.append([
            _fmt(row["rank"], "{}"),
            row["item"],
            str(row["shown"]),
            str(row["best"]),
            str(row["worst"]),
            _fmt(row["bw_score"], "{:+.3f}") + _fmt_ci(row["bw_score_ci"], "{:+.3f}"),
            _fmt(row["utility"], "{:+.3f}") + _fmt_ci(row["utility_ci"], "{:+.3f}"),
            _fmt(row["utility_se"], "{:.3f}"),
            _fmt(row["share"], "{:.1f}") + _fmt_ci(row["share_ci"], "{:.1f}"),
        ])
    out = [_align(lines, left=(1,))]
    logit = group["logit"]
    if logit["status"] == "ok":
        out.append(f"Average share: {group['average_share']:.1f} (100 / number of items)")
        out.append(
            f"Fit: log-likelihood {logit['log_likelihood']:.2f} (null {logit['log_likelihood_null']:.2f}); "
            f"RLH {logit['rlh']:.3f} (chance {logit['rlh_chance']:.3f}); "
            f"McFadden pseudo-R2 {logit['mcfadden_r2']:.3f}; "
            f"LR chi-square {logit['lr_chi_square']:.1f} on {logit['lr_degrees_of_freedom']} df"
        )
        coded = ", ".join(
            f"{label} {entry['utility']:+.3f} (SE {entry['se']:.3f})"
            for label, entry in logit["reference_coded"].items() if label != logit["reference_item"]
        )
        out.append(f"Reference-coded utilities ({logit['reference_item']} = 0): {coded}")
    elif logit["status"] == "not_estimated":
        out.append("Logit not estimated for this group (see warnings).")
    pairs = [pair for pair in group["adjacent_pairs"] if pair["difference_ci"] is not None]
    if pairs:
        unit = "share points" if pairs[0]["metric"] == "share" else "B-W score"
        out.append(f"Adjacent items (difference in {unit}, bootstrap interval, share of replicates with the same order):")
        for pair in pairs:
            sure = "" if pair["difference_ci"][0] > 0 else "  not separated"
            out.append(
                f"  {pair['higher']} vs {pair['lower']}: {pair['difference']:+.3f}"
                f"{_fmt_ci(pair['difference_ci'], '{:+.3f}')}  {100 * pair['prob_higher_above']:.0f}%{sure}"
            )
    return "\n".join(out)


def _align(lines, left=()):
    widths = [max(len(line[c]) for line in lines) for c in range(len(lines[0]))]
    out = []
    for line in lines:
        cells = [line[c].ljust(widths[c]) if c in left else line[c].rjust(widths[c]) for c in range(len(line))]
        out.append("  ".join(cells).rstrip())
    return "\n".join(out)


def render_text(report):
    meta = report["input"]
    out = ["MaxDiff analysis", ""]
    out.append(f"Input: {meta['path']} ({meta['format']} format)")
    out.append(
        f"Respondents: {report['overall']['n_respondents']}   Valid sets: {meta['sets_valid']}   "
        f"Excluded sets: {meta['sets_excluded']}   Items: {meta['n_items']}   Items per set: {meta['items_per_set']}"
    )
    if meta["sets_excluded"]:
        out.append("Excluded sets by reason:")
        for reason, count in meta["excluded_by_reason"].items():
            out.append(f"  {reason}: {count} (first: {meta['excluded_examples'][reason]})")
    method = report["method"]
    out.append(f"Counting score: {method['counting']}")
    out.append(f"Logit: {method['logit']}")
    out.append(f"Shares: {method['shares']}")
    out.append(f"Intervals: {method['intervals']}")
    out.append("")
    out.append(f"All respondents (n={report['overall']['n_respondents']})")
    out.append(render_table(report["overall"]))
    for name, group in report.get("segments", {}).items():
        out.append("")
        flag = "  [below minimum base]" if group.get("below_min_base") else ""
        out.append(f"Segment {report['segment_column']} = {name} (n={group['n_respondents']}){flag}")
        out.append(render_table(group))
    for block in report.get("segment_differences", []):
        a, b = block["segments"]
        unit = "share points" if block["metric"] == "share" else "B-W score"
        out.append("")
        out.append(f"Difference {a} minus {b} ({unit}; * = bootstrap interval excludes 0)")
        lines = [["Item", "Difference", "Interval", ""]]
        for row in block["items"]:
            lines.append([
                row["item"], _fmt(row["difference"], "{:+.3f}"),
                _fmt_ci(row["difference_ci"], "{:+.3f}").strip(), "*" if row["excludes_zero"] else "",
            ])
        out.append(_align(lines, left=(0, 3)))
    warnings = list(report["warnings"])
    if warnings:
        out.append("")
        out.append("Warnings:")
        out.extend(f"- {w}" for w in warnings)
    if meta["notes"]:
        out.append("")
        out.append("Notes:")
        out.extend(f"- {n}" for n in meta["notes"])
    return "\n".join(out)


def build_parser():
    parser = argparse.ArgumentParser(
        description="MaxDiff analysis: counting scores and an aggregate multinomial logit from a best-worst CSV.",
        epilog="Input shapes and every option are described in references/input-formats.md.",
    )
    parser.add_argument("input", help="responses CSV (long or wide format)")
    parser.add_argument("--design", help="design CSV with columns version,set,position,item (wide format only)")
    parser.add_argument("--format", choices=["auto", "long", "wide", "respondent"], default="auto")
    parser.add_argument("--choice-coding", choices=["label", "position"], default="label",
                        help="wide/respondent formats: best and worst hold item labels (default) or the position "
                             "of the chosen item in the set")
    parser.add_argument("--delimiter", default=",", help="CSV delimiter (default: comma)")
    parser.add_argument("--respondent-col", default="respondent")
    parser.add_argument("--set-col", default="set")
    parser.add_argument("--item-col", default="item")
    parser.add_argument("--best-col", default="best")
    parser.add_argument("--worst-col", default="worst")
    parser.add_argument("--version-col", default="version")
    parser.add_argument("--position-col", default="position")
    parser.add_argument("--shown-cols", help="wide format: comma-separated columns holding the shown items")
    parser.add_argument("--shown-col", help="wide format: one column holding all shown items in a delimited cell")
    parser.add_argument("--shown-sep", default=";", help="separator inside --shown-col (default ;)")
    parser.add_argument("--best-prefix", default="b",
                        help="respondent format: best columns are <prefix><set number> (default b: b1, b2, ...)")
    parser.add_argument("--worst-prefix", default="w",
                        help="respondent format: worst columns are <prefix><set number> (default w: w1, w2, ...)")
    parser.add_argument("--segment-col", help="column to cut the results by (one value per respondent)")
    parser.add_argument("--model", choices=["sequential", "marginal", "best-only"], default="sequential",
                        help="sequential: worst is chosen from the items left after best (default); marginal: worst "
                             "is chosen from all shown items; best-only: worst choices are not modelled")
    parser.add_argument("--no-logit", action="store_true", help="counting analysis only")
    parser.add_argument("--share-scale", choices=["preference", "probability"], default="preference",
                        help="preference: exp(u)/sum exp(u); probability: exp(u)/(exp(u)+a-1) rescaled to 100")
    parser.add_argument("--items-per-set", type=int, help="a for --share-scale probability when set sizes vary")
    parser.add_argument("--bootstrap", type=int, default=BOOTSTRAP_REPLICATES,
                        help=f"bootstrap replicates over respondents (default {BOOTSTRAP_REPLICATES}; 0 = no intervals)")
    parser.add_argument("--seed", type=int, default=SEED, help=f"random seed for the bootstrap (default {SEED})")
    parser.add_argument("--ci", type=float, default=CI_LEVEL, help="interval level in percent (default 95)")
    parser.add_argument("--min-base", type=int, default=MIN_BASE,
                        help=f"warn when a reported group has fewer respondents (default {MIN_BASE})")
    parser.add_argument("--respondent-scores", action="store_true",
                        help="include each respondent's counting scores in the JSON output")
    parser.add_argument("--json", action="store_true", help="print JSON instead of the text report")
    return parser


def run(args):
    if args.bootstrap < 0:
        raise InputError("--bootstrap must be 0 or more")
    if not 0 < args.ci < 100:
        raise InputError("--ci must be between 0 and 100, for example 95")
    if len(args.delimiter) != 1:
        raise InputError("--delimiter must be a single character")
    if not args.shown_sep:
        raise InputError("--shown-sep must not be empty")
    sets, items, segments, meta = load_sets(args)
    k = len(items)
    stats = respondent_stats(sets, items)
    respondents = list(stats)
    sizes = sorted({len(s["items"]) for s in sets})
    items_per_set = sizes[0] if len(sizes) == 1 else None
    if args.share_scale == "probability" and not args.no_logit:
        if args.items_per_set:
            items_per_set = args.items_per_set
        elif items_per_set is None:
            raise InputError(
                f"--share-scale probability needs one set size, but sets show {sizes[0]} to {sizes[-1]} items; "
                "pass --items-per-set or use --share-scale preference"
            )
        if items_per_set < 2:
            raise InputError("--items-per-set must be 2 or more")

    warnings = []
    if meta["sets_excluded"]:
        share = 100.0 * meta["sets_excluded"] / meta["sets_read"]
        detail = ", ".join(f"{reason} {count}" for reason, count in meta["excluded_by_reason"].items())
        warnings.append(f"{meta['sets_excluded']} of {meta['sets_read']} sets ({share:.1f}%) were excluded: {detail}.")
    if meta["respondents_without_valid_sets"]:
        warnings.append(
            f"{len(meta['respondents_without_valid_sets'])} respondent(s) had no valid set and are not in the base."
        )
    if meta["items_without_valid_sets"]:
        warnings.append(
            "Items that appear only in excluded sets are not scored: " + ", ".join(meta["items_without_valid_sets"]) + "."
        )
    if len(sizes) > 1:
        warnings.append(f"Sets show {sizes[0]} to {sizes[-1]} items; check that this matches the design.")
    if not args.no_logit:
        warnings.append(
            "The utility SE comes from the inverse information matrix and treats every set as independent; "
            "quote the bootstrap intervals, which resample respondents."
        )

    overall = analyse_group(stats, respondents, items, args, items_per_set, random.Random(args.seed), True)
    warnings.extend(overall.pop("warnings"))
    overall.pop("_replicates")

    level = f"{args.ci:g}%"
    if args.model == "sequential":
        logit_text = (
            "aggregate sequential best-then-worst multinomial logit: P(best=i|S) = exp(u_i)/sum_S exp(u_j), "
            "then P(worst=j|S minus best) = exp(-u_j)/sum exp(-u_k); Newton-Raphson; utilities zero-centred"
        )
    elif args.model == "marginal":
        logit_text = (
            "aggregate marginal best-worst multinomial logit: P(best=i|S) = exp(u_i)/sum_S exp(u_j) and "
            "P(worst=j|S) = exp(-u_j)/sum_S exp(-u_k), both over all shown items; Newton-Raphson; "
            "utilities zero-centred"
        )
    else:
        logit_text = (
            "aggregate multinomial logit on best choices only: P(best=i|S) = exp(u_i)/sum_S exp(u_j); "
            "Newton-Raphson; utilities zero-centred; worst choices are validated but not modelled"
        )
    if args.share_scale == "preference":
        share_text = "share of preference, 100 * exp(u_i) / sum_j exp(u_j)"
    else:
        share_text = (
            f"probability scale, exp(u_i) / (exp(u_i) + a - 1) with a = {items_per_set}, rescaled to sum to 100, "
            "applied to the pooled utilities (Sawtooth applies it per respondent to HB utilities, so the numbers "
            "will not match a Sawtooth HB report)"
        )
    report = {
        "skill": "maxdiff-analysis",
        "version": VERSION,
        "input": {
            "path": args.input,
            "design": args.design,
            "format": meta["format"],
            "n_items": k,
            "items_per_set": items_per_set if items_per_set is not None else f"{sizes[0]}-{sizes[-1]}",
            "sets_read": meta["sets_read"],
            "sets_valid": meta["sets_valid"],
            "sets_excluded": meta["sets_excluded"],
            "excluded_by_reason": meta["excluded_by_reason"],
            "excluded_examples": meta["excluded_examples"],
            "respondents_read": meta["respondents_read"],
            "respondents_without_valid_sets": meta["respondents_without_valid_sets"],
            "items_without_valid_sets": meta["items_without_valid_sets"],
            "notes": meta["notes"],
        },
        "method": {
            "counting": "best-minus-worst score = (times best - times worst) / times shown, from -1 to +1",
            "logit": "not run (--no-logit)" if args.no_logit else logit_text,
            "shares": "not run (--no-logit)" if args.no_logit else share_text,
            "intervals": (
                f"{level} percentile bootstrap over respondents, {args.bootstrap} replicates, seed {args.seed}"
                if args.bootstrap else "none (--bootstrap 0)"
            ),
            "hierarchical_bayes": "not implemented; these are pooled (aggregate) estimates, not individual utilities",
            "anchoring": "not supported; scores are relative to the items tested, with no absolute threshold",
        },
        "overall": overall,
    }
    if args.segment_col:
        report["segment_column"] = args.segment_col
        report["segments"] = {}
        names = sorted({segments[r] for r in respondents})
        for name in names:
            members = [r for r in respondents if segments[r] == name]
            group = analyse_group(
                stats, members, items, args, items_per_set, random.Random(f"{args.seed}:{name}"), False
            )
            for w in group.pop("warnings"):
                warnings.append(f"Segment {name}: {w}")
            report["segments"][name] = group
        if args.bootstrap and len(names) > 1:
            report["segment_differences"] = segment_differences(report["segments"], items, args)
        for group in report["segments"].values():
            group.pop("_replicates")
        if "(blank)" in names:
            warnings.append("Respondents with an empty segment cell are grouped as '(blank)'.")
    if args.respondent_scores:
        people = []
        for r in respondents:
            st = stats[r]
            people.append({
                "respondent": r,
                "segment": segments.get(r),
                "sets": st["sets"],
                "bw_score": {
                    items[i]: ((st["best"][i] - st["worst"][i]) / st["shown"][i] if st["shown"][i] else None)
                    for i in range(k)
                },
            })
        report["respondents"] = people
    report["warnings"] = warnings
    return report


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = run(args)
    except InputError as exc:
        print(f"maxdiff-analysis: input error: {exc}", file=sys.stderr)
        return 2
    except EstimationError as exc:
        print(f"maxdiff-analysis: logit failed: {exc}", file=sys.stderr)
        return 3
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
