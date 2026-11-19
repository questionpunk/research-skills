#!/usr/bin/env python3
"""Survey weighting: rake (iterative proportional fitting) or cell-weight (post-stratify) a sample to known
population margins, optionally trim extreme weights and re-rake, and report the design effect, Kish effective
sample size, weight distribution, achieved margins and weighted estimates. Writes a new CSV with the weight
column appended; never overwrites the input.

Standard library only, Python 3.9+. No network, no randomness. Formulas and thresholds: references/sources.md.

Usage:
  python3 scripts/survey_weighting.py sample.csv --targets targets.csv
  python3 scripts/survey_weighting.py sample.csv --targets targets.csv --out weighted.csv --trim-max 5
  python3 scripts/survey_weighting.py sample.csv --target "gender:Female=51;Male=49" \\
      --target "age:18-34=30;35-54=34;55+=36" --out weighted.csv --estimate q1
  python3 scripts/survey_weighting.py sample.csv --targets cells.csv --method cell --out weighted.csv

Targets file, long form (raking):  variable,category,target   (shares, percents or counts per variable)
Targets file, cell form (post-stratification): one column per variable plus a target column.
Name the target column percent, share or count (or pass --target-unit) to state the unit instead of inferring it.
Rows excluded for an unusable base weight get a blank weight cell; zero-target categories get weight 0.

Exit codes: 0 success; 2 bad input or a refused calculation (the message says what to fix).
"""
import argparse
import csv
import io
import itertools
import json
import math
import os
import re
import sys
from statistics import NormalDist

VERSION = "0.1.0"

DEFAULT_TOLERANCE = 1e-6  # max |weighted share - target share| on every margin (convention of this skill)
DEFAULT_MAX_ITER = 1000  # Battaglia et al. (2009) suggest a cap such as 75; raking is cheap, so allow more
SMALL_CATEGORY = 0.02  # Battaglia et al. (2009): categories under about 2% are candidates for collapsing
EXTREME_WEIGHT_RATIO = 5.0  # common practice flags weights over 4-5 times the mean (Izrael et al.; unconfirmed)
HIGH_DEFF = 2.0  # a design effect of 2 halves the effective sample (arithmetic, flagged by this skill)
DROP_STOP_SHARE = 0.05  # pack rule: refuse when more than 5% of rows would be excluded (same in survey-crosstabs)
SHARE_SLACK = 0.01  # shares adding to 1 +/- 0.01 count as rounding (convention of this skill)
PERCENT_SLACK = 1.0  # percents adding to 100 +/- 1 count as rounding (convention of this skill)
TINY_WEIGHT_RATIO = 0.01  # warn when a positive weight is under 1/100 of the mean (convention of this skill)
DEFAULT_NA = ["", "NA", "N/A", "n/a", "#N/A", "NaN", "nan", "NULL", "null", "None"]
DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|", "\\t": "\t"}
# A coded answer label: "5 - Very satisfied", "5: Yes", "5. Yes", "5) Yes" or "(5) Yes". The delimiter (or the
# parentheses) is required, so "1 week", "18 to 24" and "50k-75k" stay distinct categories.
LABELLED_RE = re.compile(r"^\s*(?:\(\s*(-?\d{1,4})\s*\)|(-?\d{1,4})\s*[-–—:=.)])\s*[^\W\d_].*$")


def labelled_code(text):
    m = LABELLED_RE.match(text)
    return None if m is None else int(m.group(1) if m.group(1) is not None else m.group(2))


class InputError(Exception):
    """Bad input or a refused calculation; exit code 2."""


# ------------------------------------------------------------------------------------------------ CSV reading

def decode(data, path):
    if data.startswith(b"\xef\xbb\xbf"):
        body, codec, encoding, offset = data[3:], "utf-8", "UTF-8 with BOM", 3
    elif data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        body, codec, encoding, offset = data, "utf-16", "UTF-16", 0
    elif data[:200].count(b"\x00") > 20:
        raise InputError(f"{path} looks like UTF-16 without a byte-order mark; re-export it as CSV UTF-8")
    else:
        body, codec, encoding, offset = data, "utf-8", "UTF-8", 0
    try:
        return body.decode(codec), encoding
    except UnicodeDecodeError as exc:
        raise InputError(f"{path} is not valid {encoding} text (byte {exc.start + offset}); re-export it as "
                         "'CSV UTF-8' (Excel)")


def sniff_delimiter(text):
    """Pick the delimiter that gives the first 50 records (parsed as CSV, so quoted line breaks stay inside their
    field) the most consistent width."""
    best, best_key = ",", None
    for delim in (",", ";", "\t", "|"):
        try:
            reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
            rows = [r for r in itertools.islice(reader, 200) if any(c.strip() for c in r)][:50]
        except csv.Error:
            continue
        if not rows:
            continue
        width = len(rows[0])
        key = (width > 1, sum(1 for r in rows if len(r) == width), width)
        if best_key is None or key > best_key:
            best, best_key = delim, key
    return best


def read_table(path, delimiter=None, skip_rows=None, notes=None, detect_qualtrics=True):
    notes = notes if notes is not None else []
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except FileNotFoundError:
        raise InputError(f"file not found: {path}")
    except IsADirectoryError:
        raise InputError(f"{path} is a folder, not a CSV file")
    text, encoding = decode(data, path)
    if encoding != "UTF-8":
        notes.append(f"{os.path.basename(path)} read as {encoding}.")
    if delimiter:
        delim = DELIMITERS.get(delimiter.lower(), delimiter)
        if len(delim) != 1:
            raise InputError(f"--delimiter takes one character or comma, semicolon, tab, pipe; got {delimiter!r}")
    else:
        delim = sniff_delimiter(text)
    table = []
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim, strict=True)
    line = 0  # physical line where the last complete record ended
    try:
        for r in reader:
            line = reader.line_num
            if any(c.strip() for c in r):
                table.append(r)
    except csv.Error as exc:
        # strict=True: an opening quote that is never closed would otherwise swallow every later row.
        raise InputError(f"{path} is not valid CSV at the record starting on line {line + 1} ({exc}): check for a "
                         "quote (\") that is opened but never closed, or pass --delimiter.")
    if not table:
        raise InputError(f"{path} is empty or has no header row")
    headers = [h.strip() for h in table[0]]
    repeated = sorted({h for h in headers if headers.count(h) > 1})
    if repeated:
        raise InputError(f"{path} has more than one column named {', '.join(repr(h) for h in repeated)}. Rename "
                         "them so each column is unique.")
    body = table[1:]
    if skip_rows is None:
        skip_rows = 0
        if detect_qualtrics and len(body) >= 2 and any(c.strip().startswith('{"ImportId"') for c in body[1]):
            skip_rows = 2
            notes.append("Qualtrics export detected: skipped the question-text and ImportId rows (not copied to "
                         "the output file).")
    elif skip_rows:
        notes.append(f"Skipped {skip_rows} row(s) under the header (--skip-rows).")
    rows = []
    for index, row in enumerate(body[skip_rows:], start=2 + skip_rows):
        if len(row) > len(headers) and not any(c.strip() for c in row[len(headers):]):
            row = row[: len(headers)]
        if len(row) != len(headers):
            raise InputError(f"{path} row {index} has {len(row)} cells but the header has {len(headers)}; fix the "
                             "row or pass --delimiter.")
        rows.append(row)
    return headers, rows, delim


