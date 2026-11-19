#!/usr/bin/env python3
"""UX scale scoring: SUS (standard or all-positive), UMUX-Lite, SEQ and raw NASA-TLX from a CSV, with t
intervals, the SUS curved grade, percentile and adjective, checks for miscoded SUS data, and tests of two
designs (independent or paired) or of a target.

Standard library only, Python 3.9+. No network, no randomness. Formulas and benchmarks: references/sources.md.

Usage:
  python3 scripts/ux_scale_scoring.py sus.csv --instrument sus
  python3 scripts/ux_scale_scoring.py sus.csv --instrument sus --group-col design --compare A B
  python3 scripts/ux_scale_scoring.py sus.csv --instrument sus --group-col design --compare A B --paired --id-col participant
  python3 scripts/ux_scale_scoring.py umux.csv --instrument umux-lite --items capabilities,ease
  python3 scripts/ux_scale_scoring.py seq.csv --instrument seq --group-col task
  python3 scripts/ux_scale_scoring.py tlx.csv --instrument tlx --target 50 --tail below
  python3 scripts/ux_scale_scoring.py sus.csv --instrument sus --scores-out work/sus_scores.csv --json

Input: one row per participant (per participant and design for a within-subjects study), one column per item.

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

VERSION = "0.1.1"

INSTRUMENTS = {
    "sus": {"name": "SUS (standard, alternating tone)", "items": 10, "scale": (1, 5), "higher_is_better": True},
    "sus-positive": {"name": "SUS (all-positive wording)", "items": 10, "scale": (1, 5), "higher_is_better": True},
    "umux-lite": {"name": "UMUX-Lite", "items": 2, "scale": (1, 7), "higher_is_better": True},
    "seq": {"name": "SEQ (Single Ease Question)", "items": 1, "scale": (1, 7), "higher_is_better": True},
    "tlx": {"name": "Raw NASA-TLX", "items": 6, "scale": (0, 100), "higher_is_better": False},
}
# Sauro and Lewis (2016) curved grading scale, as published in Lewis and Sauro (2018) and on MeasuringU: lower
# bound of each grade's SUS range and the lower bound of its percentile range. Percentiles between rows are
# linear interpolation (this skill's convention), anchored at (0, 0) and (100, 100).
CGS = [
    ("F", 0.0, 0.0), ("F", 25.1, 2.0), ("D", 51.7, 15.0), ("C-", 62.7, 35.0), ("C", 65.0, 41.0),
    ("C+", 71.1, 60.0), ("B-", 72.6, 65.0), ("B", 74.1, 70.0), ("B+", 77.2, 80.0), ("A-", 78.9, 85.0),
    ("A", 80.8, 90.0), ("A+", 84.1, 96.0),
]
# Bangor, Kortum and Miller (2009): mean SUS of participants who chose each adjective.
ADJECTIVES = [
    ("Worst Imaginable", 12.5), ("Awful", 20.3), ("Poor", 35.7), ("OK", 50.9), ("Good", 71.4),
    ("Excellent", 85.5), ("Best Imaginable", 90.9),
]
# The curved grade and the closest adjective come from different published schemes. When the adjective falls
# outside these (this skill's reading of the two tables side by side), the output says the two disagree.
GRADE_ADJECTIVES = {"A": {"Excellent", "Best Imaginable"}, "B": {"Good", "Excellent"}, "C": {"OK", "Good"},
                    "D": {"Poor", "OK"}, "F": {"Worst Imaginable", "Awful", "Poor"}}
UMUX_LITE_SLOPE, UMUX_LITE_INTERCEPT = 0.65, 22.9  # Lewis, Utesch and Maher (2013), n = 791; 7-point only
SUS_BENCHMARK_MEAN = 68  # average SUS, 50th percentile (Sauro and Lewis 2016; MeasuringU)
DEFAULT_MIN_BASE = 12  # this skill's reporting convention, not a power rule; see references/sources.md
DEFAULT_MAX_IMPUTED = 1  # --impute-midpoint fills at most this many skipped SUS items per participant
NON_READ_STOP_SHARE = 0.05  # stop when more than 5% of non-blank item answers cannot be read
TLX_SUBSCALES = ("mental", "physical", "temporal", "performance", "effort", "frustration")
TLX_PATTERNS = {
    # Whole words only: "time" alone would match "Timestamp", "hard" would match "hardware".
    "mental": r"mental", "physical": r"physical",
    "temporal": r"temporal|(?<![a-z])time[ _-]?pressure|(?<![a-z])hurried|(?<![a-z])rushed",
    "performance": r"perform|(?<![a-z])success", "effort": r"(?<![a-z])effort|(?<![a-z])hard(?![a-z])",
    "frustration": r"frustrat|(?<![a-z])stress|(?<![a-z])annoy",
}
SUS_ITEM_RE = re.compile(r"^(?:sus)?[ _.-]*(?:q|item|i)?[ _.-]*0?(\d{1,2})$", re.I)
# Matrix exports number the rows after the question: Q5_1 ... Q5_10, SUS_1 ... SUS_10, "Q12 - 3".
ROW_SUFFIX_RE = re.compile(r"^(.*?)[ _.-]+0?(\d{1,2})$")
SUS_PREFIX_RE = re.compile(r"sus", re.I)


def _labels(*points):
    """Build a label map from (point, label, synonym, ...) tuples."""
    return {label: point for point, *names in points for label in names}


# Each preset is one questionnaire format: its full answer scale and every label on it (synonyms share a point).
# The instrument fixes the scale (SUS 1-5, UMUX-Lite and SEQ 1-7, unless --scale), and only presets of that
# scale are considered; see resolve_scale_and_labels.
_NEU_AGREE = ("neither agree nor disagree", "neutral")
_NEU_EASE = ("neither easy nor difficult", "neutral")
LABEL_PRESETS = {
    "agree5": {"scale": (1, 5), "map": _labels(
        (1, "strongly disagree"), (2, "disagree"), (3,) + _NEU_AGREE, (4, "agree"), (5, "strongly agree"))},
    "agree5-somewhat": {"scale": (1, 5), "map": _labels(
        (1, "strongly disagree"), (2, "somewhat disagree"), (3,) + _NEU_AGREE, (4, "somewhat agree"),
        (5, "strongly agree"))},
    "agree7": {"scale": (1, 7), "map": _labels(
        (1, "strongly disagree"), (2, "disagree"), (3, "somewhat disagree"), (4,) + _NEU_AGREE,
        (5, "somewhat agree"), (6, "agree"), (7, "strongly agree"))},
    "ease7": {"scale": (1, 7), "map": _labels(
        (1, "very difficult"), (2, "difficult"), (3, "somewhat difficult"), (4,) + _NEU_EASE,
        (5, "somewhat easy"), (6, "easy"), (7, "very easy"))},
}
INSTRUMENT_PRESETS = {"sus": ("agree5", "agree5-somewhat"), "sus-positive": ("agree5", "agree5-somewhat"),
                      "umux-lite": ("agree7", "agree5", "agree5-somewhat"), "seq": ("ease7",), "tlx": ()}
# "4 - Agree", "4 = Agree", "4. Agree", "(4) Agree", "4: Agree", "4 Agree": a number, then a separator or a
# space, then a label. "2hrs" or "1st" are not read as points.
LABELLED_RE = re.compile(r"^\s*(?:\(\s*(-?\d{1,3})\s*\)\s*|(-?\d{1,3})\s*(?:[-–—:=.)]\s*|\s+))([^\W\d_].*)$")
NON_ANSWER_RE = re.compile(
    r"^(n/?a|na|none|-+|\.|\?|don'?t know|do not know|dk|not applicable|prefer not to (say|answer)|refused|"
    r"skipped|no answer|no opinion|nan)$",
    re.I,
)
DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|", "\\t": "\t"}
DELIMITER_NAMES = {",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe"}


class InputError(Exception):
    """Bad input or a calculation the script refuses to do (exit code 2)."""


# ------------------------------------------------------------------------------------------------ statistics

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
    # Excel can save trailing empty columns: drop them when no row has anything there.
    while len(headers) > 1 and not headers[-1] and not any(
            len(r) >= len(headers) and r[len(headers) - 1].strip() for r in table[1:]):
        headers.pop()
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
    """The number in a plain numeric answer ("4", "4.0", "4,0"), else None. Python's float() also reads "0_5"
    as 5, so an underscore is refused."""
    if "_" in text:
        return None
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


def preset_value(name, text):
    return LABEL_PRESETS[name]["map"].get(text)


def read_point(raw, labels, allow_fraction=False):
    """Return (value, None) or (None, reason). Reasons: blank, non_answer, non_numeric, non_integer. A digital
    TLX slider can record 42.5 (allow_fraction); every other scale here has whole points."""
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
        return (value, None) if allow_fraction else (None, "non_integer")
    return int(value), None


# ------------------------------------------------------------------------------------------------- analysis

def detect_items(headers, instrument, items_arg):
    want = INSTRUMENTS[instrument]["items"]
    if items_arg:
        items = [c.strip() for c in items_arg.split(",") if c.strip()]
        missing = [c for c in items if c not in headers]
        if missing:
            raise InputError("--items: not columns: " + ", ".join(missing) + ". Columns: " + ", ".join(headers))
        if len(items) != want or len(set(items)) != want:
            raise InputError(f"{INSTRUMENTS[instrument]['name']} has {want} item(s); --items gave {len(items)}")
        return items, "given"
    if instrument in ("sus", "sus-positive"):
        for pool in ([h for h in headers if SUS_PREFIX_RE.search(h)], headers):
            numbered = {}
            for h in pool:
                match = SUS_ITEM_RE.match(SUS_PREFIX_RE.sub("", h) if pool is not headers else h)
                if match:  # every number, so Q1 ... Q15 or Q0 ... Q10 is not cut down to ten
                    numbered.setdefault(int(match.group(1)), []).append(h)
            if sorted(numbered) == list(range(1, 11)) and all(len(v) == 1 for v in numbered.values()):
                return [numbered[i][0] for i in range(1, 11)], "auto-detected (numbered 1 to 10)"
        groups = {}
        for h in headers:
            match = ROW_SUFFIX_RE.match(h)
            if match:
                groups.setdefault(match.group(1).lower(), {}).setdefault(int(match.group(2)), []).append(h)
        complete = [g for g in groups.values()
                    if sorted(g) == list(range(1, 11)) and all(len(v) == 1 for v in g.values())]
        if len(complete) == 1:
            return [complete[0][i][0] for i in range(1, 11)], "auto-detected (matrix rows 1 to 10)"
        raise InputError("could not find ten SUS item columns numbered 1 to 10 (e.g. sus_1 ... sus_10). Pass "
                         "--items COL1,...,COL10 in questionnaire order. Columns: " + ", ".join(headers))
    if instrument == "umux-lite":
        cap = [h for h in headers if re.search(r"capab|requirement", h, re.I)]
        ease = [h for h in headers if re.search(r"(?<![a-z])eas(e|y)", h, re.I) and h not in cap]
        if len(cap) == 1 and len(ease) == 1:
            return [cap[0], ease[0]], "auto-detected (capabilities, ease)"
        raise InputError("could not find the two UMUX-Lite items. Pass --items CAPABILITIES_COL,EASE_COL. "
                         "Columns: " + ", ".join(headers))
    if instrument == "seq":
        cands = [h for h in headers if re.search(r"\bseq\b|seq[_ ]|(?<![a-z])eas(e|y)|difficult", h, re.I)]
        if len(cands) == 1:
            return cands, "auto-detected"
        raise InputError("could not find a single SEQ column. Pass --items COL. Columns: " + ", ".join(headers))
    found = []
    for sub in TLX_SUBSCALES:
        cands = [h for h in headers if re.search(TLX_PATTERNS[sub], h, re.I) and h not in found]
        if len(cands) != 1:
            raise InputError("could not match the six NASA-TLX subscales by name. Pass --items in the order "
                             + ",".join(TLX_SUBSCALES) + ". Columns: " + ", ".join(headers))
        found.append(cands[0])
    return found, "auto-detected (mental, physical, temporal, performance, effort, frustration)"


def resolve_scale(args, instrument):
    default = INSTRUMENTS[instrument]["scale"]
    if not args.scale:
        return default
    scale = parse_scale(args.scale)
    if instrument.startswith("sus") and scale != (1, 5):
        raise InputError("SUS is scored on its 1-5 scale only. A 7-point or 0-10 version is not the SUS, and the "
                         "published benchmarks do not apply to it.")
    return scale


def score_row(instrument, values, scale, reverse_performance, seq_reversed=False):
    low, high = scale
    if instrument == "sus":
        contributions = [(v - 1) if i % 2 == 0 else (5 - v) for i, v in enumerate(values)]
        return 2.5 * sum(contributions)
    if instrument == "sus-positive":
        return 2.5 * sum(v - 1 for v in values)
    if instrument == "umux-lite":
        return 100.0 * sum(v - low for v in values) / (2 * (high - low))
    if instrument == "seq":
        return float(low + high - values[0]) if seq_reversed else float(values[0])
    rescaled = [100.0 * (v - low) / (high - low) for v in values]
    if reverse_performance:
        rescaled[3] = 100.0 - rescaled[3]
    return sum(rescaled) / 6


def pearson(xs, ys):
    n = len(xs)
    if n < 3 or max(xs) == min(xs) or max(ys) == min(ys):  # a constant side has no correlation (and float
        return None                                           # rounding would invent one)
    mx, my = math.fsum(xs) / n, math.fsum(ys) / n
    sxx = math.fsum((x - mx) ** 2 for x in xs)
    syy = math.fsum((y - my) ** 2 for y in ys)
    r = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)
    return max(-1.0, min(1.0, r))


def cgs(score):
    """Curved grade and interpolated percentile for a SUS score (Sauro and Lewis 2016)."""
    score = max(0.0, min(100.0, score))
    grade = CGS[0][0]
    for g, lower, _ in CGS:
        if score >= lower - 1e-9:
            grade = g
    points = [(lower, pct) for _, lower, pct in CGS] + [(100.0, 100.0)]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= score <= x1:
            return grade, y0 + (y1 - y0) * (score - x0) / (x1 - x0)
    return grade, 100.0


def adjective(score):
    """The Bangor et al. (2009) adjective whose mean SUS is closest to the score (this skill's rule)."""
    return min(ADJECTIVES, key=lambda a: abs(a[1] - score))[0]


def summarize(label, scores, confidence, min_base, bounds, instrument, seven_point=True):
    n = len(scores)
    out = {"label": label, "n": n, "small_base": n < min_base}
    if n == 0:
        out["note"] = "no scored participants"
        return out
    mean, sd = mean_sd(scores)
    ordered = sorted(scores)
    mid = n // 2
    out.update({"mean": mean, "sd": sd, "min": ordered[0], "max": ordered[-1],
                "median": ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2})
    if sd is None:
        out["note"] = "one participant: no interval"
    elif sd == 0:
        out["ci"] = [mean, mean]
        out["note"] = "every participant has the same score: the interval has zero width"
    else:
        half = t_critical(confidence, n - 1) * sd / math.sqrt(n)
        out["ci"] = [max(bounds[0], mean - half), min(bounds[1], mean + half)]
        out["ci_half_width"] = half
    if instrument in ("sus", "sus-positive", "umux-lite"):
        # Raw UMUX-Lite is read on the SUS benchmarks directly, as its author now recommends (sources.md).
        add_benchmarks(out, mean, out.get("ci"))
    if instrument == "umux-lite" and seven_point:
        # Historical regression (Lewis, Utesch and Maher 2013), secondary. Its interval is the transformed
        # interval of the mean: it carries no prediction or calibration error.
        out["sus_equivalent"] = UMUX_LITE_SLOPE * mean + UMUX_LITE_INTERCEPT
        if out.get("ci"):
            out["sus_equivalent_ci"] = [UMUX_LITE_SLOPE * c + UMUX_LITE_INTERCEPT for c in out["ci"]]
        bench = {}
        add_benchmarks(bench, out["sus_equivalent"], out.get("sus_equivalent_ci"))
        out["sus_equivalent_benchmarks"] = bench
    return out


def add_benchmarks(out, mean, ci):
    grade, percentile = cgs(mean)
    out.update({"grade": grade, "percentile": percentile, "adjective": adjective(mean)})
    out["grade_adjective_differ"] = out["adjective"] not in GRADE_ADJECTIVES[grade[0]]
    if ci:
        out["grade_range"] = [cgs(ci[0])[0], cgs(ci[1])[0]]
        out["percentile_range"] = [cgs(ci[0])[1], cgs(ci[1])[1]]


def apply_tail(out, tail, confidence):
    """One-sided comparison of A minus B: "above" asks whether A is higher, "below" whether A is lower. The p
    value is one-sided and the interval becomes the matching one-sided bound at the same confidence."""
    out["tail"] = tail
    if tail == "two" or not out.get("tested"):
        return
    upper = out["p_value"] / 2 if out["t"] > 0 else 1 - out["p_value"] / 2
    out["p_value"] = upper if tail == "above" else 1 - upper
    half = t_critical(2 * confidence - 1, out["df"]) * out["se"]
    out["ci"] = [out["difference"] - half, None] if tail == "above" else [None, out["difference"] + half]


def set_verdict(result, alpha, small):
    """significant / not significant. A small base is flagged, not turned into a power claim: power depends on
    the effect size, so a non-significant result says only that the interval includes no difference."""
    p_value = result.get("p_adjusted", result["p_value"])
    result["significant"] = p_value < alpha
    result["verdict"] = "significant" if result["significant"] else "not significant"
    result["small_base"] = bool(small)


def welch(a_label, b_label, a, b, confidence, min_base):
    out = {"kind": "independent", "a": a_label, "b": b_label, "n_a": len(a), "n_b": len(b), "test": "Welch t"}
    if len(a) < 2 or len(b) < 2:
        out.update({"tested": False, "note": "each side needs at least 2 participants"})
        return out
    (ma, sa), (mb, sb) = mean_sd(a), mean_sd(b)
    va, vb = sa * sa / len(a), sb * sb / len(b)
    out["difference"] = ma - mb
    if va + vb == 0:
        out.update({"tested": False, "note": "no variation in either group: the test is undefined"})
        return out
    se = math.sqrt(va + vb)
    df = (va + vb) ** 2 / (va * va / (len(a) - 1) + vb * vb / (len(b) - 1))
    t_stat = out["difference"] / se
    half = t_critical(confidence, df) * se
    out.update({"t": t_stat, "df": df, "p_value": t_two_sided_p(t_stat, df), "se": se,
                "ci": [out["difference"] - half, out["difference"] + half], "tested": True})
    set_verdict(out, 1 - confidence, len(a) < min_base or len(b) < min_base)
    return out


def paired(a_label, b_label, a_by_id, b_by_id, confidence, min_base, blank_ids=(0, 0)):
    """Paired t on participants with an id in both groups. Rows without an id are never paired."""
    ids = sorted(set(a_by_id) & set(b_by_id))
    diffs = [a_by_id[i] - b_by_id[i] for i in ids]
    out = {"kind": "paired", "a": a_label, "b": b_label, "pairs": len(ids), "test": "paired t",
           "only_in_a": len(set(a_by_id) - set(b_by_id)), "only_in_b": len(set(b_by_id) - set(a_by_id)),
           "no_id_a": blank_ids[0], "no_id_b": blank_ids[1]}
    if len(diffs) < 2:
        out.update({"tested": False, "note": "fewer than 2 participants rated both"})
        return out
    mean, sd = mean_sd(diffs)
    out["difference"] = mean
    if sd == 0:
        out.update({"tested": False, "note": "every participant has the same difference: the test is undefined"})
        return out
    se = sd / math.sqrt(len(diffs))
    df = len(diffs) - 1
    t_stat = mean / se
    half = t_critical(confidence, df) * se
    out.update({"t": t_stat, "df": df, "p_value": t_two_sided_p(t_stat, df), "se": se, "sd_difference": sd,
                "ci": [mean - half, mean + half], "tested": True})
    set_verdict(out, 1 - confidence, len(diffs) < min_base)
    return out


def target_test(group, target, tail, confidence, min_base):
    out = {"label": group["label"], "target": target, "tail": tail, "n": group["n"], "kind": "target"}
    if group.get("pooled_paired"):
        out.update({"tested": False, "note": "pooled over designs in a paired study (each participant counted "
                                             "once per design): test each design instead"})
        return out
    if group.get("pooled_across_groups"):
        out.update({"tested": False, "note": "pooled across the groups, a mix of designs: test each group instead"})
        return out
    if group["n"] < 2 or not group.get("sd"):
        out.update({"tested": False, "note": "needs at least 2 participants whose scores differ"})
        return out
    se = group["sd"] / math.sqrt(group["n"])
    t_stat = (group["mean"] - target) / se
    two = t_two_sided_p(t_stat, group["n"] - 1)
    upper = two / 2 if t_stat > 0 else 1 - two / 2
    out.update({"difference": group["mean"] - target, "t": t_stat, "df": group["n"] - 1, "tested": True,
                "p_value": {"two": two, "above": upper, "below": 1 - upper}[tail]})
    set_verdict(out, 1 - confidence, group["n"] < min_base)
    return out


def holm(comparisons, method, alpha, min_base):
    """Holm or Bonferroni over one family of tests (the comparisons, or the target tests)."""
    tested = [c for c in comparisons if c.get("tested")]
    m = len(tested)
    for c in tested:
        c["family_size"] = m
    if method == "none" or m < 2:
        return
    if method == "bonferroni":
        for c in tested:
            c["p_adjusted"] = min(1.0, c["p_value"] * m)
    else:
        running = 0.0
        for rank, c in enumerate(sorted(tested, key=lambda c: c["p_value"])):
            running = max(running, min(1.0, (m - rank) * c["p_value"]))
            c["p_adjusted"] = running
    for c in tested:
        c["adjustment"] = method
        small = (c.get("pairs", min(c.get("n_a", c.get("n", 0)), c.get("n_b", c.get("n", 0))))) < min_base
        set_verdict(c, alpha, small)


def same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.realpath(a) == os.path.realpath(b)


def check_agree_orientation(raw_values, scale):
    """Stop when labelled agree answers put "agree" at the low end ("1 - Strongly agree"): SUS and UMUX-Lite
    score 1 as disagree, so reading those numbers as they stand would turn an 85 into a 15."""
    ends = {scale[0]: [], scale[1]: []}
    for raw in raw_values:
        pair = labelled_number((raw or "").strip())
        if pair and pair[0] in ends:
            ends[pair[0]].append(pair[1].lower())
    agree_low = any("agree" in t and "disagree" not in t and "not" not in t.split() for t in ends[scale[0]])
    disagree_high = any("disagree" in t for t in ends[scale[1]])
    if agree_low or disagree_high:
        raise InputError(f"the answers label {scale[0]} as agree (or {scale[1]} as disagree), the reverse of the scoring "
                         f"here ({scale[1]} = strongly agree). Check the questionnaire, then recode the answers or "
                         "map every label with --labels.")


def check_seven_point_labels(raw_values, allowed):
    """Stop when the text answers fit a 7-point agree scale better than any 5-point one: a few "Somewhat agree"
    answers among "Agree" ones mean "Agree" was 6 of 7, not 4 of 5."""
    texts = text_answers(raw_values)
    if not texts:
        return

    def unread(name):
        return sum(c for t, c in texts.items() if preset_value(name, t) is None)

    if unread("agree7") < min(unread(n) for n in allowed):
        raise InputError("the text answers fit a 7-point agree scale (" + describe_presets(["agree7"]) + "). A 7-point "
                         "SUS is not the SUS and is not scored against its benchmarks.")


def check_seq_orientation(raw_values, scale, seq_reversed):
    """Stop when labelled SEQ answers put "easy" at the low end: older forms ran very easy (1) to very difficult
    (7), the current one the other way round."""
    if seq_reversed:
        return
    ends = {scale[0]: [], scale[1]: []}
    for raw in raw_values:
        pair = labelled_number((raw or "").strip())
        if pair and pair[0] in ends:
            ends[pair[0]].append(pair[1].lower())
    negated = re.compile(r"\b(?:not|no|hardly)\b")  # "Not at all easy" is the difficult end
    easy_low = any("easy" in t and "difficult" not in t and not negated.search(t) for t in ends[scale[0]])
    hard_high = any(("difficult" in t or "hard" in t) and not negated.search(t) for t in ends[scale[1]])
    if easy_low or hard_high:
        raise InputError(f"the SEQ answers label {scale[0]} as easy (or {scale[1]} as difficult), the reverse of the "
                         f"scoring here ({scale[1]} = very easy). Pass --seq-reversed to score them as "
                         f"{scale[0] + scale[1]} - x, after checking the questionnaire's anchors.")


def analyse(args):
    if args.confidence > 1:
        args.confidence /= 100
    if not math.isfinite(args.confidence) or not 0.5 <= args.confidence < 1:
        raise InputError("--confidence must be between 0.5 and 1 (for example 0.95 or 95)")
    if args.target is not None and not math.isfinite(args.target):
        raise InputError(f"--target must be a finite number; got {args.target}")
    if args.min_base < 1:
        raise InputError(f"--min-base must be 1 or more; got {args.min_base}")
    if args.max_imputed < 1:
        raise InputError(f"--max-imputed must be 1 or more; got {args.max_imputed}")
    if args.tail == "one":
        raise InputError("--tail one is ambiguous: say --tail above or --tail below (for TLX, lower is better)")
    if args.tail in ("above", "below") and args.compare and args.target is not None:
        raise InputError("--tail sets the direction of both the target tests and --compare; run them separately so "
                         "each one-sided question is stated on its own (or drop --tail for a two-sided compare)")
    if args.compare and args.pairwise:
        raise InputError("--compare and --pairwise both name the tests to run; pass one of them")
    if args.tail in ("above", "below") and not args.compare and args.target is None:
        raise InputError("--tail above/below sets the direction of --compare or --target; pass one of them")
    if args.tail in ("above", "below") and args.pairwise:
        raise InputError("--tail above/below needs a direction for each pair, which --pairwise does not set: use "
                         "--compare A B (A minus B) for the pair the hypothesis names")
    instrument = args.instrument
    for flag, allowed in (("drop_flagged", ("sus",)), ("reverse_performance", ("tlx",)), ("seq_reversed", ("seq",))):
        if getattr(args, flag) and instrument not in allowed:
            raise InputError(f"--{flag.replace('_', '-')} applies to --instrument {allowed[0]} only")
    notes, warnings = [], []
    headers, rows = read_table(args.input, args.delimiter, args.skip_rows, notes)
    for flag in ("group_col", "id_col"):
        col = getattr(args, flag)
        if col and col not in headers:
            raise InputError(f"--{flag.replace('_', '-')} {col!r} is not a column. Columns: " + ", ".join(headers))
    if args.paired and not (args.id_col and args.group_col):
        raise InputError("--paired needs --id-col (the participant) and --group-col (the design or condition)")
    items, items_source = detect_items(headers, instrument, args.items)
    if args.reverse_performance and items_source == "given":
        perf = [i for i, c in enumerate(items) if re.search(TLX_PATTERNS["performance"], c, re.I)]
        if perf and perf != [3]:
            raise InputError(f"--reverse-performance flips the fourth --items column ({items[3]!r}), but "
                             f"{items[perf[0]]!r} looks like performance. Pass --items in the order "
                             + ",".join(TLX_SUBSCALES) + ".")
    scale = resolve_scale(args, instrument)
    if instrument == "tlx" and not args.scale:
        notes.append("NASA-TLX read on 0-100. For the paper form's 21 marks pass --scale 1-21 (or 0-20).")
    if args.impute_midpoint and not instrument.startswith("sus"):
        raise InputError("--impute-midpoint follows Brooke's SUS instruction; it is not offered for other scales")
    raw = [r[c] for r in rows for c in items]
    if instrument.startswith("sus") and not args.labels:
        check_seven_point_labels(raw, INSTRUMENT_PRESETS[instrument])
    # The instrument fixes the scale; only label maps of that scale are considered (a 7-point UMUX-Lite's
    # "Strongly agree" is 7, never the 5 of a 5-point map).
    scale, scale_source, labels, label_source = resolve_scale_and_labels(
        raw, scale if args.scale else None, (scale, f"{INSTRUMENTS[instrument]['name']} scale"),
        parse_label_map(args.labels) if args.labels else None, INSTRUMENT_PRESETS[instrument], {})
    if labels and label_source != "given":
        notes.append(label_map_note(labels, label_source))
    labelled = labelled_numbers_note(raw)
    if labelled:
        notes.append(labelled)
    if instrument == "seq":
        if args.seq_reversed and label_source == "ease7":
            raise InputError("the SEQ answers are text labels (\"Very easy\" ... \"Very difficult\"), which name their "
                             "own end; --seq-reversed would invert them. Drop --seq-reversed.")
        check_seq_orientation(raw, scale, args.seq_reversed)
    elif not args.labels:
        check_agree_orientation(raw, scale)
    excluded = {}
    unread = non_blank = 0
    records = []
    imputed = 0
    for row in rows:
        values, problem, missing = [], None, 0
        for col in items:
            value, reason = read_point(row[col], labels, instrument == "tlx")
            if reason is None and not scale[0] <= value <= scale[1]:
                reason = "out_of_range"
                if instrument.startswith("sus") and scale[1] < value <= 10 and not args.allow_unreadable:
                    raise InputError(
                        f"a SUS answer of {value:g} (column {col!r}): the SUS has 5 points, so this looks like a "
                        "7-point or 0-10 version, which is not the SUS and is not scored against its benchmarks. "
                        "Pass --allow-unreadable only if these few answers are typos.")
            if reason in ("blank", "non_answer"):
                missing += 1
                values.append(None)
                continue
            non_blank += 1
            if reason:
                unread += 1
                problem = problem or reason
                values.append(None)
                continue
            values.append(value)
        if problem:
            excluded[problem] = excluded.get(problem, 0) + 1
            continue
        if missing == len(items):
            excluded["blank"] = excluded.get("blank", 0) + 1
            continue
        if missing:
            if args.impute_midpoint and missing <= args.max_imputed:
                values = [3 if v is None else v for v in values]
                imputed += 1
            else:
                excluded["incomplete"] = excluded.get("incomplete", 0) + 1
                continue
        record = {"values": values, "imputed": missing,
                  "score": score_row(instrument, values, scale, args.reverse_performance, args.seq_reversed)}
        if args.group_col:
            record["group"] = row[args.group_col].strip() or "(blank)"
        if args.id_col:
            record["id"] = row[args.id_col].strip()
        records.append(record)
    if non_blank and unread / non_blank > NON_READ_STOP_SHARE and not args.allow_unreadable:
        raise InputError(
            f"{unread} of {non_blank} non-blank item answers ({100 * unread / non_blank:.1f}%) could not be read on the "
            f"{scale[0]}-{scale[1]} scale. Check --items, --scale and --labels (a 7-point or 0-10 SUS is not the SUS); "
            "pass --allow-unreadable only if these participants really are unusable."
        )
    if not records:
        raise InputError("no participant could be scored: " +
                         (", ".join(f"{k} {v}" for k, v in sorted(excluded.items())) or "the file has no rows"))
    if excluded.get("incomplete"):
        notes.append(f"{excluded['incomplete']} participant(s) with skipped items were not scored" +
                     (f" (more than {args.max_imputed} skipped)." if args.impute_midpoint else
                      ". --impute-midpoint scores one skipped item as 3 (Brooke's centre-point instruction)."))

    checks = {}
    if instrument in ("sus", "sus-positive"):
        odd = [sum(r["values"][0::2]) / 5 for r in records]
        even = [sum(r["values"][1::2]) / 5 for r in records]
        r_oe = pearson(odd, even)
        checks["odd_even_correlation"] = r_oe
        if instrument == "sus":
            flagged = [i for i, (o, e) in enumerate(zip(odd, even)) if (o >= 4 and e >= 4) or (o <= 2 and e <= 2)]
            checks["agree_with_both_tones"] = len(flagged)
            checks["straight_lined"] = sum(1 for r in records if len(set(r["values"])) == 1)
            if r_oe is not None and len(records) >= 10 and r_oe > 0.1:
                warnings.append(
                    f"Odd and even items move together (r = {r_oe:.2f}); in the standard SUS they should move in "
                    "opposite directions. The data may be the all-positive version, or the even items may already "
                    "be reversed. Check the questionnaire; if every item was positively worded, rerun with "
                    "--instrument sus-positive."
                )
            if flagged:
                warnings.append(
                    f"{len(flagged)} participant(s) agreed (or disagreed) with both the positive and the negative "
                    "items, a sign of misreading the alternating wording. " +
                    ("They were removed (--drop-flagged); report the result with them kept as well." if args.drop_flagged
                     else "They are kept; --drop-flagged removes them.")
                )
                if args.drop_flagged:
                    keep = set(range(len(records))) - set(flagged)
                    records = [r for i, r in enumerate(records) if i in keep]
                    excluded["flagged_inconsistent"] = len(flagged)
                    if not records:
                        raise InputError("every participant was flagged; nothing left to score")
        elif r_oe is not None and len(records) >= 10 and r_oe < -0.1:
            warnings.append(
                f"Odd and even items move in opposite directions (r = {r_oe:.2f}), as in the standard alternating "
                "SUS. If items 2, 4, 6, 8 and 10 were negatively worded, rerun with --instrument sus."
            )
    imputed = sum(1 for r in records if r["imputed"])  # after --drop-flagged, so it counts scored rows only
    if imputed:
        notes.append(f"{imputed} participant(s) with up to {args.max_imputed} skipped SUS item(s) scored with the "
                     "midpoint (3) for those items. Brooke (1996) gave that as an instruction to respondents; "
                     "applying it afterwards is this skill's option, so the complete-case result is shown too.")
    bounds = (0.0, 100.0) if instrument != "seq" else scale
    seven_point = scale[1] - scale[0] + 1 == 7
    if instrument == "umux-lite" and not seven_point:
        notes.append("The UMUX-Lite to SUS regression (0.65 x + 22.9) was fitted on the 7-point version, so it is "
                     "not applied to this scale; the raw score is read on the SUS benchmarks.")
    overall = summarize("Overall", [r["score"] for r in records], args.confidence, args.min_base, bounds, instrument,
                        seven_point)
    if args.paired:
        # Each participant appears once per design, so the rows are not independent: describe, do not infer.
        for key in ("ci", "ci_half_width", "grade_range", "percentile_range", "sus_equivalent_ci"):
            overall.pop(key, None)
        overall.get("sus_equivalent_benchmarks", {}).pop("grade_range", None)
        overall.get("sus_equivalent_benchmarks", {}).pop("percentile_range", None)
        overall["pooled_paired"] = True
        overall["note"] = "pooled over designs, each participant once per design: no interval or test"
    if args.group_col:
        # A grade describes one product's mean; the pooled line mixes the designs, so it is described, not graded.
        overall["label"] = (f"All rows (pooled across the {args.group_col} groups)" if args.paired else
                            f"All participants (pooled across the {args.group_col} groups)")
        overall["pooled_across_groups"] = True
        for key in ("grade", "grade_range", "percentile", "percentile_range", "adjective", "grade_adjective_differ",
                    "sus_equivalent_benchmarks"):
            overall.pop(key, None)
    result = {
        "tool": "ux-scale-scoring", "version": VERSION, "instrument": instrument,
        "instrument_name": INSTRUMENTS[instrument]["name"],
        "input": {"source": args.input, "items": items, "items_source": items_source, "rows_read": len(rows),
                  "scored": len(records), "excluded": excluded, "imputed_midpoint": imputed},
        "scale": {"min": scale[0], "max": scale[1], "source": scale_source, "score_range": list(bounds),
                  "higher_is_better": INSTRUMENTS[instrument]["higher_is_better"]},
        "conventions": {"adjective": "closest Bangor et al. (2009) adjective mean",
                        "percentile": "linear interpolation between the curved grading scale's grade boundaries"},
        "confidence": args.confidence,
        "overall": overall,
        "checks": checks,
    }
    if labels:
        result["input"]["labels"] = {"source": label_source, "map": labels}
    if instrument == "tlx":
        result["scale"]["tlx_performance"] = ("reversed: asked with high = good, scored 100 - x" if args.reverse_performance
                                              else "as on the official form: 0 = perfect, 100 = failure")
    if instrument == "seq":
        result["scale"]["seq_orientation"] = ("reversed export: scored as min + max - x" if args.seq_reversed
                                              else f"{scale[1]} = very easy")
    if imputed:
        complete = [r["score"] for r in records if not r["imputed"]]
        result["complete_case"] = {"n": len(complete), "mean": mean_sd(complete)[0] if complete else None}
    comparisons, groups = [], {}
    if args.group_col:
        names = sorted({r["group"] for r in records})
        groups = {n: [r for r in records if r["group"] == n] for n in names}
        result["groups"] = [summarize(n, [r["score"] for r in groups[n]], args.confidence, args.min_base, bounds,
                                      instrument, seven_point) for n in names]
        if len(names) == 1:
            warnings.append(f"Only one group ({names[0]}) has scores; nothing to compare.")
        pairs = []
        if args.compare:
            for name in args.compare:
                if name not in groups:
                    raise InputError(f"--compare: group {name!r} not found. Groups: " + ", ".join(names))
            if args.compare[0] == args.compare[1]:
                raise InputError("--compare names the same group twice")
            pairs = [tuple(args.compare)]
        elif args.pairwise:
            # Rows with no group are summarised but not tested: they are not a group anyone asked about.
            real = [n for n in names if n != "(blank)"]
            pairs = [(a, b) for i, a in enumerate(real) for b in real[i + 1:]]
            if len(real) < len(names):
                notes.append("Rows with a blank group are shown as '(blank)' and left out of --pairwise.")
        tail = args.tail or "two"

        def run_pair(a, b, keep, warn):
            """One comparison on the records `keep` accepts; `warn` adds the data warnings (first run only)."""
            ga, gb = ([r for r in groups[name] if keep(r)] for name in (a, b))
            if args.paired:
                by_id, blanks = [], []
                for name, members in ((a, ga), (b, gb)):
                    ids = [r["id"] for r in members if r["id"]]
                    dupes = sorted({i for i in ids if ids.count(i) > 1})
                    if dupes:
                        raise InputError(f"group {name!r} has more than one row for id(s) {', '.join(dupes[:5])}; "
                                         "a paired test needs one score per participant per group")
                    by_id.append({r["id"]: r["score"] for r in members if r["id"]})
                    blanks.append(sum(1 for r in members if not r["id"]))
                if any(blanks) and warn:
                    warnings.append(f"{sum(blanks)} row(s) in {a} or {b} have no participant id; they cannot be "
                                    "paired and are left out of the paired test.")
                out = paired(a, b, by_id[0], by_id[1], args.confidence, args.min_base, tuple(blanks))
            else:
                if args.id_col and warn:
                    shared = {r["id"] for r in ga if r["id"]} & {r["id"] for r in gb if r["id"]}
                    if shared:
                        warnings.append(f"{len(shared)} participant(s) appear in both {a} and {b}; the independent "
                                        "test assumes different people. Use --paired for a within-subjects study.")
                out = welch(a, b, [r["score"] for r in ga], [r["score"] for r in gb], args.confidence, args.min_base)
            apply_tail(out, tail, args.confidence)
            if out.get("tested"):
                set_verdict(out, 1 - args.confidence, out["small_base"])
            return out

        for a, b in pairs:
            comparisons.append(run_pair(a, b, lambda r: True, True))
        if args.paired:
            notes.append("The pooled line counts each participant once per group; it has no "
                         "interval or target test. Report the groups and the paired difference.")
        holm(comparisons, args.adjust, 1 - args.confidence, args.min_base)
        if imputed:
            # The same tests on participants who answered every item, as the sensitivity check beside the imputed
            # result (its own adjustment family).
            complete_cases = [run_pair(a, b, lambda r: not r["imputed"], False) for a, b in pairs]
            holm(complete_cases, args.adjust, 1 - args.confidence, args.min_base)
            for c, cc in zip(comparisons, complete_cases):
                c["complete_case"] = cc
            for g in result["groups"]:
                complete = [r["score"] for r in groups[g["label"]] if not r["imputed"]]
                g["complete_case"] = {"n": len(complete), "mean": mean_sd(complete)[0] if complete else None}
        tested = [c for c in comparisons if c.get("tested")]
        if len(tested) > 1 and args.adjust == "none":
            warnings.append(f"{len(tested)} tests were run without a multiple-comparison adjustment; pass --adjust holm.")
        if comparisons:
            result["comparisons"] = comparisons
    elif args.compare or args.pairwise:
        raise InputError("--compare and --pairwise need --group-col")
    if args.target is not None:
        tail = args.tail or "two"
        targets = [target_test(overall, args.target, tail, args.confidence, args.min_base)]
        # Rows with no group are summarised but not tested, as in --pairwise.
        targets += [target_test(g, args.target, tail, args.confidence, args.min_base) for g in result.get("groups", [])
                    if g["label"] != "(blank)"]
        holm(targets, args.adjust, 1 - args.confidence, args.min_base)  # the target tests are their own family
        if args.adjust == "none" and sum(1 for t in targets if t.get("tested")) > 1:
            warnings.append(f"{sum(1 for t in targets if t.get('tested'))} target tests were run without a "
                            "multiple-comparison adjustment; pass --adjust holm, or report the number of tests.")
        result["target"] = targets
    every = [overall] + result.get("groups", [])
    single = [g["label"] for g in every if g["n"] == 1]
    small = [g["label"] for g in every if g["n"] > 1 and g["small_base"]]
    if small:
        warnings.append(f"Small base (under {args.min_base} participants): {', '.join(small)}. Report the interval "
                        "and call the result directional; a result that is not significant there says little.")
    if single:
        warnings.append(f"One participant: {', '.join(single)}. Report the score alone: one rating has no interval and "
                        "no test, and says nothing about users in general.")
    differ = [g for g in every if g.get("grade_adjective_differ")]
    if differ:
        notes.append("Grade and adjective disagree for " + ", ".join(
            f"{g['label']} (grade {g['grade']}, adjective {g['adjective']!r})" for g in differ) +
            ": they come from different published schemes (curved grades, Sauro and Lewis 2016; adjective means, "
            "Bangor et al. 2009) and part ways near their boundaries. Report both with their sources, or the grade "
            "alone.")
    if args.scores_out:
        if same_file(args.scores_out, args.input):
            raise InputError("--scores-out points at the input file; choose another path")
        regression = instrument == "umux-lite" and seven_point
        try:
            os.makedirs(os.path.dirname(os.path.abspath(args.scores_out)), exist_ok=True)
            with open(args.scores_out, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "group", "score", "items_imputed"] + (["sus_equivalent"] if regression else []))
                for r in records:
                    extra = [UMUX_LITE_SLOPE * r["score"] + UMUX_LITE_INTERCEPT] if regression else []
                    writer.writerow([r.get("id", ""), r.get("group", ""), r["score"], r["imputed"]] + extra)
        except OSError as exc:
            raise InputError(f"cannot write {args.scores_out}: {exc.strerror or exc}")
        result["input"]["scores_written_to"] = args.scores_out
    result["notes"] = notes
    result["warnings"] = warnings
    return result


