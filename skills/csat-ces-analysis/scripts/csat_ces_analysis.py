#!/usr/bin/env python3
"""CSAT and CES analysis: the share of satisfied (or low-effort) answers with a Wilson interval, the mean with a
t interval, comparisons between segments, periods, agents or channels, a test against a target, and comments
split by satisfied, neutral and dissatisfied.

Standard library only, Python 3.9+. No network, no randomness. Formulas and thresholds: references/sources.md.

Usage:
  python3 scripts/csat_ces_analysis.py ratings.csv --scale 1-5
  python3 scripts/csat_ces_analysis.py ratings.csv --metric ces --segment-col channel --pairwise --adjust holm
  python3 scripts/csat_ces_analysis.py ratings.csv --scale 1-5 --period-col month --compare-periods 2026-09 2026-10
  python3 scripts/csat_ces_analysis.py --counts 4,6,10,40,40 --target 80 --tail above
  python3 scripts/csat_ces_analysis.py ratings.csv --scale 1-5 --comment-col comment --comments-out work/comments.csv --json

Metrics (--metric):
  csat  satisfaction rating, higher is better. Scale from --scale, --labels or the text labels (never guessed
        from the numbers seen); "satisfied" = top-2 box (4-5 on 1-5).
  ces   Customer Effort Score, 7-point agree or ease scale ("made it easy to handle my issue"), higher is
        better. "Easy" = 5-7, "difficult" = 1-3.
  ces5  original CES (Dixon, Freeman and Toman 2010): "How much effort did you personally have to put forth
        to handle your request?", 1 = very low effort to 5 = very high effort, LOWER is better. "Low effort"
        = 1-2, "high effort" = 4-5.

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

# ----------------------------------------------------------------------------------------------- conventions

METRICS = {
    "csat": {
        "name": "CSAT",
        "default_scale": None,  # inferred from the data (1-5 when every answer is 1 to 5)
        "higher_is_better": True,
        "positive": "satisfied",
        "negative": "dissatisfied",
    },
    "ces": {
        "name": "CES (7-point, higher = easier)",
        "default_scale": (1, 7),
        "higher_is_better": True,
        "positive": "easy",
        "negative": "difficult",
    },
    "ces5": {
        "name": "CES 1.0 (1 = very low effort, 5 = very high effort)",
        "default_scale": (1, 5),
        "higher_is_better": False,
        "positive": "low effort",
        "negative": "high effort",
    },
}
DEFAULT_MIN_BASE = 100  # Pew Research Center subgroup reporting rule; see references/sources.md
MIN_N_FOR_VERDICT = 5  # convention of this skill: below 5 answers on a side, no verdict is printed
NON_READ_STOP_SHARE = 0.05  # stop when more than 5% of non-blank answers cannot be read as scale points
COCHRAN_MIN_EXPECTED = 5  # auto test: Fisher exact when any expected 2x2 count is below 5 (Cochran 1954)

def _labels(*points):
    """Build a label map from (point, label, synonym, ...) tuples."""
    return {label: point for point, *names in points for label in names}


# Each preset is one questionnaire format: its full answer scale and every label on it (synonyms share a point).
# A preset is used only when the answer scale is known (--scale, the metric's fixed scale) and matches it, or
# when it is the only format that fits the text answers; see resolve_scale_and_labels.
_DIS = ("very dissatisfied", "very unsatisfied")
_NEU_SAT = ("neither satisfied nor dissatisfied", "neither", "neutral")
_NEU_AGREE = ("neither agree nor disagree", "neutral")
_NEU_EASE = ("neither easy nor difficult", "neutral")
LABEL_PRESETS = {
    "good-bad": {"scale": (1, 2), "map": _labels((1, "bad"), (2, "good"))},
    "satisfied5": {"scale": (1, 5), "map": _labels(
        (1,) + _DIS, (2, "dissatisfied", "unsatisfied"), (3,) + _NEU_SAT, (4, "satisfied"),
        (5, "very satisfied"))},
    "satisfied5-somewhat": {"scale": (1, 5), "map": _labels(
        (1,) + _DIS, (2, "somewhat dissatisfied", "somewhat unsatisfied"), (3,) + _NEU_SAT,
        (4, "somewhat satisfied"), (5, "very satisfied"))},
    "satisfied7": {"scale": (1, 7), "map": _labels(
        (1,) + _DIS, (2, "dissatisfied", "unsatisfied"), (3, "somewhat dissatisfied", "somewhat unsatisfied"),
        (4,) + _NEU_SAT, (5, "somewhat satisfied"), (6, "satisfied"), (7, "very satisfied"))},
    "agree5": {"scale": (1, 5), "map": _labels(
        (1, "strongly disagree"), (2, "disagree"), (3,) + _NEU_AGREE, (4, "agree"), (5, "strongly agree"))},
    "agree5-somewhat": {"scale": (1, 5), "map": _labels(
        (1, "strongly disagree"), (2, "somewhat disagree"), (3,) + _NEU_AGREE, (4, "somewhat agree"),
        (5, "strongly agree"))},
    "agree7": {"scale": (1, 7), "map": _labels(
        (1, "strongly disagree"), (2, "disagree"), (3, "somewhat disagree"), (4,) + _NEU_AGREE,
        (5, "somewhat agree"), (6, "agree"), (7, "strongly agree"))},
    "ease5": {"scale": (1, 5), "map": _labels(
        (1, "very difficult"), (2, "difficult"), (3,) + _NEU_EASE, (4, "easy"), (5, "very easy"))},
    "ease7": {"scale": (1, 7), "map": _labels(
        (1, "very difficult"), (2, "difficult"), (3, "somewhat difficult"), (4,) + _NEU_EASE,
        (5, "somewhat easy"), (6, "easy"), (7, "very easy"))},
    "effort5": {"scale": (1, 5), "map": _labels(
        (1, "very low effort"), (2, "low effort"), (3, "moderate effort", "neither high nor low effort"),
        (4, "high effort"), (5, "very high effort"))},
}
METRIC_PRESETS = {
    "csat": ("good-bad", "satisfied5", "satisfied5-somewhat", "satisfied7"),
    "ces": ("agree7", "ease7", "agree5", "agree5-somewhat", "ease5"),
    "ces5": ("effort5",),
}
PRESET_HINTS = {name: "Those are agree or ease labels: for the CES 'made it easy' item use --metric ces."
                for name in METRIC_PRESETS["ces"]}
PRESET_HINTS.update({name: "Those are satisfaction labels: use --metric csat." for name in METRIC_PRESETS["csat"]})
PRESET_HINTS["effort5"] = ("Those are the CES 1.0 effort labels (1 = very low effort, lower is better): use "
                           "--metric ces5.")
# "5 - Very satisfied", "5 = Very satisfied", "5. Very", "(5) Very", "5: Very", "5 Very": a number, then a
# separator or a space, then a label. "2hrs" or "1st" are not read as points.
# An --id-col named like this holds ticket or case ids, which cannot show repeat customers.
TICKET_ID_RE = re.compile(r"ticket|case|conversation|chat|interaction|order|request|incident|response|submission",
                          re.I)
LABELLED_RE = re.compile(r"^\s*(?:\(\s*(-?\d{1,3})\s*\)\s*|(-?\d{1,3})\s*(?:[-–—:=.)]\s*|\s+))([^\W\d_].*)$")
# Zendesk exports binary CSAT as "Good, I'm satisfied" / "Bad, I'm unsatisfied".
GOOD_BAD_RE = re.compile(r"^\s*(good|bad)\b", re.I)
NON_ANSWER_RE = re.compile(
    r"^(n/?a|na|none|-+|\.|\?|don'?t know|do not know|dk|not applicable|prefer not to (say|answer)|refused|"
    r"skipped|no answer|no opinion)$",
    re.I,
)
# Zendesk rating states that are not ratings: "Offered" = survey sent, not answered; "Unoffered" = not sent.
OFFERED_RE = re.compile(r"^offered$", re.I)
NOT_OFFERED_RE = re.compile(r"^(unoffered|not offered)$", re.I)
# Whole-word stems only, so "services", "release" or "please" are not taken for the rating column.
SCORE_NAME_RE = re.compile(r"(?<![a-z])(csat|ces\d?|effort|ease|easy|ratings?|scores?)(?![a-z])|satisf", re.I)
DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|", "\\t": "\t"}
DELIMITER_NAMES = {",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe"}
PERIOD_PATTERNS = (
    (re.compile(r"^(\d{4})-(\d{2})-(\d{2})$"), lambda m: (int(m[1]), int(m[2]), int(m[3]))),
    (re.compile(r"^(\d{4})-(\d{2})$"), lambda m: (int(m[1]), int(m[2]), 0)),
    (re.compile(r"^(\d{4})[ -]?Q([1-4])$", re.I), lambda m: (int(m[1]), 3 * int(m[2]) - 2, 0)),
    (re.compile(r"^Q([1-4])[ -]?(\d{4})$", re.I), lambda m: (int(m[2]), 3 * int(m[1]) - 2, 0)),
    (re.compile(r"^(\d{4})$"), lambda m: (int(m[1]), 0, 0)),
)


class InputError(Exception):
    """Bad input or a calculation the script refuses to do (exit code 2)."""


# ------------------------------------------------------------------------------------------------ statistics

def z_for(confidence):
    return NormalDist().inv_cdf(1 - (1 - confidence) / 2)


def wilson(x, n, z):
    """Wilson (1927) score interval for x successes out of n, no continuity correction."""
    if n == 0:
        return None, None
    p = x / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    low, high = max(0.0, centre - half), min(1.0, centre + half)
    if x == 0:
        low = 0.0
    if x == n:
        high = 1.0
    return low, high


def newcombe(x1, n1, x2, n2, z):
    """Newcombe (1998) method 10: hybrid score interval for p1 - p2 from the two Wilson intervals."""
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = wilson(x1, n1, z)
    l2, u2 = wilson(x2, n2, z)
    d = p1 - p2
    return d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def two_proportion_z(x1, n1, x2, n2):
    """Pooled two-proportion z-test (equal to the Pearson chi-square test without continuity correction)."""
    pooled = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return None, 1.0
    z = (x1 / n1 - x2 / n2) / se
    return z, normal_two_sided_p(z)


def normal_upper_p(z):
    """P(Z >= z) via erfc, which keeps precision far in the tail (1 - cdf rounds to 0 beyond |z| = 8.3)."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def normal_two_sided_p(z):
    return min(1.0, math.erfc(abs(z) / math.sqrt(2)))


