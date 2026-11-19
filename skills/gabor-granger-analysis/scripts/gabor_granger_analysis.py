#!/usr/bin/env python3
"""Gabor-Granger analysis: take rate at each tested price, a monotone demand curve, revenue and profit
curves, arc elasticity and the revenue- (or profit-) maximizing price with a bootstrap check.

Standard library only, Python 3.9+. No network. Deterministic for a given --seed.
Formulas, thresholds and citations: references/sources.md.

Usage:
  python3 scripts/gabor_granger_analysis.py answers.csv                       # wide: one column per price
  python3 scripts/gabor_granger_analysis.py answers.csv --intent-scale 5,4,3,2,1
  python3 scripts/gabor_granger_analysis.py answers.csv --price-cols "q1=9.99,q2=14.99,q3=19.99"
  python3 scripts/gabor_granger_analysis.py answers.csv --long --price-col price --answer-col buy --id-col rid
  python3 scripts/gabor_granger_analysis.py answers.csv --max-price-col wtp --prices 10,15,20,25,30
  python3 scripts/gabor_granger_analysis.py --counts 10:190,15:164,20:118,25:74,30:36 --base 200 --counts-sample same
  python3 scripts/gabor_granger_analysis.py answers.csv --unit-cost 6 --segment plan --json

Input shapes:
  wide       one row per respondent, one column per price (found from headers such as "$10", "price_10",
             "p10", or Qualtrics question text ending in a price; else --price-cols). A blank cell means the
             price was not asked (adaptive ladder) or not answered.
  long       one row per respondent x price (--long --price-col --answer-col, optional --id-col; without
             an id every row is its own respondent, i.e. a monadic test).
  max-price  one row per respondent with the highest ladder price they would buy at (--max-price-col and
             --prices); "none" means no ladder price.
  counts     --counts PRICE:BUYERS[/N],... (with --base N when every price has the same base) and
             --counts-sample same (one group answered every price) or separate (a new sample per price).
             Separate pairs with ";" when a number has a thousands separator ("1,299:40;1,499:31").

Answers: yes/no, 1/0, true/false, or a purchase-intent scale. Intent labels ("Definitely would buy" ...
"Definitely would not buy", "Very likely" ... "Very unlikely") are read by their words; numeric scale codes
need --intent-scale (codes listed from "definitely would buy" down). "Would buy" = top-2 box by default
(--buy-box 1 for top box); --intent-weights replaces it with a calibrated purchase probability per point.
A 7-point or unipolar likelihood scale ("Extremely likely" ... "Slightly likely") is not read by words: list its
labels highest first with --intent-scale "A|B|C|...". Two codes (1 = yes, 2 = no) are read with --intent-scale 1,2.

Exit codes: 0 success; 2 bad input or a refused calculation (the message says what to fix).
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

VERSION = "0.1.2"

# Thresholds and defaults. Each is listed with its source in references/sources.md.
SMALL_BASE = 100  # Pew Research Center subgroup reporting rule (margin of error above 10 points below 100)
MIN_N_FOR_OPTIMUM = 10  # convention of this skill: below 10 answers at any price, no optimal price is named
UNREADABLE_STOP_SHARE = 0.05  # stop when more than 5% of non-blank answers cannot be read
DEFAULT_BOOTSTRAP = 1000  # percentile-interval convention (Efron and Tibshirani 1993)
DEFAULT_SEED = 20261119  # arbitrary fixed default so runs repeat
TIE_TOLERANCE = 1e-9  # relative: objective values this close are reported as a tie

DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|", "\\t": "\t"}
DELIMITER_NAMES = {",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe"}
YES = {"yes", "y", "true", "t", "buy", "would buy", "i would buy", "1", "1.0"}
NO = {"no", "n", "false", "f", "would not buy", "wouldn't buy", "i would not buy", "i wouldn't buy", "not buy",
      "will not buy", "won't buy", "0", "0.0"}
NONE_TOKENS = {"none", "no price", "none of these", "would not buy at any price", "never", "not at any price"}
NON_ANSWER_RE = re.compile(
    r"^(n/?a|na|-+|\.|\?|don'?t know|do not know|dk|not applicable|prefer not to (say|answer)|refused|"
    r"skipped|no answer|not asked)$", re.I)
CURRENCY = "$€£¥₹"
CURRENCY_CODES = r"usd|eur|gbp|cad|aud|nzd|chf|jpy|inr"
CURRENCY_PREFIX = r"(?:[a-z]{1,2}\$|[" + CURRENCY + r"]|(?:" + CURRENCY_CODES + r")\s*)"
NUMBER = r"(\d{1,3}(?:[.,\u00a0\u202f ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
PRICE_HEADER_RE = re.compile(
    r"^(?:(?P<prefix>price|p|at|buy[ _-]?at|wtp|gg|pp)[ _\-:@]*)?(?P<cur>" + CURRENCY_PREFIX + r")?\s*"
    + NUMBER.replace("(", "(?P<num>", 1) + r"\s*(?P<suf>[" + CURRENCY + r"]|" + CURRENCY_CODES + r")?$", re.I)
PRICE_IN_TEXT_RE = re.compile(CURRENCY_PREFIX + r"\s*" + NUMBER + r"|" + NUMBER + r"\s*(?:(?:"
                              + CURRENCY_CODES + r")\b|[" + CURRENCY + r"])", re.I)
APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u00b4": "'", "`": "'",
                             "\u00a0": " ", "\u202f": " "})


def norm_text(text):
    """Lower case, straight apostrophes, single spaces: one spelling for every answer comparison."""
    return re.sub(r"\s+", " ", (text or "").translate(APOSTROPHES)).strip().lower()
LABEL_PREFIX_RE = re.compile(r"^\s*\(?\s*(-?\d{1,2})\s*\)?\s*(?:[-–—:=.)]\s*)?[^\W\d_]")


class InputError(Exception):
    """The input cannot be analysed as given (exit code 2)."""


# --------------------------------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------------------------------


def wilson(x, n, z):
    """Wilson (1927) score interval for x successes in n, no continuity correction. Returns (low, high)."""
    if n == 0:
        return None, None
    p = x / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0)) / denom
    low, high = max(0.0, centre - half), min(1.0, centre + half)
    if x == 0:
        low = 0.0
    if x == n:
        high = 1.0
    return low, high


def pava_decreasing(values, weights):
    """Weighted least-squares fit that never increases (pool-adjacent-violators, Barlow et al. 1972).

    values[i] with weight weights[i] > 0, in ascending price order. Returns the fitted list.
    """
    blocks = []  # [mean, weight, count]
    for v, w in zip(values, weights):
        blocks.append([v, w, 1])
        # Non-increasing: a later block may not sit above an earlier one.
        while len(blocks) > 1 and blocks[-1][0] > blocks[-2][0]:
            m2, w2, c2 = blocks.pop()
            m1, w1, c1 = blocks.pop()
            blocks.append([(m1 * w1 + m2 * w2) / (w1 + w2), w1 + w2, c1 + c2])
    fitted = []
    for mean, _, count in blocks:
        fitted.extend([mean] * count)
    return fitted


def arc_elasticity(p1, q1, p2, q2):
    """Midpoint (arc) elasticity of demand between (p1, q1) and (p2, q2) (Allen 1934)."""
    if q1 + q2 == 0 or p1 + p2 == 0 or p1 == p2:
        return None
    return ((q2 - q1) / ((q1 + q2) / 2.0)) / ((p2 - p1) / ((p1 + p2) / 2.0))


def percentile(sorted_values, q):
    """Linear-interpolation percentile (type 7) of an ascending list; q in 0..100."""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q / 100.0
    low = int(math.floor(pos))
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


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


def sniff_delimiter(text):
    best, best_key = ",", None
    for delim in (",", ";", "\t", "|"):
        try:  # parse as CSV (not line by line) so quoted line breaks in question text stay inside one cell
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


def read_table(path, delimiter=None, skip_rows=None, notes=None):
    """(headers, rows as dicts, question-text row or None). BOMs, UTF-16, CRLF, sniffed delimiter,
    Qualtrics's extra header rows; stops on duplicate column names and rows of the wrong width."""
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
    if delimiter:
        delim = DELIMITERS.get(delimiter.lower(), delimiter)
        if len(delim) != 1:
            raise InputError(f"--delimiter takes one character or comma, semicolon, tab, pipe; got {delimiter!r}")
    else:
        delim = sniff_delimiter(text)
        if delim != ",":
            notes.append(f"Delimiter detected: {DELIMITER_NAMES[delim]}.")
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
    text_row = None
    if skip_rows is None:
        if len(body) >= 2 and any(cell.strip().startswith('{"ImportId"') for cell in body[1]):
            skip_rows = 2
            text_row = dict(zip(headers, body[0]))
            notes.append("Qualtrics export detected: skipped the question-text and ImportId rows under the header.")
        else:
            skip_rows = 0
    elif skip_rows:
        notes.append(f"Skipped {skip_rows} row(s) under the header (--skip-rows).")
    rows = []
    for index, row in enumerate(body[skip_rows:], start=2 + skip_rows):
        if len(row) > len(headers) and not any(c.strip() for c in row[len(headers):]):
            row = row[: len(headers)]
        if len(row) != len(headers):
            hint = " If the file uses another delimiter, pass --delimiter." if len(headers) == 1 else ""
            raise InputError(f"{path} row {index} has {len(row)} cells but the header has {len(headers)}; a row "
                             f"may be cut or shifted, so values would land in the wrong columns.{hint}")
        rows.append(dict(zip(headers, (c.strip() for c in row))))
    return headers, rows, text_row


