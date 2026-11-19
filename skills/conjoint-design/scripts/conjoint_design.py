#!/usr/bin/env python3
"""Conjoint design: build and check a choice-based conjoint (CBC) design.

Standard library only, Python 3.9+. No network. Deterministic for a given --seed.
Formulas, thresholds and citations: references/sources.md and references/design-method.md.

Usage:
  python3 scripts/conjoint_design.py design SPEC --tasks 12 --concepts 3 [--none] [--versions 100] --out design.csv
  python3 scripts/conjoint_design.py check design.csv [--spec SPEC] [--respondents 300] [--subgroups 2]
  python3 scripts/conjoint_design.py sample-size --max-levels 5 --tasks 12 --concepts 3 [--respondents 300]

SPEC is a JSON file {"attributes": [{"name": ..., "levels": [...]}, ...], "prohibitions": [{"Attr": "level",
"Other": "level"}, ...]} or a text file with one attribute per line, "Name: level 1 | level 2 | level 3", and
prohibitions as "prohibit: Attr=level & Other=level" (conditions split on "&" only; a level that contains "&"
needs the JSON spec).

The design file has one row per version x task x concept: version,task,concept,<one column per attribute>.
With --none every task also has a row with concept "none" and blank attributes. A row is the none option when
its concept label is a none word (none, none of these, no choice, neither, opt-out) or all its attribute cells
are blank; a concept numbered 0 is an ordinary concept. conjoint-analysis reads this file plus the
respondents' choices and applies the same rules.

Methods:
  balanced (default)  each concept takes, per attribute, the level used least within the task, then least within
                      the version, then least in the whole design, ties broken at random (minimal overlap and
                      level balance, in the spirit of Sawtooth's shortcut method); prohibited and duplicate
                      concepts are avoided and concept order within a task is shuffled
  random              every concept drawn independently and uniformly from the allowed profiles (a fully
                      randomized design for AMCEs): two concepts in a task can be identical, as independence
                      requires

Diagnostics: level frequencies, within-task overlap, Cramer's V between attributes, D-error and relative
D-efficiency of the MNL information matrix at beta = 0 (orthonormal coding) against the Burgess-Street upper
bound for main effects, and the Johnson-Orme sample size.

Exit codes: 0 success; 2 bad input, a design file that cannot be read as choice tasks, or an impossible
design (the message says what to fix).
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

VERSION = "0.1.0"

DEFAULT_VERSIONS = 100  # convention of this skill: enough versions to balance levels across respondents
DEFAULT_SEED = 20261119  # arbitrary fixed default so runs repeat
EXPOSURE_TARGET = 500  # Johnson and Orme rule: n*t*a/c >= 500 (Sawtooth Software)
EXPOSURE_COMFORTABLE = 1000  # Sawtooth's suggested planning level
MIN_RESPONDENTS = 300  # Sawtooth rule of thumb: 300 per study, 200 per reported subgroup
MIN_PER_SUBGROUP = 200
MAX_ATTEMPTS = 2000  # tries per task before the design is declared impossible (implementation constant)
CRAMER_V_WARN = 0.10  # convention of this skill: warn when two attributes are associated beyond V = 0.10
D_EFF_WARN = 80.0  # convention of this skill: warn under 80% relative D-efficiency
# Column names conjoint-analysis reads as file columns (kept identical in both skills).
RESERVED = {"version", "block", "task", "set", "concept", "alt", "alternative", "respondent", "respondent_id",
            "resp.id", "id", "responseid", "response_id", "rid", "chosen", "choice", "segment", "weight", "ques"}
DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|", "\\t": "\t"}
# Concept labels that mean the opt-out (kept identical in conjoint-analysis). "0" is not one: 0-based concept
# numbers are ordinary concepts; a row with every attribute cell blank is the none option whatever its label.
NONE_LABELS = {"none", "none of these", "no choice", "neither", "opt-out", "opt out"}
TASK_COLS = ["task", "set", "ques", "question"]
CONCEPT_COLS = ["concept", "alt", "alternative", "option", "profile"]
VERSION_COLS = ["version", "block"]
DUPLICATE_TASK_RETRIES = 20  # implementation constant: tries to avoid repeating a task within a version


class InputError(Exception):
    """Bad input or an impossible design (exit code 2)."""


# --------------------------------------------------------------------------------------------------
# Spec
# --------------------------------------------------------------------------------------------------


def read_text_file(path):
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except FileNotFoundError:
        raise InputError(f"file not found: {path}")
    except IsADirectoryError:
        raise InputError(f"{path} is a folder, not a file")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}")
    try:
        if data.startswith(b"\xef\xbb\xbf"):
            return data[3:].decode("utf-8")
        if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
            return data.decode("utf-16")
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"{path} is not UTF-8 text (byte {exc.start}); save it as UTF-8")


def norm_label(text):
    """Version, task and concept labels as conjoint-analysis reads them: '2', '2.0' and 'Option 2' all mean 2;
    a none word means 'none'."""
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
    is a thousands separator inside one level, not a separator between levels."""
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
            raise InputError(f"{where}: write each condition as Attribute=level, joined by '&' (got {part!r}). A "
                             "level or name that contains '&' needs the JSON spec")
        name, level = part.split("=", 1)
        name = name.strip()
        if name in cond:
            raise InputError(f"{where}: a prohibition names {name!r} twice; each condition names a different "
                             "attribute")
        cond[name] = level.strip()
    return cond