def _log_choose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_exact(x1, n1, x2, n2):
    """Two-sided Fisher exact test on [[x1, n1-x1], [x2, n2-x2]]: sum of the probabilities of every table with
    the same margins that is no more likely than the observed one (relative tolerance 1e-7, as R's fisher.test)."""
    successes, total = x1 + x2, n1 + n2
    low, high = max(0, successes - n2), min(successes, n1)
    log_denominator = _log_choose(total, successes)

    def prob(a):
        return math.exp(_log_choose(n1, a) + _log_choose(n2, successes - a) - log_denominator)

    observed = prob(x1)
    p_value = sum(prob(a) for a in range(low, high + 1) if prob(a) <= observed * (1 + 1e-7))
    return min(1.0, p_value)


def _beta_cf(a, b, x):
    tiny = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1.0)
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 500):
        for numerator in (
            m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m)),
            -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1)),
        ):
            d = 1.0 + numerator * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + numerator / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1.0) < 1e-15:
            break
    return h


def regularized_beta(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    log_front = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(log_front) * _beta_cf(a, b, x) / a
    return 1.0 - math.exp(log_front) * _beta_cf(b, a, 1 - x) / b


def t_two_sided_p(t_stat, df):
    return regularized_beta(df / 2.0, 0.5, df / (df + t_stat * t_stat))


def t_critical(confidence, df):
    low, high = 0.0, 1e6
    for _ in range(200):
        mid = (low + high) / 2
        if t_two_sided_p(mid, df) > 1 - confidence:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def binomial_tail(x, n, p0, upper):
    """P(X >= x) when upper, else P(X <= x), for X ~ Binomial(n, p0)."""
    ks = range(x, n + 1) if upper else range(0, x + 1)
    if p0 <= 0:
        return 1.0 if (not upper or x == 0) else 0.0
    if p0 >= 1:
        return 1.0 if (upper or x == n) else 0.0
    return min(1.0, sum(math.exp(_log_choose(n, k) + k * math.log(p0) + (n - k) * math.log(1 - p0)) for k in ks))


def mean_sd(values):
    """Mean and sample SD with exact summation (math.fsum), so the result does not depend on the Python
    version's float sum. Identical values give an SD of exactly 0."""
    n = len(values)
    if n == 0:
        return None, None
    mean = math.fsum(values) / n
    if n < 2:
        return mean, None
    if max(values) == min(values):
        return mean, 0.0
    return mean, math.sqrt(math.fsum((v - mean) ** 2 for v in values) / (n - 1))


# ------------------------------------------------------------------------------------------------ CSV reading

def decode(data, path):
    """Decode by byte-order mark (UTF-32, UTF-16, UTF-8), else as UTF-8. Undecodable bytes stop with exit 2."""
    for bom, codec, name in ((b"\xff\xfe\x00\x00", "utf-32", "UTF-32"), (b"\x00\x00\xfe\xff", "utf-32", "UTF-32"),
                             (b"\xef\xbb\xbf", "utf-8-sig", "UTF-8 with BOM"), (b"\xff\xfe", "utf-16", "UTF-16"),
                             (b"\xfe\xff", "utf-16", "UTF-16")):
        if data.startswith(bom):
            try:
                return data.decode(codec), name
            except UnicodeDecodeError as exc:
                raise InputError(f"{path} starts with a {name} byte-order mark but is not valid {name} (byte "
                                 f"{exc.start}); the file may be cut short. Re-export it as 'CSV UTF-8'")
    if data[:200].count(b"\x00") > 20:
        raise InputError(f"{path} looks like UTF-16 without a byte-order mark; re-export it as CSV UTF-8")
    try:
        return data.decode("utf-8"), "UTF-8"
    except UnicodeDecodeError as exc:
        raise InputError(
            f"{path} is not UTF-8 text (byte {exc.start}); re-export it as 'CSV UTF-8' (Excel) or UTF-8 CSV"
        )


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
        consistent = sum(1 for r in rows if len(r) == width)
        key = (width > 1, consistent, width)
        if best_key is None or key > best_key:
            best, best_key = delim, key
    return best


def read_table(path, delimiter=None, skip_rows=None, notes=None):
    """Read a CSV into (headers, rows as dicts). Handles BOMs, UTF-16, CRLF, comma/semicolon/tab/pipe, and
    Qualtrics's extra header rows. Stops on duplicate column names and on rows of the wrong width."""
    notes = notes if notes is not None else []
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except FileNotFoundError:
        raise InputError(f"file not found: {path}")
    except IsADirectoryError:
        raise InputError(f"{path} is a folder, not a CSV file")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}")
    text, encoding = decode(data, path)
    if encoding != "UTF-8":
        notes.append(f"Read as {encoding}.")
    # Excel's "sep=;" first line names the delimiter; it is not the header.
    directive = re.match(r"\A\s*sep=(.)[ \t]*\r?\n", text)
    if directive:
        text = text[directive.end():]
        delimiter = delimiter or directive.group(1)
        notes.append(f"Excel 'sep={directive.group(1)}' line read as the delimiter and skipped.")
    if delimiter:
        delim = DELIMITERS.get(delimiter.lower(), delimiter)
        if len(delim) != 1:
            raise InputError(f"--delimiter takes one character or comma, semicolon, tab, pipe; got {delimiter!r}")
    else:
        delim = sniff_delimiter(text)
        if delim != ",":
            notes.append(f"Delimiter detected: {DELIMITER_NAMES.get(delim, repr(delim))}.")
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
        raise InputError(
            f"{path} has more than one column named {', '.join(repr(h) for h in repeated)}. Rename them so each "
            "column is unique, then pass the one you mean."
        )
    body = table[1:]
    if skip_rows is not None and skip_rows < 0:
        raise InputError(f"--skip-rows must be 0 or more; got {skip_rows}")
    if skip_rows is None:
        if len(body) >= 2 and any(cell.strip().startswith('{"ImportId"') for cell in body[1]):
            skip_rows = 2
            notes.append("Qualtrics export detected: skipped the question-text and ImportId rows under the header.")
        else:
            skip_rows = 0
    elif skip_rows:
        notes.append(f"Skipped {skip_rows} row(s) under the header (--skip-rows).")
    body = body[skip_rows:]
    rows = []
    for index, row in enumerate(body, start=2 + skip_rows):
        if len(row) > len(headers) and not any(c.strip() for c in row[len(headers):]):
            row = row[: len(headers)]
        if len(row) != len(headers):
            hint = " If the file uses another delimiter, pass --delimiter." if len(headers) == 1 else ""
            raise InputError(
                f"{path} row {index} has {len(row)} cells but the header has {len(headers)}; a row may be cut or "
                f"shifted, so values would land in the wrong columns.{hint}"
            )
        rows.append(dict(zip(headers, row)))
    return headers, rows


