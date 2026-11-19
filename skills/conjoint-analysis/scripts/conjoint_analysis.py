#!/usr/bin/env python3
"""Conjoint analysis: an aggregate multinomial logit for choice-based conjoint (CBC) data, with part-worths,
attribute importances, willingness to pay, AMCEs and marginal means, segment comparisons, counts and a
share-of-preference simulator.

Standard library only, Python 3.9+. No network. Deterministic for a given --seed.
Formulas, thresholds and citations: references/sources.md and references/input-formats.md.

Usage:
  python3 scripts/conjoint_analysis.py responses.csv --design design.csv
  python3 scripts/conjoint_analysis.py stacked.csv                      # one row per respondent x task x concept
  python3 scripts/conjoint_analysis.py responses.csv --design design.csv --price-attr "Price per week" \\
      --product "A: Brand=FreshBox; Meals per week=3; Price per week=$55" --product "B: Brand=HomeChef; ..."
  python3 scripts/conjoint_analysis.py stacked.csv --amce --segment plan --bootstrap 500 --json

Inputs (references/input-formats.md):
  design mode   --design: the file conjoint-design writes (version,task,concept,<attributes>, a "none" row per
                task when there is a none option), plus a responses file with the choices, either long
                (respondent,[version,]task,choice) or wide (respondent,[version,]task1..taskT). A choice is the
                concept label from the design ("1", "2", "Option 2") or "none".
  stacked mode  one row per respondent x task x concept: respondent,task,[version,]concept,<attributes>,chosen
                (chosen 1 on the picked row; a none row has concept "none" and blank attributes).

Model: conditional (multinomial) logit, dummy-coded part-worths (first level = reference), an alternative-
specific constant for "none", optional linear price; Newton-Raphson with step halving (as in this pack's
maxdiff-analysis). Part-worths are reported zero-centered within each attribute. Intervals: cluster-robust
(respondent) sandwich covariance and the delta method by default; --bootstrap N adds percentile intervals
from resampling respondents (each replicate refits from the full-sample estimate).

Exit codes: 0 success; 2 bad input (the message says what to fix); 3 the logit has no finite estimate or did
not converge.
"""
import argparse
import csv
import io
import itertools
import json
import math
import os
import random
import re
import sys
import time
from statistics import NormalDist

VERSION = "0.1.0"

# Thresholds and defaults. Each one is listed with its source in references/sources.md.
STUDY_FLOOR = 300  # Sawtooth rule of thumb: 300 respondents per study
SUBGROUP_FLOOR = 200  # ... and 200 per reported subgroup
MIN_RESPONDENTS_FOR_ROBUST = 2  # a cluster-robust covariance needs at least two clusters
DEFAULT_SEED = 20261119  # arbitrary fixed default so runs repeat
MAX_ITERATIONS = 100  # Newton-Raphson cap (implementation constant)
STEP_TOLERANCE = 1e-9  # largest Newton step at convergence (implementation constant)
GRADIENT_TOLERANCE = 1e-7  # largest score per choice task at convergence (implementation constant)
MAX_HALVINGS = 40  # step-halving cap (implementation constant)
SEPARATION_BOUND = 25.0  # a |utility difference| this large means the estimate is running off to infinity
MAX_EXCLUDED_SHARE = 0.05  # stop when more than 5% of tasks cannot be used (convention of this pack)
MAX_FAILED_REPLICATE_SHARE = 0.05  # withhold bootstrap intervals above this share of failed refits
CRAMER_V_WARN = 0.10  # AMCE: warn when shown attributes are associated beyond this (convention of this skill)
# Column names never read as attributes (kept identical in conjoint-design, which refuses them as attribute names).
RESERVED = {"version", "block", "task", "set", "concept", "alt", "alternative", "respondent", "respondent_id",
            "resp.id", "id", "responseid", "response_id", "rid", "chosen", "choice", "segment", "weight", "ques"}
DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|", "\\t": "\t"}
# Concept labels that mean the opt-out (kept identical in conjoint-design). "0" is not one: 0-based concept numbers
# are ordinary concepts. A row with every attribute cell blank is the none option whatever its label, and a choice
# of "0" means none only in a task that has no concept 0.
NONE_LABELS = {"none", "none of these", "no choice", "neither", "opt-out", "opt out"}
CHOSEN_TRUE = {"1", "1.0", "true", "yes", "y", "x"}
CHOSEN_FALSE = {"0", "0.0", "false", "no", "n", ""}
TASK_WIDE_RE = re.compile(r"^(task|t|choice|cbc|q)[ _-]?(\d+)$", re.I)
TASK_WIDE_PRIORITY = ["task", "cbc", "choice", "t", "q"]  # when several families match, the first one wins
# A number in a level: "1,299" (a comma followed by exactly three digits) is a thousands separator, "4,5" a decimal
# comma; a minus sign counts only when it does not follow a letter or digit ("Plan-2" is 2, "-5" is -5).
NUMBER_RE = re.compile(r"(?:(?<![\w.,])-)?(?<![\d.,])(?:\d{1,3}(?:,\d{3})+(?!\d)(?:\.\d+)?|\d+(?:[.,]\d+)?)")
OVERLAP_RATIO_WARN = 0.8  # AMCE: warn when within-task level overlap is under 80% of independent draws (convention)


class InputError(Exception):
    """The input cannot be analyzed as given (exit code 2)."""


class EstimationError(Exception):
    """No finite maximum-likelihood estimate, or no convergence (exit code 3)."""


# --------------------------------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------------------------------


def decode(data, path):
    try:
        if data.startswith(b"\xef\xbb\xbf"):
            return data[3:].decode("utf-8"), "UTF-8 with BOM"
        if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
            return data.decode("utf-16"), "UTF-16"
        if data[:200].count(b"\x00") > 20:
            raise InputError(f"{path} looks like UTF-16 without a byte-order mark; re-export it as CSV UTF-8")
        return data.decode("utf-8"), "UTF-8"
    except UnicodeDecodeError as exc:
        raise InputError(f"{path} is not valid UTF-8 or UTF-16 text (byte {exc.start}); re-export it as 'CSV UTF-8'")


def read_bytes(path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except FileNotFoundError:
        raise InputError(f"file not found: {path}")
    except IsADirectoryError:
        raise InputError(f"{path} is a folder, not a file")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}")


def sniff_delimiter(text):
    best, best_key = ",", None
    for delim in (",", ";", "\t", "|"):
        try:
            # Records, not lines: a quoted cell may hold a line break (Qualtrics question text).
            rows = [r for r in itertools.islice(csv.reader(io.StringIO(text, newline=""), delimiter=delim), 60)
                    if any(c.strip() for c in r)][:50]
        except csv.Error:
            continue
        if not rows:
            continue
        width = len(rows[0])
        key = (width > 1, sum(1 for r in rows if len(r) == width), width)
        if best_key is None or key > best_key:
            best, best_key = delim, key
    return best


def read_table(path, delimiter=None, skip_rows=None, notes=None, flag="--delimiter"):
    """(headers, rows as dicts). BOMs, UTF-16, CRLF, sniffed delimiter, Qualtrics header rows; stops on
    duplicate column names and on rows of the wrong width."""
    notes = notes if notes is not None else []
    text, encoding = decode(read_bytes(path), path)
    if encoding != "UTF-8":
        notes.append(f"{os.path.basename(path)} read as {encoding}.")
    if delimiter:
        delim = DELIMITERS.get(delimiter.lower(), delimiter)
        if len(delim) != 1:
            raise InputError(f"{flag} takes one character or comma, semicolon, tab, pipe; got {delimiter!r}")
    else:
        delim = sniff_delimiter(text)
    try:
        table = [row for row in csv.reader(io.StringIO(text, newline=""), delimiter=delim)
                 if any(cell.strip() for cell in row)]
    except csv.Error as exc:
        raise InputError(f"{path} is not valid CSV: {exc}")
    if not table:
        raise InputError(f"{path} is empty or has no header row")
    headers = [h.strip() for h in table[0]]
    repeated = sorted({h for h in headers if headers.count(h) > 1})
    if repeated:
        raise InputError(f"{path} has more than one column named {', '.join(repr(h) for h in repeated)}. "
                         "Rename them so each column is unique.")
    body = table[1:]
    if skip_rows is not None and skip_rows < 0:
        raise InputError("--skip-rows must be 0 or more")
    if skip_rows is None:
        if len(body) >= 2 and any(cell.strip().startswith('{"ImportId"') for cell in body[1]):
            skip_rows = 2
            notes.append(f"{os.path.basename(path)}: Qualtrics export detected; skipped the question-text and "
                         "ImportId rows.")
        else:
            skip_rows = 0
    rows = []
    for index, row in enumerate(body[skip_rows:], start=2 + skip_rows):
        if len(row) > len(headers) and not any(c.strip() for c in row[len(headers):]):
            row = row[: len(headers)]
        if len(row) != len(headers):
            raise InputError(f"{path} row {index} has {len(row)} cells but the header has {len(headers)}; a row may "
                             "be cut or shifted, so values would land in the wrong columns. Fix the file or pass "
                             f"{flag}.")
        rows.append(dict(zip(headers, (c.strip() for c in row))))
    if not rows:
        raise InputError(f"{path} has a header but no data rows (n = 0)")
    return headers, rows


def find_col(headers, wanted, flag, required=True):
    """A column by an explicit name, or the first header matching one of the candidate names."""
    if isinstance(wanted, str):
        if wanted in headers:
            return wanted
        # A name the user typed must exist, required or not: a typo must not silently switch the layout.
        raise InputError(f"column {wanted!r} ({flag}) not found. Columns: {', '.join(headers)}")
    lower = {h.lower(): h for h in headers}
    for w in wanted:
        if w in lower:
            return lower[w]
    if required:
        raise InputError(f"no {flag} column (looked for {', '.join(wanted)}); pass {flag}. "
                         f"Columns: {', '.join(headers)}")
    return None


