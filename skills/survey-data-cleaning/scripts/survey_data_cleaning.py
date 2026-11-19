#!/usr/bin/env python3
"""Survey data cleaning: flag speeders, straight-liners, duplicates, failed attention checks,
low-effort or copied open answers, inconsistent answers, high item non-response and platform
fraud fields in a survey export CSV.

The script FLAGS. It never changes the input file, and it removes rows only when --drop-if is given;
removed rows go to a separate file with the reason. Every threshold is in references/sources.md.

Standard library only, Python 3.9+. No network.

Usage:
  python3 scripts/survey_data_cleaning.py export.csv --out-dir cleaned \\
      --grid sat=g1..g6 --attention "ac1=Strongly disagree" --open-cols feedback \\
      --rule "exp_gt_age: years_experience > age" [--drop-if "count>=2"] [--json]
"""
import argparse
import csv
import hashlib
import io
import json
import math
import re
import statistics
import sys
from fractions import Fraction
from pathlib import Path

# Checks that count toward flag_count.
CHECKS = ["speeder", "straightliner", "duplicate", "attention_fail", "inconsistent", "high_missing"]
# Candidates a person must read: reported in their own columns, counted only after a reviewer confirms one (--confirm).
CANDIDATES = ["open_text_candidate", "pattern_candidate", "identical_answers", "shared_ip"]
# Platform fraud fields: reported in their own columns, never counted in flag_count.
PLATFORM = ["platform_bot", "platform_ballot_stuffing", "platform_duplicate"]
REPORT_ONLY = CANDIDATES + PLATFORM
ALL_FLAGS = CHECKS + REPORT_ONLY
ID_NAMES = ["id", "respondent_id", "response_id", "responseid", "respondentid"]
DURATION_NAMES = ["duration", "duration_sec", "duration_seconds", "duration (in seconds)"]
DUP_KEY_NAMES = ["email", "e-mail", "email_address", "ip", "ip_address", "ipaddress"]
IP_NAMES = {"ip", "ip_address", "ipaddress", "ip address"}
# Form-tool metadata that is not a question (Google Forms, Microsoft Forms, Typeform); left out of the default question columns.
FORM_META = {"timestamp", "submitted at", "submitted", "date submitted", "submission time", "start date", "end date", "start time",
             "end time", "completion time", "last modified time", "network id"}
QUALTRICS_META = {"startdate", "enddate", "status", "ipaddress", "progress", "duration (in seconds)", "finished", "recordeddate", "responseid",
                  "recipientlastname", "recipientfirstname", "recipientemail", "externalreference", "locationlatitude", "locationlongitude",
                  "distributionchannel", "userlanguage"}
QUALTRICS_NOT_REAL = {"1": "survey preview", "survey preview": "survey preview", "2": "survey test", "survey test": "survey test",
                      "17": "offline preview", "offline preview": "offline preview", "256": "synthetic response", "synthetic": "synthetic response"}
# Qualtrics' own Q_ fields (fraud, timing, data-quality); a question renamed Q_1 or Q_NPS is a question, not metadata.
QUALTRICS_Q_META = {"q_recaptchascore", "q_recaptchastatus", "q_ballotboxstuffing", "q_duplicaterespondent", "q_totalduration", "q_url",
                    "q_language", "q_chl", "q_datapolicyviolations", "q_emailopened"}
QUALTRICS_Q_META_PREFIXES = ("q_relevantid", "q_straightlining", "q_unanswered", "q_ambiguoustext")
RELEVANT_ID = ["q_relevantidduplicate", "q_relevantidduplicatescore", "q_relevantidfraudscore", "q_relevantidlaststartdate"]
KEY_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
KEY_POS = {c: (r, i) for r, row in enumerate(KEY_ROWS) for i, c in enumerate(row)}
# Four-key runs that occur inside ordinary words ("property", German "Wert"); see references/sources.md.
KEY_RUN_EXCEPTIONS = {"erty", "wert"}
VOWELS = set("aeiouy")
RSI_CAP = 3  # Leiner 2019: page speed factors are capped at 3 before averaging
DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t"}


class InputError(Exception):
    pass


def norm(value):
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def truthy(value):
    return norm(value) in ("true", "1", "yes")


def parse_fraction(text, name, closed_top=False):
    try:
        value = Fraction(str(text).strip())
    except (ValueError, ZeroDivisionError):
        raise InputError(f"{name}: '{text}' is not a number or a fraction such as 1/3")
    if not (0 < value < 1 or (closed_top and value == 1)):
        raise InputError(f"{name}: must be between 0 and 1, got {text}")
    return value


def require_columns(cols, headers, what):
    missing = [c for c in cols if c not in headers]
    if missing:
        raise InputError(f"{what}: column(s) not in the file: {', '.join(missing)}. Columns found: {', '.join(headers)}")


def expand_columns(spec, headers, what):
    """'a,b,c' or 'first..last' (a range in file order), or a mix. Fails on unknown columns."""
    cols = []
    for part in [p.strip() for p in spec.split(",") if p.strip()]:
        if ".." in part:
            first, last = [p.strip() for p in part.split("..", 1)]
            require_columns([first, last], headers, what)
            i, j = headers.index(first), headers.index(last)
            if j < i:
                raise InputError(f"{what}: range {part} runs backwards in the file")
            cols.extend(headers[i : j + 1])
        else:
            cols.append(part)
    require_columns(cols, headers, what)
    if len(set(cols)) != len(cols):
        raise InputError(f"{what}: a column is listed twice in '{spec}'")
    return cols


def find_by_name(headers, names):
    return [h for h in headers if h.strip().lower() in names]


def median_of(values):
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


DECIMAL_COMMA_RE = re.compile(r"^[+-]?\d+,\d+$")


def to_fraction(cell, decimal_comma=False):
    """A number cell as a Fraction. With decimal_comma (semicolon or tab files), '312,5' reads as 312.5. Raises ValueError."""
    cell = (cell or "").strip()
    if decimal_comma and DECIMAL_COMMA_RE.match(cell):
        cell = cell.replace(",", ".")
    if "/" in cell:
        raise ValueError(cell)  # '1/5' in an answer cell is a date or text, not the number 0.2
    try:
        return Fraction(cell)
    except ZeroDivisionError:
        raise ValueError(cell)


def finite_float(value):
    """float() of a Fraction, raising ValueError (not OverflowError) when it is too large for a float."""
    try:
        return float(value)
    except OverflowError:
        raise ValueError(str(value))


def positive_number(cell, what, rid, decimal_comma=False, allow_zero=False):
    try:
        value = to_fraction(cell, decimal_comma)
        finite_float(value)
    except ValueError:
        raise InputError(f"{what}: '{cell}' (id {rid}) is not a number, or is too large")
    if value < 0 or (value == 0 and not allow_zero):
        raise InputError(f"{what}: {cell} (id {rid}) is not " + ("zero or more" if allow_zero else "positive"))
    return value


# ---------- reading ----------


def read_table(path, delimiter_arg):
    if not path.is_file():
        raise InputError(f"input file not found: {path}")
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            text, encoding = raw.decode("utf-16"), "UTF-16 (Excel Unicode Text)"
        except UnicodeDecodeError:
            raise InputError("input starts with a UTF-16 byte-order mark but is not valid UTF-16; re-export the CSV as UTF-8")
        return finish_read(raw, text, encoding, delimiter_arg)
    try:
        text, encoding = raw.decode("utf-8-sig"), ("UTF-8 with BOM" if raw.startswith(b"\xef\xbb\xbf") else "UTF-8")
    except UnicodeDecodeError:
        try:
            text, encoding = raw.decode("cp1252"), "Windows-1252 (cp1252), because it is not valid UTF-8"
        except UnicodeDecodeError:
            raise InputError("input is neither UTF-8 nor Windows-1252; re-export the CSV as UTF-8")
    return finish_read(raw, text, encoding, delimiter_arg)


def finish_read(raw, text, encoding, delimiter_arg):
    if delimiter_arg == "auto":
        # The header record ends at the first line break outside quotes; a quoted header may span lines.
        quoted, end = False, len(text)
        for k, ch in enumerate(text):
            if ch == '"':
                quoted = not quoted
            elif ch in "\r\n" and not quoted:
                end = k
                break
        outside = re.sub(r'"[^"]*"', "", text[:end])
        counts = {name: outside.count(ch) for name, ch in DELIMITERS.items()}
        name = max(counts, key=lambda k: (counts[k], k == "comma"))
        if counts[name] and sorted(counts.values())[-2] == counts[name]:
            raise InputError("cannot tell the delimiter from the header row; pass --delimiter comma, semicolon or tab")
    else:
        name = delimiter_arg
    # Only \r and \n end a record: a line separator (U+2028) or form feed pasted into an answer stays in its cell.
    table = list(csv.reader(io.StringIO(text, newline=""), delimiter=DELIMITERS[name]))
    return raw, table, f"read as {encoding}, {name}-delimited" + (" (detected)" if delimiter_arg == "auto" else ""), name