def parse_scale(text, flag="--scale"):
    match = re.fullmatch(r"\s*(-?\d+)\s*-\s*(-?\d+)\s*", text or "")
    if not match or int(match.group(1)) >= int(match.group(2)):
        raise InputError(f"{flag} takes MIN-MAX from the questionnaire, such as 1-5 or 0-10; got {text!r}")
    return int(match.group(1)), int(match.group(2))


def parse_label_map(text):
    mapping = {}
    for part in text.split(","):
        label, sep, number = part.rpartition("=")
        if not sep or not label.strip():
            raise InputError(f"--labels takes LABEL=NUMBER pairs separated by commas; got {part!r}")
        try:
            mapping[norm_label(label)] = int(number.strip())
        except ValueError:
            raise InputError(f"--labels: {number.strip()!r} (for {label.strip()!r}) is not a whole number")
    return mapping


def norm_label(text):
    """Lower case with runs of whitespace collapsed, so "Strongly  agree" matches "strongly agree"."""
    return " ".join(text.split()).lower()


def as_number(text):
    """The number in a plain numeric answer ("4", "4.0", "4,0"), else None."""
    try:
        return float(text.replace(",", ".")) if re.fullmatch(r"-?\d+,\d+", text) else float(text)
    except ValueError:
        return None


def labelled_number(text):
    """(number, label) for answers like "5 - Very satisfied", else None."""
    match = LABELLED_RE.match(text)
    if not match:
        return None
    return int(match.group(1) or match.group(2)), match.group(3).strip()


def read_point(raw, labels):
    """Return (value, None) or (None, reason). Reasons: blank, non_answer, offered_not_rated, not_offered,
    non_numeric, non_integer."""
    text = (raw or "").strip()
    if not text:
        return None, "blank"
    if labels and norm_label(text) in labels:  # a label the map names ("None=1") is a point, not a non-answer
        return labels[norm_label(text)], None
    if NON_ANSWER_RE.match(text):
        return None, "non_answer"
    if OFFERED_RE.match(text):
        return None, "offered_not_rated"
    if NOT_OFFERED_RE.match(text):
        return None, "not_offered"
    value = as_number(text)
    if value is None:
        pair = labelled_number(text)
        if pair is None:
            if labels:
                good_bad = GOOD_BAD_RE.match(text)
                if good_bad and good_bad.group(1).lower() in labels:
                    return labels[good_bad.group(1).lower()], None
            return None, "non_numeric"
        value = float(pair[0])
    if math.isnan(value) or math.isinf(value):
        return None, "non_numeric"
    if value != int(value):
        return None, "non_integer"
    return int(value), None


def preset_value(name, text):
    preset = LABEL_PRESETS[name]["map"]
    if text in preset:
        return preset[text]
    if name == "good-bad":
        match = GOOD_BAD_RE.match(text)
        if match:
            return preset[match.group(1).lower()]
    return None


def text_answers(raw_values):
    """Count each distinct text answer (lower case) that is not blank, a non-answer, a number or a labelled number."""
    counts = {}
    for raw in raw_values:
        text = (raw or "").strip()
        if (not text or NON_ANSWER_RE.match(text) or OFFERED_RE.match(text) or NOT_OFFERED_RE.match(text)
                or as_number(text) is not None or labelled_number(text)):
            continue
        counts[norm_label(text)] = counts.get(norm_label(text), 0) + 1
    return counts


# A label that names an end of a rating scale: "Very satisfied", "Strongly agree", "Not at all likely",
# "Completely". "Not very ..." and the like are inner points of a 4-point scale, so they never count.
END_LABEL_RE = re.compile(r"\b(?:very|extremely|strongly|completely|totally|entirely|absolutely|highly|at all)\b",
                          re.I)
INNER_LABEL_RE = re.compile(
    r"\bnot\s+(?:very|extremely|strongly|completely|totally|entirely|absolutely|highly)\b", re.I)


def labelled_scale(raw_values):
    """Read the scale from labelled-number answers ("1 - Very dissatisfied" ... "5 - Very satisfied").
    Returns None when no answer is a labelled number; else (scale, source, None) when the lowest and the highest
    labelled codes both carry only end-point labels, or (None, None, reason) when they do not."""
    seen = {}
    for raw in raw_values:
        text = (raw or "").strip()
        pair = labelled_number(text)
        if pair and as_number(text) is None:
            seen.setdefault(pair[0], set()).add(pair[1])
    if not seen:
        return None
    low, high = min(seen), max(seen)

    def shown(point):
        return f"{point} = " + " / ".join(repr(label) for label in sorted(seen[point]))

    if low == high:
        return None, None, f"every labelled answer is {shown(low)}"
    inner = [p for p in (low, high)
             if not all(END_LABEL_RE.search(lab) and not INNER_LABEL_RE.search(lab) for lab in seen[p])]
    if inner:
        return None, None, ("the labelled answers run from " + shown(low) + " to " + shown(high) + ", and " +
                            " and ".join(shown(p) for p in inner) + " does not read as an end point (very, "
                            "extremely, strongly, completely, not at all), so an end of the scale may be missing")
    return (low, high), f"from the labelled answers: {shown(low)} and {shown(high)} read as the end points", None


def resolve_scale_and_labels(raw_values, declared, fixed, user_labels, allowed, hints):
    """Decide the answer scale and the text-label map. The scale never comes from the answers that happen to
    appear: a question where nobody chose an end point looks like a shorter scale. In order:
      1. --scale (declared), else the metric's fixed scale (fixed = (scale, source) or None);
      2. --labels: its lowest and highest points set the scale when 1 did not;
      3. a built-in preset (only those in `allowed`) that reads the text answers. With a known scale only presets
         of that scale count; with none, the preset must be the only fitting format, else stop and ask;
      4. labelled-number answers ("1 - Very dissatisfied") with no scale from 1-3: the lowest and highest
         labelled codes set the scale when both carry end-point labels (labelled_scale) and no plain number falls
         outside them;
      5. otherwise numeric answers with no scale stop with exit 2 and ask for --scale.
    `hints` maps a preset outside `allowed` to advice (for example, which --metric reads it).
    Returns (scale, scale_source, labels or None, label_source or None)."""
    scale, source = (declared, "given (--scale)") if declared else (fixed if fixed else (None, None))
    if user_labels:
        points = sorted(set(user_labels.values()))
        if scale is None:
            if len(points) < 2:
                raise InputError("--labels names one point only, so it cannot set the scale; add --scale MIN-MAX")
            scale, source = (points[0], points[-1]), "from the --labels map (its lowest and highest points)"
        elif points[0] < scale[0] or points[-1] > scale[1]:
            raise InputError(f"--labels uses points {points[0]} to {points[-1]}, outside the scale "
                             f"{scale[0]}-{scale[1]}; check --labels and --scale")
        return scale, source, user_labels, "given"
    texts = text_answers(raw_values)
    if texts:
        total = sum(texts.values())

        def unread(name):
            return sum(c for t, c in texts.items() if preset_value(name, t) is None)

        def fits_from(names):
            full = [n for n in names if unread(n) == 0]
            # A preset that reads all but a few stray answers (a typo, "test") still fits; the unread ones are
            # counted and the 5% stop rule applies to them.
            return full or [n for n in names if unread(n) < total and unread(n) <= NON_READ_STOP_SHARE * total]

        fits = fits_from(allowed)
        in_scale = [n for n in fits if scale is None or LABEL_PRESETS[n]["scale"] == scale]
        if not in_scale:
            if fits:
                raise InputError(
                    "the text answers fit " + describe_presets(fits) + f", not the {scale[0]}-{scale[1]} scale "
                    f"({source}). Pass --scale MIN-MAX from the questionnaire, or --labels LABEL=N,...")
            for name in fits_from([n for n in LABEL_PRESETS if n not in allowed]):
                if name in hints:
                    raise InputError(f"the text answers fit {describe_presets([name])}. {hints[name]}")
            return scale, source, None, None  # unknown labels: counted as unreadable, and the 5% rule applies
        observed = {n: tuple(sorted((t, preset_value(n, t)) for t in texts)) for n in in_scale}
        if len(set(observed.values())) > 1 or len({LABEL_PRESETS[n]["scale"] for n in in_scale}) > 1:
            raise InputError(
                "the text answers fit more than one answer scale: " + describe_presets(in_scale) + ". The answers "
                "alone cannot say which (nobody may have chosen some points). Pass --scale MIN-MAX from the "
                "questionnaire, or --labels LABEL=N,...")
        name = in_scale[0]
        if scale is None:
            scale, source = LABEL_PRESETS[name]["scale"], f"from the {name} labels"
        return scale, source, LABEL_PRESETS[name]["map"], name
    if scale is None:
        numbers = [v for v, reason in (read_point(r, None) for r in raw_values) if reason is None]
        seen = f"numbers from {min(numbers)} to {max(numbers)}" if numbers else "no readable numbers"
        found = labelled_scale(raw_values)
        why = ""
        if found:
            if found[0] and all(found[0][0] <= v <= found[0][1] for v in numbers):
                return found[0], found[1], None, None
            why = (f"; {found[2]}" if found[2] else
                   f"; some plain numbers fall outside the labelled codes {found[0][0]}-{found[0][1]}")
        raise InputError(
            f"the answers are {seen}{why}. The scale cannot be read from the answers: if nobody chose an end point "
            "the scale looks shorter than it was. Pass --scale MIN-MAX from the questionnaire (for example "
            "--scale 1-5), or --labels.")
    return scale, source, None, None