CURRENCY_STRIP_RE = re.compile(r"^(?:[a-z]{1,2}\$|[" + CURRENCY + r"]|(?:" + CURRENCY_CODES + r")\b)\s*|\s*(?:["
                               + CURRENCY + r"]|\b(?:" + CURRENCY_CODES + r"))$", re.I)


def parse_number(text, decimal):
    """A price or number as float, or None. Thousands separators: '1,299' (exactly three digits after each
    comma) with a decimal dot, '1.299,50' with a decimal comma, and spaces ('1 299'). Under --decimal comma a
    lone dot ('9.99') is refused rather than read as a thousands separator."""
    t = (text or "").strip()
    for _ in range(2):
        t = CURRENCY_STRIP_RE.sub("", t).strip()
    if re.fullmatch(r"-?\d{1,3}(?:[\u00a0\u202f ]\d{3})+(?:[.,]\d+)?", t):
        t = re.sub(r"[\u00a0\u202f ]", "", t)
    if decimal == "comma":
        if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", t):
            t = t.replace(".", "")
        elif "." in t:
            return None
        t = t.replace(",", ".")
    else:
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", t):
            t = t.replace(",", "")
    try:
        value = float(t)
    except ValueError:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def parse_price_list(text, decimal, flag):
    out = []
    sep = ";" if decimal == "comma" or ";" in text else ","
    for part in text.split(sep):
        value = parse_number(part, decimal)
        if value is None or value < 0:
            raise InputError(f"{flag}: {part!r} is not a price (separate prices with {sep!r}; use ';' when a "
                             "price has a thousands separator, e.g. 999;1,299;1,499)")
        out.append(value)
    if len(set(out)) != len(out):
        raise InputError(f"{flag}: a price is listed twice")
    return out


def find_price_columns(headers, text_row, decimal, notes):
    """{column: price} from headers such as '$10', 'price_10', 'p10', or Qualtrics question text."""
    found = {}
    for h in headers:
        m = PRICE_HEADER_RE.match(h)
        if m:
            value = parse_number(m.group("num"), decimal)
            bare = not m.group("cur") and not m.group("suf") and (m.group("prefix") or "").lower() in ("", "p")
            if value is not None and bare and value == int(value) and value < 10:
                continue  # P1, P2, 3: question numbers, not prices; single-digit prices need a currency or price_
            if value is not None:
                found[h] = value
    if len(found) < 2 and text_row:
        found = {}
        for h, label in text_row.items():
            prices = PRICE_IN_TEXT_RE.findall(label or "")
            if len(prices) == 1:
                value = parse_number(prices[0][0] or prices[0][1], decimal)
                if value is not None:
                    found[h] = value
        if len(found) >= 2:
            notes.append("Prices read from the Qualtrics question-text row: "
                         + ", ".join(f"{c}={fmt_price(p)}" for c, p in found.items()) + ".")
    if len(found) < 2:
        return {}
    if len(set(found.values())) != len(found):
        dup = sorted({p for p in found.values() if list(found.values()).count(p) > 1})
        raise InputError(f"two columns map to the same price ({', '.join(fmt_price(p) for p in dup)}); "
                         "pass --price-cols COL=PRICE,... to say which is which")
    return found


# --------------------------------------------------------------------------------------------------
# Answers
# --------------------------------------------------------------------------------------------------

_NOT = r"(?:(?:(?:would|will|do|does)\s*)?(?:not\b|n'?t\b)|(?:won'?t|wouldn'?t|wont|wouldnt|no)\b)"
INTENT_WORDS = [  # (pattern, point on a 5-point scale where 5 = most likely to buy); checked in order, on
    # norm_text (lower case, straight apostrophes). The midpoint comes first: "neither likely nor unlikely".
    (re.compile(r"might or might not|may or may not|not sure|unsure|neither|neutral|undecided"), 3),
    (re.compile(r"\bdefinitely\s+" + _NOT + r"|\bcertainly\s+" + _NOT + r"|extremely unlikely|very unlikely|"
                r"not at all likely|not likely at all"), 1),
    (re.compile(r"\bprobably\s+" + _NOT + r"|somewhat unlikely|\bunlikely\b|not likely|not very likely"), 2),
    (re.compile(r"definitely|extremely likely|very likely|certainly"), 5),
    (re.compile(r"probably|somewhat likely|\blikely\b"), 4),
]
NEGATION_RE = re.compile(r"\bnot\b|n't\b|\bno\b|\bnever\b|\bunlikely\b|\bwont\b|\bwouldnt\b")
LIKELY_QUALIFIER_RE = re.compile(r"(?<!not )\b(extremely|very|quite|fairly|somewhat|moderately|slightly)\s+(un)?likely\b")


def word_point(text):
    """Point 1-5 for an intent label, or None. A label that reads as positive but carries a negation
    ("Definitely, not at this price") is not guessed: None, so it is counted as unreadable."""
    low = norm_text(text)
    for pattern, point in INTENT_WORDS:
        if pattern.search(low):
            if point >= 4 and NEGATION_RE.search(low):
                return None
            return point
    return None


def finer_likelihood_scale(labels):
    """True when the labels hold more likelihood qualifiers on one side than a 5-point scale has (a 7-point
    bipolar or a unipolar 'extremely ... slightly likely' scale), so reading by words would merge points."""
    sides = {"": set(), "un": set()}
    for label in labels:
        for qualifier, un in LIKELY_QUALIFIER_RE.findall(norm_text(label)):
            sides[un or ""].add(qualifier)
    return any(len(q) > 2 or q & {"moderately", "slightly"} for q in sides.values())


