#!/usr/bin/env python3
"""Van Westendorp analysis: price sensitivity meter (OPP, IPP/IDP, PMC, PME, acceptable range) from a CSV.

Standard library only, Python 3.9+. Deterministic (the bootstrap is seeded), no network.

Usage:
  python3 scripts/van_westendorp_analysis.py answers.csv
  python3 scripts/van_westendorp_analysis.py answers.csv --json --chart psm.svg
  python3 scripts/van_westendorp_analysis.py answers.csv --segment plan --bootstrap 1000 --at 29

Default conventions (sources, alternatives and other tools' choices: references/sources.md and
references/tool-conventions.md):
  * Grid: every distinct price an analysed respondent gave.
  * too cheap(p) = share with too-cheap price >= p, cheap(p) = share with cheap price >= p (both fall);
    expensive(p) = share with expensive price <= p, too expensive(p) = share with too-expensive price <= p
    (both rise); not cheap = 1 - cheap, not expensive = 1 - expensive.  (--boundary changes this.)
  * OPP = too cheap x too expensive. IPP (also called IDP) = cheap x expensive.
  * PMC / PME, original definition (Van Westendorp 1976): too cheap x not cheap, too expensive x not
    expensive. Narrower definition: too cheap x expensive, too expensive x cheap. Both ranges are always
    printed; --range-definition picks the headline one.
  * A crossing between two neighbouring grid prices is found by linear interpolation of the difference of
    the two curves (--no-interpolate: the first grid price at which the curves have met or crossed).
    A difference of exactly zero over several neighbouring grid prices is reported as the midpoint of that
    interval, with the interval and a warning (--tie min|max|mean|midpoint).
  * A respondent is consistent when too cheap <= cheap <= expensive <= too expensive (--strict: <).
    Inconsistent respondents are excluded and counted unless --keep-inconsistent is given.
  * Newton-Miller-Smith extension: runs when both purchase-intent columns are found or named.
"""
import argparse
import bisect
import csv
import io
import json
import math
import random
import re
import sys
from fractions import Fraction
from xml.sax.saxutils import escape

VERSION = "0.2.1"
DEFAULT_MIN_N = 100
DEFAULT_INTENT_SCALE = "5,4,3,2,1"
NMS_PRESETS = {
    "sawtooth-excel": "0.7,0.5,0.3,0.1,0",
    "orme-cpg": "0.75,0.25,0.10,0,0",
    "fifths": "0.8,0.6,0.4,0.2,0",
}
DEFAULT_NMS_PRESET = "sawtooth-excel"
CONFIDENCE = 0.95
CURRENCY_CHARS = "$€£¥₴₹"
PRICE_KEYS = ("too_cheap", "cheap", "expensive", "too_expensive")
CURVE_KEYS = PRICE_KEYS + ("not_cheap", "not_expensive")
FALLING = {"too_cheap", "cheap", "not_expensive"}
LABELS = {
    "too_cheap": "too cheap",
    "cheap": "cheap",
    "expensive": "expensive",
    "too_expensive": "too expensive",
    "not_cheap": "not cheap",
    "not_expensive": "not expensive",
}
RANGE_PAIRS = {
    "original": {"pmc": ("too_cheap", "not_cheap"), "pme": ("too_expensive", "not_expensive")},
    "narrower": {"pmc": ("too_cheap", "expensive"), "pme": ("too_expensive", "cheap")},
}
POINT_NAMES = {
    "pmc": "PMC  point of marginal cheapness",
    "opp": "OPP  optimal price point",
    "ipp": "IPP  indifference price point (IDP)",
    "pme": "PME  point of marginal expensiveness",
}
COMPAT = {
    "r": {"strict": True, "boundary": "exclusive-forced-ends", "tie": "min", "r_ties": True},
    "r-1.3.0": {"strict": True, "boundary": "exclusive", "tie": "min", "no_interpolate": True},
}
BOUNDARY_TEXT = {
    "inclusive": "too cheap and cheap: share with a price >= p; expensive and too expensive: share with a price <= p",
    "exclusive": "too cheap and cheap: share with a price > p; expensive and too expensive: share with a price <= p",
    "exclusive-forced-ends": "too cheap and cheap: share with a price > p; expensive and too expensive: share with a "
                             "price <= p; at and below a question's lowest answer its curve is set to 100% (falling) "
                             "or 0% (rising)",
}
INTENT_WORDS = {"intent", "intention", "likelihood", "likely", "pi", "nms"}
# Text accepted next to a price: a currency symbol, an ISO 4217 code, or one of a few short abbreviations.
# Anything else (k, m, mo, /month) is a multiplier or a unit, which the script will not guess.
ISO_CURRENCIES = set("""
AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL BSD BTN BWP BYN BZD CAD CDF
CHF CLP CNY COP CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD
HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD
MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN
PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SYP SZL THB TJS TMT TND TOP TRY TTD
TWD TZS UAH UGX USD UYU UZS VES VND VUV WST XAF XCD XOF XPF YER ZAR ZMW ZWL
""".split())
CURRENCY_ABBREVIATIONS = {"RS", "KR", "FR", "TL", "NT", "RMB"}


class InputError(Exception):
    """Bad input: the message is shown to the user and the exit code is 2."""


# ---------------------------------------------------------------- reading

def _norm(name):
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)  # piCheap, tooExpensive
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _is_intent(norm):
    return bool(INTENT_WORDS & set(norm.split()))


def _price_kind(norm):
    """Which of the four price questions a normalised header names, or None."""
    squashed = norm.replace(" ", "")
    if any(w in squashed for w in ("toocheap", "tooinexpensive", "soinexpensive", "socheap", "doubt", "toolow")) \
            or norm == "tc":
        return "too_cheap"
    if any(w in squashed for w in ("tooexpensive", "soexpensive", "neverconsider", "toohigh")) or norm == "te":
        return "too_expensive"
    if "cheap" in squashed or "bargain" in squashed or "goodvalue" in squashed or "inexpensive" in squashed:
        return "cheap"
    if "expensive" in squashed:
        return "expensive"
    return None


def detect_columns(header, args):
    """Map roles to header names. Flags win; otherwise names are matched; ambiguity is an error."""
    explicit = {
        "too_cheap": args.too_cheap, "cheap": args.cheap, "expensive": args.expensive,
        "too_expensive": args.too_expensive, "intent_cheap": args.intent_cheap,
        "intent_expensive": args.intent_expensive, "id": args.id, "segment": args.segment, "weight": args.weight,
    }
    for role, name in explicit.items():
        if name is not None and name not in header:
            raise InputError(f"column {name!r} (given for --{role.replace('_', '-')}) is not in the file. "
                             f"Columns: {', '.join(header)}")
    found = {k: [] for k in PRICE_KEYS + ("intent_cheap", "intent_expensive", "id")}
    for name in header:
        norm = _norm(name)
        kind = _price_kind(norm)
        if norm in ("id", "respondent", "respondent id", "response id", "respondentid", "responseid"):
            found["id"].append(name)
        elif kind and _is_intent(norm):
            if kind in ("cheap", "expensive"):
                found["intent_" + kind].append(name)
        elif kind:
            found[kind].append(name)
    columns = {}
    for role in PRICE_KEYS:
        flag = "--" + role.replace("_", "-")
        if explicit[role] is not None:
            columns[role] = explicit[role]
        elif len(found[role]) == 1:
            columns[role] = found[role][0]
        elif not found[role] and role == "too_cheap":
            columns[role] = None  # three-question variant; reported, never silent
        elif not found[role]:
            raise InputError(f"no column found for the {LABELS[role]!r} price. Name it with {flag}. "
                             f"Columns: {', '.join(header)}")
        else:
            raise InputError(f"several columns could be the {LABELS[role]!r} price: {', '.join(found[role])}. "
                             f"Pick one with {flag}.")
    for role in ("intent_cheap", "intent_expensive"):
        flag = "--" + role.replace("_", "-")
        if args.no_nms:
            columns[role] = None
        elif explicit[role] is not None:
            columns[role] = explicit[role]
        elif len(found[role]) == 1:
            columns[role] = found[role][0]
        elif not found[role]:
            columns[role] = None
        else:
            raise InputError(f"several columns could be the purchase intent at the {role.split('_')[1]} price: "
                             f"{', '.join(found[role])}. Pick one with {flag}, or pass --no-nms.")
    used = [v for v in columns.values() if v]
    if len(set(used)) != len(used):
        raise InputError("the price and purchase-intent columns must be different columns; got " +
                         ", ".join(f"{k}={v}" for k, v in columns.items() if v))
    if (columns["intent_cheap"] is None) != (columns["intent_expensive"] is None):
        have = "intent_cheap" if columns["intent_cheap"] else "intent_expensive"
        raise InputError(f"found only one purchase-intent column ({columns[have]}). The Newton-Miller-Smith extension "
                         "needs both: name them with --intent-cheap and --intent-expensive, or pass --no-nms.")
    columns["id"] = explicit["id"] if explicit["id"] is not None else (found["id"][0] if len(found["id"]) == 1 else None)
    columns["segment"] = explicit["segment"]
    columns["weight"] = explicit["weight"]
    taken = {v for v in columns.values() if v}
    args.unused_columns = [h for h in header if h not in taken] if columns["too_cheap"] is None else []
    return columns