def describe_presets(names):
    parts = []
    for name in names:
        lo, hi = LABEL_PRESETS[name]["scale"]
        by_point = {}
        for label, point in LABEL_PRESETS[name]["map"].items():
            by_point.setdefault(point, label)
        parts.append(f"{name} ({lo}-{hi}: " + ", ".join(f"{p}={by_point[p]}" for p in sorted(by_point)) + ")")
    return "; ".join(parts)


def label_map_note(labels, label_source):
    by_point = {}
    for label, point in labels.items():
        by_point.setdefault(point, []).append(label)
    text = "; ".join(f"{p} = {' / '.join(by_point[p])}" for p in sorted(by_point))
    return (f"Text answers read with the {label_source} label map: {text}. Check it matches the questionnaire; "
            "pass --labels to override.")


def labelled_numbers_note(raw_values):
    """Show which labels came with which numbers ("5 - Very satisfied"), so a reversed or odd export is seen."""
    seen = {}
    for raw in raw_values:
        pair = labelled_number((raw or "").strip())
        if pair and as_number((raw or "").strip()) is None:
            seen.setdefault(pair[0], set()).add(pair[1])
    if not seen:
        return None
    return ("Numbers with labels read as their number: " +
            "; ".join(f"{p} = {' / '.join(sorted(seen[p])[:3])}" for p in sorted(seen)) + ".")


# ------------------------------------------------------------------------------------------------- analysis


def bands(metric_key, scale, args):
    """Return (positive_points, negative_points, rule text). Top-2/bottom-2 box on 5+ point scales, top/bottom
    1 box on 2-4 point scales, unless --positive / --negative override."""
    low, high = scale
    points = high - low + 1
    width = 2 if points >= 5 else 1
    if metric_key == "ces" and points == 7:
        # Top-3 / bottom-3 box on any 7-point coding (1-7, 0-6 ...), counted from the ends of the scale.
        positive, negative = list(range(high - 2, high + 1)), list(range(low, low + 3))
    elif metric_key == "ces5":
        positive, negative = [1, 2], [4, 5]
    else:
        positive = list(range(high - width + 1, high + 1))
        negative = list(range(low, low + width))
    if args.positive:
        positive = parse_points(args.positive, scale, "--positive")
    if args.negative:
        negative = parse_points(args.negative, scale, "--negative")
    if set(positive) & set(negative):
        raise InputError("--positive and --negative overlap; a point cannot be both")
    return positive, negative


def middle_label(scale, positive, negative):
    """What the points outside both boxes are called: "neutral" only when that is the scale's single midpoint."""
    middle = [p for p in range(scale[0], scale[1] + 1) if p not in positive and p not in negative]
    if len(middle) == 1 and (scale[0] + scale[1]) % 2 == 0 and middle[0] == (scale[0] + scale[1]) // 2:
        return middle, "neutral"
    return middle, "middle (neither box)"


def parse_points(text, scale, flag):
    out = []
    for part in text.split(","):
        match = re.fullmatch(r"\s*(-?\d+)\s*(?:-\s*(-?\d+)\s*)?", part)
        if not match:
            raise InputError(f"{flag} takes points or ranges such as 4-5 or 1,2; got {part.strip()!r}")
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) is not None else start
        if end < start:
            raise InputError(f"{flag} range {part.strip()!r} runs backwards; write it lowest first")
        out.extend(range(start, end + 1))
    if any(p < scale[0] or p > scale[1] for p in out):
        raise InputError(f"{flag} {text!r} has points outside the scale {scale[0]}-{scale[1]}")
    return sorted(set(out))


def summarize(label, values, positive, negative, scale, z, confidence, min_base):
    n = len(values)
    counts = {str(p): 0 for p in range(scale[0], scale[1] + 1)}
    for v in values:
        counts[str(v)] += 1
    x_pos = sum(1 for v in values if v in positive)
    x_neg = sum(1 for v in values if v in negative)
    out = {"label": label, "n": n, "distribution": counts, "positive": x_pos, "negative": x_neg,
           "neutral": n - x_pos - x_neg, "small_base": n < min_base, "notes": []}
    if n == 0:
        out["notes"].append("no valid answers")
        return out
    lo, hi = wilson(x_pos, n, z)
    nlo, nhi = wilson(x_neg, n, z)
    mean, sd = mean_sd(values)
    out.update({
        "pct_positive": 100 * x_pos / n, "positive_ci": [100 * lo, 100 * hi],
        "pct_negative": 100 * x_neg / n, "negative_ci": [100 * nlo, 100 * nhi],
        "pct_neutral": 100 * (n - x_pos - x_neg) / n,
        "mean": mean, "sd": sd,
    })
    if scale[1] - scale[0] == 1:
        out["mean"], out["sd"] = None, None  # a two-point (good/bad) scale has a share, not a meaningful mean
    elif sd is not None:
        if sd > 0:
            half = t_critical(confidence, n - 1) * sd / math.sqrt(n)
            # Clipped to the scale: a t interval can run past the end points on a small, skewed base.
            out["mean_ci"] = [max(scale[0], mean - half), min(scale[1], mean + half)]
        else:
            out["mean_ci"] = [mean, mean]
            out["notes"].append("every answer is the same: the mean's interval has zero width and says nothing "
                                "about precision")
    if n < MIN_N_FOR_VERDICT:
        out["notes"].append(f"fewer than {MIN_N_FOR_VERDICT} answers: show the counts, draw no conclusion")
    return out


def compare(kind, a, b, z, confidence, test, min_base):
    out = {"kind": kind, "a": a["label"], "b": b["label"], "n_a": a["n"], "n_b": b["n"]}
    if a["n"] == 0 or b["n"] == 0:
        out.update({"tested": False, "note": "one side has no valid answers"})
        return out
    x1, n1, x2, n2 = a["positive"], a["n"], b["positive"], b["n"]
    out["difference_pct"] = 100 * (x1 / n1 - x2 / n2)
    low, high = newcombe(x1, n1, x2, n2, z)
    out["difference_ci"] = [100 * low, 100 * high]
    out["small_base"] = n1 < min_base or n2 < min_base
    if a.get("sd") is not None and b.get("sd") is not None:
        se2 = a["sd"] ** 2 / n1 + b["sd"] ** 2 / n2
        out["mean_difference"] = a["mean"] - b["mean"]
        if se2 > 0 and min(n1, n2) >= MIN_N_FOR_VERDICT:
            df = se2 ** 2 / ((a["sd"] ** 2 / n1) ** 2 / (n1 - 1) + (b["sd"] ** 2 / n2) ** 2 / (n2 - 1))
            t_stat = out["mean_difference"] / math.sqrt(se2)
            half = t_critical(confidence, df) * math.sqrt(se2)
            out.update({"mean_t": t_stat, "mean_df": df, "mean_p_value": t_two_sided_p(t_stat, df),
                        "mean_difference_ci": [out["mean_difference"] - half, out["mean_difference"] + half]})
    if min(n1, n2) < MIN_N_FOR_VERDICT:
        out.update({"tested": False, "note": f"fewer than {MIN_N_FOR_VERDICT} answers on one side: no verdict"})
        return out
    total_pos, total = x1 + x2, n1 + n2
    expected = [n1 * total_pos / total, n1 * (total - total_pos) / total,
                n2 * total_pos / total, n2 * (total - total_pos) / total]
    use_fisher = test == "fisher" or (test == "auto" and min(expected) < COCHRAN_MIN_EXPECTED)
    if use_fisher:
        out.update({"test": "fisher exact", "p_value": fisher_exact(x1, n1, x2, n2)})
    else:
        stat, p_value = two_proportion_z(x1, n1, x2, n2)
        out.update({"test": "two-proportion z", "z": stat, "p_value": p_value})
    out["tested"] = True
    set_verdict(out, 1 - confidence)
    return out


