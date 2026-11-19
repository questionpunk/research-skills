#!/usr/bin/env python3
"""Open-ended coding: the arithmetic around a codebook (the agent does the coding itself).

Subcommands:
  sample      seeded random sample of answers (codebook building, blind double coding)
  saturation  new codes per batch while the codebook is being built
  validate    check a codebook and a coded file (unknown codes, uncoded rows, quotes)
  counts      code frequencies with explicit denominators, nets, intervals, codebook health
  agreement   percent agreement, Cohen's kappa, Krippendorff's alpha, bootstrap intervals
  merge       write adjudicated codes back into the coded file

Standard library only, Python 3.9+. No network. Formulas and thresholds: references/sources.md.
Exit codes: 0 ok, 1 validate found problems, 2 bad input.
"""
import argparse
import csv
import io
import json
import math
import os
import random
import re
import sys
from collections import Counter
from fractions import Fraction
from itertools import combinations

NO_ANSWER = "NO_ANSWER"  # blank answer
UNCODABLE = "UNCODABLE"  # text with no usable content: "n/a", gibberish, off-topic
OTHER = "OTHER"  # a real answer that fits no code in the codebook
RESERVED = (OTHER, UNCODABLE, NO_ANSWER)
EXCLUSIVE = (UNCODABLE, NO_ANSWER)  # cannot be combined with any other code
CODEBOOK_COLUMNS = ("code", "label", "definition", "include", "exclude", "example_quote")
RESERVED_LABELS = {
    OTHER: "Other (a real answer that fits no code)",
    UNCODABLE: "Uncodable (n/a, gibberish, off-topic)",
    NO_ANSWER: "No answer (blank)",
}
# Typed text that is usually not an answer. Used only to raise a warning for a person to review.
NON_ANSWER_TEXT = {"n/a", "na", "none", "-", "--", ".", "no comment", "idk", "?", "x"}
SENTIMENTS = ("positive", "negative", "neutral", "mixed")
# Defaults below are conventions, each listed in references/sources.md.
DEFAULT_MIN_BASE = 30
DEFAULT_BOOTSTRAP = 2000
DEFAULT_RARE_BELOW = 5
DEFAULT_BROAD_ABOVE = 50.0
DEFAULT_OTHER_ABOVE = 10.0
PARADOX_AGREEMENT = 80.0  # percent agreement at or above this ...
PARADOX_KAPPA = 0.40  # ... with kappa below this is flagged
Z_95 = 1.959964
# Leading or trailing marks that show a quote was trimmed; removed before the word-for-word check.
TRIM_MARKS = ("[...]", "[…]", "...", "…")
# File delimiter: None = detect from the header line (comma, then semicolon, tab or pipe). Set by --csv-delimiter.
CSV_DELIMITER = None


class InputError(Exception):
    """Bad input: reported on stderr, exit code 2."""


# ---------------------------------------------------------------- reading files


def header_line(content):
    """The header row with quoted text removed, so a comma inside a quoted question does not count."""
    unquoted = re.sub(r'"(?:[^"]|"")*"', "", content[:65536])
    return re.split(r"[\r\n]", unquoted, maxsplit=1)[0]


def detect_delimiter(content):
    """Comma unless the header line has none and holds a semicolon, tab or pipe (European Excel exports)."""
    header = header_line(content)
    if "," in header:
        return ","
    priority = (";", "\t", "|")
    found = [(header.count(d), -priority.index(d), d) for d in priority if d in header]
    return max(found)[2] if found else ","


def read_csv(path, delimiter=None):
    forced = delimiter or CSV_DELIMITER
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            content = handle.read()
        if forced and forced not in header_line(content):
            forced = None  # --csv-delimiter names the separator of the files that use it; files this script wrote use commas
        reader = csv.DictReader(io.StringIO(content, newline=""), delimiter=forced or detect_delimiter(content))
        if not reader.fieldnames:
            raise InputError(f"{path}: empty file or no header row")
        fields = [f.strip() for f in reader.fieldnames]
        if len(set(fields)) != len(fields):
            raise InputError(f"{path}: duplicate column names in the header")
        rows = []
        for raw in reader:
            if None in raw:
                raise InputError(f"{path}: line {reader.line_num} has more cells than the header")
            rows.append({k.strip(): (v or "") for k, v in raw.items()})
    except FileNotFoundError:
        raise InputError(f"{path}: file not found")
    except UnicodeDecodeError:
        raise InputError(f"{path}: not UTF-8 text; re-save the file as UTF-8 CSV")
    except csv.Error as exc:
        raise InputError(f"{path}: not a readable CSV ({exc})")
    except OSError as exc:
        raise InputError(f"{path}: cannot be read ({exc.strerror or exc})")
    return fields, rows


def guard_output(out, inputs, option="--out"):
    """Refuse to write over a file the command reads."""
    if not out:
        return
    target = os.path.realpath(out)
    for path in inputs:
        if path and (os.path.realpath(path) == target or (os.path.exists(out) and os.path.exists(path) and os.path.samefile(out, path))):
            raise InputError(f"{option} {out} is also an input file; write to a new file so the input is kept")


def write_csv(path, columns, rows):
    try:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    except OSError as exc:
        raise InputError(f"{path}: cannot be written ({exc.strerror or exc})")


def need_column(path, fields, name, what):
    if name not in fields:
        hint = ""
        if len(fields) == 1:
            seps = [d for d in (";", "\t", "|", ",") if d in fields[0]]
            if seps:
                hint = f" The header looks separated by {seps[0]!r}: pass --csv-delimiter {seps[0]!r}."
        raise InputError(f"{path}: no {what} column named '{name}'. Columns found: {', '.join(fields)}.{hint}")


def squash(text):
    return " ".join(text.split())


def untrim(quote):
    """The quote without the '...' marks that show it was trimmed at either end."""
    quote = squash(quote)
    changed = True
    while changed and quote:
        changed = False
        for mark in TRIM_MARKS:
            if quote.startswith(mark):
                quote, changed = quote[len(mark):].strip(), True
            if quote.endswith(mark):
                quote, changed = quote[: -len(mark)].strip(), True
    return quote


def read_codebook(path, separator=";"):
    """Returns (ordered list of entries, list of problems). Reserved codes need not be listed.

    An optional `parent` column groups codes into nets. `separator` is the code separator of the coded files.
    """
    fields, rows = read_csv(path)
    missing = [c for c in CODEBOOK_COLUMNS if c not in fields]
    if missing:
        raise InputError(
            f"{path}: codebook must have the columns {', '.join(CODEBOOK_COLUMNS)}; missing: {', '.join(missing)}"
        )
    entries, problems, seen = [], [], set()
    for number, row in enumerate(rows, start=2):
        code = row["code"].strip()
        if not code:
            problems.append(f"codebook line {number}: empty code")
            continue
        if code in seen:
            problems.append(f"codebook line {number}: code '{code}' is defined twice")
            continue
        if "," in code or (separator and separator in code) or any(ch.isspace() for ch in code):
            problems.append(
                f"codebook line {number}: code '{code}' contains a space, a comma or the code separator "
                f"'{separator}'; use a short name such as SLOW_SUPPORT"
            )
        seen.add(code)
        if code.upper() in RESERVED and code not in RESERVED:
            problems.append(f"codebook line {number}: reserved code must be written '{code.upper()}'")
        required = ("label", "definition") if code in RESERVED else CODEBOOK_COLUMNS[1:]
        for column in required:
            if not row[column].strip():
                problems.append(f"codebook line {number}: code '{code}' has an empty '{column}'")
        entry = {c: row[c].strip() for c in CODEBOOK_COLUMNS}
        entry["parent"] = row.get("parent", "").strip()
        if entry["parent"] and code in RESERVED:
            problems.append(f"codebook line {number}: reserved code '{code}' cannot have a parent")
        entries.append(entry)
    for entry in entries:
        if entry["parent"] and (entry["parent"] in seen or entry["parent"] in RESERVED):
            problems.append(f"codebook: parent '{entry['parent']}' is also the name of a code; give nets their own names")
    if not [e for e in entries if e["code"] not in RESERVED]:
        raise InputError(f"{path}: codebook defines no codes")
    return entries, problems


def nets_from(entries):
    nets = {}
    for entry in entries:
        if entry["parent"] and entry["code"] not in RESERVED:
            nets.setdefault(entry["parent"], []).append(entry["code"])
    return nets


def add_csv_option(parser):
    parser.add_argument(
        "--csv-delimiter",
        help="delimiter between the columns of every CSV read (default: detected; a comma unless the header has none "
        "and holds ';', a tab or '|'). Output files use commas",
    )


def add_coded_options(parser, text_help="column with the answer text; a blank answer counts as NO_ANSWER"):
    parser.add_argument("--id-col", default="id", help="column with the row id (default: id)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--codes-col", help="one column holding all codes of the row (default: codes)")
    group.add_argument("--code-cols", help="comma-separated names of 0/1 columns, one per code")
    group.add_argument("--code-prefix", help="prefix of the 0/1 code columns, e.g. code_ (code = the rest)")
    parser.add_argument("--delimiter", "--code-sep", dest="delimiter", default=";", help="separator between codes inside --codes-col (default: ;). Not the file delimiter: see --csv-delimiter")
    add_csv_option(parser)
    parser.add_argument("--text-col", help=text_help)
    parser.add_argument("--codebook", help="codebook CSV (code,label,definition,include,exclude,example_quote[,parent])")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")


def read_coded(path, args, text_col=None, segment_col=None, extra_col=None, text_optional=False):
    """One dict per row: id, codes (ordered, unique), text, segment, extra, line. Structure errors only."""
    fields, rows = read_csv(path)
    if not rows:
        raise InputError(f"{path}: no data rows")
    need_column(path, fields, args.id_col, "id")
    if text_col and text_optional and text_col not in fields:
        text_col = None
    if text_col:
        need_column(path, fields, text_col, "answer text")
    if segment_col:
        need_column(path, fields, segment_col, "segment")
    if extra_col:
        need_column(path, fields, extra_col, "sentiment")
    wide = None
    if args.code_cols:
        wide = [(c.strip(), c.strip()) for c in args.code_cols.split(",") if c.strip()]
        for column, _ in wide:
            need_column(path, fields, column, "code")
    elif args.code_prefix:
        wide = [(f, f[len(args.code_prefix):]) for f in fields if f.startswith(args.code_prefix)]
        if not wide or any(not code for _, code in wide):
            raise InputError(f"{path}: no usable columns start with '{args.code_prefix}'")
    codes_col = args.codes_col or "codes"
    if wide is None:
        need_column(path, fields, codes_col, "codes")
        if not args.delimiter:
            raise InputError("--delimiter must not be empty")
    out, seen = [], set()
    for number, row in enumerate(rows, start=2):
        row_id = row[args.id_col].strip()
        if not row_id:
            raise InputError(f"{path}: line {number} has an empty id")
        if row_id in seen:
            raise InputError(f"{path}: id '{row_id}' appears more than once (line {number})")
        seen.add(row_id)
        if wide is None:
            codes = [c.strip() for c in row[codes_col].split(args.delimiter) if c.strip()]
        else:
            codes = []
            for column, code in wide:
                cell = row[column].strip()
                if cell not in ("0", "1"):
                    raise InputError(f"{path}: line {number}, column '{column}': expected 0 or 1, found '{cell}'")
                if cell == "1":
                    codes.append(code)
        out.append(
            {
                "id": row_id,
                "codes": list(dict.fromkeys(codes)),
                "text": row[text_col] if text_col else None,
                "segment": row[segment_col].strip() if segment_col else None,
                "extra": row[extra_col].strip() if extra_col else None,
                "line": number,
            }
        )
    listed = [code for _, code in wide] if wide else []
    return out, listed