def parse_price(text, decimal, where, markers):
    """Blank -> None. A number, with an optional currency symbol or code -> float. Anything else -> InputError."""
    raw = text.strip().replace(" ", " ")
    if raw == "":
        return None
    unit = r"(?:[A-Za-z]{1,3}\.?|[%s])" % re.escape(CURRENCY_CHARS)
    match = re.fullmatch(r"(%s)?\s*(-?)\s*(%s)?\s*([\d.,]+)\s*(%s)?" % (unit, unit, unit), raw)
    fail = InputError(f"{where}: {text.strip()!r} is not a price. Fix the cell, or list tokens that mean "
                      "'no answer' with --na.")
    if not match:
        raise fail
    cleaned = match.group(4)
    for marker in (match.group(1), match.group(3), match.group(5)):
        if marker:
            code = marker.rstrip(".").upper()
            if code not in ISO_CURRENCIES and code not in CURRENCY_ABBREVIATIONS and code not in CURRENCY_CHARS:
                raise InputError(f"{where}: {text.strip()!r} carries {marker!r}, which is not a currency symbol or "
                                 "code. If it is a multiplier or a unit (k, m, mo), write the price as a plain number "
                                 "in one unit for every respondent.")
            markers.add(code)
    thousands = "," if decimal == "point" else "."
    mark = "." if decimal == "point" else ","
    grouped = re.fullmatch(r"\d{1,3}(%s\d{3})+(%s\d+)?" % (re.escape(thousands), re.escape(mark)), cleaned)
    plain = re.fullmatch(r"\d+(%s\d+)?|%s\d+" % (re.escape(mark), re.escape(mark)), cleaned)
    if not (grouped or plain):
        if decimal == "point" and re.fullmatch(r"\d+,\d{1,2}", cleaned):
            raise InputError(f"{where}: {text.strip()!r} is not a price. If the file uses a decimal comma, pass "
                             "--decimal comma.")
        raise fail
    value = float(cleaned.replace(thousands, "").replace(mark, "."))
    return -value if match.group(2) else value


def parse_scale(args):
    """Map each purchase-intent answer (as text) to its purchase probability."""
    if args.nms_weights and args.nms_preset:
        raise InputError("give --nms-weights or --nms-preset, not both.")
    spec = args.nms_weights or NMS_PRESETS[args.nms_preset or DEFAULT_NMS_PRESET]
    values = [v.strip() for v in args.intent_scale.split(",") if v.strip()]
    try:
        weights = [float(w) for w in spec.split(",")]
    except ValueError:
        raise InputError(f"--nms-weights must be numbers separated by commas; got {spec!r}.")
    if len(values) != len(weights) or len(set(values)) != len(values):
        raise InputError("--intent-scale and the purchase-probability weights must list the same number of distinct "
                         f"scale points (got {len(values)} and {len(weights)}).")
    if any(w < 0 or w > 1 for w in weights):
        raise InputError("purchase-probability weights must each be between 0 and 1.")
    if any(a < b for a, b in zip(weights, weights[1:])):
        raise InputError("purchase-probability weights must not increase: list the scale from highest to lowest intent.")
    return dict(zip(values, weights))


def read_rows(path, args):
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            text = handle.read()
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}")
    except UnicodeDecodeError:
        raise InputError(f"{path} is not UTF-8 text. Export the data as a UTF-8 CSV.")
    if not text.strip() or not text.splitlines()[0].strip():
        raise InputError(f"{path} is empty or has no header row.")

    def records(sep):
        # Records, not physical lines: a quoted cell may hold a line break (Qualtrics question text).
        return csv.reader(io.StringIO(text, newline=""), delimiter=sep)

    delimiter = args.delimiter
    if delimiter is None:
        # Count fields with the csv reader, so separators inside quoted header names do not count.
        counts = {d: len(next(records(d))) for d in (",", ";", "\t")}
        best = max(counts.values())
        if best == 1:
            raise InputError("the header row has a single column. Expected a CSV with the price columns; "
                             "set the separator with --delimiter if it is not a comma, semicolon or tab.")
        delimiter = "," if counts[","] == best else max(counts, key=lambda d: counts[d])
    elif delimiter == "\\t":
        delimiter = "\t"
    try:
        table = list(records(delimiter))
    except csv.Error as exc:
        raise InputError(f"{path} could not be read as CSV: {exc}")
    skip = args.skip_rows
    if skip is None:
        # Qualtrics puts the question text and an {"ImportId": ...} row under the header.
        skip = next((i + 1 for i, row in enumerate(table[1:3]) if any("ImportId" in c for c in row)), 0)
        if skip:
            args.skipped_note = (f"Skipped {skip} row(s) under the header: a Qualtrics export's question-text and "
                                 "ImportId rows (pass --skip-rows 0 to keep them).")
    if skip < 0:
        raise InputError("--skip-rows must be 0 or more.")
    reader = iter(table[:1] + table[1 + skip:])
    header = [h.strip() for h in next(reader)]
    if len(set(header)) != len(header):
        raise InputError("the header row repeats a column name; column names must be unique.")
    columns = detect_columns(header, args)
    index = {name: i for i, name in enumerate(header)}
    na = {t.strip().lower() for t in args.na.split(",") if t.strip()} if args.na else set()
    scale = parse_scale(args)
    if columns["intent_cheap"] and not args.intent_scale_given:
        raise InputError("purchase-intent columns found, but the scale direction is not stated. Read the codebook "
                         "and pass --intent-scale with the answers highest intent first: --intent-scale 5,4,3,2,1 if 5 "
                         "means 'definitely would buy', --intent-scale 1,2,3,4,5 if 1 does. Or pass --no-nms.")
    rows, markers = [], set()
    for line_no, cells in enumerate(reader, start=2 + skip):
        if not any(c.strip() for c in cells):
            continue
        if len(cells) > len(header):
            if any(c.strip() for c in cells[len(header):]):
                raise InputError(f"line {line_no} has {len(cells)} fields but the header has {len(header)}. A price "
                                 "written with a thousands separator that is also the delimiter (1,000 in a comma "
                                 "file) splits the cell; quote it or remove the separator.")
            cells = cells[:len(header)]
        if len(cells) < len(header):
            cells = cells + [""] * (len(header) - len(cells))

        def cell(role):
            value = cells[index[columns[role]]]
            return "" if value.strip().lower() in na else value

        rid = cells[index[columns["id"]]].strip() if columns["id"] else ""
        row = {"id": rid or f"row {line_no}", "line": line_no, "weight": 1, "segment": None}
        for role in PRICE_KEYS:
            row[role] = None if columns[role] is None else parse_price(
                cell(role), args.decimal, f"line {line_no}, column {columns[role]!r}", markers)
        if columns["intent_cheap"]:
            for role in ("intent_cheap", "intent_expensive"):
                value = cell(role).strip()
                if value == "":
                    row[role] = None
                elif value in scale:
                    row[role] = scale[value]
                else:
                    raise InputError(f"line {line_no}, column {columns[role]!r}: {value!r} is not on the purchase-intent "
                                     f"scale ({', '.join(scale)}). Set the scale with --intent-scale (highest intent first).")
        if columns["weight"]:
            value = cells[index[columns["weight"]]].strip()
            try:
                row["weight"] = Fraction(value)
            except (ValueError, ZeroDivisionError):
                raise InputError(f"line {line_no}, column {columns['weight']!r}: {value!r} is not a weight. Every "
                                 "respondent needs a non-negative number.")
            if row["weight"] < 0:
                raise InputError(f"line {line_no}, column {columns['weight']!r}: a weight cannot be negative.")
        if columns["segment"]:
            row["segment"] = cells[index[columns["segment"]]].strip() or "(blank)"
        rows.append(row)
    if not rows:
        raise InputError(f"{path} has a header but no respondents.")
    return rows, columns, sorted(markers)


