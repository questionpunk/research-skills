#!/usr/bin/env python3
"""Kano analysis: classify each respondent's functional/dysfunctional answer pair with Kano's evaluation table
(Berger et al. 1993), assign each feature its category (the mode, ties M > O > A > I), test whether the top
category is a clear winner (Fong 1996), and compute Better/Worse coefficients (Timko, in Berger et al. 1993)
with intervals, self-stated importance, segments and an optional quadrant chart. The `design` command writes
the question pairs for a feature list and checks wording you supply.

Standard library only, Python 3.9+. No network, no randomness. Formulas and thresholds: references/sources.md.

Usage:
  python3 scripts/kano_analysis.py analyze answers.csv
  python3 scripts/kano_analysis.py analyze answers.csv --pair "Dark mode=dm_f,dm_d" --pair "Sync=sync_f,sync_d"
  python3 scripts/kano_analysis.py analyze export.csv --qp-answer-col "Q3" --segment-col plan --chart kano.svg
  python3 scripts/kano_analysis.py analyze long.csv --long --feature-col feature --functional-col f \
      --dysfunctional-col d --respondent-col id
  python3 scripts/kano_analysis.py analyze --counts counts.csv
  python3 scripts/kano_analysis.py design --features "Dark mode;Offline sync" --product "the app"

Answers: 1 like, 2 must-be (expect), 3 neutral, 4 live with, 5 dislike (Berger et al.'s order), or the answer
text. If your tool numbers them the other way (1 dislike ... 5 like), pass --code-order dislike-first.

Exit codes: 0 success; 2 bad input or a refused calculation (the message says what to fix).
"""
import argparse
import csv
import io
import json
import math
import os
import re
import sys
from statistics import NormalDist

VERSION = "0.1.0"

CATEGORIES = ["A", "O", "M", "I", "R", "Q"]
NAMES = {"A": "attractive", "O": "one-dimensional", "M": "must-be", "I": "indifferent", "R": "reverse",
         "Q": "questionable"}
TIE_ORDER = ["M", "O", "A", "I", "R", "Q"]  # Berger et al. (1993) p. 11 for M > O > A > I; R, Q our extension
# Rows: functional answer 1-5 (like, must-be, neutral, live with, dislike); columns: dysfunctional answer.
TABLE = ["QAAAO", "RIIIM", "RIIIM", "RIIIM", "RRRRQ"]  # Berger et al. (1993) p. 6, Fig. 4
FONG_Z = 1.65  # Fong (1996), as applied by Raverta and Loera (2026)
Q_WARN_SHARE = 0.10  # convention of this skill (Sauerwein et al. 1996 saw at most 2%)
SMALL_N = 30  # convention of this skill: features with fewer answers are flagged as a small base
UNREADABLE_STOP = 0.05
R_WARN_SHARE = 0.20  # convention of this skill: overall reverse share that prompts a code-order check
OVERALL = object()  # key of the all-respondents results; never equal to a segment value from the data
ANSWER_WORDS = ["like", "must-be", "neutral", "live with", "dislike"]
BERGER_ENGLISH = ["I like it that way", "It must be that way", "I am neutral", "I can live with it that way",
                  "I dislike it that way"]
LABELS = {
    1: ["i like it that way", "i like it", "like it", "like", "i would like it", "i would like it that way",
        "i'd like it", "i enjoy it", "delighted", "i like it this way"],
    2: ["it must be that way", "must be that way", "must be", "must-be", "i expect it", "i expect it that way",
        "i expect it to be that way", "expect it", "expected", "it must be this way", "i expect it this way",
        "it is a basic requirement", "must have"],
    3: ["i am neutral", "i'm neutral", "im neutral", "neutral", "i don't care", "i do not care", "indifferent",
        "i feel neutral", "doesn't matter", "does not matter", "i don't mind"],
    4: ["i can live with it that way", "i can live with it", "live with it", "live with", "i can tolerate it",
        "tolerate", "i tolerate it", "tolerable", "i can live with it this way", "i can accept it"],
    5: ["i dislike it that way", "i dislike it", "dislike it", "dislike", "i don't like it", "i do not like it",
        "i dislike it this way", "i would dislike it", "i'd dislike it"],
}


def _label_key(text):
    """Lower-case, curly apostrophe and dashes normalised ("must-be" = "must be"), other punctuation dropped."""
    text = re.sub("[-\u2010-\u2015]", " ", text.casefold().replace("\u2019", "'"))
    return re.sub(r"\s+", " ", re.sub(r"[^\w' ]", "", text)).strip()


LABEL_LOOKUP = {_label_key(v): k for k, vs in LABELS.items() for v in vs}
NA = {"", "na", "n/a", "#n/a", "nan", "null", "none", "-"}
DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|", "\\t": "\t"}
QP_HEADER = re.compile(r"^(?P<q>.*?) \| (?P<feature>.+): (?P<part>functional|dysfunctional|category|importance)$")
# One line per feature; either half may be blank when the respondent skipped it ("Dark mode: 1 / ").
QP_LINE = re.compile(r"^(?P<feature>.+): (?P<f>[^/]*?)\s*/\s*(?P<d>.*?)(?: · (?P<r>\d+)/9)?$")
F_SUFFIX = re.compile(r"^(?P<stem>.+?)[\s_\-:|.(\[]+(?P<word>functional|func|positive|pos|present|has|f)[\])]?$", re.I)
D_SUFFIX = re.compile(r"^(?P<stem>.+?)[\s_\-:|.(\[]+(?P<word>dysfunctional|dysfunc|dys|negative|neg|absent|"
                      r"has[\s_\-]?not|d)[\])]?$", re.I)
# Only these suffixes stop the run when their partner is missing; the generic ones ("_has", "_pos", " D") also
# name ordinary columns, so an unpaired one is ignored and listed in the notes.
STRONG_SUFFIX = {"functional", "func", "dysfunctional", "dysfunc", "dys"}
I_SUFFIX = re.compile(r"^(?P<stem>.+?)[\s_\-:|.(\[]+(?P<word>importance|imp|importance_1_9)[\])]?$", re.I)