class AnswerReader:
    """Turns answer cells into (buy 0/1, value in [0, 1]) with one consistent rule for the whole file."""

    def __init__(self, args, cells):
        self.kind = None
        self.scale = None  # codes highest first
        self.buy_box = args.buy_box
        self.weights = None
        if args.intent_scale:
            sep = "|" if "|" in args.intent_scale else ","
            self.scale = [c.strip() for c in args.intent_scale.split(sep) if c.strip()]
            self.scale_keys = [norm_text(c) for c in self.scale]
            if len(self.scale) < 2 or len(set(self.scale_keys)) != len(self.scale_keys):
                raise InputError("--intent-scale lists each scale code once, from 'definitely would buy' down, "
                                 "for example 5,4,3,2,1 (labels: separate them with |)")
        if args.intent_weights:
            try:
                self.weights = [float(w) for w in args.intent_weights.split(",")]
            except ValueError:
                raise InputError("--intent-weights takes numbers between 0 and 1, highest intent first")
            if any(not math.isfinite(w) or w < 0 or w > 1 for w in self.weights):
                raise InputError("--intent-weights must be numbers between 0 and 1")
        values = [c for c in cells if c and not NON_ANSWER_RE.match(norm_text(c))]
        lowered = {norm_text(v) for v in values}
        words = [word_point(v) for v in values]
        if self.scale:
            self.kind = "scale"
        elif any(w is not None for w in words):
            if finer_likelihood_scale(lowered):
                labels = sorted({v for v in values if LIKELY_QUALIFIER_RE.search(norm_text(v))})[:7]
                raise InputError(
                    "the answer labels look like a 7-point or unipolar likelihood scale ("
                    + ", ".join(repr(v) for v in labels) + "); reading them as 5 points would merge scale points. "
                    "List every label highest intent first with --intent-scale, separated by |, for example "
                    "--intent-scale 'Extremely likely|Very likely|Somewhat likely|Neither likely nor unlikely|"
                    "Somewhat unlikely|Very unlikely|Extremely unlikely'")
            self.kind = "words"
        else:
            codes = {v for v in lowered if parse_number(v, "dot") is not None}
            other = {v for v in codes if v not in YES | NO and parse_number(v, "dot") not in (0.0, 1.0)}
            if other:
                if len({parse_number(v, "dot") for v in codes}) == 2:
                    raise InputError(
                        "the answers use two codes (" + ", ".join(sorted(codes)) + "). Say which one means "
                        "'would buy': --intent-scale YES_CODE,NO_CODE, for example --intent-scale 1,2 when 1 = yes")
                raise InputError(
                    "the answers include scale codes other than 0 and 1 ("
                    + ", ".join(sorted(other)[:6])
                    + "). Say which code means 'definitely would buy': pass --intent-scale with the codes highest "
                    "intent first, for example --intent-scale 5,4,3,2,1 (most tools) or 1,2,3,4,5")
            self.kind = "binary"
        points = 2 if self.kind == "binary" else (len(self.scale) if self.scale else 5)
        self.points = points
        if self.buy_box is None:
            self.buy_box = 1 if points == 2 else 2
        if self.weights is not None:
            if self.kind == "binary":
                raise InputError("--intent-weights needs a purchase-intent scale; these answers are yes/no")
            if len(self.weights) != points:
                raise InputError(f"--intent-weights needs {points} numbers (one per scale point, highest first)")
            if any(self.weights[i] < self.weights[i + 1] for i in range(points - 1)):
                raise InputError("--intent-weights must not increase from the top scale point down")
        if self.kind != "binary" and not (1 <= self.buy_box < points):
            raise InputError(f"--buy-box must be between 1 and {points - 1}")

    def read(self, raw):
        """(rank, value) where rank counts down from 0 = top intent, or None, or the string reason."""
        text = (raw or "").strip()
        low = norm_text(text)
        if not low or NON_ANSWER_RE.match(low):
            return "blank"
        if self.kind == "binary":
            if low in YES or parse_number(low, "dot") == 1.0:
                return 0
            if low in NO or parse_number(low, "dot") == 0.0:
                return 1
            return "unreadable"
        if self.kind == "scale":
            keys = self.scale_keys
            if low in keys:
                return keys.index(low)
            m = LABEL_PREFIX_RE.match(text)
            if m:
                if norm_text(m.group(1)) in keys:
                    return keys.index(norm_text(m.group(1)))
                rest = norm_text(re.sub(r"^\s*\(?\s*-?\d{1,2}\s*\)?\s*[-–—:=.)]?\s*", "", text))
                if rest in keys:
                    return keys.index(rest)
            number = parse_number(text, "dot")
            if number is not None and number == int(number) and str(int(number)) in keys:
                return keys.index(str(int(number)))
            return "unreadable"
        point = word_point(text)
        if point is None:
            if low in YES:
                return 0
            if low in NO:
                return 4
            return "unreadable"
        return 5 - point

    def value(self, rank):
        if self.kind == "binary":
            return 1.0 if rank == 0 else 0.0
        if self.weights is not None:
            return self.weights[rank]
        return 1.0 if rank < self.buy_box else 0.0

    def buys(self, rank):
        return rank == 0 if self.kind == "binary" else rank < self.buy_box

    def describe(self):
        if self.kind == "binary":
            return "yes/no answers; would buy = yes"
        if self.scale and self.points == 2:
            source = f"two codes, {self.scale[0]} = would buy, {self.scale[1]} = would not"
            if self.weights is None:
                return source
        else:
            source = f"scale {' | '.join(self.scale)} (highest intent first)" if self.scale else \
                "intent labels read by their words (5 points, 'definitely would buy' highest)"
        if self.weights is not None:
            return (f"{source}; value = calibrated purchase probability "
                    + ", ".join(f"{w:g}" for w in self.weights) + " (highest first)")
        box = "top box" if self.buy_box == 1 else f"top-{self.buy_box} box"
        return f"{source}; would buy = {box}"


# --------------------------------------------------------------------------------------------------
# Building respondents
# --------------------------------------------------------------------------------------------------