def set_verdict(result, alpha):
    """significant / not significant. A small base is flagged, not turned into a power claim: power depends on
    the effect size, so a non-significant result says only that the interval includes no difference."""
    p_value = result.get("p_adjusted", result["p_value"])
    result["significant"] = p_value < alpha
    result["verdict"] = "significant" if result["significant"] else "not significant"


def adjust(comparisons, method, alpha):
    """Holm or Bonferroni within each family: the segment comparisons are one family, the period (trend)
    comparisons another. Each tested comparison records its family and the family size."""
    families = {}
    for c in comparisons:
        if c.get("tested"):
            families.setdefault("segment" if c["kind"] == "segment" else "period", []).append(c)
    for family, tested in families.items():
        m = len(tested)
        for c in tested:
            c["family"], c["family_size"] = family, m
        if method == "none":
            continue
        if method == "bonferroni":
            for c in tested:
                c["p_adjusted"] = min(1.0, c["p_value"] * m)
        else:  # Holm (1979) step-down
            running = 0.0
            for rank, c in enumerate(sorted(tested, key=lambda c: c["p_value"])):
                running = max(running, min(1.0, (m - rank) * c["p_value"]))
                c["p_adjusted"] = running
        for c in tested:
            c["adjustment"] = method
            set_verdict(c, alpha)


def target_test(group, target_pct, tail, confidence, min_base):
    """Score test of the positive share against a fixed target; exact binomial when n*p0 or n*(1-p0) is below
    5. The two-tailed score test agrees with the two-sided Wilson interval at the same level; see sources.md."""
    n, x = group["n"], group["positive"]
    p0 = target_pct / 100
    out = {"target_pct": target_pct, "tail": tail, "n": n, "pct_positive": group.get("pct_positive"),
           "difference_pct": None if n == 0 else 100 * x / n - target_pct, "small_base": n < min_base}
    if n == 0:
        out.update({"tested": False, "note": "no valid answers"})
        return out
    if not 0 < p0 < 1:
        out.update({"tested": False, "note": "a target of 0% or 100% cannot be tested; give a value between"})
        return out
    if n < MIN_N_FOR_VERDICT:
        out.update({"tested": False, "note": f"fewer than {MIN_N_FOR_VERDICT} answers: no verdict"})
        return out
    if n * p0 < 5 or n * (1 - p0) < 5:
        upper, lower = binomial_tail(x, n, p0, True), binomial_tail(x, n, p0, False)
        p_value = {"above": upper, "below": lower, "two": min(1.0, 2 * min(upper, lower))}[tail]
        out.update({"test": "exact binomial", "p_value": p_value})
    else:
        z = (x / n - p0) / math.sqrt(p0 * (1 - p0) / n)
        upper = normal_upper_p(z)
        p_value = {"above": upper, "below": normal_upper_p(-z), "two": normal_two_sided_p(z)}[tail]
        out.update({"test": "one-sample score z", "z": z, "p_value": p_value})
    out["tested"] = True
    set_verdict(out, 1 - confidence)
    return out


def tail_text(tail):
    return "two-tailed" if tail == "two" else f"one-tailed, {tail}"


def order_periods(labels, explicit):
    if explicit:
        order = [p.strip() for p in explicit.split(",")]
        repeated = sorted({p for p in order if order.count(p) > 1})
        if repeated:
            raise InputError("--period-order lists a period twice: " + ", ".join(repeated))
        missing = [p for p in labels if p not in order]
        if missing:
            raise InputError("--period-order is missing these periods: " + ", ".join(missing))
        return [p for p in order if p in labels]
    if len(labels) <= 1:
        return list(labels)
    keys = {}
    for label in labels:
        for pattern, key in PERIOD_PATTERNS:
            match = pattern.match(label)
            if match:
                keys[label] = key(match)
                break
    if len(keys) == len(labels):
        return sorted(labels, key=lambda p: keys[p])
    numbered = [re.fullmatch(r"(.*?)(\d+)", p) for p in labels]
    if all(numbered) and len({m.group(1) for m in numbered}) == 1:
        return sorted(labels, key=lambda p: int(re.fullmatch(r".*?(\d+)", p).group(1)))
    raise InputError(
        "cannot tell the time order of these periods: " + ", ".join(sorted(labels)) +
        ". Pass --period-order P1,P2,... from earliest to latest, or use labels such as 2026-09 or 2026-Q3."
    )


def same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.realpath(a) == os.path.realpath(b)


def detect_score_column(headers, taken):
    candidates = [h for h in headers if h not in taken and SCORE_NAME_RE.search(h)]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise InputError("could not find the rating column by name. Columns: " + ", ".join(headers) +
                         ". Pass --score-col NAME.")
    raise InputError("more than one column could be the rating: " + ", ".join(candidates) + ". Pass --score-col NAME.")