def norm_label(text):
    """Version, task and concept labels: '2', '2.0' and 'Option 2' all mean 2; a none word means 'none'. '0' stays
    '0' (a 0-based concept number), as in conjoint-design."""
    t = (text or "").strip()
    if t.lower() in NONE_LABELS:
        return "none"
    if re.fullmatch(r"-?\d+(\.0+)?", t):
        return str(int(float(t)))
    m = re.fullmatch(r"(?:option|concept|alt(?:ernative)?|profile|card|product|choice)\s*[#:]?\s*(\d+)", t, re.I)
    if m:
        return str(int(m.group(1)))
    return t


def split_levels(rest):
    """Levels separated by '|', else ';', else ','. With commas, '1,299' (a digit, a comma, exactly three digits)
    is a thousands separator inside one level (the same rule as conjoint-design)."""
    if "|" in rest:
        parts = rest.split("|")
    elif ";" in rest:
        parts = rest.split(";")
    else:
        parts = re.split(r"(?<!\d),|,(?!\d{3}(?!\d))", rest)
    return [l.strip() for l in parts if l.strip()]


def parse_condition(text, where):
    cond = {}
    for part in re.split(r"\s*&\s*", text.strip()):
        if "=" not in part:
            raise InputError(f"{where}: write each condition as Attribute=level, joined by '&' (got {part!r})")
        name, level = part.split("=", 1)
        cond[name.strip()] = level.strip()
    return cond


def load_spec(path):
    """Attribute level order and prohibitions from a conjoint-design spec: JSON or 'Name: a | b | c' lines plus
    'prohibit: Attr=level & Other=level' lines."""
    text, _ = decode(read_bytes(path), path)
    out, prohibitions = [], []
    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise InputError(f"{path} is not valid JSON: {exc}")
        if not isinstance(data, dict) or not isinstance(data.get("attributes"), list):
            raise InputError(f"{path}: the JSON spec is an object with an 'attributes' list")
        for a in data["attributes"]:
            if not isinstance(a, dict) or "name" not in a or not isinstance(a.get("levels"), list):
                raise InputError(f"{path}: each attribute needs a name and a list of levels")
            out.append((str(a["name"]).strip(), [str(l).strip() for l in a["levels"]]))
        for pr in data.get("prohibitions") or []:
            if not isinstance(pr, dict):
                raise InputError(f"{path}: each prohibition is an object of attribute: level")
            prohibitions.append({str(k).strip(): str(v).strip() for k, v in pr.items()})
    else:
        for number, line in enumerate(text.splitlines(), start=1):
            line = line.strip().lstrip("-*").strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"prohibit\s*:", line, re.I)
            if m:
                prohibitions.append(parse_condition(line[m.end():], f"{path} line {number}"))
                continue
            if ":" not in line:
                continue
            name, rest = line.split(":", 1)
            out.append((name.strip(), split_levels(rest)))
    if not out:
        raise InputError(f"{path}: no attributes found")
    levels = dict(out)
    for pr in prohibitions:
        for a, l in pr.items():
            if a not in levels or l not in levels[a]:
                raise InputError(f"{path}: prohibition names {a}={l}, which is not an attribute level of the spec")
    return out, prohibitions


def numbers_in(text):
    """Every number in a level or price, as floats: '$1,299' -> [1299.0], '4,5' -> [4.5], '$40-$70' -> [40, 70]."""
    out = []
    for token in NUMBER_RE.findall((text or "").replace("\u00a0", " ")):
        if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?", token):
            out.append(float(token.replace(",", "")))
        else:
            out.append(float(token.replace(",", ".")))
    return out


def level_number(text):
    """The one number in a level, or None when it has none or several."""
    found = numbers_in(text)
    return found[0] if len(found) == 1 else None


def natural_key(level):
    value = level_number(level)
    if value is not None:
        return (0, value, level)
    return (1, 0.0, level)


class Data:
    def __init__(self):
        self.attrs = []
        self.levels = {}
        self.respondents = {}  # rid -> {"segment": str or None, "tasks": [(alts, chosen_index)]}
        self.has_none = False
        self.prohibitions = []
        self.counts = {"respondents_read": 0, "tasks_read": 0, "tasks_used": 0, "excluded": {}}
        self.notes = []

    def exclude(self, reason):
        self.counts["excluded"][reason] = self.counts["excluded"].get(reason, 0) + 1


def load(args):
    data = Data()
    spec = None
    if args.spec:
        spec_attrs, data.prohibitions = load_spec(args.spec)
        spec = dict(spec_attrs)
        args._spec_order = [a for a, _ in spec_attrs]
    if args.design:
        load_design_mode(args, data)
    else:
        load_stacked_mode(args, data)
    if not data.respondents:
        raise InputError("no usable choice tasks (n = 0)")
    for a in data.attrs:
        if len(data.levels[a]) < 2:
            raise InputError(f"attribute {a!r} shows only one level; it cannot be estimated. Remove it with "
                             "--attribute-cols")
    if spec:
        for a in data.attrs:
            if a not in spec:
                raise InputError(f"attribute {a!r} is not in the spec {args.spec}")
            extra = [l for l in data.levels[a] if l not in spec[a]]
            if extra:
                raise InputError(f"{a}: levels in the data but not in the spec: {', '.join(extra)}")
            data.levels[a] = list(spec[a])
    else:
        for a in data.attrs:
            data.levels[a] = sorted(data.levels[a], key=natural_key)
    excluded = sum(data.counts["excluded"].values())
    total = data.counts["tasks_read"]
    if total and excluded / total > MAX_EXCLUDED_SHARE and not args.allow_exclusions:
        reasons = ", ".join(f"{k} {v}" for k, v in data.counts["excluded"].items())
        raise InputError(f"{excluded} of {total} tasks ({excluded / total:.0%}) cannot be used ({reasons}). That many "
                         "usually means a wrong column, version or choice coding. Fix the mapping, or pass "
                         "--allow-exclusions to analyze the rest")
    return data


def pick_attributes(args, headers, structural, data, path):
    """Attribute columns: --attribute-cols, else the spec's attributes, else every column that is not structural
    or reserved (each reserved column skipped is named in a note)."""
    if args.attribute_cols:
        attrs = [c.strip() for c in args.attribute_cols.split(",") if c.strip()]
        for c in attrs:
            find_col(headers, c, "--attribute-cols")
        return attrs
    spec_order = getattr(args, "_spec_order", None)
    if spec_order:
        missing = [a for a in spec_order if a not in headers]
        if missing:
            raise InputError(f"{path} has no column for spec attribute(s) {', '.join(missing)}. Columns: "
                             f"{', '.join(headers)}")
        others = [h for h in headers if h not in structural and h not in spec_order and h.lower() not in RESERVED]
        if others:
            data.notes.append(f"Columns not in the spec, not read as attributes: {', '.join(others)}.")
        return list(spec_order)
    attrs = [h for h in headers if h not in structural and h.lower() not in RESERVED]
    skipped = [h for h in headers if h not in structural and h.lower() in RESERVED]
    if skipped:
        data.notes.append(f"Column(s) {', '.join(skipped)} have reserved names and were not read as attributes; "
                          "name them in --attribute-cols if they are attributes.")
    return attrs


def zero_coded_none(rows, attrs):
    """True when some rows have '0' in every attribute cell and '0' appears in no other row: Sawtooth writes its
    none concept that way."""
    zero_rows = 0
    for r in rows:
        cells = [r[a] for a in attrs]
        if all(c == "0" for c in cells):
            zero_rows += 1
        elif any(c == "0" for c in cells):
            return False
    return zero_rows > 0


def is_none_row(label, cells, zero_none, where):
    """The shared none rule (conjoint-design uses the same): a none word as the concept label, or every attribute
    cell blank (or '0' in a Sawtooth-style file). A none word with levels filled in is an error."""
    blank = all(not c for c in cells) or (zero_none and all(c == "0" for c in cells))
    if label == "none" and not blank:
        raise InputError(f"{where} is labelled as the none option but has attribute levels; blank them or relabel "
                         "the concept")
    return blank or label == "none"