# ---------------------------------------------------------------- price sensitivity meter

def classify(rows, keys, opts):
    """Split rows into incomplete, out of the price limits, inconsistent and consistent."""
    incomplete, outside, inconsistent, consistent, ties = [], [], [], [], 0
    for row in rows:
        prices = [row[k] for k in keys]
        if any(p is None for p in prices):
            incomplete.append(row)
        elif (opts.min_price is not None and min(prices) < opts.min_price) or \
                (opts.max_price is not None and max(prices) > opts.max_price):
            outside.append(row)
        else:
            pairs = list(zip(prices, prices[1:]))
            if all(a < b for a, b in pairs) if opts.strict else all(a <= b for a, b in pairs):
                consistent.append(row)
                ties += any(a == b for a, b in pairs)
            else:
                inconsistent.append(row)
    return incomplete, outside, inconsistent, consistent, ties


class CurveEvaluator:
    """Weighted count on one question's curve at any price. The grid and the --at report both use it."""

    def __init__(self, rows, key, boundary, total):
        pairs = sorted((r[key], r["weight"]) for r in rows)
        self.values = [v for v, _ in pairs]
        self.prefix = [0]
        for _, w in pairs:
            self.prefix.append(self.prefix[-1] + w)
        self.falling = key in FALLING
        self.boundary = boundary
        self.total = total

    def __call__(self, p):
        if self.falling:
            cut = bisect.bisect_left(self.values, p) if self.boundary == "inclusive" else bisect.bisect_right(self.values, p)
            value = self.total - self.prefix[cut]
        else:
            value = self.prefix[bisect.bisect_right(self.values, p)]
        if self.boundary == "exclusive-forced-ends" and p <= self.values[0]:
            value = self.total if self.falling else 0
        return value


def build_curves(rows, keys, boundary):
    """Weighted counts on the grid of all distinct prices. Counts stay exact (int or Fraction)."""
    grid = sorted({row[k] for row in rows for k in keys})
    total = sum(r["weight"] for r in rows)
    counts = {}
    for key in keys:
        evaluate = CurveEvaluator(rows, key, boundary, total)
        counts[key] = [evaluate(p) for p in grid]
    if "cheap" in counts:
        counts["not_cheap"] = [total - c for c in counts["cheap"]]
        counts["not_expensive"] = [total - c for c in counts["expensive"]]
    return grid, counts, total


def _tie(prices, rule):
    if rule == "min":
        return prices[0]
    if rule == "max":
        return prices[-1]
    if rule == "mean":
        return sum(prices) / len(prices)
    return (prices[0] + prices[-1]) / 2


def crossing(grid, falling, rising, interpolate=True, tie="midpoint", r_ties=False):
    """Where a falling and a rising curve (exact counts on the grid) cross. Rules: module docstring.

    r_ties (--compat r): R pricesensitivitymeter 1.3.3 takes a crossing at every sign change of the
    difference, so a run of coinciding prices gives its first price and, only when the curves part again
    before the highest observed price, its last price; --tie then picks from those one or two prices.
    """
    diff = [a - b for a, b in zip(falling, rising)]
    first = next((i for i, d in enumerate(diff) if d <= 0), None)
    if first is None or (first == 0 and diff[0] < 0):
        return {"price": None, "status": "no_crossing"}
    if not interpolate:
        run = [first]
        while run[-1] + 1 < len(grid) and falling[run[-1] + 1] == falling[first] and rising[run[-1] + 1] == rising[first]:
            run.append(run[-1] + 1)
        prices = [grid[i] for i in run]
        result = {"price": _tie(prices, tie), "status": "first_met", "at": grid[first]}
        if len(prices) > 1:
            result["interval"] = [prices[0], prices[-1]]
        return result
    if diff[first] == 0:
        run = [first]
        while run[-1] + 1 < len(grid) and diff[run[-1] + 1] == 0:
            run.append(run[-1] + 1)
        prices = [grid[i] for i in run]
        if len(prices) == 1:
            return {"price": prices[0], "status": "exact", "at": prices[0]}
        if r_ties:
            ends = [prices[0]] + ([prices[-1]] if run[-1] + 1 < len(grid) else [])
            return {"price": _tie(ends, tie), "status": "flat", "interval": [prices[0], prices[-1]]}
        return {"price": _tie(prices, tie), "status": "flat", "interval": [prices[0], prices[-1]]}
    x1, x2, d1, d2 = grid[first - 1], grid[first], diff[first - 1], diff[first]
    return {"price": x1 + (x2 - x1) * float(Fraction(d1) / Fraction(d1 - d2)), "status": "interpolated",
            "between": [x1, x2]}


def price_points(grid, counts, opts):
    def point(a, b):
        if a not in counts or b not in counts:
            return {"price": None, "status": "unavailable", "curves": [LABELS[a], LABELS[b]]}
        fall, rise = (a, b) if a in FALLING else (b, a)
        result = crossing(grid, counts[fall], counts[rise], not opts.no_interpolate, opts.tie,
                          getattr(opts, "r_ties", False))
        result["curves"] = [LABELS[a], LABELS[b]]
        return result

    points = {
        "pmc": point(*RANGE_PAIRS[opts.range_definition]["pmc"]),
        "opp": point("too_cheap", "too_expensive"),
        "ipp": point("cheap", "expensive"),
        "pme": point(*RANGE_PAIRS[opts.range_definition]["pme"]),
    }
    points["ipp"]["alias"] = "IDP"
    other = "narrower" if opts.range_definition == "original" else "original"
    alternative = {"definition": other, "pmc": point(*RANGE_PAIRS[other]["pmc"]), "pme": point(*RANGE_PAIRS[other]["pme"])}
    return points, alternative


def shares_at(rows, keys, price, boundary, total):
    """Share on each curve at one candidate price, from the same evaluator as the curves (so --compat r's
    pinned ends apply here too)."""
    def share(count):
        return float(Fraction(count) / Fraction(total))

    out = {"price": price}
    for key in keys:
        out[key] = share(CurveEvaluator(rows, key, boundary, total)(price))
    out["not_cheap"] = 1 - out["cheap"]
    out["not_expensive"] = 1 - out["expensive"]
    if "too_cheap" in keys:
        # Respondent by respondent: neither of the two rejections applies at this price.
        pinned = boundary == "exclusive-forced-ends"
        forced = pinned and price <= min(r["too_cheap"] for r in rows)
        # The pinned lower end of the too-expensive curve: nobody rejects a price at or below its lowest value.
        no_te = pinned and price <= min(r["too_expensive"] for r in rows)
        strict_fall = boundary != "inclusive"
        out["neither_too_cheap_nor_too_expensive"] = 0.0 if forced else share(sum(
            r["weight"] for r in rows
            if not (r["too_cheap"] > price if strict_fall else r["too_cheap"] >= price)
            and (no_te or not r["too_expensive"] <= price)))
    return out


def quantile(values, q):
    """Linear-interpolated quantile of sorted values (position (n - 1) * q)."""
    pos = (len(values) - 1) * q
    low = math.floor(pos)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (pos - low)


