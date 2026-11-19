#!/usr/bin/env python3
"""Survey crosstabs (banner tables): column percentages with bases, significance letters from pairwise
column-proportion tests with Holm, Benjamini-Hochberg or Bonferroni adjustment, a chi-square test per table,
Wilson intervals, weighted bases with Kish effective n, optional means with Welch t-tests, and an anonymity
rule that suppresses groups and cells under k respondents (with complementary suppression).

Standard library only, Python 3.9+. No network, no randomness. Formulas and thresholds: references/sources.md.

Usage:
  python3 scripts/survey_crosstabs.py survey.csv --list-columns
  python3 scripts/survey_crosstabs.py survey.csv --rows q1 q2 --banner plan region
  python3 scripts/survey_crosstabs.py survey.csv --rows q1 --banner plan --weight weight --means --json
  python3 scripts/survey_crosstabs.py survey.csv --rows q3 --multi q3 --banner team --anonymity 5
  python3 scripts/survey_crosstabs.py counts.csv --count-col n --rows party --banner gender

Exit codes: 0 success; 2 bad input or a refused calculation (the message says what to fix).
"""
import argparse
import csv
import io
import json
import math
import re
import sys
from statistics import NormalDist

VERSION = "0.1.1"

DEFAULT_SMALL_BASE = 30  # convention of this skill: no letters for a column with an (effective) base under 30
DEFAULT_ANONYMITY_K = 5  # common minimum group size in employee surveys; configurable (references/sources.md)
COCHRAN_MIN_EXPECTED = 5  # Cochran (1954): expected counts under 5 make the chi-square / z approximation doubtful
DROP_STOP_SHARE = 0.05  # refuse when more than 5% of rows would be dropped for unreadable weights or counts
DEFAULT_NA = ["", "NA", "N/A", "n/a", "#N/A", "NaN", "nan", "NULL", "null", "None"]
# A coded label needs an explicit delimiter or parentheses after the code ("5 - Very", "(5) Very", "5. Very"), so
# "1 week", "18 to 24" and "50k-75k" stay text categories. Same rule as survey-weighting.
LABELLED_RE = re.compile(r"^\s*(?:\((-?\d{1,4})\)|(-?\d{1,4})\s*[-–—:=.)])\s*[^\W\d_].*$")
THOUSANDS_RE = re.compile(r"-?[1-9]\d{0,2}(?:,\d{3})+")  # "0,500" is a decimal comma, never thousands
DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|", "\\t": "\t"}


class InputError(Exception):
    """Bad input or a refused calculation; exit code 2."""


# ------------------------------------------------------------------------------------------------ statistics

def z_for(confidence):
    return NormalDist().inv_cdf(1 - (1 - confidence) / 2)


def norm_two_sided(z):
    # erfc keeps precision in the far tail, where 1 - cdf rounds to 0.
    return math.erfc(abs(z) / math.sqrt(2))


def wilson(p, n, z):
    """Wilson (1927) score interval for a proportion p observed on (effective) base n."""
    if n <= 0:
        return None
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0)) / denom
    return [max(0.0, centre - half), min(1.0, centre + half)]


def _gamma_series(a, x):
    total = term = 1.0 / a
    ap = a
    for _ in range(10000):
        ap += 1
        term *= x / ap
        total += term
        if abs(term) < abs(total) * 1e-15:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gamma_cf(a, x):
    tiny = 1e-300
    b = x + 1 - a
    c = 1 / tiny
    d = 1 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def chi2_sf(x, df):
    """Upper tail of the chi-square distribution: Q(df/2, x/2), the regularized upper incomplete gamma."""
    if x <= 0:
        return 1.0
    a, y = df / 2.0, x / 2.0
    if y < a + 1:
        return max(0.0, 1.0 - _gamma_series(a, y))
    return min(1.0, _gamma_cf(a, y))