def load_design_mode(args, data):
    dheaders, drows = read_table(args.design, args.design_delimiter, None, data.notes, "--design-delimiter")
    tcol = find_col(dheaders, ["task", "set", "ques", "question"], "--design task column")
    ccol = find_col(dheaders, ["concept", "alt", "alternative", "option", "profile"], "--design concept column")
    vcol = find_col(dheaders, ["version", "block"], "version", required=False)
    attrs = pick_attributes(args, dheaders, (tcol, ccol, vcol), data, args.design)
    if not attrs:
        raise InputError(f"{args.design} has no attribute columns besides version, task and concept")
    data.attrs = attrs
    data.levels = {a: [] for a in attrs}
    zero_none = zero_coded_none(drows, attrs)
    if zero_none:
        data.notes.append("Design rows with 0 in every attribute read as the none option (Sawtooth coding).")
    design = {}
    for r in drows:
        key = (norm_label(r[vcol]) if vcol else "1", norm_label(r[tcol]))
        concept = norm_label(r[ccol])
        cells = tuple(r[a] for a in attrs)
        where = f"{args.design}: version {key[0]} task {key[1]} concept {r[ccol]!r}"
        if is_none_row(concept, cells, zero_none, where):
            if any(lab == "none" for lab, _ in design.get(key, [])):
                raise InputError(f"{args.design}: version {key[0]} task {key[1]} has more than one none row")
            design.setdefault(key, []).append(("none", None))
            continue
        if any(not c for c in cells):
            raise InputError(f"{where} has a blank level")
        for a, c in zip(attrs, cells):
            if c not in data.levels[a]:
                data.levels[a].append(c)
        if any(lab == concept for lab, _ in design.get(key, [])):
            raise InputError(f"{args.design}: version {key[0]} task {key[1]} lists concept {concept} twice, so a "
                             "recorded choice could not say which profile was picked")
        design.setdefault(key, []).append((concept, cells))
    for key, alts in design.items():
        if sum(1 for lab, _ in alts if lab != "none") < 2:
            raise InputError(f"{args.design}: version {key[0]} task {key[1]} has fewer than two concepts")
    if args.none_when_missing_row:
        added = 0
        for key, alts in design.items():
            if not any(lab == "none" for lab, _ in alts):
                alts.append(("none", None))
                added += 1
        if added:
            data.notes.append(f"--none-when-missing-row: a none option added to {added} design tasks (every task "
                              "without one), chosen only where the response says none.")
    versions = {k[0] for k in design}

    headers, rows = read_table(args.input, args.delimiter, args.skip_rows, data.notes)
    rcol = find_col(headers, args.respondent_col or ["respondent", "respondent_id", "id", "resp.id", "responseid",
                                                     "response_id", "rid"], "--respondent-col")
    rvcol = find_col(headers, args.version_col or ["version", "block"], "--version-col", required=False)
    scol = find_col(headers, args.segment, "--segment") if args.segment else None
    if len(versions) > 1 and not rvcol:
        raise InputError(f"the design has {len(versions)} versions but the responses have no version column; pass "
                         "--version-col")
    only_version = next(iter(versions)) if len(versions) == 1 else None
    long_task = find_col(headers, args.task_col or ["task", "set", "ques"], "--task-col", required=False)
    choice_col = find_col(headers, args.choice_col or ["choice", "chosen_concept", "answer", "selected"],
                          "--choice-col", required=False)
    if long_task and choice_col:
        entries = [(r, norm_label(r[long_task]), r[choice_col]) for r in rows]
        data.notes.append(f"Responses read as long: {rcol}, {long_task}, {choice_col}.")
    else:
        families = {}
        for h in headers:
            m = TASK_WIDE_RE.match(h)
            if m:
                families.setdefault(m.group(1).lower(), {})[h] = str(int(m.group(2)))
        if not families:
            raise InputError("the responses file has neither task and choice columns (long) nor task1..taskN columns "
                             f"(wide). Pass --task-col and --choice-col. Columns: {', '.join(headers)}")
        family = next(f for f in TASK_WIDE_PRIORITY if f in families)
        wide = families[family]
        ignored = [h for f, cols in families.items() if f != family for h in cols]
        entries = [(r, t, r[h]) for r in rows for h, t in wide.items()]
        data.notes.append(f"Responses read as wide: {len(wide)} task columns ({', '.join(list(wide)[:4])}...)."
                          + (f" Not read as tasks: {', '.join(ignored[:6])}." if ignored else ""))
    seen = set()
    for r, task, raw in entries:
        rid = r[rcol]
        if not rid:
            data.counts["tasks_read"] += 1
            data.exclude("no respondent id")
            continue
        version = norm_label(r[rvcol]) if rvcol else only_version
        resp = data.respondents.setdefault(rid, {"segment": r[scol] if scol else None, "tasks": [],
                                                 "version": version})
        if scol and resp["segment"] != r[scol]:
            raise InputError(f"respondent {rid!r} has more than one value of {scol!r}; a segment must be fixed per "
                             "respondent")
        if not (raw or "").strip():
            continue  # task not shown or not answered: not a choice
        data.counts["tasks_read"] += 1
        if (rid, task) in seen:
            data.exclude("same respondent and task twice")
            continue
        seen.add((rid, task))
        key = (version, task)
        if key not in design:
            data.exclude("version and task not in the design")
            continue
        alts = design[key]
        labels = [lab for lab, _ in alts]
        choice = norm_label(raw)
        if choice == "0" and "0" not in labels:
            choice = "none"  # '0' is none only in a task with no concept 0
        if choice == "none" and "none" not in labels:
            data.exclude("chose none but the design has no none row")
            continue
        if choice not in labels:
            data.exclude("choice is not a concept of that task")
            continue
        if "none" in labels:
            data.has_none = True
        resp["tasks"].append((tuple(cells for _, cells in alts), labels.index(choice)))
        data.counts["tasks_used"] += 1
    data.respondents = {k: v for k, v in data.respondents.items() if v["tasks"]}
    data.counts["respondents_read"] = len({r[rcol] for r in rows if r[rcol]})


def load_stacked_mode(args, data):
    headers, rows = read_table(args.input, args.delimiter, args.skip_rows, data.notes)
    rcol = find_col(headers, args.respondent_col or ["respondent", "respondent_id", "id", "resp.id", "responseid",
                                                     "response_id", "rid"], "--respondent-col")
    tcol = find_col(headers, args.task_col or ["task", "set", "ques", "question"], "--task-col")
    ccol = find_col(headers, args.concept_col or ["concept", "alt", "alternative", "option", "profile"],
                    "--concept-col", required=False)
    chcol = find_col(headers, args.chosen_col or ["chosen", "choice", "selected"], "--chosen-col")
    vcol = find_col(headers, args.version_col or ["version", "block"], "--version-col", required=False)
    scol = find_col(headers, args.segment, "--segment") if args.segment else None
    attrs = pick_attributes(args, headers, {rcol, tcol, ccol, chcol, vcol, scol}, data, args.input)
    if not attrs:
        raise InputError("no attribute columns found; pass --attribute-cols")
    data.attrs = attrs
    data.levels = {a: [] for a in attrs}
    zero_none = zero_coded_none(rows, attrs)
    if zero_none:
        data.notes.append("Rows with 0 in every attribute read as the none option (Sawtooth coding).")
    groups = {}
    order = []
    for r in rows:
        key = (r[rcol], norm_label(r[vcol]) if vcol else "", norm_label(r[tcol]))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)
    data.notes.append(f"Stacked rows read: {rcol}, {tcol}, {chcol}; attributes {', '.join(attrs)}.")
    added_none = 0
    for key in order:
        rid = key[0]
        data.counts["tasks_read"] += 1
        if not rid:
            data.exclude("no respondent id")
            continue
        grp = groups[key]
        seg = grp[0][scol] if scol else None
        resp = data.respondents.setdefault(rid, {"segment": seg, "tasks": []})
        if scol and any(g[scol] != resp["segment"] for g in grp):
            raise InputError(f"respondent {rid!r} has more than one value of {scol!r}")
        profiles, chosen = [], []
        reason = None
        for g in grp:
            flag = g[chcol].strip().lower()
            if flag in CHOSEN_TRUE:
                pick = True
            elif flag in CHOSEN_FALSE:
                pick = False
            else:
                reason = "chosen is not 0/1"
                break
            cells = tuple(g[a] for a in attrs)
            label = norm_label(g[ccol]) if ccol else ""
            is_none = is_none_row(label, cells, zero_none, f"respondent {rid} task {key[2]} concept {label!r}")
            if not is_none and any(not c for c in cells):
                reason = "blank attribute level"
                break
            profiles.append(None if is_none else cells)
            chosen.append(pick)
        if reason:
            data.exclude(reason)
            continue
        if profiles.count(None) > 1:
            data.exclude("more than one none row")
            continue
        if args.none_when_missing_row and None not in profiles:
            # The none option was offered in every task: add it everywhere, chosen only where no concept was.
            profiles.append(None)
            chosen.append(sum(chosen) == 0)
            added_none += 1
        if sum(chosen) != 1:
            data.exclude("not exactly one chosen row")
            continue
        if len(profiles) < 2:
            data.exclude("fewer than two alternatives")
            continue
        if len(set(p for p in profiles if p is not None)) < sum(1 for p in profiles if p is not None):
            if len(data.notes) < 30:
                data.notes.append(f"Respondent {rid} task {key[2]} shows the same concept twice.")
        for p in profiles:
            if p is None:
                data.has_none = True
                continue
            for a, c in zip(attrs, p):
                if c not in data.levels[a]:
                    data.levels[a].append(c)
        resp["tasks"].append((tuple(profiles), chosen.index(True)))
        data.counts["tasks_used"] += 1
    if added_none:
        data.notes.append(f"--none-when-missing-row: a none option added to {added_none} tasks (every task without "
                          "a none row), chosen where no concept was.")
    data.respondents = {k: v for k, v in data.respondents.items() if v["tasks"]}
    data.counts["respondents_read"] = len({k[0] for k in order if k[0]})


# --------------------------------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------------------------------