def bootstrap(rows, keys, opts):
    """Percentile intervals for the four points from seeded resampling of respondents."""
    rng = random.Random(opts.seed)
    draws = {k: [] for k in ("pmc", "opp", "ipp", "pme")}
    widths = []
    for _ in range(opts.bootstrap):
        sample = rng.choices(rows, k=len(rows))
        if sum(r["weight"] for r in sample) == 0:
            continue
        grid, counts, _ = build_curves(sample, keys, opts.boundary)
        points, _ = price_points(grid, counts, opts)
        for key, value in points.items():
            if value["price"] is not None:
                draws[key].append(value["price"])
        if points["pmc"]["price"] is not None and points["pme"]["price"] is not None:
            # The width is formed within each resample: the two ends move together.
            widths.append(points["pme"]["price"] - points["pmc"]["price"])
    tail = (1 - CONFIDENCE) / 2
    intervals = {}
    for key, values in draws.items():
        values.sort()
        intervals[key] = {"low": quantile(values, tail), "high": quantile(values, 1 - tail),
                          "resamples_with_a_value": len(values)} if values else \
            {"low": None, "high": None, "resamples_with_a_value": 0}
    widths.sort()
    width = {"low": quantile(widths, tail), "high": quantile(widths, 1 - tail), "resamples_with_a_value": len(widths)} \
        if widths else {"low": None, "high": None, "resamples_with_a_value": 0}
    return {"resamples": opts.bootstrap, "seed": opts.seed, "confidence": CONFIDENCE, "method": "percentile",
            "intervals": intervals, "range_width": width}


# ---------------------------------------------------------------- Newton-Miller-Smith

def purchase_probability(row, price, variant, p_low, p_high, side="at"):
    """One respondent's purchase probability at a price, or its limit from just below or above (side).

    Stated answers win at the respondent's own cheap and expensive prices (the mean of the two when the
    prices are equal). Otherwise p_low at or below too cheap and p_high at or above too expensive, and
    linear in between. variant 'modified' (and any respondent without a too-cheap price) holds the
    cheap-price probability for every price below cheap. Where two of a respondent's prices are equal the
    function jumps, so the value at that price and its one-sided limits differ.
    """
    tc, c, e, te = (row[k] for k in PRICE_KEYS)
    pc, pe = row["intent_cheap"], row["intent_expensive"]
    if side == "at":
        if price == c and price == e:
            return (pc + pe) / 2
        if price == c:
            return pc
        if price == e:
            return pe
        below_c, below_e = price < c, price < e
        low_end = tc is not None and price <= tc
        high_end = price >= te
    elif side == "below":  # limit as the price rises to this value
        below_c, below_e = price <= c, price <= e
        low_end = tc is not None and price <= tc
        high_end = price > te
    else:  # "above": limit as the price falls to this value
        below_c, below_e = price < c, price < e
        low_end = tc is not None and price < tc
        high_end = price >= te
    if below_c:
        if variant == "modified" or tc is None:
            return pc
        return p_low if low_end else p_low + (pc - p_low) * (price - tc) / (c - tc)
    if below_e:
        return pc + (pe - pc) * (price - c) / (e - c)
    return p_high if high_end else pe + (p_high - pe) * (price - e) / (te - e)


def nms_analysis(rows, grid, opts):
    usable = [r for r in rows if r["intent_cheap"] is not None and r["intent_expensive"] is not None]
    total = float(sum(r["weight"] for r in usable))
    if not usable or total == 0:
        return None, 0, 0

    def mean_probability(price, side):
        return sum(float(r["weight"]) * purchase_probability(r, price, opts.nms_variant, opts.nms_too_cheap_prob,
                                                             opts.nms_too_expensive_prob, side) for r in usable) / total

    # Every respondent's own prices are grid prices, so between two neighbouring grid prices each respondent
    # (and so the mean) is linear: it runs from the limit just above the left price to the limit just below
    # the right one. At a grid price the value can differ from both limits when a respondent gave two
    # questions the same price.
    trial = [mean_probability(p, "at") for p in grid]
    below = [mean_probability(p, "below") for p in grid]
    above = [mean_probability(p, "above") for p in grid]
    revenue = [p * t for p, t in zip(grid, trial)]
    best_trial = max(trial)
    trial_prices = [p for p, t in zip(grid, trial) if t == best_trial]
    grid_rev = max(revenue)
    at = revenue.index(grid_rev)
    best_price, best_rev, best_rev_trial = grid[at], grid_rev, trial[at]
    for i in range(len(grid) - 1):
        x1, x2, t1, t2 = grid[i], grid[i + 1], above[i], below[i + 1]
        slope = (t2 - t1) / (x2 - x1)
        if slope >= 0:
            continue
        vertex = -(t1 - slope * x1) / (2 * slope)
        if x1 < vertex < x2:
            t = t1 + slope * (vertex - x1)
            if vertex * t > best_rev * (1 + 1e-12):
                best_price, best_rev, best_rev_trial = vertex, vertex * t, t
    # A one-sided limit can beat every price actually evaluated (a jump at a tied price). It is not attained,
    # so it is reported separately, with the side from which a price approaches it.
    approached = None
    for i, p in enumerate(grid):
        for side, values in (("below", below), ("above", above)):
            if side == "above" and i == len(grid) - 1:  # above the highest price the curve is flat at p_high
                continue
            if p * values[i] > best_rev * (1 + 1e-9) and (approached is None or p * values[i] > approached["revenue_index"]):
                approached = {"price": p, "side": side, "revenue_index": p * values[i], "trial": values[i]}
    trial_approached = None
    for i, p in enumerate(grid):
        for side, values in (("below", below), ("above", above)):
            if side == "above" and i == len(grid) - 1:  # above the highest price the curve is flat at p_high
                continue
            if values[i] > best_trial + 1e-12 and (trial_approached is None or values[i] > trial_approached["trial"]):
                trial_approached = {"price": p, "side": side, "trial": values[i]}
    reversed_intent = sum(1 for r in usable if r["intent_expensive"] > r["intent_cheap"])
    curve = []
    for i, (p, t, r) in enumerate(zip(grid, trial, revenue)):
        row = {"price": p, "trial": t, "revenue_index": r}
        if i > 0 and abs(below[i] - t) > 1e-12:
            row["trial_just_below"] = below[i]
        if i < len(grid) - 1 and abs(above[i] - t) > 1e-12:
            row["trial_just_above"] = above[i]
        curve.append(row)
    result = {
        "n": len(usable),
        "variant": opts.nms_variant,
        "probability_at_too_cheap": opts.nms_too_cheap_prob,
        "probability_at_too_expensive": opts.nms_too_expensive_prob,
        "trial_max": {"price": trial_prices[0], "trial": best_trial, "tied_prices": trial_prices[1:]},
        "trial_max_approached": trial_approached,
        "revenue_max": {"price": best_price, "revenue_index": best_rev, "trial": best_rev_trial,
                        "on_grid": best_price in grid},
        "revenue_max_approached": approached,
        "revenue_max_on_grid": {"price": grid[at], "revenue_index": grid_rev},
        "curve": curve,
    }
    return result, len(rows) - len(usable), reversed_intent


# ---------------------------------------------------------------- analysis