def load(args, notes):
    """Returns (respondents, prices, reader_description, counts dict, binary flag).

    Each respondent: {"id", "segment", "answers": {price: (buy bool, value float)}}.
    """
    counts = {"rows": 0, "no_answers": 0, "unreadable_cells": 0, "blank_cells": 0, "answer_cells": 0}
    shapes = [flag for flag, on in (("--counts", args.counts), ("--long", args.long),
                                    ("--max-price-col", args.max_price_col), ("--price-cols", args.price_cols)) if on]
    if len(shapes) > 1:
        raise InputError(f"{' and '.join(shapes)} describe different input shapes; use one")
    if args.counts:
        if args.input or args.segment or args.id_col:
            raise InputError("--counts replaces the CSV file: drop the file name, --segment and --id-col")
        return load_counts(args, notes, counts)
    if args.counts_sample or args.base:
        raise InputError("--base and --counts-sample go with --counts only")
    if not args.input:
        raise InputError("give a CSV file, or --counts PRICE:BUYERS,... for aggregated counts")
    if args.skip_rows is not None and args.skip_rows < 0:
        raise InputError("--skip-rows must be 0 or more")
    headers, rows, text_row = read_table(args.input, args.delimiter, args.skip_rows, notes)
    counts["rows"] = len(rows)
    if not rows:
        raise InputError(f"{args.input} has a header but no data rows (n = 0)")
    if args.segment and args.segment not in headers:
        raise InputError(f"--segment column {args.segment!r} not found. Columns: {', '.join(headers)}")
    if args.id_col and args.id_col not in headers:
        raise InputError(f"--id-col {args.id_col!r} not found. Columns: {', '.join(headers)}")
    if args.id_col and not args.long:
        ids = [r[args.id_col] for r in rows if r[args.id_col]]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise InputError(f"respondent id(s) {', '.join(repr(d) for d in dup[:5])} appear on more than one row; "
                             "one row per respondent is expected here (or use --long)")

    if args.max_price_col:
        return load_max_price(args, headers, rows, notes, counts)

    if args.long:
        for flag, col in (("--price-col", args.price_col), ("--answer-col", args.answer_col)):
            if not col:
                raise InputError(f"--long needs {flag}")
            if col not in headers:
                raise InputError(f"{flag} {col!r} not found. Columns: {', '.join(headers)}")
        if args.id_col:
            blank_ids = sum(1 for r in rows if not r[args.id_col])
            if blank_ids:
                raise InputError(f"{blank_ids} row(s) have a blank {args.id_col!r}: rows are grouped into respondents "
                                 "by this id, so blank ids would merge different people. Fill them or drop the rows")
        cells = [r[args.answer_col] for r in rows]
        reader = AnswerReader(args, cells)
        by_id = {}
        bad_price = 0
        for i, r in enumerate(rows):
            price = parse_number(r[args.price_col], args.decimal) if r[args.price_col] else None
            if price is None or price < 0:
                bad_price += 1
                continue
            rid = r[args.id_col] if args.id_col else f"row{i + 2}"
            seg = r.get(args.segment) if args.segment else None
            resp = by_id.setdefault(rid, {"id": rid, "segment": seg, "raw": {}})
            if args.segment and resp["segment"] != seg:
                raise InputError(f"respondent {rid!r} has two values of {args.segment!r} ({resp['segment']!r} and "
                                 f"{seg!r}); a respondent belongs to one segment")
            if price in resp["raw"]:
                raise InputError(f"respondent {rid!r} has two rows for price {fmt_price(price)}; "
                                 "remove the duplicate or check --id-col")
            resp["raw"][price] = r[args.answer_col]
        if bad_price:
            share = bad_price / len(rows)
            notes.append(f"{bad_price} row(s) without a readable price were skipped.")
            if share > UNREADABLE_STOP_SHARE and not args.allow_unreadable:
                raise InputError(f"{bad_price} of {len(rows)} rows ({share:.0%}) have no readable price in "
                                 f"{args.price_col!r}; check the column and --decimal, or pass --allow-unreadable")
        prices = sorted({p for resp in by_id.values() for p in resp["raw"]})
        raw_respondents = list(by_id.values())
    else:
        if args.price_cols:
            mapping = {}
            for part in args.price_cols.split(";" if ";" in args.price_cols else ","):
                if "=" not in part:
                    raise InputError("--price-cols takes COLUMN=PRICE pairs separated by commas")
                col, price = part.rsplit("=", 1)
                col = col.strip()
                if col not in headers:
                    raise InputError(f"--price-cols: column {col!r} not found. Columns: {', '.join(headers)}")
                value = parse_number(price, args.decimal)
                if value is None or value < 0:
                    raise InputError(f"--price-cols: {price!r} is not a price")
                mapping[col] = value
            if len(set(mapping.values())) != len(mapping):
                raise InputError("--price-cols maps two columns to the same price")
        else:
            mapping = find_price_columns(headers, text_row, args.decimal, notes)
            if not mapping:
                raise InputError(
                    "could not tell which columns are prices. Name them like '$10' or 'price_10', or pass "
                    "--price-cols COL=PRICE,COL=PRICE (or --long, or --max-price-col). Columns: "
                    + ", ".join(headers))
        cells = [r[c] for r in rows for c in mapping]
        reader = AnswerReader(args, cells)
        raw_respondents = []
        for i, r in enumerate(rows):
            rid = r[args.id_col] if args.id_col and r[args.id_col] else f"row{i + 2 + (args.skip_rows or 0)}"
            raw_respondents.append({"id": rid, "segment": r.get(args.segment) if args.segment else None,
                                    "raw": {mapping[c]: r[c] for c in mapping}})
        prices = sorted(mapping.values())
        notes.append("Price columns: " + ", ".join(f"{c} = {fmt_price(p)}" for c, p in
                                                    sorted(mapping.items(), key=lambda kv: kv[1])) + ".")

    respondents = []
    unreadable_examples = []
    for resp in raw_respondents:
        answers = {}
        for price, cell in resp["raw"].items():
            rank = reader.read(cell)
            if rank == "blank":
                counts["blank_cells"] += 1
                continue
            counts["answer_cells"] += 1
            if rank == "unreadable":
                counts["unreadable_cells"] += 1
                if len(unreadable_examples) < 5 and cell not in unreadable_examples:
                    unreadable_examples.append(cell)
                continue
            answers[price] = (reader.buys(rank), reader.value(rank))
        if not answers:
            counts["no_answers"] += 1
            continue
        respondents.append({"id": resp["id"], "segment": resp["segment"], "answers": answers})
    if counts["answer_cells"]:
        share = counts["unreadable_cells"] / counts["answer_cells"]
        if share > UNREADABLE_STOP_SHARE and not args.allow_unreadable:
            raise InputError(
                f"{counts['unreadable_cells']} of {counts['answer_cells']} answers ({share:.0%}) could not be read "
                f"as {reader.describe()} (for example {', '.join(repr(u) for u in unreadable_examples)}). Look at "
                "them: a missing --intent-scale code or a different answer wording is the usual cause. "
                "--allow-unreadable drops them instead")
    if counts["unreadable_cells"]:
        notes.append(f"{counts['unreadable_cells']} unreadable answer(s) dropped "
                     f"(for example {', '.join(repr(u) for u in unreadable_examples)}).")
    if not respondents:
        raise InputError("no respondent has a readable answer at any price (n = 0)")
    binary = reader.weights is None
    return respondents, prices, reader.describe(), counts, binary


def load_max_price(args, headers, rows, notes, counts):
    col = args.max_price_col
    if col not in headers:
        raise InputError(f"--max-price-col {col!r} not found. Columns: {', '.join(headers)}")
    if not args.prices:
        raise InputError("--max-price-col needs --prices, the full price ladder that was tested")
    prices = sorted(parse_price_list(args.prices, args.decimal, "--prices"))
    respondents = []
    for i, r in enumerate(rows):
        cell = r[col].strip()
        rid = r[args.id_col] if args.id_col and r[args.id_col] else f"row{i + 2}"
        if not cell or NON_ANSWER_RE.match(norm_text(cell)):
            counts["blank_cells"] += 1
            counts["no_answers"] += 1
            continue
        counts["answer_cells"] += 1
        if norm_text(cell) in NONE_TOKENS:
            top = None
        else:
            top = parse_number(cell, args.decimal)
            if top is None or top < 0:  # negative values are missing-value codes (-99, -1), not prices
                counts["unreadable_cells"] += 1
                counts["no_answers"] += 1
                continue
        answers = {}
        for p in prices:
            buys = top is not None and p <= top + 1e-9
            answers[p] = (buys, 1.0 if buys else 0.0)
        respondents.append({"id": rid, "segment": r.get(args.segment) if args.segment else None,
                            "answers": answers})
    if counts["answer_cells"] and counts["unreadable_cells"] / counts["answer_cells"] > UNREADABLE_STOP_SHARE \
            and not args.allow_unreadable:
        raise InputError(f"{counts['unreadable_cells']} of {counts['answer_cells']} values in {col!r} are not "
                         "prices or 'none'; check --decimal, or pass --allow-unreadable")
    tops = [parse_number(r[col], args.decimal) for r in rows if r[col].strip()]
    off_ladder = sum(1 for t in tops if t is not None and t >= 0 and all(abs(t - p) > 1e-9 for p in prices))
    if counts["unreadable_cells"]:
        notes.append(f"{counts['unreadable_cells']} value(s) in {col!r} are not prices or 'none' (negative codes such "
                     "as -99 count here) and were dropped.")
    if off_ladder:
        notes.append(f"{off_ladder} highest price(s) are not on the ladder; each counts as buying at every ladder "
                     "price at or below it.")
    if not respondents:
        raise InputError("no respondent has a readable highest price (n = 0)")
    notes.append(f"Highest-price column {col!r}; ladder {', '.join(fmt_price(p) for p in prices)}.")
    return respondents, prices, "highest acceptable price per respondent; would buy = price at or below it", \
        counts, True


def parse_count(text, allow_thousands):
    t = (text or "").strip()
    if allow_thousands and re.fullmatch(r"\d{1,3}(,\d{3})+", t):
        t = t.replace(",", "")
    return int(t) if re.fullmatch(r"\d+", t) else None