AMBIGUOUS_COMMA_RE = re.compile(r"-?\d{1,3},\d{3}")  # "1,020": 1020 with a thousands comma, or 1.020


def ambiguous_number(text):
    """True for '1,020'-style text, which is a thousands separator in English and a decimal comma elsewhere."""
    return bool(AMBIGUOUS_COMMA_RE.fullmatch((text or "").strip().rstrip("%").strip()))


def parse_number(text):
    """A finite float, or None. '51,5' is a decimal comma; '1,020,000' and '1,020.5' use thousands commas.
    '1,020' is ambiguous: callers check ambiguous_number() first and refuse it."""
    text = (text or "").strip().rstrip("%").strip()
    if ambiguous_number(text):
        return None
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", text):
        text = text.replace(",", "")
    elif re.fullmatch(r"-?\d+,\d+", text):
        text = text.replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def norm(text):
    """Category key: trimmed, case-folded, inner whitespace collapsed; '5 - Label' keys by its code."""
    t = re.sub(r"\s+", " ", (text or "").strip()).casefold()
    code = labelled_code(t)
    if code is not None:
        return "#" + str(code)
    if re.fullmatch(r"-?\d+(\.0+)?", t):
        return "#" + str(int(float(t)))
    return t


# ------------------------------------------------------------------------------------------------ targets

def parse_inline_targets(items):
    out = []
    for item in items or []:
        m = re.match(r"^([^:]+):(.+)$", item)
        if not m:
            raise InputError(f"--target takes VARIABLE:CAT=VALUE;CAT=VALUE; got {item!r}")
        var = m.group(1).strip()
        for part in m.group(2).split(";"):
            if not part.strip():
                continue
            if "=" not in part:
                raise InputError(f"--target {var}: {part!r} needs CATEGORY=VALUE")
            cat, val = part.rsplit("=", 1)
            out.append((var, cat.strip(), val.strip()))
    return out


HEADER_UNITS = {"count": "counts", "total": "counts", "population": "counts", "percent": "percents",
                "share": "shares", "proportion": "shares", "target": None}


def target_value(var, cat, val):
    if ambiguous_number(val):
        raise InputError(f"target for {var}={cat} is {val!r}, which could be {val.replace(',', '')} (thousands "
                         f"comma) or {val.replace(',', '.')} (decimal comma); write it without the comma")
    v = parse_number(val)
    if v is None or v < 0:
        raise InputError(f"target for {var}={cat} is {val!r}; it must be a non-negative number")
    return v


def load_targets(args, notes):
    """Returns (kind, spec, header_unit). kind 'rake': spec {var: [(label, value, has_percent_sign)]};
    kind 'cell': spec (vars, [(labels tuple, value, has_percent_sign)]). header_unit comes from the name of the
    target column (count, percent, share...) or None for 'target'."""
    header_unit = None
    if args.targets and args.target:
        raise InputError("give targets with --targets FILE or --target, not both")
    if not args.targets and not args.target:
        if args.base_weight:
            return "none", None, None  # diagnostics of an existing weight column
        raise InputError("give targets with --targets FILE or --target 'var:cat=value;cat=value' (or only "
                         "--base-weight COL to report on existing weights)")
    if args.targets:
        headers, rows, _ = read_table(args.targets, None, 0, notes, detect_qualtrics=False)
        lower = [h.lower() for h in headers]
        tcol = lower.index("target") if "target" in lower else next(
            (i for i, h in enumerate(lower) if h in HEADER_UNITS), None)
        if tcol is None:
            raise InputError(f"{args.targets}: no target column. Name it 'target' (shares, percents or counts), "
                             "or 'percent', 'share' or 'count' to state the unit.")
        header_unit = HEADER_UNITS[lower[tcol]]
        if "variable" in lower and "category" in lower:
            vi, ci = lower.index("variable"), lower.index("category")
            triples = [(r[vi].strip(), r[ci].strip(), r[tcol].strip()) for r in rows]
            kind = "rake"
        else:
            keys = [i for i in range(len(headers)) if i != tcol]
            if not keys:
                raise InputError(f"{args.targets}: needs variable,category,target (raking) or one column per "
                                 "variable plus target (cells)")
            cells = []
            for r in rows:
                labels = tuple(r[i].strip() for i in keys)
                val = r[tcol].strip()
                cells.append((labels, target_value("cell", " x ".join(labels), val), val.endswith("%")))
            return "cell", ([headers[i] for i in keys], cells), header_unit
    else:
        triples = parse_inline_targets(args.target)
        kind = "rake"
    if not triples:
        raise InputError("the targets are empty: give at least one variable,category,target row")
    margins = {}
    for var, cat, val in triples:
        v = target_value(var, cat, val)
        margins.setdefault(var, [])
        if norm(cat) in [norm(c) for c, _, _ in margins[var]]:
            raise InputError(f"target for {var}={cat} is given twice")
        margins[var].append((cat, v, val.endswith("%")))
    return kind, margins, header_unit


def to_shares(values, label, notes, unit=None, rescale=False):
    """Target values -> shares. unit: 'shares', 'percents', 'counts' or None (inferred from the total).
    Returns (shares, unit, total)."""
    total = sum(values)
    if total <= 0:
        raise InputError(f"targets for {label} add up to 0")
    if unit is None:
        if abs(total - 1) <= SHARE_SLACK:
            unit = "shares"
        elif abs(total - 100) <= PERCENT_SLACK:
            unit = "percents"
        elif 0.9 <= total <= 1.1 or 90 <= total <= 110:
            raise InputError(f"targets for {label} add up to {total:g}: shares or percents that do not add up to "
                             "1 or 100, or population counts? Fix them, or say which with --target-unit counts, "
                             "or --target-unit percents (or shares) plus --rescale-targets.")
        else:
            unit = "counts"
    if unit != "counts":
        full, slack = (1.0, SHARE_SLACK) if unit == "shares" else (100.0, PERCENT_SLACK)
        if abs(total - full) > slack and not rescale:
            raise InputError(f"targets for {label} are {unit} but add up to {total:g}, not {full:g}. Fix or complete "
                             "them (a missing category?), pass --rescale-targets to rescale them to 100%, or "
                             "--target-unit counts if they are population counts.")
        if abs(total - full) > 1e-9:
            notes.append(f"Targets for {label} add up to {total:g} {unit}; rescaled to 100%.")
    return [v / total for v in values], unit, total