# A whole code ("2", or "2.0" from a spreadsheet), optionally followed by a label; "2.5" is not a code.
CODE_RE = re.compile(r"^\(?\s*([1-5])(?:\.0+)?\s*\)?"
                     r"(?:\s*[-\u2013\u2014:=.)]\s*(?P<label>\D.*)?|\s+(?P<label2>\D.*))?$")
IMPORTANCE_SCALE_MIN_N = 10  # convention of this skill: answers needed before noting a possibly shorter scale


class InputError(Exception):
    """Bad input or a refused calculation; exit code 2."""


# ------------------------------------------------------------------------------------------------ method

def classify(functional, dysfunctional):
    """Kano category for one answer pair (each 1-5 in Berger's order)."""
    return TABLE[functional - 1][dysfunctional - 1]


def fong(a, b, n):
    """Fong's (1996) threshold; the top category is a clear winner when |a - b| >= threshold."""
    if n <= 0:
        return None
    threshold = FONG_Z * math.sqrt((a + b) * (2 * n - a - b) / (2 * n))
    return {"a": a, "b": b, "n": n, "threshold": threshold, "difference": abs(a - b),
            "significant": abs(a - b) >= threshold and abs(a - b) > 0}


def wilson(x, n, z):
    if n <= 0:
        return None
    p = x / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0)) / denom
    return [max(0.0, centre - half), min(1.0, centre + half)]


def summarize(name, counts, importance, z, small_n):
    n = sum(counts[c] for c in CATEGORIES)
    out = {"feature": name, "n": n, "counts": dict(counts),
           "shares": {c: (counts[c] / n if n else None) for c in CATEGORIES}}
    if n == 0:
        out.update({"category": None, "tied_with": [], "fong": None, "better": None, "worse": None,
                    "better_ci": None, "worse_ci": None, "importance": None, "notes": ["no answers"]})
        return out
    top = max(counts[c] for c in CATEGORIES)
    tied = [c for c in TIE_ORDER if counts[c] == top]
    category = tied[0]
    ranked = sorted(CATEGORIES, key=lambda c: (-counts[c], TIE_ORDER.index(c)))
    out["category"] = category
    out["category_name"] = NAMES[category]
    out["tied_with"] = tied if len(tied) > 1 else []
    out["second"] = ranked[1]
    # Every class level with the runner-up, so a tie for second place is visible ("A vs M/O").
    out["runners_up"] = [c for c in TIE_ORDER if c != category and counts[c] == counts[ranked[1]]]
    out["fong"] = fong(counts[ranked[0]], counts[ranked[1]], n)
    base = counts["A"] + counts["O"] + counts["M"] + counts["I"]
    out["base_aomi"] = base
    if base:
        out["better"] = (counts["A"] + counts["O"]) / base
        out["worse"] = -(counts["O"] + counts["M"]) / base or 0.0
        out["better_ci"] = wilson(counts["A"] + counts["O"], base, z)
        wci = wilson(counts["O"] + counts["M"], base, z)
        out["worse_ci"] = [-wci[1] + 0.0, -wci[0] + 0.0]  # + 0.0 turns -0.0 into 0.0
    else:
        out["better"] = out["worse"] = out["better_ci"] = out["worse_ci"] = None
    notes = []
    if importance:
        mean_imp = sum(importance) / len(importance)
        out["importance"] = {"mean": mean_imp, "n": len(importance)}
        if out["better"] is not None:
            scale = (mean_imp - 1) / 8
            out["importance"]["better_weighted"] = out["better"] * scale
            out["importance"]["worse_weighted"] = out["worse"] * scale + 0.0
    else:
        out["importance"] = None
    if out["tied_with"]:
        notes.append(f"tie between {', '.join(out['tied_with'])}; resolved M > O > A > I (Berger et al. 1993), "
                     "then R > Q (this skill's convention); report it as a tie")
    if out["fong"] and not out["fong"]["significant"]:
        notes.append(f"not a clear winner: {category} vs {'/'.join(out['runners_up'])} (Fong's test)")
    if counts["Q"] / n > Q_WARN_SHARE:
        notes.append(f"questionable answers {100 * counts['Q'] / n:.0f}%: the question pair may be unclear")
    if category == "R":
        notes.append("reverse is the mode: check the code order and that the functional question is the 'has it' "
                     "form; if both are right, most respondents do not want this feature (Berger et al. 1993)")
    if n < small_n:
        notes.append(f"small base (n = {n})")
    out["notes"] = notes
    return out


# ------------------------------------------------------------------------------------------------ reading

def decode(data, path):
    if data.startswith(b"\xef\xbb\xbf"):
        raw, codec, encoding = data[3:], "utf-8", "UTF-8 with BOM"
    elif data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        raw, codec, encoding = data, "utf-16", "UTF-16"
    elif b"\x00" in data[:200]:
        raise InputError(f"{path} looks like UTF-16 without a byte-order mark; re-export it as CSV UTF-8")
    else:
        raw, codec, encoding = data, "utf-8", "UTF-8"
    try:
        return raw.decode(codec), encoding
    except UnicodeDecodeError as exc:
        raise InputError(f"{path} is not valid {encoding} text (byte {exc.start}); re-export it as 'CSV UTF-8' "
                         "(Excel)")


def sniff_delimiter(text, candidates=(",", ";", "\t", "|")):
    lines = [line for line in text.splitlines() if line.strip()][:50]
    best, best_key = ",", None
    for delim in candidates:
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