class Model:
    """Parameter layout. Dummy-coded part-worths (first level = 0), optional linear attributes, none ASC."""

    def __init__(self, attrs, levels, linear, has_none):
        self.attrs = attrs
        self.levels = levels
        self.linear = {}
        self.center = {}
        self.code_like = []
        for a in linear:
            values = []
            for l in levels[a]:
                found = numbers_in(l)
                if len(found) != 1:
                    raise InputError(f"--price-attr/--linear {a!r}: level {l!r} has "
                                     + ("no number" if not found else f"{len(found)} numbers") +
                                     " in it; a linear attribute needs exactly one number per level ('$1,299' and "
                                     "'4,5' are one number each)")
                values.append(found[0])
            if len(set(values)) < 2:
                raise InputError(f"{a!r} needs at least two different numeric levels to be linear")
            self.linear[a] = dict(zip(levels[a], values))
            # Linear values are centered on their mean for fitting, so the none constant and the information
            # matrix do not depend on where the price scale starts (a $1,000 shift changes nothing).
            self.center[a] = sum(values) / len(values)
            ordered = sorted(values)
            if all(re.fullmatch(r"\d+", l.strip()) for l in levels[a]) and \
                    ordered in ([float(i) for i in range(1, len(values) + 1)], [float(i) for i in range(len(values))]):
                self.code_like.append(a)
        self.names = []
        self.index = {}
        for a in attrs:
            if a in self.linear:
                self.index[(a, None)] = len(self.names)
                self.names.append(f"{a} (per unit)")
            else:
                for l in levels[a][1:]:
                    self.index[(a, l)] = len(self.names)
                    self.names.append(f"{a}: {l}")
        self.none_index = None
        if has_none:
            self.none_index = len(self.names)
            self.names.append("None")
        self.p = len(self.names)
        # Size of a one-unit change on the utility scale, used to detect estimates running off to infinity.
        self.scale = [1.0] * self.p
        for a, vals in self.linear.items():
            self.scale[self.index[(a, None)]] = max(vals.values()) - min(vals.values())
        self._cache = {}

    def encode(self, profile):
        """Sparse x for one alternative: list of (index, value)."""
        if profile is None:
            return ((self.none_index, 1.0),)
        hit = self._cache.get(profile)
        if hit is not None:
            return hit
        x = []
        for a, l in zip(self.attrs, profile):
            if a in self.linear:
                x.append((self.index[(a, None)], self.linear[a][l] - self.center[a]))
            elif l != self.levels[a][0]:
                x.append((self.index[(a, l)], 1.0))
        x = tuple(x)
        self._cache[profile] = x
        return x

    def utility_of(self, beta, profile_dict):
        """Utility of a product given as {attr: level or number}."""
        v = 0.0
        for a in self.attrs:
            val = profile_dict[a]
            if a in self.linear:
                v += beta[self.index[(a, None)]] * (float(val) - self.center[a])
            elif val != self.levels[a][0]:
                v += beta[self.index[(a, val)]]
        return v


def pool_tasks(model, respondents, rids):
    """Identical tasks (same alternatives in the same order) pooled: list of (xs, counts, total)."""
    pooled = {}
    for rid in rids:
        for alts, chosen in respondents[rid]["tasks"]:
            entry = pooled.get(alts)
            if entry is None:
                entry = [0] * len(alts)
                pooled[alts] = entry
            entry[chosen] += 1
    out = []
    for alts, counts in pooled.items():
        out.append(([model.encode(a) for a in alts], counts, sum(counts)))
    return out


def evaluate(beta, tasks, p, derivatives=True):
    loglik = 0.0
    grad = [0.0] * p if derivatives else None
    info = [[0.0] * p for _ in range(p)] if derivatives else None
    for xs, counts, total in tasks:
        vs = [sum(beta[i] * v for i, v in x) for x in xs]
        top = max(vs)
        ws = [math.exp(v - top) for v in vs]
        s = sum(ws)
        logs = top + math.log(s)
        for v, c in zip(vs, counts):
            if c:
                loglik += c * (v - logs)
        if not derivatives:
            continue
        probs = [w / s for w in ws]
        mean = {}
        for x, pr in zip(xs, probs):
            for i, v in x:
                mean[i] = mean.get(i, 0.0) + pr * v
        for x, c in zip(xs, counts):
            if c:
                for i, v in x:
                    grad[i] += c * v
        for i, m in mean.items():
            grad[i] -= total * m
        for x, pr in zip(xs, probs):
            w = total * pr
            for i, vi in x:
                row = info[i]
                for j, vj in x:
                    row[j] += w * vi * vj
        items = list(mean.items())
        for i, mi in items:
            row = info[i]
            for j, mj in items:
                row[j] -= total * mi * mj
    return loglik, grad, info


def cholesky(matrix):
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
    n = len(lower)
    y = [0.0] * n
    for i in range(n):
        y[i] = (rhs[i] - sum(lower[i][m] * y[m] for m in range(i))) / lower[i][i]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (y[i] - sum(lower[m][i] * x[m] for m in range(i + 1, n))) / lower[i][i]
    return x


def invert(matrix):
    lower = cholesky(matrix)
    if lower is None:
        return None
    n = len(matrix)
    cols = [cholesky_solve(lower, [1.0 if r == c else 0.0 for r in range(n)]) for c in range(n)]
    return [[cols[c][r] for c in range(n)] for r in range(n)]


def fit(tasks, p, start=None, n_tasks=None, unit_scale=None):
    """Maximum-likelihood MNL by Newton-Raphson with step halving. Raises EstimationError."""
    beta = list(start) if start else [0.0] * p
    n_tasks = n_tasks or sum(t for _, _, t in tasks)
    loglik, grad, info = evaluate(beta, tasks, p)
    for iteration in range(1, MAX_ITERATIONS + 1):
        lower = cholesky(info)
        if lower is None:
            # Positive definite at the start but not now: the estimate is running off to infinity.
            raise EstimationError("separation" if iteration > 1 else "singular")
        step = cholesky_solve(lower, grad)
        scale = 1.0
        trial = [b + s for b, s in zip(beta, step)]
        t_ll, t_grad, t_info = evaluate(trial, tasks, p)
        if t_ll < loglik - 1e-12 * abs(loglik):
            for _ in range(MAX_HALVINGS):
                scale /= 2.0
                trial = [b + scale * s for b, s in zip(beta, step)]
                t_ll = evaluate(trial, tasks, p, False)[0]
                if t_ll >= loglik - 1e-12 * abs(loglik):
                    break
            else:
                raise EstimationError("no_ascent")
            t_ll, t_grad, t_info = evaluate(trial, tasks, p)
        beta, loglik, grad, info = trial, t_ll, t_grad, t_info
        if max(abs(b) * (unit_scale[i] if unit_scale else 1.0) for i, b in enumerate(beta)) > SEPARATION_BOUND:
            raise EstimationError("separation")
        if max(abs(scale * s) for s in step) < STEP_TOLERANCE and max(abs(g) for g in grad) < GRADIENT_TOLERANCE * n_tasks:
            return {"beta": beta, "loglik": loglik, "info": info, "iterations": iteration}
    raise EstimationError("no_convergence")


def respondent_scores(model, respondents, rids, beta):
    """Each respondent's score vector (sum over their tasks of x_chosen - E[x]) at beta."""
    out = []
    for rid in rids:
        g = [0.0] * model.p
        for alts, chosen in respondents[rid]["tasks"]:
            xs = [model.encode(a) for a in alts]
            vs = [sum(beta[i] * v for i, v in x) for x in xs]
            top = max(vs)
            ws = [math.exp(v - top) for v in vs]
            s = sum(ws)
            for i, v in xs[chosen]:
                g[i] += v
            for x, w in zip(xs, ws):
                pr = w / s
                for i, v in x:
                    g[i] -= pr * v
        out.append(g)
    return out


def robust_cov(h_inv, scores):
    """Cluster-robust sandwich H^-1 (G/(G-1) sum g g') H^-1, clusters = respondents."""
    p = len(h_inv)
    g_count = len(scores)
    meat = [[0.0] * p for _ in range(p)]
    for g in scores:
        nz = [(i, v) for i, v in enumerate(g) if v != 0.0]
        for i, vi in nz:
            row = meat[i]
            for j, vj in nz:
                row[j] += vi * vj
    factor = g_count / (g_count - 1.0)
    tmp = [[sum(h_inv[i][k] * meat[k][j] for k in range(p)) for j in range(p)] for i in range(p)]
    return [[factor * sum(tmp[i][k] * h_inv[k][j] for k in range(p)) for j in range(p)] for i in range(p)]


def describe_error(kind, model, data, rids=None):
    if kind == "separation":
        never, always = [], []
        shown = {}
        chosen = {}
        for rid in (rids if rids is not None else list(data.respondents)):
            for alts, c in data.respondents[rid]["tasks"]:
                for k, prof in enumerate(alts):
                    if prof is None:
                        shown[("None", "")] = shown.get(("None", ""), 0) + 1
                        if k == c:
                            chosen[("None", "")] = chosen.get(("None", ""), 0) + 1
                        continue
                    for a, l in zip(model.attrs, prof):
                        shown[(a, l)] = shown.get((a, l), 0) + 1
                        if k == c:
                            chosen[(a, l)] = chosen.get((a, l), 0) + 1
        for key, n in shown.items():
            label = "the none option" if key[0] == "None" else f"{key[0]}={key[1]}"
            if chosen.get(key, 0) == 0:
                never.append(label)
            elif chosen.get(key, 0) == n:
                always.append(label)
        detail = ""
        if never:
            detail += " Never chosen: " + ", ".join(never[:8]) + "."
        if always:
            detail += " Always chosen when shown: " + ", ".join(always[:8]) + "."
        return ("no finite maximum-likelihood estimate: some utilities run off to infinity (separation)." + detail +
                " Collect more answers, merge the level with a neighbor, or report counts (--counts-only).")
    if kind == "singular":
        return ("the information matrix is singular: some effects are not identified (a level never shown, two "
                "attributes that always move together, or a linear attribute with one value per task)")
    if kind == "no_ascent":
        return "Newton-Raphson could not increase the likelihood (step halving exhausted)"
    return f"Newton-Raphson did not converge in {MAX_ITERATIONS} iterations"


# --------------------------------------------------------------------------------------------------
# Derived quantities
# --------------------------------------------------------------------------------------------------