def target_unit(args, header_unit, has_percent):
    """Unit precedence: --target-unit, then the target column's name, then a % sign, then the total."""
    if args.target_unit and args.target_unit != "auto":
        return args.target_unit
    if header_unit:
        return header_unit
    return "percents" if has_percent else None


# ------------------------------------------------------------------------------------------------ weighting

def rake(base, groups, shares, tol, max_iter, total, history=None, names=None):
    """Iterative proportional fitting (Deming and Stephan 1940).
    base: starting weights; groups: per variable, list of category index per respondent (None = skip);
    shares: per variable, target share per category; total: weight total to rake to.
    history: if a list, receives per-iteration per-variable margins before adjustment.
    names: per variable, (variable, [labels]) for messages.
    Raises InputError when a category with a positive target has no weight left (the targets are infeasible)."""
    w = list(base)
    # Respondents with no value on a variable (None and a positive starting weight) keep their weight on that
    # margin. Excluded rows (starting weight 0) are also None but do not change the total raked to.
    partial = [any(c is None and base[i] > 0 for i, c in enumerate(g)) for g in groups]
    for it in range(1, max_iter + 1):
        for v, (g, s) in enumerate(zip(groups, shares)):
            sums = [0.0] * len(s)
            known = 0.0
            for i, c in enumerate(g):
                if c is not None:
                    sums[c] += w[i]
                    known += w[i]
            if history is not None:
                history.append({"iteration": it, "variable": v, "margins": list(sums)})
            dead = [k for k in range(len(s)) if s[k] > 0 and not sums[k] > 0]
            if dead:
                var, labels = names[v] if names else (f"variable {v + 1}", [str(k) for k in range(len(s))])
                raise InputError(
                    f"the targets cannot all be met: {var}={labels[dead[0]]} needs {s[dead[0]]:.1%} of the weight, "
                    "but every respondent in it has weight 0 after the other margins were applied (a target of 0, "
                    "or a zero base weight, removed them). Raking cannot create weight: check the zero targets, "
                    "or collapse categories.")
            # Respondents missing this variable keep their weight; targets apply to the known part.
            goal_total = known if partial[v] else total
            factors = [(s[k] * goal_total / sums[k]) if sums[k] > 0 else 0.0 for k in range(len(s))]
            for i, c in enumerate(g):
                if c is not None:
                    w[i] *= factors[c]
        err = margin_error(w, groups, shares)
        if err < tol:
            return w, it, err, True
    return w, max_iter, margin_error(w, groups, shares), False


def margin_error(w, groups, shares):
    worst = 0.0
    for g, s in zip(groups, shares):
        sums = [0.0] * len(s)
        known = 0.0
        for i, c in enumerate(g):
            if c is not None:
                sums[c] += w[i]
                known += w[i]
        if not known > 0:
            return math.inf  # a margin with no weight cannot match a target that adds up to 100%
        worst = max(worst, max(abs(sums[k] / known - s[k]) for k in range(len(s))))
    return worst


def check_weights(w, keep):
    """Final guard before reporting or writing: finite, non-negative weights with a positive total."""
    vals = [w[i] for i in keep]
    if not all(math.isfinite(x) and x >= 0 for x in vals) or not sum(vals) > 0:
        raise InputError("the weights came out negative, infinite or all zero, so they cannot be used. Check the "
                         "targets (zero targets, conflicting margins) and the base weights.")


def weight_summary(w):
    ws = sorted(w)
    n = len(ws)
    total = sum(ws)
    mean = total / n
    w2 = sum(x * x for x in ws)
    var = sum((x - mean) ** 2 for x in ws) / n  # two-pass: no cancellation when weights are nearly equal
    cv = math.sqrt(var) / mean if mean > 0 else None
    neff = total * total / w2 if w2 > 0 else 0.0

    def q(p):  # type 7 quantile (linear interpolation), as R's default
        h = (n - 1) * p
        lo = math.floor(h)
        return ws[lo] + (h - lo) * (ws[min(lo + 1, n - 1)] - ws[lo])

    return {
        "n": n, "sum": total, "mean": mean, "min": ws[0], "p05": q(0.05), "median": q(0.5), "p95": q(0.95),
        "max": ws[-1], "max_to_mean": ws[-1] / mean if mean > 0 else None,
        # Undefined (None) when any weight is 0: a zero-target category or a zero weight leaves no finite ratio.
        "max_to_min": (ws[-1] / ws[0]) if ws[0] > 0 else None, "zero_weights": sum(1 for x in ws if x == 0),
        "min_positive_to_mean": (min(x for x in ws if x > 0) / mean) if mean > 0 else None, "cv": cv,
        "deff": 1 + cv * cv if cv is not None else None, "n_eff": neff,
        "efficiency": neff / n if n else None,
    }


def wilson(p, n, z):
    if n <= 0:
        return None
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0)) / denom
    return [max(0.0, centre - half), min(1.0, centre + half)]


# ------------------------------------------------------------------------------------------------ main logic

BLANK_TOKEN = "(blank)"


def parse_collapse(items):
    """{var: {norm(old value): new label}}. '(blank)' as an old value maps empty cells."""
    out = {}
    for item in items or []:
        m = re.match(r"^([^:]+):([^=]+)=(.+)$", item)
        if not m:
            raise InputError(f"--collapse takes VARIABLE:NEW=old1;old2; got {item!r}")
        var, new = m.group(1).strip(), m.group(2).strip()
        for old in m.group(3).split(";"):
            if old.strip():
                key = "" if old.strip().lower() == BLANK_TOKEN else norm(old)
                out.setdefault(var, {})[key] = new
    return out


def map_value(raw, var, collapse, na):
    """(key, mapped) for one data cell: collapse mappings apply first, so a missing code such as NA or a blank
    can be mapped to a category; otherwise a missing value gives (None, False)."""
    mapped = collapse.get(var, {}).get(norm(raw))
    if mapped is not None:
        return norm(mapped), True
    if raw in na:
        return None, False
    return norm(raw), False