def load(args, notes):
    """Return list of records {value, segment, period, comment, id} and input metadata."""
    meta = {}
    if args.counts:
        if args.input:
            raise InputError("pass either a CSV file or --counts, not both")
        try:
            counts = [int(c) for c in args.counts.split(",")]
        except ValueError:
            raise InputError(f"--counts takes whole numbers separated by commas; got {args.counts!r}")
        if any(c < 0 for c in counts):
            raise InputError("--counts cannot be negative")
        if args.scale:
            scale = parse_scale(args.scale)
        else:
            # The number of counts is the number of scale points, so this is not a guess from the answers; only
            # the numbering is assumed (1 upwards, 0-10 for 11 points) and printed.
            default = METRICS[args.metric]["default_scale"]
            scale = default or {2: (1, 2), 3: (1, 3), 4: (1, 4), 5: (1, 5), 7: (1, 7), 10: (1, 10),
                                11: (0, 10)}.get(len(counts))
            if scale is None:
                raise InputError(f"{len(counts)} counts given; pass --scale MIN-MAX so each count has a scale point")
            if not default:
                notes.append(f"{len(counts)} counts read as points {scale[0]} to {scale[1]}; pass --scale if the "
                             "questionnaire numbered them differently.")
        if len(counts) != scale[1] - scale[0] + 1:
            raise InputError(
                f"--counts has {len(counts)} values but the scale {scale[0]}-{scale[1]} has "
                f"{scale[1] - scale[0] + 1} points; give one count per point, lowest point first"
            )
        records = [{"value": scale[0] + i} for i, c in enumerate(counts) for _ in range(c)]
        for flag in ("segment_col", "period_col", "comment_col", "id_col", "comments_out"):
            if getattr(args, flag):
                raise InputError(f"--{flag.replace('_', '-')} needs a CSV with one row per answer, not --counts")
        meta.update({"source": "counts", "scale": scale, "scale_source": "given" if args.scale else "from counts",
                     "rows_read": len(records), "excluded": {}})
        return records, meta
    if not args.input:
        raise InputError("give a CSV file of ratings or --counts")
    headers, rows = read_table(args.input, args.delimiter, args.skip_rows, notes)
    for flag in ("score_col", "segment_col", "period_col", "comment_col", "id_col"):
        col = getattr(args, flag)
        if col and col not in headers:
            raise InputError(f"--{flag.replace('_', '-')} {col!r} is not a column. Columns: " + ", ".join(headers))
    taken = {c for c in (args.segment_col, args.period_col, args.comment_col, args.id_col) if c}
    score_col = args.score_col or detect_score_column(headers, taken)
    meta.update({"source": args.input, "score_col": score_col,
                 "score_col_source": "given" if args.score_col else "auto-detected"})
    raw_values = [r[score_col] for r in rows]
    default = METRICS[args.metric]["default_scale"]
    fixed = (default, f"{METRICS[args.metric]['name']} scale; pass --scale for another") if default else None
    scale, scale_source, labels, label_source = resolve_scale_and_labels(
        raw_values, parse_scale(args.scale) if args.scale else None, fixed,
        parse_label_map(args.labels) if args.labels else None, METRIC_PRESETS[args.metric], PRESET_HINTS)
    if labels:
        meta["labels"] = {"source": label_source, "map": labels}
        if label_source != "given":
            notes.append(label_map_note(labels, label_source))
    labelled = labelled_numbers_note(raw_values)
    if labelled:
        notes.append(labelled)
    parsed = [read_point(raw, labels) for raw in raw_values]
    meta.update({"scale": scale, "scale_source": scale_source})
    excluded = {}
    records = []
    blank_periods = 0
    for row, (value, reason) in zip(rows, parsed):
        if reason is None and not scale[0] <= value <= scale[1]:
            reason = "out_of_range"
        if reason:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        record = {"value": value}
        if args.segment_col:
            record["segment"] = row[args.segment_col].strip() or "(blank)"
        if args.period_col:
            # A blank period stays in the overall and segment results but out of the trend.
            record["period"] = row[args.period_col].strip() or None
            blank_periods += record["period"] is None
        if args.comment_col:
            record["comment"] = row[args.comment_col].strip()
        if args.id_col:
            record["id"] = row[args.id_col].strip()
        records.append(record)
    if blank_periods:
        notes.append(f"{blank_periods} answer(s) have no period: kept in the overall and segment results, left "
                     "out of the period results.")
    meta["blank_period"] = blank_periods
    not_answers = ("blank", "non_answer", "offered_not_rated", "not_offered")
    non_blank = len(rows) - sum(excluded.get(k, 0) for k in not_answers)
    if excluded.get("offered_not_rated"):
        rated = len(rows) - sum(excluded.values())
        offered = rated + excluded["offered_not_rated"]
        meta["response_rate_offered"] = rated / offered if offered else None
        notes.append(f"Zendesk 'Offered' rows: {excluded['offered_not_rated']} surveys sent but not rated, so "
                     f"{rated} usable ratings of {offered} offered surveys ({100 * rated / offered:.1f}% response "
                     "rate; 'Unoffered' rows are left out of it).")
    unread = sum(excluded.get(k, 0) for k in ("non_numeric", "non_integer", "out_of_range"))
    if non_blank and unread / non_blank > NON_READ_STOP_SHARE and not args.allow_unreadable:
        raise InputError(
            f"{unread} of {non_blank} non-blank answers ({100 * unread / non_blank:.1f}%) could not be read as points "
            f"on the {scale[0]}-{scale[1]} scale ({', '.join(f'{k} {v}' for k, v in sorted(excluded.items()))}). "
            "That is more than 5%, so a whole answer category may be dropping out. Check --score-col, --scale and "
            "--labels; pass --allow-unreadable only if these rows really are unusable."
        )
    meta.update({"rows_read": len(rows), "excluded": excluded})
    return records, meta


def analyse(args):
    if args.confidence > 1:
        args.confidence /= 100
    if not 0.5 <= args.confidence < 1:
        raise InputError("--confidence must be between 0.5 and 1 (for example 0.95 or 95)")
    for flag in ("confidence", "target", "target_mean"):
        value = getattr(args, flag)
        if value is not None and not math.isfinite(value):
            raise InputError(f"--{flag.replace('_', '-')} must be a finite number; got {value}")
    if args.min_base < 1:
        raise InputError(f"--min-base must be 1 or more; got {args.min_base}")
    if args.tail == "one":
        raise InputError("--tail one is ambiguous: say --tail above or --tail below (for CES 1.0, lower is better)")
    if args.paired:
        raise InputError("--paired is not supported; see step 7 (Independence) in SKILL.md")
    notes, warnings = [], []
    if args.target is not None and 0 < args.target <= 1:
        notes.append(f"--target {args.target:g} read as a share: {100 * args.target:g}%.")
        args.target *= 100
    records, meta = load(args, notes)
    metric = METRICS[args.metric]
    scale = meta["scale"]
    positive, negative = bands(args.metric, scale, args)
    middle, middle_name = middle_label(scale, positive, negative)
    if args.metric == "ces5" and scale != (1, 5):
        raise InputError("--metric ces5 is the 1-5 effort scale; for another scale use --metric ces or csat")
    if args.metric == "ces" and scale[1] - scale[0] + 1 != 7:
        warnings.append("CES 2.0 is normally a 7-point scale; this one has "
                        f"{scale[1] - scale[0] + 1} points, so it will not compare with 7-point CES benchmarks.")
    z = z_for(args.confidence)
    alpha = 1 - args.confidence
    values = [r["value"] for r in records]
    overall = summarize("Overall", values, positive, negative, scale, z, args.confidence, args.min_base)
    result = {
        "tool": "csat-ces-analysis", "version": VERSION, "metric": args.metric, "metric_name": metric["name"],
        "input": {k: v for k, v in meta.items() if k != "scale"},
        "scale": {"min": scale[0], "max": scale[1], "source": meta["scale_source"],
                  "higher_is_better": metric["higher_is_better"]},
        "convention": {
            "positive_label": metric["positive"], "positive_points": positive,
            "negative_label": metric["negative"], "negative_points": negative,
            "middle_label": middle_name, "middle_points": middle,
            "headline": "mean (lower is better)" if args.metric == "ces5" else f"% {metric['positive']}",
            "interval": f"Wilson score {round(100 * args.confidence, 4):g}% (shares); t interval (means)",
            "difference_interval": "Newcombe (1998) hybrid score, method 10",
        },
        "confidence": args.confidence,
        "overall": overall,
    }
    result["input"]["rows_used"] = len(records)
    if not records:
        raise InputError("no valid answers to analyse after exclusions: " +
                         ", ".join(f"{k} {v}" for k, v in sorted(meta["excluded"].items())))
    points_used = {v for v in values}
    if len(points_used) == 1:
        warnings.append(f"Every answer is {values[0]}: there is no variation to compare or explain.")
    unused_ends = [p for p in scale if p not in points_used]
    if unused_ends:
        warnings.append(f"Nobody chose end point(s) {', '.join(map(str, unused_ends))} of the {scale[0]}-{scale[1]} "
                        f"scale ({meta['scale_source']}); confirm the scale against the questionnaire.")
    comparisons = []

    def group_values(key, value):
        return [r["value"] for r in records if r.get(key) == value]

    if args.segment_col:
        names = sorted({r["segment"] for r in records})
        result["segments"] = []
        for name in names:
            vals = group_values("segment", name)
            result["segments"].append(summarize(name, vals, positive, negative, scale, z, args.confidence,
                                                args.min_base))
        if len(names) == 1:
            warnings.append(f"Only one segment ({names[0]}) has answers; nothing to compare.")
        seg = {s["label"]: s for s in result["segments"]}
        pairs = []
        if args.compare:
            for name in args.compare:
                if name not in seg:
                    raise InputError(f"--compare: segment {name!r} not found. Segments: " + ", ".join(names))
            if args.compare[0] == args.compare[1]:
                raise InputError("--compare names the same segment twice")
            pairs = [tuple(args.compare)]
        elif args.pairwise:
            # Answers with no segment are summarised but not tested: they are not a segment anyone asked about.
            real = [n for n in names if n != "(blank)"]
            pairs = list(itertools.combinations(real, 2))
            if len(real) < len(names):
                notes.append("Answers with a blank segment are shown as '(blank)' and left out of --pairwise.")
        for a, b in pairs:
            comparisons.append(compare("segment", seg[a], seg[b], z, args.confidence, args.test, args.min_base))
    elif args.compare or args.pairwise:
        raise InputError("--compare and --pairwise need --segment-col")
    if args.period_col:
        found = sorted({r["period"] for r in records if r["period"] is not None})
        if args.compare_periods and not args.period_order:
            try:
                labels = order_periods(found, None)
            except InputError:
                labels = found  # one named pair needs no time order
        else:
            labels = order_periods(found, args.period_order)
        result["periods"] = []
        for name in labels:
            vals = group_values("period", name)
            result["periods"].append(summarize(name, vals, positive, negative, scale, z, args.confidence,
                                               args.min_base))
        per = {p["label"]: p for p in result["periods"]}
        if args.compare_periods:
            earlier, later = args.compare_periods
            for name in (earlier, later):
                if name not in per:
                    raise InputError(f"--compare-periods: period {name!r} not found. Periods: " + ", ".join(labels))
            pairs = [(later, earlier)]
            kind = "period"
        else:
            pairs = [(labels[i + 1], labels[i]) for i in range(len(labels) - 1)]
            kind = "trend"
        for a, b in pairs:
            comparisons.append(compare(kind, per[a], per[b], z, args.confidence, args.test, args.min_base))
        if args.segment_col:
            # Mix: did the segments' share of each period change, and did their satisfaction change?
            result["segment_by_period"] = []
            for p in labels:
                in_period = [r for r in records if r["period"] == p]
                for s in sorted({r["segment"] for r in records}):
                    vals = [r["value"] for r in in_period if r["segment"] == s]
                    result["segment_by_period"].append({
                        "period": p, "segment": s, "n": len(vals),
                        "pct_of_period": 100 * len(vals) / len(in_period) if in_period else None,
                        "pct_positive": 100 * sum(1 for v in vals if v in positive) / len(vals) if vals else None})
        if args.id_col:
            seen = {}
            for r in records:
                if r.get("id") and r["period"] is not None:
                    seen.setdefault(r["id"], set()).add(r["period"])
            shared = sum(1 for periods in seen.values() if len(periods) > 1)
            if shared:
                warnings.append(f"{shared} {args.id_col!r} value(s) answered in more than one period. The period "
                                "tests assume independent samples, so their p-values are approximate.")
    elif args.compare_periods:
        raise InputError("--compare-periods needs --period-col")
    if args.id_col:
        ids = [r["id"] for r in records if r.get("id")]
        repeats = len(ids) - len(set(ids))
        result["input"]["id_col"] = args.id_col
        result["input"]["repeat_answers"] = repeats
        if repeats:
            warnings.append(f"{repeats} answer(s) share a {args.id_col!r} value with an earlier answer. Tests treat "
                            "every answer as independent.")
        if TICKET_ID_RE.search(args.id_col):
            notes.append(f"--id-col {args.id_col!r} looks like a ticket or case id, not a customer id: distinct "
                         "values count tickets, and repeat customers cannot be seen. Pass a customer id column to "
                         "check independence.")
    adjust(comparisons, args.adjust, alpha)
    families = {}
    for c in comparisons:
        if c.get("tested"):
            families[c["family"]] = c["family_size"]
    if args.adjust == "none" and any(m > 1 for m in families.values()):
        warnings.append("Several tests were run without a multiple-comparison adjustment (" +
                        ", ".join(f"{m} {f}" for f, m in sorted(families.items())) + "); pass --adjust holm, or "
                        "report the number of tests.")
    if comparisons:
        result["comparisons"] = comparisons
    if args.target is not None:
        result["target"] = target_test(overall, args.target, args.tail or "two", args.confidence, args.min_base)
    if args.target_mean is not None:
        n, sd = overall["n"], overall.get("sd")
        tm = {"target_mean": args.target_mean, "tail": args.tail or "two", "n": n, "mean": overall.get("mean"),
              "small_base": overall["small_base"]}
        if overall.get("mean") is None:
            tm.update({"tested": False, "note": "a two-point (good/bad) scale has no mean; test the share with --target"})
        elif n < MIN_N_FOR_VERDICT:
            tm.update({"tested": False, "note": f"fewer than {MIN_N_FOR_VERDICT} answers: no verdict"})
        elif sd:
            t_stat = (overall["mean"] - args.target_mean) / (sd / math.sqrt(n))
            two = t_two_sided_p(t_stat, n - 1)
            upper = two / 2 if t_stat > 0 else 1 - two / 2
            tm.update({"t": t_stat, "df": n - 1, "tested": True,
                       "p_value": {"two": two, "above": upper, "below": 1 - upper}[tm["tail"]]})
            set_verdict(tm, alpha)
        else:
            tm.update({"tested": False, "note": "every answer is the same, so the t-test is undefined"})
        result["target_mean"] = tm
    small = [g["label"] for g in [overall] + result.get("segments", []) + result.get("periods", [])
             if g["n"] and g["small_base"]]
    if small:
        warnings.append(f"Small base (under {args.min_base} answers): {', '.join(small)}. Show their intervals; a "
                        "result that is not significant there says little, since the interval is wide.")
    if args.comment_col:
        result["comments"] = split_comments(records, positive, negative, metric, middle_name)
        if args.comments_out:
            if args.input and same_file(args.comments_out, args.input):
                raise InputError("--comments-out points at the input file; choose another path")
            write_comments(args.comments_out, records, positive, negative, metric, middle_name)
            result["comments"]["written_to"] = args.comments_out
    elif args.comments_out:
        raise InputError("--comments-out needs --comment-col")
    result["notes"] = notes
    result["warnings"] = warnings
    return result