def load_counts(args, notes, counts):
    """--counts as respondents. 'separate': each price is its own sample (monadic). 'same': one group of
    `base` people answered every price, so the buyers fall (weakly) with price and the drop between adjacent
    prices is the number whose highest accepted price is the lower one; the group is rebuilt from those drops."""
    if args.counts_sample not in ("same", "separate"):
        raise InputError("--counts needs --counts-sample: 'same' when one group of people answered every price "
                         "(a full or adaptive ladder, as in most published tables), 'separate' when each price was "
                         "asked of a different sample (monadic). The respondent count and the bootstrap differ")
    text = args.counts.strip()
    semi = ";" in text
    if args.decimal == "comma" and not semi and len([x for x in text.split(",") if ":" in x]) > 1:
        raise InputError("with --decimal comma, separate --counts pairs with ';'")
    parts = text.split(";" if semi else ",")
    cells = []
    for part in parts:
        part = part.strip()
        if ":" not in part:
            raise InputError(f"--counts: {part!r} is not PRICE:BUYERS or PRICE:BUYERS/N. If a number has a thousands "
                             "separator, separate the pairs with ';' (for example '999:120;1,299:85')")
        price_text, rest = part.split(":", 1)
        price = parse_number(price_text, args.decimal)
        if price is None or price < 0:
            raise InputError(f"--counts: {price_text!r} is not a price")
        buyers_text, n_text = rest.split("/", 1) if "/" in rest else (rest, args.base)
        if n_text in (None, ""):
            raise InputError("--counts PRICE:BUYERS needs --base N, or write PRICE:BUYERS/N")
        buyers, n = parse_count(buyers_text, semi), parse_count(str(n_text), True)
        if buyers is None or n is None:
            raise InputError(f"--counts: buyers and base must be whole numbers ({part!r})")
        if n <= 0 or buyers > n:
            raise InputError(f"--counts: need 0 <= buyers <= base and base > 0 ({part!r})")
        if any(abs(price - c[0]) < 1e-12 for c in cells):
            raise InputError(f"--counts lists price {fmt_price(price)} twice")
        cells.append((price, buyers, n))
    cells.sort()
    prices = [c[0] for c in cells]
    respondents = []
    if args.counts_sample == "separate":
        seq = 0
        for price, buyers, n in cells:
            for j in range(n):
                seq += 1
                yes = j < buyers
                respondents.append({"id": f"c{seq}", "segment": None, "answers": {price: (yes, 1.0 if yes else 0.0)}})
        notes.append("Counts input, separate samples: each price is its own sample (monadic); respondents read = "
                     "the sum of the bases.")
    else:
        bases = {c[2] for c in cells}
        if len(bases) != 1:
            raise InputError("--counts-sample same needs one base for every price (the same people answered each); "
                             "the bases differ, so these are separate samples or a partial ladder")
        base = bases.pop()
        rising = [(a[0], b[0]) for a, b in zip(cells, cells[1:]) if b[1] > a[1]]
        if rising:
            raise InputError(
                f"buyers rise from {fmt_price(rising[0][0])} to {fmt_price(rising[0][1])}: one group with consistent "
                "answers cannot do that, so the group cannot be rebuilt from these counts. Use the respondent-level "
                "file, or --counts-sample separate (intervals then ignore that the same people answered each price)")
        tiers = [(None, base - cells[0][1])] + [(cells[k][0], cells[k][1] - (cells[k + 1][1] if k + 1 < len(cells)
                                                                              else 0)) for k in range(len(cells))]
        seq = 0
        for top, count in tiers:
            for _ in range(count):
                seq += 1
                answers = {p: (top is not None and p <= top, 1.0 if top is not None and p <= top else 0.0)
                           for p in prices}
                respondents.append({"id": f"c{seq}", "segment": None, "answers": answers})
        notes.append(f"Counts input, one group of {base} answering every price: rebuilt as {base} respondents from the "
                     "drop in buyers between adjacent prices.")
    counts["rows"] = len(respondents)
    counts["answer_cells"] = sum(len(r["answers"]) for r in respondents)
    return respondents, prices, "counts of buyers per price", counts, True


# --------------------------------------------------------------------------------------------------
# Consistency and imputation
# --------------------------------------------------------------------------------------------------


def check_and_complete(respondents, prices, mode, impute, by_value=False, monadic=False):
    """Flags respondents whose answer rises with price (would buy at a higher price but not a lower one; with
    calibrated weights, a higher value at a higher price), and (impute=True) fills prices that were not asked
    from the monotone assumption. Returns (kept respondents, stats). Each kept respondent carries "complete"
    (asked + filled answers) and "imputed" (the filled prices)."""
    stats = {"inconsistent": 0, "inconsistent_excluded": 0, "imputed_cells": 0, "incomplete": 0}
    kept = []
    for resp in respondents:
        ans = resp["answers"]
        asked = sorted(ans)
        if by_value:
            inconsistent = any(ans[hi][1] > ans[lo][1] + 1e-12 for i, lo in enumerate(asked) for hi in asked[i + 1:])
        else:
            inconsistent = any(ans[hi][0] and not ans[lo][0] for i, lo in enumerate(asked) for hi in asked[i + 1:])
        if inconsistent:
            stats["inconsistent"] += 1
            if mode == "exclude":
                stats["inconsistent_excluded"] += 1
                continue
            kept.append({**resp, "complete": dict(ans), "imputed": set()})
            continue
        complete = dict(ans)
        imputed = set()
        if impute and len(asked) < len(prices):
            for p in prices:
                if p in complete:
                    continue
                above = [q for q in asked if q > p and ans[q][0]]
                below = [q for q in asked if q < p and not ans[q][0]]
                if above:
                    complete[p] = ans[min(above)]
                elif below:
                    complete[p] = ans[max(below)]
                else:
                    continue
                imputed.add(p)
                stats["imputed_cells"] += 1
        if not monadic and len(complete) < len(prices):
            stats["incomplete"] += 1
        kept.append({**resp, "complete": complete, "imputed": imputed})
    return kept, stats


# --------------------------------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------------------------------


def curve(group, prices):
    """Per-price n, sum of values, buyers. Returns lists aligned to prices."""
    n = [0] * len(prices)
    total = [0.0] * len(prices)
    buyers = [0] * len(prices)
    index = {p: i for i, p in enumerate(prices)}
    for resp in group:
        for p, (buy, value) in resp["complete"].items():
            i = index[p]
            n[i] += 1
            total[i] += value
            buyers[i] += 1 if buy else 0
    return n, total, buyers


def observed_counts(group, prices):
    """Answers actually given at each price (filled cells left out)."""
    index = {p: i for i, p in enumerate(prices)}
    n = [0] * len(prices)
    for resp in group:
        for p in resp["complete"]:
            if p not in resp.get("imputed", ()):
                n[index[p]] += 1
    return n


def objective_values(prices, take, unit_cost):
    if unit_cost is None:
        return [p * t for p, t in zip(prices, take)]
    return [(p - unit_cost) * t for p, t in zip(prices, take)]


def best_index(values):
    top = max(values)
    tol = TIE_TOLERANCE * max(abs(top), 1.0)
    return [i for i, v in enumerate(values) if v >= top - tol]


def fit(group, prices, unit_cost):
    n, total, buyers = curve(group, prices)
    used = [i for i in range(len(prices)) if n[i] > 0]
    take = [total[i] / n[i] if n[i] else None for i in range(len(prices))]
    mono_used = pava_decreasing([take[i] for i in used], [n[i] for i in used]) if used else []
    mono = [None] * len(prices)
    for i, m in zip(used, mono_used):
        mono[i] = m
    return n, total, buyers, take, mono, used