def code_of(text):
    """Leading integer code of '5', '5 - Very satisfied', '(5) Very satisfied'; None otherwise. Same rule as
    survey-crosstabs, so categories are keyed the same way in both skills."""
    code = labelled_code(text)
    if code is not None:
        return code
    value = parse_number(text)
    if value is not None and value == int(value):
        return int(value)
    return None


def spelling_warnings(var, variants, labels):
    """variants: {category index: set of raw data values matched to it without --collapse}. Target matching
    ignores case and spacing; survey-crosstabs does not, so it would split these into separate groups."""
    out = []
    for k, vs in sorted(variants.items()):
        if len(vs) > 1 and not all(code_of(v) is not None for v in vs):
            out.append(f"{var}: {', '.join(repr(v) for v in sorted(vs))} were all matched to the target "
                       f"{labels[k]!r} (case and spacing are ignored when matching targets). survey-crosstabs keeps "
                       f"them as separate groups: standardise the spelling in the data before tabulating by {var}.")
    return out


def same_file(a, b):
    if os.path.exists(a) and os.path.exists(b):
        return os.path.samefile(a, b)
    return os.path.abspath(a) == os.path.abspath(b)


def collapse_targets(var, items, collapse, notes):
    """Apply --collapse to the target categories too: targets whose label is an old value are summed into the
    new category, so 'age:55+=55-64;65+' works whether the targets list 55+ or 55-64 and 65+."""
    mapping = collapse.get(var, {})
    out, where, combined = [], {}, {}
    for cat, value, pct in items:
        label = mapping.get(norm(cat), cat)
        key = norm(label)
        if key in where:
            j = where[key]
            out[j] = (out[j][0], out[j][1] + value, out[j][2] or pct)
        else:
            where[key] = len(out)
            out.append((label, value, pct))
        if label != cat:
            combined.setdefault(label, []).append(cat)
    for label, olds in combined.items():
        notes.append(f"{var}: targets for {', '.join(olds)} were combined into {label} (--collapse).")
    return out


def collapse_cells(variables, cells, collapse, notes):
    """Cell form of collapse_targets: map each label in a cell, then sum cells that became the same."""
    out, where, changed = [], {}, 0
    for labels, value, pct in cells:
        new = tuple(collapse.get(v, {}).get(norm(x), x) for v, x in zip(variables, labels))
        changed += new != labels
        key = tuple(norm(x) for x in new)
        if key in where:
            j = where[key]
            out[j] = (out[j][0], out[j][1] + value, out[j][2] or pct)
        else:
            where[key] = len(out)
            out.append((new, value, pct))
    if changed:
        notes.append(f"{changed} target cell(s) were relabelled by --collapse and cells that became the same were "
                     "summed.")
    return out


def achieved_margins(specs, w, base):
    """Per margin: n, share before weighting (base weights), target, weighted share and mean weight, all from
    the final weight vector w."""
    achieved = []
    for info, g in specs:
        sums = [0.0] * len(info["labels"])
        before = [0.0] * len(info["labels"])
        for i, c in enumerate(g):
            if c is not None:
                sums[c] += w[i]
                before[c] += base[i]
        known, before_total = sum(sums), sum(before)
        achieved.append({"variable": info["variable"], "categories": [{
            "category": lab, "n": info["counts"][k],
            "sample_share": before[k] / before_total if before_total else None,
            "target_share": info["target"][k], "weighted_share": sums[k] / known if known else None,
            "mean_weight": (sums[k] / info["counts"][k]) if info["counts"][k] else None,
        } for k, lab in enumerate(info["labels"])]})
    return achieved