def read_table(path, delimiter=None, skip_rows=None, notes=None):
    notes = notes if notes is not None else []
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except FileNotFoundError:
        raise InputError(f"file not found: {path}")
    except IsADirectoryError:
        raise InputError(f"{path} is a folder, not a CSV file")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror}")
    text, encoding = decode(data, path)
    if encoding != "UTF-8":
        notes.append(f"Read as {encoding}.")
    if skip_rows is not None and skip_rows < 0:
        raise InputError("--skip-rows must be 0 or more")
    excel_sep = re.match(r"^\s*sep=(.)\s*?(\r\n|\n|\r)", text)
    if excel_sep and not delimiter:
        delimiter = excel_sep.group(1)
    if excel_sep:
        text = text[excel_sep.end():]
        notes.append("Skipped Excel's 'sep=' line.")
    if delimiter:
        delim = DELIMITERS.get(delimiter.lower(), delimiter)
        if len(delim) != 1:
            raise InputError(f"--delimiter takes one character or comma, semicolon, tab, pipe; got {delimiter!r}")
    else:
        # A pipe inside QuestionPunk headers ("Q3 | Dark mode: functional") must not win the sniff.
        delim = sniff_delimiter(text)
        first = next((line for line in text.splitlines() if line.strip()), "")
        if delim == "|" and " | " in first:
            delim = sniff_delimiter(text, (",", ";", "\t"))
    # strict: an unterminated quote is an error, not one long cell that swallows the rows after it.
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim, strict=True)
    table, last = [], 0  # (physical line where the record starts, cells)
    try:
        for r in reader:
            if any(c.strip() for c in r):
                table.append((last + 1, r))
            last = reader.line_num
    except csv.Error as exc:
        raise InputError(f"{path} is not valid CSV: the record starting on line {last + 1} fails ({exc}). Look "
                         "for an unclosed quote mark.")
    if not table:
        raise InputError(f"{path} is empty or has no header row")
    headers = [h.strip() for h in table[0][1]]
    while headers and not headers[-1]:  # Excel's trailing empty columns; their cells are trimmed below
        headers.pop()
    repeated = sorted({h for h in headers if headers.count(h) > 1})
    if repeated:
        raise InputError(f"{path} has more than one column named {', '.join(repr(h) for h in repeated)}. Rename "
                         "them so each column is unique.")
    body = table[1:]
    if skip_rows is None:
        skip_rows = 0
        if len(body) >= 2 and any(c.strip().startswith('{"ImportId"') for c in body[1][1]):
            skip_rows = 2
            notes.append("Qualtrics export detected: skipped the question-text and ImportId rows under the header.")
    elif skip_rows:
        notes.append(f"Skipped {skip_rows} row(s) under the header (--skip-rows).")
    rows = []
    for line, row in body[skip_rows:]:
        if len(row) > len(headers) and not any(c.strip() for c in row[len(headers):]):
            row = row[: len(headers)]
        if len(row) != len(headers):
            raise InputError(f"{path} line {line} has {len(row)} cells but the header has {len(headers)}; fix the "
                             "row or pass --delimiter.")
        rows.append(dict(zip(headers, row)))
    return headers, rows


def _label_code(text):
    return LABEL_LOOKUP.get(_label_key(text))


def read_answer(raw, reverse):
    """(code 1-5 in Berger's order, None) or (None, reason). A recognised answer text wins over its number,
    so '1 - I dislike it' is read as dislike whatever the code order."""
    text = (raw or "").strip()
    if text.casefold() in NA:
        return None, "blank"
    m = CODE_RE.match(text)
    if m:
        label = (m.group("label") or m.group("label2") or "").strip()
        if label:
            # A label wins over the number; one we do not know ("1 - Strongly disagree", another language) makes
            # the answer unreadable rather than trusting a number whose direction the label may contradict.
            code = _label_code(label)
            return (code, None) if code else (None, "unreadable")
        code = int(m.group(1))
        return (6 - code if reverse else code), None
    code = _label_code(text)
    if code:
        return code, None
    return None, "unreadable"


def answer_is_numeric(raw):
    """True for a bare code ("2", "2.0"): only these depend on --code-order."""
    m = CODE_RE.match((raw or "").strip())
    return bool(m) and not (m.group("label") or m.group("label2") or "").strip()


def read_importance(raw):
    text = (raw or "").strip()
    if text.casefold() in NA:
        return None
    m = re.match(r"^\(?\s*([1-9])(?:\.0+)?\s*\)?(?:\s*/\s*9)?(?:\s*[-–—:=.)]\s*(?:\D.*)?)?$", text)
    return int(m.group(1)) if m else "bad"


def detect_pairs(headers, args, notes):
    """Returns list of (feature, functional col, dysfunctional col, importance col or None) and a source label."""
    if args.pair:
        pairs = []
        for item in args.pair:
            if "=" not in item:
                raise InputError(f"--pair takes 'FEATURE=FUNCTIONAL_COL,DYSFUNCTIONAL_COL[,IMPORTANCE_COL]'; got {item!r}")
            name, cols = item.split("=", 1)
            if not name.strip():
                raise InputError(f"--pair {item!r} has no feature name before '='")
            # Parsed as one CSV record, so a column name holding a comma can be double-quoted.
            try:
                parts = [c.strip() for c in next(csv.reader([cols], skipinitialspace=True, strict=True))]
            except (csv.Error, StopIteration):
                raise InputError(f"--pair {name}: cannot read the column list {cols!r}")
            if len(parts) not in (2, 3):
                raise InputError(f"--pair {name}: give two or three column names (double-quote a name that "
                                 "contains a comma)")
            for c in parts:
                if c not in headers:
                    raise InputError(f"--pair {name}: column {c!r} not found. Columns: {', '.join(headers)}")
            pairs.append((name.strip(), parts[0], parts[1], parts[2] if len(parts) == 3 else None))
        check_pairs(pairs)
        return pairs, "--pair"
    qp = {}
    for h in headers:
        m = QP_HEADER.match(h)
        if m:
            qp.setdefault((m.group("q"), m.group("feature")), {})[m.group("part")] = h
    if qp:
        questions = sorted({q for q, _ in qp})
        if args.question:
            questions = [q for q in questions if q == args.question]
            if not questions:
                raise InputError(f"--question {args.question!r} not found in the export headers")
        elif len(questions) > 1:
            raise InputError("the export has several Kano questions (" + ", ".join(questions) + "); pick one with "
                             "--question")
        chosen = {feat: parts for (q, feat), parts in qp.items() if q == questions[0]}
        orphans = sorted(feat for feat, parts in chosen.items()
                         if ("functional" in parts) != ("dysfunctional" in parts))
        if orphans:
            raise InputError(f"question {questions[0]}: these features have only one of the functional/dysfunctional "
                             "columns: " + ", ".join(orphans) + ". Find the missing column, or pass --pair for each "
                             "feature you want analysed.")
        pairs = [(feat, parts["functional"], parts["dysfunctional"], parts.get("importance"))
                 for feat, parts in chosen.items() if "functional" in parts]
        return pairs, f"QuestionPunk export, question {questions[0]}"
    funcs, dysfs, imps = {}, {}, {}
    for h in headers:
        for rx, store in ((D_SUFFIX, dysfs), (I_SUFFIX, imps), (F_SUFFIX, funcs)):
            m = rx.match(h)
            if m:
                key = m.group("stem").strip().casefold()
                if key in store:
                    raise InputError(f"columns {store[key][1]!r} and {h!r} both look like the same half of the "
                                     f"{m.group('stem').strip()!r} pair; pass --pair to say which to use")
                store[key] = (m.group("stem").strip(), h, m.group("word").casefold())
                break
    stems = [s for s in funcs if s in dysfs]
    if not stems:
        raise InputError("could not find functional/dysfunctional column pairs. Name them like 'dark_mode_f' and "
                         "'dark_mode_d' (or '... functional' / '... dysfunctional'), pass --pair "
                         "'Feature=func_col,dysfunc_col' for each feature, --qp-answer-col for a QuestionPunk "
                         f"answer column, or --long. Columns: {', '.join(headers)}")
    halves = [store[s] for store in (funcs, dysfs) for s in store if s not in stems]
    strong = sorted(h for _, h, word in halves if word in STRONG_SUFFIX)
    if strong:
        raise InputError("these columns look like half of a Kano pair but have no partner: "
                         + ", ".join(strong) + ". Pass --pair for each feature.")
    if halves:
        notes.append("Ignored columns whose names end like half of a pair but have no partner: "
                     + ", ".join(sorted(h for _, h, _ in halves)) + ". If one is a Kano answer, pass --pair.")
    return [(funcs[s][0], funcs[s][1], dysfs[s][1], imps.get(s, (None, None))[1]) for s in stems], "column names"