def part_worths(model, beta):
    """Zero-centered part-worths per attribute, the centered none utility, and importances (as a dict)."""
    out = {}
    ranges = {}
    centre_total = 0.0
    for a in model.attrs:
        if a in model.linear:
            b = beta[model.index[(a, None)]]
            vals = model.linear[a]
            u = {l: b * (v - model.center[a]) for l, v in vals.items()}
        else:
            raw = {l: (0.0 if l == model.levels[a][0] else beta[model.index[(a, l)]]) for l in model.levels[a]}
            m = sum(raw.values()) / len(raw)
            u = {l: v - m for l, v in raw.items()}
            centre_total += m
        out[a] = u
        ranges[a] = max(u.values()) - min(u.values())
    total = sum(ranges.values())
    importance = {a: (100.0 * r / total if total > 0 else None) for a, r in ranges.items()}
    none_u = (beta[model.none_index] - centre_total) if model.none_index is not None else None
    return out, importance, none_u


def flatten(model, beta, extra=None):
    """All reported quantities of interest as one flat dict name -> value (for the delta method/bootstrap)."""
    pw, imp, none_u = part_worths(model, beta)
    flat = {}
    for a, u in pw.items():
        for l, v in u.items():
            flat[("pw", a, l)] = v
        if imp[a] is not None:
            flat[("imp", a)] = imp[a]
    if none_u is not None:
        flat[("none",)] = none_u
    if extra:
        flat.update(extra(beta))
    return flat


def delta_intervals(func, beta, cov, z, scale=None):
    """Delta-method standard errors and normal intervals for every value func(beta) returns. The difference step
    is relative to each parameter's size on the utility scale (a per-dollar price effect of 1e-6 gets a step far
    below it). Shares and importances are percentages, so their intervals are cut at 0 and 100."""
    base = func(beta)
    p = len(beta)
    grads = {k: [0.0] * p for k in base}
    for i in range(p):
        unit = 1.0 / scale[i] if scale and scale[i] > 0 else 1.0
        h = 1e-6 * max(unit, abs(beta[i]))
        up = list(beta)
        dn = list(beta)
        up[i] += h
        dn[i] -= h
        fu, fd = func(up), func(dn)
        for k in base:
            if k in fu and k in fd and grads[k] is not None:
                grads[k][i] = (fu[k] - fd[k]) / (2 * h)
            else:
                grads[k] = None
    out = {}
    for k, v in base.items():
        g = grads[k]
        if g is None:
            out[k] = (v, None, None, None)
            continue
        var = sum(g[i] * cov[i][j] * g[j] for i in range(p) for j in range(p) if g[i] and g[j])
        se = math.sqrt(max(var, 0.0))
        low, high = v - z * se, v + z * se
        if k[0] in ("share", "imp"):
            low, high = max(low, 0.0), min(high, 100.0)
        out[k] = (v, se, low, high)
    return out


def wtp_values(model, price_attr):
    def f(beta):
        b = beta[model.index[(price_attr, None)]]
        out = {}
        if b >= 0:
            return out  # no willingness to pay without a negative price effect (a bootstrap resample may hit this)
        for a in model.attrs:
            if a == price_attr:
                continue
            if a in model.linear:
                out[("wtp", a, "per unit")] = -beta[model.index[(a, None)]] / b
                continue
            for l in model.levels[a][1:]:
                out[("wtp", a, l)] = -beta[model.index[(a, l)]] / b
        return out
    return f


def parse_products(specs, model, data, price_attr):
    products = []
    for spec in specs:
        name, _, body = spec.partition(":")
        if not body.strip():
            raise InputError(f"--product {spec!r}: write 'Name: Attr=level; Attr=level'")
        prof = {}
        for part in re.split(r";|\|", body):
            if not part.strip():
                continue
            if "=" not in part:
                raise InputError(f"--product {name.strip()!r}: {part.strip()!r} is not Attr=level")
            a, l = part.split("=", 1)
            a, l = a.strip(), l.strip()
            if a not in model.attrs:
                raise InputError(f"--product {name.strip()!r}: unknown attribute {a!r}; attributes: "
                                 + ", ".join(model.attrs))
            if a in model.linear:
                if l in model.linear[a]:
                    prof[a] = model.linear[a][l]
                else:
                    found = numbers_in(l)
                    if len(found) != 1:
                        raise InputError(f"--product {name.strip()!r}: {a} needs one number, got {l!r}")
                    value = found[0]
                    lo, hi = min(model.linear[a].values()), max(model.linear[a].values())
                    if not lo <= value <= hi:
                        raise InputError(f"--product {name.strip()!r}: {a} = {value:g} is outside the tested range "
                                         f"{lo:g} to {hi:g}; a logit model cannot extrapolate")
                    prof[a] = value
            else:
                if l not in model.levels[a]:
                    raise InputError(f"--product {name.strip()!r}: {a} has no level {l!r}; levels: "
                                     + ", ".join(model.levels[a]) +
                                     (". Use --price-attr to allow prices between tested levels." if a == price_attr
                                      else ""))
                prof[a] = l
        missing = [a for a in model.attrs if a not in prof]
        if missing:
            raise InputError(f"--product {name.strip()!r} does not set {', '.join(missing)}")
        for rule in data.prohibitions:
            if all(a in prof and (level_number(l) == prof[a] if a in model.linear else prof[a] == l)
                   for a, l in rule.items()):
                raise InputError(f"--product {name.strip()!r} is a prohibited combination in the spec ("
                                 + " & ".join(f"{a}={l}" for a, l in rule.items()) + "): it cannot exist, so it "
                                 "gets no share")
        products.append((name.strip(), prof))
    names = [n for n, _ in products]
    if len(set(names)) != len(names):
        raise InputError("two --product entries have the same name")
    if any(n.lower() == "none" for n in names):
        raise InputError("a --product cannot be named 'None': that name is the none option in the simulator")
    return products


def share_values(model, products, include_none):
    def f(beta):
        vs = [model.utility_of(beta, prof) for _, prof in products]
        if include_none:
            vs.append(beta[model.none_index])
        top = max(vs)
        ws = [math.exp(v - top) for v in vs]
        s = sum(ws)
        out = {("share", n): 100.0 * w / s for (n, _), w in zip(products, ws)}
        if include_none:
            out[("share", "None")] = 100.0 * ws[-1] / s
        return out
    return f


# --------------------------------------------------------------------------------------------------
# Counts, AMCE, marginal means
# --------------------------------------------------------------------------------------------------


def counts_analysis(model, data, rids):
    shown, chosen = {}, {}
    none_tasks = none_chosen = 0
    for rid in rids:
        for alts, c in data.respondents[rid]["tasks"]:
            for k, prof in enumerate(alts):
                if prof is None:
                    none_tasks += 1
                    none_chosen += 1 if k == c else 0
                    continue
                for a, l in zip(model.attrs, prof):
                    shown[(a, l)] = shown.get((a, l), 0) + 1
                    if k == c:
                        chosen[(a, l)] = chosen.get((a, l), 0) + 1
    out = {}
    for a in model.attrs:
        out[a] = {l: {"shown": shown.get((a, l), 0), "chosen": chosen.get((a, l), 0),
                      "choice_rate": (chosen.get((a, l), 0) / shown[(a, l)]) if shown.get((a, l)) else None}
                  for l in model.levels[a]}
    return out, (none_chosen / none_tasks if none_tasks else None), none_tasks


def ols_cluster(rows_x, ys, clusters):
    """OLS with CR1 cluster-robust covariance (Stata small-sample factor). rows_x: dense lists."""
    k = len(rows_x[0])
    n = len(ys)
    xtx = [[0.0] * k for _ in range(k)]
    xty = [0.0] * k
    for x, y in zip(rows_x, ys):
        for i in range(k):
            if x[i]:
                xty[i] += x[i] * y
                for j in range(k):
                    if x[j]:
                        xtx[i][j] += x[i] * x[j]
    inv = invert(xtx)
    if inv is None:
        raise InputError("the AMCE regression is singular: a level is never shown, or levels always co-occur")
    b = [sum(inv[i][j] * xty[j] for j in range(k)) for i in range(k)]
    by = {}
    for x, y, c in zip(rows_x, ys, clusters):
        e = y - sum(bi * xi for bi, xi in zip(b, x))
        acc = by.setdefault(c, [0.0] * k)
        for i in range(k):
            if x[i]:
                acc[i] += x[i] * e
    g = len(by)
    meat = [[0.0] * k for _ in range(k)]
    for acc in by.values():
        for i in range(k):
            if acc[i]:
                for j in range(k):
                    meat[i][j] += acc[i] * acc[j]
    factor = (g / (g - 1.0)) * ((n - 1.0) / (n - k)) if g > 1 and n > k else float("nan")
    tmp = [[sum(inv[i][m] * meat[m][j] for m in range(k)) for j in range(k)] for i in range(k)]
    cov = [[factor * sum(tmp[i][m] * inv[m][j] for m in range(k)) for j in range(k)] for i in range(k)]
    return b, cov