def analyse_group(label, group, prices, args, binary, z, rng, monadic=False):
    warnings = []
    n, total, buyers, take, mono, used = fit(group, prices, args.unit_cost)
    n_obs = observed_counts(group, prices)
    rows = []
    obj_used = objective_values([prices[i] for i in used], [mono[i] for i in used], args.unit_cost)
    raw_obj = objective_values([prices[i] for i in used], [take[i] for i in used], args.unit_cost)
    for k, i in enumerate(used):
        low, high = wilson(buyers[i], n[i], z) if binary else (None, None)
        nxt = used[k + 1] if k + 1 < len(used) else None
        rows.append({
            "price": prices[i], "n": n[i], "n_observed": n_obs[i], "buyers": buyers[i] if binary else None,
            "take_rate": take[i], "ci_low": low, "ci_high": high, "ci_method": "wilson" if binary else "bootstrap",
            "monotone_take_rate": mono[i], "monotone_ci_low": None, "monotone_ci_high": None,
            "revenue_index": prices[i] * mono[i],
            "profit_index": (prices[i] - args.unit_cost) * mono[i] if args.unit_cost is not None else None,
            "raw_revenue_index": prices[i] * take[i],
            "raw_profit_index": (prices[i] - args.unit_cost) * take[i] if args.unit_cost is not None else None,
            "arc_elasticity_to_next": arc_elasticity(prices[i], mono[i], prices[nxt], mono[nxt])
            if nxt is not None else None,
            "small_base": n_obs[i] < args.min_base,
        })
    missing = [prices[i] for i in range(len(prices)) if n[i] == 0]
    if missing:
        warnings.append("No answers at " + ", ".join(fmt_price(p) for p in missing) + "; those prices are left out.")
    pooled = [rows[k]["price"] for k in range(len(rows))
              if abs(rows[k]["take_rate"] - rows[k]["monotone_take_rate"]) > 1e-12]
    if pooled:
        warnings.append("The raw take rate rises with price somewhere; the monotone curve pools "
                        + ", ".join(fmt_price(p) for p in pooled) + " (pool-adjacent-violators).")
    small = [r["price"] for r in rows if r["small_base"]]
    if small:
        warnings.append(f"Small base (under {args.min_base} answers given, filled cells not counted) at "
                        + ", ".join(fmt_price(p) for p in small) + ": treat the curve as directional.")

    optimum = {"named": False, "objective": "profit" if args.unit_cost is not None else "revenue"}
    if len(used) < 2:
        optimum["reason"] = "fewer than two prices with answers: no curve"
    elif min(n[i] for i in used) < MIN_N_FOR_OPTIMUM:
        optimum["reason"] = (f"fewer than {MIN_N_FOR_OPTIMUM} answers at some price: no optimal price named "
                             "(convention of this skill)")
    elif max(obj_used) <= 0:
        optimum["reason"] = ("no price has a positive " + optimum["objective"] +
                             (" (every tested price is at or below the unit cost, or nobody buys)"
                              if args.unit_cost is not None else " (nobody would buy at any price)"))
    else:
        best = best_index(obj_used)
        bi = used[best[0]]
        optimum.update({
            "named": True, "price": prices[bi], "value": obj_used[best[0]], "take_rate": mono[bi],
            "tied_with": [prices[used[b]] for b in best[1:]],
            "at_lowest_price": best[0] == 0, "at_highest_price": best[-1] == len(used) - 1,
        })
        if optimum["tied_with"]:
            warnings.append("The " + optimum["objective"] + " index is equal at "
                            + ", ".join(fmt_price(prices[used[b]]) for b in best)
                            + "; the lowest is shown. Report them as tied.")
        if optimum["at_highest_price"]:
            warnings.append("The optimum is the highest price tested: the ladder may stop below the real optimum. "
                            "Test higher prices before concluding.")
        if optimum["at_lowest_price"]:
            warnings.append("The optimum is the lowest price tested: the ladder may start above the real optimum. "
                            "Test lower prices before concluding.")
        raw_best = [used[b] for b in best_index(raw_obj)] if max(raw_obj) > 0 else []
        if pooled and raw_best and bi not in raw_best:
            warnings.append(f"On the raw (unpooled) take rates the {optimum['objective']} index peaks at "
                            + ", ".join(fmt_price(prices[i]) for i in raw_best) + " instead. If low prices may read "
                            "as low quality, report both curves (raw_revenue_index, raw_profit_index).")
    if used and all(abs(mono[i] - mono[used[0]]) < 1e-12 for i in used):
        warnings.append("Every price has the same take rate: the answers do not separate the prices.")

    boot = None
    if args.bootstrap and len(used) >= 2:
        boot = bootstrap(group, prices, used, args, rng, label, monadic)
        if boot:
            for r in rows:
                key = fmt_key(r["price"])
                r["monotone_ci_low"], r["monotone_ci_high"] = boot["monotone_take_rate_intervals"][key]
                if not binary:
                    r["ci_low"], r["ci_high"] = boot["take_rate_intervals"][key]
        if optimum.get("named") and boot and boot.get("optimum_share"):
            share = boot["optimum_share"].get(fmt_key(optimum["price"]), 0.0)
            optimum["bootstrap_share"] = share
            if share < 0.5:
                warnings.append(f"The optimum is unstable: {fmt_price(optimum['price'])} is the optimum in only "
                                f"{share:.0%} of bootstrap samples. Report the range of prices, not one price.")
    return {"label": label, "respondents": len(group), "prices": rows, "optimum": optimum, "bootstrap": boot,
            "warnings": warnings}


def fmt_key(price):
    return f"{price:.10g}"


def nearest_rank(sorted_values, q):
    """Inverse empirical CDF (Hyndman-Fan type 1): always one of the values, so an optimum interval names
    tested prices only."""
    if not sorted_values:
        return None
    k = max(1, math.ceil(q / 100.0 * len(sorted_values) - 1e-9))
    return sorted_values[min(k, len(sorted_values)) - 1]


def bootstrap(group, prices, used, args, rng, label, monadic=False):
    """Percentile bootstrap over respondents. A monadic test is resampled within each price cell (cell sizes are
    fixed by design); a ladder is resampled over respondents as a whole, because which prices a respondent was
    asked depends on their answers there. A tied optimum splits the replicate's vote among the tied prices."""
    if monadic:
        strata = {}
        for resp in group:
            strata.setdefault(tuple(sorted(resp["complete"])), []).append(resp)
        strata = list(strata.values())
    else:
        strata = [list(group)]
    reps = args.bootstrap
    used_prices = [prices[i] for i in used]
    takes = {p: [] for p in used_prices}
    monos = {p: [] for p in used_prices}
    optimum_counts = {}
    opt_draws = []
    no_positive = 0
    failed = 0
    started = time.monotonic()
    for b in range(reps):
        sample = []
        for members in strata:
            sample.extend(members[rng.randrange(len(members))] for _ in range(len(members)))
        n, total, _, take, mono, u = fit(sample, prices, args.unit_cost)
        if u != used:
            failed += 1
            continue
        for i in used:
            takes[prices[i]].append(take[i])
            monos[prices[i]].append(mono[i])
        obj = objective_values(used_prices, [mono[i] for i in used], args.unit_cost)
        if max(obj) > 0:
            tied = best_index(obj)
            for t in tied:
                key = fmt_key(used_prices[t])
                optimum_counts[key] = optimum_counts.get(key, 0) + 1.0 / len(tied)
            opt_draws.append(used_prices[tied[0]])
        else:
            no_positive += 1
        if b == 9:
            expected = (time.monotonic() - started) / 10.0 * reps
            if expected > 20:
                print(f"gabor-granger-analysis: about {expected:.0f} s for {reps} bootstrap samples of {label}; "
                      "use --bootstrap 200 for a first look", file=sys.stderr)
    done = reps - failed
    if done == 0:
        return None
    alpha = (1 - args.confidence) / 2 * 100

    def intervals(draws):
        out = {}
        for p, vals in draws.items():
            vals.sort()
            out[fmt_key(p)] = [percentile(vals, alpha), percentile(vals, 100 - alpha)]
        return out

    shares = {k: v / done for k, v in sorted(optimum_counts.items(), key=lambda kv: float(kv[0]))}
    opt_draws.sort()
    return {"replicates": done, "failed": failed, "seed": args.seed, "resampling": "within price cells" if monadic
            else "respondents", "take_rate_intervals": intervals(takes),
            "monotone_take_rate_intervals": intervals(monos),
            "optimum_share": shares, "no_positive_optimum_share": no_positive / done,
            "optimum_interval": [nearest_rank(opt_draws, alpha), nearest_rank(opt_draws, 100 - alpha)]
            if opt_draws else None}