def check_pairs(pairs):
    """One pair per feature, and no column used by two pairs (it would count the same answers twice)."""
    names = [p[0].casefold() for p in pairs]
    repeated = sorted({p[0] for p in pairs if names.count(p[0].casefold()) > 1})
    if repeated:
        raise InputError("--pair names the same feature more than once: " + ", ".join(repeated))
    cols = [c for p in pairs for c in p[1:] if c]
    reused = sorted({c for c in cols if cols.count(c) > 1})
    if reused:
        raise InputError("these columns are used by more than one --pair (or twice in one): " + ", ".join(reused))


def parse_count(name, cat, raw):
    """A count must be a whole, finite, non-negative number; '12.0' from a spreadsheet is accepted."""
    text = (raw or "").strip()
    if not text:
        raise InputError(f"--counts: {name} {cat} is blank; write 0 if nobody gave that answer")
    try:
        value = float(text)
    except ValueError:
        raise InputError(f"--counts: {name} {cat} is {text!r}, not a number")
    if not math.isfinite(value) or value < 0 or value != int(value):
        raise InputError(f"--counts: {name} {cat} is {text!r}; counts must be whole numbers of answers (0 or more). "
                         "Percentages are not counts: Fong's test and the intervals need the real numbers.")
    return int(value)


def collect(args, notes):
    """Returns ({segment: {feature: (counts, importance list)}}, feature order, stats)."""
    reverse = args.code_order == "dislike-first"
    if args.counts:
        headers, rows = read_table(args.counts, args.delimiter, 0, notes)
        lower = {h.lower(): h for h in headers}
        need = ["feature"] + [c.lower() for c in CATEGORIES]
        missing = [c for c in need if c not in lower]
        if missing:
            raise InputError(f"--counts file needs columns feature,A,O,M,I,R,Q; missing {', '.join(missing)}")
        if not rows:
            raise InputError(f"{args.counts} has a header but no features")
        data, order = {OVERALL: {}}, []
        for r in rows:
            name = r[lower["feature"]].strip()
            if not name:
                raise InputError("--counts: a row has no feature name")
            if name.casefold() in (o.casefold() for o in order):
                raise InputError(f"--counts: feature {name!r} appears more than once; give one row per feature")
            counts = {c: parse_count(name, c, r[lower[c.lower()]]) for c in CATEGORIES}
            data[OVERALL][name] = (counts, [])
            order.append(name)
        return data, order, {"respondents": None, "rows": len(rows), "source": "counts"}
    if not args.input:
        raise InputError("give a CSV of answers (or --counts FILE)")
    headers, rows = read_table(args.input, args.delimiter, args.skip_rows, notes)
    if not rows:
        raise InputError(f"{args.input} has a header but no respondents")
    if args.segment_col and args.segment_col not in headers:
        raise InputError(f"segment column {args.segment_col!r} not found. Columns: {', '.join(headers)}")
    stats = {"respondents": len(rows), "rows": len(rows), "incomplete_pairs": 0, "unreadable": 0, "read": 0,
             "bad_importance": 0, "numeric": 0, "no_segment": 0, "no_feature": 0}
    data, order = {OVERALL: {}}, []
    unreadable_examples = []
    canonical = {}  # "dark mode" -> "Dark mode": spellings that differ only in case are one feature

    def unreadable(raw, weight=1):
        stats["unreadable"] += weight
        if len(unreadable_examples) < 5 and raw.strip() not in unreadable_examples:
            unreadable_examples.append(raw.strip())

    def add(segment, feature, f, d, imp):
        feature = canonical.setdefault(feature.casefold(), feature)
        seg = data.setdefault(segment, {})
        if feature not in seg:
            seg[feature] = ({c: 0 for c in CATEGORIES}, [])
        if feature not in order:
            order.append(feature)
        if f is None or d is None:
            return
        seg[feature][0][classify(f, d)] += 1
        if imp is not None:
            seg[feature][1].append(imp)

    def handle(segs, feature, fraw, draw, iraw):
        f, fr = read_answer(fraw, reverse)
        d, dr = read_answer(draw, reverse)
        for raw, reason in ((fraw, fr), (draw, dr)):
            if reason == "unreadable":
                unreadable(raw)
            elif reason is None:
                stats["read"] += 1
                stats["numeric"] += answer_is_numeric(raw)
        if (fr == "blank" and dr is None) or (dr == "blank" and fr is None):  # one half read, the other skipped
            stats["incomplete_pairs"] += 1
        imp = None
        if iraw is not None and f is not None and d is not None:
            v = read_importance(iraw)
            if v == "bad":
                stats["bad_importance"] += 1
            else:
                imp = v
        for seg in segs:
            add(seg, feature, f if d is not None else None, d if f is not None else None, imp)

    if args.qp_answer_col or args.long:
        if args.qp_answer_col:
            if args.qp_answer_col not in headers:
                raise InputError(f"--qp-answer-col {args.qp_answer_col!r} not found. Columns: {', '.join(headers)}")
            source = "QuestionPunk answer text"
            for line_no, r in enumerate(rows, 1):
                segs = segments_of(r, args, stats)
                seen = set()
                for line in (r[args.qp_answer_col] or "").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    m = QP_LINE.match(line)
                    if not m:
                        unreadable(line, 2)  # a line holds both halves of a pair
                        continue
                    name = m.group("feature").strip()
                    if name.casefold() in seen:
                        raise InputError(f"--qp-answer-col: respondent {line_no} has more than one answer for {name!r}")
                    seen.add(name.casefold())
                    handle(segs, name, m.group("f"), m.group("d"), m.group("r"))
        else:
            cols = [args.feature_col, args.functional_col, args.dysfunctional_col]
            if not all(cols):
                raise InputError("--long needs --feature-col, --functional-col and --dysfunctional-col")
            for c in cols + [c for c in (args.importance_col, args.respondent_col) if c]:
                if c not in headers:
                    raise InputError(f"column {c!r} not found. Columns: {', '.join(headers)}")
            source = "long format"
            # One row per respondent x feature: rows are not respondents. Count respondents only from an ID column.
            stats["respondents"] = None
            ids, seen = set(), set()
            for r in rows:
                feature = (r[args.feature_col] or "").strip()
                if not feature:
                    stats["no_feature"] += 1
                    continue
                if args.respondent_col:
                    rid = (r[args.respondent_col] or "").strip()
                    if not rid:
                        raise InputError(f"a row for {feature!r} has no {args.respondent_col!r}")
                    if (rid, feature.casefold()) in seen:
                        raise InputError(f"respondent {rid!r} has more than one answer for {feature!r}; keep one row "
                                         "per respondent and feature")
                    seen.add((rid, feature.casefold()))
                    ids.add(rid)
                handle(segments_of(r, args, stats), feature, r[args.functional_col], r[args.dysfunctional_col],
                       r[args.importance_col] if args.importance_col else None)
            if args.respondent_col:
                stats["respondents"] = len(ids)
            else:
                notes.append(f"{len(rows)} rows, one per respondent and feature; pass --respondent-col to count "
                             "respondents.")
            if stats["no_feature"]:
                notes.append(f"{stats['no_feature']} row(s) have no feature name and were left out.")
    else:
        pairs, source = detect_pairs(headers, args, notes)
        if not pairs:
            raise InputError("no Kano feature columns found")
        for r in rows:
            segs = segments_of(r, args, stats)
            for feature, fc, dc, ic in pairs:
                handle(segs, feature, r[fc], r[dc], r[ic] if ic else None)
    total = stats["read"] + stats["unreadable"]
    if total == 0:
        raise InputError("no Kano answers found in the file")
    if stats["unreadable"] / total > UNREADABLE_STOP and not args.allow_unreadable:
        raise InputError(f"{stats['unreadable']} of {total} answers ({stats['unreadable'] / total:.1%}) could not be "
                         "read as one of the five Kano answers, e.g. " + "; ".join(repr(x) for x in unreadable_examples)
                         + ". Map them (codes 1-5, or Berger's wording), or pass --allow-unreadable to exclude them.")
    if stats["unreadable"]:
        notes.append(f"{stats['unreadable']} answer(s) could not be read and were left out, e.g. "
                     + "; ".join(repr(x) for x in unreadable_examples) + ".")
    if stats["incomplete_pairs"]:
        notes.append(f"{stats['incomplete_pairs']} feature answer(s) had only one half of the pair and were left out.")
    if stats["bad_importance"]:
        notes.append(f"{stats['bad_importance']} importance answer(s) were not 1-9 and were left out.")
    importance = [v for _, values in data[OVERALL].values() for v in values]
    if len(importance) >= IMPORTANCE_SCALE_MIN_N and max(importance) <= 7:
        notes.append(f"No importance answer is above {max(importance)}: the weighted coefficients assume Berger's "
                     "1-9 scale. If the question used 1-5 or 1-7, read only the order of the means.")
    if stats["no_segment"]:
        notes.append(f"{stats['no_segment']} row(s) have no {args.segment_col} value; they count under All "
                     "respondents only.")
    stats["source"] = source
    return data, order, stats