def load_spec(path):
    text = read_text_file(path)
    attributes, prohibitions = [], []
    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise InputError(f"{path} is not valid JSON: {exc}")
        if not isinstance(data, dict) or not isinstance(data.get("attributes"), list) \
                or not isinstance(data.get("prohibitions", []) or [], list):
            raise InputError(f"{path}: the JSON spec is an object with an 'attributes' list (and optionally a "
                             "'prohibitions' list)")
        for a in data["attributes"]:
            if not isinstance(a, dict) or "name" not in a or not isinstance(a.get("levels"), list):
                raise InputError(f"{path}: each attribute needs a name and a list of levels")
            attributes.append({"name": str(a["name"]).strip(), "levels": [str(l).strip() for l in a["levels"]]})
        for p in data.get("prohibitions") or []:
            if not isinstance(p, dict):
                raise InputError(f"{path}: each prohibition is an object naming two or more attributes and levels")
            prohibitions.append({str(k).strip(): str(v).strip() for k, v in p.items()})
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
                raise InputError(f"{path} line {number}: write 'Attribute: level 1 | level 2' (got {line!r})")
            name, rest = line.split(":", 1)
            attributes.append({"name": name.strip(), "levels": split_levels(rest)})
    return validate_spec(attributes, prohibitions, path)


def validate_spec(attributes, prohibitions, where):
    if len(attributes) < 1:
        raise InputError(f"{where}: no attributes found")
    names = [a["name"] for a in attributes]
    if len(set(n.lower() for n in names)) != len(names):
        raise InputError(f"{where}: an attribute name is used twice")
    for a in attributes:
        if not a["name"]:
            raise InputError(f"{where}: an attribute has no name")
        if a["name"].lower() in RESERVED:
            raise InputError(f"{where}: {a['name']!r} is a reserved column name; rename the attribute")
        if len(a["levels"]) < 2:
            hint = (" (with commas, '1,299' is read as one number: separate levels with '|')"
                    if any("," in l for l in a["levels"]) else "")
            raise InputError(f"{where}: attribute {a['name']!r} needs at least two levels (a constant cannot be "
                             f"estimated){hint}")
        if len(set(a["levels"])) != len(a["levels"]):
            raise InputError(f"{where}: attribute {a['name']!r} lists a level twice")
        if any(not l for l in a["levels"]):
            raise InputError(f"{where}: attribute {a['name']!r} has a blank level")
    index = {a["name"]: a for a in attributes}
    for p in prohibitions:
        if len(p) < 2:
            raise InputError(f"{where}: a prohibition must name two or more attributes (to drop a level, remove "
                             "it from the attribute instead)")
        for name, level in p.items():
            if name not in index:
                raise InputError(f"{where}: prohibition names unknown attribute {name!r}")
            if level not in index[name]["levels"]:
                raise InputError(f"{where}: prohibition names unknown level {level!r} of {name!r}")
    return attributes, prohibitions


# --------------------------------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------------------------------


def prohibited(profile, prohibitions, names):
    """True when a full or partial profile (dict name -> level) matches every condition of a prohibition."""
    for p in prohibitions:
        if all(name in profile and profile[name] == level for name, level in p.items()):
            return True
    return False


def generate(attributes, prohibitions, tasks, concepts, versions, method, seed):
    rng = random.Random(seed)
    names = [a["name"] for a in attributes]
    space = 1
    for a in attributes:
        space *= len(a["levels"])
    if concepts < 2:
        raise InputError("--concepts must be at least 2 (a choice needs two options)")
    if tasks < 1 or versions < 1:
        raise InputError("--tasks and --versions must be at least 1")
    if method == "balanced" and concepts > space:
        raise InputError(f"only {space} distinct profiles exist, fewer than {concepts} concepts per task")
    allowed_list = None
    allowed = 0
    if space <= 200000:
        allowed_list = [combo for combo in _all_profiles(attributes)
                        if not prohibited(dict(zip(names, combo)), prohibitions, names)]
        allowed = len(allowed_list)
        if allowed < (concepts if method == "balanced" else 1):
            raise InputError(f"the prohibitions leave {allowed} allowed profile(s), fewer than {concepts} concepts")
    global_count = {n: {l: 0 for l in a["levels"]} for n, a in zip(names, attributes)}
    rows = []
    for v in range(1, versions + 1):
        version_count = {n: {l: 0 for l in a["levels"]} for n, a in zip(names, attributes)}
        seen_tasks = set()
        for t in range(1, tasks + 1):
            if method == "random":
                task = [_random_concept(attributes, names, prohibitions, allowed_list, rng)
                        for _ in range(concepts)]
            else:
                for attempt in range(MAX_ATTEMPTS):
                    task = _make_task(attributes, names, prohibitions, concepts, rng, version_count,
                                      global_count, attempt)
                    if task is None:
                        continue
                    key = frozenset(tuple(c[n] for n in names) for c in task)
                    if key in seen_tasks and attempt < DUPLICATE_TASK_RETRIES:
                        continue
                    seen_tasks.add(key)
                    break
                else:
                    raise InputError(f"could not build task {t} of version {v} in {MAX_ATTEMPTS} tries; the "
                                     "prohibitions are probably too tight for this many concepts")
            for j, concept in enumerate(task, start=1):
                for n in names:
                    version_count[n][concept[n]] += 1
                    global_count[n][concept[n]] += 1
                rows.append({"version": v, "task": t, "concept": j, **concept})
    return rows, allowed