def split_header(table, notes):
    """Returns (headers, extra header rows, data rows, is_qualtrics). Handles the Qualtrics three-row header."""
    if not table or not any(h.strip() for h in table[0]):
        raise InputError("input has no header row")
    headers = table[0]
    if any(not h.strip() for h in headers):
        raise InputError("the header row has blank column names. If this is a SurveyMonkey export, its first two rows are both headers: "
                         "merge them into one row of unique names (or export with condensed/single-row headers) and run again")
    if len(set(headers)) != len(headers):
        dupes = sorted({h for h in headers if headers.count(h) > 1})
        raise InputError(f"duplicate column names in the header: {', '.join(dupes)}")
    extra = 0
    for k in (1, 2):
        if k < len(table) and any(c.strip().startswith('{"ImportId"') for c in table[k]):
            extra = k
    if extra:
        notes.append(f"Qualtrics export detected: {extra} extra header row(s) (question text and ImportId) skipped; they are kept in the clean file")
    elif len(table) > 1 and headers[0] == "StartDate" and table[1] and table[1][0].strip() == "Start Date":
        extra = 1
        notes.append("Qualtrics export detected: 1 extra header row (question text) skipped; it is kept in the clean file")
    body = [r for r in table[1 + extra :] if any(c.strip() for c in r)]
    if not body:
        raise InputError("input has a header but no respondent rows")
    for n, r in enumerate(body, 1):
        if len(r) != len(headers):
            raise InputError(f"data row {n} has {len(r)} cells, the header has {len(headers)}")
    is_qualtrics = bool(extra) or "ResponseId" in headers
    return headers, table[1 : 1 + extra], body, is_qualtrics


# ---------- per-answer helpers ----------


def longest_run(values):
    """Longest run of identical consecutive non-blank answers; a blank breaks the run."""
    best = run = 0
    previous = None
    for value in values:
        value = norm(value)
        if not value:
            run, previous = 0, None
            continue
        run = run + 1 if value == previous else 1
        previous = value
        best = max(best, run)
    return best


def numeric_answers(values, decimal_comma=False):
    """Answered cells as numbers, or None when any answered cell is not a number. NaN or infinity raises ValueError."""
    out = []
    for v in values:
        v = (v or "").strip()
        if not v:
            continue
        if v.lower().lstrip("+-") in ("nan", "inf", "infinity"):
            raise ValueError(v)
        try:
            number = to_fraction(v, decimal_comma)
        except ValueError:
            return None
        try:
            out.append(finite_float(number))
        except ValueError:
            raise ValueError(v)  # too large for a float: reported like infinity
    return out