def analyse(rows, columns, opts, scale):
    """Analyse one set of rows (the whole file or one segment)."""
    warnings = []
    three = columns["too_cheap"] is None or all(r["too_cheap"] is None for r in rows)
    keys = PRICE_KEYS[1:] if three else PRICE_KEYS
    incomplete, outside, inconsistent, consistent, ties = classify(rows, keys, opts)
    analysed = sorted(consistent + inconsistent if opts.keep_inconsistent else consistent, key=lambda r: r["line"])
    sign = " < " if opts.strict else " <= "
    rule = sign.join(LABELS[k] for k in keys)
    if not analysed:
        raise InputError(f"no respondent is left to analyse: {len(rows)} read, {len(incomplete)} incomplete, "
                         f"{len(outside)} outside the price limits, {len(inconsistent)} inconsistent ({rule}). "
                         "Check the column mapping: " + ", ".join(f"{LABELS[k]}={columns[k]!r}" for k in keys))
    total = sum(r["weight"] for r in analysed)
    if total == 0:
        raise InputError("the analysed respondents have a total weight of zero.")
    # Zero-weight respondents are counted in the audit but take no part in the estimate: their prices would
    # otherwise add grid points (and move interpolated crossings) and count toward the base.
    estimated = [r for r in analysed if r["weight"] > 0]
    zero_weight = len(analysed) - len(estimated)
    if zero_weight:
        warnings.append(f"{zero_weight} analysed respondent(s) have weight 0: counted here, left out of the curves, "
                        "the price points, the bootstrap and the base.")
    if three:
        warnings.append("Three-question variant: there is no too-cheap price, so OPP (too cheap x too expensive) and "
                        "PMC (too cheap x not cheap, or too cheap x expensive) cannot be computed. IPP and PME are reported."
                        + (f" Columns not used: {', '.join(opts.unused_columns)}; if one is the too-cheap question, "
                           "name it with --too-cheap." if getattr(opts, "unused_columns", None) else ""))
    if incomplete:
        warnings.append(f"{len(incomplete)} respondent(s) left out: at least one price is missing.")
    if outside:
        limits = " and ".join(t for t in (f"below {fmt(opts.min_price)}" if opts.min_price is not None else "",
                                          f"above {fmt(opts.max_price)}" if opts.max_price is not None else "") if t)
        warnings.append(f"{len(outside)} respondent(s) excluded: a price {limits} (--min-price / --max-price).")
    if inconsistent:
        share = 100 * len(inconsistent) / (len(inconsistent) + len(consistent))
        action = "KEPT (--keep-inconsistent)" if opts.keep_inconsistent else "excluded"
        warnings.append(f"{len(inconsistent)} inconsistent respondent(s) {action}: prices not in the order {rule} "
                        f"({share:.1f}% of complete respondents).")
    if ties and not opts.strict:
        warnings.append(f"{ties} analysed respondent(s) gave the same price to two neighbouring questions; "
                        "they count as consistent. Pass --strict to exclude them.")
    not_positive = sum(1 for r in analysed if min(r[k] for k in keys) <= 0)
    if not_positive:
        warnings.append(f"{not_positive} analysed respondent(s) gave a price of zero or less. They are included "
                        "unchanged; exclude them with --min-price if they are not real answers.")
    if len(estimated) < opts.min_n:
        warnings.append(f"Small sample: n = {len(estimated)} analysed with a positive weight, below {opts.min_n}. "
                        "Treat the result as directional.")

    grid, counts, total = build_curves(estimated, keys, opts.boundary)
    points, alternative = price_points(grid, counts, opts)
    for key, point in points.items():
        name = key.upper()
        if point["status"] == "no_crossing":
            warnings.append(f"{name}: the {point['curves'][0]} and {point['curves'][1]} curves do not cross "
                            "on the observed prices; no value is reported.")
        elif point["status"] == "flat":
            low, high = point["interval"]
            warnings.append(f"{name}: the {point['curves'][0]} and {point['curves'][1]} curves coincide from "
                            f"{fmt(low)} to {fmt(high)}; {fmt(point['price'])} is reported (--tie {opts.tie}"
                            f"{', R rule' if getattr(opts, 'r_ties', False) else ''}). "
                            "Read it as that interval, not as a point.")
    pmc, pme, opp, ipp = (points[k]["price"] for k in ("pmc", "pme", "opp", "ipp"))
    if pmc is not None and pme is not None and pmc > pme:
        warnings.append("PMC is above PME, so there is no acceptable range under this definition. "
                        "Check the column mapping and whether the file pools different segments.")
    elif pmc is not None and pmc == pme:
        warnings.append("PMC equals PME: the acceptable range has no width. This happens with very few respondents "
                        "or when almost everyone names the same prices.")
    if opp is not None and ipp is not None and ipp < opp:
        warnings.append("IPP is below OPP, which is unusual. Check the column mapping, the sample size and whether "
                        "the file pools segments with different price levels.")

    nms = None
    if columns["intent_cheap"]:
        out_of_order = {id(r) for r in inconsistent}
        nms, missing_intent, reversed_intent = nms_analysis([r for r in estimated if id(r) not in out_of_order], grid, opts)
        kept_out = sum(1 for r in estimated if id(r) in out_of_order)
        if kept_out:
            warnings.append(f"Newton-Miller-Smith extension: {kept_out} kept inconsistent respondent(s) left out; with "
                            "prices out of order their purchase-probability line is not defined.")
        if nms is None:
            warnings.append("Newton-Miller-Smith extension skipped: no analysed respondent answered both "
                            "purchase-intent questions.")
        else:
            nms["weights"] = scale
            if three:
                nms["variant"] = "modified"
                warnings.append("Newton-Miller-Smith extension: without a too-cheap price the cheap-price probability "
                                "is held for every lower price (the modified variant).")
            if missing_intent:
                warnings.append(f"Newton-Miller-Smith extension: {missing_intent} analysed respondent(s) left out "
                                "(a purchase-intent answer is missing).")
            if reversed_intent:
                warnings.append(f"Newton-Miller-Smith extension: {reversed_intent} respondent(s) stated a higher "
                                "purchase intent at their expensive price than at their cheap price.")
            for key, what in (("revenue_max_approached", "revenue"), ("trial_max_approached", "trial")):
                near = nms[key]
                if near:
                    where = "just below" if near["side"] == "below" else "just above"
                    warnings.append(
                        f"Newton-Miller-Smith extension: the highest {what} is approached {where} {fmt(near['price'])} "
                        f"(trial {pct(near['trial'])}), where respondents who gave two questions the same price make "
                        f"the purchase probability jump; at {fmt(near['price'])} itself it is lower. Report a price "
                        f"{where} {fmt(near['price'])}, not {fmt(near['price'])}.")
            if nms["trial_max"]["tied_prices"]:
                warnings.append("Newton-Miller-Smith extension: several prices share the maximum trial; "
                                "the lowest is reported.")

    boot = None
    if opts.bootstrap:
        boot = bootstrap(estimated, keys, opts)
        width = boot["range_width"]
        if width["low"] is not None and width["low"] <= 0:
            warnings.append(f"Bootstrap: the {pct(CONFIDENCE, 0)} interval of the range width (PME minus PMC, "
                            f"{fmt(width['low'])} to {fmt(width['high'])} over {width['resamples_with_a_value']} "
                            "resamples) reaches zero or below, so this sample does not show a range of positive width.")

    def share(value):
        return float(Fraction(value) / Fraction(total))

    return {
        "respondents": {
            "read": len(rows),
            "incomplete": len(incomplete),
            "outside_price_limits": len(outside),
            "outside_price_limits_ids": [r["id"] for r in outside],
            "inconsistent": len(inconsistent),
            "inconsistent_ids": [r["id"] for r in inconsistent],
            "inconsistent_kept": bool(opts.keep_inconsistent),
            "with_tied_prices": ties,
            "analysed": len(analysed),
            "zero_weight": zero_weight,
            "estimated": len(estimated),
            "weight_total": float(total),
            "consistency_rule": rule,
        },
        "questions": 3 if three else 4,
        "price_points": points,
        "acceptable_range": {"low": pmc, "high": pme, "definition": opts.range_definition},
        "alternative_range": {"low": alternative["pmc"]["price"], "high": alternative["pme"]["price"],
                              "definition": alternative["definition"],
                              "pmc_curves": alternative["pmc"]["curves"], "pme_curves": alternative["pme"]["curves"]},
        "price_summary": {k: {"min": min(r[k] for r in estimated),
                              "median": quantile(sorted(r[k] for r in estimated), 0.5),
                              "max": max(r[k] for r in estimated)} for k in keys},
        "at": [shares_at(estimated, keys, p, opts.boundary, total) for p in opts.at],
        "bootstrap": boot,
        "curves": [dict({"price": p}, **{k: share(counts[k][i]) for k in CURVE_KEYS if k in counts})
                   for i, p in enumerate(grid)],
        "nms": nms,
        "warnings": warnings,
    }