def _all_profiles(attributes):
    return itertools.product(*(a["levels"] for a in attributes))


def _random_concept(attributes, names, prohibitions, allowed_list, rng):
    """One concept drawn uniformly from the allowed profiles, independently of every other concept."""
    if allowed_list is not None:
        return dict(zip(names, rng.choice(allowed_list)))
    for _ in range(MAX_ATTEMPTS):
        profile = {n: rng.choice(a["levels"]) for n, a in zip(names, attributes)}
        if not prohibited(profile, prohibitions, names):
            return profile
    raise InputError(f"no allowed profile found in {MAX_ATTEMPTS} random draws; the prohibitions are too tight")


def _make_task(attributes, names, prohibitions, concepts, rng, version_count, global_count, attempt):
    """One task of the balanced method, concepts in random on-screen order; None when no task could be built."""
    task = []
    task_count = {n: {l: 0 for l in a["levels"]} for n, a in zip(names, attributes)}
    # After many failed attempts, loosen the balance rule so prohibitions can be satisfied.
    jitter = attempt >= 50
    for _ in range(concepts):
        concept = None
        for _try in range(20):
            # Spec order first (it keeps overlap minimal on the fixtures); shuffled on retries.
            order = list(range(len(attributes)))
            if _try:
                rng.shuffle(order)
            profile = {}
            ok = True
            for qi in order:
                a = attributes[qi]
                n = names[qi]
                candidates = [l for l in a["levels"]
                              if not prohibited({**profile, n: l}, prohibitions, names)]
                if not candidates:
                    ok = False
                    break
                if jitter and rng.random() < 0.3:
                    level = rng.choice(candidates)
                else:
                    keyed = [(task_count[n][l], version_count[n][l], global_count[n][l], rng.random(), l)
                             for l in candidates]
                    level = min(keyed)[4]
                profile[n] = level
            if not ok:
                continue
            if any(all(profile[n] == other[n] for n in names) for other in task):
                if _try > 5:
                    continue
                # Perturb one attribute at random to break the duplicate.
                qi = rng.randrange(len(attributes))
                n = names[qi]
                alt = [l for l in attributes[qi]["levels"] if l != profile[n]
                       and not prohibited({**profile, n: l}, prohibitions, names)]
                if not alt:
                    continue
                profile[n] = rng.choice(alt)
                if any(all(profile[m] == other[m] for m in names) for other in task):
                    continue
            concept = profile
            break
        if concept is None:
            return None
        for n in names:
            task_count[n][concept[n]] += 1
        task.append(concept)
    # Concepts are built in sequence, so the later ones absorb the overlap; shuffle the on-screen order so no
    # position is systematically the one that repeats a level.
    rng.shuffle(task)
    return task


# --------------------------------------------------------------------------------------------------
# Reading a design file
# --------------------------------------------------------------------------------------------------


def sniff_delimiter(text):
    lines = [line for line in text.splitlines() if line.strip()][:50]
    best, best_key = ",", None
    for delim in (",", ";", "\t", "|"):
        try:
            rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=delim))
        except csv.Error:
            continue
        if not rows:
            continue
        width = len(rows[0])
        key = (width > 1, sum(1 for r in rows if len(r) == width), width)
        if best_key is None or key > best_key:
            best, best_key = delim, key
    return best


def read_design(path, delimiter=None, attribute_cols=None):
    text = read_text_file(path)
    first, _, rest = text.partition("\n")
    m = re.fullmatch(r"\s*sep=(.)\s*", first)
    if m:  # Excel's "sep=;" first line
        text, delimiter = rest, delimiter or m.group(1)
    delim = DELIMITERS.get((delimiter or "").lower(), delimiter) if delimiter else sniff_delimiter(text)
    if len(delim) != 1:
        raise InputError(f"--delimiter must be comma, semicolon, tab, pipe or one character (got {delimiter!r})")
    try:
        table = [r for r in csv.reader(io.StringIO(text, newline=""), delimiter=delim) if any(c.strip() for c in r)]
    except csv.Error as exc:
        raise InputError(f"{path} is not valid CSV: {exc}")
    if not table:
        raise InputError(f"{path} is empty")
    header = [h.strip() for h in table[0]]
    while header and not header[-1] and all(len(r) < len(header) or not r[len(header) - 1].strip()
                                              for r in table[1:]):
        header.pop()  # an empty trailing column, as spreadsheets often write
        table = [r[:len(header)] for r in table]
    if any(not h for h in header):
        raise InputError(f"{path}: a column has no name")
    dup = sorted({h for h in header if [x.lower() for x in header].count(h.lower()) > 1})
    if dup:
        raise InputError(f"{path}: duplicate column name(s) {', '.join(dup)} (names are compared ignoring case)")
    lower = {h.lower(): h for h in header}

    def find(cands, need):
        for c in cands:
            if c in lower:
                return lower[c]
        if need:
            raise InputError(f"{path} needs a {cands[0]!r} column (and 'version' when there are several "
                             f"versions). Found: {', '.join(header)}")
        return None

    tcol, ccol, vcol = find(TASK_COLS, True), find(CONCEPT_COLS, True), find(VERSION_COLS, False)
    if attribute_cols:
        attrs = [c.strip() for c in attribute_cols.split(",")]
        missing = [c for c in attrs if c not in header]
        if missing:
            raise InputError(f"{path}: attribute column(s) not found: {', '.join(missing)}")
        if len(set(attrs)) != len(attrs):
            raise InputError("--attribute-cols names a column twice")
    else:
        attrs = [h for h in header if h not in (tcol, ccol, vcol) and h.lower() not in RESERVED]
    if not attrs:
        raise InputError(f"{path} has no attribute columns besides version, task and concept")
    rows = []
    for number, r in enumerate(table[1:], start=2):
        if len(r) != len(header):
            raise InputError(f"{path} row {number} has {len(r)} cells but the header has {len(header)}")
        rec = dict(zip(header, (c.strip() for c in r)))
        rows.append({"version": rec[vcol] if vcol else "1", "task": rec[tcol], "concept": rec[ccol],
                     **{a: rec[a] for a in attrs}})
    if not rows:
        raise InputError(f"{path} has a header but no rows")
    return attrs, rows