# --------------------------------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------------------------------


def fmt_price(p):
    if abs(p - round(p, 2)) < 1e-9:
        return f"{p:,.2f}"
    return f"{p:,.6f}".rstrip("0")


def fmt_index(v):
    return f"{v:,.2f}" if abs(v) >= 1 else f"{v:.4g}"


def pct(v):
    return "-" if v is None else f"{100 * v:.1f}%"


def level(confidence):
    return f"{100 * confidence:g}%"


def render(result):
    out = [f"Gabor-Granger analysis ({result['answers']})"]
    c = result["counts"]
    out.append(f"Respondents: {c['read']} read, {c['no_answers']} without a readable answer, "
               f"{c['inconsistent']} inconsistent ({c['inconsistent_rule']}), {c['analysed']} analysed. "
               f"Imputed answers: {c['imputed_cells']}.")
    out.append(f"Design: {result['design']}.")
    for note in result["notes"]:
        out.append("Note: " + note)
    for w in result["warnings"]:
        out.append("Warning: " + w)
    for g in result["groups"]:
        out.append("")
        out.append(f"== {g['label']} (n = {g['respondents']}) ==")
        has_profit = any(r["profit_index"] is not None for r in g["prices"])
        imputed = any(r["n_observed"] != r["n"] for r in g["prices"])
        head = ["Price", "n", "Asked" if imputed else None, "Take (raw)",
                f"{level(result['confidence'])} CI" + ("" if result["binary"] else " (boot.)"), "Take (monotone)",
                "Revenue idx", "Profit idx" if has_profit else None, "Arc elast."]
        head = [h for h in head if h]
        lines = [head]
        boot = g.get("bootstrap") or {}
        for r in g["prices"]:
            ci = f"{pct(r['ci_low'])}-{pct(r['ci_high'])}" if r["ci_low"] is not None else "-"
            row = [fmt_price(r["price"]), str(r["n"]) + ("*" if r["small_base"] else "")]
            if imputed:
                row.append(str(r["n_observed"]))
            row += [pct(r["take_rate"]), ci, pct(r["monotone_take_rate"]), fmt_index(r["revenue_index"])]
            if has_profit:
                row.append(fmt_index(r["profit_index"]))
            e = r["arc_elasticity_to_next"]
            row.append("-" if e is None else f"{e:.2f}")
            lines.append(row)
        widths = [max(len(line[i]) for line in lines) for i in range(len(head))]
        for line in lines:
            out.append("  ".join(cell.rjust(w) for cell, w in zip(line, widths)))
        o = g["optimum"]
        if o["named"]:
            text = (f"{o['objective'].capitalize()}-maximizing tested price: {fmt_price(o['price'])} "
                    f"(monotone take rate {pct(o['take_rate'])}, {o['objective']} index {fmt_index(o['value'])})")
            if "bootstrap_share" in o:
                text += f"; optimum in {o['bootstrap_share']:.0%} of bootstrap samples"
            out.append(text)
            if boot.get("optimum_share"):
                out.append("Bootstrap optimum: " + ", ".join(f"{fmt_price(float(k))} {v:.0%}"
                                                             for k, v in boot["optimum_share"].items())
                           + (f"; no profitable price in {boot['no_positive_optimum_share']:.0%}"
                              if boot.get("no_positive_optimum_share") else ""))
        else:
            out.append("No optimal price named: " + o["reason"])
        for w in g["warnings"]:
            out.append("Warning: " + w)
    out.append("")
    out.append("Conventions: " + "; ".join(result["conventions"]))
    return "\n".join(out)


# --------------------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------------------


def build_parser():
    p = argparse.ArgumentParser(
        description="Gabor-Granger analysis: demand curve, revenue/profit-maximizing price and checks.",
        epilog="Examples: gabor_granger_analysis.py answers.csv --intent-scale 5,4,3,2,1 ; "
               "gabor_granger_analysis.py --counts 10:190,15:164,20:118 --base 200 --counts-sample same")
    p.add_argument("input", nargs="?", help="CSV of answers (omit with --counts)")
    shape = p.add_argument_group("input shape")
    shape.add_argument("--price-cols", help="wide: COLUMN=PRICE pairs, separated by commas (semicolons when prices use a decimal comma)")
    shape.add_argument("--long", action="store_true", help="one row per respondent x price")
    shape.add_argument("--price-col", help="long: the price column")
    shape.add_argument("--answer-col", help="long: the answer column")
    shape.add_argument("--id-col", help="respondent id column (long: rows with one id are one respondent)")
    shape.add_argument("--max-price-col", help="one column with each respondent's highest acceptable price")
    shape.add_argument("--prices", help="the tested ladder, comma-separated (semicolons when a price has a "
                       "thousands separator or a decimal comma; needed with --max-price-col)")
    shape.add_argument("--counts", help="PRICE:BUYERS[/N],... aggregated counts instead of a CSV (pairs separated by "
                       "';' when a number has a thousands separator)")
    shape.add_argument("--base", help="respondents per price for --counts PRICE:BUYERS")
    shape.add_argument("--counts-sample", choices=["same", "separate"],
                       help="--counts: 'same' = one group answered every price; 'separate' = a new sample per price")
    shape.add_argument("--design", choices=["auto", "full", "adaptive", "monadic"], default="auto",
                       help="how prices were asked: full ladder (blanks are skips, nothing filled), adaptive ladder "
                       "(prices not asked are filled from monotonicity), monadic (one price each). Default auto")
    ans = p.add_argument_group("answers")
    ans.add_argument("--intent-scale", help="scale codes highest intent first, e.g. 5,4,3,2,1; labels separated "
                     "by |, e.g. 'Extremely likely|Very likely|...'")
    ans.add_argument("--buy-box", type=int, help="top-N box counted as 'would buy' (default 2; 1 for a 2-code scale)")
    ans.add_argument("--intent-weights", help="calibrated purchase probability per scale point, highest first")
    ans.add_argument("--inconsistent", choices=["exclude", "keep"], default="exclude",
                     help="respondents who buy at a higher price but not a lower one (default exclude)")
    ans.add_argument("--no-impute", action="store_true",
                     help="do not fill prices that were not asked (same as --design full for a ladder)")
    out = p.add_argument_group("analysis and output")
    out.add_argument("--unit-cost", type=float, help="variable cost per unit: maximize profit instead of revenue")
    out.add_argument("--segment", help="column to split the analysis by")
    out.add_argument("--bootstrap", type=int, default=DEFAULT_BOOTSTRAP,
                     help=f"bootstrap replicates (default {DEFAULT_BOOTSTRAP}; 0 = off)")
    out.add_argument("--seed", type=int, default=DEFAULT_SEED)
    out.add_argument("--confidence", type=float, default=0.95)
    out.add_argument("--min-base", type=int, default=SMALL_BASE, help=f"small-base flag (default {SMALL_BASE})")
    out.add_argument("--curves-csv", help="write the curve table to this CSV (never the input file)")
    out.add_argument("--json", action="store_true", help="JSON on stdout")
    io_ = p.add_argument_group("file reading")
    io_.add_argument("--delimiter", help="comma, semicolon, tab, pipe or one character (default: sniffed)")
    io_.add_argument("--skip-rows", type=int, help="rows under the header to skip (Qualtrics: detected)")
    io_.add_argument("--decimal", choices=["dot", "comma"], default="dot", help="decimal mark in prices")
    io_.add_argument("--allow-unreadable", action="store_true",
                     help="drop unreadable answers even when they are more than 5%% of answers")
    p.add_argument("--version", action="version", version=VERSION)
    return p