def analyse(args):
    notes, warnings = [], []
    protected = [("the input", args.input)] + ([("the targets file", args.targets)] if args.targets else [])
    if args.out:
        for what, path in protected:
            if same_file(args.out, path):
                raise InputError(f"--out is {what}; choose a new file name (inputs are never overwritten)")
        if os.path.exists(args.out) and not args.overwrite:
            raise InputError(f"{args.out} already exists; choose a new name or pass --overwrite")
    headers, rows, delim = read_table(args.input, args.delimiter, args.skip_rows, notes)
    if not rows:
        raise InputError(f"{args.input} has a header but no respondents")
    idx = {h: i for i, h in enumerate(headers)}
    kind, spec, header_unit = load_targets(args, notes)
    if kind == "none":
        refused = [f for f, on in (("--trim-max/--trim-min", args.trim_max or args.trim_min), ("--out", args.out),
                                   ("--method", args.method), ("--collapse", args.collapse),
                                   ("--scale-total", args.scale_total)) if on]
        if refused:
            raise InputError(f"{', '.join(refused)} need(s) targets: without them there is nothing to rake, and "
                             "capping weights without re-raking would move the margins. Pass --targets or --target.")
    method = "none" if kind == "none" else args.method or ("cell" if kind == "cell" else "rake")
    if method == "cell" and kind != "cell":
        raise InputError("--method cell needs a cell targets file: one column per variable plus a target column")
    if method == "rake" and kind == "cell":
        raise InputError("this targets file is in cell form; use --method cell, or give margins as "
                         "variable,category,target")
    if args.out and args.weight_col in idx:
        raise InputError(f"the input already has a column {args.weight_col!r}; pass --weight-col with a new name")
    na = set(args.na if args.na is not None else DEFAULT_NA)
    collapse = parse_collapse(args.collapse)

    # Base weights. Rows without a usable one are excluded: they get a blank weight cell in the output, which
    # survey-crosstabs also excludes (and counts), under the same 5% rule.
    base = [1.0] * len(rows)
    keep = list(range(len(rows)))
    if args.base_weight:
        if args.base_weight not in idx:
            raise InputError(f"base weight column {args.base_weight!r} not found. Columns: {', '.join(headers)}")
        bad = []
        for i, r in enumerate(rows):
            text = r[idx[args.base_weight]]
            if ambiguous_number(text):
                raise InputError(f"base weight {text.strip()!r} on data row {i + 1} could be a thousands comma or a "
                                 "decimal comma; write the weights without commas")
            v = parse_number(text)
            if v is None or v < 0 or (v == 0 and method != "none"):
                bad.append(i)
            else:
                base[i] = v
        if bad:
            share = len(bad) / len(rows)
            if share > DROP_STOP_SHARE and not args.allow_drop:
                raise InputError(f"{len(bad)} of {len(rows)} rows ({share:.1%}) have a missing, zero or unreadable "
                                 "base weight. Fix them or pass --allow-drop (they are excluded and counted).")
            notes.append(f"{len(bad)} row(s) with no usable base weight are excluded: left out of the weighting, "
                         "with a blank weight cell in the output file (survey-crosstabs excludes blank weights too"
                         + (", and needs --allow-drop for them, as here" if share > DROP_STOP_SHARE else "") + ").")
            bad_set = set(bad)
            keep = [i for i in keep if i not in bad_set]
    keep_set = set(keep)
    base_k = [base[i] if i in keep_set else 0.0 for i in range(len(rows))]
    z = NormalDist().inv_cdf(0.975)

    if collapse and method != "none":
        weighting_vars = list(spec) if method == "rake" else spec[0]
        stray = [v for v in collapse if v not in weighting_vars]
        if stray:
            raise InputError(f"--collapse names {', '.join(repr(v) for v in stray)}, which is not a weighting "
                             f"variable. Weighting variables: {', '.join(weighting_vars)}")
    if method == "none":
        w = list(base_k)
        specs, fit, count_target, trim = [], {"method": "none", "column": args.base_weight}, None, None
    elif method == "rake":
        variables = list(spec)
        for var in variables:
            if var not in idx:
                raise InputError(f"targets name {var!r}, which is not a column. Columns: {', '.join(headers)}")
        groups, shares, specs, names = [], [], [], []
        units, count_totals = set(), []
        for var in variables:
            spec[var] = collapse_targets(var, spec[var], collapse, notes)
            labels = [c for c, _, _ in spec[var]]
            unit = target_unit(args, header_unit, any(p for _, _, p in spec[var]))
            sh, unit, raw_total = to_shares([v for _, v, _ in spec[var]], var, notes, unit, args.rescale_targets)
            units.add(unit)
            if unit == "counts":
                count_totals.append(raw_total)
            keyed = {norm(c): k for k, c in enumerate(labels)}
            g, unknown, missing, variants = [], {}, 0, {}
            for i in range(len(rows)):
                if i not in keep_set:
                    g.append(None)
                    continue
                raw = rows[i][idx[var]].strip()
                key, mapped = map_value(raw, var, collapse, na)
                if key is None:
                    missing += 1
                    g.append(None)
                    continue
                if key not in keyed:
                    unknown[raw] = unknown.get(raw, 0) + 1
                    g.append(None)
                    continue
                g.append(keyed[key])
                if not mapped:
                    variants.setdefault(keyed[key], set()).add(raw)
            if unknown:
                raise InputError(f"{var}: values with no target: "
                                 + ", ".join(f"{k!r} ({v})" for k, v in sorted(unknown.items(), key=lambda x: -x[1]))
                                 + f". Targets are: {', '.join(labels)}. Map them with --collapse "
                                 f"'{var}:TARGET=value1;value2' or fix the targets.")
            if missing:
                if args.missing == "refuse":
                    raise InputError(f"{var}: {missing} respondent(s) have no value. Map them to a category with "
                                     f"--collapse '{var}:CATEGORY=NA;{BLANK_TOKEN}' (use the missing codes in the "
                                     "data), or pass --missing skip-margin (they keep their weight on this margin "
                                     "and the target applies to the others).")
                notes.append(f"{var}: {missing} respondent(s) with no value are not adjusted on this margin.")
            warnings.extend(spelling_warnings(var, variants, labels))
            counts = [0] * len(labels)
            for c in g:
                if c is not None:
                    counts[c] += 1
            empty = [labels[k] for k in range(len(labels)) if counts[k] == 0 and sh[k] > 0]
            if empty:
                raise InputError(f"{var}: no respondents in {', '.join(empty)}, which have a target above 0. "
                                 "Raking cannot reach it: combine it with a neighbouring category, for example "
                                 f"--collapse '{var}:NEW={empty[0]};NEIGHBOUR' (applies to the data and the targets).")
            n_known = sum(counts)
            for k, lab in enumerate(labels):
                if counts[k] and (counts[k] / n_known < SMALL_CATEGORY or 0 < sh[k] < SMALL_CATEGORY):
                    warnings.append(f"{var}={lab}: under 2% of the sample or the target. Check its support and "
                                    "definition; combining it with a neighbour steadies the weights but changes "
                                    "what the margin controls (Battaglia et al. 2009).")
            groups.append(g)
            shares.append(sh)
            names.append((var, labels))
            specs.append(({"variable": var, "labels": labels, "counts": counts, "target": sh}, g))
        if len(units) > 1:
            warnings.append("Targets mix shares/percents and counts across variables; each variable was rescaled "
                            "to shares and the weights average 1 unless --scale-total is given.")
        consistent_counts = (units == {"counts"}
                             and max(count_totals) - min(count_totals) <= 0.01 * max(count_totals))
        if units == {"counts"} and not consistent_counts and not (args.scale_total or args.scale_mean_one):
            raise InputError("count targets give different population totals per variable ("
                             + ", ".join(f"{t:g}" for t in count_totals) + "). Fix them so they describe one "
                             "population, or choose the scale: --scale-total N or --scale-mean-one.")
        total = count_totals[0] if consistent_counts else sum(base_k)
        history = [] if args.history else None
        w, iterations, err, converged = rake(base_k, groups, shares, args.tolerance, args.max_iter, total, history,
                                             names)
        if not converged:
            raise InputError(f"raking did not converge in {args.max_iter} iterations (largest margin error "
                             f"{err:.2e}). The margins may conflict (a combination with no respondents). Collapse "
                             "small categories or drop a variable, then rerun.")
        trim = None
        if args.trim_max or args.trim_min:
            w, trim, converged = trim_and_rake(w, groups, shares, args, total, keep, names)
            err = margin_error(w, groups, shares)
            if not (converged and err < args.tolerance):
                raise InputError(f"after trimming, re-raking did not bring the margins within {args.tolerance:g} "
                                 f"(largest margin error {err:.2e} after {trim['cycles']} trim cycle(s)). Raise "
                                 "--max-iter, loosen --trim-max/--trim-min, or collapse sparse categories; do not "
                                 "use these weights.")
        fit = {"method": "rake", "iterations": iterations, "converged": True, "max_margin_error": err,
               "tolerance": args.tolerance, "trim": trim, "history": history}
        count_target = count_totals[0] if consistent_counts else None
    else:
        variables, cells = spec
        for var in variables:
            if var not in idx:
                raise InputError(f"targets name {var!r}, which is not a column. Columns: {', '.join(headers)}")
        cells = collapse_cells(variables, cells, collapse, notes)
        unit = target_unit(args, header_unit, any(p for _, _, p in cells))
        sh, unit, raw_total = to_shares([v for _, v, _ in cells], "the cells", notes, unit, args.rescale_targets)
        keyed = {}
        for k, (labels, _, _) in enumerate(cells):
            key = tuple(norm(x) for x in labels)
            if key in keyed:
                raise InputError(f"cell {labels} is given twice in the targets")
            keyed[key] = k
        cell_of, unknown, missing = [], {}, 0
        for i, r in enumerate(rows):
            if i not in keep_set:
                cell_of.append(None)
                continue
            raw = [r[idx[v]].strip() for v in variables]
            key = tuple(map_value(x, v, collapse, na)[0] for v, x in zip(variables, raw))
            if any(k is None for k in key):
                missing += 1
                cell_of.append(None)
                continue
            if key not in keyed:
                unknown[tuple(raw)] = unknown.get(tuple(raw), 0) + 1
                cell_of.append(None)
                continue
            cell_of.append(keyed[key])
        if unknown:
            raise InputError("respondents in cells with no target: " + ", ".join(
                f"{' x '.join(k)} ({v})" for k, v in list(unknown.items())[:10]) + ". Add the cells or --collapse.")
        if missing:
            raise InputError(f"{missing} respondent(s) have no value on a weighting variable; cell weighting needs "
                             f"every one. Map them to a category with --collapse 'VAR:CATEGORY=NA;{BLANK_TOKEN}', "
                             "or use raking.")
        counts = [0] * len(cells)
        sums = [0.0] * len(cells)
        for i, c in enumerate(cell_of):
            if c is not None:
                counts[c] += 1
                sums[c] += base[i]
        empty = [" x ".join(cells[k][0]) for k in range(len(cells)) if counts[k] == 0 and sh[k] > 0]
        if empty:
            raise InputError("no respondents in cell(s) " + "; ".join(empty) + " with a target above 0. Collapse "
                             "them with a neighbour (--collapse), or rake on the margins instead (--method rake "
                             "with a variable,category,target file).")
        total = sum(sums)
        w = [0.0] * len(rows)
        for i, c in enumerate(cell_of):
            if c is not None:
                w[i] = base[i] * sh[c] * total / sums[c]
        thin = [" x ".join(cells[k][0]) for k in range(len(cells)) if 0 < counts[k] < 5]
        if thin:
            warnings.append("cells with fewer than 5 respondents get unstable weights: " + "; ".join(thin)
                            + ". Consider collapsing or raking.")
        trim = None
        if args.trim_max or args.trim_min:
            warnings.append("Trimming is applied to raked weights only; cell weights were not trimmed. Use raking "
                            "if weights need capping.")
        specs = [({"variable": " x ".join(variables), "labels": [" x ".join(c[0]) for c in cells],
                   "counts": counts, "target": sh}, cell_of)]
        fit = {"method": "cell", "iterations": 1, "converged": True, "max_margin_error": 0.0, "trim": None,
               "history": None}
        count_target = raw_total if unit == "counts" else None

    # Final scale, then every diagnostic from the final weight vector.
    n_active = len(keep)
    check_weights(w, keep)
    current = sum(w)
    if method == "none":
        target_sum, scale_note = current, f"existing weights in {args.base_weight!r}, not rescaled"
    elif args.scale_total:
        target_sum, scale_note = args.scale_total, f"weights sum to {args.scale_total:g} (--scale-total)"
    elif count_target is not None and not args.scale_mean_one:
        target_sum, scale_note = count_target, f"weights sum to the target population total {count_target:g}"
    else:
        target_sum, scale_note = float(n_active), f"weights average 1 (sum = {n_active} respondents)"
    factor = target_sum / current
    w = [x * factor for x in w]
    check_weights(w, keep)
    achieved = achieved_margins(specs, w, base_k)
    if fit["method"] == "rake":
        fit["max_margin_error"] = margin_error(w, groups, shares)
    summary = weight_summary([w[i] for i in keep])
    warnings.extend(weight_warnings(summary, trim, args))

    estimates = []
    for col in args.estimate or []:
        if col not in idx:
            raise InputError(f"--estimate column {col!r} not found")
        estimates.append(estimate(col, rows, idx[col], w, keep, na, z))

    written = None
    if args.out:
        write_output(args.out, headers, rows, w, keep, args.weight_col, args.overwrite)
        written = args.out
    return {
        "tool": "survey-weighting", "version": VERSION,
        "input": {"file": args.input, "rows": len(rows), "weighted_rows": n_active, "excluded_rows":
                  len(rows) - n_active, "notes": notes},
        "fit": fit, "scale": scale_note, "margins": achieved, "weights": summary, "estimates": estimates,
        "warnings": warnings, "output": written, "weight_col": args.weight_col,
    }