def _beta_cf(a, b, x):
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = tiny if abs(d) < tiny else d
    d = 1 / d
    h = d
    for m in range(1, 10000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return h


def reg_beta(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _beta_cf(a, b, x) / a
    return 1 - front * _beta_cf(b, a, 1 - x) / b


def t_two_sided(t, df):
    return reg_beta(df / 2.0, 0.5, df / (df + t * t))


def t_crit(confidence, df):
    lo, hi = 0.0, 1000.0
    target = 1 - confidence
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_two_sided(mid, df) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _log_choose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_exact(a, n1, c, n2):
    """Two-sided Fisher exact p for successes a of n1 vs c of n2 (sum of tables no more likely than observed)."""
    m = a + c
    total = n1 + n2
    lo, hi = max(0, m - n2), min(m, n1)

    def prob(x):
        return math.exp(_log_choose(n1, x) + _log_choose(n2, m - x) - _log_choose(total, m))

    observed = prob(a)
    return min(1.0, sum(prob(x) for x in range(lo, hi + 1) if prob(x) <= observed * (1 + 1e-7)))


def adjust_pvalues(pvals, method):
    """Holm (1979), Benjamini-Hochberg (1995) or Bonferroni adjusted p-values, in input order."""
    m = len(pvals)
    if m == 0 or method == "none":
        return list(pvals)
    if method == "bonferroni":
        return [min(1.0, p * m) for p in pvals]
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    if method == "holm":
        running = 0.0
        for rank, i in enumerate(order):
            running = max(running, min(1.0, (m - rank) * pvals[i]))
            adj[i] = running
        return adj
    if method == "bh":
        running = 1.0
        for rank in range(m - 1, -1, -1):
            i = order[rank]
            running = min(running, min(1.0, pvals[i] * m / (rank + 1)))
            adj[i] = running
        return adj
    raise InputError(f"unknown adjustment {method}")


def kish(w_sum, w2_sum):
    """Kish (1965) effective sample size (sum w)^2 / sum w^2."""
    return (w_sum * w_sum / w2_sum) if w2_sum > 0 else 0.0


# ------------------------------------------------------------------------------------------------ CSV reading

def decode(data, path):
    try:
        if data.startswith(b"\xef\xbb\xbf"):
            return data[3:].decode("utf-8"), "UTF-8 with BOM"
        if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
            return data.decode("utf-16"), "UTF-16"
        if data[:200].count(b"\x00") > 20:
            raise InputError(f"{path} looks like UTF-16 without a byte-order mark; re-export it as CSV UTF-8")
        return data.decode("utf-8"), "UTF-8"
    except UnicodeError as exc:
        where = f" (byte {exc.start})" if isinstance(exc, UnicodeDecodeError) else ""
        raise InputError(f"{path} is not valid UTF-8 or UTF-16 text{where}; re-export it as 'CSV UTF-8' (Excel)")


def parse_records(text, delim, path):
    """Strict CSV parse: an unclosed quote is an error naming the line its record starts on, not a merged row."""
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim, strict=True)
    table, start = [], 1
    try:
        for record in reader:
            if any(c.strip() for c in record):
                table.append(record)
            start = reader.line_num + 1
    except csv.Error as exc:
        raise InputError(f"{path} is not valid CSV: the record starting on line {start} is broken ({exc}); "
                         "usually an unclosed quote. Fix that line and run again.")
    return table


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


def read_table(path, delimiter=None, skip_rows=None, notes=None):
    """(headers, rows as dicts). BOMs, UTF-16, CRLF, sniffed delimiter, Qualtrics 3-row headers."""
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
        notes.append(f"Read as {encoding}.")
    if delimiter:
        delim = DELIMITERS.get(delimiter.lower(), delimiter)
        if len(delim) != 1:
            raise InputError(f"--delimiter takes one character or comma, semicolon, tab, pipe; got {delimiter!r}")
    else:
        delim = sniff_delimiter(text)
        if delim != ",":
            notes.append(f"Delimiter detected: {dict((v, k) for k, v in DELIMITERS.items())[delim]}.")
    table = parse_records(text, delim, path)
    if not table:
        raise InputError(f"{path} is empty or has no header row")
    headers = [h.strip() for h in table[0]]
    repeated = sorted({h for h in headers if headers.count(h) > 1})
    if repeated:
        raise InputError(f"{path} has more than one column named {', '.join(repr(h) for h in repeated)}. Rename "
                         "them so each column is unique, then pass the one you mean.")
    body = table[1:]
    if skip_rows is None:
        if len(body) >= 2 and any(cell.strip().startswith('{"ImportId"') for cell in body[1]):
            skip_rows = 2
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
        rows.append(dict(zip(headers, row)))
    return headers, rows


def ambiguous_comma(text):
    """'1,020' could be 1020 (thousands) or 1.02 (decimal comma): refuse rather than guess."""
    return bool(re.fullmatch(r"-?[1-9]\d{0,2},\d{3}", text.strip()))


def parse_number(text):
    """A finite number; '0,75' reads as a decimal comma, '1,020,000' as thousands, '1,020' as None (ambiguous)."""
    text = text.strip()
    if ambiguous_comma(text):
        return None
    if THOUSANDS_RE.fullmatch(text) and text.count(",") > 1:
        text = text.replace(",", "")
    elif re.fullmatch(r"-?\d+,\d+", text):
        text = text.replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def parse_count(text):
    """A whole non-negative count: '12', '12.0', '1,000' or '1,000,000' (comma thousands). None otherwise."""
    text = text.strip()
    if THOUSANDS_RE.fullmatch(text) and not text.startswith("-"):
        text = text.replace(",", "")
    if re.fullmatch(r"\d+(?:\.0+)?", text):
        return int(float(text)) if "." in text else int(text)
    return None


def code_of(text):
    """Leading integer code of '5', '5 - Very satisfied', '(5) Very satisfied'; None otherwise."""
    m = LABELLED_RE.match(text)
    if m:
        return int(m.group(1) if m.group(1) is not None else m.group(2))
    value = parse_number(text)
    if value is not None and value == int(value):
        return int(value)
    return None


# ------------------------------------------------------------------------------------------------ variables

class Variable:
    """A row or banner variable: per-record category keys, display labels, order."""

    def __init__(self, name, values, na, multi_sep=None, order=None):
        self.name = name
        self.multi = multi_sep is not None
        cleaned = []
        for raw in values:
            text = (raw or "").strip()
            if text in na:
                cleaned.append(None)
            elif self.multi:
                parts = [p.strip() for p in text.split(multi_sep) if p.strip() and p.strip() not in na]
                cleaned.append(parts or None)
            else:
                cleaned.append(text)
        flat = [v for c in cleaned if c is not None for v in (c if self.multi else [c])]
        codes = [code_of(v) for v in flat]
        self.numeric = bool(flat) and all(c is not None for c in codes)
        labels = {}
        counts = {}
        if self.numeric:
            for v, c in zip(flat, codes):
                counts.setdefault(c, {}).setdefault(v, 0)
                counts[c][v] += 1
            # Two different text labels on one code ("1. Jan", "1. Feb") are two answers, not one coded answer.
            for variants in counts.values():
                texts = {re.sub(r"\s+", " ", re.sub(r"^\s*\(?-?\d{1,4}\)?\s*[-–—:=.)]?\s*", "", v)).strip().lower()
                         for v in variants if re.search(r"[^\W\d_]", v)}
                if len(texts) > 1:
                    self.numeric = False
                    break
        if self.numeric:
            for c, variants in counts.items():
                # Prefer a variant that carries a text label ("5 - Very satisfied" over "5").
                labelled = {v: n for v, n in variants.items() if re.search(r"[^\W\d_]", v)}
                pool = labelled or variants
                labels[c] = max(pool, key=lambda s: (pool[s], len(s), s))
            keyed = [None if c is None else ([code_of(v) for v in c] if self.multi else code_of(c)) for c in cleaned]
        else:
            for v in flat:
                labels.setdefault(v, v)
            keyed = cleaned
        self.keys = keyed
        self.labels = labels
        self.order_given = order
        self.categories = list(labels)

    def ordered(self, weights_by_key):
        if self.order_given:
            wanted = []
            lookup = {str(self.labels[k]).lower(): k for k in self.labels}
            lookup.update({str(k).lower(): k for k in self.labels})
            for item in self.order_given:
                key = lookup.get(item.strip().lower())
                if key is None:
                    raise InputError(f"--order for {self.name}: {item!r} is not a value of that column; values are "
                                     + ", ".join(repr(self.labels[k]) for k in self.labels))
                if key not in wanted:
                    wanted.append(key)
            return wanted + [k for k in self.categories if k not in wanted]
        if self.numeric:
            return sorted(self.categories)
        return sorted(self.categories, key=lambda k: (-weights_by_key.get(k, 0.0), self.categories.index(k)))


def letters_for(count):
    out = []
    for i in range(count):
        s, n = "", i
        while True:
            s = chr(65 + n % 26) + s
            n = n // 26 - 1
            if n < 0:
                break
        out.append(s)
    return out


# ------------------------------------------------------------------------------------------------ loading

def parse_kv_list(items, flag, merge=False):
    """COLUMN=v1;v2 items. A repeated column adds up (merge, for --hide) or stops (--order), never overwrites."""
    out = {}
    for item in items or []:
        if "=" not in item:
            raise InputError(f"{flag} takes COLUMN=VALUES; got {item!r}")
        col, rest = item.split("=", 1)
        values = [v for v in rest.split(";") if v.strip()]
        if col.strip() in out and not merge:
            raise InputError(f"{flag} names {col.strip()!r} twice; give its values once")
        out.setdefault(col.strip(), []).extend(values)
    return out


def parse_nets(items):
    nets = []
    for item in items or []:
        m = re.match(r"^([^:]+):([^=]+)=(.+)$", item)
        if not m:
            raise InputError(f"--net takes COLUMN:LABEL=v1;v2 (for example 'q1:Satisfied=4;5'); got {item!r}")
        nets.append((m.group(1).strip(), m.group(2).strip(), [v.strip() for v in m.group(3).split(";") if v.strip()]))
    return nets


def load(args, notes):
    headers, rows = read_table(args.input, args.delimiter, args.skip_rows, notes)
    if args.list_columns:
        return headers, rows, None, None
    if not args.rows:
        raise InputError("pass --rows with the question column(s) to tabulate (run --list-columns to see them)")
    for col in list(args.rows) + list(args.banner or []) + [c for c in (args.weight, args.count_col) if c] \
            + list(args.multi or []):
        if col not in headers:
            raise InputError(f"column {col!r} not found. Columns: {', '.join(headers)}")
    overlap = set(args.rows) & set(args.banner or [])
    if overlap:
        raise InputError(f"{', '.join(sorted(overlap))} is both a row and a banner variable; pick one role")
    freq, weights, dropped = [], [], {"blank": 0, "unreadable": 0, "negative": 0}
    for r in rows:
        f, w = 1, 1.0
        if args.count_col:
            raw = (r[args.count_col] or "").strip()
            v = parse_count(raw)
            if v is None:
                dropped["negative" if re.fullmatch(r"-\d+(?:\.0+)?", raw) else "unreadable"] += 1
                f = None
            else:
                f = v
        if args.weight and f is not None:
            text = (r[args.weight] or "").strip()
            if ambiguous_comma(text):
                raise InputError(f"weight {text!r} in column {args.weight} could be {text.replace(',', '')} "
                                 f"(thousands) or {text.replace(',', '.')} (decimal comma). Re-export the weights "
                                 "with a decimal point and no thousands separator.")
            v = parse_number(text) if text else None
            if not text:
                dropped["blank"] += 1
                f = None
            elif v is None:
                dropped["unreadable"] += 1
                f = None
            elif v < 0:
                dropped["negative"] += 1
                f = None
            else:
                w = v
        freq.append(f)
        weights.append(w)
    n_drop = sum(dropped.values())
    if n_drop:
        what = "weight" if args.weight else "count"
        share = n_drop / len(rows)
        detail = ", ".join(f"{v} {k}" for k, v in dropped.items() if v)
        if share > DROP_STOP_SHARE and not args.allow_drop:
            raise InputError(f"{n_drop} of {len(rows)} rows ({share:.1%}) have no usable {what} ({detail}). Fix the "
                             f"{what} column, or pass --allow-drop to exclude them (they will be counted).")
        notes.append(f"Excluded {n_drop} row(s) with no usable {what} ({detail}).")
    keep = [i for i, f in enumerate(freq) if f is not None]
    if args.weight and keep and all(weights[i] == 0 for i in keep):
        raise InputError(f"every usable weight in {args.weight} is 0, so no weighted percentage exists. Check the "
                         "weight column (or drop --weight).")
    zero_w = sum(1 for i in keep if weights[i] == 0)
    if zero_w:
        notes.append(f"{zero_w} row(s) have weight 0: they count in the unweighted base but add nothing to percentages.")
    rows = [rows[i] for i in keep]
    used_w = {weights[i] for i in keep if freq[i]}
    data = {"freq": [freq[i] for i in keep], "w": [weights[i] for i in keep], "rows": rows,
            "rows_read": len(freq), "rows_used": len(keep),
            # Equal positive weights give exactly the unweighted results (Kish n_eff = n), so the unweighted
            # tests, including Fisher's exact test, apply.
            "constant_w": bool(args.weight) and len(used_w) == 1 and next(iter(used_w)) > 0}
    if data["constant_w"]:
        notes.append(f"Every weight in {args.weight} is the same, so the results equal the unweighted ones.")
    return headers, rows, data, dropped


# ------------------------------------------------------------------------------------------------ tables

class Acc:
    __slots__ = ("n", "w", "w2")

    def __init__(self):
        self.n, self.w, self.w2 = 0, 0.0, 0.0

    def add(self, f, w):
        self.n += f
        self.w += f * w
        self.w2 += f * w * w


def column_stats(acc, weighted):
    neff = kish(acc.w, acc.w2) if weighted else float(acc.n)
    return neff


def pair_test(p1, n1, p2, n2, a_count, n1_count, c_count, n2_count, weighted, mode):
    """Column-proportion test. Returns (p_value, method, z or None) or (None, reason, None)."""
    if n1 <= 0 or n2 <= 0:
        return None, "empty column", None
    pooled = (n1 * p1 + n2 * p2) / (n1 + n2)
    expected_ok = min(n1 * pooled, n1 * (1 - pooled), n2 * pooled, n2 * (1 - pooled)) >= COCHRAN_MIN_EXPECTED
    if mode == "z" or (mode == "auto" and expected_ok):
        se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
        if se == 0:
            return 1.0, "z", 0.0
        z = (p1 - p2) / se
        return norm_two_sided(z), "z", z
    if weighted:
        return None, "too few expected answers to test with weights", None
    return fisher_exact(a_count, n1_count, c_count, n2_count), "fisher", None


def welch(m1, s1, n1, m2, s2, n2):
    if n1 < 2 or n2 < 2:
        return None, None
    v1, v2 = s1 * s1 / n1, s2 * s2 / n2
    se = math.sqrt(v1 + v2)
    if se == 0:
        # Neither group has any spread: the Welch t and its df are undefined; report the means, not a test.
        return None, None
    t = (m1 - m2) / se
    df = (v1 + v2) ** 2 / ((v1 * v1 / (n1 - 1)) + (v2 * v2 / (n2 - 1)))
    return t_two_sided(t, df), t


def banner_letters(banner_var, data):
    """One letter per group for the whole run, from every row with that group, so a group keeps its letter in
    every table even when it has no answers to one question."""
    bweights = {}
    for i, bk in enumerate(banner_var.keys):
        if bk is not None:
            bweights[bk] = bweights.get(bk, 0.0) + data["freq"][i] * data["w"][i]
    if banner_var.order_given or banner_var.numeric:
        bcats = [b for b in banner_var.ordered(bweights) if b in bweights]
    else:
        bcats = sorted([b for b in banner_var.categories if b in bweights], key=lambda b: str(b).lower())
    return dict(zip(bcats, letters_for(len(bcats)))), bcats


def build_table(row_var, banner_var, data, args, z, nets, letter_map=None, force_hidden=()):
    weighted = bool(args.weight) and not data.get("constant_w")
    freq, w = data["freq"], data["w"]
    nrec = len(freq)
    # Columns: Total + banner categories.
    if banner_var is not None:
        bkeys = banner_var.keys
    else:
        bkeys = [None] * nrec
    blank_row = blank_banner = 0
    total_acc = Acc()
    col_acc = {}
    cell = {}  # (col, cat) -> Acc ; col None = Total
    values_num = {}  # col -> list of (x, f, w) for means
    weight_by_cat = {}
    for i in range(nrec):
        rk = row_var.keys[i]
        if rk is None:
            blank_row += freq[i]
            continue
        cats = rk if row_var.multi else [rk]
        cols = [None]
        if banner_var is not None:
            bk = bkeys[i]
            if bk is None:
                blank_banner += freq[i]
            else:
                cols.append(bk)
        for col in cols:
            acc = total_acc if col is None else col_acc.setdefault(col, Acc())
            acc.add(freq[i], w[i])
            for c in set(cats):
                cell.setdefault((col, c), Acc()).add(freq[i], w[i])
            if row_var.numeric and not row_var.multi:
                values_num.setdefault(col, []).append((rk, freq[i], w[i]))
        for c in set(cats):
            weight_by_cat[c] = weight_by_cat.get(c, 0.0) + freq[i] * w[i]
    cats = row_var.ordered(weight_by_cat)
    if banner_var is not None:
        if letter_map is None:
            letter_map, _ = banner_letters(banner_var, data)
        # Under the anonymity rule every group stays listed (empty ones hidden), so a group missing from one table
        # does not show that all its members skipped that question.
        bcats = [b for b in letter_map if b in col_acc or args.anonymity is not None]
    else:
        bcats = []
    columns = [{"key": None, "label": "Total", "letter": None, "acc": total_acc}]
    for b in bcats:
        columns.append({"key": b, "label": str(banner_var.labels[b]), "letter": letter_map[b],
                        "acc": col_acc.setdefault(b, Acc())})
    for col in columns:
        acc = col["acc"]
        col["n"] = acc.n
        col["weighted_base"] = acc.w
        col["n_eff"] = column_stats(acc, weighted)
        # Relative tolerance: rescaled weights give 29.999999999999996 for an effective base of 30.
        col["small_base"] = col["n_eff"] < args.small_base * (1 - 1e-9)
        col["suppressed"] = False

    # Rows: categories, nets.
    table_rows = []
    for c in cats:
        table_rows.append({"key": c, "label": str(row_var.labels[c]), "kind": "category", "members": [c]})
    for net_col, net_label, members in nets:
        if net_col != row_var.name:
            continue
        keys = []
        lookup = {str(row_var.labels[k]).lower(): k for k in row_var.labels}
        lookup.update({str(k).lower(): k for k in row_var.labels})
        for mem in members:
            if mem.lower() not in lookup:
                raise InputError(f"--net {net_col}:{net_label}: {mem!r} is not a value of {net_col}")
            keys.append(lookup[mem.lower()])
        table_rows.append({"key": ("net", net_label), "label": f"NET {net_label}", "kind": "net", "members": keys})
    # Net accumulators.
    for tr in table_rows:
        if tr["kind"] != "net":
            continue
        members = set(tr["members"])
        for i in range(nrec):
            rk = row_var.keys[i]
            if rk is None:
                continue
            hit = bool(members & set(rk if row_var.multi else [rk]))
            if not hit:
                continue
            cols = [None] + ([bkeys[i]] if banner_var is not None and bkeys[i] is not None else [])
            for col in cols:
                cell.setdefault((col, tr["key"]), Acc()).add(freq[i], w[i])

    for tr in table_rows:
        tr["cells"] = []
        for col in columns:
            acc = cell.get((col["key"], tr["key"]), Acc())
            base = col["acc"]
            pct = acc.w / base.w if base.w > 0 else None
            tr["cells"].append({
                "count": acc.n,
                "weighted_count": acc.w,
                "pct": pct,
                "ci": wilson(pct, col["n_eff"], z) if pct is not None and col["n_eff"] > 0 else None,
                "letters": [],
                "suppressed": False,
            })

    # Means.
    mean_row = None
    if args.means and row_var.numeric and not row_var.multi:
        mean_row = {"key": ("mean",), "label": "Mean", "kind": "mean", "cells": []}
        for col in columns:
            vals = values_num.get(col["key"], [])
            W = sum(f * ww for _, f, ww in vals)
            W2 = sum(f * ww * ww for _, f, ww in vals)
            if W <= 0:
                mean_row["cells"].append({"mean": None, "sd": None, "n_eff": 0.0, "ci": None, "letters": [],
                                          "suppressed": False})
                continue
            mean = sum(x * f * ww for x, f, ww in vals) / W
            neff = kish(W, W2) if weighted else float(sum(f for _, f, _ in vals))
            var_pop = sum(f * ww * (x - mean) ** 2 for x, f, ww in vals) / W
            sd = math.sqrt(var_pop * neff / (neff - 1)) if neff > 1 else None
            ci = None
            if sd is not None and neff > 1:
                half = t_crit(args.confidence, neff - 1) * sd / math.sqrt(neff)
                ci = [mean - half, mean + half]
            mean_row["cells"].append({"mean": mean, "sd": sd, "n_eff": neff, "ci": ci, "letters": [],
                                      "suppressed": False})

    table = {
        "row_var": row_var.name,
        "banner_var": banner_var.name if banner_var is not None else None,
        "type": "multi" if row_var.multi else "single",
        "columns": columns,
        "rows": table_rows,
        "mean_row": mean_row,
        "blank_row": blank_row,
        "blank_banner": blank_banner,
        "notes": [],
    }
    table["hidden_groups"] = set()
    if args.anonymity:
        table["hidden_groups"] = apply_anonymity(table, args.anonymity, force_hidden)
    run_tests(table, args, weighted)
    if row_var.multi or banner_var is None or table.get("withheld"):
        table["chi_square"] = None
    elif args.test == "none":
        table["chi_square"] = {"statistic": None, "df": None, "p": None,
                               "note": "descriptive only (--test none): no tests run"}
    else:
        table["chi_square"] = chi_square(table, weighted)
    return table


# ------------------------------------------------------------------------------------------------ anonymity

def _hidden_arcs(table, k):
    """The unknowns a reader faces, as arcs of a flow network (references/sources.md, "Anonymity rule").

    Single-choice: each respondent is one unit of flow S -> group column -> answer row -> Total -> S, so group
    bases, answer cells and Total cells obey conservation. Printed numbers are fixed arcs and are left out; every
    hidden number is an arc (u, v, value, lower bound, upper bound). The reader is assumed to know every printed
    count (JSON prints them exactly), that a hidden cell in a shown column or in Total is at least 1 (zeros are
    printed), and nothing else. Multi-select: column sums are not constrained, so columns and Total connect to a
    free hub instead.
    """
    columns, cat_rows = table["columns"], [r for r in table["rows"] if r["kind"] == "category"]
    single = table["type"] == "single"
    inf = float("inf")
    arcs, free = [], []
    total = columns[0]
    banner = len(columns) > 1 or table["banner_var"] is not None
    # What a reader knows bounds a hidden group's cell in a multi-select table: the hidden groups' combined base.
    hidden_mass = total["n"] - table["blank_banner"] - sum(c["n"] for c in columns[1:] if not c["suppressed"])
    hidden_mass -= max(0, sum(1 for c in columns[1:] if c["suppressed"]) - 1)  # every other hidden group has >= 1
    for i, r in enumerate(cat_rows):
        t_cell = r["cells"][0]
        if banner:
            group_sum = 0
            for ci in range(1, len(columns)):
                cell, col = r["cells"][ci], columns[ci]
                group_sum += cell["count"]
                if cell["suppressed"]:
                    arcs.append({"u": ("C", ci), "v": ("R", i), "f": cell["count"],
                                 "lb": 0 if col["suppressed"] else 1,
                                 "ub": inf if single else (hidden_mass if col["suppressed"] else col["n"]),
                                 "kind": "cell", "row": i, "col": ci, "hidden_col": col["suppressed"]})
            if table["blank_banner"]:
                arcs.append({"u": ("B",), "v": ("R", i), "f": t_cell["count"] - group_sum, "lb": 0,
                             "ub": table["blank_banner"],
                             "kind": "cell", "row": i, "col": "blank", "hidden_col": True})
            if t_cell["suppressed"]:
                arcs.append({"u": ("R", i), "v": ("T",), "f": t_cell["count"], "lb": 1, "ub": total["n"],
                             "kind": "cell", "row": i, "col": 0, "hidden_col": False})
        elif t_cell["suppressed"]:
            arcs.append({"u": ("S",), "v": ("T",), "f": t_cell["count"], "lb": 1, "ub": total["n"],
                         "kind": "cell", "row": i, "col": 0, "hidden_col": False})
    if single:
        for ci in range(1, len(columns)):
            if columns[ci]["suppressed"]:
                arcs.append({"u": ("S",), "v": ("C", ci), "f": columns[ci]["n"], "lb": 1, "ub": inf, "kind": "base"})
    else:
        free = [("C", ci) for ci in range(1, len(columns))] + [("B",), ("T",)]
        if not banner:
            free = [("S",), ("T",)]
    return arcs, free


def _residual(arcs, free, skip=None):
    graph = {}
    for idx, a in enumerate(arcs):
        if idx == skip:
            continue
        if a["f"] < a["ub"]:
            graph.setdefault(a["u"], set()).add(a["v"])
        if a["f"] > a["lb"]:
            graph.setdefault(a["v"], set()).add(a["u"])
    for node in free:
        graph.setdefault(node, set()).add(("H",))
        graph.setdefault(("H",), set()).add(node)
    return graph


def _reaches(graph, start, goal):
    seen, todo = {start}, [start]
    while todo:
        node = todo.pop()
        if node == goal:
            return True
        for nxt in graph.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return False


def feasible_moves(arcs, free, idx):
    """(can go up, can go down) for hidden arc idx: a cycle through it in the residual graph (network flow:
    the difference of two feasible tables decomposes into such cycles)."""
    a = arcs[idx]
    graph = _residual(arcs, free, skip=idx)
    up = a["f"] < a["ub"] and _reaches(graph, a["v"], a["u"])
    down = a["f"] > a["lb"] and _reaches(graph, a["u"], a["v"])
    return up, down


def disclosures(table, k):
    """Hidden values a reader could pin down: a hidden count of 1 to k-1 with only one possible value, or a hidden
    column of fewer than k people whose members can only have given one answer."""
    arcs, free = _hidden_arcs(table, k)
    found = []
    possible = {}
    for idx, a in enumerate(arcs):
        if a["kind"] != "cell":
            continue
        up, down = feasible_moves(arcs, free, idx)
        if 0 < a["f"] < k and not up and not down:
            found.append(("cell", a))
        if a["hidden_col"] and (a["f"] > 0 or up):
            possible.setdefault(a["col"], set()).add(a["row"])
    if table["type"] == "single":
        columns = table["columns"]
        everyone_same = any(r["cells"][0]["count"] == columns[0]["n"] for r in table["rows"] if r["kind"] == "category")
        small = [ci for ci in range(1, len(columns)) if columns[ci]["suppressed"] and 0 < columns[ci]["n"] < k]
        if 0 < table["blank_banner"] < k:
            small.append("blank")
        for col in small:
            if len(possible.get(col, ())) <= 1 and not everyone_same:
                found.append(("column", {"col": col}))
    return found


def apply_anonymity(table, k, force_hidden=()):
    """Primary suppression (groups and cells under k), then complementary suppression until no hidden value can be
    pinned down from what is printed (checked exactly by disclosures()). Returns the hidden group keys."""
    columns, rows = table["columns"], table["rows"]
    cat_rows = [r for r in rows if r["kind"] == "category"]
    notes = table["notes"]
    banner = columns[1:]
    table["anonymity_k"] = k
    if columns[0]["n"] < k:
        withhold(table, f"Anonymity: fewer than {k} people answered, so the whole table is hidden.")
        return set()
    for col in banner:
        if 0 < col["n"] < k or col["key"] in force_hidden:
            col["suppressed"] = True
    primary_cols = [c["label"] for c in banner if c["suppressed"]]
    if primary_cols:
        notes.append(f"Anonymity: {len(primary_cols)} group(s) hidden (fewer than {k} respondents, hidden with "
                     "another small group in any table of this run, or named in --hide): " + ", ".join(primary_cols) + ".")

    def hide_column(ci):
        columns[ci]["suppressed"] = True
        for r in cat_rows:
            r["cells"][ci]["suppressed"] = True

    for ci, col in enumerate(columns):
        if col["suppressed"]:
            hide_column(ci)
    primary = 0
    for r in cat_rows:
        for cell in r["cells"]:
            if not cell["suppressed"] and 0 < cell["count"] < k:
                cell["suppressed"] = True
                primary += 1
    secondary, extra_cols = 0, []

    def shown_groups():
        return [ci for ci in range(1, len(columns)) if not columns[ci]["suppressed"] and columns[ci]["n"] > 0]

    for _ in range(4 * (len(cat_rows) + 1) * (len(columns) + 1)):
        hidden_cols = [c for c in banner if c["suppressed"]]
        union = sum(c["n"] for c in hidden_cols)
        if hidden_cols and union < k and shown_groups():
            # The hidden groups together are Total minus the shown groups: keep hiding until they reach k people.
            found = [("column", {"col": None})]
        else:
            found = disclosures(table, k)
        if not found:
            break
        kind, info = found[0]
        col = info["col"]
        if kind == "cell" and isinstance(col, int) and not info.get("hidden_col"):
            i = info["row"]
            if col == 0:
                cands = [(r["cells"][0]["count"], ri, 0) for ri, r in enumerate(cat_rows)
                         if not r["cells"][0]["suppressed"] and r["cells"][0]["count"] > 0]
            else:
                cands = [(cat_rows[i]["cells"][cj]["count"], i, cj) for cj in shown_groups()
                         if cj != col and not cat_rows[i]["cells"][cj]["suppressed"] and cat_rows[i]["cells"][cj]["count"] > 0]
                if table["type"] == "single":
                    cands += [(r["cells"][col]["count"], ri, col) for ri, r in enumerate(cat_rows)
                              if not r["cells"][col]["suppressed"] and r["cells"][col]["count"] > 0]
            if cands:
                # Prefer the smallest cell that removes this disclosure on its own.
                cands.sort()
                pick = cands[0]
                for cand in cands:
                    cat_rows[cand[1]]["cells"][cand[2]]["suppressed"] = True
                    still = any(f[1] is info or (f[1].get("row") == i and f[1].get("col") == col)
                                for f in disclosures(table, k))
                    cat_rows[cand[1]]["cells"][cand[2]]["suppressed"] = False
                    if not still:
                        pick = cand
                        break
                cat_rows[pick[1]]["cells"][pick[2]]["suppressed"] = True
                secondary += 1
                continue
            if col > 0:
                hide_column(col)
                extra_cols.append(columns[col]["label"])
                continue
        groups = shown_groups()
        if groups:
            ci = min(groups, key=lambda c: (columns[c]["n"], columns[c]["label"]))
            hide_column(ci)
            extra_cols.append(columns[ci]["label"])
            continue
        withhold(table, "Anonymity: no pattern of hidden cells protects every small count in this table, so the "
                        "whole table is hidden.")
        return set()
    else:
        withhold(table, "Anonymity: the table could not be protected cell by cell, so it is hidden.")
        return set()
    if extra_cols:
        notes.append("Anonymity: also hid " + ", ".join(sorted(extra_cols)) + ", so hidden groups cannot be "
                     "worked out as Total minus the shown groups.")
    if primary or secondary:
        # One combined count: splitting it into "under k" and "complementary" would bound each hidden value.
        notes.append(f"Anonymity: {primary + secondary} cell(s) hidden (fewer than {k} respondents, or hidden with "
                     "them so no hidden count can be worked out from what is shown).")
    # Nets and means are hidden wherever one of their cells is.
    for r in rows:
        if r["kind"] != "net":
            continue
        for ci in range(len(columns)):
            if columns[ci]["suppressed"] or any(cr["cells"][ci]["suppressed"] for cr in cat_rows
                                                if cr["key"] in r["members"]):
                r["cells"][ci]["suppressed"] = True
    if table["mean_row"]:
        for ci in range(len(columns)):
            if columns[ci]["suppressed"] or any(cr["cells"][ci]["suppressed"] for cr in cat_rows):
                table["mean_row"]["cells"][ci]["suppressed"] = True
    for ci, col in enumerate(columns):
        if col["suppressed"] or col["n"] < k or table["type"] != "single":
            continue
        for r in cat_rows:
            if r["cells"][ci]["count"] == col["n"]:
                notes.append(f"Anonymity: everyone in {col['label']} gave the same answer ({r['label']}), so "
                             "showing this column reveals each member's answer. Consider hiding it (--hide).")
    return {c["key"] for c in banner if c["suppressed"]}


def withhold(table, note):
    """Hide a whole table: bases of groups, every cell, mean and nets; answer labels are dropped too, because a
    listed answer shows that somebody chose it."""
    for col in table["columns"]:
        col["suppressed"] = True
    table["rows"] = []
    table["mean_row"] = None
    table["withheld"] = True
    table["notes"].append(note)


# ------------------------------------------------------------------------------------------------ tests

def run_tests(table, args, weighted):
    columns = table["columns"]
    banner_idx = list(range(1, len(columns))) if args.test != "none" else []
    tests = []
    for r in table["rows"]:
        for x in range(len(banner_idx)):
            for y in range(x + 1, len(banner_idx)):
                i, j = banner_idx[x], banner_idx[y]
                ci, cj = columns[i], columns[j]
                a, b = r["cells"][i], r["cells"][j]
                rec = {"row": r["label"], "a": ci["letter"], "b": cj["letter"], "p": None, "p_adj": None,
                       "method": None, "significant": False, "higher": None}
                if a["suppressed"] or b["suppressed"]:
                    rec["method"] = "not tested: hidden by the anonymity rule"
                elif ci["small_base"] or cj["small_base"]:
                    rec["method"] = f"not tested: base under {args.small_base}"
                elif a["pct"] is None or b["pct"] is None:
                    rec["method"] = "not tested: empty column"
                else:
                    p, method, zval = pair_test(a["pct"], ci["n_eff"], b["pct"], cj["n_eff"], a["count"], ci["n"],
                                                b["count"], cj["n"], weighted, args.test)
                    rec["p"], rec["method"], rec["z"] = p, method, zval
                    if p is not None:
                        rec["higher"] = ci["letter"] if a["pct"] > b["pct"] else (cj["letter"] if b["pct"] > a["pct"] else None)
                rec["_cells"] = (r, i, j)
                tests.append(rec)
    mean_tests = []
    mr = table["mean_row"]
    if mr:
        for x in range(len(banner_idx)):
            for y in range(x + 1, len(banner_idx)):
                i, j = banner_idx[x], banner_idx[y]
                a, b = mr["cells"][i], mr["cells"][j]
                rec = {"row": "Mean", "a": columns[i]["letter"], "b": columns[j]["letter"], "p": None,
                       "p_adj": None, "method": None, "significant": False, "higher": None}
                if a["suppressed"] or b["suppressed"]:
                    rec["method"] = "not tested: hidden by the anonymity rule"
                elif columns[i]["small_base"] or columns[j]["small_base"]:
                    rec["method"] = f"not tested: base under {args.small_base}"
                elif a["mean"] is None or b["mean"] is None or a["sd"] is None or b["sd"] is None:
                    rec["method"] = "not tested: too few answers"
                else:
                    p, t = welch(a["mean"], a["sd"], a["n_eff"], b["mean"], b["sd"], b["n_eff"])
                    rec["p"], rec["method"], rec["t"] = p, "welch t", t
                    if p is None:
                        rec["method"] = "not tested: no spread in either group (Welch t undefined)"
                    if p is not None:
                        rec["higher"] = columns[i]["letter"] if a["mean"] > b["mean"] else (
                            columns[j]["letter"] if b["mean"] > a["mean"] else None)
                rec["_cells"] = (mr, i, j)
                mean_tests.append(rec)
    # With exactly two answers, the second row's tests mirror the first: count each comparison once.
    cat_labels = [r["label"] for r in table["rows"] if r["kind"] == "category"]
    mirrored = []
    if table["type"] == "single" and len(cat_labels) == 2:
        mirrored = [t for t in tests if t["row"] == cat_labels[1]]
        tests_for_adjust = [t for t in tests if t["row"] != cat_labels[1]]
    else:
        tests_for_adjust = tests
    families = []
    if args.family == "table":
        families = [tests_for_adjust + mean_tests]
    else:
        by_row = {}
        for t in tests_for_adjust + mean_tests:
            by_row.setdefault(t["row"], []).append(t)
        families = list(by_row.values())
    for fam in families:
        done = [t for t in fam if t["p"] is not None]
        adj = adjust_pvalues([t["p"] for t in done], args.adjust)
        for t, pa in zip(done, adj):
            t["p_adj"] = pa
            t["significant"] = pa < args.alpha and t["higher"] is not None
            t["family_size"] = len(done)
    first = {(t["a"], t["b"]): t for t in tests if cat_labels and t["row"] == cat_labels[0]}
    for t in mirrored:
        twin = first.get((t["a"], t["b"]))
        if twin is not None and t["p"] is not None:
            t["p_adj"] = twin["p_adj"]
            t["family_size"] = twin.get("family_size")
            t["significant"] = twin["significant"] and t["higher"] is not None
    for t in tests + mean_tests:
        r, i, j = t.pop("_cells")
        if t["significant"]:
            hi, lo = (i, j) if t["higher"] == columns[i]["letter"] else (j, i)
            cell = r["cells"][hi]
            # Letters stay a list of tokens: with more than 26 groups a letter can be "AA".
            cell["letters"] = sorted(cell["letters"] + [columns[lo]["letter"]], key=lambda s: (len(s), s))
    table["tests"] = tests + mean_tests
    table["tests_run"] = sum(1 for t in tests_for_adjust + mean_tests if t["p"] is not None)


def chi_square(table, weighted):
    """Pearson chi-square of independence over shown categories x banner columns. With weights, the weighted
    table is scaled to the Kish effective total (a first-order design-effect correction)."""
    columns = table["columns"][1:]
    cat_rows = [r for r in table["rows"] if r["kind"] == "category"]
    use_cols = [i + 1 for i, c in enumerate(columns)
                if c["weighted_base" if weighted else "n"] > 0 and not c["suppressed"]]
    if any(r["cells"][ci]["suppressed"] for r in cat_rows for ci in use_cols):
        # A statistic computed from hidden cells can be inverted to recover them (sources.md, Anonymity rule).
        return {"statistic": None, "df": None, "p": None,
                "note": "withheld: the anonymity rule hides cells in the groups it would test"}
    if len(use_cols) < 2 or len(cat_rows) < 2:
        return {"statistic": None, "df": None, "p": None, "note": "needs at least two groups and two answers"}
    # Equal weights (constant_w) report unweighted results: use the counts, or X2 would scale with the weight.
    obs = [[r["cells"][ci]["weighted_count" if weighted else "count"] for ci in use_cols] for r in cat_rows]
    obs = [row for row in obs if sum(row) > 0]
    if len(obs) < 2:
        return {"statistic": None, "df": None, "p": None, "note": "every answer is the same"}
    total = sum(sum(row) for row in obs)
    scale = 1.0
    if weighted:
        accs = [table["columns"][ci]["acc"] for ci in use_cols]
        n_eff_groups = kish(sum(a.w for a in accs), sum(a.w2 for a in accs))
        scale = n_eff_groups / total if total > 0 else 1.0
    obs = [[v * scale for v in row] for row in obs]
    total = sum(sum(row) for row in obs)
    row_t = [sum(row) for row in obs]
    col_t = [sum(obs[i][j] for i in range(len(obs))) for j in range(len(use_cols))]
    stat, small, tiny, cells = 0.0, 0, 0, 0
    for i, row in enumerate(obs):
        for j, o in enumerate(row):
            e = row_t[i] * col_t[j] / total
            cells += 1
            if e < COCHRAN_MIN_EXPECTED:
                small += 1
            if e < 1:
                tiny += 1
            stat += (o - e) ** 2 / e if e > 0 else 0.0
    df = (len(obs) - 1) * (len(use_cols) - 1)
    out = {"statistic": stat, "df": df, "p": chi2_sf(stat, df),
           "cramers_v": math.sqrt(stat / (total * min(len(obs) - 1, len(use_cols) - 1))) if total > 0 else None,
           "expected_under_5": small, "cells": cells,
           "weighted": weighted, "reliable": not (tiny or small > 0.2 * cells),
           "groups": [table["columns"][ci]["label"] for ci in use_cols]}
    if not out["reliable"]:
        out["note"] = (f"{small} of {cells} expected counts are under 5"
                       + (f" and {tiny} under 1" if tiny else "") + ": the chi-square approximation is unreliable "
                       "(Cochran 1954). Combine small answers or groups, or read the pairwise tests.")
        if len(obs) == 2 and len(use_cols) == 2 and not weighted:
            a = int(round(obs[0][0]))
            out["fisher_p"] = fisher_exact(a, int(round(col_t[0])), int(round(obs[0][1])), int(round(col_t[1])))
    return out


# ------------------------------------------------------------------------------------------------ analysis

def analyse(args):
    notes = []
    if not 0 < args.alpha < 1:
        raise InputError("--alpha must be between 0 and 1, e.g. 0.05")
    if args.confidence > 1:
        args.confidence /= 100.0
    if not 0 < args.confidence < 1:
        raise InputError("--confidence must be between 0 and 1 (or 50-99.9 as a percent)")
    if args.anonymity is not None and args.anonymity < 2:
        raise InputError("--anonymity K needs K of 2 or more (the usual minimum is 5)")
    headers, rows, data, dropped = load(args, notes)
    if args.list_columns:
        return {"columns": describe_columns(headers, rows, args)}
    if data["rows_used"] == 0 or sum(f * w for f, w in zip(data["freq"], data["w"])) <= 0:
        raise InputError("no usable rows (every count, or every weight, is 0)")
    if args.anonymity and sum(data["freq"]) < args.anonymity:
        raise InputError(f"the file has {sum(data['freq'])} respondents, fewer than the anonymity threshold "
                         f"{args.anonymity}, so no table can be shown without identifying someone")
    na = set(args.na if args.na is not None else DEFAULT_NA)
    multi = set(args.multi or [])
    orders = parse_kv_list(args.order, "--order")
    nets = parse_nets(args.net)
    seen_nets = set()
    for net_col, net_label, _ in nets:
        if net_col not in args.rows:
            raise InputError(f"--net names {net_col!r}, which is not one of --rows")
        if (net_col, net_label.lower()) in seen_nets:
            raise InputError(f"--net {net_col}:{net_label} is given twice; give each net on a question its own name")
        seen_nets.add((net_col, net_label.lower()))
    hide = parse_kv_list(args.hide, "--hide", merge=True)
    for col in hide:
        if col not in (args.banner or []):
            raise InputError(f"--hide names {col!r}, which is not one of --banner")
    if hide and not args.anonymity:
        raise InputError("--hide works with the anonymity rule: add --anonymity")
    banner_vars = []
    for b in args.banner or []:
        if b in multi:
            raise InputError(f"{b} is a multi-select column; a banner column must give each respondent one group")
        bv = Variable(b, [r[b] for r in data["rows"]], na, order=orders.get(b))
        banner_vars.append(bv)
    weighted = bool(args.weight)
    z = z_for(args.confidence)
    row_vars = []
    for rname in args.rows:
        rv = Variable(rname, [r[rname] for r in data["rows"]], na, args.multi_sep if rname in multi else None,
                      orders.get(rname))
        if not rv.categories:
            notes.append(f"{rname}: no answers; skipped.")
            continue
        if args.means and not rv.numeric and rname not in multi:
            notes.append(f"{rname}: answers are not numeric codes, so no mean row.")
        row_vars.append(rv)
    if args.anonymity and weighted:
        notes.append("Anonymity: the rule is checked on respondent counts. Weighted percentages and bases add "
                     "information it does not model; for an employee or other identifiable population, release "
                     "unweighted tables.")
    by_banner = {}
    for bv in banner_vars or [None]:
        letter_map = force = None
        if bv is not None:
            letter_map, _ = banner_letters(bv, data)
            force = set()
            lookup = {str(bv.labels[key]).lower(): key for key in bv.labels}
            for item in hide.get(bv.name, []):
                key = lookup.get(item.strip().lower())
                if key is None:
                    raise InputError(f"--hide {bv.name}: {item!r} is not a group of that column; groups are "
                                     + ", ".join(repr(bv.labels[x]) for x in bv.labels))
                force.add(key)
        # One suppression decision per banner: a group hidden in any table is hidden in all of them, so a reader
        # cannot subtract one table from another (repeat until no new group is hidden).
        for _ in range(len(letter_map or {}) + 1):
            built = [build_table(rv, bv, data, args, z, nets, letter_map, force or ()) for rv in row_vars]
            hidden = set().union(*[t["hidden_groups"] for t in built]) if built else set()
            if bv is None or not args.anonymity or hidden <= force:
                break
            force |= hidden
        by_banner[bv.name if bv is not None else None] = built
    tables = []
    for idx in range(len(row_vars)):
        for bv in banner_vars or [None]:
            tables.append(by_banner[bv.name if bv is not None else None][idx])
    if weighted:
        w_all = [f * w for f, w in zip(data["freq"], data["w"])]
        W = sum(w_all)
        W2 = sum(f * w * w for f, w in zip(data["freq"], data["w"]))
        n = sum(data["freq"])
        neff = kish(W, W2)
        wstats = {"n": n, "sum_w": W, "n_eff": neff, "deff": (n / neff) if neff else None,
                  "efficiency": (neff / n) if n else None}
    else:
        wstats = None
    total_tests = sum(t["tests_run"] for t in tables)
    return {
        "tool": "survey-crosstabs",
        "version": VERSION,
        "input": {
            "file": args.input,
            "rows_read": data["rows_read"],
            "rows_used": data["rows_used"],
            "respondents": sum(data["freq"]),
            "weight_col": args.weight,
            "count_col": args.count_col,
            "notes": notes,
        },
        "settings": {
            "test": args.test, "adjust": args.adjust, "family": args.family, "alpha": args.alpha,
            "confidence": args.confidence, "small_base": args.small_base, "anonymity_k": args.anonymity,
        },
        "weights": wstats,
        "tables": [strip_table(t) for t in tables],
        "tests_run": total_tests,
    }


COLUMN_FIELDS = ("key", "label", "letter", "n", "weighted_base", "n_eff", "small_base", "suppressed")
CELL_FIELDS = ("count", "weighted_count", "pct", "ci", "letters", "suppressed")
MEAN_FIELDS = ("mean", "sd", "n_eff", "ci", "letters", "suppressed")
TABLE_FIELDS = ("row_var", "banner_var", "type", "blank_row", "blank_banner", "notes", "anonymity_k", "withheld",
                "tests", "tests_run", "chi_square")


def strip_table(t):
    """The released table, built from an allowlist: a hidden group or cell keeps only its label and the fact that
    it is hidden (every count, base, share, interval, effective n and letter goes)."""
    out = {key: t[key] for key in TABLE_FIELDS if key in t}
    out["withheld"] = bool(t.get("withheld"))
    out["columns"] = []
    if out["withheld"]:
        # Nothing about who answered: the blank counts give the number of answers, the column list who gave them.
        out["blank_row"] = out["blank_banner"] = None
        out["rows"], out["mean_row"] = [], None
        for key in ("chi_square", "nets"):
            if key in out:
                out[key] = None
        return out
    for c in t["columns"]:
        col = {key: c[key] for key in COLUMN_FIELDS}
        col["key"] = col["key"] if col["key"] is None or isinstance(col["key"], (int, str)) else str(col["key"])
        if c["suppressed"]:
            col.update({"n": None, "weighted_base": None, "n_eff": None, "small_base": None})
        out["columns"].append(col)
    rows = []
    for r in t["rows"]:
        rr = {"label": r["label"], "kind": r["kind"]}
        if r["kind"] == "net":
            rr["members"] = [str(m) for m in r["members"]]
        rr["cells"] = []
        for cell in r["cells"]:
            c = {key: cell[key] for key in CELL_FIELDS}
            if c["suppressed"]:
                c.update({"count": None, "weighted_count": None, "pct": None, "ci": None, "letters": []})
            rr["cells"].append(c)
        rows.append(rr)
    out["rows"] = rows
    out["mean_row"] = None
    if t["mean_row"]:
        cells = []
        for cell in t["mean_row"]["cells"]:
            c = {key: cell[key] for key in MEAN_FIELDS}
            if c["suppressed"]:
                c.update({"mean": None, "sd": None, "n_eff": None, "ci": None, "letters": []})
            cells.append(c)
        out["mean_row"] = {"label": "Mean", "kind": "mean", "cells": cells}
    return out


def describe_columns(headers, rows, args):
    na = set(args.na if args.na is not None else DEFAULT_NA)
    out = []
    for h in headers:
        vals = [(r[h] or "").strip() for r in rows]
        answered = [v for v in vals if v not in na]
        distinct = []
        for v in answered:
            if v not in distinct:
                distinct.append(v)
        multi_hint = sum(1 for v in answered if args.multi_sep in v) > 0.2 * max(1, len(answered))
        out.append({"column": h, "answered": len(answered), "blank": len(vals) - len(answered),
                    "distinct": len(distinct), "examples": distinct[:5],
                    "numeric_codes": bool(answered) and all(code_of(v) is not None for v in answered),
                    "looks_multi_select": multi_hint})
    return out


# ------------------------------------------------------------------------------------------------ rendering

def fmt_pct(p):
    return "-" if p is None else f"{100 * p:.0f}%"


def fmt_num(x, digits=0):
    if x is None:
        return "-"
    return f"{x:,.{digits}f}"


def fmt_letters(letters):
    return ("" if all(len(x) == 1 for x in letters) else ",").join(letters)


def fmt_p(p):
    if p is None:
        return "-"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def md(text):
    """A label safe inside a Markdown table cell: an escaped pipe, newlines as spaces."""
    return " ".join(str(text).split()).replace("|", "\\|")


def render(result, show_ci=False):
    if "columns" in result and "tables" not in result:
        lines = ["| Column | Answered | Blank | Distinct | Numeric codes | Multi-select? | Examples |",
                 "|---|---|---|---|---|---|---|"]
        for c in result["columns"]:
            lines.append(f"| {c['column']} | {c['answered']} | {c['blank']} | {c['distinct']} | "
                         f"{'yes' if c['numeric_codes'] else 'no'} | {'maybe' if c['looks_multi_select'] else 'no'} | "
                         + "; ".join(c["examples"]) + " |")
        return "\n".join(lines)
    s = result["settings"]
    inp = result["input"]
    out = [f"# Crosstabs: {inp['file']}", ""]
    out.append(f"Rows read {inp['rows_read']}, used {inp['rows_used']}"
               + (f" ({inp['respondents']} respondents from counts)" if inp["count_col"] else "") + ".")
    if result["weights"]:
        wst = result["weights"]
        out.append(f"Weighted by `{inp['weight_col']}`: n = {wst['n']}, Kish effective n = {wst['n_eff']:.1f}, "
                   f"design effect from weighting = {wst['deff']:.2f} (efficiency {100 * wst['efficiency']:.0f}%).")
    for note in inp["notes"]:
        out.append(f"- {note}")
    adj = {"holm": "Holm", "bh": "Benjamini-Hochberg", "bonferroni": "Bonferroni", "none": "no adjustment"}[s["adjust"]]
    out.append("")
    out.append(f"Letters: column-proportion tests ({'z, Fisher exact when an expected count is under 5' if s['test'] == 'auto' else s['test']}"
               f"), {adj} within each {s['family']}, alpha {s['alpha']}. A letter marks a share (or mean) "
               "significantly higher than the column with that letter. Total is not tested. "
               f"Columns with {'an effective' if result['weights'] else 'a'} base under {s['small_base']} are flagged "
               "and not tested."
               + (" With weights, tests use each group's Kish effective n: an approximation that ignores strata, "
                  "clusters and replicate weights." if result["weights"] else "")
               + (f" Anonymity rule: groups and cells under {s['anonymity_k']} respondents hidden "
                  "(shown as *), and any value that could be worked out from what is shown." if s["anonymity_k"] else ""))
    out.append(f"Tests run: {result['tests_run']}.")
    for t in result["tables"]:
        out.append("")
        title = t["row_var"] + (f" by {t['banner_var']}" if t["banner_var"] else "")
        out.append(f"## {title}" + (" (multi-select: shares add to more than 100%)" if t["type"] == "multi" else ""))
        out.append("")
        if t["withheld"]:
            for note in t["notes"]:
                out.append(f"- {note}")
            continue
        heads = [md(c["label"]) if c["letter"] is None else f"{md(c['label'])} ({c['letter']})" for c in t["columns"]]
        out.append("| | " + " | ".join(heads) + " |")
        out.append("|---" * (len(heads) + 1) + "|")

        def base_cell(c, key, digits=0):
            if c["suppressed"]:
                return "*"
            v = fmt_num(c[key], digits)
            return v + (" !" if key == "n" and c["small_base"] and c["letter"] is not None else "")

        out.append("| Base (n) | " + " | ".join(base_cell(c, "n") for c in t["columns"]) + " |")
        if result["weights"]:
            out.append("| Weighted base | " + " | ".join(base_cell(c, "weighted_base", 1) for c in t["columns"]) + " |")
            out.append("| Effective n | " + " | ".join(base_cell(c, "n_eff", 1) for c in t["columns"]) + " |")
        for r in t["rows"]:
            cells = []
            for cell in r["cells"]:
                if cell["suppressed"]:
                    cells.append("*")
                    continue
                txt = fmt_pct(cell["pct"])
                if show_ci and cell["ci"]:
                    txt += f" ({100 * cell['ci'][0]:.0f}-{100 * cell['ci'][1]:.0f})"
                if cell["letters"]:
                    txt += " " + fmt_letters(cell["letters"])
                cells.append(txt)
            label = f"**{md(r['label'])}**" if r["kind"] == "net" else md(r["label"])
            out.append(f"| {label} | " + " | ".join(cells) + " |")
        if t.get("mean_row"):
            cells = []
            for cell in t["mean_row"]["cells"]:
                if cell["suppressed"]:
                    cells.append("*")
                    continue
                txt = fmt_num(cell["mean"], 2)
                if show_ci and cell["ci"]:
                    txt += f" ({cell['ci'][0]:.2f}-{cell['ci'][1]:.2f})"
                if cell["letters"]:
                    txt += " " + fmt_letters(cell["letters"])
                cells.append(txt)
            out.append("| Mean | " + " | ".join(cells) + " |")
        out.append("")
        if t["blank_row"] or t["blank_banner"]:
            out.append(f"No answer to {t['row_var']}: {t['blank_row']} (left out of every base)."
                       + (f" No {t['banner_var']}: {t['blank_banner']} (in Total only)." if t["blank_banner"] else ""))
        cs = t.get("chi_square")
        if cs and cs.get("statistic") is not None:
            line = (f"Chi-square{' (weighted: Kish approximation, scaled to effective n)' if cs['weighted'] else ''}: "
                    f"X2 = {cs['statistic']:.2f}, df = {cs['df']}, p = {fmt_p(cs['p'])}"
                    + (f", Cramer's V = {cs['cramers_v']:.2f}." if cs.get("cramers_v") is not None else "."))
            if not cs["reliable"]:
                line += " " + cs["note"]
                if "fisher_p" in cs:
                    line += f" Fisher exact p = {fmt_p(cs['fisher_p'])}."
            out.append(line)
        elif cs:
            out.append(f"Chi-square: not computed ({cs.get('note')}).")
        small = [c["label"] for c in t["columns"] if c["small_base"] and not c["suppressed"] and c["letter"]]
        if small:
            out.append(f"! Small base (under {s['small_base']}): " + ", ".join(small) + ". Directional only, not tested.")
        for note in t["notes"]:
            out.append(f"- {note}")
    return "\n".join(out)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="survey_crosstabs.py",
        description="Crosstabs (banner tables) with bases, significance letters, chi-square, weights and an "
                    "anonymity rule.",
        epilog="Example: python3 scripts/survey_crosstabs.py survey.csv --rows q1 q2 --banner plan --weight wt",
    )
    parser.add_argument("input", help="CSV, one row per respondent (or per cell with --count-col)")
    parser.add_argument("--list-columns", action="store_true", help="list columns with answered/distinct counts, then stop")
    parser.add_argument("--rows", nargs="+", metavar="COL", help="question column(s) to tabulate (the table rows)")
    parser.add_argument("--banner", nargs="+", metavar="COL", help="group column(s) across the top (segments)")
    parser.add_argument("--weight", metavar="COL", help="respondent weight column (e.g. from survey-weighting)")
    parser.add_argument("--count-col", metavar="COL", help="aggregated input: number of respondents in each row")
    parser.add_argument("--multi", nargs="+", metavar="COL", help="row columns that hold several answers per cell")
    parser.add_argument("--multi-sep", default=";", help="separator inside a multi-select cell (default ;)")
    parser.add_argument("--net", action="append", metavar="COL:LABEL=v1;v2",
                        help="add a net row, e.g. 'q1:Satisfied=4;5' (repeatable)")
    parser.add_argument("--means", action="store_true", help="add a mean row (Welch t letters) for numeric-coded rows")
    parser.add_argument("--order", action="append", metavar="COL=v1;v2;...", help="category order for a column")
    parser.add_argument("--na", nargs="*", help="cell values that mean no answer (default: blank, NA, N/A, #N/A, "
                                                "NaN, NULL, None)")
    parser.add_argument("--test", choices=["auto", "z", "none"], default="auto",
                        help="pairwise test: auto (z, or Fisher exact when an expected count is under 5), z, none")
    parser.add_argument("--adjust", choices=["holm", "bh", "bonferroni", "none"], default="holm",
                        help="multiple-comparison adjustment (default holm)")
    parser.add_argument("--family", choices=["table", "row"], default="table",
                        help="tests adjusted together: every test in a table (default) or each row (as SPSS)")
    parser.add_argument("--alpha", type=float, default=0.05, help="significance level for letters (default 0.05)")
    parser.add_argument("--confidence", type=float, default=0.95, help="interval confidence, 0.95 or 95")
    parser.add_argument("--small-base", type=float, default=DEFAULT_SMALL_BASE,
                        help=f"flag and do not test columns with a smaller (effective) base (default {DEFAULT_SMALL_BASE})")
    parser.add_argument("--anonymity", type=int, nargs="?", const=DEFAULT_ANONYMITY_K, metavar="K",
                        help=f"hide groups and cells with fewer than K respondents (default K {DEFAULT_ANONYMITY_K})")
    parser.add_argument("--hide", action="append", metavar="COL=g1;g2",
                        help="with --anonymity, also hide these groups in every table (keep the same groups hidden "
                             "across waves), e.g. 'team=Legal;HR'")
    parser.add_argument("--show-ci", action="store_true", help="print intervals in the text tables")
    parser.add_argument("--delimiter", help="comma, semicolon, tab, pipe or one character (default: sniffed)")
    parser.add_argument("--skip-rows", type=int, help="rows under the header to skip (Qualtrics is detected)")
    parser.add_argument("--allow-drop", action="store_true",
                        help="go on when more than 5%% of rows have no usable weight or count (they are counted)")
    parser.add_argument("--json", action="store_true", help="machine-readable output, full precision")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = analyse(args)
    except InputError as exc:
        print(f"survey-crosstabs: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str) if args.json else render(result, args.show_ci))
    return 0


if __name__ == "__main__":
    sys.exit(main())