def amce_analysis(model, data, rids, z):
    """AMCE by OLS of chosen on level dummies (concept rows only), and marginal means, both clustered by
    respondent (Hainmueller, Hopkins and Yamamoto 2014; Leeper, Hobolt and Tilley 2020)."""
    cols = [(a, l) for a in model.attrs for l in model.levels[a][1:]]
    pos = {c: i + 1 for i, c in enumerate(cols)}
    xs, ys, cl = [], [], []
    mm_rows = []
    for rid in rids:
        for alts, c in data.respondents[rid]["tasks"]:
            for k, prof in enumerate(alts):
                if prof is None:
                    continue
                x = [0.0] * (len(cols) + 1)
                x[0] = 1.0
                for a, l in zip(model.attrs, prof):
                    if (a, l) in pos:
                        x[pos[(a, l)]] = 1.0
                y = 1.0 if k == c else 0.0
                xs.append(x)
                ys.append(y)
                cl.append(rid)
                mm_rows.append((prof, y, rid))
    b, cov = ols_cluster(xs, ys, cl)
    amce = {}
    for (a, l), i in pos.items():
        if not math.isfinite(cov[i][i]):
            amce[(a, l)] = (b[i], None, None, None)  # one respondent: no clustered SE
            continue
        se = math.sqrt(max(cov[i][i], 0.0))
        amce[(a, l)] = (b[i], se, b[i] - z * se, b[i] + z * se)
    mm = {}
    for qi, a in enumerate(model.attrs):
        for l in model.levels[a]:
            sel = [(y, rid) for prof, y, rid in mm_rows if prof[qi] == l]
            n = len(sel)
            if not n:
                mm[(a, l)] = (None, None, None, None)
                continue
            mean = sum(y for y, _ in sel) / n
            per = {}
            for y, rid in sel:
                per[rid] = per.get(rid, 0.0) + (y - mean)
            g = len(per)
            var = (g / (g - 1.0)) * sum(v * v for v in per.values()) / (n * n) if g > 1 else float("nan")
            se = math.sqrt(var) if var == var else None
            mm[(a, l)] = (mean, se, mean - z * se if se is not None else None, mean + z * se if se is not None else None)
    # Independence checks. Within a profile: Cramer's V between attributes (prohibitions show up here). Between the
    # profiles of a task: how often two concepts share a level, against sum p_l^2 for independent draws (a balanced,
    # minimal-overlap design shows up here even when V is near 0).
    vmax = 0.0
    profiles = [prof for prof, _, _ in mm_rows]
    for i in range(len(model.attrs)):
        for j in range(i + 1, len(model.attrs)):
            v = cramers_v([p[i] for p in profiles], [p[j] for p in profiles])
            if v is not None:
                vmax = max(vmax, v)
    overlap = {}
    for qi, a in enumerate(model.attrs):
        freq = {}
        for prof in profiles:
            freq[prof[qi]] = freq.get(prof[qi], 0) + 1
        expected = sum((n / len(profiles)) ** 2 for n in freq.values()) if profiles else 0.0
        same = pairs = 0
        for rid in rids:
            for alts, _ in data.respondents[rid]["tasks"]:
                shown = [prof[qi] for prof in alts if prof is not None]
                for x in range(len(shown)):
                    for y in range(x + 1, len(shown)):
                        pairs += 1
                        same += shown[x] == shown[y]
        overlap[a] = {"observed": same / pairs if pairs else None, "expected_if_independent": expected}
    return amce, mm, vmax, len(ys), overlap


def cramers_v(xs, ys):
    n = len(xs)
    xl, yl = sorted(set(xs)), sorted(set(ys))
    if n == 0 or len(xl) < 2 or len(yl) < 2:
        return None
    table, rx, ry = {}, {}, {}
    for x, y in zip(xs, ys):
        table[(x, y)] = table.get((x, y), 0) + 1
        rx[x] = rx.get(x, 0) + 1
        ry[y] = ry.get(y, 0) + 1
    chi2 = sum((table.get((x, y), 0) - rx[x] * ry[y] / n) ** 2 / (rx[x] * ry[y] / n) for x in xl for y in yl)
    return math.sqrt(chi2 / (n * (min(len(xl), len(yl)) - 1)))


def chi2_sf(x, df):
    """Upper tail of the chi-square distribution (regularized incomplete gamma, Numerical Recipes 6.2)."""
    if x <= 0:
        return 1.0
    a, x2 = df / 2.0, x / 2.0
    if x2 < a + 1:
        term = total = 1.0 / a
        ap = a
        for _ in range(1000):
            ap += 1
            term *= x2 / ap
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return max(0.0, 1.0 - total * math.exp(-x2 + a * math.log(x2) - math.lgamma(a)))
    b = x2 + 1 - a
    c = 1.0 / 1e-300
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return math.exp(-x2 + a * math.log(x2) - math.lgamma(a)) * h


# --------------------------------------------------------------------------------------------------
# One group
# --------------------------------------------------------------------------------------------------


def percentile(sorted_values, q):
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q / 100.0
    low = int(math.floor(pos))
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


def analyse_group(label, model, data, rids, args, z, rng, products, extra_funcs, min_base):
    warnings = []
    tasks = pool_tasks(model, data.respondents, rids)
    n_tasks = sum(t for _, _, t in tasks)
    counts, none_rate, none_tasks = counts_analysis(model, data, rids)
    group = {"label": label, "respondents": len(rids), "tasks": n_tasks, "distinct_tasks": len(tasks),
             "counts": counts, "none_chosen_share": none_rate, "warnings": warnings}
    if len(rids) < min_base:
        warnings.append(f"Small base: {len(rids)} respondents (under {min_base}); treat results as directional.")
    if args.counts_only:
        return group
    try:
        res = fit(tasks, model.p, n_tasks=n_tasks, unit_scale=model.scale)
    except EstimationError as exc:
        raise EstimationError(f"{label}: " + describe_error(exc.args[0], model, data, rids))
    beta = res["beta"]
    ll_null = sum(-t * math.log(len(xs)) for xs, _, t in tasks)
    h_inv = invert(res["info"])
    if h_inv is None:
        raise EstimationError(f"{label}: " + describe_error("singular", model, data, rids))
    if len(rids) >= MIN_RESPONDENTS_FOR_ROBUST:
        cov = robust_cov(h_inv, respondent_scores(model, data.respondents, rids, beta))
        cov_kind = "cluster-robust (respondents)"
    else:
        cov = h_inv
        cov_kind = "model-based (one respondent: no clustering possible)"
        warnings.append("One respondent: standard errors assume independent tasks.")
    group.update({
        "fit": {"loglik": res["loglik"], "loglik_null": ll_null,
                "mcfadden_r2": 1.0 - res["loglik"] / ll_null if ll_null else None,
                "rlh": math.exp(res["loglik"] / n_tasks) if n_tasks else None,
                "rlh_chance": math.exp(ll_null / n_tasks) if n_tasks else None,
                "iterations": res["iterations"], "parameters": model.p, "covariance": cov_kind},
        "coefficients": [{"name": n, "estimate": b, "se_model": math.sqrt(max(h_inv[i][i], 0.0)),
                          "se_robust": math.sqrt(max(cov[i][i], 0.0))}
                         for i, (n, b) in enumerate(zip(model.names, beta))],
    })

    funcs = list(extra_funcs)
    if args.price_attr:
        # Decide on willingness to pay before any ratio is taken: a price effect at or near zero would divide by 0.
        i = model.index[(args.price_attr, None)]
        b_price, se_price = beta[i], math.sqrt(max(cov[i][i], 0.0))
        if b_price >= 0 or abs(b_price) < z * se_price:
            funcs = [(kind, f) for kind, f in funcs if kind != "wtp"]
            warnings.append(f"The price coefficient ({b_price:.4g}, SE {se_price:.3g}) is not clearly negative, so "
                            "willingness to pay is not reported: dividing by a price effect near zero gives "
                            "meaningless values.")

    def everything(b):
        out = flatten(model, b)
        for _, f in funcs:
            out.update(f(b))
        return out

    delta = delta_intervals(everything, beta, cov, z, model.scale)
    boot = None
    if args.bootstrap and len(rids) < 2:
        warnings.append("Bootstrap skipped: resampling one respondent gives no interval.")
    elif args.bootstrap:
        boot = bootstrap(model, data, rids, args, rng, beta, everything, label)
        if boot["failed"] > MAX_FAILED_REPLICATE_SHARE * args.bootstrap:
            warnings.append(f"{boot['failed']} of {args.bootstrap} bootstrap refits failed (separation in a "
                            "resample); bootstrap intervals withheld, delta-method intervals shown.")
            boot["intervals"] = {}
        elif boot["partial"]:
            warnings.append(f"Bootstrap intervals withheld for {len(boot['partial'])} value(s) missing from more than "
                            f"{MAX_FAILED_REPLICATE_SHARE:.0%} of refits (a price effect at or above zero in a "
                            "resample leaves no willingness to pay); delta-method intervals shown for them.")
    group["estimates"] = {json_key(k): {"value": v[0], "se": v[1], "low": v[2], "high": v[3],
                                        "boot_low": (boot["intervals"].get(k) or (None, None))[0] if boot else None,
                                        "boot_high": (boot["intervals"].get(k) or (None, None))[1] if boot else None}
                          for k, v in delta.items()}
    group["bootstrap"] = {"replicates": args.bootstrap, "failed": boot["failed"], "seed": args.seed} if boot else None
    group["_beta"] = beta
    group["_cov"] = cov
    if none_rate is not None and none_rate > 0.5:
        warnings.append(f"None was chosen in {none_rate:.0%} of tasks: the products shown may be unrealistic or "
                        "overpriced, and part-worths rest on few concept choices.")
    return group


def json_key(k):
    return " | ".join(str(x) for x in k)