def group_of(value, positive, negative, metric, middle_name):
    if value in positive:
        return metric["positive"]
    if value in negative:
        return metric["negative"]
    return middle_name


def split_comments(records, positive, negative, metric, middle_name):
    """Per group: answers, answers with a comment, and (with --id-col) distinct values of that column behind them
    (customers only when the column holds customer ids)."""
    out = {}
    for name in (metric["negative"], middle_name, metric["positive"]):
        members = [r for r in records if group_of(r["value"], positive, negative, metric, middle_name) == name]
        out[name] = {"answers": len(members), "with_comment": sum(1 for r in members if r.get("comment"))}
        if any("id" in r for r in records):
            out[name]["distinct_ids"] = len({r["id"] for r in members if r.get("id")})
    return out


def write_comments(path, records, positive, negative, metric, middle_name):
    rows = []
    order = {metric["negative"]: 0, middle_name: 1, metric["positive"]: 2}
    with_id = any("id" in r for r in records)
    for r in records:
        if r.get("comment"):
            row = {"group": group_of(r["value"], positive, negative, metric, middle_name), "score": r["value"],
                   "segment": r.get("segment", ""), "period": r.get("period") or "", "comment": r["comment"]}
            if with_id:
                row = {"id": r.get("id", ""), **row}
            rows.append(row)
    rows.sort(key=lambda r: order[r["group"]])
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as handle:
            if path.lower().endswith(".json"):
                json.dump(rows, handle, indent=2, ensure_ascii=False)
            else:
                fields = (["id"] if with_id else []) + ["group", "score", "segment", "period", "comment"]
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
    except OSError as exc:
        raise InputError(f"cannot write {path}: {exc.strerror or exc}")


# ------------------------------------------------------------------------------------------------ rendering

def pct(value):
    return "-" if value is None else f"{value:.1f}%"


def rng(pair, unit="%"):
    if not pair:
        return "-"
    return f"{pair[0]:.1f}{unit} to {pair[1]:.1f}{unit}" if unit else f"{pair[0]:.2f} to {pair[1]:.2f}"


def fmt_p(p_value):
    return "<0.0001" if p_value < 0.0001 else f"{p_value:.4f}"


def verdict_text(t):
    text = t["verdict"]
    if not t["significant"] and t.get("small_base"):
        text += " (small base: the interval is wide, so a real difference may have been missed)"
    return text


def group_line(g, metric, conv, mean_first):
    if not g["n"]:
        return f"{g['label']}: no valid answers"
    mean = "" if g.get("mean") is None else (
        f"mean {g['mean']:.2f}" + (f" ({rng(g['mean_ci'], '')})" if g.get("mean_ci") else ""))
    flag = " [small base]" if g["small_base"] else ""
    shares = (f"{metric['positive']} {pct(g['pct_positive'])} ({rng(g['positive_ci'])}); {conv['middle_label']} "
              f"{pct(g['pct_neutral'])}; {metric['negative']} {pct(g['pct_negative'])}")
    body = f"{mean}; {shares}" if mean_first and mean else shares + (f"; {mean}" if mean else "")
    notes = "".join(f" [{n}]" for n in g.get("notes", []))
    return f"{g['label']}: n = {g['n']}{flag}; {body}{notes}"