def fill_blank_answers(rows):
    """A blank answer with no codes is NO_ANSWER. Returns how many rows were filled."""
    filled = 0
    for row in rows:
        if row["text"] is not None and not row["text"].strip() and not row["codes"]:
            row["codes"] = [NO_ANSWER]
            filled += 1
    return filled


def coding_problems(rows, known):
    """Problems that make counts wrong. `known` is the set of codebook codes, or None."""
    problems = []
    lowered = {c.lower(): c for c in known} if known else {}
    for row in rows:
        where = f"row {row['id']}"
        codes = row["codes"]
        if not codes:
            problems.append(f"{where}: no code (code it, or use {OTHER} / {UNCODABLE} / {NO_ANSWER})")
            continue
        for code in codes:
            if "," in code and (known is None or code not in known):
                problems.append(
                    f"{where}: code '{code}' contains a comma; separate codes with the code separator "
                    f"(';' by default, --delimiter to change it)"
                )
            elif known is not None and code not in known and code not in RESERVED:
                hint = lowered.get(code.lower())
                problems.append(f"{where}: unknown code '{code}'" + (f" (did you mean '{hint}'?)" if hint else ""))
            elif code.upper() in RESERVED and code not in RESERVED:
                problems.append(f"{where}: reserved code must be written '{code.upper()}', found '{code}'")
        for code in EXCLUSIVE:
            if code in codes and len(codes) > 1:
                problems.append(f"{where}: {code} cannot be combined with other codes ({', '.join(codes)})")
        if row["text"] is not None:
            blank = not row["text"].strip()
            if blank and codes != [NO_ANSWER]:
                problems.append(f"{where}: the answer is blank but it is coded {', '.join(codes)}")
            if not blank and NO_ANSWER in codes:
                problems.append(f"{where}: coded {NO_ANSWER} but the answer is not blank")
    return problems


def stop_on(problems, path):
    if problems:
        shown = "\n  ".join(problems[:20])
        more = f"\n  ... and {len(problems) - 20} more" if len(problems) > 20 else ""
        raise InputError(
            f"{path}: {len(problems)} coding problem(s); fix them first (the validate subcommand lists all):\n  "
            f"{shown}{more}"
        )


# ---------------------------------------------------------------- statistics


def cohen_kappa(labels_a, labels_b):
    """Cohen (1960): kappa = (p_o - p_e) / (1 - p_e), p_e from each coder's own marginals.

    Returns (p_o, p_e, kappa) as Fractions; kappa is None when p_e = 1 (both coders constant and equal).
    """
    n = len(labels_a)
    if n == 0 or n != len(labels_b):
        raise ValueError("two equally long, non-empty lists of labels are required")
    p_o = Fraction(sum(1 for a, b in zip(labels_a, labels_b) if a == b), n)
    count_a, count_b = Counter(labels_a), Counter(labels_b)
    p_e = Fraction(sum(count_a[k] * count_b[k] for k in count_a), n * n)
    if p_e == 1:
        return p_o, p_e, None
    return p_o, p_e, (p_o - p_e) / (1 - p_e)


def kappa_2x2(a, b, c, d):
    """Kappa from a present/absent table: a both, b first coder only, c second only, d neither."""
    n = a + b + c + d
    chance = (a + b) * (a + c) + (c + d) * (b + d)
    if n == 0 or chance == n * n:
        return None
    p_e = Fraction(chance, n * n)
    return (Fraction(a + d, n) - p_e) / (1 - p_e)


def alpha_2x2(a, b, c, d):
    """Krippendorff (2011), section A: alpha = 1 - (n - 1) * o01 / (n0 * n1) with n = 2N values."""
    ones, zeros = 2 * a + b + c, 2 * d + b + c
    if ones == 0 or zeros == 0:
        return None
    return 1 - Fraction((ones + zeros - 1) * (b + c), ones * zeros)


def krippendorff_alpha_nominal(units):
    """Krippendorff (2011), nominal metric, any number of coders, missing values simply left out.

    `units` is a list of lists: the values assigned to each unit. Units with fewer than two values
    cannot be paired and are ignored. Returns a Fraction, or None when the values do not vary.
    """
    coincidences = Counter()
    for values in units:
        m = len(values)
        if m < 2:
            continue
        for i, c in enumerate(values):
            for j, k in enumerate(values):
                if i != j:
                    coincidences[(c, k)] += Fraction(1, m - 1)
    totals = Counter()
    for (c, _), weight in coincidences.items():
        totals[c] += weight
    if len(totals) < 2:
        return None
    n = sum(totals.values())
    matches = sum(weight for (c, k), weight in coincidences.items() if c == k)
    chance = sum(n_c * (n_c - 1) for n_c in totals.values())
    return ((n - 1) * matches - chance) / (n * (n - 1) - chance)


def alpha_binary_sums(mismatch, ones, zeros):
    """Binary alpha from sums over units: mismatch = sum of k(m-k)/(m-1), ones = sum k, zeros = sum (m-k)."""
    if ones == 0 or zeros == 0:
        return None
    return 1 - (ones + zeros - 1) * mismatch / (ones * zeros)


def wilson(count, base, z=Z_95):
    """Wilson (1927) score interval for a proportion, no continuity correction. Returns (low, high)."""
    if base <= 0:
        raise ValueError("base must be positive")
    p = count / base
    centre = (p + z * z / (2 * base)) / (1 + z * z / base)
    half = z * math.sqrt(p * (1 - p) / base + z * z / (4 * base * base)) / (1 + z * z / base)
    return max(0.0, centre - half), min(1.0, centre + half)


def percentile(ordered, q):
    """Percentile q (0 to 100) of an ascending list, linear interpolation between ranks."""
    position = (len(ordered) - 1) * q / 100.0
    low = int(math.floor(position))
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def bootstrap_interval(values, replicates):
    """95% percentile interval, or None when fewer than half of the replicates were defined."""
    defined = sorted(float(v) for v in values if v is not None)
    if not defined or len(defined) * 2 < replicates:
        return None
    return [round(percentile(defined, 2.5), 4), round(percentile(defined, 97.5), 4)]


def landis_koch(kappa):
    """Landis & Koch (1977) labels. The authors call the divisions 'clearly arbitrary'."""
    if kappa is None:
        return None
    kappa = round(float(kappa), 4)  # exact fractions and floats must land in the same band
    if kappa < 0:
        return "poor"
    for limit, label in ((0.20, "slight"), (0.40, "fair"), (0.60, "moderate"), (0.80, "substantial")):
        if kappa <= limit:
            return label
    return "almost perfect"


def mchugh(kappa):
    """McHugh (2012), Table 3: a stricter reading of the same number."""
    if kappa is None:
        return None
    kappa = round(float(kappa), 4)
    if kappa <= 0.20:
        return "none"
    for limit, label in ((0.40, "minimal"), (0.60, "weak"), (0.80, "moderate")):
        if kappa < limit:
            return label
    return "strong" if kappa <= 0.90 else "almost perfect"


def krippendorff_band(alpha):
    """Krippendorff (2004): rely on alpha >= .800; .667 to .800 tentative conclusions only."""
    if alpha is None:
        return None
    alpha = round(float(alpha), 4)
    if alpha >= 0.8:
        return "meets 0.800"
    if alpha >= 0.667:
        return "tentative only (0.667 to 0.800)"
    return "below 0.667"


def crosses(interval, band):
    return bool(interval) and band(interval[0]) != band(interval[1])


def kappa_crosses_band(interval):
    """True when a kappa interval spans an edge of either scale printed beside it (Landis-Koch or McHugh)."""
    return crosses(interval, landis_koch) or crosses(interval, mchugh)


def number(value, digits=4):
    return None if value is None else round(float(value), digits)


def show(value, digits=3):
    return "undefined" if value is None else f"{float(value):.{digits}f}"


def show_ci(interval, digits=3):
    return "-" if not interval else f"{interval[0]:.{digits}f} to {interval[1]:.{digits}f}"


def percent(count, base, min_base):
    """Share in percent with one decimal, or None when the base is zero or under the minimum."""
    if base == 0 or base < min_base:
        return None
    return round(100.0 * count / base, 1)


def percent_ci(count, base, min_base):
    if base == 0 or base < min_base:
        return None
    low, high = wilson(count, base)
    return [round(100.0 * low, 1), round(100.0 * high, 1)]


def show_percent(value):
    return "--" if value is None else f"{value:.1f}%"


def show_percent_ci(interval):
    return "--" if not interval else f"{interval[0]:.1f} to {interval[1]:.1f}"


def table(headers, rows):
    widths = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    lines = ["  ".join(str(h).ljust(w) for h, w in zip(headers, widths)).rstrip()]
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append("  ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip())
    return "\n".join(lines)


def emit(args, result, text):
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else text)
    return 0


# ---------------------------------------------------------------- sample


def allocate(sizes, total):
    """Proportional allocation by largest remainder. `sizes` maps stratum -> eligible rows."""
    pool = sum(sizes.values())
    exact = {name: Fraction(total * size, pool) for name, size in sizes.items()}
    quota = {name: int(value) for name, value in exact.items()}
    left = total - sum(quota.values())
    for name in sorted(sizes, key=lambda s: (-(exact[s] - quota[s]), s))[:left]:
        quota[name] += 1
    return quota