def pattern_of(seq):
    """'repeating block of N' or 'staircase' for a fully answered numeric grid, else ''."""
    n = len(seq)
    for period in range(2, n // 2 + 1):
        if len(set(seq[:period])) > 1 and all(seq[i] == seq[i - period] for i in range(period, n)):
            return f"repeating block of {period}"
    steps = [b - a for a, b in zip(seq, seq[1:])]
    if all(abs(s) == 1 for s in steps):
        best = run = 1
        for a, b in zip(steps, steps[1:]):
            run = run + 1 if a == b else 1
            best = max(best, run)
        if best >= 3:
            return "staircase"
    return ""


def keyboard_run(text, exempt=KEY_RUN_EXCEPTIONS):
    """Longest run of neighbouring keys on one QWERTY row, in one direction, e.g. 'asdf' or 'poiu'.
    Runs in `exempt` (either direction) are skipped, so 'property, asdf' still finds 'asdf'."""
    best_len, best = 0, ""
    chars = text.lower()
    i = 0
    while i < len(chars):
        j, step = i, 0
        while j + 1 < len(chars) and chars[j] in KEY_POS and chars[j + 1] in KEY_POS:
            (r1, p1), (r2, p2) = KEY_POS[chars[j]], KEY_POS[chars[j + 1]]
            d = p2 - p1
            if r1 != r2 or d not in (1, -1) or (step and d != step):
                break
            step = d
            j += 1
        found = chars[i : j + 1]
        if j - i + 1 > best_len and found not in exempt and found[::-1] not in exempt:
            best_len, best = j - i + 1, found
        i = max(j, i + 1)
    return best


def open_text_reasons(text, min_chars, repeat_run, key_run):
    compact = re.sub(r"\s+", "", text or "")
    if not compact:
        return []
    reasons = []
    if len(compact) < min_chars:
        reasons.append("too_short")
    letters = [c for c in compact.lower() if c.isalpha()]
    if letters and len(letters) >= min_chars and all("a" <= c <= "z" for c in letters) and not (set(letters) & VOWELS):
        reasons.append("no_vowels")
    if re.search(r"([^\d\s])\1{%d,}" % (repeat_run - 1), compact.lower()):
        reasons.append("repeated_chars")
    run = keyboard_run(text)
    if len(run) >= key_run:
        reasons.append("keyboard_run")
    return reasons


def near_duplicates(answers, threshold):
    """Pairs (a, b, Jaccard) with a < b, Jaccard >= threshold and different texts, in (a, b) order.

    answers: list of (row, normalised text, frozenset of words). Exact prefix filtering (Bayardo, Ma & Srikant 2007):
    with words ordered rarest first, two sets with Jaccard >= t share a word among the first |x| - ceil(t|x|) + 1 words
    of each, so only pairs that do are compared. Same result as comparing every pair, without the n^2 pass.
    """
    freq = {}
    for _, _, toks in answers:
        for t in toks:
            freq[t] = freq.get(t, 0) + 1
    index, pairs = {}, []
    for b, (_, text_b, tok_b) in enumerate(answers):
        if not tok_b:
            continue
        ordered = sorted(tok_b, key=lambda t: (freq[t], t))
        prefix = ordered[: len(ordered) - math.ceil(threshold * len(ordered)) + 1]
        candidates = set()
        for t in prefix:
            candidates.update(index.get(t, ()))
        for a in sorted(candidates):
            text_a, tok_a = answers[a][1], answers[a][2]
            if text_a == text_b:
                continue
            small, big = sorted((len(tok_a), len(tok_b)))
            if Fraction(small, big) < threshold:
                continue
            score = Fraction(len(tok_a & tok_b), len(tok_a | tok_b))
            if score >= threshold:
                pairs.append((a, b, score))
        for t in prefix:
            index.setdefault(t, []).append(b)
    return sorted(pairs, key=lambda p: (p[0], p[1]))


# ---------- consistency rules ----------

TOKEN_RE = re.compile(
    r"""\s*(?:(?P<str>"[^"]*"|'[^']*')|(?P<num>\d+(?:\.\d+)?)|(?P<op>==|!=|<=|>=|<|>)|(?P<col>\[[^\]]+\]|[A-Za-z_][\w.]*)|(?P<sign>[+-]))"""
)


def parse_rule(text, headers, index):
    """name: A OP B [and C OP D ...]. Operand: column, [column with spaces], number, "text", column +/- number."""
    name = f"rule{index}"
    m = re.match(r"^\s*([\w-]+)\s*:\s*(.+)$", text)
    body = text
    if m:
        name, body = m.group(1), m.group(2)
    tokens, pos = [], 0
    while pos < len(body):
        if not body[pos:].strip():
            break
        t = TOKEN_RE.match(body, pos)
        if not t:
            raise InputError(f"--rule '{text}': cannot read from '{body[pos:].strip()}'")
        tokens.append((t.lastgroup, t.group(t.lastgroup)))
        pos = t.end()

    def operand(i):
        if i >= len(tokens):
            raise InputError(f"--rule '{text}': incomplete comparison")
        kind, value = tokens[i]
        if kind == "str":
            return ("str", value[1:-1]), i + 1
        if kind == "num":
            return ("num", Fraction(value)), i + 1
        if kind == "sign" and i + 1 < len(tokens) and tokens[i + 1][0] == "num":
            return ("num", Fraction(tokens[i + 1][1]) * (1 if value == "+" else -1)), i + 2
        if kind == "col" and value.lower() != "and":
            col = value[1:-1] if value.startswith("[") else value
            require_columns([col], headers, f"--rule '{text}'")
            if i + 2 < len(tokens) and tokens[i + 1][0] == "sign" and tokens[i + 2][0] == "num":
                offset = Fraction(tokens[i + 2][1]) * (1 if tokens[i + 1][1] == "+" else -1)
                return ("col", col, offset), i + 3
            return ("col", col, Fraction(0)), i + 1
        raise InputError(f"--rule '{text}': expected a column, number or quoted text, got '{value}'")

    conditions, i = [], 0
    while True:
        left, i = operand(i)
        if i >= len(tokens) or tokens[i][0] != "op":
            raise InputError(f"--rule '{text}': expected one of == != < <= > >=")
        op = tokens[i][1]
        right, i = operand(i + 1)
        if "str" in (left[0], right[0]) and op not in ("==", "!="):
            raise InputError(f"--rule '{text}': quoted text can only be compared with == or !=")
        conditions.append((left, op, right))
        if i >= len(tokens):
            break
        if tokens[i][0] != "col" or tokens[i][1].lower() != "and":
            raise InputError(f"--rule '{text}': expected 'and' or the end, got '{tokens[i][1]}'")
        i += 1
    return {"name": name, "text": body.strip(), "conditions": conditions}


def eval_condition(cond, row, decimal_comma=False):
    """True, False, or None when a needed cell is blank or not a number (not evaluable)."""
    left, op, right = cond
    text_mode = "str" in (left[0], right[0])
    # column == column (no offset) on text cells compares the text, e.g. fav_brand == least_fav_brand.
    if not text_mode and op in ("==", "!=") and left[0] == right[0] == "col" and not left[2] and not right[2]:
        cells = [(row.get(o[1]) or "").strip() for o in (left, right)]
        if all(cells):
            try:
                for c in cells:
                    to_fraction(c, decimal_comma)
            except ValueError:
                text_mode = True

    def value(operand):
        if operand[0] == "str":
            return norm(operand[1])
        if operand[0] == "num":
            return operand[1]
        cell = (row.get(operand[1]) or "").strip()
        if not cell:
            return None
        if text_mode:
            return norm(cell)
        try:
            return to_fraction(cell, decimal_comma) + operand[2]  # exact: 0.1 + 0.2 == 0.3
        except ValueError:
            return None

    a, b = value(left), value(right)
    if a is None or b is None:
        return None
    return {"==": a == b, "!=": a != b, "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]


def eval_rule(rule, row, decimal_comma=False):
    results = [eval_condition(c, row, decimal_comma) for c in rule["conditions"]]
    if any(r is False for r in results):
        return False
    if any(r is None for r in results):
        return None
    return True


def parse_drop_rule(text):
    """Comma = OR. Each term is count>=N, not_screened, or flag names joined with + (all of them)."""
    terms = []
    for part in [p.strip() for p in text.split(",") if p.strip()]:
        m = re.match(r"^count\s*>=\s*(\d+)$", part)
        if m:
            if int(m.group(1)) < 1:
                raise InputError("--drop-if: count>=N needs N of at least 1")
            terms.append(("count", int(m.group(1))))
        elif part == "not_screened":
            terms.append(("not_screened", None))
        else:
            names = [n.strip() for n in part.split("+")]
            bad = [n for n in names if n not in ALL_FLAGS]
            if bad:
                raise InputError(f"--drop-if: unknown check '{', '.join(bad)}'. Use count>=N, not_screened or: {', '.join(ALL_FLAGS)}")
            terms.append(("all", names))
    if not terms:
        raise InputError("--drop-if: empty rule")
    return terms


# ---------- main analysis ----------


def analyse(args):
    path = Path(args.input)
    notes = []
    raw, table, how, delimiter = read_table(path, args.delimiter)
    notes.append(how)
    # Semicolon and tab exports come from locales that write 312,5 for 312.5; a comma file cannot hold an unquoted decimal comma.
    dc = delimiter != "comma"
    headers, extra_rows, body, is_qualtrics = split_header(table, notes)
    rows = [dict(zip(headers, r)) for r in body]
    n = len(rows)
    lower = {h.strip().lower(): h for h in headers}

    # id column
    if args.id_col:
        require_columns([args.id_col], headers, "--id-col")
        id_col = args.id_col
    else:
        hits = find_by_name(headers, ID_NAMES)
        id_col = hits[0] if len(hits) == 1 else None
        notes.append(f"id column: {id_col} (found by name)" if id_col else "id column: none named or found; rows are identified by row number")
    ids = [(r[id_col].strip() if id_col else "") or f"row{i}" for i, r in enumerate(rows, 1)]

    # rules stated before the data were seen
    before = (args.set_before or "").strip()
    known = ALL_FLAGS + ["drop"]
    if before and before not in ("all", "none"):
        bad = [x.strip() for x in before.split(",") if x.strip() not in known]
        if bad:
            raise InputError(f"--set-before: unknown name '{', '.join(bad)}'. Use all, none, or: {', '.join(known)}")

    def set_before(name):
        if not before:
            return "not stated"
        if before == "all" or (before != "none" and name in [x.strip() for x in before.split(",")]):
            return "yes"
        return "no (post hoc)"

    # rows that are not real, finished responses (Qualtrics Status / Finished): counted, not screened
    not_screened = {}
    if is_qualtrics:
        for i, r in enumerate(rows):
            reasons = []
            if "Status" in r and norm(r["Status"]) in QUALTRICS_NOT_REAL:
                reasons.append(QUALTRICS_NOT_REAL[norm(r["Status"])])
            if "Finished" in r and norm(r["Finished"]) in ("0", "false"):
                reasons.append("unfinished")
            if reasons:
                not_screened[i] = ", ".join(reasons)
        present = [c for c in ("Status", "Finished") if c in headers]
        notes.append("Qualtrics Status / Finished: " + (f"{', '.join(present)} read; {len(not_screened)} preview, test or unfinished row(s) set aside, not screened"
                                                       if present else "columns not present; every row was screened"))
    active = [i for i in range(n) if i not in not_screened]
    if not active:
        raise InputError("every row is a preview, test or unfinished response; nothing to screen")

    flags = [{c: None for c in ALL_FLAGS} for _ in rows]
    details = [[] for _ in rows]
    extra_cols = {}  # column name -> list of values for the flags file
    log = []

    def entry(check, status, rule, threshold, flagged, extra=None):
        item = {"check": check, "status": status, "rule": rule, "threshold": threshold, "set_before_results": set_before(check) if status == "run" else "",
                "n_flagged": len(flagged), "share_flagged": round(len(flagged) / len(active), 4), "ids": [ids[i] for i in flagged], "counts_toward_flag_count": check in CHECKS,
                "kind": "counted" if check in CHECKS else "candidate" if check in CANDIDATES else "platform", "_rows": list(flagged)}
        item.update(extra or {})
        log.append(item)

    # columns used by several checks
    if args.duration_col:
        require_columns([args.duration_col], headers, "--duration-col")
        dur_col = args.duration_col
    else:
        hits = find_by_name(headers, DURATION_NAMES)
        dur_col = hits[0] if len(hits) == 1 else None
    page_cols = expand_columns(args.page_time_cols, headers, "--page-time-cols") if args.page_time_cols else []
    if args.speed_by:
        require_columns([args.speed_by], headers, "--speed-by")
    if args.dup_cols is None:
        dup_cols, dup_source = find_by_name(headers, DUP_KEY_NAMES), "found by name"
    elif args.dup_cols.strip().lower() == "none":
        dup_cols, dup_source = [], "disabled"
    else:
        dup_cols, dup_source = expand_columns(args.dup_cols, headers, "--dup-cols"), "given"
    if args.item_cols:
        item_cols = expand_columns(args.item_cols, headers, "--item-cols")
    else:
        skip = set(([id_col] if id_col else []) + ([dur_col] if dur_col else []) + dup_cols + page_cols)
        if is_qualtrics:
            meta = {h for h in headers if h.strip().lower() in QUALTRICS_META | QUALTRICS_Q_META
                    or h.strip().lower().startswith(QUALTRICS_Q_META_PREFIXES)}
            if meta - skip:
                notes.append("question columns: Qualtrics metadata columns left out (" + ", ".join(h for h in headers if h in meta - skip) + ")")
            skip |= meta
        form_meta = [h for h in headers if norm(h) in FORM_META and h not in skip]
        if form_meta:
            notes.append("question columns: form metadata columns left out (" + ", ".join(form_meta) + ")")
            skip |= set(form_meta)
        item_cols = [h for h in headers if h not in skip]
    if not item_cols:
        raise InputError("no question columns left for the item non-response check; name them with --item-cols")
    answered = [sum(1 for c in item_cols if r[c].strip()) for r in rows]

    # 1. speeders
    fraction = parse_fraction(args.speed_fraction, "--speed-fraction")
    if dur_col or page_cols:
        group = {i: (norm(rows[i][args.speed_by]) or "(blank)") if args.speed_by else "all" for i in active}
        durations, reasons = {}, {i: [] for i in active}
        info = {}
        if dur_col:
            for i in active:
                cell = rows[i][dur_col].strip()
                if cell:
                    durations[i] = positive_number(cell, f"duration column '{dur_col}'", ids[i], dc, allow_zero=True)
            if not durations and not page_cols:
                raise InputError(f"duration column '{dur_col}' has no values")
            if not durations:
                notes.append(f"duration column '{dur_col}' is blank for every screened respondent: speed uses the page times only")
            groups = {}
            for g in sorted(set(group.values())):
                values = [durations[i] for i in durations if group[i] == g]
                if values:
                    med = median_of(values)
                    groups[g] = {"n": len(values), "median": float(med), "cutoff": float(med * fraction), "_cut": med * fraction}
                    if not med:
                        notes.append(f"speeder: the median duration{' in ' + g if args.speed_by else ''} is 0, so no one there can be under a "
                                     "share of it; look at the 0-second rows by hand")
            for i, d in durations.items():
                if d < groups[group[i]]["_cut"]:
                    reasons[i].append(f"{float(d):g} < {groups[group[i]]['cutoff']:g}")
        if durations:
            per_item = {i: durations[i] / answered[i] for i in durations if answered[i]}
            extra_cols["duration_per_item"] = [f"{float(per_item[i]):.2f}" if i in per_item else "" for i in range(n)]
            if args.min_per_item is not None:
                floor = positive_number(args.min_per_item, "--min-per-item", "option", dc)
                for i, v in per_item.items():
                    if v < floor:
                        reasons[i].append(f"{float(v):.2f} per answered item < {args.min_per_item}")
            if args.speed_by:
                info["groups"] = {g: {k: v for k, v in d.items() if k != "_cut"} for g, d in groups.items()}
            else:
                info.update({"median": groups["all"]["median"], "cutoff": groups["all"]["cutoff"]})
            info.update({"fraction": args.speed_fraction, "n_not_evaluable": len(active) - len(durations)})
        has_durations = bool(durations)
        rsi = {}
        if page_cols:
            cutoff_rsi = float(positive_number(args.rsi_cutoff, "--rsi-cutoff", "option"))
            factors = {i: [] for i in active}
            for col in page_cols:
                times = {i: positive_number(rows[i][col].strip(), f"page time column '{col}'", ids[i], dc, allow_zero=True)
                         for i in active if rows[i][col].strip()}
                for g in set(group.values()):
                    members = [i for i in times if group[i] == g]
                    if members:
                        med = median_of([times[i] for i in members])
                        for i in members:
                            # A page time of 0 is as fast as it gets: the capped factor (or 1 when the median is 0 too).
                            factor = med / times[i] if times[i] else (RSI_CAP if med else 1)
                            factors[i].append(min(float(factor), RSI_CAP))
            rsi = {i: sum(f) / len(f) for i, f in factors.items() if f}
            extra_cols["speed_index"] = [f"{rsi[i]:.2f}" if i in rsi else "" for i in range(n)]
            for i, v in rsi.items():
                if v > cutoff_rsi:
                    reasons[i].append(f"speed index {v:.2f} > {cutoff_rsi:g}")
            info["speed_index_cutoff"] = cutoff_rsi
        flagged = []
        for i in active:
            if i in durations or i in rsi:
                flags[i]["speeder"] = int(bool(reasons[i]))
                if reasons[i]:
                    flagged.append(i)
                    details[i].append("speeder: " + "; ".join(reasons[i]))
        rule = " or ".join(([f"{dur_col} < {args.speed_fraction} x median" + (f" within {args.speed_by}" if args.speed_by else "")] if has_durations else [])
                           + ([f"{dur_col} per answered item < {args.min_per_item}"] if has_durations and args.min_per_item is not None else [])
                           + ([f"page speed index > {args.rsi_cutoff}"] if page_cols else []))
        if has_durations and args.speed_by:
            threshold = "; ".join(f"{g}: n {d['n']}, median {d['median']:g}, cut-off {d['cutoff']:g}" for g, d in info["groups"].items())
        elif has_durations:
            threshold = f"median {info['median']:g}, cut-off {info['cutoff']:g}"
        else:
            threshold = f"{len(page_cols)} page time columns"
        entry("speeder", "run", rule, threshold, flagged, info)
    else:
        entry("speeder", "skipped", "no duration column named (--duration-col) or found by name, and no --page-time-cols", "", [])

    # 2. straight-lining, variability and patterns per grid
    grids = {}
    for spec in args.grid or []:
        if "=" not in spec:
            raise InputError(f"--grid '{spec}': use name=col1,col2,... or name=first..last")
        name, cols = spec.split("=", 1)
        name = name.strip()
        cols = expand_columns(cols, headers, f"--grid {name}")
        if len(cols) < 2:
            raise InputError(f"--grid {name}: a grid needs at least 2 columns")
        if name in grids:
            raise InputError(f"--grid {name}: name used twice")
        grids[name] = cols
    if grids:
        if args.longstring_min is not None and args.longstring_fraction is not None:
            raise InputError("use --longstring-min or --longstring-fraction, not both")
        if args.longstring_min is not None and args.longstring_min < 2:
            raise InputError("--longstring-min must be at least 2")
        if args.min_grid_items < 2 or args.pattern_min_items < 4:
            raise InputError("--min-grid-items must be at least 2 and --pattern-min-items at least 4")
        lfrac = parse_fraction(args.longstring_fraction, "--longstring-fraction") if args.longstring_fraction is not None else None
        thresholds, short = {}, []
        for name, cols in grids.items():
            if len(cols) < args.min_grid_items:
                short.append(name)
            if args.longstring_min is not None:
                thresholds[name] = args.longstring_min
            elif lfrac is not None:
                thresholds[name] = int(len(cols) * lfrac) + 1  # strictly more than the fraction of the grid
            else:
                thresholds[name] = len(cols)  # every item identical
            extra_cols[f"longstring_{name}"] = [""] * n
            extra_cols[f"irv_{name}"] = [""] * n
        flagged, patterned, no_irv = [], [], set()
        for i in active:
            hit, pat = [], []
            for name, cols in grids.items():
                values = [rows[i][c] for c in cols]
                run = longest_run(values)
                extra_cols[f"longstring_{name}"][i] = run
                try:
                    numbers = numeric_answers(values, dc)
                except ValueError as bad:
                    col = next(c for c in cols if rows[i][c].strip() == str(bad))
                    raise InputError(f"--grid {name}: '{bad}' in column {col} (id {ids[i]}, data row {i + 1}) is not a finite number; blank the cell or fix it")
                if numbers is None:
                    no_irv.add(name)
                elif len(numbers) >= 2:
                    extra_cols[f"irv_{name}"][i] = f"{statistics.stdev(numbers):.4f}"
                if name in short:
                    continue
                if run >= thresholds[name]:
                    hit.append(f"{name} {run}/{len(cols)}")
                elif numbers and len(numbers) >= args.min_grid_items and len(set(numbers)) == 1:
                    hit.append(f"{name} zero variance over {len(numbers)} answered")
                elif numbers is None:
                    labels = [norm(v) for v in values if norm(v)]
                    if len(labels) >= args.min_grid_items and len(set(labels)) == 1:
                        hit.append(f"{name} same answer on all {len(labels)} answered")
                if numbers and len(numbers) == len(cols) >= args.pattern_min_items:
                    kind = pattern_of(numbers)
                    if kind:
                        pat.append(f"{name} {kind}")
            flags[i]["straightliner"] = int(bool(hit))
            flags[i]["pattern_candidate"] = int(bool(pat))
            if hit:
                flagged.append(i)
                details[i].append("straightliner: " + ", ".join(hit))
            if pat:
                patterned.append(i)
                details[i].append("pattern_candidate: " + ", ".join(pat))
        mode = ("--longstring-min" if args.longstring_min is not None else f"more than {args.longstring_fraction} of the grid" if lfrac is not None else "every item in the grid identical")
        grid_info = {g: {"columns": c, "threshold": thresholds[g], "flagged": g not in short, "variability": "not computed (answers are not numbers)" if g in no_irv else "computed"} for g, c in grids.items()}
        entry("straightliner", "run", f"longest run of identical consecutive answers in a grid >= threshold ({mode}), or zero variability over {args.min_grid_items}+ answered items",
              "; ".join(f"{g}: {thresholds[g]} of {len(c)} items" + (f" (reported only: fewer than {args.min_grid_items} items)" if g in short else "") for g, c in grids.items()),
              flagged, {"grids": grid_info, "min_grid_items": args.min_grid_items})
        entry("pattern_candidate", "run", "fully answered numeric grid that repeats a block (1-2-1-2) or steps by one (1-2-3-4-5); candidates to look at",
              f"grids of {args.pattern_min_items}+ items", patterned)
    else:
        entry("straightliner", "skipped", "no --grid given", "", [])
        entry("pattern_candidate", "skipped", "no --grid given", "", [])

    # 3. duplicates (the first row of a group is kept unflagged; later rows are flagged)
    # Counted: a repeated id or a repeated value in an identifying key column (email, or a column the user named).
    # Candidates only: identical answers (short surveys repeat by chance) and a shared IP (households, offices, carriers).
    ignore = expand_columns(args.dup_ignore, headers, "--dup-ignore") if args.dup_ignore else []
    compare_cols = [h for h in headers if h != id_col and h not in ignore]
    dup_reasons, same_rows, same_ip = [[] for _ in rows], [[] for _ in rows], [[] for _ in rows]
    seen = {}
    for i in active:
        key = tuple(rows[i][c] for c in compare_cols)
        if key in seen:
            same_rows[i].append(f"answers identical to {ids[seen[key]]}")
            details[seen[key]].append(f"note: first of identical rows ({ids[i]})")
        else:
            seen[key] = i
    ip_cols = [c for c in dup_cols if norm(c) in IP_NAMES]
    key_cols = ([id_col] if id_col else []) + [c for c in dup_cols if c not in ip_cols]
    for col in key_cols + ip_cols:
        seen = {}
        for i in active:
            value = norm(rows[i][col])
            if not value:
                continue
            if value in seen:
                (same_ip if col in ip_cols else dup_reasons)[i].append(f"same {col} as {ids[seen[value]]}")
            else:
                seen[value] = i
    for check, reasons_by_row in (("duplicate", dup_reasons), ("identical_answers", same_rows), ("shared_ip", same_ip)):
        if check == "shared_ip" and not ip_cols:
            entry(check, "skipped", "no IP column among the key columns", "", [])
            continue
        flagged = []
        for i in active:
            flags[i][check] = int(bool(reasons_by_row[i]))
            if reasons_by_row[i]:
                flagged.append(i)
                details[i].append(f"{check}: " + "; ".join(reasons_by_row[i]))
        if check == "duplicate":
            entry(check, "run", "later row repeating an earlier value in the id column or an identifying key column",
                  "key columns: " + (", ".join(key_cols) if key_cols else "none") + f" ({dup_source})", flagged, {"key_columns": key_cols})
        elif check == "identical_answers":
            entry(check, "run", "later row identical to an earlier one in all columns except the id" + (f" and {', '.join(ignore)}" if ignore else "")
                  + "; a candidate: in a short survey honest respondents give identical answers", f"{len(compare_cols)} columns compared", flagged)
        else:
            entry(check, "run", "later row repeating an earlier IP address; a candidate: a shared IP is not proof of a duplicate",
                  "IP columns: " + ", ".join(ip_cols), flagged, {"key_columns": ip_cols})

    # 4. attention checks
    checks = []
    for spec in args.attention or []:
        if "=" not in spec:
            raise InputError(f"--attention '{spec}': use column=expected answer")
        col, expected = spec.split("=", 1)
        require_columns([col.strip()], headers, "--attention")
        if col.strip() in [c for c, _ in checks]:
            raise InputError(f"--attention: column {col.strip()} is given twice; each check is one column, and one wrong answer must not count as two failures")
        checks.append((col.strip(), expected))
    if checks:
        blank_fails = args.attention_blank == "fail"
        need = args.attention_min_fails if args.attention_min_fails is not None else min(2, len(checks))
        if need < 1 or need > len(checks):
            raise InputError(f"--attention-min-fails must be between 1 and the number of checks ({len(checks)})")
        flagged, blank_ids = [], []
        for i in active:
            r = rows[i]
            if any(not r[col].strip() for col, _ in checks):
                blank_ids.append(ids[i])
            failed = [f"{col}='{r[col].strip()}'" if r[col].strip() else f"{col} blank" for col, expected in checks
                      if norm(r[col]) != norm(expected) and (blank_fails or r[col].strip())]
            flags[i]["attention_fail"] = int(len(failed) >= need)
            if failed:
                details[i].append(("attention_fail: " if len(failed) >= need else "note: attention checks failed below the threshold: ") + ", ".join(failed))
            if len(failed) >= need:
                flagged.append(i)
        rule = "failed attention checks >= threshold (" + ("a blank counts as a failure" if blank_fails else "a blank means the check was not shown and is not a failure") + ")"
        if need == 1 and len(checks) == 1:
            rule += "; one check: a single failure flags, a screening convention (Prolific allows it only in studies under 5 minutes)"
        entry("attention_fail", "run", rule, f"{need} of {len(checks)} checks", flagged,
              {"min_fails": need, "blank": args.attention_blank, "blank_ids": blank_ids, "checks": [{"column": c, "expected": e} for c, e in checks]})
    else:
        entry("attention_fail", "skipped", "no --attention column=expected given", "", [])

    # 5. open answers (candidates for a person to judge)
    open_cols = expand_columns(args.open_cols, headers, "--open-cols") if args.open_cols else []
    if open_cols:
        for name, value in (("--open-min-chars", args.open_min_chars), ("--repeat-run", args.repeat_run), ("--keyboard-run", args.keyboard_run), ("--paste-min-chars", args.paste_min_chars)):
            if value < 1:
                raise InputError(f"{name} must be at least 1")
        similar = None if str(args.similar_text).lower() == "off" else parse_fraction(args.similar_text, "--similar-text", closed_top=True)
        reasons = {i: [] for i in active}
        for col in open_cols:
            groups, long_answers = {}, []
            for i in active:
                for reason in open_text_reasons(rows[i][col], args.open_min_chars, args.repeat_run, args.keyboard_run):
                    reasons[i].append(f"{col} {reason}")
                text_norm = norm(rows[i][col])
                if len(text_norm) >= args.paste_min_chars:
                    groups.setdefault(text_norm, []).append(i)
                    long_answers.append((i, text_norm, frozenset(re.findall(r"\w+", text_norm))))
            for members in groups.values():
                if len(members) > 1:
                    for i in members:
                        reasons[i].append(f"{col} same_text_as " + ", ".join(ids[j] for j in members if j != i))
            if similar is not None:
                near = {}
                for a, b, score in near_duplicates(long_answers, similar):
                    i, j = long_answers[a][0], long_answers[b][0]
                    near.setdefault(i, []).append(f"{ids[j]} ({float(score):.2f})")
                    near.setdefault(j, []).append(f"{ids[i]} ({float(score):.2f})")
                for i, others in near.items():
                    reasons[i].append(f"{col} similar_text_to " + ", ".join(others))
        flagged = []
        for i in active:
            flags[i]["open_text_candidate"] = int(bool(reasons[i]))
            if reasons[i]:
                flagged.append(i)
                details[i].append("open_text_candidate: " + "; ".join(reasons[i]))
        entry("open_text_candidate", "run", "mechanical heuristics; candidates to read, counted only when a reviewer confirms one (--confirm)",
              f"fewer than {args.open_min_chars} characters; no vowels; a character repeated {args.repeat_run}+ times; "
              f"{args.keyboard_run}+ neighbouring keys; same text of {args.paste_min_chars}+ characters from 2+ respondents"
              + ("" if similar is None else f"; word overlap (Jaccard) >= {args.similar_text} between two such answers"), flagged, {"columns": open_cols})
    else:
        entry("open_text_candidate", "skipped", "no --open-cols given", "", [])

    # 6. inconsistent answers
    rules = [parse_rule(t, headers, k) for k, t in enumerate(args.rule or [], 1)]
    if len({r["name"] for r in rules}) != len(rules):
        raise InputError("--rule: two rules share a name")
    if rules:
        flagged, not_evaluable = [], {r["name"]: [] for r in rules}
        for i in active:
            hit, evaluated = [], False
            for rule in rules:
                result = eval_rule(rule, rows[i], dc)
                if result is None:
                    not_evaluable[rule["name"]].append(ids[i])
                else:
                    evaluated = True
                    if result:
                        hit.append(rule["name"])
            if evaluated:
                flags[i]["inconsistent"] = int(bool(hit))
            if hit:
                flagged.append(i)
                details[i].append("inconsistent: " + ", ".join(hit))
        entry("inconsistent", "run", "; ".join(f"{r['name']}: {r['text']}" for r in rules), "the rule states the inconsistency; true = flagged", flagged,
              {"not_evaluable": not_evaluable})
    else:
        entry("inconsistent", "skipped", "no --rule given", "", [])

    # 7. item non-response
    max_missing = parse_fraction(args.max_missing, "--max-missing")
    shares, flagged = [], []
    for i in range(n):
        share = Fraction(len(item_cols) - answered[i], len(item_cols))
        shares.append(share)
        if i in not_screened:
            continue
        flags[i]["high_missing"] = int(share > max_missing)
        if share > max_missing:
            flagged.append(i)
            details[i].append(f"high_missing: {share.numerator}/{share.denominator} blank")
    entry("high_missing", "run", f"share of blank answers > {args.max_missing}", f"{len(item_cols)} question columns", flagged, {"n_item_columns": len(item_cols)})

    # 8. platform fraud fields (report only)
    recaptcha_min = parse_fraction(args.recaptcha_min, "--recaptcha-min")
    score_col, status_col = lower.get("q_recaptchascore"), lower.get("q_recaptchastatus")
    if score_col:
        flagged, errors, blank = [], 0, 0
        for i in active:
            cell = rows[i][score_col].strip()
            if status_col and norm(rows[i][status_col]) == "error":
                errors += 1
                continue
            if not cell:
                blank += 1
                continue
            try:
                score = to_fraction(cell, dc)
            except ValueError:
                raise InputError(f"{score_col}: '{cell}' (id {ids[i]}) is not a number")
            flags[i]["platform_bot"] = int(score < recaptcha_min)
            if score < recaptcha_min:
                flagged.append(i)
                details[i].append(f"platform_bot: {score_col} {cell} < {args.recaptcha_min}")
        entry("platform_bot", "run", f"{score_col} < {args.recaptcha_min}" + (f", ignored when {status_col} is error" if status_col else f" ({'Q_RecaptchaStatus'} not present, so errors cannot be excluded)"),
              f"{errors} with a reCAPTCHA error and {blank} blank: not evaluated", flagged, {"n_error": errors, "n_blank": blank})
    else:
        entry("platform_bot", "not present", "no Q_RecaptchaScore column in the file", "", [])
    for check, field in (("platform_ballot_stuffing", "q_ballotboxstuffing"), ("platform_duplicate", "q_duplicaterespondent")):
        col = lower.get(field)
        if col:
            flagged = []
            for i in active:
                flags[i][check] = int(truthy(rows[i][col]))
                if flags[i][check]:
                    flagged.append(i)
                    details[i].append(f"{check}: {col} = {rows[i][col].strip()}")
            entry(check, "run", f"{col} is true", "set by the survey platform", flagged)
        else:
            entry(check, "not present", f"no {'Q_BallotBoxStuffing' if 'ballot' in field else 'Q_DuplicateRespondent'} column in the file", "", [])
    old = [lower[f] for f in RELEVANT_ID if f in lower]
    if old:
        notes.append(f"RelevantID columns present ({', '.join(old)}): not used. Qualtrics deprecated RelevantID on 30 June 2025; newer responses hold only 0, false or blank")

    # reviewer overrides: --clear removes a flag, --confirm makes a candidate count toward flag_count
    def select(spec, option):
        """ID:CHECK (every screened row with that id) or row=N:CHECK (one row, numbered as in the flags file)."""
        if ":" not in spec:
            raise InputError(f"{option} '{spec}': use ID:check or row=N:check")
        who, check = spec.rsplit(":", 1)
        if check not in ALL_FLAGS:
            raise InputError(f"{option} '{spec}': unknown check '{check}'")
        m = re.match(r"^row=(\d+)$", who)
        if m:
            k = int(m.group(1)) - 1
            if not 0 <= k < n:
                raise InputError(f"{option} '{spec}': no data row {m.group(1)} (the file has {n})")
            matches = [k]
        else:
            matches = [i for i, x in enumerate(ids) if x == who]
            if not matches:
                raise InputError(f"{option} '{spec}': no respondent with id '{who}'")
        hits = [i for i in matches if flags[i][check] == 1]
        if not hits:
            raise InputError(f"{option} '{spec}': {who} is not flagged on {check}")
        return check, hits

    cleared, confirmed = [], [set() for _ in rows]
    for spec in args.clear or []:
        check, hits = select(spec, "--clear")
        for i in hits:
            flags[i][check] = 0
            details[i].append(f"cleared by reviewer: {check}")
            cleared.append({"id": ids[i], "row": i + 1, "check": check})
    for spec in args.confirm or []:
        check, hits = select(spec, "--confirm")
        if check not in CANDIDATES:
            raise InputError(f"--confirm '{spec}': only candidates can be confirmed ({', '.join(CANDIDATES)}); {check} already counts or is a platform field")
        for i in hits:
            confirmed[i].add(check)
            details[i].append(f"confirmed by reviewer: {check}")

    # the checks table shows final flags; initial hits and reviewer changes are kept beside them
    for e in log:
        initial = e.pop("_rows")
        if e["status"] != "run":
            continue
        final = [i for i in initial if flags[i][e["check"]] == 1]
        e.update({"n_initial": len(initial), "cleared_ids": [ids[i] for i in initial if flags[i][e["check"]] != 1],
                  "n_flagged": len(final), "share_flagged": round(len(final) / len(active), 4), "ids": [ids[i] for i in final]})
        if e["check"] in CANDIDATES:
            e["confirmed_ids"] = [ids[i] for i in final if e["check"] in confirmed[i]]

    counts = [None if i in not_screened else sum(1 for c in CHECKS if flags[i][c] == 1) + len(confirmed[i]) for i in range(n)]

    # drop rule
    drop = None
    if args.drop_if:
        terms = parse_drop_rule(args.drop_if)
        ran = {e["check"] for e in log if e["status"] == "run"}
        for kind, value in terms:
            if kind == "all" and [c for c in value if c not in ran]:
                raise InputError(f"--drop-if names a check that did not run: {', '.join(c for c in value if c not in ran)}")
        removed = []
        for i in range(n):
            for kind, value in terms:
                if (kind == "not_screened" and i in not_screened) or (i in active and ((kind == "count" and counts[i] >= value) or (kind == "all" and all(flags[i][c] == 1 for c in value)))):
                    removed.append(i)
                    break
        drop = {"rule": args.drop_if, "removed": removed, "preview": bool(args.preview)}
    elif args.preview:
        raise InputError("--preview needs --drop-if: it shows who that rule would remove without writing the clean file")

    compare_cols = expand_columns(args.compare_cols, headers, "--compare-cols") if args.compare_cols else []
    warn_share = parse_fraction(args.warn_share, "--warn-share")
    return {"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "headers": headers, "extra_rows": extra_rows, "body": body, "rows": rows, "ids": ids, "flags": flags,
            "details": details, "counts": counts, "confirmed": confirmed, "shares": shares, "log": log, "notes": notes, "cleared": cleared, "drop": drop, "extra_cols": extra_cols,
            "not_screened": not_screened, "active": active, "set_before_drop": set_before("drop"), "compare_cols": compare_cols, "warn_share": warn_share}


def write_outputs(result, args):
    path = result["path"]
    out_dir = Path(args.out_dir) if args.out_dir else path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    files = {"flags": out_dir / f"{stem}.flags.csv", "log": out_dir / f"{stem}.cleaning-log.md"}
    if result["drop"] and not result["drop"]["preview"]:
        files["clean"] = out_dir / f"{stem}.clean.csv"
        files["removed"] = out_dir / f"{stem}.removed.csv"
    for target in files.values():
        if target.resolve() == path.resolve():
            raise InputError(f"refusing to overwrite the input file: {target}")
    ids, flags, counts, active, not_screened = result["ids"], result["flags"], result["counts"], result["active"], result["not_screened"]
    n, m = len(ids), len(result["active"])
    extra = result["extra_cols"]

    with open(files["flags"], "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row", "id", "screened"] + CHECKS + ["flag_count"] + REPORT_ONLY + ["confirmed", "missing_share"] + list(extra) + ["details"])
        for i in range(n):
            w.writerow([i + 1, ids[i], f"no: {not_screened[i]}" if i in not_screened else "yes"] + ["" if flags[i][c] is None else flags[i][c] for c in CHECKS]
                       + ["" if counts[i] is None else counts[i]] + ["" if flags[i][c] is None else flags[i][c] for c in REPORT_ONLY]
                       + [", ".join(c for c in CANDIDATES if c in result["confirmed"][i])] + [f"{float(result['shares'][i]):.4f}"] + [extra[k][i] for k in extra] + [" | ".join(result["details"][i])])

    active_counts = [counts[i] for i in active]
    distribution = {str(k): active_counts.count(k) for k in sorted(set(active_counts))}
    ran = [e for e in result["log"] if e["status"] == "run"]
    one_plus, two_plus = sum(1 for c in active_counts if c >= 1), sum(1 for c in active_counts if c >= 2)
    limit = float(result["warn_share"])
    warnings = [f"{e['check']} flags {e['share_flagged']:.1%} of screened respondents, above {limit:.0%}: check the threshold, the column and the sample source before acting on it"
                for e in ran if e["share_flagged"] > limit]
    if two_plus / m > limit:
        warnings.append(f"{two_plus / m:.1%} of screened respondents have 2 or more flags, above {limit:.0%}: removing them would change the sample materially")
    overlap = {}
    names = [e["check"] for e in ran]
    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            both = sum(1 for i in active if flags[i][names[a]] == 1 and flags[i][names[b]] == 1)
            if both:
                overlap[f"{names[a]} + {names[b]}"] = both

    drop_summary, composition = None, {}
    removed = result["drop"]["removed"] if result["drop"] else [i for i in active if counts[i] >= 2]
    gone = set(removed)
    preview = bool(result["drop"] and result["drop"]["preview"])
    if result["drop"] and not preview:
        with open(files["clean"], "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(result["headers"])
            w.writerows(result["extra_rows"])
            w.writerows(r for i, r in enumerate(result["body"]) if i not in gone)
        with open(files["removed"], "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(result["headers"] + ["removed_reason"])
            for i in removed:
                why = f"not screened: {not_screened[i]}" if i in not_screened else "flags: " + ", ".join(c for c in ALL_FLAGS if flags[i][c] == 1)
                w.writerow(result["body"][i] + [f"--drop-if {result['drop']['rule']} ({why})"])
    if result["drop"]:
        drop_summary = {"rule": result["drop"]["rule"], "preview": preview, "set_before_results": result["set_before_drop"], "n_removed": len(removed), "n_kept": n - len(removed),
                        "share_removed": round(len(removed) / n, 4), "ids": [ids[i] for i in removed]}
        if len(removed) / n > limit:
            warnings.append(f"the removal rule takes out {len(removed) / n:.1%} of the file, above {limit:.0%}")
    for col in result["compare_cols"]:
        table = {}
        for i in (range(n) if result["drop"] else active):
            value = result["rows"][i][col].strip() or "(blank)"
            table.setdefault(value, [0, 0])[0 if i in gone else 1] += 1
        composition[col] = {v: {"removed": a, "kept": b} for v, (a, b) in sorted(table.items())}

    summary = {
        "input": str(path),
        "input_sha256": result["sha256"],
        "n_rows": n,
        "n_respondents": m,
        "not_screened": [{"row": i + 1, "id": ids[i], "reason": why} for i, why in not_screened.items()],
        "notes": result["notes"],
        "checks": result["log"],
        "cleared": result["cleared"],
        "flag_count_distribution": distribution,
        "sample": {"share_with_1_or_more_flags": round(one_plus / m, 4), "share_with_2_or_more_flags": round(two_plus / m, 4), "warn_share": limit, "warnings": warnings},
        "flag_overlap": overlap,
        "respondents": [{"row": i + 1, "id": ids[i], "flags": [c for c in CHECKS if flags[i][c] == 1], "flag_count": counts[i], "report_only": [c for c in REPORT_ONLY if flags[i][c] == 1],
                         "confirmed": [c for c in CANDIDATES if c in result["confirmed"][i]]}
                        for i in active if counts[i] or any(flags[i][c] == 1 for c in REPORT_ONLY)],
        "drop": drop_summary,
        "composition": {"groups": ("would be removed vs kept" if preview else "removed vs kept") if result["drop"] else "2+ flags vs the rest", "columns": composition} if composition else None,
        "files": {k: str(v) for k, v in files.items()},
    }

    lines = [f"# Cleaning log: {path.name}", "", f"- Input: `{path.name}` (SHA-256 `{result['sha256']}`), {n} rows, {m} screened. The input file was not changed."]
    lines += [f"- {note}" for note in result["notes"]]
    if not_screened:
        lines += ["", "## Not screened (kept in the file, counted here)", ""] + [f"- {ids[i]} (row {i + 1}): {why}" for i, why in not_screened.items()]
    lines += ["", "## Checks", "", "\"Set before results\" is what the user stated with --set-before: yes, no (post hoc), or not stated.", "",
              "Flagged, share and ids are after reviewer decisions; Hits is the count before them, and cleared or confirmed ids are listed.", "",
              "| Check | Rule | Threshold | Set before results | Hits | Flagged | Share | Ids | Cleared | Confirmed |", "|---|---|---|---|---|---|---|---|---|---|"]
    for e in result["log"]:
        label = e["check"] + {"counted": "", "candidate": " (candidate: counts only when confirmed)", "platform": " (report only)"}[e["kind"]]
        if e["status"] != "run":
            lines.append(f"| {label} | {'not present' if e['status'] == 'not present' else 'not run'}: {e['rule']} | | | | | | | | |")
        else:
            lines.append(f"| {label} | {e['rule'].replace('|', '/')} | {e['threshold']} | {e['set_before_results']} | {e['n_initial']} | {e['n_flagged']} of {m} | {e['share_flagged']:.1%} | "
                         f"{', '.join(e['ids']) or 'none'} | {', '.join(e['cleared_ids'])} | {', '.join(e.get('confirmed_ids', []))} |")
    for e in result["log"]:
        if e.get("blank_ids"):
            lines.append(f"\n- {e['check']}: blank in at least one check for {', '.join(e['blank_ids'])} (blank = {e['blank']}).")
        if e.get("n_not_evaluable"):
            lines.append(f"\n- {e['check']}: {e['n_not_evaluable']} respondent(s) had no duration and were not checked on it.")
        for name, who in (e.get("not_evaluable") or {}).items():
            if who:
                lines.append(f"\n- Rule {name}: not evaluable (blank or non-numeric) for {', '.join(who)}.")
    if result["cleared"]:
        lines += ["", "## Flags cleared by a reviewer", ""] + [f"- {c['id']} (row {c['row']}): {c['check']}" for c in result["cleared"]]
    confirmed_rows = [i for i in active if result["confirmed"][i]]
    if confirmed_rows:
        lines += ["", "## Candidates confirmed by a reviewer (counted in the flag count)", ""] + [f"- {ids[i]} (row {i + 1}): {', '.join(sorted(result['confirmed'][i]))}" for i in confirmed_rows]
    lines += ["", "## Sample summary", "", f"- With 1 or more flags: {one_plus} of {m} ({one_plus / m:.1%}). With 2 or more: {two_plus} of {m} ({two_plus / m:.1%}).", "",
              "| Flags | Respondents |", "|---|---|"] + [f"| {k} | {v} |" for k, v in distribution.items()]
    lines += [""] + ([f"- Warning: {w}" for w in warnings] or [f"- No check and no removal is above the {limit:.0%} comparison point."])
    lines += ["", "## Flags that occur together", ""] + ([f"- {k}: {v}" for k, v in overlap.items()] or ["- No respondent has two flags at once."])
    if composition:
        left = ("Would remove" if preview else "Removed") if result["drop"] else "2+ flags"
        right = "Kept" if result["drop"] else "Rest"
        lines += ["", f"## Who is affected ({left.lower()} vs {right.lower()})", ""]
        for col, table in composition.items():
            lines += [f"| {col} | {left} | {right} |", "|---|---|---|"] + [f"| {v} | {c['removed']} | {c['kept']} |" for v, c in table.items()] + [""]
    lines += ["", "## Removal", ""]
    if drop_summary and preview:
        lines.append(f"- Preview of `--drop-if {drop_summary['rule']}` (set before results: {drop_summary['set_before_results']}): would remove {drop_summary['n_removed']} of {n} ({drop_summary['share_removed']:.1%}); would keep {drop_summary['n_kept']}.")
        lines.append(f"- Would remove: {', '.join(drop_summary['ids']) or 'none'}. No clean or removed file was written; rerun without --preview once the user agrees.")
    elif drop_summary:
        lines.append(f"- Rule: `--drop-if {drop_summary['rule']}` (set before results: {drop_summary['set_before_results']}). Removed {drop_summary['n_removed']} of {n} ({drop_summary['share_removed']:.1%}); kept {drop_summary['n_kept']}.")
        lines.append(f"- Removed ids: {', '.join(drop_summary['ids']) or 'none'}. Rows and reasons: `{files['removed'].name}`. Clean file: `{files['clean'].name}`.")
        lines.append("- Report key results with and without the removed rows.")
    else:
        lines.append("- No rows removed (no --drop-if rule was given). Flags only.")
    files["log"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def build_parser():
    p = argparse.ArgumentParser(description="Flag low-quality survey responses. Flags only; removes rows only with --drop-if. The input file is never changed.")
    p.add_argument("input", help="survey export CSV (one row per respondent, header row; Qualtrics three-row headers are handled)")
    p.add_argument("--out-dir", help="folder for the output files (default: next to the input)")
    p.add_argument("--delimiter", default="auto", choices=["auto", "comma", "semicolon", "tab"], help="column separator (default: detected from the header row and reported)")
    p.add_argument("--id-col", help="respondent id column (default: a column named id / respondent_id / response_id / ResponseId, else row number)")
    p.add_argument("--duration-col", help="completion time column, any unit (default: a column named duration / duration_sec / 'Duration (in seconds)')")
    p.add_argument("--speed-fraction", default="1/3", help="speeder = duration below this fraction of the median (default 1/3; 0.5 is the stricter academic variant)")
    p.add_argument("--speed-by", metavar="COL", help="compute the median within each value of this column (survey path, device)")
    p.add_argument("--page-time-cols", help="per-page time columns; adds a speed index (median page time / own time, capped at 3, averaged)")
    p.add_argument("--rsi-cutoff", default="2.0", help="speeder when the page speed index is above this (default 2.0)")
    p.add_argument("--min-per-item", help="also flag when duration per answered item is below this (no default)")
    p.add_argument("--grid", action="append", metavar="NAME=COLS", help="a grid of same-scale items, e.g. sat=q1,q2,q3 or sat=q1..q8 (repeatable)")
    p.add_argument("--min-grid-items", type=int, default=4, help="grids with fewer items are reported but never flagged (default 4)")
    p.add_argument("--longstring-min", type=int, help="flag a run of at least this many identical consecutive answers (default: every item in the grid)")
    p.add_argument("--longstring-fraction", help="flag a run longer than this fraction of the grid, e.g. 0.5")
    p.add_argument("--pattern-min-items", type=int, default=6, help="grids need this many items for the pattern check (default 6)")
    p.add_argument("--dup-cols", help="key columns to check for repeats, e.g. email,ip; 'none' to disable (default: columns named email / ip / ...)")
    p.add_argument("--dup-ignore", help="columns to leave out of the identical-row comparison, e.g. timestamps")
    p.add_argument("--attention", action="append", metavar="COL=EXPECTED", help="attention check column and its correct answer (repeatable)")
    p.add_argument("--attention-min-fails", type=int, help="failed checks needed for a flag (default: 2, or 1 when only one check is given)")
    p.add_argument("--attention-blank", default="fail", choices=["fail", "unshown"],
                   help="a blank attention check: 'fail' (default) counts it as failed; 'unshown' means skip logic never showed it, so it is not a failure")
    p.add_argument("--open-cols", help="open-text columns to screen, e.g. feedback,why")
    p.add_argument("--open-min-chars", type=int, default=3, help="shorter answers are 'too_short' candidates (default 3)")
    p.add_argument("--repeat-run", type=int, default=4, help="same character this many times in a row (default 4)")
    p.add_argument("--keyboard-run", type=int, default=4, help="neighbouring keys on one keyboard row (default 4)")
    p.add_argument("--paste-min-chars", type=int, default=20, help="answers of at least this length are compared across respondents (default 20)")
    p.add_argument("--similar-text", default="0.8", help="word overlap (Jaccard) at or above which two answers are near-duplicates (default 0.8; 'off' to disable)")
    p.add_argument("--rule", action="append", metavar="'NAME: A OP B [and ...]'", help="an inconsistency, e.g. 'exp: years_experience > age' (repeatable)")
    p.add_argument("--item-cols", help="question columns for item non-response (default: all but id, duration, duplicate-key, page-time and platform metadata columns)")
    p.add_argument("--max-missing", default="0.5", help="flag when the share of blank answers is above this (default 0.5)")
    p.add_argument("--recaptcha-min", default="0.5", help="Q_RecaptchaScore below this is reported as a likely bot (default 0.5)")
    p.add_argument("--warn-share", default="0.12", help="warn when a check, the 2+ flag group or the removal is above this share (default 0.12)")
    p.add_argument("--set-before", metavar="all|none|NAMES", help="which rules were fixed before seeing results (pre-registration, panel contract): all, none, or check names and 'drop'")
    p.add_argument("--compare-cols", help="demographic columns: show who is removed (or has 2+ flags) against who is kept")
    p.add_argument("--clear", action="append", metavar="ID:CHECK", help="a reviewer's decision to clear a flag: ID:check (every row with that id carrying it) or row=N:check (one row); recorded in the log (repeatable)")
    p.add_argument("--confirm", action="append", metavar="ID:CHECK", help="a reviewer's decision that a candidate (open_text_candidate, pattern_candidate, identical_answers, shared_ip) is real; it then counts in flag_count (repeatable)")
    p.add_argument("--drop-if", help="write a clean file without matching rows: 'count>=2', 'duplicate', 'speeder+attention_fail', 'not_screened', or several joined by commas (any)")
    p.add_argument("--preview", action="store_true", help="with --drop-if: show who the rule would remove and the --compare-cols table, without writing the clean or removed file")
    p.add_argument("--json", action="store_true", help="print the summary as JSON")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = analyse(args)
        summary = write_outputs(result, args)
    except InputError as e:
        print(f"survey-data-cleaning: error: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(summary, indent=2))
        return 0
    m = summary["n_respondents"]
    print(f"{summary['n_rows']} rows in {summary['input']} (file not changed); {m} screened, {len(summary['not_screened'])} set aside")
    for note in summary["notes"]:
        print(f"  note: {note}")
    ran = [e["check"] for e in summary["checks"] if e["status"] == "run"]
    print("Checks run: " + (", ".join(ran) or "none") + ". Not run: " + (", ".join(e["check"] for e in summary["checks"] if e["status"] != "run") or "none"))
    for e in summary["checks"]:
        if e["status"] != "run":
            print(f"  {e['check']:<24} {e['status'] if e['status'] == 'not present' else 'not run'} ({e['rule']})")
        else:
            tag = {"counted": "", "candidate": " (candidates)", "platform": " (report only)"}[e["kind"]]
            changed = (f"; cleared {', '.join(e['cleared_ids'])}" if e["cleared_ids"] else "") + (f"; confirmed {', '.join(e['confirmed_ids'])}" if e.get("confirmed_ids") else "")
            print(f"  {e['check']:<24} {e['n_flagged']:>3} flagged{tag} ({e['share_flagged']:.1%})  [{e['threshold']}]  {', '.join(e['ids'])}{changed}")
    print("Flags per respondent: " + ", ".join(f"{k} flags: {v}" for k, v in summary["flag_count_distribution"].items()))
    for w in summary["sample"]["warnings"]:
        print(f"Warning: {w}")
    if summary["drop"] and summary["drop"]["preview"]:
        d = summary["drop"]
        print(f"Preview: --drop-if {d['rule']} would remove {d['n_removed']} of {summary['n_rows']} ({d['share_removed']:.1%}): {', '.join(d['ids']) or 'none'}. No clean file written.")
        for col, table in ((summary["composition"] or {}).get("columns") or {}).items():
            print(f"  {col}: " + "; ".join(f"{v} {c['removed']} removed / {c['kept']} kept" for v, c in table.items()))
    elif summary["drop"]:
        d = summary["drop"]
        print(f"Removed {d['n_removed']} of {summary['n_rows']} with --drop-if {d['rule']}: {', '.join(d['ids']) or 'none'}")
    else:
        print("No rows removed (flags only). Add --drop-if to write a clean file.")
    for k, v in summary["files"].items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