# ------------------------------------------------------------------------------------------------ rendering

def fmt_p(p_value):
    return "< 0.0001" if p_value < 0.0001 else f"= {p_value:.4f}"


def group_line(g, instrument):
    if not g["n"]:
        return f"{g['label']}: no scored participants"
    digits = 2 if instrument == "seq" else 1
    text = f"{g['label']}: n = {g['n']}{' [small base]' if g['small_base'] else ''}; mean {g['mean']:.{digits}f}"
    if g.get("ci"):
        text += f" ({g['ci'][0]:.{digits}f} to {g['ci'][1]:.{digits}f})"
    if g.get("sd") is not None:
        text += f"; SD {g['sd']:.{digits}f}"
    text += f"; median {g['median']:.{digits}f}"
    if "grade" in g:
        on = " on the SUS scale" if instrument == "umux-lite" else ""
        text += (f"; grade{on} {g['grade']}" + (f" ({g['grade_range'][0]} to {g['grade_range'][1]})"
                                                 if g.get("grade_range") else "") +
                 f", percentile ~{g['percentile']:.0f} (interpolated), closest Bangor adjective {g['adjective']!r}")
    if "sus_equivalent" in g:
        b = g["sus_equivalent_benchmarks"]
        text += f"; regression SUS-equivalent (0.65 x + 22.9, secondary) {g['sus_equivalent']:.1f}"
        if g.get("sus_equivalent_ci"):
            text += f" ({g['sus_equivalent_ci'][0]:.1f} to {g['sus_equivalent_ci'][1]:.1f})"
        text += f", grade {b['grade']}"
    if g.get("note"):
        text += f" [{g['note']}]"
    return text