def run(rows, columns, markers, opts, scale):
    result = {"skill": "van-westendorp-analysis", "version": VERSION, "columns": columns}
    result.update(analyse(rows, columns, opts, scale))
    pairs = RANGE_PAIRS[opts.range_definition]
    result["conventions"] = {
        "compat": opts.compat,
        "range_definition": opts.range_definition,
        "pmc": " x ".join(LABELS[k] for k in pairs["pmc"]),
        "pme": " x ".join(LABELS[k] for k in pairs["pme"]),
        "opp": "too cheap x too expensive",
        "ipp": "cheap x expensive (IPP, also called IDP)",
        "boundary": opts.boundary,
        "curves": BOUNDARY_TEXT[opts.boundary] + "; not cheap = 1 - cheap; not expensive = 1 - expensive",
        "grid": "every distinct price given by an analysed respondent",
        "interpolation": "none: the first grid price at which the two curves have met or crossed"
                         if opts.no_interpolate else "linear between neighbouring grid prices",
        "tie": opts.tie,
        "weights": columns["weight"] or "none (every respondent counts once)",
    }
    if getattr(opts, "skipped_note", None):
        result["warnings"].insert(0, opts.skipped_note)
    if len(markers) > 1:
        result["warnings"].append("The prices carry different currency markers (" + ", ".join(markers) +
                                  "). The script does not convert currencies; analyse one currency at a time.")
    result["currency_markers"] = markers
    if columns["segment"]:
        names = sorted({r["segment"] for r in rows})
        result["segments"] = {}
        for name in names:
            subset = [r for r in rows if r["segment"] == name]
            try:
                result["segments"][name] = analyse(subset, columns, opts, scale)
            except InputError as exc:
                result["segments"][name] = {"error": str(exc)}
    return result


# ---------------------------------------------------------------- output

def fmt(value):
    return "n/a" if value is None else f"{value:,.2f}"


def pct(value, digits=1):
    return f"{100 * value:.{digits}f}%"


def describe(point):
    status = point["status"]
    if status == "exact":
        return f"curves meet exactly at {fmt(point['at'])}"
    if status == "interpolated":
        return f"interpolated between {fmt(point['between'][0])} and {fmt(point['between'][1])}"
    if status == "flat":
        return f"curves coincide from {fmt(point['interval'][0])} to {fmt(point['interval'][1])}"
    if status == "first_met":
        return f"first observed price where the curves have met or crossed ({fmt(point['at'])})"
    if status == "unavailable":
        return "needs the too-cheap question"
    return "curves do not cross"


def render_text(result, show_curves):
    r = result["respondents"]
    c = result["conventions"]
    out = ["Van Westendorp price sensitivity meter", ""]
    out.append("Respondents")
    out.append(f"  read                 {r['read']}")
    out.append(f"  incomplete           {r['incomplete']}  (left out)")
    if r["outside_price_limits"]:
        out.append(f"  outside price limits {r['outside_price_limits']}  (excluded; ids: "
                   + ", ".join(r["outside_price_limits_ids"][:20]) + ")")
    kept = "kept (--keep-inconsistent)" if r["inconsistent_kept"] else "excluded"
    out.append(f"  inconsistent         {r['inconsistent']}  ({kept}; rule: {r['consistency_rule']})")
    if r["inconsistent_ids"]:
        ids = r["inconsistent_ids"]
        out.append("    ids: " + ", ".join(ids[:20]) + (f", and {len(ids) - 20} more" if len(ids) > 20 else ""))
    out.append(f"  analysed             {r['analysed']}" +
               (f"  (weighted total {r['weight_total']:g})" if result["columns"]["weight"] else ""))
    out.append("")
    out.append("Columns: " + "; ".join(f"{LABELS.get(k, k.replace('_', ' '))} = {v}"
                                       for k, v in result["columns"].items() if v and k != "id"))
    out.append("Answers (min / median / max): " + "; ".join(
        f"{LABELS[k]} {fmt(v['min'])} / {fmt(v['median'])} / {fmt(v['max'])}" for k, v in result["price_summary"].items()))
    out.append("")
    boot = result["bootstrap"]
    head = f"{'Price point':<40}{'Price':>12}  {'Curves':<32}"
    out.append(head + (f"{pct(boot['confidence'], 0) + ' interval':<24}" if boot else "") + "How found")
    for key in ("pmc", "opp", "ipp", "pme"):
        p = result["price_points"][key]
        line = f"{POINT_NAMES[key]:<40}{fmt(p['price']):>12}  {' x '.join(p['curves']):<32}"
        if boot:
            iv = boot["intervals"][key]
            line += f"{(fmt(iv['low']) + ' to ' + fmt(iv['high'])):<24}"
        out.append(line + describe(p))
    out.append("")
    rng, alt = result["acceptable_range"], result["alternative_range"]
    out.append(f"Acceptable price range, {rng['definition']} definition ({c['pmc']}; {c['pme']}): "
               f"{fmt(rng['low'])} to {fmt(rng['high'])}")
    out.append(f"Acceptable price range, {alt['definition']} definition ({' x '.join(alt['pmc_curves'])}; "
               f"{' x '.join(alt['pme_curves'])}): {fmt(alt['low'])} to {fmt(alt['high'])}")
    if boot:
        out.append(f"Intervals: percentile bootstrap, {boot['resamples']} resamples of respondents, seed {boot['seed']}.")
    for row in result["at"]:
        out.append("")
        out.append(f"At a price of {fmt(row['price'])}: " + "; ".join(
            f"{LABELS[k]} {pct(row[k])}" for k in CURVE_KEYS if k in row))
        if "neither_too_cheap_nor_too_expensive" in row:
            out.append(f"  neither too cheap nor too expensive: {pct(row['neither_too_cheap_nor_too_expensive'])}")
    if "segments" in result:
        out.append("")
        out.append(f"By segment ({result['columns']['segment']})")
        out.append(f"  {'Segment':<20}{'n':>6}{'PMC':>12}{'OPP':>12}{'IPP':>12}{'PME':>12}")
        for name, seg in result["segments"].items():
            if "error" in seg:
                out.append(f"  {name:<20}  not analysed: {seg['error']}")
                continue
            p = seg["price_points"]
            out.append(f"  {name:<20}{seg['respondents']['analysed']:>6}" +
                       "".join(f"{fmt(p[k]['price']):>12}" for k in ("pmc", "opp", "ipp", "pme")))
        for name, seg in result["segments"].items():
            for w in seg.get("warnings", []):
                out.append(f"  - {name}: {w}")
    out.append("")
    out.append("Conventions" + (f" (--compat {c['compat']})" if c["compat"] else ""))
    out.append(f"  Curves: {c['curves']}.")
    out.append(f"  Grid: {c['grid']}. Crossings: {c['interpolation']}; coinciding curves: --tie {c['tie']}.")
    out.append(f"  Weights: {c['weights']}.")
    nms = result["nms"]
    if nms:
        out.append("")
        out.append(f"Newton-Miller-Smith extension ({nms['variant']} variant, n = {nms['n']})")
        out.append("  Purchase probability by intent answer: " +
                   ", ".join(f"{k} = {pct(v)}" for k, v in nms["weights"].items()))
        t, rv, g = nms["trial_max"], nms["revenue_max"], nms["revenue_max_on_grid"]
        out.append(f"  Price with the highest trial:    {fmt(t['price'])}  (trial {pct(t['trial'])})")
        out.append(f"  Price with the highest revenue:  {fmt(rv['price'])}  (trial {pct(rv['trial'])}, "
                   f"revenue index {fmt(rv['revenue_index'])} per respondent)")
        if not rv["on_grid"]:
            out.append(f"    highest among the observed prices only: {fmt(g['price'])} "
                       f"(revenue index {fmt(g['revenue_index'])})")
        out.append("")
        out.append(f"  {'Price':>12}{'Trial':>10}{'Revenue index':>16}")
        for row in nms["curve"]:
            out.append(f"  {fmt(row['price']):>12}{100 * row['trial']:>9.2f}%{fmt(row['revenue_index']):>16}")
    if show_curves:
        keys = [k for k in CURVE_KEYS if k in result["curves"][0]]
        out.append("")
        out.append("Cumulative curves (share of analysed respondents)")
        out.append(f"  {'Price':>12}" + "".join(f"{LABELS[k]:>15}" for k in keys))
        for row in result["curves"]:
            out.append(f"  {fmt(row['price']):>12}" + "".join(f"{pct(row[k]):>15}" for k in keys))
    out.append("")
    if result["warnings"]:
        out.append("Warnings")
        out.extend(f"  - {w}" for w in result["warnings"])
    else:
        out.append("Warnings: none")
    return "\n".join(out)