def bootstrap(model, data, rids, args, rng, beta_hat, func, label):
    reps = args.bootstrap
    values = {}
    failed = 0
    started = time.monotonic()
    for b in range(reps):
        sample = [rids[rng.randrange(len(rids))] for _ in rids]
        tasks = pool_tasks(model, data.respondents, sample)
        try:
            res = fit(tasks, model.p, start=beta_hat, unit_scale=model.scale)
        except EstimationError:
            failed += 1
            continue
        for k, v in func(res["beta"]).items():
            values.setdefault(k, []).append(v)
        if b == 4:
            expected = (time.monotonic() - started) / 5.0 * reps
            if expected > 20:
                print(f"conjoint-analysis: about {expected:.0f} s for {reps} bootstrap refits of {label}; use "
                      "--bootstrap 100 for a first look", file=sys.stderr)
    alpha = (100.0 - args.ci) / 2.0
    intervals = {}
    partial = []
    good = reps - failed
    for k, vals in values.items():
        if len(vals) < good - MAX_FAILED_REPLICATE_SHARE * reps:
            partial.append(k)
            continue
        vals.sort()
        intervals[k] = (percentile(vals, alpha), percentile(vals, 100.0 - alpha))
    return {"intervals": intervals, "failed": failed, "partial": partial}


# --------------------------------------------------------------------------------------------------
# Main analysis and output
# --------------------------------------------------------------------------------------------------


def amce_block(model, data, rids, z):
    a_est, mm, vmax, n_rows, overlap = amce_analysis(model, data, rids, z)
    block = {"amce": {json_key(k): dict(zip(("estimate", "se", "low", "high"), v)) for k, v in a_est.items()},
             "marginal_means": {json_key(k): dict(zip(("mean", "se", "low", "high"), v)) for k, v in mm.items()},
             "baseline": {a: model.levels[a][0] for a in model.attrs}, "concept_rows": n_rows,
             "max_cramers_v": vmax, "within_task_overlap": overlap, "warnings": []}
    if vmax > CRAMER_V_WARN:
        block["warnings"].append(f"Shown attributes are associated (largest Cramer's V {vmax:.2f}): prohibitions or "
                                 "a restricted design (or chance in a small sample), so these AMCEs may mix "
                                 "attribute effects. Use them only with a fully randomized design.")
    low = [(a, o) for a, o in overlap.items() if o["observed"] is not None and o["expected_if_independent"] > 0
           and o["observed"] < OVERLAP_RATIO_WARN * o["expected_if_independent"]]
    if low:
        a, o = min(low, key=lambda t: t[1]["observed"] / t[1]["expected_if_independent"])
        block["warnings"].append(f"Concepts in a task share a level less often than independent draws would ({a}: "
                                 f"{o['observed']:.0%} of pairs vs {o['expected_if_independent']:.0%}): the design "
                                 "avoids overlap (a balanced or minimal-overlap design), so profiles were not "
                                 "assigned independently and these AMCEs do not have their usual meaning. Use the "
                                 "logit part-worths, or field a fully randomized design for AMCEs.")
    return block


def segment_wald(seg_groups, p):
    """Cluster-robust Wald test that every segment has the same utilities: sum_g (b_g - b)' V_g^-1 (b_g - b), with b
    the precision-weighted mean, against chi-square with (G - 1) p df. Each V_g is the segment's respondent-clustered
    covariance, so repeated tasks per person are not counted as independent evidence."""
    precisions, betas = [], []
    for g in seg_groups:
        inv = invert(g["_cov"])
        if inv is None:
            return {"method": "cluster-robust Wald", "statistic": None, "df": None, "p_value": None,
                    "note": f"Not computed: the clustered covariance of {g['label']} is singular (too few respondents "
                            "for the number of parameters)."}
        precisions.append(inv)
        betas.append(g["_beta"])
    total = [[sum(w[i][j] for w in precisions) for j in range(p)] for i in range(p)]
    total_inv = invert(total)
    if total_inv is None:
        return {"method": "cluster-robust Wald", "statistic": None, "df": None, "p_value": None,
                "note": "Not computed: the pooled precision matrix is singular."}
    rhs = [sum(sum(w[i][j] * b[j] for j in range(p)) for w, b in zip(precisions, betas)) for i in range(p)]
    mean = [sum(total_inv[i][j] * rhs[j] for j in range(p)) for i in range(p)]
    stat = 0.0
    for w, b in zip(precisions, betas):
        d = [b[i] - mean[i] for i in range(p)]
        stat += sum(d[i] * w[i][j] * d[j] for i in range(p) for j in range(p))
    df = (len(seg_groups) - 1) * p
    return {"method": "cluster-robust Wald", "statistic": stat, "df": df, "p_value": chi2_sf(stat, df),
            "note": "Tests whether one set of utilities fits every segment, with respondent-clustered covariances. A "
                    "difference in scale (how consistently each segment chooses) also makes it significant (Swait "
                    "and Louviere 1993). Importances and willingness to pay do not depend on scale; simulated shares "
                    "do, so compare importances and WTP first."}


def analyse(args):
    if args.bootstrap < 0:
        raise InputError("--bootstrap must be 0 or more")
    if not 50 < args.ci < 100:
        raise InputError("--ci is a percentage between 50 and 100, for example 95")
    if not args.input:
        raise InputError("give the responses file (or the stacked file)")
    data = load(args)
    linear = []
    if args.price_attr:
        if args.price_attr not in data.attrs:
            raise InputError(f"--price-attr {args.price_attr!r} is not an attribute. Attributes: "
                             + ", ".join(data.attrs))
        linear.append(args.price_attr)
    for a in (args.linear or []):
        if a not in data.attrs:
            raise InputError(f"--linear {a!r} is not an attribute")
        if a not in linear:
            linear.append(a)
    model = Model(data.attrs, data.levels, linear, data.has_none)
    z = NormalDist().inv_cdf(0.5 + args.ci / 200.0)
    rng = random.Random(args.seed)
    products = parse_products(args.product or [], model, data, args.price_attr)
    include_none = model.none_index is not None and not args.sim_no_none
    extra = []
    if args.price_attr and not args.counts_only:
        extra.append(("wtp", wtp_values(model, args.price_attr)))
    if products and not args.counts_only:
        extra.append(("share", share_values(model, products, include_none)))
    rids = sorted(data.respondents)
    notes = list(data.notes)
    for a in model.code_like:
        notes.append(f"Check: the levels of {a!r} are the numbers 1 to {len(model.levels[a])} (or 0 up), which look "
                     "like level codes from a design export, not real values. A linear effect and willingness to pay "
                     "are then per code step: map the codes to the real values first.")
    if len(products) == 1 and not include_none:
        notes.append("One simulated product and no none option: its share is 100% by construction. Add the "
                     "competing products.")
    if args.price_attr is None and not args.counts_only:
        notes.append("No --price-attr: no willingness to pay. Price, if it is an attribute, has a part-worth per "
                     "level.")
    overall = analyse_group("All respondents", model, data, rids, args, z, rng, products, extra, STUDY_FLOOR)
    groups = [overall]
    lr = None
    segments = []
    if args.segment:
        labels = sorted({data.respondents[r]["segment"] or "(blank)" for r in rids})
        ok = True
        for lab in labels:
            members = [r for r in rids if (data.respondents[r]["segment"] or "(blank)") == lab]
            segments.append((lab, members))
            try:
                g = analyse_group(f"{args.segment} = {lab}", model, data, members, args, z, rng, products, extra,
                                  SUBGROUP_FLOOR)
            except EstimationError as exc:
                ok = False
                g = {"label": f"{args.segment} = {lab}", "respondents": len(members), "error": str(exc),
                     "warnings": [str(exc)]}
            groups.append(g)
        if len(labels) == 1:
            notes.append(f"Only one value of {args.segment!r}: the segment equals the overall result.")
        elif ok and not args.counts_only:
            lr = segment_wald(groups[1:], model.p)
    amce = None
    if args.amce:
        amce = amce_block(model, data, rids, z)
        if segments and len(segments) > 1:
            amce["segments"] = {}
            base_label, base_mm = None, None
            for lab, members in segments:
                try:
                    block = amce_block(model, data, members, z)
                except InputError as exc:
                    amce["segments"][lab] = {"respondents": len(members), "error": str(exc)}
                    continue
                entry = {"respondents": len(members), "amce": block["amce"],
                         "marginal_means": block["marginal_means"]}
                if base_mm is None:
                    base_label, base_mm = lab, block["marginal_means"]
                else:
                    # Segments hold different respondents, so the two estimates are independent.
                    diffs = {}
                    for k, v in block["marginal_means"].items():
                        b0 = base_mm.get(k) or {}
                        if v["mean"] is None or b0.get("mean") is None:
                            continue
                        d = v["mean"] - b0["mean"]
                        if v["se"] is None or b0["se"] is None:
                            diffs[k] = {"difference": d, "se": None, "low": None, "high": None}
                            continue
                        se = math.sqrt(v["se"] ** 2 + b0["se"] ** 2)
                        diffs[k] = {"difference": d, "se": se, "low": d - z * se, "high": d + z * se}
                    entry["mm_difference_vs"] = base_label
                    entry["mm_differences"] = diffs
                amce["segments"][lab] = entry
    result = {
        "version": VERSION,
        "ci": args.ci,
        "input": {"responses": args.input, "design": args.design, "mode": "design" if args.design else "stacked"},
        "attributes": {a: model.levels[a] for a in model.attrs},
        "linear": {a: model.linear[a] for a in model.linear},
        "none_option": model.none_index is not None,
        "counts": {"respondents_read": data.counts["respondents_read"], "respondents_used": len(rids),
                   "tasks_read": data.counts["tasks_read"], "tasks_used": data.counts["tasks_used"],
                   "tasks_excluded": data.counts["excluded"]},
        "notes": notes,
        "groups": [{k: v for k, v in g.items() if not k.startswith("_")} for g in groups],
        "segment_test": lr,
        "amce": amce,
        "products": [{"name": n, "profile": p} for n, p in products],
        "conventions": [
            "aggregate conditional logit, main effects only (no interactions), dummy coding, first level of each "
            "attribute = reference; linear attributes centered on the mean tested value",
            "part-worths zero-centered within each attribute; none utility on the same centered scale",
            "importance = range of an attribute's part-worths / sum of ranges x 100 (from aggregate utilities)",
            (f"{args.ci:g}% intervals: cluster-robust sandwich + delta method"
             + (f"; percentile bootstrap over respondents ({args.bootstrap} replicates, seed {args.seed}) where "
                "shown as boot_low/boot_high" if args.bootstrap else "")) if not args.counts_only
            else "counts only: no model and no intervals",
            "shares = logit share of preference (IIA): similar products split share too evenly",
        ] + (["WTP = -(part-worth difference) / price coefficient, per unit of the price attribute, each level "
              "against its attribute's first level"] if args.price_attr else []),
    }
    return result, groups