def comparison_text(c):
    if not c.get("tested"):
        return c.get("note", "not tested")
    verdict = c["verdict"]
    if not c["significant"] and c.get("small_base"):
        verdict += " (small base: a real difference may have been missed)"
    p_text = f"p {fmt_p(c['p_value'])}" + (f", {c['adjustment']}-adjusted p {fmt_p(c['p_adjusted'])} over "
                                             f"{c['family_size']} tests" if "p_adjusted" in c else "")
    low, high = c["ci"]
    interval = (f"lower bound {low:+.2f}" if high is None else f"upper bound {high:+.2f}" if low is None
                else f"{low:+.2f} to {high:+.2f}")
    return (f"{c['difference']:+.2f} ({interval}), t = {c['t']:.3f}, df = {c['df']:.1f}, {p_text}: {verdict}")


def render(result):
    inst = result["instrument"]
    inp = result["input"]
    level = f"{round(100 * result['confidence'], 4):g}%"
    sc = result["scale"]
    lines = [f"{result['instrument_name']}: items {', '.join(inp['items'])} ({inp['items_source']}); answers "
             f"{sc['min']}-{sc['max']} ({sc['source']}); scores {sc['score_range'][0]:g}-"
             f"{sc['score_range'][1]:g}, {'higher' if sc['higher_is_better'] else 'lower'} is better" +
             (f"; TLX performance {sc['tlx_performance']}" if "tlx_performance" in sc else "") +
             (f"; SEQ {sc['seq_orientation']}" if "seq_orientation" in sc else "") + "."]
    ex = inp["excluded"]
    lines.append(f"Data: {inp['source']}. Rows {inp['rows_read']}, scored {inp['scored']}, excluded {sum(ex.values())}"
                 + (f" ({', '.join(f'{k} {v}' for k, v in sorted(ex.items()))})" if ex else "") + ".")
    lines.append(f"Intervals: {level} t intervals on the mean.")
    lines.append("")
    lines.append(group_line(result["overall"], inst))
    if result.get("complete_case"):
        cc = result["complete_case"]
        lines.append(f"  Complete cases only (no imputed items): n = {cc['n']}" +
                     (f", mean {cc['mean']:.1f}" if cc["mean"] is not None else ""))
    if result.get("groups"):
        lines += ["", "By group:"]
        for g in result["groups"]:
            lines.append("  " + group_line(g, inst))
            cc = g.get("complete_case")
            if cc:
                lines.append(f"    Complete cases only: n = {cc['n']}" +
                             (f", mean {cc['mean']:.1f}" if cc["mean"] is not None else ""))
    if result.get("comparisons"):
        lines += ["", "Comparisons (A minus B):"]
        for c in result["comparisons"]:
            head = f"  {c['a']} vs {c['b']} ({c['test']}" + (f", {c['pairs']} pairs" if c["kind"] == "paired" else "") + \
                (f", one-tailed: is {c['a']} {c['tail']} {c['b']}?" if c.get("tail", "two") != "two" else "") + "): "
            lines.append(head + comparison_text(c))
            if c.get("complete_case"):
                lines.append("    Complete cases only: " + comparison_text(c["complete_case"]))
    for t in result.get("target", []):
        if t.get("tested"):
            tail = "two-tailed" if t["tail"] == "two" else f"one-tailed, {t['tail']}"
            p_text = f"p {fmt_p(t['p_value'])}" + (f", {t['adjustment']}-adjusted p {fmt_p(t['p_adjusted'])}"
                                                   if "p_adjusted" in t else "")
            lines.append(f"{t['label']} vs target {t['target']:g} ({tail} t): difference "
                         f"{t['difference']:+.2f}, t = {t['t']:.3f}, {p_text} -> {t['verdict']}")
        else:
            lines.append(f"{t['label']} vs target {t['target']:g}: {t['note']}")
    if inp.get("scores_written_to"):
        lines.append(f"Scores written to {inp['scores_written_to']}")
    checks = result.get("checks") or {}
    if checks:
        parts = []
        if checks.get("odd_even_correlation") is not None:
            parts.append(f"odd/even item correlation {checks['odd_even_correlation']:.2f}")
        if "agree_with_both_tones" in checks:
            parts.append(f"agreed with both tones {checks['agree_with_both_tones']}")
            parts.append(f"straight-lined {checks['straight_lined']}")
        if parts:
            lines += ["", "SUS checks: " + "; ".join(parts)]
    for title, key in (("Notes", "notes"), ("Warnings", "warnings")):
        if result.get(key):
            lines += ["", title + ":"] + [f"  - {w}" for w in result[key]]
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------------- CLI