def weight_warnings(summary, trim, args):
    out = []
    ratio = summary["max_to_mean"] or 0.0
    if trim and trim["trim_max"] and not trim["cap_met"]:
        out.append(f"the trimming cap was not met: after {trim['cycles']} trim cycle(s) the largest weight is "
                   f"{ratio:.1f} times the mean, above --trim-max {trim['trim_max']:g}, because re-raking to the "
                   "margins pulls it back up. The margins are exact; the cap is not. Collapse sparse categories, "
                   "weight on fewer variables, or use bounded calibration (for example R survey::calibrate with "
                   "bounds), which this script does not do.")
    elif ratio > EXTREME_WEIGHT_RATIO:
        if trim and trim["trim_max"]:
            out.append(f"largest weight is {ratio:.1f} times the mean, within your cap of {trim['trim_max']:g}.")
        else:
            out.append(f"largest weight is {ratio:.1f} times the mean; consider --trim-max 5 and compare estimates "
                       "with and without trimming.")
    if summary["zero_weights"]:
        out.append(f"{summary['zero_weights']} respondent(s) have weight 0 (their category has a target of 0). They "
                   "stay in the output with weight 0: survey-crosstabs counts them in the unweighted base but they "
                   "add nothing to percentages.")
    smallest = summary["min_positive_to_mean"]
    if smallest is not None and smallest < TINY_WEIGHT_RATIO:
        out.append(f"the smallest weight is {smallest:.2g} times the mean: those respondents barely count, "
                   "usually because the margins push a sparse combination of categories down hard. Collapse sparse "
                   "categories or drop a weighting variable"
                   + ("; --trim-min 0.2 floors small weights." if not args.trim_min else "."))
    if summary["deff"] and summary["deff"] > HIGH_DEFF:
        out.append(f"design effect from weighting is {summary['deff']:.2f}: the weighted sample is worth about "
                   f"{summary['n_eff']:.0f} unweighted respondents (Kish approximation).")
    return out