def choose_design(args, respondents, weights):
    """(design label, monadic, impute, notes). Never infers a design from missing answers alone: when most
    respondents answered one price but some answered several, it stops and asks."""
    singles = sum(1 for r in respondents if len(r["answers"]) == 1)
    design = args.design
    notes = []
    if args.counts:
        design = "monadic" if args.counts_sample == "separate" else "full"
    elif design == "auto":
        if singles == len(respondents):
            design = "monadic"
            notes.append("Every respondent answered one price, read as a monadic test: each price is its own sample "
                         "and nothing is filled. If this was an adaptive ladder, pass --design adaptive.")
        elif singles * 2 > len(respondents):
            raise InputError(
                f"{singles} of {len(respondents)} respondents answered one price and the rest several: say how the "
                "prices were asked with --design monadic (one price each; the others are data errors), adaptive "
                "(start price, then up or down) or full (every price; blanks are skips)")
        else:
            design = "ladder"
    elif design == "monadic" and singles != len(respondents):
        raise InputError(f"--design monadic, but {len(respondents) - singles} respondent(s) answered more than one "
                         "price; check --id-col, or use --design full or adaptive")
    monadic = design == "monadic"
    impute = design in ("ladder", "adaptive") and not args.no_impute
    if impute and weights:
        impute = False
        notes.append("Nothing is filled with --intent-weights: a calibrated value at an asked price only bounds the "
                     "value at prices not asked. Each price uses the respondents asked there, who on an adaptive "
                     "ladder are not a random subset.")
    label = {"monadic": "monadic (one price per respondent)", "full": "full ladder (blanks are skips, not filled)",
             "adaptive": "adaptive ladder", "ladder": "price ladder (full or adaptive; read from the answers)"}[design]
    if design in ("ladder", "adaptive"):
        label += ", prices not asked filled from monotonicity" if impute else ", nothing filled"
    return label, monadic, impute, notes


def analyse(args):
    if not (0.5 < args.confidence < 1):
        if 50 < args.confidence < 100:
            args.confidence /= 100.0
        else:
            raise InputError("--confidence must be between 0.5 and 1 (or 50 and 100)")
    if args.bootstrap < 0:
        raise InputError("--bootstrap must be 0 or more")
    if args.unit_cost is not None and (not math.isfinite(args.unit_cost) or args.unit_cost < 0):
        raise InputError("--unit-cost must be a number, 0 or more")
    notes = []
    respondents, prices, answers_desc, counts, binary = load(args, notes)
    if len(prices) < 2:
        raise InputError("only one price was tested: a demand curve needs at least two prices")
    if args.unit_cost is not None and args.unit_cost >= max(prices):
        notes.append("The unit cost is at or above every tested price: no price makes a profit.")
    design, monadic, impute, design_notes = choose_design(args, respondents, not binary)
    notes.extend(design_notes)
    kept, stats = check_and_complete(respondents, prices, args.inconsistent, impute, by_value=not binary,
                                     monadic=monadic)
    if not kept:
        raise InputError("every respondent was excluded as inconsistent; look at the answers, or pass "
                         "--inconsistent keep")
    share_inconsistent = stats["inconsistent"] / len(respondents)
    z = NormalDist().inv_cdf(1 - (1 - args.confidence) / 2)
    rng = random.Random(args.seed)
    groups = [analyse_group("All respondents", kept, prices, args, binary, z, rng, monadic)]
    if args.segment:
        labels = sorted({r["segment"] or "(blank)" for r in kept})
        for lab in labels:
            members = [r for r in kept if (r["segment"] or "(blank)") == lab]
            groups.append(analyse_group(f"{args.segment} = {lab}", members, prices, args, binary, z, rng, monadic))
        if len(labels) == 1:
            notes.append(f"Only one value of {args.segment!r}: the segment result equals the overall result.")
    top_warnings = []
    if stats["inconsistent"]:
        top_warnings.append(
            f"{stats['inconsistent']} respondent(s) ({share_inconsistent:.0%}) answered more positively at a higher "
            f"price than at a lower one ({'excluded' if args.inconsistent == 'exclude' else 'kept'})."
            + (" Over 10% (a review heuristic of this skill): check the answer coding and price order, and rerun "
               "with --inconsistent keep to see whether the optimum moves; price read as quality is another cause."
               if share_inconsistent > 0.10 else ""))
    if stats["incomplete"]:
        top_warnings.append(f"{stats['incomplete']} respondent(s) lack an answer at some price"
                            + (" after filling" if impute else "") + "; each price uses the respondents who have one "
                            "there.")
    if stats["imputed_cells"]:
        top_warnings.append(f"{stats['imputed_cells']} answer(s) were filled from monotonicity, not asked; they count "
                            "in n and in the intervals as if asked (the 'n_observed' column gives the answers given).")
    conventions = [
        "take rate = share who would buy at the price (" + answers_desc + ")",
        "monotone curve = weighted pool-adjacent-violators fit, never rising with price",
        "revenue index = price x monotone take rate" + ("; profit index = (price - unit cost) x take rate"
                                                        if args.unit_cost is not None else ""),
        "optimum chosen among tested prices only (no interpolation)",
        f"{'Wilson' if binary else 'bootstrap'} {level(args.confidence)} intervals on the raw take rate",
        "arc elasticity = midpoint formula on the monotone curve",
        "prices not asked are filled from the monotone assumption" if impute else "no imputation",
        f"bootstrap {args.bootstrap} replicates, seed {args.seed}" if args.bootstrap else "no bootstrap",
        "stated intent, not calibrated to real purchase" if binary else
        "calibrated purchase probabilities supplied by the user",
    ]
    read = len(respondents) + counts["no_answers"]
    result = {
        "version": VERSION,
        "answers": answers_desc,
        "design": design,
        "binary": binary,
        "confidence": args.confidence,
        "prices_tested": prices,
        "unit_cost": args.unit_cost,
        "counts": {"read": read, "no_answers": counts["no_answers"],
                   "unreadable_answers": counts["unreadable_cells"], "inconsistent": stats["inconsistent"],
                   "inconsistent_rule": "excluded" if args.inconsistent == "exclude" else "kept",
                   "imputed_cells": stats["imputed_cells"], "analysed": len(kept)},
        "notes": notes,
        "warnings": top_warnings,
        "conventions": conventions,
        "groups": groups,
    }
    if args.curves_csv:
        write_curves(args, result)
    return result


def write_curves(args, result):
    if args.input and os.path.exists(args.curves_csv) and os.path.samefile(args.curves_csv, args.input):
        raise InputError("--curves-csv would overwrite the input file; choose another path")
    fields = ["price", "n", "n_observed", "take_rate", "ci_low", "ci_high", "monotone_take_rate", "monotone_ci_low",
              "monotone_ci_high", "revenue_index", "profit_index", "raw_revenue_index", "raw_profit_index",
              "arc_elasticity_to_next"]
    try:
        with open(args.curves_csv, "w", newline="", encoding="utf-8") as handle:
            w = csv.writer(handle)
            w.writerow(["group"] + fields)
            for g in result["groups"]:
                for r in g["prices"]:
                    w.writerow([g["label"]] + ["" if r[f] is None else r[f] for f in fields])
    except OSError as exc:
        raise InputError(f"cannot write --curves-csv {args.curves_csv}: {exc.strerror or exc}")


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = analyse(args)
    except InputError as exc:
        print(f"gabor-granger-analysis: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, allow_nan=False))
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