def build_parser():
    parser = argparse.ArgumentParser(
        description="Score SUS, UMUX-Lite, SEQ or raw NASA-TLX with intervals, benchmarks and comparisons.",
        epilog="Example: python3 scripts/ux_scale_scoring.py sus.csv --instrument sus --group-col design "
               "--compare A B --json",
    )
    parser.add_argument("input", help="CSV with one row per participant (any delimiter, UTF-8 or UTF-16)")
    parser.add_argument("--instrument", required=True, choices=sorted(INSTRUMENTS),
                        help="sus, sus-positive, umux-lite, seq or tlx")
    parser.add_argument("--items", metavar="COL,...", help="item columns in questionnaire order (default: detected)")
    parser.add_argument("--scale", metavar="MIN-MAX", help="answer scale when not the default (UMUX-Lite 1-5, "
                        "TLX 1-21 or 0-20); SUS is always 1-5")
    parser.add_argument("--labels", metavar="LABEL=N,...", help="map text answers to points (within the scale)")
    parser.add_argument("--group-col", help="column with the design, product, task or condition")
    parser.add_argument("--id-col", help="participant id column (needed for --paired)")
    parser.add_argument("--compare", nargs=2, metavar=("A", "B"), help="test two groups")
    parser.add_argument("--pairwise", action="store_true", help="test every pair of groups")
    parser.add_argument("--paired", action="store_true", help="same participants rated both groups (paired t)")
    parser.add_argument("--adjust", choices=["none", "holm", "bonferroni"], default="none",
                        help="multiple-comparison adjustment (default none, warns when several tests run)")
    parser.add_argument("--target", type=float, help="test each mean against this score (e.g. 68 for SUS)")
    parser.add_argument("--tail", choices=["two", "above", "below", "one"], help="direction of the target tests or "
                        "of --compare (A minus B): two (default), above or below; decide it before seeing the data")
    parser.add_argument("--impute-midpoint", action="store_true",
                        help="SUS only: score a skipped item as 3 (Brooke's centre-point instruction), for participants "
                        "who skipped at most --max-imputed items; default excludes them")
    parser.add_argument("--max-imputed", type=int, default=DEFAULT_MAX_IMPUTED,
                        help=f"most skipped SUS items filled per participant with --impute-midpoint (default "
                        f"{DEFAULT_MAX_IMPUTED})")
    parser.add_argument("--drop-flagged", action="store_true",
                        help="SUS only: exclude participants who agreed (or disagreed) with both item tones")
    parser.add_argument("--reverse-performance", action="store_true",
                        help="TLX only: the performance item was asked with high = good; reverse it")
    parser.add_argument("--seq-reversed", action="store_true",
                        help="SEQ only: the export codes 1 = very easy; score as min + max - x")
    parser.add_argument("--scores-out", metavar="PATH", help="write one score per participant to a CSV")
    parser.add_argument("--confidence", type=float, default=0.95, help="confidence level, 0.95 or 95 (default 0.95)")
    parser.add_argument("--min-base", type=int, default=DEFAULT_MIN_BASE,
                        help=f"flag groups with fewer participants as a small base (default {DEFAULT_MIN_BASE})")
    parser.add_argument("--delimiter", help="CSV delimiter: a character or comma, semicolon, tab, pipe (default sniffed)")
    parser.add_argument("--skip-rows", type=int, help="rows under the header to skip (Qualtrics is detected)")
    parser.add_argument("--allow-unreadable", action="store_true",
                        help="go on when more than 5%% of item answers cannot be read (those participants are excluded)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON (full precision)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = analyse(args)
    except InputError as exc:
        print(f"ux-scale-scoring: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