def trim_and_rake(w, groups, shares, args, total, keep, names=None):
    """Cap weights at trim_max x mean (and floor at trim_min x mean), re-rake, repeat (Battaglia et al. 2009).
    Respondents whose weight is 0 (a zero-target category) stay at 0 and are not floored.
    Returns (weights, trim report, converged) where converged is the status of the last rake run."""
    live = [i for i in keep if w[i] > 0]
    live_set = set(live)
    cycles = 0
    converged = True
    for _ in range(args.trim_cycles):
        mean = sum(w[i] for i in keep) / len(keep)
        hi = args.trim_max * mean if args.trim_max else math.inf
        lo = args.trim_min * mean if args.trim_min else 0.0
        if all(lo * (1 - 1e-9) <= w[i] <= hi * (1 + 1e-9) for i in live):
            break
        cycles += 1
        clipped = [min(max(x, lo), hi) if i in live_set else 0.0 for i, x in enumerate(w)]
        w, _, _, converged = rake(clipped, groups, shares, args.tolerance, args.max_iter, total, names=names)
    mean = sum(w[i] for i in keep) / len(keep)
    vals = [w[i] for i in live]
    return w, {
        "trim_max": args.trim_max, "trim_min": args.trim_min, "cycles": cycles,
        "max_to_mean_after": max(vals) / mean, "min_to_mean_after": min(vals) / mean,
        "cap_met": (not args.trim_max or max(vals) / mean <= args.trim_max * (1 + 1e-6))
        and (not args.trim_min or min(vals) / mean >= args.trim_min * (1 - 1e-6)),
    }, converged


def estimate(col, rows, ci, w, keep, na, z):
    """Weighted vs unweighted shares. Categories are keyed as survey-crosstabs keys them: by numeric code when
    every answer has one ('5' and '5 - Very likely' are one category), otherwise by the exact trimmed text
    ('Yes' and 'YES' are two categories)."""
    texts = [(i, rows[i][ci].strip()) for i in keep]
    texts = [(i, t) for i, t in texts if t not in na]
    codes = [code_of(t) for _, t in texts]
    numeric = bool(texts) and all(c is not None for c in codes)
    counts, wsum, variants = {}, {}, {}
    W = W2 = 0.0
    for (i, text), code in zip(texts, codes):
        key = code if numeric else text
        variants.setdefault(key, {}).setdefault(text, 0)
        variants[key][text] += 1
        counts[key] = counts.get(key, 0) + 1
        wsum[key] = wsum.get(key, 0.0) + w[i]
        W += w[i]
        W2 += w[i] * w[i]
    n = len(texts)
    labels = {}
    for key, vs in variants.items():
        labelled = {v: c for v, c in vs.items() if re.search(r"[^\W\d_]", v)}
        pool = labelled or vs
        labels[key] = max(pool, key=lambda s: (pool[s], len(s), s))
    neff = W * W / W2 if W2 > 0 else 0.0
    cats = sorted(counts, key=lambda k: (-wsum[k], str(k)))
    return {
        "column": col, "n": n, "n_eff": neff, "weighted_base": W,
        "note": None if W > 0 else "every respondent who answered has weight 0, so no weighted estimate exists",
        "categories": [{
            "category": labels[k], "n": counts[k], "unweighted_share": counts[k] / n,
            "weighted_share": wsum[k] / W if W > 0 else None,
            "ci": wilson(wsum[k] / W, neff, z) if W > 0 else None,
        } for k in cats],
    }


def write_output(path, headers, rows, w, keep, col, overwrite=False):
    """Input rows plus the weight column; excluded rows get a blank weight cell. A new file is created
    exclusively (never clobbering one that appeared meanwhile); --overwrite replaces atomically."""
    keep_set = set(keep)
    target = path
    if overwrite:
        target = os.path.join(os.path.dirname(os.path.abspath(path)), f".{os.path.basename(path)}.{os.getpid()}.tmp")
    try:
        handle = open(target, "x", encoding="utf-8", newline="")
    except FileExistsError:
        raise InputError(f"{path} already exists; choose a new name or pass --overwrite")
    except OSError as exc:
        raise InputError(f"cannot write {path}: {exc.strerror}")
    try:
        with handle:
            writer = csv.writer(handle)
            writer.writerow(headers + [col])
            for i, r in enumerate(rows):
                writer.writerow(r + [repr(w[i]) if i in keep_set else ""])
        if overwrite:
            os.replace(target, path)
    except OSError as exc:
        if overwrite and os.path.exists(target):
            os.remove(target)
        raise InputError(f"cannot write {path}: {exc.strerror or exc}")
    except BaseException:
        if overwrite and os.path.exists(target):
            os.remove(target)
        raise


# ------------------------------------------------------------------------------------------------ rendering

def cell(text):
    """Text for a Markdown table cell: a | or a line break inside a label would break the table."""
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def pct(x, d=1):
    return "-" if x is None else f"{100 * x:.{d}f}%"