def cmd_sample(args):
    fields, rows = read_csv(args.input)
    need_column(args.input, fields, args.id_col, "id")
    need_column(args.input, fields, args.text_col, "answer text")
    if args.stratify_col:
        need_column(args.input, fields, args.stratify_col, "stratum")
    if args.top_up_min is not None:
        if args.top_up_min < 1:
            raise InputError("--top-up-min must be at least 1")
        need_column(args.input, fields, args.codes_col, "codes (needed for --top-up-min)")
        if not args.top_up_out:
            raise InputError(
                "--top-up-min needs --top-up-out FILE: the rare-code rows are chosen from the first coder's codes, "
                "so they go to their own file and stay out of the random sample used for kappa and alpha"
            )
    if args.top_up_out and args.top_up_min is None:
        raise InputError("--top-up-out needs --top-up-min")
    if args.top_up_out and args.out and os.path.realpath(args.top_up_out) == os.path.realpath(args.out):
        raise InputError("--top-up-out must differ from --out")
    if args.top_up_out and not args.out:
        raise InputError("--top-up-out needs --out for the random sample")
    guard_output(args.out, [args.input] + list(args.exclude or []))
    guard_output(args.top_up_out, [args.input] + list(args.exclude or []), "--top-up-out")
    ids = [r[args.id_col].strip() for r in rows]
    if any(not i for i in ids):
        raise InputError(f"{args.input}: some rows have an empty id")
    duplicates = [i for i, c in Counter(ids).items() if c > 1]
    if duplicates:
        raise InputError(f"{args.input}: duplicate ids, for example '{duplicates[0]}'; a sample needs unique ids")
    excluded = set()
    for path in args.exclude or []:
        ex_fields, ex_rows = read_csv(path)
        need_column(path, ex_fields, args.id_col, "id")
        excluded.update(r[args.id_col].strip() for r in ex_rows)
    blank = [r for r in rows if not r[args.text_col].strip()]
    pool = [
        r for r in rows if r[args.id_col].strip() not in excluded and (args.include_blank or r[args.text_col].strip())
    ]
    adjusted = None
    if args.fraction is not None:
        if not 0 < args.fraction <= 1:
            raise InputError("--fraction must be above 0 and at most 1")
        size = max(1, round(len(pool) * args.fraction))
        if args.at_least is not None:
            if args.at_least < 1:
                raise InputError("--at-least must be at least 1")
            floor = min(args.at_least, len(pool))
            if size < floor:
                adjusted = f"{args.fraction:g} of {len(pool)} is {size}, raised to {floor} by --at-least {args.at_least}"
                size = floor
    elif args.n is not None:
        size = args.n
        if args.at_least is not None:
            raise InputError("--at-least goes with --fraction")
    else:
        raise InputError("give --n or --fraction")
    if args.all_if_fewer and args.n is None:
        raise InputError("--all-if-fewer goes with --n")
    if size < 1:
        raise InputError("--n must be at least 1")
    if size > len(pool) and args.all_if_fewer:
        adjusted = f"asked for {size}, only {len(pool)} eligible: took them all"
        size = len(pool)
    if not pool:
        raise InputError(f"{args.input}: no eligible answers ({len(rows)} rows, {len(blank)} blank, {len(excluded)} ids excluded)")
    if size > len(pool):
        raise InputError(
            f"asked for {size} answers but only {len(pool)} are eligible "
            f"({len(rows)} rows, {len(blank)} blank, {len(excluded)} ids excluded). Use --n {len(pool)} to take all."
        )
    rng = random.Random(args.seed)
    strata = None
    if args.stratify_col:
        groups = {}
        for index, row in enumerate(pool):
            groups.setdefault(row[args.stratify_col].strip() or "(blank)", []).append(index)
        quota = allocate({name: len(members) for name, members in groups.items()}, size)
        chosen = set()
        for name in sorted(groups):
            chosen.update(rng.sample(groups[name], quota[name]))
        strata = {name: {"eligible": len(groups[name]), "sampled": quota[name]} for name in sorted(groups)}
    else:
        chosen = set(rng.sample(range(len(pool)), size))
    random_rows = set(chosen)
    topped = {}
    if args.top_up_min is not None:
        carried = [
            [c.strip() for c in row[args.codes_col].split(args.delimiter) if c.strip() and c.strip() != NO_ANSWER]
            for row in pool
        ]
        for code in sorted({c for codes in carried for c in codes}):
            holders = [i for i, codes in enumerate(carried) if code in codes]
            have = sum(1 for i in holders if i in chosen)
            spare = [i for i in holders if i not in chosen]
            add = min(max(args.top_up_min - have, 0), len(spare))
            if add:
                chosen.update(rng.sample(spare, add))
                topped[code] = add
    picked = [row for index, row in enumerate(pool) if index in random_rows]  # file order unless --shuffle
    audit = [row for index, row in enumerate(pool) if index in chosen and index not in random_rows]
    if args.shuffle:
        random.Random(args.seed).shuffle(picked)
    columns = fields if args.all_columns else [args.id_col, args.text_col]
    summary = {
        "input": args.input,
        "rows": len(rows),
        "blank_answers": len(blank),
        "excluded_ids": len(excluded),
        "eligible": len(pool),
        "requested": size,
        "size_note": adjusted,
        "sampled": len(picked),
        "seed": args.seed,
        "order": "shuffled (seeded)" if args.shuffle else "file order",
        "strata": strata,
        "topped_up": topped,
        "columns": columns,
        "ids": [r[args.id_col].strip() for r in picked],
        "out": args.out,
        "top_up_ids": [r[args.id_col].strip() for r in audit],
        "top_up_out": args.top_up_out,
    }
    if args.out:
        write_csv(args.out, columns, picked)
    if args.top_up_out:
        write_csv(args.top_up_out, columns, audit)
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    elif args.out:
        print(
            f"Sampled {len(picked)} of {len(pool)} eligible answers (seed {args.seed}) from {len(rows)} rows; "
            f"{len(blank)} blank {'included' if args.include_blank else 'left out'}, {len(excluded)} ids excluded."
        )
        if adjusted:
            print(f"Sample size: {adjusted}.")
        if args.shuffle:
            print(f"Rows are in a seeded random order (seed {args.seed}): read and code them in this order.")
        if strata:
            print("By " + args.stratify_col + ": " + ", ".join(f"{k} {v['sampled']} of {v['eligible']}" for k, v in strata.items()))
        print(f"Wrote {args.out} with columns: {', '.join(columns)}")
        if args.top_up_out:
            print(
                f"Rare-code audit: {len(audit)} extra row(s) written to {args.top_up_out} ("
                + (", ".join(f"{k} +{v}" for k, v in topped.items()) or "none needed")
                + "). They were chosen from the first coder's codes, so they cannot find rows that coder missed and "
                "they change the code shares kappa depends on. Have them coded blind too, but compute kappa and "
                "alpha on the random sample only; read the audit rows as a disagreement check."
            )
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(picked)
    return 0


# ---------------------------------------------------------------- saturation


def cmd_saturation(args):
    """Guest, Namey and Chen (2020): new codes in a run of answers divided by the codes found in the base.

    A code is new in a run when it first appears in one of the run's rows. With the default --step 1 the run
    moves forward one answer at a time, as in Guest et al.; --step equal to --run gives non-overlapping runs.
    """
    if args.base < 1 or args.run < 1 or not args.threshold >= 0:
        raise InputError("--base and --run must be at least 1 and --threshold must not be negative")
    step = args.step
    if step < 1:
        raise InputError("--step must be at least 1")
    known = None
    if args.codebook:
        entries, problems = read_codebook(args.codebook, args.delimiter)
        if problems:
            raise InputError(f"{args.codebook}: " + "; ".join(problems))
        known = {e["code"] for e in entries}
    rows, _ = read_coded(args.input, args, text_col=args.text_col)
    fill_blank_answers(rows)
    uncoded = [row["id"] for row in rows if not row["codes"]]
    if uncoded:
        raise InputError(
            f"{args.input}: {len(uncoded)} row(s) have no code (for example id '{uncoded[0]}'). An uncoded row is not "
            "evidence that no new code turned up: finish coding them, or remove the rows you have not read yet."
        )
    stop_on(coding_problems(rows, known), args.input)
    blank_rows = sum(1 for row in rows if row["codes"] == [NO_ANSWER])
    rows = [row for row in rows if row["codes"] != [NO_ANSWER]]  # a blank answer cannot show a new code
    if len(rows) < args.base + args.run:
        raise InputError(
            f"{args.input}: {len(rows)} rows; a base of {args.base} and one run of {args.run} need {args.base + args.run}"
        )
    first_seen = {}  # code -> index of the row where it first appears
    for index, row in enumerate(rows):
        for code in row["codes"]:
            if code not in RESERVED and code not in first_seen:
                first_seen[code] = index
    base_new = [c for c, i in first_seen.items() if i < args.base]
    base_codes = len(base_new)
    if base_codes == 0:
        raise InputError(f"{args.input}: the base rows carry no codes")
    batches = [{"batch": "base", "rows": f"1-{args.base}", "new_codes": base_new, "codes_so_far": base_codes, "new_pct_of_base": None}]
    edges = [(s, s + args.run) for s in range(args.base, len(rows) - args.run + 1, step)]
    reached = None
    for number_, (start, end) in enumerate(edges, start=1):
        new = [c for c, i in first_seen.items() if start <= i < end]
        share = round(100.0 * len(new) / base_codes, 1)
        if reached is None and 100.0 * len(new) <= args.threshold * base_codes:
            reached = number_
        batches.append(
            {
                "batch": f"run {number_}",
                "rows": f"{start + 1}-{end}",
                "new_codes": new,
                "codes_so_far": sum(1 for i in first_seen.values() if i < end),
                "new_pct_of_base": share,
            }
        )
    leftover = len(rows) - edges[-1][1]
    point = edges[reached - 1][0] if reached else None
    result = {
        "input": args.input,
        "base": args.base,
        "run": args.run,
        "step": step,
        "threshold_pct": args.threshold,
        "base_codes": base_codes,
        "batches": batches,
        "rows_not_evaluated": leftover,
        "blank_answers_skipped": blank_rows,
        "reached_at_run": reached,
        "reached_after_rows": edges[reached - 1][1] if reached else None,
        "saturation_point": point,
    }
    verdict = (
        f"Stopping rule met in run {reached} (rows {point + 1}-{point + args.run}): new codes are at most "
        f"{args.threshold:g}% of the {base_codes} base codes. Saturation at answer {point} (+{args.run}), "
        "in Guest et al.'s notation."
        if reached
        else f"Stopping rule not met: every run added more than {args.threshold:g}% of the {base_codes} base codes. "
        "Sample more answers and continue."
    )
    result["verdict"] = verdict
    how = "moving one answer at a time, as in Guest et al. 2020" if step == 1 else f"moving {step} answers at a time"
    text = f"Saturation log: {args.input} (rows in the order read; runs of {args.run}, {how})\n\n" + table(
        ["Batch", "Rows", "New codes", "Codes so far", "New / base codes"],
        [
            [b["batch"], b["rows"], len(b["new_codes"]), b["codes_so_far"], "" if b["new_pct_of_base"] is None else f"{b['new_pct_of_base']:.1f}%"]
            for b in batches
        ],
    )
    text += f"\n\n{verdict}"
    if blank_rows:
        text += f"\n{blank_rows} blank answer(s) ({NO_ANSWER}) were skipped: rows are numbered among the answers only."
    if leftover:
        text += f"\n{leftover} trailing row(s) do not fill a run and were not evaluated."
    return emit(args, result, text)


# ---------------------------------------------------------------- validate


def source_problems(args, rows):
    """Every source respondent must be in the coded file once, with the same answer text."""
    fields, source = read_csv(args.source)
    need_column(args.source, fields, args.id_col, "id")
    text_col = args.source_text_col or args.text_col
    if text_col:
        need_column(args.source, fields, text_col, "answer text")
    problems, coded = [], {row["id"]: row for row in rows}
    source_ids = [r[args.id_col].strip() for r in source]
    empty = sum(1 for i in source_ids if not i)
    if empty:
        problems.append(f"{empty} source row(s) have an empty id: every respondent needs an id to be matched")
    duplicated = sorted(i for i, c in Counter(source_ids).items() if i and c > 1)
    if duplicated:
        problems.append(
            f"{len(duplicated)} id(s) appear more than once in the source file (for example '{duplicated[0]}'): "
            "those respondents cannot be matched one to one"
        )
    missing = [i for i in source_ids if i not in coded]
    extra = [row["id"] for row in rows if row["id"] not in set(source_ids)]
    if missing:
        problems.append(
            f"{len(missing)} of {len(source_ids)} source row(s) are missing from the coded file "
            f"(for example id '{missing[0]}'): every respondent must be coded, blanks as {NO_ANSWER}"
        )
    if extra:
        problems.append(f"{len(extra)} coded row(s) are not in the source file (for example id '{extra[0]}')")
    if text_col and args.text_col:
        changed = [r[args.id_col].strip() for r in source if r[args.id_col].strip() in coded
                   and squash(r[text_col]) != squash(coded[r[args.id_col].strip()]["text"])]
        if changed:
            problems.append(
                f"{len(changed)} row(s) have answer text that differs from the source (for example id '{changed[0]}'): "
                "the codes may belong to another answer; never retype answers, copy codes in by id (merge)"
            )
    return problems, len(source)