def segments_of(row, args, stats):
    segs = [OVERALL]
    if args.segment_col:
        value = (row[args.segment_col] or "").strip()
        if value.casefold() in NA:
            stats["no_segment"] += 1
        else:
            segs.append(value)
    return segs


# ------------------------------------------------------------------------------------------------ analysis

def same_file(a, b):
    if os.path.realpath(a) == os.path.realpath(b):
        return True
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def check_chart_path(args):
    """--chart must never replace the data being analysed, and replaces another file only with --overwrite."""
    for source in (args.input, args.counts):
        if source and same_file(args.chart, source):
            raise InputError(f"--chart {args.chart} is the input file; choose another name")
    if os.path.exists(args.chart) and not args.overwrite:
        raise InputError(f"{args.chart} already exists; choose another name or pass --overwrite")


def confidence_level(value):
    level = value / 100.0 if value > 1 else value
    if not (math.isfinite(level) and 0 < level < 1):
        raise InputError(f"--confidence must be between 0 and 1 (e.g. 0.95) or 0 and 100 (e.g. 95); got {value:g}")
    return level


def check_flags(args):
    """Refuse options that would be silently ignored, so the run does what the command line says."""
    given = lambda *names: [n for n in names if getattr(args, n.lstrip("-").replace("-", "_"))]
    if args.counts:
        extra = given("input", "--pair", "--long", "--qp-answer-col", "--segment-col", "--question", "--skip-rows",
                      "--respondent-col", "--feature-col", "--functional-col", "--dysfunctional-col",
                      "--importance-col")
        if args.code_order != "like-first":
            extra.append("--code-order")
        if extra:
            raise InputError("--counts reads category counts only; drop " + ", ".join(extra))
        return
    modes = given("--pair", "--long", "--qp-answer-col")
    if len(modes) > 1:
        raise InputError("use one of --pair, --long and --qp-answer-col, not " + " and ".join(modes))
    if not args.long:
        extra = given("--feature-col", "--functional-col", "--dysfunctional-col", "--importance-col",
                      "--respondent-col")
        if extra:
            raise InputError(", ".join(extra) + " go with --long")
    if args.question and (args.pair or args.long or args.qp_answer_col):
        raise InputError("--question picks a question in a QuestionPunk wide export; it does not combine with "
                         + modes[0])