def write_chart(path, result):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(render_svg(result))


def write_curves_csv(path, result):
    keys = [k for k in CURVE_KEYS if k in result["curves"][0]]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["price"] + keys)
        for row in result["curves"]:
            writer.writerow([repr(row["price"])] + [f"{row[k]:.6f}" for k in keys])


# Chart colours: four fixed categorical slots (light, dark) plus a dash pattern each, so no curve is told
# apart by colour alone. Ink and grid colours follow the same light/dark pairs.
SERIES_STYLE = [("s1", ""), ("s2", "7 4"), ("s3", "2 4"), ("s4", "10 3 2 3")]
SVG_STYLE = """
.bg{fill:#fcfcfb}.ink{fill:#0b0b0b}.sub{fill:#52514e}.mute{fill:#898781}
.grid{stroke:#e1e0d9;stroke-width:1}.axis{stroke:#c3c2b7;stroke-width:1}
.band{fill:#898781;opacity:.14}.rule{stroke:#52514e;stroke-width:1;stroke-dasharray:3 3}
.line{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}.dot{stroke:#fcfcfb;stroke-width:1}
text{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:12px}.title{font-size:14px;font-weight:600}
.s1{stroke:#2a78d6}.s2{stroke:#eb6834}.s3{stroke:#1baf7a}.s4{stroke:#eda100}
.f1{fill:#2a78d6}.f2{fill:#eb6834}.f3{fill:#1baf7a}.f4{fill:#eda100}
@media (prefers-color-scheme: dark){
.bg{fill:#1a1a19}.ink{fill:#f0efec}.sub{fill:#c3c2b7}.grid{stroke:#2c2c2a}.axis{stroke:#383835}
.rule{stroke:#c3c2b7}.dot{stroke:#1a1a19}
.s1{stroke:#3987e5}.s2{stroke:#d95926}.s3{stroke:#199e70}.s4{stroke:#c98500}
.f1{fill:#3987e5}.f2{fill:#d95926}.f3{fill:#199e70}.f4{fill:#c98500}}
"""


def _ticks(low, high, target=6):
    raw = ((high - low) or 1.0) / target
    mag = 10 ** math.floor(math.log10(raw))
    step = next(s * mag for s in (1, 2, 5, 10) if s * mag >= raw)
    first = math.ceil(low / step) * step
    ticks = []
    while first <= high + step * 1e-9:
        ticks.append(round(first, 10))
        first += step
    return ticks


def _num(value):
    return f"{value:,.2f}".rstrip("0").rstrip(".") if value % 1 else f"{value:,.0f}"


def _panel(top, title, xs, series, x_low, x_high, y_max, y_format, markers, band):
    """One chart panel. series: list of (label, [y values]); markers: list of (label, price)."""
    left, right, plot_top, height = 64, 730, top + 86, 220
    width = right - left

    def sx(x):
        return left + (x - x_low) / ((x_high - x_low) or 1.0) * width

    def sy(y):
        return plot_top + height - (y / (y_max or 1.0)) * height

    parts = [f'<text class="ink title" x="{left}" y="{top + 16}">{escape(title)}</text>']
    lx = left
    for (label, _), (cls, dash) in zip(series, SERIES_STYLE):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<line class="line {cls}" x1="{lx}" y1="{top + 34}" x2="{lx + 26}" y2="{top + 34}"{d}/>')
        parts.append(f'<text class="sub" x="{lx + 32}" y="{top + 38}">{escape(label)}</text>')
        lx += 46 + 7 * len(label)
    for i in range(5):
        y = y_max * i / 4
        cls = "axis" if i == 0 else "grid"
        parts.append(f'<line class="{cls}" x1="{left}" y1="{sy(y):.1f}" x2="{right}" y2="{sy(y):.1f}"/>')
        parts.append(f'<text class="mute" x="{left - 8}" y="{sy(y) + 4:.1f}" text-anchor="end">{escape(y_format(y))}</text>')
    for tick in _ticks(x_low, x_high):
        parts.append(f'<text class="mute" x="{sx(tick):.1f}" y="{plot_top + height + 18}" text-anchor="middle">{_num(tick)}</text>')
    if band and band[0] is not None and band[1] is not None and band[1] > band[0]:
        parts.append(f'<rect class="band" x="{sx(band[0]):.1f}" y="{plot_top}" width="{sx(band[1]) - sx(band[0]):.1f}" '
                     f'height="{height}"><title>Acceptable range {_num(band[0])} to {_num(band[1])}</title></rect>')
    shown = sorted((m for m in markers if m[1] is not None), key=lambda m: m[1])
    for row, (label, price) in enumerate(shown):
        x = sx(price)
        y_label = top + 54 + 13 * (row % 3)
        anchor, dx = ("end", -4) if x > right - 110 else ("start", 4)
        parts.append(f'<line class="rule" x1="{x:.1f}" y1="{y_label - 9}" x2="{x:.1f}" y2="{plot_top + height}"/>')
        parts.append(f'<text class="ink" x="{x + dx:.1f}" y="{y_label}" text-anchor="{anchor}">{escape(label)} {_num(price)}</text>')
    for (label, ys), (cls, dash) in zip(series, SERIES_STYLE):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        pts = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in zip(xs, ys))
        parts.append(f'<polyline class="line {cls}" points="{pts}"{d}/>')
        if len(xs) <= 60:
            for x, y in zip(xs, ys):
                parts.append(f'<circle class="dot f{cls[1]}" cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="4">'
                             f'<title>{escape(label)} at {_num(x)}: {escape(y_format(y))}</title></circle>')
    parts.append(f'<text class="mute" x="{right}" y="{plot_top + height + 36}" text-anchor="end">Price</text>')
    return "\n".join(parts), plot_top + height + 48


def render_svg(result):
    curves = result["curves"]
    xs = [row["price"] for row in curves]
    pad = (xs[-1] - xs[0]) * 0.03 or 1.0
    x_low, x_high = xs[0] - pad, xs[-1] + pad
    keys = ("too_cheap", "not_cheap", "not_expensive", "too_expensive") \
        if result["conventions"]["range_definition"] == "original" else PRICE_KEYS
    series = [(LABELS[k].capitalize(), [row[k] for row in curves]) for k in keys if k in curves[0]]
    points = result["price_points"]
    markers = [(k.upper(), points[k]["price"]) for k in ("pmc", "opp", "ipp", "pme")]
    rng = result["acceptable_range"]
    n = result["respondents"]["analysed"]
    title = f"Price sensitivity meter: share of {n} respondents ({rng['definition']} range definition)"
    body, bottom = _panel(0, title, xs, series, x_low, x_high, 1.0, lambda y: f"{100 * y:.0f}%", markers,
                          (rng["low"], rng["high"]))
    panels = [body]
    nms = result["nms"]
    if nms:
        # Draw the same curve the optimiser uses: vertical jumps at tied prices, straight lines between.
        nx, trial = [], []
        for row in nms["curve"]:
            for key in ("trial_just_below", "trial", "trial_just_above"):
                if key in row:
                    nx.append(row["price"])
                    trial.append(row[key])
        revenue = [x * t for x, t in zip(nx, trial)]
        body, bottom = _panel(bottom, f"Newton-Miller-Smith trial: mean purchase probability (n = {nms['n']})",
                              nx, [("Trial", trial)], x_low, x_high, max(trial) or 1.0,
                              lambda y: f"{100 * y:.0f}%", [("Highest trial", nms["trial_max"]["price"])], None)
        panels.append(body)
        body, bottom = _panel(bottom, "Newton-Miller-Smith revenue index: price x trial, per respondent",
                              nx, [("Revenue index", revenue)], x_low, x_high,
                              max(max(revenue), nms["revenue_max"]["revenue_index"]) or 1.0, _num,
                              [("Highest revenue", nms["revenue_max"]["price"])], None)
        panels.append(body)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 {bottom}" width="760" height="{bottom}" '
            f'role="img" aria-label="{escape(title)}">\n<style>{SVG_STYLE}</style>\n'
            f'<rect class="bg" width="760" height="{bottom}"/>\n' + "\n".join(panels) + "\n</svg>\n")