def fmt(v, pattern="{:.3f}"):
    return "-" if v is None else pattern.format(v)


def pick_interval(e, boot):
    """Bootstrap interval when one was computed for this value, else the delta-method one."""
    if boot and e.get("boot_low") is not None:
        return e["boot_low"], e["boot_high"]
    return e["low"], e["high"]


def render(result, groups):
    out = []
    ci = f"{result['ci']:g}%"
    c = result["counts"]
    exc = ", ".join(f"{k}: {v}" for k, v in c["tasks_excluded"].items()) or "none"
    out.append(f"Conjoint analysis ({result['input']['mode']} input): {c['respondents_used']} respondents, "
               f"{c['tasks_used']} of {c['tasks_read']} tasks used (excluded: {exc}).")
    for n in result["notes"]:
        out.append("Note: " + n)
    for g in groups:
        out.append("")
        out.append(f"== {g['label']} (n = {g['respondents']}) ==")
        if "error" in g:
            out.append("Error: " + g["error"])
            continue
        if "fit" in g:
            f = g["fit"]
            out.append(f"Log-likelihood {f['loglik']:.2f} (null {f['loglik_null']:.2f}), McFadden R2 "
                       f"{fmt(f['mcfadden_r2'])}, RLH {fmt(f['rlh'])}; {f['covariance']} SEs.")
            est = g["estimates"]
            boot = g.get("bootstrap")
            out.append(f"Chance RLH {fmt(f.get('rlh_chance'))} (1 / alternatives per task).")
            out.append(f"Attribute / level                       Part-worth    {ci + ' CI':<20}Importance")
            for a, levels in result["attributes"].items():
                imp = est.get(f"imp | {a}")
                if imp:
                    lo, hi = pick_interval(imp, boot)
                    imp_txt = f"{imp['value']:.1f}% ({fmt(lo, '{:.1f}')} to {fmt(hi, '{:.1f}')})"
                else:
                    imp_txt = "-"
                first = True
                for l in levels:
                    e = est[f"pw | {a} | {l}"]
                    lo, hi = pick_interval(e, boot)
                    out.append(f"{(a + ': ' + l)[:38]:<38} {e['value']:>10.3f}   {lo:>7.3f} to {hi:<7.3f}   "
                               + (imp_txt if first else ""))
                    first = False
                if a in result["linear"]:
                    c = next(c for c in g["coefficients"] if c["name"] == f"{a} (per unit)")
                    out.append(f"  ({a} is linear: {c['estimate']:.4g} per unit, robust SE {c['se_robust']:.3g}; "
                               "the rows above are that line at the tested values)")
            if "none" in est:
                e = est["none"]
                lo, hi = pick_interval(e, boot)
                out.append(f"{'None':<38} {e['value']:>10.3f}   {lo:>7.3f} to {hi:<7.3f}")
            wtp = [(k, v) for k, v in est.items() if k.startswith("wtp")]
            if wtp:
                out.append(f"Willingness to pay, each level vs its attribute's first level (price units, {ci} CI):")
                for k, v in wtp:
                    lo, hi = pick_interval(v, boot)
                    out.append(f"  {k[6:]:<36} {v['value']:>10.2f}   {fmt(lo, '{:>9.2f}')} to {fmt(hi, '{:.2f}')}")
            shares = [(k, v) for k, v in est.items() if k.startswith("share")]
            if shares:
                out.append(f"Simulated share of preference ({ci} CI):")
                for k, v in shares:
                    lo, hi = pick_interval(v, boot)
                    out.append(f"  {k[8:]:<36} {v['value']:>6.1f}%   {lo:.1f} to {hi:.1f}")
        else:
            out.append("Counts only (no logit):")
            for a, lv in g["counts"].items():
                for l, cc in lv.items():
                    out.append(f"  {a}: {l}  shown {cc['shown']}, chosen {cc['chosen']}, rate "
                               f"{fmt(cc['choice_rate'], '{:.3f}')}")
        if g.get("none_chosen_share") is not None:
            out.append(f"None chosen in {g['none_chosen_share']:.1%} of tasks.")
        for w in g["warnings"]:
            out.append("Warning: " + w)
    if result["segment_test"]:
        t = result["segment_test"]
        out.append("")
        if t["statistic"] is None:
            out.append(f"Segment test: {t['note']}")
        else:
            out.append(f"Segment test ({t['method']}): chi2 = {t['statistic']:.2f}, df = {t['df']}, "
                       f"p = {t['p_value']:.4g}. {t['note']}")
    if result["amce"]:
        a = result["amce"]
        out.append("")
        out.append(f"AMCE (change in probability of choosing a concept vs the baseline level), {a['concept_rows']} "
                   "concept rows, respondent-clustered SEs:")
        for k, v in a["amce"].items():
            out.append(f"  {k:<36} {v['estimate']:>7.3f}  ({fmt(v['low'])} to {fmt(v['high'])})")
        out.append("Marginal means (share of concepts with the level that were chosen):")
        for k, v in a["marginal_means"].items():
            if v["mean"] is not None:
                out.append(f"  {k:<36} {v['mean']:>7.3f}  ({fmt(v['low'])} to {fmt(v['high'])})")
        for lab, seg in (a.get("segments") or {}).items():
            out.append(f"Segment {lab} (n = {seg['respondents']}):" + (f" {seg['error']}" if "error" in seg else ""))
            if "error" in seg:
                continue
            for k, v in seg["marginal_means"].items():
                if v["mean"] is None:
                    continue
                line = f"  {k:<36} MM {v['mean']:>6.3f} ({fmt(v['low'])} to {fmt(v['high'])})"
                d = (seg.get("mm_differences") or {}).get(k)
                if d:
                    line += (f"; vs {seg['mm_difference_vs']} {d['difference']:+.3f} ({fmt(d['low'])} to "
                             f"{fmt(d['high'])})")
                out.append(line)
        for w in a["warnings"]:
            out.append("Warning: " + w)
    out.append("")
    out.append("Conventions: " + "; ".join(result["conventions"]))
    return "\n".join(out)


def build_parser():
    p = argparse.ArgumentParser(description="Aggregate logit analysis of choice-based conjoint data.",
                                epilog="Input formats: references/input-formats.md.")
    p.add_argument("input", nargs="?", help="responses CSV (with --design) or a stacked CSV")
    p.add_argument("--design", help="design CSV from conjoint-design: version,task,concept,<attributes>")
    p.add_argument("--spec", help="conjoint-design spec, to fix the level order")
    p.add_argument("--respondent-col")
    p.add_argument("--version-col")
    p.add_argument("--task-col")
    p.add_argument("--choice-col", help="design mode, long responses: the chosen concept label")
    p.add_argument("--concept-col", help="stacked mode: the concept label column")
    p.add_argument("--chosen-col", help="stacked mode: 1 on the chosen row")
    p.add_argument("--attribute-cols", help="comma-separated attribute columns (default: every other column)")
    p.add_argument("--none-when-missing-row", action="store_true",
                   help="a task with no concept chosen (stacked) or a 'none' choice with no none row (design) "
                        "counts as choosing none")
    p.add_argument("--price-attr", help="price attribute: estimated as linear, enables WTP and in-between prices")
    p.add_argument("--linear", action="append", help="another numeric attribute to estimate as linear")
    p.add_argument("--product", action="append",
                   help="simulator product 'Name: Attr=level; Attr=level' (repeat for each product)")
    p.add_argument("--sim-no-none", action="store_true", help="leave the none option out of the simulator")
    p.add_argument("--segment", help="column with one value per respondent")
    p.add_argument("--amce", action="store_true", help="AMCEs and marginal means (fully randomized designs)")
    p.add_argument("--counts-only", action="store_true", help="counts analysis only, no logit")
    p.add_argument("--bootstrap", type=int, default=0, help="percentile bootstrap replicates over respondents "
                                                            "(default 0: delta-method intervals only)")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--ci", type=float, default=95.0, help="interval level in percent (default 95)")
    p.add_argument("--allow-exclusions", action="store_true",
                   help="analyse even when more than 5%% of tasks are excluded")
    p.add_argument("--delimiter", help="responses delimiter (default: sniffed)")
    p.add_argument("--design-delimiter", help="design delimiter (default: sniffed)")
    p.add_argument("--skip-rows", type=int, help="rows under the header to skip (Qualtrics: detected)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--version", action="version", version=VERSION)
    return p


def no_nan(value):
    """Strict JSON: NaN and infinities become null."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: no_nan(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [no_nan(v) for v in value]
    return value


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result, groups = analyse(args)
    except InputError as exc:
        print(f"conjoint-analysis: {exc}", file=sys.stderr)
        return 2
    except EstimationError as exc:
        print(f"conjoint-analysis: {exc.args[0]}", file=sys.stderr)
        return 3
    print(json.dumps(no_nan(result), indent=2, allow_nan=False) if args.json else render(result, groups))
    return 0


if __name__ == "__main__":
    sys.exit(main())