def cmd_validate(args):
    if args.source_text_col and not args.text_col:
        raise InputError("--source-text-col needs --text-col: the answer column of the coded file to compare with")
    entries, errors = read_codebook(args.codebook, args.delimiter)
    known = {e["code"] for e in entries}
    rows, _ = read_coded(args.input, args, text_col=args.text_col)
    filled = fill_blank_answers(rows)
    errors += coding_problems(rows, known)
    warnings = []
    used = Counter(code for row in rows for code in row["codes"])
    for entry in entries:
        if entry["code"] not in RESERVED and not used[entry["code"]]:
            warnings.append(f"code '{entry['code']}' is in the codebook but no row uses it")
    by_id = {row["id"]: row for row in rows}
    source_rows = None
    if args.source:
        found, source_rows = source_problems(args, rows)
        errors += found
    if args.text_col:
        texts = [squash(row["text"]) for row in rows]
        for row in rows:
            typed = squash(row["text"]).lower()
            if typed in NON_ANSWER_TEXT and not set(row["codes"]) & {UNCODABLE, NO_ANSWER}:
                warnings.append(f"row {row['id']}: the answer is '{typed}' but it is coded {', '.join(row['codes'])}")
        for entry in entries:
            quote = untrim(entry["example_quote"])
            if entry["code"] not in RESERVED and quote and not any(quote in text for text in texts):
                warnings.append(f"code '{entry['code']}': example_quote is not found word for word in any answer")
    checked_quotes = 0
    if args.quotes:
        if not args.text_col:
            raise InputError("--quotes needs --text-col, to compare each quote with the answer")
        q_fields, q_rows = read_csv(args.quotes)
        for column in ("id", "code", "quote"):
            need_column(args.quotes, q_fields, column, "quote file")
        for number_, quote_row in enumerate(q_rows, start=2):
            where = f"quotes line {number_}"
            row = by_id.get(quote_row["id"].strip())
            quote = untrim(quote_row["quote"])
            checked_quotes += 1
            if row is None:
                errors.append(f"{where}: row id '{quote_row['id'].strip()}' is not in the coded file")
                continue
            if not quote or quote not in squash(row["text"]):
                errors.append(f"{where}: quote is not word for word in the answer of row {row['id']}")
            if quote_row["code"].strip() not in row["codes"]:
                errors.append(f"{where}: row {row['id']} is not coded '{quote_row['code'].strip()}'")
    result = {
        "input": args.input,
        "codebook": args.codebook,
        "rows": len(rows),
        "codes_in_codebook": len([e for e in entries if e["code"] not in RESERVED]),
        "nets": nets_from(entries),
        "source": args.source,
        "source_rows": source_rows,
        "source_text_checked": bool(args.source and args.text_col),
        "blank_rows_set_to_NO_ANSWER": filled,
        "quotes_checked": checked_quotes,
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Validate: {len(rows)} rows against {result['codes_in_codebook']} codes in {args.codebook}")
        if filled:
            print(f"{filled} blank answer(s) with no code are treated as {NO_ANSWER}.")
        if args.source:
            print(
                f"Checked against the source file {args.source} ({source_rows} rows): "
                + ("ids and answer text." if args.text_col else "ids only; pass --text-col to also check the answer text.")
            )
        else:
            print("Not checked against the source responses: pass --source to confirm every respondent is in the file.")
        if checked_quotes:
            print(f"{checked_quotes} quote(s) checked against the answers.")
        for label, items in (("ERROR", errors), ("warning", warnings)):
            for item in items:
                print(f"{label}: {item}")
        print(f"Result: {len(errors)} error(s), {len(warnings)} warning(s). " + ("OK" if not errors else "Not OK"))
    return 0 if not errors else 1


# ---------------------------------------------------------------- counts


def count_block(rows, codes, min_base, nets, mentions):
    total = len(rows)
    no_answer = sum(1 for r in rows if NO_ANSWER in r["codes"])
    uncodable = sum(1 for r in rows if UNCODABLE in r["codes"])
    answered = total - no_answer
    codable = answered - uncodable
    used = Counter(code for r in rows for code in r["codes"])
    assignments = sum(used[code] for code in codes if code != UNCODABLE)
    lines = []
    for code in codes:
        line = {
            "code": code,
            "n": used[code],
            "pct_of_all": percent(used[code], total, min_base),
            "pct_of_answered": percent(used[code], answered, min_base),
            "ci95_of_answered": percent_ci(used[code], answered, min_base),
        }
        if mentions:
            line["pct_of_mentions"] = None if code == UNCODABLE or answered < min_base else percent(used[code], assignments, min_base)
        lines.append(line)
    net_lines = []
    for parent, children in nets.items():
        members = set(children)
        n = sum(1 for r in rows if members & set(r["codes"]))
        net_lines.append(
            {
                "net": parent,
                "codes": children,
                "n": n,
                "sum_of_code_counts": sum(used[c] for c in children),
                "pct_of_all": percent(n, total, min_base),
                "pct_of_answered": percent(n, answered, min_base),
                "ci95_of_answered": percent_ci(n, answered, min_base),
            }
        )
    return {
        "all_respondents": total,
        "answered": answered,
        "no_answer": no_answer,
        "uncodable": uncodable,
        "codable": codable,
        "pct_answered_of_all": percent(answered, total, min_base),
        "pct_no_answer_of_all": percent(no_answer, total, min_base),
        "small_base_all": total < min_base,
        "small_base_answered": answered < min_base,
        "code_assignments": assignments,
        "mean_codes_per_codable_answer": round(assignments / codable, 2) if codable else None,
        "codes": lines,
        "nets": net_lines,
    }


def health_check(rows, substantive, answered, args):
    """Signs that the codebook needs work. Counts only, so a small base cannot produce a percentage."""
    used = Counter(code for r in rows for code in r["codes"])
    pairs = Counter()
    for row in rows:
        present = [c for c in substantive if c in row["codes"]]
        for first, second in combinations(present, 2):
            pairs[(first, second)] += 1
    top = []
    for (first, second), n in sorted(pairs.items(), key=lambda item: (-item[1], item[0]))[: args.top_pairs]:
        smaller = first if used[first] <= used[second] else second
        top.append({"codes": [first, second], "n": n, "smaller_code": smaller, "smaller_code_n": used[smaller]})
    return {
        "thresholds": {"rare_below": args.rare_below, "broad_above_pct": args.broad_above, "other_above_pct": args.other_above},
        "unused": [c for c in substantive if used[c] == 0],
        "rare": [{"code": c, "n": used[c]} for c in substantive if 0 < used[c] < args.rare_below],
        "broad": [{"code": c, "n": used[c]} for c in substantive if answered and 100.0 * used[c] > args.broad_above * answered],
        "other_n": used[OTHER],
        "other_above_threshold": bool(answered) and 100.0 * used[OTHER] > args.other_above * answered,
        "top_pairs": top,
    }


def health_lines(health, answered):
    lines = []
    if health["unused"]:
        lines.append("Never used: " + ", ".join(health["unused"]) + ". Drop them or check their definitions.")
    if health["rare"]:
        lines.append(
            f"Used fewer than {health['thresholds']['rare_below']} times: "
            + ", ".join(f"{r['code']} ({r['n']})" for r in health["rare"])
            + ". Too few to report alone; consider merging into a neighbour or a net."
        )
    if health["broad"]:
        lines.append(
            f"On more than {health['thresholds']['broad_above_pct']:g}% of answers: "
            + ", ".join(f"{r['code']} ({r['n']} of {answered})" for r in health["broad"])
            + ". Probably several ideas in one code; consider splitting."
        )
    if health["other_above_threshold"]:
        lines.append(
            f"OTHER is {health['other_n']} of {answered} answers, above {health['thresholds']['other_above_pct']:g}%: "
            "the codebook does not cover the answers. Re-read OTHER and add codes."
        )
    for pair in health["top_pairs"]:
        lines.append(
            f"Together: {pair['codes'][0]} + {pair['codes'][1]} on {pair['n']} answer(s) "
            f"({pair['n']} of the {pair['smaller_code_n']} {pair['smaller_code']} answers). "
            "If most of one code sits inside the other, the definitions overlap."
        )
    return lines or ["Nothing flagged."]


def sentiment_block(rows, column, min_base):
    problems = []
    values = []
    for row in rows:
        value = row["extra"].lower()
        empty_ok = bool(set(row["codes"]) & {NO_ANSWER, UNCODABLE})
        if not value and not empty_ok:
            problems.append(f"row {row['id']}: '{column}' is empty on a coded answer")
        elif value and value not in SENTIMENTS:
            problems.append(f"row {row['id']}: '{column}' is '{row['extra']}', expected one of {', '.join(SENTIMENTS)}")
        elif value and empty_ok:
            problems.append(f"row {row['id']}: '{column}' is set on {'a blank' if NO_ANSWER in row['codes'] else 'an uncodable'} answer")
        elif value:
            values.append(value)
    if problems:
        raise InputError("sentiment column: " + "; ".join(problems[:10]))
    tally, base = Counter(values), len(values)
    return {
        "column": column,
        "base": base,
        "small_base": base < min_base,
        "values": [
            {"value": v, "n": tally[v], "pct": percent(tally[v], base, min_base), "ci95": percent_ci(tally[v], base, min_base)}
            for v in SENTIMENTS
        ],
    }


def segment_cell(line):
    if line["pct_of_answered"] is None:
        return f"{line['n']} (--)"
    return f"{line['n']} ({show_percent(line['pct_of_answered'])}, {show_percent_ci(line['ci95_of_answered'])})"


def cmd_counts(args):
    if args.min_base < 1:
        raise InputError("--min-base must be at least 1")
    if args.rare_below < 0 or args.top_pairs < 0 or not 0 <= args.broad_above <= 100 or not 0 <= args.other_above <= 100:
        raise InputError("--rare-below and --top-pairs must not be negative; --broad-above and --other-above are percentages")
    labels, known, order, nets = dict(RESERVED_LABELS), None, [], {}
    if args.codebook:
        entries, problems = read_codebook(args.codebook, args.delimiter)
        if problems:
            raise InputError(f"{args.codebook}: " + "; ".join(problems))
        known = {e["code"] for e in entries}
        order = [e["code"] for e in entries if e["code"] not in RESERVED]
        labels.update({e["code"]: e["label"] for e in entries})
        nets = nets_from(entries)
    rows, listed = read_coded(
        args.input, args, text_col=args.text_col, segment_col=args.segment_col, extra_col=args.sentiment_col
    )
    filled = fill_blank_answers(rows)
    stop_on(coding_problems(rows, known), args.input)
    used = Counter(code for r in rows for code in r["codes"])
    substantive = list(dict.fromkeys(order + [c for c in listed + sorted(used) if c not in RESERVED]))
    position = {code: index for index, code in enumerate(substantive)}
    substantive.sort(key=lambda code: (-used[code], position[code]))
    codes = substantive + [OTHER, UNCODABLE]
    overall = count_block(rows, codes, args.min_base, nets, args.mentions)
    notes = [
        "A response can carry several codes, so the code shares can add up to more than 100%. "
        "They are shares of respondents, not shares of mentions.",
        f"'% of answered' uses the {overall['answered']} respondents who typed something; "
        f"'% of all' uses all {overall['all_respondents']} rows, including {overall['no_answer']} blank.",
        "95% intervals are Wilson score intervals on '% of answered'. They describe sampling error only and "
        "assume the respondents are a random sample. They are not a test of the difference between segments.",
    ]
    if nets:
        notes.append("A net counts each respondent once, however many of its codes the answer carries; it is not the sum of its codes.")
    if args.mentions:
        notes.append(f"'% of mentions' divides by the {overall['code_assignments']} code assignments, not by respondents; it adds up to 100%.")
    if overall["small_base_answered"]:
        notes.append(
            f"Base under {args.min_base}: percentages are withheld (shown as --). Report counts, "
            f"for example '{overall['codes'][0]['n']} of {overall['answered']}'."
        )
    if filled:
        notes.append(f"{filled} blank answer(s) with no code were counted as {NO_ANSWER}.")
    result = {"input": args.input, "min_base": args.min_base, "labels": {c: labels.get(c, "") for c in codes}}
    result.update(overall)
    result["health"] = health_check(rows, substantive, overall["answered"], args)
    if args.sentiment_col:
        result["sentiment"] = sentiment_block(rows, args.sentiment_col, args.min_base)
    if args.segment_col:
        segments = {}
        for row in rows:
            segments.setdefault(row["segment"] or "(blank)", []).append(row)
        result["segment_col"] = args.segment_col
        result["segments"] = {
            name: count_block(group, codes, args.min_base, nets, args.mentions) for name, group in sorted(segments.items())
        }
        small = [name for name, block in result["segments"].items() if block["small_base_answered"]]
        if small:
            notes.append(
                f"Segments with fewer than {args.min_base} answered rows (percentages withheld, do not compare): "
                + ", ".join(small)
            )
    result["notes"] = notes
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    out = [f"Code frequencies: {args.input}\n"]
    out.append(
        table(
            ["Base", "n", "% of all"],
            [
                ["All respondents (rows)", overall["all_respondents"], ""],
                ["Answered (typed something)", overall["answered"], show_percent(overall["pct_answered_of_all"])],
                ["No answer (blank)", overall["no_answer"], show_percent(overall["pct_no_answer_of_all"])],
                ["Uncodable, within answered", overall["uncodable"], ""],
                ["Codable answers", overall["codable"], ""],
            ],
        )
    )
    head = ["Code", "Label", "n", f"% of all ({overall['all_respondents']})", f"% of answered ({overall['answered']})", "95% interval"]
    body = [
        [l["code"], labels.get(l["code"], ""), l["n"], show_percent(l["pct_of_all"]), show_percent(l["pct_of_answered"]), show_percent_ci(l["ci95_of_answered"])]
        for l in overall["codes"]
    ]
    if args.mentions:
        head.append(f"% of mentions ({overall['code_assignments']})")
        for row, line in zip(body, overall["codes"]):
            row.append("" if line["code"] == UNCODABLE else show_percent(line["pct_of_mentions"]))
    out.append("\n" + table(head, body))
    out.append(
        f"\n{overall['code_assignments']} code assignments on {overall['codable']} codable answers"
        + (f" (mean {overall['mean_codes_per_codable_answer']} per answer)." if overall["codable"] else ".")
    )
    if nets:
        out.append(
            "\nNets (each respondent counted once)\n\n"
            + table(
                ["Net", "Codes", "n", "Sum of code counts", f"% of all ({overall['all_respondents']})", f"% of answered ({overall['answered']})", "95% interval"],
                [
                    [n["net"], " + ".join(n["codes"]), n["n"], n["sum_of_code_counts"], show_percent(n["pct_of_all"]), show_percent(n["pct_of_answered"]), show_percent_ci(n["ci95_of_answered"])]
                    for n in overall["nets"]
                ],
            )
        )
    if args.sentiment_col:
        block = result["sentiment"]
        out.append(
            f"\nSentiment ({args.sentiment_col}), one value per answer, base {block['base']}\n\n"
            + table(
                ["Value", "n", "%", "95% interval"],
                [[v["value"], v["n"], show_percent(v["pct"]), show_percent_ci(v["ci95"])] for v in block["values"]],
            )
        )
    if args.segment_col:
        names = list(result["segments"])
        seg_rows = [
            ["Answered (base)"]
            + [str(result["segments"][n]["answered"]) + (" SMALL BASE" if result["segments"][n]["small_base_answered"] else "") for n in names],
            ["No answer (blank)"] + [str(result["segments"][n]["no_answer"]) for n in names],
        ]
        for index, code in enumerate(codes):
            lines = [result["segments"][name]["codes"][index] for name in names]
            seg_rows.append([code] + [segment_cell(l) for l in lines])
        for index, parent in enumerate(nets):
            lines = [result["segments"][name]["nets"][index] for name in names]
            seg_rows.append([f"NET {parent}"] + [segment_cell(l) for l in lines])
        out.append(
            f"\nBy {args.segment_col}: n (% of answered in the segment, 95% interval)\n\n" + table(["Code"] + names, seg_rows)
        )
    out.append("\nCodebook health\n" + "\n".join(f"- {line}" for line in health_lines(result["health"], overall["answered"])))
    out.append("\nNotes\n" + "\n".join(f"- {note}" for note in notes))
    print("\n".join(out))
    return 0


# ---------------------------------------------------------------- agreement


def code_line(code, a, b, c, d, gold):
    """Everything reported for one code and one pair of coders. With `gold`, the first coder is the reference."""
    n = a + b + c + d
    kappa, alpha = kappa_2x2(a, b, c, d), alpha_2x2(a, b, c, d)
    unused = a + b + c == 0
    agreement = 100.0 * (a + d) / n
    reason = None
    if kappa is None:
        reason = (
            "neither coder used this code: expected agreement is 1, so kappa is undefined"
            if unused
            else "both coders gave this code to every row: expected agreement is 1, so kappa is undefined"
        )
    line = {
        "code": code,
        "both": a,
        "a_only": b,
        "b_only": c,
        "neither": d,
        "used_by_a": a + b,
        "used_by_b": a + c,
        "percent_agreement": round(agreement, 1),
        "expected_agreement": number(Fraction((a + b) * (a + c) + (c + d) * (b + d), n * n)),
        "kappa": number(kappa),
        "kappa_undefined_reason": reason,
        "landis_koch": landis_koch(kappa),
        "mchugh": mchugh(kappa),
        "positive_agreement": number(Fraction(2 * a, 2 * a + b + c)) if not unused else None,
        "negative_agreement": number(Fraction(2 * d, 2 * d + b + c)) if d + b + c else None,
        "pabak": number(Fraction(2 * (a + d), n) - 1),
        "high_agreement_low_kappa": kappa is not None and agreement >= PARADOX_AGREEMENT and float(kappa) < PARADOX_KAPPA,
        "alpha": number(alpha),
        "krippendorff_band": krippendorff_band(alpha),
    }
    if gold:
        line["precision"] = number(Fraction(a, a + c)) if a + c else None
        line["recall"] = number(Fraction(a, a + b)) if a + b else None
        line["f1"] = number(Fraction(2 * a, 2 * a + b + c)) if not unused else None
    return line


def pair_report(units, set_x, set_y, codes, gold):
    """Two coders on the units both coded: per-code lines and overall figures."""
    lines, cells = [], {}
    for code in codes:
        cell = [(0 if code in set_x[u] else 2) + (0 if code in set_y[u] else 1) for u in units]  # 0 both, 1 x only, 2 y only, 3 neither
        cells[code] = cell
        tally = Counter(cell)
        lines.append(code_line(code, tally[0], tally[1], tally[2], tally[3], gold))
    n = len(units)
    defined = [l for l in lines if l["kappa"] is not None]
    lowest = min(defined, key=lambda l: l["kappa"]) if defined else None
    one_code_each = all(len(set_x[u]) == 1 and len(set_y[u]) == 1 for u in units)
    # With one code per response the codes mirror each other, so pooling would count each
    # disagreement twice; the categorical kappa is the overall figure in that case.
    pooled_codes = [] if one_code_each else [l["code"] for l in lines if l["both"] + l["a_only"] + l["b_only"]]
    pooled = [sum(l[key] for l in lines if l["code"] in pooled_codes) for key in ("both", "a_only", "b_only", "neither")]
    pooled_kappa = kappa_2x2(*pooled) if pooled_codes else None
    exact = [set_x[u] == set_y[u] for u in units]
    overall = {
        "units": n,
        "exact_code_set_match": sum(exact),
        "exact_code_set_match_pct": round(100.0 * sum(exact) / n, 1),
        "codes_compared": len(lines),
        "codes_with_undefined_kappa": [l["code"] for l in lines if l["kappa"] is None],
        "mean_kappa": round(sum(l["kappa"] for l in defined) / len(defined), 4) if defined else None,
        "min_kappa": lowest["kappa"] if lowest else None,
        "min_kappa_code": lowest["code"] if lowest else None,
        "pooled_decisions": sum(pooled) if pooled_codes else 0,
        "pooled_percent_agreement": round(100.0 * (pooled[0] + pooled[3]) / sum(pooled), 1) if pooled_codes else None,
        "pooled_kappa": number(pooled_kappa),
        "pooled_landis_koch": landis_koch(pooled_kappa),
    }
    single = None
    if one_code_each:
        cat_x = [next(iter(set_x[u])) for u in units]
        cat_y = [next(iter(set_y[u])) for u in units]
        p_o, p_e, kappa = cohen_kappa(cat_x, cat_y)
        alpha = krippendorff_alpha_nominal([[x, y] for x, y in zip(cat_x, cat_y)])
        single = {
            "percent_agreement": round(100.0 * float(p_o), 1),
            "expected_agreement": number(p_e),
            "kappa": number(kappa),
            "landis_koch": landis_koch(kappa),
            "mchugh": mchugh(kappa),
            "alpha": number(alpha),
            "krippendorff_band": krippendorff_band(alpha),
        }
    return {"lines": lines, "overall": overall, "single": single, "cells": cells, "pooled_codes": pooled_codes, "exact": exact}


def bootstrap_pair(units, set_x, set_y, report, replicates, rng):
    """Percentile bootstrap over responses for a pair of coders. Adds intervals to `report` in place."""
    n = len(units)
    codes = [l["code"] for l in report["lines"]]
    cells = [report["cells"][code] for code in codes]
    pooled_index = [i for i, code in enumerate(codes) if code in report["pooled_codes"]]
    kappas, alphas = [[] for _ in codes], [[] for _ in codes]
    means, pooled, exact, cat_kappa, cat_alpha = [], [], [], [], []
    single = report["single"] is not None
    if single:
        cat_x = [next(iter(set_x[u])) for u in units]
        cat_y = [next(iter(set_y[u])) for u in units]
    for _ in range(replicates):
        draw = rng.choices(range(n), k=n)
        tables, defined = [], []
        for index, cell in enumerate(cells):
            tally = [0, 0, 0, 0]
            for u in draw:
                tally[cell[u]] += 1
            tables.append(tally)
            kappa = kappa_2x2(*tally)
            kappas[index].append(kappa)
            alphas[index].append(alpha_2x2(*tally))
            if kappa is not None:
                defined.append(kappa)
        means.append(sum(defined) / len(defined) if defined else None)
        if pooled_index:
            pooled.append(kappa_2x2(*[sum(tables[i][k] for i in pooled_index) for k in range(4)]))
        exact.append(100.0 * sum(1 for u in draw if report["exact"][u]) / n)
        if single:
            xs, ys = [cat_x[u] for u in draw], [cat_y[u] for u in draw]
            cat_kappa.append(cohen_kappa(xs, ys)[2])
            cat_alpha.append(krippendorff_alpha_nominal([[x, y] for x, y in zip(xs, ys)]))
    for index, line in enumerate(report["lines"]):
        line["kappa_ci95"] = bootstrap_interval(kappas[index], replicates) if line["kappa"] is not None else None
        line["alpha_ci95"] = bootstrap_interval(alphas[index], replicates) if line["alpha"] is not None else None
        line["ci_crosses_band"] = (
            kappa_crosses_band(line["kappa_ci95"]) or crosses(line["alpha_ci95"], krippendorff_band)
        )
    overall = report["overall"]
    overall["mean_kappa_ci95"] = bootstrap_interval(means, replicates) if overall["mean_kappa"] is not None else None
    overall["pooled_kappa_ci95"] = bootstrap_interval(pooled, replicates) if overall["pooled_kappa"] is not None else None
    overall["pooled_kappa_ci_crosses_band"] = crosses(overall["pooled_kappa_ci95"], landis_koch)  # only Landis-Koch is printed for it
    overall["exact_code_set_match_pct_ci95"] = [round(v, 1) for v in bootstrap_interval(exact, replicates)]
    if single:
        report["single"]["kappa_ci95"] = bootstrap_interval(cat_kappa, replicates) if report["single"]["kappa"] is not None else None
        report["single"]["alpha_ci95"] = bootstrap_interval(cat_alpha, replicates) if report["single"]["alpha"] is not None else None
        report["single"]["ci_crosses_band"] = kappa_crosses_band(report["single"]["kappa_ci95"]) or crosses(
            report["single"]["alpha_ci95"], krippendorff_band
        )


def parse_coder_info(values, count, paths):
    coders = []
    if values and len(values) != count:
        raise InputError(f"--coder-info was given {len(values)} time(s) but there are {count} coders (gold first, then the files in order)")
    for index in range(count):
        coder = {"key": chr(65 + index), "id": os.path.splitext(os.path.basename(paths[index]))[0], "kind": None, "model": None, "file": paths[index]}
        if values:
            parts = [p.strip() for p in values[index].split(",")]
            if len(parts) not in (2, 3) or not parts[0] or parts[1].lower() not in ("human", "llm"):
                raise InputError(f"--coder-info '{values[index]}': expected ID,human or ID,llm,MODEL")
            if parts[1].lower() == "llm" and (len(parts) < 3 or not parts[2]):
                raise InputError(f"--coder-info '{values[index]}': an llm coder needs the model name: ID,llm,MODEL")
            if parts[1].lower() == "human" and len(parts) == 3:
                raise InputError(f"--coder-info '{values[index]}': a human coder takes no model: ID,human")
            coder.update({"id": parts[0], "kind": parts[1].lower(), "model": parts[2] if len(parts) == 3 else None})
        coders.append(coder)
    return coders


def describe(coder):
    kind = {"human": "human", "llm": f"LLM, {coder['model']}", None: "type not stated"}[coder["kind"]]
    return f"{coder['key']} = {coder['id']} ({kind})"


def cmd_agreement(args):
    paths = ([args.gold] if args.gold else []) + list(args.coders)
    if len(paths) < 2:
        raise InputError("agreement needs two or more coded files (or --gold and at least one file)")
    if len(paths) > 26:
        raise InputError("at most 26 coders")
    if args.bootstrap < 0 or 0 < args.bootstrap < 100:
        raise InputError("--bootstrap must be 0 (off) or at least 100 replicates")
    coders = parse_coder_info(args.coder_info, len(paths), paths)
    known, order = None, []
    if args.codebook:
        entries, problems = read_codebook(args.codebook, args.delimiter)
        if problems:
            raise InputError(f"{args.codebook}: " + "; ".join(problems))
        known = {e["code"] for e in entries}
        order = [e["code"] for e in entries if e["code"] not in RESERVED]
    guard_output(args.disagreements, paths + [args.codebook, args.sample], "--disagreements")
    loaded, listed, without_text = [], [], []
    for path in paths:
        rows, wide_codes = read_coded(path, args, text_col=args.text_col, text_optional=True)
        loaded.append({r["id"]: r for r in rows})
        listed += wide_codes
        if args.text_col and rows[0]["text"] is None:
            without_text.append(path)
    sample_text = {}
    if args.sample:
        s_fields, s_rows = read_csv(args.sample)
        need_column(args.sample, s_fields, args.id_col, "id")
        sample_ids = list(dict.fromkeys(r[args.id_col].strip() for r in s_rows if r[args.id_col].strip()))
        if not sample_ids:
            raise InputError(f"{args.sample}: no ids")
        if args.text_col and args.text_col in s_fields:
            sample_text = {r[args.id_col].strip(): r[args.text_col] for r in s_rows}
        elif args.text_col:
            without_text.append(args.sample)
        for path, by_id in zip(paths, loaded):
            missing = [i for i in sample_ids if i not in by_id]
            if missing:
                raise InputError(
                    f"{path}: {len(missing)} of the {len(sample_ids)} sampled id(s) are not coded "
                    f"(for example '{missing[0]}'); every coder codes every row of {args.sample}"
                )
        all_ids = sample_ids
    else:
        all_ids = list(dict.fromkeys(i for by_id in loaded for i in by_id))
    if args.text_col and len(without_text) == len(paths) + (1 if args.sample else 0):
        raise InputError(
            f"no file has an answer column named '{args.text_col}': check the name, or leave out --text-col"
        )
    holders = {i: [j for j, by_id in enumerate(loaded) if i in by_id] for i in all_ids}
    mismatched = []
    for i in all_ids:
        texts = {squash(loaded[j][i]["text"]) for j in holders[i] if loaded[j][i]["text"] is not None}
        if i in sample_text:
            texts.add(squash(sample_text[i]))
        if len(texts) > 1:
            mismatched.append(i)
    if mismatched:
        raise InputError(
            f"{len(mismatched)} id(s) carry different answer text in different files (for example '{mismatched[0]}'): "
            "the coders did not code the same answers. Rebuild the second coder's file from the sample by id."
        )
    partial = [i for i in all_ids if len(holders[i]) < len(paths)]
    if partial and not args.allow_unmatched:
        raise InputError(
            f"the files do not hold the same rows: {len(partial)} id(s) are missing from at least one file "
            f"(for example '{partial[0]}'). All coders must code the same sample; pass --allow-unmatched to "
            "compare each row across the coders who coded it."
        )
    comparable = [i for i in all_ids if len(holders[i]) >= 2]
    if not comparable:
        raise InputError("the files share no row ids")
    for index, by_id in enumerate(loaded):
        mine = [by_id[i] for i in comparable if i in by_id]
        fill_blank_answers(mine)
        stop_on(coding_problems(mine, known), paths[index])
    blank = [i for i in comparable if all(loaded[j][i]["codes"] == [NO_ANSWER] for j in holders[i])]
    units = [i for i in comparable if i not in set(blank)]
    if not units:
        raise InputError("no rows to compare after matching ids and dropping rows every coder marked NO_ANSWER")
    sets = [{i: set(by_id[i]["codes"]) for i in units if i in by_id} for by_id in loaded]
    used = set().union(*[s for coder_sets in sets for s in coder_sets.values()])
    codes = list(dict.fromkeys(order + [c for c in listed if c not in RESERVED]))
    codes += sorted(c for c in used if c not in codes and c not in RESERVED)
    codes += [c for c in RESERVED if c in used or (known is not None and c in known and c != NO_ANSWER)]
    rng = random.Random(args.seed)
    two = len(paths) == 2
    notes = [
        "Kappa and alpha are computed per code on present/absent, never on joined code strings. "
        "Read the lowest code, not only the mean: pooling hides weak codes (O'Connor & Joffe 2020).",
        "Bands are conventions. Landis & Koch (1977) call their own divisions 'clearly arbitrary'; McHugh (2012) "
        "reads kappa under 0.60 as weak or worse. For alpha, Krippendorff (2004) relies on 0.800 or more and "
        "treats 0.667 to 0.800 as fit for tentative conclusions only.",
        "A rare code can show high percent agreement and a low or negative kappa (Feinstein & Cicchetti 1990). "
        "Read kappa with positive and negative agreement and PABAK (Byrt, Bishop & Carlin 1993).",
    ]
    kinds = {c["kind"] for c in coders}
    if kinds == {"llm"}:
        notes.append("All coders are language models: this measures consistency between model runs, not agreement with a person. It is not double coding.")
    elif None in kinds:
        notes.append("Coder type not stated (--coder-info): say in the report who or what coded, with the model name for an LLM.")
    if blank:
        notes.append(f"{len(blank)} row(s) that every coder marked {NO_ANSWER} were left out: they would inflate agreement.")
    if args.sample:
        notes.append(f"Compared on the {len(all_ids)} id(s) of the sample {args.sample}; rows outside it were left out.")
    if not args.text_col:
        notes.append("No --text-col: the script could not check that the coders saw the same answer text.")
    elif without_text:
        notes.append(
            f"No '{args.text_col}' column in {', '.join(without_text)}: the answer text in that file could not be "
            "checked against the others."
        )
    if partial:
        notes.append(f"{len(partial)} id(s) were not coded by every coder; {len(all_ids) - len(comparable)} of them by one coder only (ignored).")
    result = {
        "coders": coders,
        "gold": coders[0]["key"] if args.gold else None,
        "codebook_version": args.codebook_version,
        "bootstrap": {"replicates": args.bootstrap, "seed": args.seed, "level": 95, "method": "percentile, resampling responses"},
    }
    pair_units = {}
    reports = {}
    for x, y in combinations(range(len(paths)), 2):
        shared = [u for u in units if u in sets[x] and u in sets[y]]
        if not shared:
            continue
        pair_units[(x, y)] = shared
        reports[(x, y)] = pair_report(shared, sets[x], sets[y], codes, gold=bool(args.gold) and x == 0)
    if not reports:
        raise InputError("no pair of coders shares a row to compare")
    if two:
        report = reports[(0, 1)]
        if args.bootstrap:
            bootstrap_pair(pair_units[(0, 1)], sets[0], sets[1], report, args.bootstrap, rng)
        result.update({"overall": report["overall"], "single_coded": report["single"], "per_code": report["lines"]})
    else:
        result.update(multi_coder(units, sets, codes, reports, coders, args.bootstrap, rng))
    if args.bootstrap and any(l.get("ci_crosses_band") for l in result["per_code"]):
        notes.append("Intervals marked * cross a band edge: the label could be either side, so do not quote the band without the interval.")
    if any(l.get("high_agreement_low_kappa") for l in result["per_code"]):
        notes.append(
            f"Flag 'high agreement, low kappa': percent agreement of {PARADOX_AGREEMENT:g}% or more with kappa under "
            f"{PARADOX_KAPPA:.2f}. Usually a rare (or near-universal) code; judge it on positive agreement and the disputed rows."
        )
    disputed = []
    for u in units:
        present = [j for j in range(len(paths)) if u in sets[j]]
        if any(sets[j][u] != sets[present[0]][u] for j in present):
            everyone = set.intersection(*[sets[j][u] for j in present])
            anyone = set.union(*[sets[j][u] for j in present])
            text = next((loaded[j][u]["text"] for j in present if loaded[j][u]["text"] is not None), "")
            row = {args.id_col: u, "text": text}
            for j in range(len(paths)):
                row[f"codes_{coders[j]['key']}"] = args.delimiter.join(loaded[j][u]["codes"]) if j in present else ""
            row["in_dispute"] = args.delimiter.join(sorted(anyone - everyone, key=lambda c: (codes.index(c) if c in codes else len(codes), c)))
            row["final_codes"] = ""
            disputed.append(row)
    result["disagreements"] = {"rows": len(disputed), "out": args.disagreements}
    if args.disagreements:
        write_csv(args.disagreements, [args.id_col, "text"] + [f"codes_{c['key']}" for c in coders] + ["in_dispute", "final_codes"], disputed)
    result["notes"] = notes
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    out = [f"Agreement on {len(units)} responses"]
    out.append("Coders: " + "; ".join(describe(c) for c in coders) + (f". Reference (gold): {coders[0]['key']}" if args.gold else ""))
    out.append(f"Codebook version: {args.codebook_version or 'not stated'}")
    if args.bootstrap:
        out.append(f"Intervals: 95% percentile bootstrap over responses, {args.bootstrap} replicates, seed {args.seed}")
    out.append("")
    out.append(text_two(result, coders, bool(args.gold)) if two else text_multi(result, coders, bool(args.gold)))
    out.append(
        f"\n{len(disputed)} response(s) with different code sets"
        + (f"; written to {args.disagreements} for adjudication (fill final_codes, then run merge)." if args.disagreements else " (list them with --disagreements FILE).")
    )
    out.append("\nNotes\n" + "\n".join(f"- {note}" for note in notes))
    print("\n".join(out))
    return 0


def multi_coder(units, sets, codes, reports, coders, replicates, rng):
    """Three or more coders: alpha per code over all coders, plus a kappa summary for every pair."""
    count = len(sets)
    present = [[j for j in range(count) if u in sets[j]] for u in units]
    per_code, stats = [], []
    for code in codes:
        values = [[code in sets[j][u] for j in present[i]] for i, u in enumerate(units)]
        alpha = krippendorff_alpha_nominal(values)
        pair_kappas = {pair: next(l["kappa"] for l in report["lines"] if l["code"] == code) for pair, report in reports.items()}
        defined = {pair: k for pair, k in pair_kappas.items() if k is not None}
        low = min(defined, key=defined.get) if defined else None
        per_code.append(
            {
                "code": code,
                "used_by": {coders[j]["key"]: sum(1 for u in units if u in sets[j] and code in sets[j][u]) for j in range(count)},
                "alpha": number(alpha),
                "krippendorff_band": krippendorff_band(alpha),
                "mean_pairwise_kappa": round(sum(defined.values()) / len(defined), 4) if defined else None,
                "min_pairwise_kappa": defined[low] if low else None,
                "min_pairwise_kappa_pair": f"{coders[low[0]]['key']}-{coders[low[1]]['key']}" if low else None,
            }
        )
        stats.append([(sum(v), len(v)) for v in values])  # (k coders used the code, m coders coded the row)
    one_code_each = all(len(sets[j][u]) == 1 for i, u in enumerate(units) for j in present[i])
    categories = [[next(iter(sets[j][u])) for j in present[i]] for i, u in enumerate(units)] if one_code_each else None
    single = None
    if one_code_each:
        alpha = krippendorff_alpha_nominal(categories)
        single = {"alpha": number(alpha), "krippendorff_band": krippendorff_band(alpha)}
    if replicates:
        n = len(units)
        draws = [[] for _ in codes]
        cat = []
        for _ in range(replicates):
            draw = rng.choices(range(n), k=n)
            for index, stat in enumerate(stats):
                mismatch = ones = zeros = 0.0
                for u in draw:
                    k, m = stat[u]
                    if m >= 2:
                        mismatch += k * (m - k) / (m - 1)
                        ones += k
                        zeros += m - k
                draws[index].append(alpha_binary_sums(mismatch, ones, zeros))
            if one_code_each:
                cat.append(krippendorff_alpha_nominal([categories[u] for u in draw]))
        for index, line in enumerate(per_code):
            line["alpha_ci95"] = bootstrap_interval(draws[index], replicates) if line["alpha"] is not None else None
            line["ci_crosses_band"] = crosses(line["alpha_ci95"], krippendorff_band)
        if one_code_each:
            single["alpha_ci95"] = bootstrap_interval(cat, replicates) if single["alpha"] is not None else None
            single["ci_crosses_band"] = crosses(single["alpha_ci95"], krippendorff_band)
    pairwise = []
    for (x, y), report in reports.items():
        entry = {"pair": f"{coders[x]['key']}-{coders[y]['key']}"}
        entry.update({k: report["overall"][k] for k in ("units", "exact_code_set_match", "exact_code_set_match_pct", "mean_kappa", "min_kappa", "min_kappa_code")})
        entry["categorical_kappa"] = report["single"]["kappa"] if report["single"] else None
        entry["per_code"] = report["lines"]
        pairwise.append(entry)
    alphas = [l for l in per_code if l["alpha"] is not None]
    lowest = min(alphas, key=lambda l: l["alpha"]) if alphas else None
    overall = {
        "units": len(units),
        "coders": count,
        "codes_compared": len(per_code),
        "codes_with_undefined_alpha": [l["code"] for l in per_code if l["alpha"] is None],
        "mean_alpha": round(sum(l["alpha"] for l in alphas) / len(alphas), 4) if alphas else None,
        "min_alpha": lowest["alpha"] if lowest else None,
        "min_alpha_code": lowest["code"] if lowest else None,
    }
    return {"overall": overall, "single_coded": single, "per_code": per_code, "pairwise": pairwise}


def text_two(result, coders, gold):
    lines, overall, single = result["per_code"], result["overall"], result["single_coded"]
    a, b = coders[0]["key"], coders[1]["key"]
    out = [
        table(
            ["Code", f"{a} used", f"{b} used", "both", f"{a} only", f"{b} only", "neither", "% agree", "pos. agree", "neg. agree", "PABAK"],
            [
                [l["code"], l["used_by_a"], l["used_by_b"], l["both"], l["a_only"], l["b_only"], l["neither"], f"{l['percent_agreement']:.1f}%", show(l["positive_agreement"]), show(l["negative_agreement"]), show(l["pabak"])]
                for l in lines
            ],
        ),
        "",
    ]
    rows = []
    for l in lines:
        flags = []
        if l["kappa"] is None:
            flags.append("not tested" if l["used_by_a"] + l["used_by_b"] == 0 else "on every row")
        if l.get("ci_crosses_band"):
            flags.append("* interval crosses a band")
        if l["high_agreement_low_kappa"]:
            flags.append("high agreement, low kappa")
        rows.append(
            [l["code"], show(l["kappa"]), show_ci(l.get("kappa_ci95")), l["landis_koch"] or "-", l["mchugh"] or "-", show(l["alpha"]), show_ci(l.get("alpha_ci95")), l["krippendorff_band"] or "-", "; ".join(flags)]
        )
    out.append(table(["Code", "kappa", "95% interval", "Landis-Koch", "McHugh", "alpha", "95% interval", "alpha band", "Flags"], rows))
    for l in lines:
        if l["kappa_undefined_reason"]:
            out.append(f"  {l['code']}: {l['kappa_undefined_reason']}.")
    if gold:
        out.append(
            f"\nAgainst the reference coder {a} (precision: share of {b}'s uses that {a} also coded; recall: share of {a}'s uses that {b} found)\n\n"
            + table(
                ["Code", f"{a} used", f"{b} used", "precision", "recall", "F1", "kappa"],
                [[l["code"], l["used_by_a"], l["used_by_b"], show(l["precision"]), show(l["recall"]), show(l["f1"]), show(l["kappa"])] for l in lines],
            )
        )
    out.append("\nOverall")
    exact_ci = overall.get("exact_code_set_match_pct_ci95")
    out.append(
        f"  Identical code set on {overall['exact_code_set_match']} of {overall['units']} responses ({overall['exact_code_set_match_pct']:.1f}%"
        + (f", 95% interval {exact_ci[0]:.1f} to {exact_ci[1]:.1f}" if exact_ci else "")
        + ")"
    )
    if overall["mean_kappa"] is not None:
        defined = overall["codes_compared"] - len(overall["codes_with_undefined_kappa"])
        out.append(
            f"  Kappa across {defined} codes: mean {show(overall['mean_kappa'])}"
            + (f" (95% interval {show_ci(overall.get('mean_kappa_ci95'))})" if overall.get("mean_kappa_ci95") else "")
            + f", lowest {show(overall['min_kappa'])} ({overall['min_kappa_code']})"
        )
    if overall["pooled_decisions"]:
        out.append(
            f"  Pooled over {overall['pooled_decisions']} code-by-response decisions (codes at least one coder used): "
            f"{overall['pooled_percent_agreement']:.1f}% agreement, kappa {show(overall['pooled_kappa'])}"
            + (f" (95% interval {show_ci(overall.get('pooled_kappa_ci95'))})" if overall.get("pooled_kappa_ci95") else "")
            + (f", {overall['pooled_landis_koch']}" if overall["pooled_kappa"] is not None else "")
            + (" (* interval crosses a band)" if overall.get("pooled_kappa_ci_crosses_band") else "")
        )
    if single:
        out.append(
            f"  One code per response for both coders: categorical kappa {show(single['kappa'])}"
            + (f" (95% interval {show_ci(single.get('kappa_ci95'))})" if single.get("kappa_ci95") else "")
            + (f", Landis-Koch {single['landis_koch']}, McHugh {single['mchugh']}" if single["kappa"] is not None else "")
            + f"; alpha {show(single['alpha'])}"
            + (f" (95% interval {show_ci(single.get('alpha_ci95'))})" if single.get("alpha_ci95") else "")
            + (f", {single['krippendorff_band']}" if single["alpha"] is not None else "")
            + f"; {single['percent_agreement']:.1f}% agreement"
        )
    return "\n".join(out)


def undefined_flag(line):
    """Flag for a code whose alpha is undefined: nobody used it, or every coder used it on every row."""
    return "not tested" if sum(line["used_by"].values()) == 0 else "on every row"


def text_multi(result, coders, gold=False):
    keys = [c["key"] for c in coders]
    out = [
        table(
            ["Code", "used by " + "/".join(keys), "alpha", "95% interval", "alpha band", "mean pairwise kappa", "lowest pairwise kappa", "Flags"],
            [
                [
                    l["code"],
                    "/".join(str(l["used_by"][k]) for k in keys),
                    show(l["alpha"]),
                    show_ci(l.get("alpha_ci95")),
                    l["krippendorff_band"] or "-",
                    show(l["mean_pairwise_kappa"]) if l["mean_pairwise_kappa"] is not None else "-",
                    f"{show(l['min_pairwise_kappa'])} ({l['min_pairwise_kappa_pair']})" if l["min_pairwise_kappa"] is not None else "-",
                    undefined_flag(l) if l["alpha"] is None else ("* interval crosses a band" if l.get("ci_crosses_band") else ""),
                ]
                for l in result["per_code"]
            ],
        )
    ]
    for l in result["per_code"]:
        if l["alpha"] is None:
            reason = "no coder used this code" if undefined_flag(l) == "not tested" else "every coder gave this code to every row"
            out.append(f"  {l['code']}: {reason}: the values do not vary, so alpha is undefined.")
    head = ["Pair", "responses", "identical code set", "mean kappa", "lowest kappa (code)"]
    single = result["single_coded"]
    if single:
        head.append("categorical kappa")
    rows = []
    for p in result["pairwise"]:
        row = [
            p["pair"],
            p["units"],
            f"{p['exact_code_set_match']} ({p['exact_code_set_match_pct']:.1f}%)",
            show(p["mean_kappa"]) if p["mean_kappa"] is not None else "-",
            f"{show(p['min_kappa'])} ({p['min_kappa_code']})" if p["min_kappa"] is not None else "-",
        ]
        if single:
            row.append(show(p["categorical_kappa"]))
        rows.append(row)
    out.append("\nPairwise Cohen's kappa (each pair on the responses both coded)\n\n" + table(head, rows))
    if gold:
        a = keys[0]
        for p in result["pairwise"]:
            if not p["pair"].startswith(f"{a}-"):
                continue
            b = p["pair"].split("-", 1)[1]
            out.append(
                f"\nAgainst the reference coder {a}: coder {b} (precision: share of {b}'s uses that {a} also coded; "
                f"recall: share of {a}'s uses that {b} found)\n\n"
                + table(
                    ["Code", f"{a} used", f"{b} used", "precision", "recall", "F1", "kappa"],
                    [[l["code"], l["used_by_a"], l["used_by_b"], show(l["precision"]), show(l["recall"]), show(l["f1"]), show(l["kappa"])] for l in p["per_code"]],
                )
            )
    overall = result["overall"]
    out.append("\nOverall")
    if overall["mean_alpha"] is not None:
        out.append(f"  Alpha across codes: mean {show(overall['mean_alpha'])}, lowest {show(overall['min_alpha'])} ({overall['min_alpha_code']})")
    if single:
        out.append(
            f"  One code per response for every coder: alpha {show(single['alpha'])}"
            + (f" (95% interval {show_ci(single.get('alpha_ci95'))})" if single.get("alpha_ci95") else "")
            + (f", {single['krippendorff_band']}" if single["alpha"] is not None else "")
        )
    return "\n".join(out)


# ---------------------------------------------------------------- merge


def cmd_merge(args):
    """Write decided codes into the coded file by id. Also the batch-coding path: a responses file with no codes
    column gets one, filled from `id,codes` batch files, so answer text is never retyped."""
    guard_output(args.out, [args.input] + list(args.adjudicated) + [args.codebook])
    fields, rows = read_csv(args.input)
    need_column(args.input, fields, args.id_col, "id")
    added_column = args.codes_col not in fields
    if added_column:
        fields = fields + [args.codes_col]
        for row in rows:
            row[args.codes_col] = ""
    known = None
    if args.codebook:
        entries, problems = read_codebook(args.codebook, args.delimiter)
        if problems:
            raise InputError(f"{args.codebook}: " + "; ".join(problems))
        known = {e["code"] for e in entries} | set(RESERVED)
    by_id = {}
    for number_, row in enumerate(rows, start=2):
        row_id = row[args.id_col].strip()
        if not row_id:
            raise InputError(f"{args.input}: line {number_} has an empty id")
        if row_id in by_id:
            raise InputError(f"{args.input}: id '{row_id}' appears more than once")
        by_id[row_id] = row
    changed, same, pending, seen, total = [], [], [], set(), 0
    for path in args.adjudicated:
        adj_fields, adj_rows = read_csv(path)
        need_column(path, adj_fields, args.id_col, "id")
        need_column(path, adj_fields, args.final_col, "final codes")
        total += len(adj_rows)
        for number_, adj in enumerate(adj_rows, start=2):
            row_id = adj[args.id_col].strip()
            if not row_id:
                raise InputError(f"{path}: line {number_} has an empty id")
            if row_id not in by_id:
                raise InputError(f"{path}: line {number_}: id '{row_id}' is not in {args.input}")
            if row_id in seen:
                raise InputError(f"{path}: id '{row_id}' appears more than once across the --adjudicated files")
            seen.add(row_id)
            final = list(dict.fromkeys(c.strip() for c in adj[args.final_col].split(args.delimiter) if c.strip()))
            if not final:
                pending.append(row_id)
                continue
            if known is not None and [c for c in final if c not in known]:
                raise InputError(f"{path}: line {number_}: unknown code in '{adj[args.final_col]}'")
            if len(final) > 1 and set(final) & set(EXCLUSIVE):
                raise InputError(f"{path}: line {number_}: {UNCODABLE} and {NO_ANSWER} cannot be combined with other codes")
            current = [c.strip() for c in by_id[row_id][args.codes_col].split(args.delimiter) if c.strip()]
            (same if set(current) == set(final) else changed).append(row_id)
            by_id[row_id][args.codes_col] = args.delimiter.join(final)
    if pending and not args.allow_pending:
        raise InputError(
            f"{len(pending)} row(s) have no {args.final_col} (for example id '{pending[0]}'). "
            "Decide them, or pass --allow-pending to leave those rows as they are."
        )
    uncoded = [r[args.id_col].strip() for r in rows if not r[args.codes_col].strip()]
    write_csv(args.out, fields, rows)
    result = {
        "input": args.input,
        "adjudicated": args.adjudicated,
        "out": args.out,
        "rows": len(rows),
        "codes_column_added": added_column,
        "changed": changed,
        "confirmed": same,
        "pending": pending,
        "rows_without_codes": len(uncoded),
    }
    text = (
        f"Merged {total} row(s) from {len(args.adjudicated)} file(s) into {args.out} ({len(rows)} rows): {len(changed)} changed, "
        f"{len(same)} confirmed as they were, {len(pending)} left pending."
    )
    if added_column:
        text += f" Added the '{args.codes_col}' column."
    if uncoded:
        text += f" {len(uncoded)} row(s) still have no codes; validate lists them."
    return emit(args, result, text)


# ---------------------------------------------------------------- command line


def build_parser():
    parser = argparse.ArgumentParser(
        prog="open_ended_coding.py",
        description="Sampling, validation, counts and coder agreement for coded open-ended answers.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("sample", help="draw a seeded random sample of answers")
    p.add_argument("input", help="CSV with one row per response")
    p.add_argument("--id-col", default="id", help="column with the row id (default: id)")
    p.add_argument("--text-col", required=True, help="column with the answer text")
    size = p.add_mutually_exclusive_group()
    size.add_argument("--n", type=int, help="number of answers to draw")
    size.add_argument("--fraction", type=float, help="share of eligible answers to draw, e.g. 0.2")
    p.add_argument("--all-if-fewer", action="store_true", help="with --n: take every eligible answer when there are fewer than N")
    p.add_argument("--at-least", type=int, help="with --fraction: draw at least this many, or all eligible answers if fewer")
    p.add_argument("--shuffle", action="store_true", help="write the rows in a seeded random order (read the codebook sample in this order) instead of file order")
    p.add_argument("--seed", type=int, default=1, help="random seed (default: 1); report it")
    p.add_argument("--exclude", action="append", help="CSV whose ids must not be drawn again (repeatable)")
    p.add_argument("--include-blank", action="store_true", help="blank answers may be drawn (default: left out)")
    p.add_argument("--stratify-col", help="draw proportionally within the values of this column")
    p.add_argument("--top-up-min", type=int, help="rare-code audit: pick extra rows until every code of the first coder is carried by at least this many rows (needs --codes-col and --top-up-out)")
    p.add_argument("--top-up-out", help="CSV for the --top-up-min rows; kept apart from the random sample in --out")
    p.add_argument("--codes-col", default="codes", help="codes column used by --top-up-min (default: codes)")
    p.add_argument("--delimiter", "--code-sep", dest="delimiter", default=";", help="separator between codes inside --codes-col (default: ;)")
    add_csv_option(p)
    p.add_argument("--all-columns", action="store_true", help="keep every column (default: id and text only, so a second coder cannot see earlier codes)")
    p.add_argument("--out", help="write the sample to this CSV (default: stdout)")
    p.add_argument("--json", action="store_true", help="print a JSON summary with the sampled ids")
    p.set_defaults(func=cmd_sample)

    p = sub.add_parser("saturation", help="new codes per batch while building the codebook")
    p.add_argument("input", help="the coded codebook sample, rows in the order they were read")
    add_coded_options(p)
    p.add_argument("--base", type=int, default=50, help="answers in the base (default: 50)")
    p.add_argument("--run", type=int, default=25, help="answers per run (default: 25)")
    p.add_argument("--step", type=int, default=1, help="answers the run moves forward each time (default: 1, as in Guest et al. 2020; set it equal to --run for non-overlapping runs)")
    p.add_argument("--threshold", type=float, default=5.0, help="stop when a run's new codes are at most this percent of the base codes (default: 5)")
    p.set_defaults(func=cmd_saturation)

    p = sub.add_parser("validate", help="check a coded file against the codebook")
    p.add_argument("input", help="coded CSV, one row per response")
    add_coded_options(p)
    p.add_argument("--quotes", help="CSV with columns id,code,quote: each quote must be word for word in that row ('...' at either end is allowed)")
    p.add_argument("--source", help="the original responses CSV: every id must be coded once, with the same answer text")
    p.add_argument("--source-text-col", help="answer column in --source if it differs from --text-col")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("counts", help="code frequencies with explicit denominators")
    p.add_argument("input", help="coded CSV, one row per response")
    add_coded_options(p)
    p.add_argument("--segment-col", help="column to cut the counts by")
    p.add_argument("--min-base", type=int, default=DEFAULT_MIN_BASE, help=f"withhold percentages on bases under this (default: {DEFAULT_MIN_BASE})")
    p.add_argument("--mentions", action="store_true", help="add a '%% of mentions' column (share of code assignments)")
    p.add_argument("--sentiment-col", help="optional column with one of positive, negative, neutral, mixed per answer; counted, never computed")
    p.add_argument("--rare-below", type=int, default=DEFAULT_RARE_BELOW, help=f"health check: flag codes used fewer than this many times (default: {DEFAULT_RARE_BELOW})")
    p.add_argument("--broad-above", type=float, default=DEFAULT_BROAD_ABOVE, help=f"health check: flag codes on more than this percent of answers (default: {DEFAULT_BROAD_ABOVE:g})")
    p.add_argument("--other-above", type=float, default=DEFAULT_OTHER_ABOVE, help=f"health check: flag OTHER above this percent of answers (default: {DEFAULT_OTHER_ABOVE:g})")
    p.add_argument("--top-pairs", type=int, default=5, help="health check: how many co-occurring code pairs to list (default: 5)")
    p.set_defaults(func=cmd_counts)

    p = sub.add_parser("agreement", help="agreement between two or more coders, with bootstrap intervals")
    p.add_argument("coders", nargs="*", help="coded CSVs, one per coder, same rows")
    add_coded_options(p, text_help="column with the answer text, copied into --disagreements when a file has it")
    p.add_argument("--gold", help="reference coding (for example a person's): adds precision, recall and F1 for the other coder")
    p.add_argument("--coder-info", action="append", help="ID,human or ID,llm,MODEL; once per coder, gold first, then the files in order")
    p.add_argument("--codebook-version", help="version label of the codebook both coders used, printed in the report")
    p.add_argument("--bootstrap", type=int, default=DEFAULT_BOOTSTRAP, help=f"bootstrap replicates for 95%% intervals; 0 turns them off (default: {DEFAULT_BOOTSTRAP})")
    p.add_argument("--seed", type=int, default=1, help="bootstrap seed (default: 1)")
    p.add_argument("--allow-unmatched", action="store_true", help="rows missing from a file are treated as not coded by that coder")
    p.add_argument("--sample", help="the sample file the second coder was given: compare on its ids only, and every coder file must hold all of them with the same answer text")
    p.add_argument("--disagreements", help="write the rows with different code sets to this CSV for adjudication")
    p.set_defaults(func=cmd_agreement)

    p = sub.add_parser("merge", help="write adjudicated codes back into the coded file")
    p.add_argument("input", help="coded CSV")
    p.add_argument("--adjudicated", required=True, action="append", help="CSV with the id column and the final codes: the --disagreements file filled in, or an id,codes batch file with --final-col codes (repeatable)")
    p.add_argument("--out", required=True, help="where to write the merged coded file")
    p.add_argument("--id-col", default="id", help="column with the row id (default: id)")
    p.add_argument("--codes-col", default="codes", help="codes column in the coded file (default: codes)")
    p.add_argument("--final-col", default="final_codes", help="column with the decided codes (default: final_codes)")
    p.add_argument("--delimiter", "--code-sep", dest="delimiter", default=";", help="separator between codes (default: ;)")
    add_csv_option(p)
    p.add_argument("--codebook", help="codebook CSV; final codes must be in it")
    p.add_argument("--allow-pending", action="store_true", help="rows with no final codes stay as they are")
    p.add_argument("--json", action="store_true", help="print machine-readable JSON")
    p.set_defaults(func=cmd_merge)
    return parser


def main(argv=None):
    global CSV_DELIMITER
    args = build_parser().parse_args(argv)
    CSV_DELIMITER = args.csv_delimiter
    if CSV_DELIMITER is not None:
        CSV_DELIMITER = {"\\t": "\t", "tab": "\t", "semicolon": ";", "comma": ",", "pipe": "|"}.get(CSV_DELIMITER, CSV_DELIMITER)
        if len(CSV_DELIMITER) != 1:
            print("open-ended-coding: error: --csv-delimiter must be one character (or tab, semicolon, comma, pipe)", file=sys.stderr)
            return 2
    if getattr(args, "delimiter", ";") == "":
        print("open-ended-coding: error: --delimiter must not be empty", file=sys.stderr)
        return 2
    if args.command == "validate" and not args.codebook:
        print("open-ended-coding: error: validate needs --codebook", file=sys.stderr)
        return 2
    try:
        return args.func(args)
    except InputError as exc:
        print(f"open-ended-coding: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