def analyse(args):
    notes = []
    check_flags(args)
    args.confidence = confidence_level(args.confidence)
    z = NormalDist().inv_cdf(1 - (1 - args.confidence) / 2)
    if args.chart:
        check_chart_path(args)
    data, order, stats = collect(args, notes)
    segments = [OVERALL] + sorted(s for s in data if s is not OVERALL)
    results = {}
    for seg in segments:
        feats = []
        for name in order:
            counts, imp = data.get(seg, {}).get(name, ({c: 0 for c in CATEGORIES}, []))
            feats.append(summarize(name, counts, imp, z, args.small_base))
        feats.sort(key=lambda f: (TIE_ORDER.index(f["category"]) if f["category"] else 99,
                                  f["worse"] if f["worse"] is not None else 0))
        results[seg] = feats
    warnings = []
    overall = results[OVERALL]
    total = {c: sum(f["counts"][c] for f in overall) for c in CATEGORIES}
    n_total = sum(total.values())
    reverse_modes = [f["feature"] for f in overall if f["category"] == "R"]
    # Reversed codes turn true A, O and M answers into R and leave I alone, so R outnumbering A + O + M, a large
    # R share, or R as the mode of most features all point at the code order (thresholds: references/sources.md).
    if n_total and total["R"] and (len(reverse_modes) > len(overall) / 2 or total["R"] / n_total > R_WARN_SHARE
                                   or total["R"] > total["A"] + total["O"] + total["M"]):
        warnings.append(f"Reverse answers are {100 * total['R'] / n_total:.0f}% overall (A + O + M "
                        f"{100 * (total['A'] + total['O'] + total['M']) / n_total:.0f}%), the mode for "
                        f"{len(reverse_modes)} of {len(overall)} features. "
                        + ("Check the codebook first: if 1 meant 'I dislike it', rerun with --code-order "
                           + ("like-first" if args.code_order == "dislike-first" else "dislike-first") + ". "
                           if stats.get("numeric") else
                           "Check how the answers were coded upstream (a reversed scale before export). ")
                        + "Also check that the functional and dysfunctional columns are not swapped. If the codes and "
                        "the question direction are right, the reverse answers are a finding: some respondents do not "
                        "want these features.")
    if n_total and total["Q"] / n_total > Q_WARN_SHARE:
        warnings.append(f"Questionable answers are {100 * total['Q'] / n_total:.0f}% overall (the same extreme answer "
                        "to both questions): the pairs may be unclear or respondents inattentive. Check the wording "
                        "and pilot it.")
    chart = None
    if args.chart:
        write_chart(args.chart, overall, args.overwrite)
        chart = args.chart
    return {
        "tool": "kano-analysis", "version": VERSION,
        "input": {"file": args.input or args.counts, "source": stats.get("source"),
                  "respondents": stats.get("respondents"), "rows": stats.get("rows"),
                  "numeric_answers": stats.get("numeric"),
                  "code_order": args.code_order if stats.get("numeric") else None,
                  "segment_col": args.segment_col, "notes": notes},
        "settings": {"confidence": args.confidence, "small_base": args.small_base, "fong_z": FONG_Z,
                     "tie_order": "".join(TIE_ORDER)},
        "overall": overall,
        "segments": {seg: results[seg] for seg in segments if seg is not OVERALL},
        "warnings": warnings, "chart": chart,
    }


# ------------------------------------------------------------------------------------------------ chart