def render(result):
    metric = METRICS[result["metric"]]
    conv, scale, inp = result["convention"], result["scale"], result["input"]
    mean_first = result["metric"] == "ces5"
    level = f"{round(100 * result['confidence'], 4):g}%"
    lines = [f"{result['metric_name']}: {metric['positive']} = points {','.join(map(str, conv['positive_points']))}"
             f" on a {scale['min']}-{scale['max']} scale; {metric['negative']} = "
             f"{','.join(map(str, conv['negative_points']))}; {conv['middle_label']} = "
             f"{','.join(map(str, conv['middle_points'])) or 'none'}. Scale: {scale['source']}."
             + (" Headline: the mean (lower is better); the low-effort share is this skill's convention."
                if mean_first else "")]
    excluded = inp.get("excluded", {})
    lines.append(f"Data: {inp['source']}" + (f", column {inp['score_col']!r}" if inp.get("score_col") else "") +
                 f". Rows {inp['rows_read']}, used {inp['rows_used']}, excluded {sum(excluded.values())}" +
                 (f" ({', '.join(f'{k} {v}' for k, v in sorted(excluded.items()))})" if excluded else "") + ".")
    lines.append(f"Intervals: {level}; shares Wilson score, means t, differences Newcombe hybrid score.")
    lines.append("")
    o = result["overall"]
    lines.append(group_line(o, metric, conv, mean_first))
    if o["n"]:
        lines.append("  Distribution: " + "  ".join(f"{k}: {v}" for k, v in o["distribution"].items()))
    for key, title in (("segments", "By segment"), ("periods", "By period")):
        if result.get(key):
            lines += ["", title + ":"] + ["  " + group_line(g, metric, conv, mean_first) for g in result[key]]
    if result.get("segment_by_period"):
        lines += ["", f"Segment mix by period (n, % of the period's answers, % {metric['positive']}):"]
        for row in result["segment_by_period"]:
            lines.append(f"  {row['period']} / {row['segment']}: n = {row['n']}, {pct(row['pct_of_period'])} of "
                         f"period, {pct(row['pct_positive'])} {metric['positive']}")
    if result.get("comparisons"):
        lines += ["", f"Comparisons (difference in % {metric['positive']}, A minus B; p-values raw unless marked "
                      "adjusted):"]
        for c in result["comparisons"]:
            head = f"  {c['a']} vs {c['b']}: "
            if not c.get("difference_ci"):
                lines.append(head + c.get("note", "not tested"))
                continue
            text = head + f"{c['difference_pct']:+.1f} points ({rng(c['difference_ci'], ' pts')})"
            if c.get("tested"):
                p_text = f"p = {fmt_p(c['p_value'])}"
                if "p_adjusted" in c:
                    p_text += (f", {c['adjustment']}-adjusted p = {fmt_p(c['p_adjusted'])} over the "
                               f"{c['family_size']} {c['family']} test(s)")
                text += f", {c['test']}, {p_text}: {verdict_text(c)}"
            else:
                text += f": {c.get('note', 'not tested')}"
            if "mean_difference" in c:
                text += f". Mean {c['mean_difference']:+.2f}"
                if "mean_p_value" in c:
                    text += f" (Welch p = {fmt_p(c['mean_p_value'])}, raw, supporting detail)"
            lines.append(text)
    if result.get("target"):
        t = result["target"]
        if t.get("tested"):
            lines += ["", f"Against target {t['target_pct']:g}% ({tail_text(t['tail'])}, {t['test']}): "
                          f"{pct(t['pct_positive'])} vs {t['target_pct']:g}%, p = {fmt_p(t['p_value'])}"
                          f" -> {verdict_text(t)}"]
        else:
            lines += ["", f"Against target {t['target_pct']:g}%: {t.get('note')}"]
    if result.get("target_mean"):
        t = result["target_mean"]
        head = f"Mean against target {t['target_mean']:g} ({tail_text(t['tail'])} t): "
        if t.get("tested"):
            lines += ["", head + f"mean {t['mean']:.2f}, t = {t['t']:.3f}, df = {t['df']}, p = "
                                 f"{fmt_p(t['p_value'])} -> {verdict_text(t)}"]
        else:
            lines += ["", head + t["note"]]
    if result.get("comments"):
        parts = []
        for k, v in result["comments"].items():
            if k == "written_to":
                continue
            ids = (f", {v['distinct_ids']} distinct {result['input'].get('id_col', 'id')!r} values"
                   if "distinct_ids" in v else "")
            parts.append(f"{k} {v['with_comment']} of {v['answers']} answers{ids}")
        lines += ["", "Comments: " + "; ".join(parts)]
        if result["comments"].get("written_to"):
            lines.append(f"  Written to {result['comments']['written_to']}")
    for title, key in (("Notes", "notes"), ("Warnings", "warnings")):
        if result.get(key):
            lines += ["", title + ":"] + [f"  - {w}" for w in result[key]]
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------------- CLI

def build_parser():
    parser = argparse.ArgumentParser(
        description="CSAT and CES with Wilson intervals, segment/period comparisons and comments split by group.",
        epilog="Example: python3 scripts/csat_ces_analysis.py ratings.csv --scale 1-5 --segment-col channel --pairwise "
               "--adjust holm --json",
    )
    parser.add_argument("input", nargs="?", help="CSV with one row per answer (any delimiter, UTF-8 or UTF-16)")
    parser.add_argument("--metric", choices=sorted(METRICS), default="csat", help="csat (default), ces or ces5")
    parser.add_argument("--counts", metavar="C1,C2,...", help="answer counts per scale point, lowest scale number first (1, 2, ... 5)")
    parser.add_argument("--score-col", help="rating column (default: detected from the header names)")
    parser.add_argument("--scale", metavar="MIN-MAX", help="the questionnaire's scale, e.g. 1-5, 1-7, 0-10. Needed for "
                        "numeric CSAT; text labels and --labels set it; ces is 1-7 and ces5 1-5 unless given")
    parser.add_argument("--positive", metavar="POINTS", help="points counted as satisfied/easy, e.g. 4-5 (overrides "
                        "the top-2 box)")
    parser.add_argument("--negative", metavar="POINTS", help="points counted as dissatisfied/difficult, e.g. 1-2")
    parser.add_argument("--labels", metavar="LABEL=N,...", help="map text answers to points; its lowest and highest points set the scale unless --scale is given, "
                        "e.g. 'Unhappy=1,Okay=2,Happy=3'")
    parser.add_argument("--segment-col", help="column to break results down by (agent, channel, plan ...)")
    parser.add_argument("--period-col", help="column with the period label (2026-09, 2026-Q3 ...)")
    parser.add_argument("--period-order", metavar="P1,P2,...", help="periods from earliest to latest")
    parser.add_argument("--compare", nargs=2, metavar=("A", "B"), help="test two segments")
    parser.add_argument("--pairwise", action="store_true", help="test every pair of segments")
    parser.add_argument("--compare-periods", nargs=2, metavar=("EARLIER", "LATER"), help="test two periods")
    parser.add_argument("--adjust", choices=["none", "holm", "bonferroni"], default="none",
                        help="multiple-comparison adjustment across the tests in this run (default: none, warns)")
    parser.add_argument("--test", choices=["auto", "z", "fisher"], default="auto",
                        help="share test: auto (Fisher exact when an expected count is under 5, else z), z, fisher")
    parser.add_argument("--target", type=float, metavar="PCT", help="test the overall share against this percent (85, or 0.85)")
    parser.add_argument("--target-mean", type=float, metavar="X", help="test the overall mean against this value")
    parser.add_argument("--tail", choices=["two", "above", "below", "one"], help="target test direction: two (default), above or below")
    parser.add_argument("--comment-col", help="open-ended comment column")
    parser.add_argument("--comments-out", metavar="PATH", help="write comments split by group (.csv or .json)")
    parser.add_argument("--id-col", help="respondent or customer id column (flags repeat answers)")
    parser.add_argument("--paired", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--confidence", type=float, default=0.95, help="confidence level, 0.95 or 95 (default 0.95)")
    parser.add_argument("--min-base", type=int, default=DEFAULT_MIN_BASE,
                        help=f"flag groups with fewer answers as a small base (default {DEFAULT_MIN_BASE})")
    parser.add_argument("--delimiter", help="CSV delimiter: a character or comma, semicolon, tab, pipe (default: sniffed)")
    parser.add_argument("--skip-rows", type=int, help="rows under the header to skip (Qualtrics is detected)")
    parser.add_argument("--allow-unreadable", action="store_true",
                        help="go on when more than 5%% of non-blank answers cannot be read (they are excluded and counted)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON (full precision)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = analyse(args)
    except InputError as exc:
        print(f"csat-ces-analysis: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
