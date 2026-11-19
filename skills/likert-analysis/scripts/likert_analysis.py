#!/usr/bin/env python3
"""Likert analysis: per-item distributions, top-2 and bottom-2 box with Wilson intervals, medians and means,
a diverging stacked bar table, reverse-coded item detection, Cronbach's alpha with a Feldt interval and
alpha-if-item-deleted, and group comparisons (Mann-Whitney per item, a proportion test on the boxes, Welch t
on the scale score).

Standard library only, Python 3.9+. No network, no randomness. Formulas and thresholds: references/sources.md.

Usage:
  python3 scripts/likert_analysis.py survey.csv --items q1,q2,q3,q4 --scale 1-5
  python3 scripts/likert_analysis.py survey.csv --items-prefix engage_ --scale 1-5 --reverse engage_3 --alpha
  python3 scripts/likert_analysis.py survey.csv --items-prefix engage_ --scale 1-5 --alpha --group-col team --pairwise --adjust holm
  python3 scripts/likert_analysis.py survey.csv --items q1,q2 --labels "Never=1,Rarely=2,Sometimes=3,Often=4,Always=5"
  python3 scripts/likert_analysis.py survey.csv --items q1,q2,q3 --scale 1-7 --table-out work/diverging.csv --json

Input: one row per respondent, one column per item. The answer scale comes from --scale, --labels or the text
labels, never from the numbers that happen to appear.

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

DEFAULT_MIN_BASE = 100  # Pew Research Center subgroup reporting rule (shared pack convention)
MIN_N_FOR_VERDICT = 5  # convention of this skill: no verdict when a group has fewer than 5 answers
NON_READ_STOP_SHARE = 0.05  # stop when more than 5% of non-blank answers cannot be read on the scale
EXACT_MW_MAX_N = 50  # exact Mann-Whitney p when both groups have under 50 answers (as R's wilcox.test)


def _labels(*points):
    """Build a label map from (point, label, synonym, ...) tuples."""
    return {label: point for point, *names in points for label in names}


# Each preset is one questionnaire format: its full answer scale and every label on it (synonyms share a point).
# A preset is used only when the answer scale is known (--scale) and matches it, or when it is the only format
# that fits the text answers; see resolve_scale_and_labels. Unipolar scales (frequency, importance) have no
# neutral point: their middle is "sometimes", not "neither".
_NEU_AGREE = ("neither agree nor disagree", "neutral")
_NEU_SAT = ("neither satisfied nor dissatisfied", "neither", "neutral")
LABEL_PRESETS = {
    "agree4": {"scale": (1, 4), "map": _labels(
        (1, "strongly disagree"), (2, "disagree"), (3, "agree"), (4, "strongly agree"))},
    "agree5": {"scale": (1, 5), "map": _labels(
        (1, "strongly disagree"), (2, "disagree"), (3,) + _NEU_AGREE, (4, "agree"), (5, "strongly agree"))},
    "agree5-somewhat": {"scale": (1, 5), "map": _labels(
        (1, "strongly disagree"), (2, "somewhat disagree"), (3,) + _NEU_AGREE, (4, "somewhat agree"),
        (5, "strongly agree"))},
    "agree7": {"scale": (1, 7), "map": _labels(
        (1, "strongly disagree"), (2, "disagree"), (3, "somewhat disagree"), (4,) + _NEU_AGREE,
        (5, "somewhat agree"), (6, "agree"), (7, "strongly agree"))},
    "satisfied5": {"scale": (1, 5), "map": _labels(
        (1, "very dissatisfied"), (2, "dissatisfied"), (3,) + _NEU_SAT, (4, "satisfied"), (5, "very satisfied"))},
    "satisfied5-somewhat": {"scale": (1, 5), "map": _labels(
        (1, "very dissatisfied"), (2, "somewhat dissatisfied"), (3,) + _NEU_SAT, (4, "somewhat satisfied"),
        (5, "very satisfied"))},
    "satisfied7": {"scale": (1, 7), "map": _labels(
        (1, "very dissatisfied"), (2, "dissatisfied"), (3, "somewhat dissatisfied"), (4,) + _NEU_SAT,
        (5, "somewhat satisfied"), (6, "satisfied"), (7, "very satisfied"))},
    "frequency5": {"scale": (1, 5), "unipolar": True, "map": _labels(
        (1, "never"), (2, "rarely"), (3, "sometimes"), (4, "often"), (5, "always"))},
    "importance5": {"scale": (1, 5), "unipolar": True, "map": _labels(
        (1, "not at all important"), (2, "slightly important"), (3, "moderately important"), (4, "very important"),
        (5, "extremely important"))},
}
ALLOWED_PRESETS = tuple(LABEL_PRESETS)
# "4 - Agree", "4 = Agree", "4. Agree", "(4) Agree", "4: Agree", "4 Agree": a number, then a separator or a
# space, then a label. "2hrs" or "1st" are not read as points.
LABELLED_RE = re.compile(r"^\s*(?:\(\s*(-?\d{1,3})\s*\)\s*|(-?\d{1,3})\s*(?:[-–—:=.)]\s*|\s+))([^\W\d_].*)$")
NON_ANSWER_RE = re.compile(
    r"^(n/?a|na|none|-+|\.|\?|don'?t know|do not know|dk|not applicable|prefer not to (say|answer)|refused|"
    r"skipped|no answer|no opinion)$",
    re.I,
)
DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|", "\\t": "\t"}
DELIMITER_NAMES = {",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe"}


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


def text_answers(raw_values):
    """Count each distinct text answer (lower case) that is not blank, a non-answer, a number or a labelled number."""
    counts = {}
    for raw in raw_values:
        text = (raw or "").strip()
        if (not text or NON_ANSWER_RE.match(text) or as_number(text) is not None or labelled_number(text)):
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


def normal_two_sided_p(z):
    return min(1.0, math.erfc(abs(z) / math.sqrt(2)))


def preset_value(name, text):
    return LABEL_PRESETS[name]["map"].get(text)


def read_point(raw, labels):
    """Return (value, None) or (None, reason). Reasons: blank, non_answer, non_numeric, non_integer."""
    text = (raw or "").strip()
    if not text:
        return None, "blank"
    if labels and norm_label(text) in labels:  # a label the map names ("None=1") is a point, not a non-answer
        return labels[norm_label(text)], None
    if NON_ANSWER_RE.match(text):
        return None, "non_answer"
    value = as_number(text)
    if value is None:
        pair = labelled_number(text)
        if pair is None:
            return None, "non_numeric"
        value = float(pair[0])
    if math.isnan(value) or math.isinf(value):
        return None, "non_numeric"
    if value != int(value):
        return None, "non_integer"
    return int(value), None


def f_cdf(x, d1, d2):
    if x <= 0:
        return 0.0
    return regularized_beta(d1 / 2.0, d2 / 2.0, d1 * x / (d1 * x + d2))


def f_quantile(q, d1, d2):
    """Quantile of the F(d1, d2) distribution by bisection on its CDF."""
    low, high = 0.0, 1.0
    while f_cdf(high, d1, d2) < q:
        high *= 2
        if high > 1e12:
            break
    for _ in range(300):
        mid = (low + high) / 2
        if f_cdf(mid, d1, d2) < q:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def variance(values):
    """Sample variance with exact summation; identical values give exactly 0."""
    n = len(values)
    if max(values) == min(values):
        return 0.0
    mean = math.fsum(values) / n
    return math.fsum((v - mean) ** 2 for v in values) / (n - 1)


def cronbach_alpha(matrix):
    """matrix: list of complete respondent rows. alpha = k/(k-1) * (1 - sum of item variances / total variance)."""
    k = len(matrix[0])
    item_vars = [variance([row[j] for row in matrix]) for j in range(k)]
    total_var = variance([sum(row) for row in matrix])
    if total_var == 0:
        return None
    return k / (k - 1) * (1 - sum(item_vars) / total_var)


def feldt_interval(alpha, n, k, confidence):
    """Feldt (1965); Feldt, Woodruff and Salih (1987): (1 - alpha)/(1 - alpha_hat) ~ F(n-1, (n-1)(k-1))."""
    d1, d2 = n - 1, (n - 1) * (k - 1)
    tail = (1 - confidence) / 2
    return 1 - (1 - alpha) * f_quantile(1 - tail, d1, d2), 1 - (1 - alpha) * f_quantile(tail, d1, d2)


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def midranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for m in range(i, j + 1):
            ranks[order[m]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def _rank_sum_counts(n1, n_total):
    """Number of ways to choose n1 of the ranks 1..n_total with each rank sum (no ties)."""
    max_sum = sum(range(n_total - n1 + 1, n_total + 1))
    table = [[0] * (max_sum + 1) for _ in range(n1 + 1)]
    table[0][0] = 1
    for rank in range(1, n_total + 1):
        for size in range(min(n1, rank), 0, -1):
            row, prev = table[size], table[size - 1]
            for s in range(max_sum, rank - 1, -1):
                if prev[s - rank]:
                    row[s] += prev[s - rank]
    return table[n1]


def _exact_conditional_p(x, combined):
    """Two-sided exact p given the observed ties: the permutation distribution of the rank sum of x over every
    way of choosing len(x) of the pooled answers, built tie group by tie group (doubled midranks are integers)."""
    n1 = len(x)
    levels = sorted(set(combined))
    sizes = [combined.count(v) for v in levels]
    doubled, start = {}, 0
    for value, size in zip(levels, sizes):
        doubled[value] = 2 * start + size + 1
        start += size
    observed = sum(doubled[v] for v in x)
    remaining = len(combined)
    dist = {(0, 0): 1}
    for value, size in zip(levels, sizes):
        step = doubled[value]
        remaining -= size
        choose = [math.comb(size, j) for j in range(size + 1)]
        new = {}
        for (k, total), ways in dist.items():
            # Keep only states that can still reach exactly n1 chosen answers.
            for j in range(max(0, n1 - k - remaining), min(size, n1 - k) + 1):
                key = (k + j, total + j * step)
                new[key] = new.get(key, 0) + ways * choose[j]
        dist = new
    final = {total: ways for (k, total), ways in dist.items() if k == n1}
    denominator = math.comb(len(combined), n1)
    below = sum(w for t, w in final.items() if t <= observed) / denominator
    above = sum(w for t, w in final.items() if t >= observed) / denominator
    return min(1.0, 2 * min(below, above))


def mann_whitney(x, y, method="auto"):
    """Mann-Whitney U for x vs y. When both groups have fewer than 50 answers the p-value is exact: the usual
    null distribution without ties, the conditional (permutation) distribution given the ties otherwise, as R's
    wilcox.test documents. Larger groups use the normal approximation with tie and continuity correction.
    Returns U for x (= R's W), p, method, and the probability of superiority P(X > Y) + 0.5 P(X = Y) = U/(n1 n2)."""
    n1, n2 = len(x), len(y)
    combined = list(x) + list(y)
    ranks = midranks(combined)
    u = sum(ranks[:n1]) - n1 * (n1 + 1) / 2
    ties = len(set(combined)) < len(combined)
    out = {"u": u, "n_a": n1, "n_b": n2, "prob_superiority": u / (n1 * n2),
           "rank_biserial": 2 * u / (n1 * n2) - 1}
    exact = method == "exact" or (method == "auto" and n1 < EXACT_MW_MAX_N and n2 < EXACT_MW_MAX_N)
    if not ties and exact:
        counts = _rank_sum_counts(n1, n1 + n2)
        total = math.comb(n1 + n2, n1)
        offset = n1 * (n1 + 1) // 2
        q = int(round(u))
        below = sum(counts[offset + v] for v in range(0, q + 1) if offset + v < len(counts)) / total
        above = sum(counts[offset + v] for v in range(q, n1 * n2 + 1) if offset + v < len(counts)) / total
        out.update({"method": "exact", "p_value": min(1.0, 2 * min(below, above))})
        return out
    if exact:
        out.update({"method": "exact conditional on ties", "p_value": _exact_conditional_p(list(x), combined)})
        return out
    n = n1 + n2
    tie_term = 0.0
    for value in set(combined):
        t = combined.count(value)
        tie_term += t ** 3 - t
    sigma = math.sqrt(n1 * n2 / 12 * ((n + 1) - tie_term / (n * (n - 1))))
    centred = u - n1 * n2 / 2
    if sigma == 0:
        out.update({"method": "normal approximation", "p_value": 1.0, "z": 0.0})
        return out
    correction = 0.5 if centred > 0 else (-0.5 if centred < 0 else 0.0)
    z = (centred - correction) / sigma
    out.update({"method": "normal approximation, tie and continuity corrected", "z": z,
                "p_value": normal_two_sided_p(z)})
    return out


# ------------------------------------------------------------------------------------------------- analysis

def detect_items(headers, args, exclude):
    if args.items:
        items = [c.strip() for c in args.items.split(",") if c.strip()]
        missing = [c for c in items if c not in headers]
        if missing:
            raise InputError("--items: not columns: " + ", ".join(missing) + ". Columns: " + ", ".join(headers))
        if len(set(items)) != len(items):
            raise InputError("--items lists a column twice")
        return items, "given"
    if args.items_prefix:
        items = [h for h in headers if h.startswith(args.items_prefix) and h not in exclude]
        if not items:
            raise InputError(f"no column starts with {args.items_prefix!r}. Columns: " + ", ".join(headers))
        return items, f"columns starting with {args.items_prefix!r}"
    raise InputError("name the items: --items COL1,COL2,... or --items-prefix PREFIX. Columns: " + ", ".join(headers))


def item_summary(name, values, scale, box, z, confidence, min_base):
    low, high = scale
    n = len(values)
    points = list(range(low, high + 1))
    counts = {str(p): sum(1 for v in values if v == p) for p in points}
    top = points[-box:]
    bottom = points[:box]
    mid = (low + high) / 2
    out = {"item": name, "n": n, "distribution": counts, "small_base": n < min_base,
           "top_box_points": top, "bottom_box_points": bottom}
    if n == 0:
        out["note"] = "no valid answers"
        return out
    x_top = sum(1 for v in values if v in top)
    x_bottom = sum(1 for v in values if v in bottom)
    ordered = sorted(values)
    m = n // 2
    median = float(ordered[m]) if n % 2 else (ordered[m - 1] + ordered[m]) / 2
    mean, sd = mean_sd(values)
    out.update({
        "pct": {k: 100 * v / n for k, v in counts.items()},
        "top_box": x_top, "pct_top_box": 100 * x_top / n, "top_box_ci": [100 * c for c in wilson(x_top, n, z)],
        "bottom_box": x_bottom, "pct_bottom_box": 100 * x_bottom / n,
        "bottom_box_ci": [100 * c for c in wilson(x_bottom, n, z)],
        "diverging": {"negative": 100 * sum(1 for v in values if v < mid) / n,
                      "neutral": 100 * sum(1 for v in values if v == mid) / n,
                      "positive": 100 * sum(1 for v in values if v > mid) / n},
        "median": median, "mean": mean, "sd": sd,
    })
    if sd:
        half = t_critical(confidence, n - 1) * sd / math.sqrt(n)
        out["mean_ci"] = [max(low, mean - half), min(high, mean + half)]  # clipped to the scale's ends
    elif sd == 0:
        out["mean_ci"] = [mean, mean]
        out["note"] = "every answer is the same: the interval has zero width and says nothing about precision"
    if n % 2 == 0 and ordered[m - 1] != ordered[m]:
        out["median_note"] = "the two middle answers differ; the median is their midpoint"
    return out


def reliability(items, records, confidence):
    complete = [[r[i] for i in items] for r in records if all(r.get(i) is not None for i in items)]
    n, k = len(complete), len(items)
    out = {"items": items, "k": k, "n_complete": n}
    if k < 2:
        out["note"] = "alpha needs at least 2 items"
        return out, complete
    if n < 3:
        out["note"] = "alpha needs at least 3 respondents who answered every item"
        return out, complete
    per_item = []
    for j, name in enumerate(items):
        # Item orientation is checked whether or not alpha is defined: items that cancel each other out give
        # a constant total (alpha undefined) and corrected item-total correlations of -1.
        rest = [sum(row) - row[j] for row in complete]
        own = [row[j] for row in complete]
        entry = {"item": name, "corrected_item_total_r": pearson(own, rest)}
        if k > 2:
            # Same listwise sample as the full-scale alpha, so the two are comparable.
            entry["alpha_if_deleted"] = cronbach_alpha([row[:j] + row[j + 1:] for row in complete])
        per_item.append(entry)
    out["per_item"] = per_item
    alpha = cronbach_alpha(complete)
    if alpha is None:
        out["note"] = "every respondent has the same total: alpha is undefined"
        return out, complete
    out["alpha"] = alpha
    low, high = feldt_interval(alpha, n, k, confidence)
    out["alpha_ci"] = [low, high]
    return out, complete


def set_verdict(result, alpha):
    """significant / not significant. A small base is flagged, not turned into a power claim: power depends on
    the effect size, so a non-significant result says only that the interval includes no difference."""
    p_value = result.get("p_adjusted", result["p_value"])
    result["significant"] = p_value < alpha
    result["verdict"] = "significant" if result["significant"] else "not significant"


def compare_item(item, a_label, b_label, a_vals, b_vals, top, z, confidence, min_base, mw_method):
    out = {"item": item, "a": a_label, "b": b_label, "n_a": len(a_vals), "n_b": len(b_vals),
           "small_base": len(a_vals) < min_base or len(b_vals) < min_base}
    if min(len(a_vals), len(b_vals)) < MIN_N_FOR_VERDICT:
        out.update({"tested": False, "note": f"fewer than {MIN_N_FOR_VERDICT} answers on one side: no verdict"})
        return out
    mw = mann_whitney(a_vals, b_vals, mw_method)
    out.update({"test": f"Mann-Whitney ({mw['method']})", "u": mw["u"], "p_value": mw["p_value"],
                "prob_superiority": mw["prob_superiority"], "rank_biserial": mw["rank_biserial"], "tested": True})
    if "z" in mw:
        out["z"] = mw["z"]
    x1 = sum(1 for v in a_vals if v in top)
    x2 = sum(1 for v in b_vals if v in top)
    n1, n2 = len(a_vals), len(b_vals)
    low, high = newcombe(x1, n1, x2, n2, z)
    total = x1 + x2
    expected = [n1 * total / (n1 + n2), n1 * (n1 + n2 - total) / (n1 + n2),
                n2 * total / (n1 + n2), n2 * (n1 + n2 - total) / (n1 + n2)]
    if min(expected) < 5:
        box_p, box_test = fisher_exact(x1, n1, x2, n2), "Fisher exact"
    else:
        box_p, box_test = two_proportion_z(x1, n1, x2, n2)[1], "two-proportion z"
    out["top_box"] = {"difference_pct": 100 * (x1 / n1 - x2 / n2), "ci": [100 * low, 100 * high],
                      "p_value": box_p, "test": box_test, "tested": True, "small_base": out["small_base"]}
    return out


def welch(a, b, confidence, min_base):
    out = {"n_a": len(a), "n_b": len(b), "small_base": len(a) < min_base or len(b) < min_base}
    if min(len(a), len(b)) < MIN_N_FOR_VERDICT:
        return dict(out, tested=False, note=f"fewer than {MIN_N_FOR_VERDICT} respondents on one side: no verdict")
    (ma, sa), (mb, sb) = mean_sd(a), mean_sd(b)
    va, vb = sa * sa / len(a), sb * sb / len(b)
    if va + vb == 0:
        return dict(out, tested=False, note="no variation: the test is undefined")
    se = math.sqrt(va + vb)
    df = (va + vb) ** 2 / (va * va / (len(a) - 1) + vb * vb / (len(b) - 1))
    t_stat = (ma - mb) / se
    half = t_critical(confidence, df) * se
    out.update({"test": "Welch t", "difference": ma - mb, "t": t_stat, "df": df,
                "p_value": t_two_sided_p(t_stat, df), "ci": [ma - mb - half, ma - mb + half], "tested": True})
    return out


def test_family(tests):
    """Every p-value the run reports as a test: each item's Mann-Whitney test, each item's top-box test, and the
    scale-score Welch test. One family, so --adjust covers all of them."""
    family = []
    for t in tests:
        if t.get("tested"):
            family.append(t)
            if t.get("top_box", {}).get("tested"):
                family.append(t["top_box"])
    return family


def adjust(tests, method, alpha):
    tested = test_family(tests)
    m = len(tested)
    for t in tested:
        t["family_size"] = m
    if method == "none" or m < 2:
        return
    if method == "bonferroni":
        for t in tested:
            t["p_adjusted"] = min(1.0, t["p_value"] * m)
    else:
        running = 0.0
        for rank, t in enumerate(sorted(tested, key=lambda t: t["p_value"])):
            running = max(running, min(1.0, (m - rank) * t["p_value"]))
            t["p_adjusted"] = running
    for t in tested:
        t["adjustment"] = method
        set_verdict(t, alpha)


def same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.realpath(a) == os.path.realpath(b)


def analyse(args):
    if args.confidence > 1:
        args.confidence /= 100
    if not math.isfinite(args.confidence) or not 0.5 <= args.confidence < 1:
        raise InputError("--confidence must be between 0.5 and 1 (for example 0.95 or 95)")
    if args.min_base < 1:
        raise InputError(f"--min-base must be 1 or more; got {args.min_base}")
    if args.box is not None and args.box < 1:
        raise InputError(f"--box must be 1 or more; got {args.box}")
    notes, warnings = [], []
    headers, rows = read_table(args.input, args.delimiter, args.skip_rows, notes)
    if args.group_col and args.group_col not in headers:
        raise InputError(f"--group-col {args.group_col!r} is not a column. Columns: " + ", ".join(headers))
    items, items_source = detect_items(headers, args, {args.group_col})
    if args.group_col in items:
        raise InputError("--group-col is also listed as an item")
    raw = [r[c] for r in rows for c in items]
    scale, scale_source, labels, label_source = resolve_scale_and_labels(
        raw, parse_scale(args.scale) if args.scale else None, None,
        parse_label_map(args.labels) if args.labels else None, ALLOWED_PRESETS, {})
    if labels and label_source != "given":
        notes.append(label_map_note(labels, label_source))
    labelled = labelled_numbers_note(raw)
    if labelled:
        notes.append(labelled)
    preset = LABEL_PRESETS.get(label_source or "")
    if args.unipolar or (preset and preset.get("unipolar")):
        polarity = "unipolar"
    elif preset:
        polarity = "bipolar"
    else:
        polarity = "not stated"
    regions = ("negative", "neutral", "positive") if polarity == "bipolar" else ("low", "middle", "high")
    if polarity == "not stated":
        notes.append("Numeric answers: the bars split below, at and above the midpoint. If the scale is bipolar "
                      "(disagree to agree) the midpoint is neutral; pass --unipolar for never-to-always or "
                      "importance scales, where it is not.")
    parsed = {c: [read_point(r[c], labels) for r in rows] for c in items}
    points = scale[1] - scale[0] + 1
    box = args.box or (2 if points >= 4 else 1)
    if box * 2 > points:
        raise InputError(f"--box {box} is too wide for a {points}-point scale")
    reverse = [c.strip() for c in (args.reverse or "").split(",") if c.strip()]
    for c in reverse:
        if c not in items:
            raise InputError(f"--reverse {c!r} is not one of the items")
    excluded = {}
    per_item = {c: {"unread": 0, "non_blank": 0} for c in items}
    unread = non_blank = 0
    records = [dict() for _ in rows]  # answers as given; reversal applies only to the keyed scale score
    for c in items:
        for i, (value, reason) in enumerate(parsed[c]):
            if reason is None and not scale[0] <= value <= scale[1]:
                reason = "out_of_range"
            if reason in ("blank", "non_answer"):
                excluded[reason] = excluded.get(reason, 0) + 1
                records[i][c] = None
                continue
            non_blank += 1
            per_item[c]["non_blank"] += 1
            if reason:
                unread += 1
                per_item[c]["unread"] += 1
                excluded[reason] = excluded.get(reason, 0) + 1
                records[i][c] = None
                continue
            records[i][c] = value
    bad_items = [c for c in items if per_item[c]["non_blank"]
                 and per_item[c]["unread"] / per_item[c]["non_blank"] > NON_READ_STOP_SHARE]
    if (non_blank and unread / non_blank > NON_READ_STOP_SHARE or bad_items) and not args.allow_unreadable:
        where = (f"; items over 5%: {', '.join(bad_items)}" if bad_items else "")
        raise InputError(
            f"{unread} of {non_blank} non-blank answers ({100 * unread / non_blank:.1f}%) could not be read on the "
            f"{scale[0]}-{scale[1]} scale ({', '.join(f'{k} {v}' for k, v in sorted(excluded.items()) if k not in ('blank', 'non_answer'))})"
            f"{where}. That is more than 5% overall or in one item, so a whole answer category may be dropping out. "
            "Check --items, --scale and --labels; pass --allow-unreadable only if these answers really are unusable."
        )

    def keyed(c, value):
        return scale[0] + scale[1] - value if c in reverse else value

    if args.group_col:
        for i, r in enumerate(rows):
            records[i]["_group"] = r[args.group_col].strip() or "(blank)"
    z = z_for(args.confidence)
    alpha_level = 1 - args.confidence
    summaries = []
    for c in items:
        vals = [r[c] for r in records if r.get(c) is not None]
        s = item_summary(c, vals, scale, box, z, args.confidence, args.min_base)
        s["reversed_in_scale_score"] = c in reverse
        s["unreadable"] = per_item[c]["unread"]
        summaries.append(s)
    if not any(s["n"] for s in summaries):
        raise InputError("no valid answers in any item after exclusions")
    result = {
        "tool": "likert-analysis", "version": VERSION,
        "input": {"source": args.input, "items": items, "items_source": items_source, "rows_read": len(rows),
                  "cells_excluded": excluded, "reversed": reverse},
        "scale": {"min": scale[0], "max": scale[1], "points": points, "source": scale_source,
                  "polarity": polarity, "region_labels": list(regions),
                  "top_box_points": summaries[0]["top_box_points"],
                  "bottom_box_points": summaries[0]["bottom_box_points"],
                  "neutral_point": (scale[0] + scale[1]) // 2 if points % 2 and polarity == "bipolar" else None},
        "confidence": args.confidence,
        "items": summaries,
    }
    if labels:
        result["input"]["labels"] = {"source": label_source, "map": labels}
    if reverse:
        notes.append("Item results are as answered; " + ", ".join(reverse) + " reversed (min + max - x) only in "
                     "the reliability check and the scale score.")
    for s in summaries:
        if s["n"] and len([k for k, v in s["distribution"].items() if v]) == 1:
            warnings.append(f"{s['item']}: every answer is the same point; nothing to compare or correlate.")
        if not s["n"]:
            warnings.append(f"{s['item']}: no readable answers ({s['unreadable']} unreadable).")
    small = [s["item"] for s in summaries if s["n"] and s["small_base"]]
    if small:
        warnings.append(f"Small base (under {args.min_base} answers) on {len(small)} item(s); report intervals: a "
                        "result that is not significant there says little, since the interval is wide.")
    scale_scores = {}
    if args.alpha or args.scale_items is not None:
        if args.scale_items is not None:
            scale_items = []
            for c in (c.strip() for c in args.scale_items.split(",")):
                if c and c not in scale_items:
                    scale_items.append(c)
            bad = [c for c in scale_items if c not in items]
            if bad:
                raise InputError("--scale-items must be among the items: " + ", ".join(bad))
        else:
            scale_items = items
        if len(scale_items) < 2:
            raise InputError("a reliability check needs at least two different items; --scale-items gave "
                             f"{len(scale_items)}")
        keyed_records = [{c: (None if r.get(c) is None else keyed(c, r[c])) for c in scale_items} for r in records]
        rel, complete = reliability(scale_items, keyed_records, args.confidence)
        result["reliability"] = rel
        if rel.get("per_item"):
            negative = [e["item"] for e in rel["per_item"]
                        if e["corrected_item_total_r"] is not None and e["corrected_item_total_r"] < 0]
            if negative:
                rel["direction_problem"] = negative
                warnings.append(
                    "Negative corrected item-total correlation: " + ", ".join(negative) + ". These items run against "
                    "the rest: check the wording; if they are reverse-worded, rerun with --reverse " +
                    ",".join(negative) + ". Do not reverse an item only because the number improves."
                )
            weak = [e["item"] for e in rel["per_item"] if e["corrected_item_total_r"] is not None
                    and 0 <= e["corrected_item_total_r"] < 0.3]
            if weak:
                notes.append("Corrected item-total r under 0.3 (weak fit with the rest): " + ", ".join(weak) + ".")
        if rel.get("alpha") is not None and rel["alpha"] < 0:
            warnings.append(f"Alpha is negative ({rel['alpha']:.3f}): the items are not all scored in the same "
                            "direction, or they do not measure one thing. Do not report it as a reliability.")
        if rel.get("n_complete", 0) < len(rows):
            notes.append(f"Alpha uses the {rel['n_complete']} respondents who answered every scale item "
                         f"(listwise); {len(rows) - rel['n_complete']} left out.")
        for i, r in enumerate(keyed_records):
            if all(r.get(c) is not None for c in scale_items):
                scale_scores[i] = math.fsum(r[c] for c in scale_items) / len(scale_items)
        vals = list(scale_scores.values())
        if vals:
            mean, sd = mean_sd(vals)
            rel["scale_score"] = {"n": len(vals), "mean": mean, "sd": sd,
                                  "definition": "mean of the scale items, reverse-worded items reversed"}
            if sd:
                half = t_critical(args.confidence, len(vals) - 1) * sd / math.sqrt(len(vals))
                rel["scale_score"]["ci"] = [mean - half, mean + half]
    if args.group_col:
        names = sorted({r["_group"] for r in records})
        result["groups"] = []
        for g in names:
            members = [r for r in records if r["_group"] == g]
            entry = {"label": g, "n": len(members),
                     "items": [item_summary(c, [r[c] for r in members if r.get(c) is not None], scale, box, z,
                                            args.confidence, args.min_base) for c in items]}
            vals = [scale_scores[i] for i, r in enumerate(records) if r["_group"] == g and i in scale_scores]
            if vals:
                mean, sd = mean_sd(vals)
                entry["scale_score"] = {"n": len(vals), "mean": mean, "sd": sd}
                if sd:
                    half = t_critical(args.confidence, len(vals) - 1) * sd / math.sqrt(len(vals))
                    entry["scale_score"]["ci"] = [mean - half, mean + half]
            result["groups"].append(entry)
        if len(names) == 1:
            warnings.append(f"Only one group ({names[0]}); nothing to compare.")
        pairs = []
        if args.compare:
            for g in args.compare:
                if g not in names:
                    raise InputError(f"--compare: group {g!r} not found. Groups: " + ", ".join(names))
            if args.compare[0] == args.compare[1]:
                raise InputError("--compare names the same group twice")
            pairs = [tuple(args.compare)]
        elif args.pairwise:
            # Rows with no group are summarised but not tested: they are not a group anyone asked about.
            real = [g for g in names if g != "(blank)"]
            pairs = [(a, b) for i, a in enumerate(real) for b in real[i + 1:]]
            if len(real) < len(names):
                notes.append("Rows with a blank group are shown as '(blank)' and left out of --pairwise.")
        tests = []
        top = list(range(scale[1] - box + 1, scale[1] + 1))
        sizes = {g: sum(1 for r in records if r["_group"] == g) for g in names}
        slow = [p for p in pairs if 30 <= min(sizes[p[0]], sizes[p[1]])
                and (args.mw_method == "exact" or max(sizes[p[0]], sizes[p[1]]) < EXACT_MW_MAX_N)]
        if args.mw_method != "normal" and len(slow) * len(items) >= 20 and points >= 7:
            print(f"likert-analysis: running {len(slow) * len(items)} exact Mann-Whitney tests on groups of 30 to 49; "
                  "each can take about half a second on 7 to 11 points, so this may take minutes. "
                  "--mw-method normal is much faster.", file=sys.stderr)
        for a, b in pairs:
            for c in items:
                av = [r[c] for r in records if r["_group"] == a and r.get(c) is not None]
                bv = [r[c] for r in records if r["_group"] == b and r.get(c) is not None]
                tests.append(compare_item(c, a, b, av, bv, top, z, args.confidence, args.min_base, args.mw_method))
            if result.get("reliability", {}).get("direction_problem"):
                tests.append({"item": "(scale score)", "a": a, "b": b, "tested": False,
                              "note": "not compared: some items run against the rest; fix reverse coding first"})
            elif result.get("reliability", {}).get("scale_score"):
                av = [scale_scores[i] for i, r in enumerate(records) if r["_group"] == a and i in scale_scores]
                bv = [scale_scores[i] for i, r in enumerate(records) if r["_group"] == b and i in scale_scores]
                w = welch(av, bv, args.confidence, args.min_base)
                w.update({"item": "(scale score)", "a": a, "b": b})
                tests.append(w)
        for t in test_family(tests):
            set_verdict(t, alpha_level)
        adjust(tests, args.adjust, alpha_level)
        family = test_family(tests)
        if len(family) > 1 and args.adjust == "none":
            warnings.append(f"{len(family)} tests were run (rank and top-box tests per item, and the scale score) "
                            "without a multiple-comparison adjustment; pass --adjust holm, or report the number of "
                            "tests.")
        if tests:
            result["comparisons"] = tests
    elif args.compare or args.pairwise:
        raise InputError("--compare and --pairwise need --group-col")
    if args.table_out:
        if same_file(args.table_out, args.input):
            raise InputError("--table-out points at the input file; choose another path")
        try:
            os.makedirs(os.path.dirname(os.path.abspath(args.table_out)), exist_ok=True)
            with open(args.table_out, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["item", "n", "unreadable", "reversed_in_scale_score"] +
                                [f"pct_{p}" for p in range(scale[0], scale[1] + 1)] +
                                [f"pct_{r}" for r in regions] + ["pct_top_box", "median", "mean"])
                for s in summaries:
                    if s["n"]:
                        writer.writerow([s["item"], s["n"], s["unreadable"], s["reversed_in_scale_score"]] +
                                        [s["pct"][str(p)] for p in range(scale[0], scale[1] + 1)] +
                                        [s["diverging"]["negative"], s["diverging"]["neutral"],
                                         s["diverging"]["positive"], s["pct_top_box"], s["median"], s["mean"]])
                    else:  # kept, so an item that could not be read does not vanish from the chart
                        writer.writerow([s["item"], 0, s["unreadable"], s["reversed_in_scale_score"]] +
                                        [""] * (points + 6))
        except OSError as exc:
            raise InputError(f"cannot write {args.table_out}: {exc.strerror or exc}")
        result["input"]["table_written_to"] = args.table_out
    result["notes"] = notes
    result["warnings"] = warnings
    return result


# ------------------------------------------------------------------------------------------------ rendering

def fmt_p(p_value):
    return "< 0.0001" if p_value < 0.0001 else f"= {p_value:.4f}"


def verdict_text(t):
    text = t["verdict"]
    if not t["significant"] and t.get("small_base"):
        text += " (small base: a real difference may have been missed)"
    return text


def bar(s, width=40):
    """Diverging bar centred on a common column, so items line up on the midpoint: below | at | above."""
    d = s["diverging"]
    neg, neu, pos = (round(width * d[k] / 100) for k in ("negative", "neutral", "positive"))
    left = neg + neu // 2
    return " " * (width - left) + "-" * neg + "." * (neu // 2) + "|" + "." * (neu - neu // 2) + "+" * pos


def render(result):
    sc = result["scale"]
    inp = result["input"]
    lo, mid, hi = sc["region_labels"]
    lines = [f"Items: {', '.join(inp['items'])} ({inp['items_source']}). Scale {sc['min']}-{sc['max']} "
             f"({sc['source']}; {sc['polarity']}); top box = {','.join(map(str, sc['top_box_points']))}, bottom box = "
             f"{','.join(map(str, sc['bottom_box_points']))}" +
             (f"; reversed in the scale score only: {', '.join(inp['reversed'])}" if inp["reversed"] else "") + "."]
    ex = inp["cells_excluded"]
    lines.append(f"Data: {inp['source']}. Rows {inp['rows_read']}; answers excluded {sum(ex.values())}" +
                 (f" ({', '.join(f'{k} {v}' for k, v in sorted(ex.items()))})" if ex else "") + ".")
    lines.append(f"Intervals: {round(100 * result['confidence'], 4):g}%; boxes Wilson score, means t.")
    lines += ["", f"Per item, as answered (bar: - {lo} | . {mid} | + {hi}, centred on the midpoint):"]
    for s in result["items"]:
        if not s["n"]:
            lines.append(f"  {s['item']}: no valid answers ({s['unreadable']} unreadable)")
            continue
        dist = " ".join(f"{k}:{v:.0f}%" for k, v in s["pct"].items())
        lines.append(f"  {s['item']}: n = {s['n']}"
                     f"{' [small base]' if s['small_base'] else ''}; top box {s['pct_top_box']:.1f}% "
                     f"({s['top_box_ci'][0]:.1f} to {s['top_box_ci'][1]:.1f}); bottom box {s['pct_bottom_box']:.1f}% "
                     f"({s['bottom_box_ci'][0]:.1f} to {s['bottom_box_ci'][1]:.1f}); "
                     f"median {s['median']:g}; mean {s['mean']:.2f}" +
                     (f" ({s['mean_ci'][0]:.2f} to {s['mean_ci'][1]:.2f})" if s.get("mean_ci") else "") +
                     (f"; {s['unreadable']} unreadable" if s["unreadable"] else "") +
                     (f" [{s['median_note']}]" if s.get("median_note") else "") +
                     (f" [{s['note']}]" if s.get("note") else ""))
        lines.append(f"      {dist}   {bar(s)}")
    for g in result.get("groups", []):
        ss = g.get("scale_score")
        lines += ["", f"Group {g['label']} (n = {g['n']})" +
                  (f"; scale score mean {ss['mean']:.2f}" + (f" ({ss['ci'][0]:.2f} to {ss['ci'][1]:.2f})" if ss.get("ci")
                                                              else "") if ss else "") + ":"]
        for s in g["items"]:
            if s["n"]:
                lines.append(f"  {s['item']}: n = {s['n']}; top box {s['pct_top_box']:.1f}% "
                             f"({s['top_box_ci'][0]:.1f} to {s['top_box_ci'][1]:.1f}); bottom box "
                             f"{s['pct_bottom_box']:.1f}%; median {s['median']:g}; mean {s['mean']:.2f}")
    rel = result.get("reliability")
    if rel:
        lines += ["", f"Reliability ({rel['k']} items, {rel['n_complete']} complete respondents):"]
        if "alpha" in rel:
            lines.append(f"  Cronbach's alpha {rel['alpha']:.3f} (Feldt {round(100 * result['confidence'], 4):g}% "
                         f"interval {rel['alpha_ci'][0]:.3f} to {rel['alpha_ci'][1]:.3f})")
        else:
            lines.append(f"  {rel.get('note')}")
        for e in rel.get("per_item", []):
            r = e["corrected_item_total_r"]
            lines.append(f"    {e['item']}: corrected item-total r " + ("-" if r is None else f"{r:.3f}") +
                         (f"; alpha if deleted {e['alpha_if_deleted']:.3f}" if e.get("alpha_if_deleted") is not None else ""))
        if rel.get("scale_score"):
            ss = rel["scale_score"]
            lines.append(f"  Scale score (mean of items, reversed items keyed): n = {ss['n']}, mean {ss['mean']:.2f}" +
                         (f" ({ss['ci'][0]:.2f} to {ss['ci'][1]:.2f})" if ss.get("ci") else ""))
    if result.get("comparisons"):
        lines += ["", "Comparisons (A vs B; independent groups; p-values raw unless marked adjusted):"]
        for t in result["comparisons"]:
            head = f"  {t['item']}: {t['a']} vs {t['b']}: "
            if not t.get("tested"):
                lines.append(head + t.get("note", "not tested"))
                continue
            p_text = f"p {fmt_p(t['p_value'])}" + (f", {t['adjustment']}-adjusted p {fmt_p(t['p_adjusted'])} over "
                                                   f"{t['family_size']} tests" if "p_adjusted" in t else "")
            if t["item"] == "(scale score)":
                lines.append(head + f"mean difference {t['difference']:+.2f} ({t['ci'][0]:+.2f} to {t['ci'][1]:+.2f}), "
                             f"Welch t, {p_text}: {verdict_text(t)}")
            else:
                tb = t["top_box"]
                tb_p = f"p {fmt_p(tb['p_value'])}" + (f", {tb['adjustment']}-adjusted p {fmt_p(tb['p_adjusted'])}"
                                                       if "p_adjusted" in tb else "")
                lines.append(head + f"{t['test']}, U = {t['u']:g}, P(A > B) + half P(A = B) = "
                             f"{t['prob_superiority']:.2f}, {p_text}: {verdict_text(t)}. Top box "
                             f"{tb['difference_pct']:+.1f} points ({tb['ci'][0]:+.1f} to {tb['ci'][1]:+.1f}), "
                             f"{tb['test']} {tb_p}: {verdict_text(tb)}")
    if inp.get("table_written_to"):
        lines.append(f"\nDiverging table written to {inp['table_written_to']}")
    for title, key in (("Notes", "notes"), ("Warnings", "warnings")):
        if result.get(key):
            lines += ["", title + ":"] + [f"  - {w}" for w in result[key]]
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------------- CLI

def build_parser():
    parser = argparse.ArgumentParser(
        description="Likert and rating-scale items: distributions, boxes, medians and means, Cronbach's alpha, "
                    "group comparisons.",
        epilog="Example: python3 scripts/likert_analysis.py survey.csv --items-prefix engage_ --scale 1-5 --alpha "
               "--group-col team --pairwise --adjust holm --json",
    )
    parser.add_argument("input", help="CSV with one row per respondent (any delimiter, UTF-8 or UTF-16)")
    parser.add_argument("--items", metavar="COL,...", help="item columns")
    parser.add_argument("--items-prefix", metavar="PREFIX", help="every column starting with PREFIX is an item")
    parser.add_argument("--scale", metavar="MIN-MAX", help="the questionnaire's answer scale, e.g. 1-5. Needed for "
                        "numeric answers; text labels and --labels set it otherwise")
    parser.add_argument("--unipolar", action="store_true", help="the scale runs from none to a lot (never-always, "
                        "not at all-extremely important): its middle is not neutral")
    parser.add_argument("--labels", metavar="LABEL=N,...", help="map text answers to points; its lowest and highest "
                        "points set the scale unless --scale is given")
    parser.add_argument("--box", type=int, help="width of the top and bottom box, 1 or more (default 2; 1 on a 2-3 "
                        "point scale)")
    parser.add_argument("--reverse", metavar="COL,...", help="reverse-worded items, recoded as min + max - x in the "
                        "reliability check and scale score (item results stay as answered)")
    parser.add_argument("--alpha", action="store_true", help="treat the items as one scale: Cronbach's alpha and a "
                        "scale score")
    parser.add_argument("--scale-items", metavar="COL,...", help="the subset of items that form the scale (implies --alpha)")
    parser.add_argument("--group-col", help="column to compare groups by")
    parser.add_argument("--compare", nargs=2, metavar=("A", "B"), help="compare two groups")
    parser.add_argument("--pairwise", action="store_true", help="compare every pair of groups")
    parser.add_argument("--adjust", choices=["none", "holm", "bonferroni"], default="none",
                        help="multiple-comparison adjustment over every test in the run: rank and top-box tests "
                        "per item and the scale score (default none, warns)")
    parser.add_argument("--mw-method", choices=["auto", "exact", "normal"], default="auto",
                        help="Mann-Whitney p: auto (exact when both groups have under 50 answers, as R), exact, or "
                        "normal (tie- and continuity-corrected approximation)")
    parser.add_argument("--table-out", metavar="PATH", help="write the per-item diverging table to a CSV")
    parser.add_argument("--confidence", type=float, default=0.95, help="confidence level, 0.95 or 95 (default 0.95)")
    parser.add_argument("--min-base", type=int, default=DEFAULT_MIN_BASE,
                        help=f"flag items or groups with fewer answers as a small base (default {DEFAULT_MIN_BASE})")
    parser.add_argument("--delimiter", help="CSV delimiter: a character or comma, semicolon, tab, pipe (default sniffed)")
    parser.add_argument("--skip-rows", type=int, help="rows under the header to skip (Qualtrics is detected)")
    parser.add_argument("--allow-unreadable", action="store_true",
                        help="go on when more than 5%% of answers cannot be read (they are excluded and counted)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON (full precision)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = analyse(args)
    except InputError as exc:
        print(f"likert-analysis: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