def write_chart(path, features, overwrite=False):
    """Better (up) against |Worse| (across), corners as Berger et al. (1993) Fig. 17."""
    size, pad = 480, 60
    plot = size - 2 * pad

    def xy(better, worse):
        return pad + abs(worse) * plot, size - pad - better * plot

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" font-family="sans-serif" '
             'font-size="11">', f'<rect width="{size}" height="{size}" fill="white"/>',
             f'<rect x="{pad}" y="{pad}" width="{plot}" height="{plot}" fill="none" stroke="#888"/>',
             f'<line x1="{pad + plot / 2}" y1="{pad}" x2="{pad + plot / 2}" y2="{pad + plot}" stroke="#ccc"/>',
             f'<line x1="{pad}" y1="{pad + plot / 2}" x2="{pad + plot}" y2="{pad + plot / 2}" stroke="#ccc"/>',
             f'<text x="{pad + 4}" y="{pad + 14}" fill="#555">Attractive</text>',
             f'<text x="{pad + plot - 4}" y="{pad + 14}" text-anchor="end" fill="#555">One-dimensional</text>',
             f'<text x="{pad + plot - 4}" y="{pad + plot - 6}" text-anchor="end" fill="#555">Must-be</text>',
             f'<text x="{pad + 4}" y="{pad + plot - 6}" fill="#555">Indifferent</text>',
             f'<text x="{size / 2}" y="{size - 20}" text-anchor="middle">|Worse| (dissatisfaction if absent)</text>',
             f'<text x="16" y="{size / 2}" text-anchor="middle" transform="rotate(-90 16 {size / 2})">Better '
             '(satisfaction if present)</text>']
    for tick in (0, 0.5, 1):
        parts.append(f'<text x="{pad + tick * plot}" y="{pad + plot + 14}" text-anchor="middle">{tick:g}</text>')
        parts.append(f'<text x="{pad - 6}" y="{pad + (1 - tick) * plot + 4}" text-anchor="end">{tick:g}</text>')
    for f in features:
        if f["better"] is None:
            continue
        x, y = xy(f["better"], f["worse"])
        label = f["feature"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#2b6cb0"/>')
        if x > pad + plot * 0.6:  # right-hand points: label to the left so it stays on the canvas
            parts.append(f'<text x="{x - 6:.1f}" y="{y - 6:.1f}" text-anchor="end">{label}</text>')
        else:
            parts.append(f'<text x="{x + 6:.1f}" y="{y - 6:.1f}">{label}</text>')
    parts.append("</svg>")
    try:
        with open(path, "w" if overwrite else "x", encoding="utf-8") as fh:
            fh.write("\n".join(parts) + "\n")
    except FileExistsError:
        raise InputError(f"{path} already exists; choose another name or pass --overwrite")
    except OSError as exc:
        raise InputError(f"cannot write the chart to {path}: {exc.strerror}")


# ------------------------------------------------------------------------------------------------ design

NEGATION = re.compile(r"\b(not|no|without|never|lacks?|unable|cannot|can't|doesn't|don't|isn't|wasn't|won't|"
                      r"didn't|aren't|weren't|couldn't|wouldn't|shouldn't|hasn't|haven't|hadn't|missing|"
                      r"unavailable|fails?|failed|disabled|poor|bad|slow)\b", re.I)
JOINED = re.compile(r"\b(?:and|or)\b|[&/]", re.I)  # "Sync & share", "Export AND print"; not "Q&A", "R&D"
ACRONYM_AMPERSAND = re.compile(r"\b[A-Z]&[A-Z]\b")


def negations(text):
    return NEGATION.findall(text.replace("\u2019", "'"))


def design(args):
    items = []
    if args.wording and (args.features or args.product):
        raise InputError("--wording checks your own pairs; drop --features and --product")
    if args.wording:
        headers, rows = read_table(args.wording, args.delimiter, 0, [])
        lower = {h.lower(): h for h in headers}
        for need in ("feature", "functional", "dysfunctional"):
            if need not in lower:
                raise InputError(f"{args.wording} needs columns feature,functional,dysfunctional")
        for r in rows:
            items.append((r[lower["feature"]].strip(), r[lower["functional"]].strip(),
                          r[lower["dysfunctional"]].strip()))
    else:
        if not args.features:
            raise InputError("design needs --features 'A;B;C' or --wording FILE")
        product = args.product or "the product"
        for feat in [f.strip() for f in args.features.split(";") if f.strip()]:
            # Lower-case the first letter mid-sentence unless it looks like an acronym ("API", "SSO").
            phrase = feat if len(feat) > 1 and feat[1].isupper() else feat[:1].lower() + feat[1:]
            items.append((feat, f"If {product} had {phrase}, how would you feel?",
                          f"If {product} did not have {phrase}, how would you feel?"))
    if len(items) < 1:
        raise InputError("no features given")
    names = [feat.casefold() for feat, _, _ in items]
    if "" in names:
        raise InputError("a row has no feature name")
    repeated = sorted({feat for feat, _, _ in items if names.count(feat.casefold()) > 1})
    if repeated:
        raise InputError("these features are listed more than once: " + ", ".join(repeated))
    checks = []
    for feat, fq, dq in items:
        issues = []
        if not fq or not dq:
            issues.append("both questions are needed")
        if dq and not negations(dq):
            issues.append("the dysfunctional question has no negation word (not, without, no ...): if it states the "
                          "absence or a worse level of the feature (\"arrives next week\"), keep it and say why; "
                          "otherwise reword it")
        if dq and len(negations(dq)) > 1:
            issues.append("the dysfunctional question has a double negative: say plainly what is missing")
        if fq and negations(fq):
            issues.append("the functional question contains a negation: respondents may read it as the absence")
        if JOINED.search(ACRONYM_AMPERSAND.sub("", feat)):
            issues.append("the feature joins two things: ask about one at a time")
        if fq and dq and fq.strip().lower() == dq.strip().lower():
            issues.append("the two questions are identical")
        if len(fq) > 140 or len(dq) > 140:
            issues.append("long question: keep each to one short sentence")
        checks.append({"feature": feat, "functional": fq, "dysfunctional": dq, "issues": issues})
    survey_issues = []
    if len(items) > 20:
        survey_issues.append(f"{len(items)} features: each needs two to three answers, so long Kano surveys tire "
                             "respondents; consider fewer or split versions")
    return {"tool": "kano-analysis", "mode": "design", "answers": BERGER_ENGLISH, "survey_issues": survey_issues,
            "importance_question": "How important is this to you: <feature>? (1 Not at all important ... "
                                   "9 Extremely important)" if args.importance else None,
            "items": checks}


# ------------------------------------------------------------------------------------------------ rendering

def md(text):
    """A table cell: a pipe in a feature name would split the row."""
    return str(text).replace("|", "\\|")


def f2(x):
    return "-" if x is None else f"{x + 0.0:.2f}".replace("-0.00", "0.00")


def render(res):
    if res.get("mode") == "design":
        out = ["# Kano questionnaire", "",
               "Answers for every question, in this order and wording (Berger et al. 1993), not numbered on screen:",
               ""] + [f"- {a}" for a in res["answers"]] + [""]
        for i, it in enumerate(res["items"], 1):
            out += [f"## {i}. {it['feature']}", "", f"- Functional: {it['functional']}",
                    f"- Dysfunctional: {it['dysfunctional']}"]
            if res["importance_question"]:
                out.append(f"- Importance: {res['importance_question'].replace('<feature>', it['feature'])}")
            for issue in it["issues"]:
                out.append(f"- CHECK: {issue}")
            out.append("")
        out += [f"CHECK: {x}" for x in res["survey_issues"]]
        return "\n".join(out)
    inp = res["input"]
    level = f"{100 * res['settings']['confidence']:g}%"
    out = [f"# Kano analysis: {inp['file']}", "",
           f"Read from {inp['source']}" + (f", {inp['respondents']} respondents" if inp["respondents"] else "")
           + (f"; numeric answers coded {inp['code_order']} (1 = "
              f"{'like' if inp['code_order'] == 'like-first' else 'dislike'})." if inp["code_order"] else ".")]
    out += [f"- {n}" for n in inp["notes"]]
    out += ["", "Category = most frequent answer class (ties M > O > A > I > R > Q). Clear = Fong's test passes "
                "(z = 1.65, two-sided 90%). "
                "n = all answers (base = A + O + M + I). A-Q are percentages of n. Better = (A + O)/base; "
                f"Worse = -(O + M)/base; intervals are {level} Wilson on the base."]
    tables = [("All respondents", res["overall"])]
    tables += [(f"{inp['segment_col']} = {seg}", feats) for seg, feats in res["segments"].items()]
    for title, feats in tables:
        out += ["", f"## {title}", ""]
        has_imp = any(f["importance"] for f in feats)
        head = ("| Feature | n (base) | Category | Clear? | A% | O% | M% | I% | R% | Q% | Better | Worse |"
                + (" Importance |" if has_imp else ""))
        out += [head, "|---" * (head.count("|") - 1) + "|"]
        for f in feats:
            if f["category"] is None:
                out.append(f"| {md(f['feature'])} | 0 | - | - |" + " - |" * (8 + (1 if has_imp else 0)))
                continue
            sh = f["shares"]
            clear = "yes" if f["fong"]["significant"] else f"no ({f['category']} vs {'/'.join(f['runners_up'])})"
            others = [c for c in f["tied_with"] if c != f["category"]]
            cat = NAMES[f["category"]] + (f" (tie with {', '.join(others)})" if others else "")
            row = (f"| {md(f['feature'])} | {f['n']} ({f['base_aomi']}) | {cat} | {clear} | "
                   + " | ".join(f"{100 * sh[c]:.0f}%" for c in CATEGORIES)
                   + f" | {f2(f['better'])}" + (f" ({f2(f['better_ci'][0])}-{f2(f['better_ci'][1])})" if f["better_ci"] else "")
                   + f" | {f2(f['worse'])}" + (f" ({f2(f['worse_ci'][0])} to {f2(f['worse_ci'][1])})" if f["worse_ci"] else "")
                   + " |")
            if has_imp:
                row += f" {f2(f['importance']['mean']) if f['importance'] else '-'} |"
            out.append(row)
        flagged = [(f["feature"], n) for f in feats for n in f["notes"]]
        if flagged:
            out += [""] + [f"- {name}: {note}" for name, note in flagged]
    if res["warnings"]:
        out += ["", "## Warnings", ""] + [f"- {w}" for w in res["warnings"]]
    if res["chart"]:
        out += ["", f"Chart: {res['chart']}"]
    return "\n".join(out)


def build_parser():
    p = argparse.ArgumentParser(prog="kano_analysis.py", description="Kano survey design and analysis.")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="classify answers and report categories, Fong's test and Better/Worse",
                       epilog="Example: python3 scripts/kano_analysis.py analyze answers.csv --segment-col plan")
    a.add_argument("input", nargs="?", help="CSV of answers, one row per respondent (or per feature with --long)")
    a.add_argument("--counts", metavar="FILE", help="CSV of category counts: feature,A,O,M,I,R,Q")
    a.add_argument("--pair", action="append", metavar="FEATURE=FCOL,DCOL[,ICOL]", help="columns of one feature")
    a.add_argument("--question", help="QuestionPunk export with several Kano questions: which one (e.g. Q3)")
    a.add_argument("--qp-answer-col", metavar="COL", help="column holding QuestionPunk Kano answer text "
                   "('Feature: X / Y' lines, as responses_read returns)")
    a.add_argument("--long", action="store_true", help="one row per respondent x feature")
    a.add_argument("--feature-col")
    a.add_argument("--functional-col")
    a.add_argument("--dysfunctional-col")
    a.add_argument("--importance-col")
    a.add_argument("--respondent-col", help="with --long: respondent ID column (counts respondents, one row per "
                   "respondent and feature)")
    a.add_argument("--code-order", choices=["like-first", "dislike-first"], default="like-first",
                   help="numeric codes: 1 = like (default, Berger's order) or 1 = dislike")
    a.add_argument("--segment-col", help="report each segment too")
    a.add_argument("--small-base", type=int, default=SMALL_N, help=f"flag features with fewer answers (default {SMALL_N})")
    a.add_argument("--confidence", type=float, default=0.95, help="interval confidence, 0-1 or 0-100 "
                   "(default 0.95)")
    a.add_argument("--chart", metavar="SVG", help="write a Better vs |Worse| quadrant chart")
    a.add_argument("--overwrite", action="store_true", help="allow --chart to replace an existing file (never "
                   "the input)")
    a.add_argument("--allow-unreadable", action="store_true", help="go on when over 5%% of answers are unreadable")
    a.add_argument("--delimiter", help="comma, semicolon, tab, pipe or one character (default: sniffed)")
    a.add_argument("--skip-rows", type=int, help="rows under the header to skip (Qualtrics is detected)")
    a.add_argument("--json", action="store_true", help="machine-readable output, full precision")
    d = sub.add_parser("design", help="write the functional/dysfunctional pairs and check wording")
    d.add_argument("--features", help="features separated by ;")
    d.add_argument("--product", help="what the features belong to, e.g. 'the app' (default 'the product')")
    d.add_argument("--wording", metavar="FILE", help="CSV feature,functional,dysfunctional to check")
    d.add_argument("--importance", action="store_true", help="add Berger's 1-9 self-stated importance question")
    d.add_argument("--delimiter", help=argparse.SUPPRESS)
    d.add_argument("--json", action="store_true")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = design(args) if args.command == "design" else analyse(args)
    except InputError as exc:
        print(f"kano-analysis: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