def design_tasks(attrs, rows):
    """Group rows into tasks: list of (version, task, [profiles as tuples]) excluding none rows; and has_none.

    The same rules as conjoint-analysis: labels normalized ('Option 2' = '2'); a row is the none option when its
    label is a none word or every attribute cell is blank; each (version, task, concept) appears once, a task
    has at most one none row and at least two concepts."""
    tasks, seen, nones = {}, set(), {}
    has_none = False
    for r in rows:
        key = (norm_label(r["version"]), norm_label(r["task"]))
        concept = norm_label(r["concept"])
        blank = all(not r[a] for a in attrs)
        where = f"version {key[0]} task {key[1]} concept {r['concept'] or '(blank)'}"
        if concept == "none" or blank:
            if concept == "none" and not blank:
                raise InputError(f"{where}: a none row must leave every attribute blank")
            nones[key] = nones.get(key, 0) + 1
            if nones[key] > 1:
                raise InputError(f"version {key[0]} task {key[1]} has more than one none row")
            has_none = True
            tasks.setdefault(key, [])
            continue
        if (key, concept) in seen:
            raise InputError(f"{where} appears twice: a recorded choice could not tell which profile was picked. "
                             "Number the concepts of a task 1, 2, 3...")
        seen.add((key, concept))
        blanks = [a for a in attrs if not r[a]]
        if blanks:
            raise InputError(f"{where}: blank level in {', '.join(blanks)}")
        tasks.setdefault(key, []).append(tuple(r[a] for a in attrs))
    short = [k for k, v in tasks.items() if len(v) < 2]
    if short:
        raise InputError(f"{len(short)} task(s) have fewer than two concepts (first: version {short[0][0]} task "
                         f"{short[0][1]}); a choice needs two or more")
    return [(k[0], k[1], v) for k, v in tasks.items()], has_none


# --------------------------------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------------------------------


def helmert(levels_count):
    """Normalized Helmert contrasts: rows = levels, columns orthonormal and orthogonal to the constant."""
    k = levels_count
    rows = [[0.0] * (k - 1) for _ in range(k)]
    for col in range(1, k):
        scale = 1.0 / math.sqrt(col * (col + 1))
        for lev in range(col):
            rows[lev][col - 1] = scale
        rows[col][col - 1] = -col * scale
    return rows


def cholesky_logdet(matrix):
    n = len(matrix)
    lower = [[0.0] * n for _ in range(n)]
    logdet = 0.0
    for i in range(n):
        for j in range(i + 1):
            total = matrix[i][j] - sum(lower[i][m] * lower[j][m] for m in range(j))
            if i == j:
                if total <= 1e-12:
                    return None
                lower[i][i] = math.sqrt(total)
                logdet += 2.0 * math.log(lower[i][i])
            else:
                lower[i][j] = total / lower[j][j]
    return logdet


def information_matrix(attrs, levels, tasks):
    """MNL information per task at beta = 0, orthonormal coding, averaged over tasks (none option excluded)."""
    codes = {a: helmert(len(levels[a])) for a in attrs}
    pos = {a: {l: i for i, l in enumerate(levels[a])} for a in attrs}
    p = sum(len(levels[a]) - 1 for a in attrs)
    info = [[0.0] * p for _ in range(p)]
    used = 0
    for _, _, profiles in tasks:
        m = len(profiles)
        if m < 2:
            continue
        used += 1
        xs = []
        for prof in profiles:
            x = []
            for a, level in zip(attrs, prof):
                x.extend(codes[a][pos[a][level]])
            xs.append(x)
        mean = [sum(x[i] for x in xs) / m for i in range(p)]
        for x in xs:
            d = [x[i] - mean[i] for i in range(p)]
            for i in range(p):
                if d[i] == 0.0:
                    continue
                di = d[i] / m
                row = info[i]
                for j in range(p):
                    row[j] += di * d[j]
    if used == 0:
        return None, p, 0
    return [[v / used for v in row] for row in info], p, used


def burgess_street_bound(levels_counts, m):
    """Upper bound on log det of the per-task information (orthonormal coding, main effects, choice sets of
    size m): sum over attributes of (l - 1) * log(2 S_q / (m^2 (l - 1))), with 2 S_q = m^2 - min sum n_a^2."""
    total = 0.0
    for l in levels_counts:
        x, y = divmod(m, l)
        min_sq = (l - y) * x * x + y * (x + 1) * (x + 1)
        trace = 1.0 - min_sq / (m * m)
        total += (l - 1) * math.log(trace / (l - 1))
    return total