# ---------------------------------------------------------------- command line

def probability(text):
    value = float(text)
    if not 0 <= value <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return value


def build_parser():
    p = argparse.ArgumentParser(
        description="Van Westendorp price sensitivity meter from a CSV with one row per respondent: OPP, IPP (IDP), "
                    "PMC, PME, the acceptable price range under both definitions, and the Newton-Miller-Smith trial "
                    "and revenue curves when two purchase-intent columns are present.")
    p.add_argument("input", help="CSV file, one row per respondent, with a header row")
    g = p.add_argument_group("columns (found by name when not given)")
    g.add_argument("--too-cheap", metavar="COLUMN", help="'too cheap' price column (absent: three-question variant)")
    g.add_argument("--cheap", metavar="COLUMN", help="'cheap / bargain' price column")
    g.add_argument("--expensive", metavar="COLUMN", help="'expensive' price column")
    g.add_argument("--too-expensive", metavar="COLUMN", help="'too expensive' price column")
    g.add_argument("--intent-cheap", metavar="COLUMN", help="purchase intent at the respondent's cheap price")
    g.add_argument("--intent-expensive", metavar="COLUMN", help="purchase intent at the respondent's expensive price")
    g.add_argument("--id", metavar="COLUMN", help="respondent id column (default: a column named id or respondent id)")
    g.add_argument("--segment", metavar="COLUMN", help="also analyse each value of this column on its own")
    g.add_argument("--weight", metavar="COLUMN", help="respondent weights (non-negative numbers) used in every curve")
    g = p.add_argument_group("reading")
    g.add_argument("--delimiter", help="field separator (default: comma, semicolon or tab, whichever splits the header into the most fields)")
    g.add_argument("--skip-rows", type=int, metavar="N",
                   help="rows under the header to skip (default: the 2 extra header rows of a Qualtrics export when "
                        "detected, otherwise 0)")
    g.add_argument("--decimal", choices=("point", "comma"), default="point", help="decimal mark in prices (default: point)")
    g.add_argument("--na", metavar="TOKENS", help="comma-separated cell values that mean 'no answer', for example NA,N/A")
    g.add_argument("--min-price", type=float, metavar="PRICE", help="exclude (and count) respondents with any price below this")
    g.add_argument("--max-price", type=float, metavar="PRICE", help="exclude (and count) respondents with any price above this")
    g = p.add_argument_group("method")
    g.add_argument("--range-definition", choices=("original", "narrower"), default="original",
                   help="headline PMC and PME. original (default, Van Westendorp 1976): too cheap x not cheap and "
                        "too expensive x not expensive. narrower: too cheap x expensive and too expensive x cheap. "
                        "The other range is always printed as well")
    g.add_argument("--strict", action="store_true",
                   help="require too cheap < cheap < expensive < too expensive (default allows equal prices)")
    g.add_argument("--keep-inconsistent", action="store_true",
                   help="keep respondents whose prices are out of order (default: exclude and count them)")
    g.add_argument("--boundary", choices=tuple(BOUNDARY_TEXT),
                   help="falling curves count answers >= p (inclusive, default) or > p (exclusive); "
                        "exclusive-forced-ends also pins each curve at its lowest answer")
    g.add_argument("--no-interpolate", action="store_true",
                   help="report the first observed price at which two curves have met or crossed, without interpolating")
    g.add_argument("--tie", choices=("min", "max", "mean", "midpoint"),
                   help="price to report when two curves coincide over several observed prices (default: midpoint)")
    g.add_argument("--compat", choices=tuple(COMPAT),
                   help="preset of the options above that follows another tool; see references/tool-conventions.md")
    g.add_argument("--min-n", type=int, default=DEFAULT_MIN_N,
                   help=f"warn when fewer respondents are analysed (default: {DEFAULT_MIN_N})")
    g.add_argument("--at", type=float, action="append", default=[], metavar="PRICE",
                   help="also report the share on each curve at this candidate price (repeatable)")
    g.add_argument("--bootstrap", type=int, default=0, metavar="N",
                   help="add percentile intervals for the four points from N resamples of respondents")
    g.add_argument("--seed", type=int, default=1, help="random seed for --bootstrap (default: 1)")
    g = p.add_argument_group("Newton-Miller-Smith extension")
    g.add_argument("--no-nms", action="store_true", help="skip the extension even when intent columns are present")
    g.add_argument("--intent-scale", default=None,
                   help="intent answers as they appear in the file, highest intent first, for example 5,4,3,2,1 "
                        "when 5 = definitely would buy. Required when the extension runs: the direction is never guessed")
    g.add_argument("--nms-preset", choices=tuple(NMS_PRESETS),
                   help="purchase probabilities for the five scale points: " +
                        "; ".join(f"{k} = {v}" for k, v in NMS_PRESETS.items()) + f" (default: {DEFAULT_NMS_PRESET})")
    g.add_argument("--nms-weights", help="purchase probability for each scale point, highest intent first")
    g.add_argument("--nms-variant", choices=("original", "modified"), default="original",
                   help="original: a set probability (default 0) at and below the too-cheap price. modified: the "
                        "cheap-price probability holds for every lower price")
    g.add_argument("--nms-too-cheap-prob", type=probability, default=0.0, metavar="P",
                   help="purchase probability at and below the too-cheap price (default: 0)")
    g.add_argument("--nms-too-expensive-prob", type=probability, default=0.0, metavar="P",
                   help="purchase probability at and above the too-expensive price (default: 0)")
    g = p.add_argument_group("output")
    g.add_argument("--json", action="store_true", help="print the result as JSON")
    g.add_argument("--curves", action="store_true", help="add the cumulative curve table to the text output")
    g.add_argument("--curves-csv", metavar="FILE.csv", help="also write the price grid and curve shares to this file")
    g.add_argument("--chart", metavar="FILE.svg", help="also write an SVG chart to this file")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.min_n < 1:
            raise InputError("--min-n must be 1 or more.")
        if args.bootstrap < 0:
            raise InputError("--bootstrap must be 0 or more.")
        if args.min_price is not None and args.max_price is not None and args.min_price > args.max_price:
            raise InputError("--min-price is above --max-price.")
        preset = COMPAT.get(args.compat, {})
        args.strict = args.strict or preset.get("strict", False)
        args.no_interpolate = args.no_interpolate or preset.get("no_interpolate", False)
        args.boundary = args.boundary or preset.get("boundary", "inclusive")
        args.tie = args.tie or preset.get("tie", "midpoint")
        args.r_ties = preset.get("r_ties", False)
        args.intent_scale_given = args.intent_scale is not None
        args.intent_scale = args.intent_scale or DEFAULT_INTENT_SCALE
        args.skipped_note = None
        rows, columns, markers = read_rows(args.input, args)
        result = run(rows, columns, markers, args, parse_scale(args))
        for path, writer in ((args.chart, write_chart), (args.curves_csv, write_curves_csv)):
            if path:
                try:
                    writer(path, result)
                except OSError as exc:
                    raise InputError(f"cannot write {path}: {exc.strerror or exc}")
        result["files"] = {"chart": args.chart, "curves_csv": args.curves_csv}
    except InputError as exc:
        print(f"van-westendorp-analysis: error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(render_text(result, args.curves))
        for label, path in (("Chart", args.chart), ("Curves", args.curves_csv)):
            if path:
                print(f"\n{label} written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