def render(res):
    out = [f"# Weighting: {res['input']['file']}", ""]
    fit = res["fit"]
    if fit["method"] == "none":
        out.append(f"Diagnostics of the existing weights in `{fit['column']}` (no targets given: nothing was raked, "
                   "trimmed or written).")
    elif fit["method"] == "rake":
        out.append(f"Raked on {len(res['margins'])} variable(s): converged in {fit['iterations']} iteration(s); "
                   f"largest margin error {fit['max_margin_error']:.1e} (tolerance {fit['tolerance']:g}).")
    else:
        out.append("Cell weighting (post-stratification): every cell matches its target exactly.")
    if fit.get("trim"):
        t = fit["trim"]
        out.append(f"Trim bounds max {t['trim_max'] or '-'} x mean, min {t['trim_min'] or '-'} x mean: "
                   + (f"trimmed and re-raked {t['cycles']} time(s)" if t["cycles"] else "no weight was outside them")
                   + f"; largest weight {t['max_to_mean_after']:.2f} x mean"
                   + ("" if t["cap_met"] else " (CAP NOT MET: the margins are exact, the cap is not; see Warnings)")
                   + ".")
    out.append(f"Scale: {res['scale']}. Rows {res['input']['rows']}, weighted {res['input']['weighted_rows']}"
               + (f", excluded {res['input']['excluded_rows']} (blank weight in the output)"
                  if res["input"]["excluded_rows"] else "") + ".")
    for n in res["input"]["notes"]:
        out.append(f"- {n}")
    ws = res["weights"]
    out += ["", "## Weights", "",
            "| n | Kish effective n | Design effect (1 + CV²) | Efficiency | Min | 5th pct | Median | 95th pct | Max | Max / mean | Max / min |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
            f"| {ws['n']} | {ws['n_eff']:.1f} | {ws['deff']:.3f} | {100 * ws['efficiency']:.0f}% | {ws['min']:.3f} | "
            f"{ws['p05']:.3f} | {ws['median']:.3f} | {ws['p95']:.3f} | {ws['max']:.3f} | {ws['max_to_mean']:.2f} | "
            + (f"{ws['max_to_min']:.1f}" if ws["max_to_min"] else f"undefined ({ws['zero_weights']} weight(s) are 0)")
            + " |"]
    out += ["", "## Margins", ""]
    for m in res["margins"]:
        out += [f"**{m['variable']}**", "", "| Category | n | Before weighting | Target | Weighted | Mean weight |",
                "|---|---|---|---|---|---|"]
        for c in m["categories"]:
            out.append(f"| {cell(c['category'])} | {c['n']} | {pct(c['sample_share'])} | {pct(c['target_share'])} | "
                       f"{pct(c['weighted_share'])} | " + ("-" if c["mean_weight"] is None else f"{c['mean_weight']:.3f}")
                       + " |")
        out.append("")
    for e in res["estimates"]:
        out += [f"## Estimate: {e['column']} (n = {e['n']}, effective n = {e['n_eff']:.1f})", ""]
        if e["note"]:
            out += [f"No weighted estimate: {e['note']}.", ""]
        out += ["| Answer | n | Unweighted | Weighted | 95% interval (Kish approx.) |", "|---|---|---|---|---|"]
        for c in e["categories"]:
            ci = c["ci"]
            out.append(f"| {cell(c['category'])} | {c['n']} | {pct(c['unweighted_share'])} | "
                       f"{pct(c['weighted_share'])} | "
                       + (f"{pct(ci[0])} to {pct(ci[1])}" if ci else "-") + " |")
        out.append("")
    if res["warnings"]:
        out += ["## Warnings", ""] + [f"- {w}" for w in res["warnings"]]
    out.append("")
    out.append(f"Output: {res['output']} (column `{res['weight_col']}`)" if res["output"]
               else "No file written (pass --out PATH to save the weights).")
    return "\n".join(out)


def build_parser():
    p = argparse.ArgumentParser(prog="survey_weighting.py",
                                description="Rake or cell-weight a survey to population targets; report the design "
                                            "effect, effective n and achieved margins.",
                                epilog="Example: python3 scripts/survey_weighting.py sample.csv --targets t.csv "
                                       "--out weighted.csv --trim-max 5")
    p.add_argument("input", help="CSV, one row per respondent")
    p.add_argument("--targets", help="targets CSV: variable,category,target (raking) or cells + target")
    p.add_argument("--target", action="append", metavar="VAR:CAT=V;CAT=V", help="inline margin (repeatable)")
    p.add_argument("--method", choices=["rake", "cell"], help="default: rake for margins, cell for a cell file")
    p.add_argument("--out", help="write the input rows plus the weight column here (never the input file)")
    p.add_argument("--overwrite", action="store_true", help="allow --out to replace an existing file")
    p.add_argument("--weight-col", default="weight", help="name of the new weight column (default weight)")
    p.add_argument("--base-weight", metavar="COL", help="design or base weight to start from")
    p.add_argument("--collapse", action="append", metavar="VAR:NEW=old1;old2", help="map data values to a target "
                   "category (repeatable); applied before missing-value checks, so NA or (blank) can be mapped")
    p.add_argument("--target-unit", choices=["auto", "shares", "percents", "counts"], default="auto",
                   help="unit of the target values (default: from the target column name, a %% sign, or the total)")
    p.add_argument("--rescale-targets", action="store_true",
                   help="rescale shares or percents that do not add up to 100%% instead of refusing")
    p.add_argument("--missing", choices=["refuse", "skip-margin"], default="refuse",
                   help="respondents with no value on a raking variable (default refuse)")
    p.add_argument("--na", nargs="*", help="cell values meaning no answer; replaces the default list (blank, NA, "
                   "N/A, n/a, #N/A, NaN, nan, NULL, null, None), so repeat any of those you still need")
    p.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE,
                   help=f"max |weighted share - target share| (default {DEFAULT_TOLERANCE:g})")
    p.add_argument("--max-iter", type=int, default=DEFAULT_MAX_ITER, help="raking iteration cap (default 1000)")
    p.add_argument("--trim-max", type=float, metavar="R", help="cap weights at R times the mean, then re-rake")
    p.add_argument("--trim-min", type=float, metavar="R", help="floor weights at R times the mean, then re-rake")
    p.add_argument("--trim-cycles", type=int, default=50, help="trim/re-rake cycles (default 50)")
    p.add_argument("--scale-total", type=float, metavar="N", help="make weights sum to N (e.g. population size)")
    p.add_argument("--scale-mean-one", action="store_true", help="weights average 1 even with count targets")
    p.add_argument("--estimate", nargs="+", metavar="COL", help="weighted vs unweighted shares of these columns")
    p.add_argument("--history", action="store_true", help="include per-iteration margins in --json")
    p.add_argument("--delimiter", help="comma, semicolon, tab, pipe or one character (default: sniffed)")
    p.add_argument("--skip-rows", type=int, help="rows under the header to skip (Qualtrics is detected)")
    p.add_argument("--allow-drop", action="store_true", help="go on when over 5%% of base weights are unusable")
    p.add_argument("--json", action="store_true", help="machine-readable output, full precision")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        for flag, value in (("--tolerance", args.tolerance), ("--trim-max", args.trim_max),
                            ("--trim-min", args.trim_min), ("--scale-total", args.scale_total)):
            if value is not None and not math.isfinite(value):
                raise InputError(f"{flag} must be a finite number, not {value}")
        if args.tolerance <= 0 or args.max_iter < 1:
            raise InputError("--tolerance must be above 0 and --max-iter at least 1")
        if args.skip_rows is not None and args.skip_rows < 0:
            raise InputError("--skip-rows must be 0 or more")
        if args.trim_max is not None and args.trim_max <= 1:
            raise InputError("--trim-max is a multiple of the mean weight and must be above 1 (5 is common)")
        if args.trim_min is not None and not 0 < args.trim_min < 1:
            raise InputError("--trim-min is a multiple of the mean weight between 0 and 1 (0.2 is common)")
        if args.scale_total is not None and not (math.isfinite(args.scale_total) and args.scale_total > 0):
            raise InputError("--scale-total is the population size the weights should add up to; it must be a "
                             "positive number")
        if args.trim_cycles < 1:
            raise InputError("--trim-cycles must be at least 1")
        result = analyse(args)
    except InputError as exc:
        print(f"survey-weighting: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