def diagnostics(attrs, levels, tasks, has_none, prohibitions=None, method=None):
    out = {"attributes": [], "warnings": []}
    concept_rows = [prof for _, _, profiles in tasks for prof in profiles]
    n_concepts = len(concept_rows)
    sizes = sorted({len(p) for _, _, p in tasks})
    out["tasks"] = len(tasks)
    out["versions"] = len({v for v, _, _ in tasks})
    per_version = {}
    for v, _, _ in tasks:
        per_version[v] = per_version.get(v, 0) + 1
    out["tasks_per_version"] = sorted(set(per_version.values()))[0] if len(set(per_version.values())) == 1 \
        else sorted(set(per_version.values()))
    out["concepts_per_task"] = sizes[0] if len(sizes) == 1 else sizes
    out["none_option"] = has_none
    out["concept_rows"] = n_concepts
    for qi, a in enumerate(attrs):
        counts = {l: 0 for l in levels[a]}
        for prof in concept_rows:
            counts[prof[qi]] += 1
        expected = n_concepts / len(levels[a])
        overlap_tasks = sum(1 for _, _, profs in tasks if len({p[qi] for p in profs}) < len(profs))
        unavoidable = bool(sizes) and len(levels[a]) < max(sizes)
        lo, hi = min(counts.values()), max(counts.values())
        out["attributes"].append({
            "name": a, "levels": len(levels[a]),
            "counts": counts, "min_count": lo, "max_count": hi,
            "max_min_ratio": (hi / lo) if lo else None,
            "max_deviation_pct": max(abs(c - expected) / expected for c in counts.values()) * 100 if expected else None,
            "tasks_with_overlap_pct": 100.0 * overlap_tasks / len(tasks) if tasks else None,
            "overlap_unavoidable": unavoidable,
        })
        if lo == 0:
            out["warnings"].append(f"{a}: level(s) never shown: " + ", ".join(l for l, c in counts.items() if c == 0)
                                   + ". Their utilities cannot be estimated.")
        elif hi / lo > 1.5:
            out["warnings"].append(f"{a}: level counts range from {lo} to {hi} (ratio {hi / lo:.2f}); the design "
                                   "is not level-balanced.")
    pairs = []
    for i in range(len(attrs)):
        for j in range(i + 1, len(attrs)):
            v = cramers_v([p[i] for p in concept_rows], [p[j] for p in concept_rows])
            pairs.append({"a": attrs[i], "b": attrs[j], "cramers_v": v})
            if v is not None and v > CRAMER_V_WARN:
                linked = any(attrs[i] in p and attrs[j] in p for p in (prohibitions or []))
                out["warnings"].append(f"{attrs[i]} and {attrs[j]} are associated (Cramer's V = {v:.2f}); their "
                                       "effects are harder to separate" +
                                       (" (expected: a prohibition links them)." if linked else "."))
    out["attribute_association"] = pairs
    top = max((p for p in pairs if p["cramers_v"] is not None), key=lambda p: p["cramers_v"], default=None)
    out["max_cramers_v"] = top["cramers_v"] if top else None
    out["max_cramers_v_pair"] = [top["a"], top["b"]] if top else None
    # Exposure from the actual allocation: respondents take versions in rotation, so a respondent sees each
    # level, on average, (times it appears in all versions) / (number of versions) times.
    n_versions = out["versions"] or 1
    low = None
    for qi, a in enumerate(attrs):
        for level in levels[a]:
            e = sum(1 for prof in concept_rows if prof[qi] == level) / n_versions
            if low is None or e < low[0]:
                low = (e, a, level)
    out["lowest_level_exposures_per_respondent"] = low[0] if low else None
    out["lowest_exposure_level"] = [low[1], low[2]] if low else None
    info, p, used = information_matrix(attrs, levels, tasks)
    out["parameters"] = p
    if info is None:
        out["d_error"] = None
        out["relative_d_efficiency_pct"] = None
        out["warnings"].append("No task has two or more concepts: no information matrix.")
        return out
    logdet = cholesky_logdet(info)
    if logdet is None:
        out["d_error"] = None
        out["relative_d_efficiency_pct"] = 0.0
        out["warnings"].append("The information matrix is singular: some effects cannot be estimated (a level "
                               "never shown or never varied within a task, or two attributes move together). Do "
                               "not field this design: fix the spec or the design first.")
        return out
    out["d_error"] = math.exp(-logdet / p)
    if len(sizes) == 1:
        bound = burgess_street_bound([len(levels[a]) for a in attrs], sizes[0])
        eff = 100.0 * math.exp((logdet - bound) / p)
        out["relative_d_efficiency_pct"] = eff
        if eff < D_EFF_WARN:
            if method == "random":
                out["warnings"].append(f"Relative D-efficiency is {eff:.1f}%, under {D_EFF_WARN:.0f}%. That is the "
                                       "expected cost of full randomization for AMCEs; plan more respondents or "
                                       "tasks rather than switching method.")
            else:
                out["warnings"].append(f"Relative D-efficiency is {eff:.1f}%, under {D_EFF_WARN:.0f}%: rebuild "
                                       "with --method balanced, more versions, or fewer prohibitions.")
    else:
        out["relative_d_efficiency_pct"] = None
        out["warnings"].append("Tasks have different numbers of concepts: relative D-efficiency is not computed.")
    return out


def spec_warnings(diag, level_counts):
    if len(level_counts) > 6:
        diag["warnings"].append(f"{len(level_counts)} attributes: full-profile tasks with more than about six "
                                "attributes overload respondents (Green and Srinivasan 1990).")
    counts = sorted(level_counts)
    if counts[-1] >= 2 * counts[0] and counts[-1] >= 4:
        diag["warnings"].append("Level counts differ a lot between attributes; attributes with more levels tend "
                                "to get more importance (number-of-levels effect).")


def cramers_v(xs, ys):
    n = len(xs)
    if n == 0:
        return None
    xl, yl = sorted(set(xs)), sorted(set(ys))
    if len(xl) < 2 or len(yl) < 2:
        return None
    table = {}
    for x, y in zip(xs, ys):
        table[(x, y)] = table.get((x, y), 0) + 1
    rx = {x: sum(1 for v in xs if v == x) for x in xl}
    ry = {y: sum(1 for v in ys if v == y) for y in yl}
    chi2 = 0.0
    for x in xl:
        for y in yl:
            e = rx[x] * ry[y] / n
            chi2 += (table.get((x, y), 0) - e) ** 2 / e
    return math.sqrt(chi2 / (n * (min(len(xl), len(yl)) - 1)))


def sample_size(max_levels, tasks, concepts, respondents=None, subgroups=None, exposure=None):
    """Johnson-Orme n x t x a / c >= 500. With `exposure` (the actual exposures per respondent of the least
    shown level, from a design), n also covers that level: n >= 500 / exposure."""
    if max_levels < 2 or tasks < 1 or concepts < 2:
        raise InputError("sample size needs --max-levels >= 2, --tasks >= 1 and --concepts >= 2")
    if respondents is not None and respondents < 1:
        raise InputError("--respondents must be at least 1")
    if subgroups is not None and subgroups < 1:
        raise InputError("--subgroups must be at least 1")
    num = tasks * concepts
    minimum = -(-EXPOSURE_TARGET * max_levels // num)  # exact integer ceiling
    comfortable = -(-EXPOSURE_COMFORTABLE * max_levels // num)
    out = {"rule": "n x t x a / c >= 500 (Johnson and Orme)", "c": max_levels, "t": tasks, "a": concepts,
           "minimum_n_500": minimum, "planning_n_1000": comfortable, "study_floor": MIN_RESPONDENTS,
           "per_subgroup_floor": MIN_PER_SUBGROUP, "subgroups": subgroups}
    if exposure:
        out["lowest_level_exposures_per_respondent"] = exposure
        out["minimum_n_500_actual"] = math.ceil(EXPOSURE_TARGET / exposure - 1e-9)
        out["planning_n_1000_actual"] = math.ceil(EXPOSURE_COMFORTABLE / exposure - 1e-9)
        minimum = max(minimum, out["minimum_n_500_actual"])
        comfortable = max(comfortable, out["planning_n_1000_actual"])
    # Each separately reported subgroup needs its own floor and its own 500 exposures per level (assumes
    # subgroups of equal size; divide by the smallest subgroup's share otherwise).
    out["per_subgroup_n"] = max(MIN_PER_SUBGROUP, minimum) if subgroups else None
    out["recommended_n"] = max(comfortable, MIN_RESPONDENTS, (subgroups or 0) * max(MIN_PER_SUBGROUP, minimum))
    if respondents is not None:
        out["respondents"] = respondents
        out["exposures_per_level"] = respondents * tasks * concepts / max_levels
        if exposure:
            out["exposures_lowest_level"] = respondents * exposure
    return out


# --------------------------------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------------------------------


def write_design(path, attrs, rows, none, inputs):
    if os.path.exists(path):
        for inp in inputs:
            if inp and os.path.exists(inp) and os.path.samefile(path, inp):
                raise InputError("--out would overwrite an input file; choose another path")
    try:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            w = csv.writer(handle)
            w.writerow(["version", "task", "concept"] + attrs)
            by_task = {}
            for r in rows:
                by_task.setdefault((r["version"], r["task"]), []).append(r)
            for (v, t), concepts_rows in by_task.items():
                for r in concepts_rows:
                    w.writerow([v, t, r["concept"]] + [r[a] for a in attrs])
                if none:
                    w.writerow([v, t, "none"] + [""] * len(attrs))
    except OSError as exc:
        raise InputError(f"cannot write {path}: {exc.strerror or exc}")


def _counts(value):
    return str(value) if isinstance(value, int) else " to ".join(str(v) for v in (min(value), max(value)))


def render_diag(d):
    out = [f"Design: {d['versions']} version(s) x {_counts(d['tasks_per_version'])} task(s) ({d['tasks']} in all), "
           f"{_counts(d['concepts_per_task'])} concept(s) per task"
           + (" + none" if d["none_option"] else "") + f", {d['parameters']} main-effect parameters."]
    if d.get("d_error") is None and d.get("relative_d_efficiency_pct") == 0.0:
        out.append("Relative D-efficiency: 0% (singular information matrix: some effects cannot be estimated)")
    elif d.get("relative_d_efficiency_pct") is not None:
        out.append(f"Relative D-efficiency (main effects, forced choice among the concepts, vs the best design "
                   f"without prohibitions): {d['relative_d_efficiency_pct']:.1f}%   D-error per task: "
                   f"{d['d_error']:.4f}")
    elif d.get("d_error") is not None:
        out.append(f"D-error per task: {d['d_error']:.4f}")
    if d.get("max_cramers_v") is not None:
        a, b = d["max_cramers_v_pair"]
        out.append(f"Largest association between two attributes: Cramer's V = {d['max_cramers_v']:.3f} ({a} x {b})")
    out.append("")
    out.append("Attribute            Levels  Min-max count  Ratio  Max dev.  Tasks with overlap")
    for a in d["attributes"]:
        ratio = "-" if a["max_min_ratio"] is None else f"{a['max_min_ratio']:.2f}"
        dev = "    -" if a["max_deviation_pct"] is None else f"{a['max_deviation_pct']:>6.1f}%"
        ov = ("-" if a["tasks_with_overlap_pct"] is None else f"{a['tasks_with_overlap_pct']:.0f}%") + \
            (" (unavoidable)" if a["overlap_unavoidable"] else "")
        out.append(f"{a['name'][:20]:<20} {a['levels']:>6}  {a['min_count']:>5}-{a['max_count']:<7} {ratio:>5}  "
                   f"{dev}  {ov}")
    for w in d["warnings"]:
        out.append("Warning: " + w)
    return "\n".join(out)


def render_sample(s):
    out = [f"Johnson-Orme rule n x t x a / c >= 500 with c = {s['c']} (most levels), t = {s['t']} tasks, "
           f"a = {s['a']} concepts:",
           f"  minimum n = {s['minimum_n_500']}; for 1,000 exposures per level n = {s['planning_n_1000']}."]
    if "minimum_n_500_actual" in s:
        out.append(f"  From this design's allocation the least shown level appears "
                   f"{s['lowest_level_exposures_per_respondent']:.2f} times per respondent: minimum n = "
                   f"{s['minimum_n_500_actual']}; for 1,000 exposures n = {s['planning_n_1000_actual']}.")
    floors = f"  Floors: {s['study_floor']} per study, {s['per_subgroup_floor']} per subgroup you will report."
    if s.get("subgroups"):
        floors += (f" With {s['subgroups']} reported subgroup(s) of equal size, at least {s['per_subgroup_n']} in "
                   "each (divide by the smallest subgroup's share if they differ).")
    out.append(floors + f" Recommended n = {s['recommended_n']}.")
    if "respondents" in s:
        out.append(f"  With {s['respondents']} respondents each level of the largest attribute appears about "
                   f"{s['exposures_per_level']:.0f} times"
                   + (f"; the least shown level about {s['exposures_lowest_level']:.0f} times."
                      if "exposures_lowest_level" in s else "."))
    return "\n".join(out)


def build_parser():
    p = argparse.ArgumentParser(description="Build and check a choice-based conjoint design.")
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("design", help="generate a design from an attribute spec")
    d.add_argument("spec", help="JSON or text attribute spec")
    d.add_argument("--tasks", type=int, required=True, help="choice tasks per respondent")
    d.add_argument("--concepts", type=int, required=True, help="product concepts per task (not counting none)")
    d.add_argument("--none", action="store_true", help="add a 'none of these' option to every task")
    d.add_argument("--versions", type=int, default=DEFAULT_VERSIONS,
                   help=f"questionnaire versions (default {DEFAULT_VERSIONS}); respondents are assigned in rotation")
    d.add_argument("--method", choices=["balanced", "random"], default="balanced")
    d.add_argument("--seed", type=int, default=DEFAULT_SEED)
    d.add_argument("--out", help="design CSV to write (refuses to overwrite the spec)")
    d.add_argument("--respondents", type=int, help="planned respondents, for exposures per level")
    d.add_argument("--subgroups", type=int, help="number of subgroups you will report separately")
    d.add_argument("--json", action="store_true")
    c = sub.add_parser("check", help="diagnose an existing design file")
    c.add_argument("design", help="design CSV: version,task,concept plus one column per attribute")
    c.add_argument("--spec", help="the attribute spec, to check prohibitions and unused levels")
    c.add_argument("--attribute-cols", help="comma-separated attribute columns (default: every other column)")
    c.add_argument("--delimiter", help="comma, semicolon, tab, pipe or one character (default: sniffed)")
    c.add_argument("--respondents", type=int, help="planned respondents, for exposures per level")
    c.add_argument("--subgroups", type=int, help="number of subgroups you will report separately")
    c.add_argument("--json", action="store_true")
    s = sub.add_parser("sample-size", help="Johnson-Orme sample size")
    s.add_argument("--max-levels", type=int, required=True, help="levels of the attribute with the most levels")
    s.add_argument("--tasks", type=int, required=True)
    s.add_argument("--concepts", type=int, required=True, help="concepts per task, not counting none")
    s.add_argument("--respondents", type=int)
    s.add_argument("--subgroups", type=int)
    s.add_argument("--json", action="store_true")
    return p


def run(args):
    if args.command == "sample-size":
        s = sample_size(args.max_levels, args.tasks, args.concepts, args.respondents, args.subgroups)
        return s, render_sample(s)
    if args.command == "design":
        attributes, prohibitions = load_spec(args.spec)
        names = [a["name"] for a in attributes]
        if args.respondents is not None and args.respondents < 1 or args.subgroups is not None and args.subgroups < 1:
            raise InputError("--respondents and --subgroups must be at least 1")
        rows, allowed = generate(attributes, prohibitions, args.tasks, args.concepts, args.versions, args.method,
                                 args.seed)
        levels = {a["name"]: a["levels"] for a in attributes}
        tasks = {}
        for r in rows:
            tasks.setdefault((r["version"], r["task"]), []).append(tuple(r[n] for n in names))
        task_list = [(k[0], k[1], v) for k, v in tasks.items()]
        diag = diagnostics(names, levels, task_list, args.none, prohibitions, args.method)
        if diag.get("d_error") is None:
            raise InputError("the design's information matrix is singular, so some effects cannot be estimated "
                             "(usually prohibitions that leave a level with only one partner, or too few tasks "
                             "and versions for the number of parameters). Loosen the prohibitions or add tasks; "
                             "nothing was written")
        ss = sample_size(max(len(a["levels"]) for a in attributes), args.tasks, args.concepts, args.respondents,
                         args.subgroups, diag["lowest_level_exposures_per_respondent"])
        result = {"version": VERSION, "method": args.method, "seed": args.seed, "spec": args.spec,
                  "attributes": attributes, "prohibitions": prohibitions, "allowed_profiles": allowed or None,
                  "diagnostics": diag, "sample_size": ss, "out": args.out}
        spec_warnings(diag, [len(a["levels"]) for a in attributes])
        if args.method == "random":
            dups = sum(1 for _, _, profs in task_list if len(set(profs)) < len(profs))
            diag["tasks_with_duplicate_concepts"] = dups
            if dups:
                diag["warnings"].append(f"{dups} task(s) show the same concept twice. Expected with --method random "
                                        "(concepts are drawn independently); keep them for an AMCE analysis.")
        if args.out:
            write_design(args.out, names, rows, args.none, [args.spec])
        text = f"Method {args.method}, seed {args.seed}.\n" + render_diag(diag) + "\n\n" + render_sample(ss)
        if args.out:
            text += f"\n\nWrote {len(rows)} concept rows" + (" plus a none row per task" if args.none else "") + \
                    f" to {args.out}."
        return result, text
    if args.respondents is not None and args.respondents < 1 or args.subgroups is not None and args.subgroups < 1:
        raise InputError("--respondents and --subgroups must be at least 1")
    attrs, rows = read_design(args.design, args.delimiter, args.attribute_cols)
    task_list, has_none = design_tasks(attrs, rows)
    levels = {a: [] for a in attrs}
    for _, _, profs in task_list:
        for prof in profs:
            for a, l in zip(attrs, prof):
                if l not in levels[a]:
                    levels[a].append(l)
    prohibitions = []
    if args.spec:
        spec_attrs, prohibitions = load_spec(args.spec)
        spec_names = [a["name"] for a in spec_attrs]
        if sorted(spec_names) != sorted(attrs):
            raise InputError(f"the spec's attributes ({', '.join(spec_names)}) differ from the design's "
                             f"({', '.join(attrs)})")
        for a in spec_attrs:
            extra = [l for l in levels[a["name"]] if l not in a["levels"]]
            if extra:
                raise InputError(f"{a['name']}: design levels not in the spec: {', '.join(extra)}")
            levels[a["name"]] = list(a["levels"])
    for a in attrs:
        if len(levels[a]) < 2:
            raise InputError(f"attribute {a!r} has {len(levels[a])} level(s) in the design; it needs two or more to "
                             "be estimated")
    diag = diagnostics(attrs, levels, task_list, has_none, prohibitions)
    spec_warnings(diag, [len(levels[a]) for a in attrs])
    if prohibitions:
        bad = sum(1 for _, _, profs in task_list for prof in profs
                  if prohibited(dict(zip(attrs, prof)), prohibitions, attrs))
        diag["prohibited_concepts"] = bad
        if bad:
            diag["warnings"].append(f"{bad} concept(s) break a prohibition in the spec.")
    dups = sum(1 for _, _, profs in task_list if len(set(profs)) < len(profs))
    diag["tasks_with_duplicate_concepts"] = dups
    if dups:
        diag["warnings"].append(f"{dups} task(s) show the same concept twice (expected only in a fully randomized "
                                "design).")
    tasks_per_version = {}
    for v, t, _ in task_list:
        tasks_per_version[v] = tasks_per_version.get(v, 0) + 1
    if len(set(tasks_per_version.values())) > 1:
        diag["warnings"].append("Versions have different numbers of tasks; the sample size below uses the "
                                "shortest version and the actual exposures per level.")
    t_per = min(tasks_per_version.values())
    sizes = diag["concepts_per_task"]
    a_per = sizes if isinstance(sizes, int) else min(sizes)
    ss = sample_size(max(len(l) for l in levels.values()), t_per, a_per, args.respondents, args.subgroups,
                     diag["lowest_level_exposures_per_respondent"])
    result = {"version": VERSION, "design": args.design, "attributes": attrs, "levels": levels,
              "diagnostics": diag, "sample_size": ss}
    return result, render_diag(diag) + "\n\n" + render_sample(ss)


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result, text = run(args)
    except InputError as exc:
        print(f"conjoint-design: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2) if args.json else text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
