#!/usr/bin/env python3
"""Score and segment a Sean Ellis product-market-fit survey from a CSV of responses.

Reads one row per respondent. Reports the share answering "very disappointed" with a
Wilson score interval, compares it with the 40% benchmark using the interval (above /
below / cannot tell), scores each segment with small-base flags, and splits the
"somewhat disappointed" group by whether their main benefit matches the core benefit.

Sources for every rule and number: references/sources.md.
Standard library only, Python 3.9+. No network. Exit 0 on success, 2 on bad input.

Usage:
  python3 scripts/pmf_survey.py responses.csv
  python3 scripts/pmf_survey.py --counts very=16,somewhat=14,not=10,na=8
  python3 scripts/pmf_survey.py responses.csv --segment-col persona --segment-col plan --benefit-col main_benefit
  python3 scripts/pmf_survey.py responses.csv --period-col wave --compare "2026-Q1,2026-Q2"
  python3 scripts/pmf_survey.py responses.csv --map "1=very" --map "2=somewhat" --map "3=not" --map "4=na" --json
"""
import argparse
import csv
import io
import json
import os
import math
import re
import sys
from collections import Counter
from statistics import NormalDist

CATEGORIES = ("very", "somewhat", "not", "na")
CATEGORY_LABELS = {
    "very": "Very disappointed",
    "somewhat": "Somewhat disappointed",
    "not": "Not disappointed",
    "na": "N/A (no longer use it)",
}
# Ellis: "at least 40%" / "over 40%" (sources.md, "The benchmark").
DEFAULT_BENCHMARK = 40.0
# Ellis: "I need at least 30 responses" (sources.md, "How many responses").
DEFAULT_MIN_BASE = 30
# Real Startup Book's rule of thumb for a low response rate (sources.md, "Who to survey").
LOW_RESPONSE_RATE = 10.0
# A numeric answer column with this many distinct values is a rating scale, not the four coded options.
RATING_SCALE_POINTS = 5
BLANK_SEGMENT = "(blank)"
DENOMINATOR_PRACTICE = (
    "Practice differs: CRV's guide leaves N/A out of the base; Pendo's PMF survey divides by all "
    "responses and offers three options with no N/A. Ellis and Vohra do not say."
)
COMPARE_RULE = (
    "Compare two waves only if the question wording, the options, who was eligible and how the survey "
    "was delivered were the same, and nobody answered in both. Otherwise the later wave is a new baseline."
)
MULTIPLE_COMPARISON_NOTE = (
    "{n} segment intervals were read at {conf:g}% each. With that many, some will clear or miss the "
    "benchmark by chance: treat a segment result as a lead to confirm on the next wave."
)
MULTIPLE_COMPARISON_NOTE_NO_BENCHMARK = (
    "{n} segment intervals were read at {conf:g}% each. With that many, some will look higher or lower than "
    "the rest by chance: treat a segment result as a lead to confirm on the next wave."
)
YES = {"yes", "y", "true", "1", "match"}
NO = {"no", "n", "false", "0", "no match"}
ANSWER_HEADER_HINTS = ("disappoint", "no longer use", "pmf")


class InputError(Exception):
    """Bad input: the message is shown to the user and the exit code is 2."""


def normalize(label):
    """Lower-case, unify dashes and apostrophes, collapse whitespace, drop trailing punctuation."""
    text = label.strip().lower()
    text = re.sub(r"[‐-―−]", "-", text)
    text = re.sub(r"[‘’ʼ`]", "'", text)
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"[\s.!,;:]+$", "", text)


# The N/A option as Ellis and Superhuman word it ("N/A - I no longer use [product]"), not any text that
# happens to contain "no longer use" (the question itself does).
MIXED_NA_RE = re.compile(r"^not disappointed\b.*\b(no longer use|don't use|do not use)\b")
NA_OPTION_RE = re.compile(r"^(n/?a|not applicable)(\b|$)|^(i )?(no longer use|don't use|do not use)\b")


def builtin_category(norm):
    """Map the label variants of the Ellis and Superhuman wordings. None when unknown."""
    if not norm:
        return None
    if norm in ("very disappointed", "very"):
        return "very"
    if norm in ("somewhat disappointed", "somewhat"):
        return "somewhat"
    if norm == "not" or norm.startswith("not disappointed"):
        # "Not disappointed - I no longer use it" mixes two options: unknown, so the user maps it.
        if MIXED_NA_RE.search(norm):
            return None
        return "not"
    if NA_OPTION_RE.search(norm):
        return "na"
    return None


def is_question_text(norm, header):
    """A second header row: the cell repeats the column header or holds the question itself."""
    return norm == normalize(header) or norm.rstrip().endswith("?") or norm.startswith("how would you feel")


def nonstandard_reason(norm):
    """A label from another scale (for example "Mildly disappointed"). None when it is not one."""
    if builtin_category(norm) is not None or MIXED_NA_RE.search(norm):
        return None  # a mixed "not disappointed / no longer use" label is unknown: ask, then --map
    if "disappoint" in norm or norm in ("neutral", "extremely", "mildly", "slightly", "moderately"):
        return "a different disappointment scale"
    return None


def parse_counts(text, option):
    counts = {}
    for part in text.split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise InputError(f'{option} expects pairs like very=16,somewhat=14,not=10,na=8; got "{part.strip()}"')
        key, value = (piece.strip().lower() for piece in part.split("=", 1))
        if key not in CATEGORIES + ("blank",):
            raise InputError(f'{option}: unknown key "{key}". Use very, somewhat, not, na, blank.')
        if key in counts:
            raise InputError(f'{option}: "{key}" is given twice.')
        if not re.fullmatch(r"[0-9]+", value):
            raise InputError(f'{option}: "{key}={value}" is not a whole number of respondents.')
        counts[key] = int(value)
    missing = [key for key in ("very", "somewhat", "not") if key not in counts]
    if missing:
        raise InputError(
            f"{option} must give very, somewhat and not (missing: {', '.join(missing)}). "
            "na and blank are optional and count as 0."
        )
    return {key: counts.get(key, 0) for key in CATEGORIES + ("blank",)}


def parse_map(pairs):
    mapping = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise InputError(f'--map expects LABEL=CATEGORY, got "{pair}"')
        label, category = pair.rsplit("=", 1)
        category = category.strip().lower()
        if category not in CATEGORIES:
            raise InputError(
                f'--map "{pair}": category must be one of {", ".join(CATEGORIES)}'
            )
        if not label.strip():
            raise InputError(f'--map "{pair}": the label is empty')
        mapping[normalize(label)] = category
    return mapping


def wilson(successes, n, z):
    """Wilson (1927) score interval for a binomial proportion, no continuity correction."""
    if n <= 0:
        raise ValueError("n must be positive")
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def newcombe_diff(x1, n1, x2, n2, z):
    """Newcombe (1998) hybrid score interval for p2 - p1, two independent samples.

    Built from the Wilson limits (l, u) of each proportion:
    lower = d - sqrt((p2 - l2)^2 + (u1 - p1)^2), upper = d + sqrt((u2 - p2)^2 + (p1 - l1)^2).
    """
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = wilson(x1, n1, z)
    l2, u2 = wilson(x2, n2, z)
    d = p2 - p1
    low = d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2)
    high = d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)
    return d, low, high


def z_for(confidence):
    return NormalDist().inv_cdf(0.5 + confidence / 200.0)


def verdict_for(low, high, benchmark):
    """Compare the interval, not the point estimate, with the benchmark."""
    b = benchmark / 100.0
    if low > b:
        return "above"
    if high < b:
        return "below"
    return "cannot_tell"


def score_block(very, base, z, benchmark, min_base, comparable=True):
    if base == 0:
        return {
            "very": 0,
            "base": 0,
            "pct": None,
            "ci_low_pct": None,
            "ci_high_pct": None,
            "verdict": "no_base",
            "small_base": True,
        }
    low, high = wilson(very, base, z)
    return {
        "very": very,
        "base": base,
        "pct": round(100 * very / base, 1),
        "ci_low_pct": round(100 * low, 1),
        "ci_high_pct": round(100 * high, 1),
        "verdict": verdict_for(low, high, benchmark) if comparable else "not_comparable",
        "small_base": base < min_base,
    }


def find_column(fieldnames, wanted, what):
    if wanted in fieldnames:
        return wanted
    lowered = {name.strip().lower(): name for name in fieldnames}
    if wanted.strip().lower() in lowered:
        return lowered[wanted.strip().lower()]
    raise InputError(
        f'{what} column "{wanted}" not found. Columns in the file: {", ".join(fieldnames)}'
    )


def detect_answer_column(fieldnames):
    hits = [
        name
        for name in fieldnames
        if any(hint in name.lower() for hint in ANSWER_HEADER_HINTS)
    ]
    if len(hits) == 1:
        return hits[0]
    reason = "no column" if not hits else "more than one column (" + ", ".join(hits) + ")"
    raise InputError(
        f"Cannot pick the disappointment answer column: {reason} has a header containing "
        f'"disappoint", "no longer use" or "pmf". Pass --answer-col. Columns in the file: '
        + ", ".join(fieldnames)
    )


DELIMITER_NAME = {";": "semicolons", "\t": "tabs", "|": "pipes"}


def read_rows(path, delimiter, explicit, notes):
    """Read the CSV. Stops on duplicate column names and on rows wider or narrower than the header, which
    a dict would otherwise resolve silently. A header with no comma but semicolons, tabs or pipes is read
    with that delimiter unless --delimiter was given."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            text = handle.read()
    except FileNotFoundError:
        raise InputError(f"File not found: {path}")
    except UnicodeDecodeError:
        raise InputError(f"{path} is not UTF-8 text. Re-export the CSV as UTF-8.")
    except OSError as exc:
        raise InputError(f"Cannot read {path}: {exc.strerror or exc}")
    first_line = text.split("\n", 1)[0]
    # Excel writes "sep=;" as line 1 to name the delimiter; it is not the header.
    sep_line = re.fullmatch(r"sep=(.)\r?", first_line)
    if sep_line:
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if not explicit:
            delimiter = sep_line.group(1)
            explicit = True
        notes.append(f'Line 1 was "{first_line.strip()}" (Excel\'s delimiter line); it was skipped.')
        first_line = text.split("\n", 1)[0]
    if not explicit and "," not in first_line:
        found = [d for d in (";", "\t", "|") if d in first_line]
        if len(found) == 1:
            delimiter = found[0]
            notes.append(f"The file uses {DELIMITER_NAME[delimiter]} as its delimiter; it was read that way.")
    try:
        table = [row for row in csv.reader(io.StringIO(text), delimiter=delimiter) if row]
    except csv.Error as exc:
        raise InputError(f"{path} is not a readable CSV: {exc}")
    if not table or not any(cell.strip() for cell in table[0]):
        raise InputError(f"{path} is empty or has no header row.")
    fieldnames = table[0]
    seen = Counter(normalize(name) for name in fieldnames)
    repeated = [name for name in dict.fromkeys(fieldnames) if seen[normalize(name)] > 1]
    if repeated:
        raise InputError(
            f"{path} has more than one column named " + ", ".join(f'"{name}"' for name in repeated)
            + " (ignoring case and spacing). Exports that repeat a question for several waves need the columns "
            "renamed first, so the script cannot pick the wrong one."
        )
    rows = []
    for index, row in enumerate(table[1:], start=2):
        if len(row) != len(fieldnames):
            raise InputError(
                f"{path} row {index} has {len(row)} cells but the header has {len(fieldnames)}; a row may be cut "
                "or shifted, so answers would land in the wrong column."
            )
        rows.append(dict(zip(fieldnames, row)))
    if not rows:
        raise InputError(f"{path} has a header but no response rows.")
    return fieldnames, rows


def classify(rows, answer_col, custom):
    """Sort rows into the four categories. Raises on labels that are unknown or from another scale."""
    labelled = []
    blank_rows = []
    question_rows = 0
    for row in rows:
        raw = (row.get(answer_col) or "").strip()
        if not raw:
            blank_rows.append(row)
            continue
        if is_question_text(normalize(raw), answer_col):
            question_rows += 1
            continue
        labelled.append((raw, normalize(raw), row))
    # Whole numbers, also as exported by pandas or R ("3.0"). Ellis has four options, so five or more
    # distinct codes, or any code above 4, is a rating scale.
    numeric = {raw: int(float(raw)) for raw, _, _ in labelled if re.fullmatch(r"[0-9]+(\.0+)?", raw)}
    is_scale = len(set(numeric.values())) >= RATING_SCALE_POINTS or any(v > 4 for v in numeric.values())
    rating_scale = set(numeric) if is_scale else set()

    unknown, nonstandard = Counter(), Counter()
    mapped_nonstandard = set()
    label_map_used = {}
    records = []
    custom_used = set()
    for raw, norm, row in labelled:
        builtin = builtin_category(norm)
        category = custom.get(norm) or builtin
        other_scale = builtin is None and (raw in rating_scale or nonstandard_reason(norm) is not None)
        if category is None:
            (nonstandard if other_scale else unknown)[raw] += 1
            continue
        if other_scale:
            mapped_nonstandard.add(raw)
        elif builtin is None:
            custom_used.add(raw)
        label_map_used[raw] = category
        records.append((category, row))
    if unknown or nonstandard:
        parts = []
        if nonstandard:
            listing = "; ".join(f'"{label}" ({count})' for label, count in sorted(nonstandard.items()))
            parts.append(
                f"Non-standard answer wording, not comparable with the {DEFAULT_BENCHMARK:g}% benchmark: {listing}. "
                "These labels belong to another scale (a different set of options or a rating scale), and the "
                "benchmark was built on Ellis's four options. To score them anyway as your own baseline, map "
                "each with --map; the benchmark verdict is then left out."
            )
        if unknown:
            listing = "; ".join(f'"{label}" ({count})' for label, count in sorted(unknown.items()))
            parts.append(
                f"Unknown answer labels: {listing}. "
                'Map each one with --map "LABEL=very|somewhat|not|na" and run again.'
            )
        raise InputError(f'Column "{answer_col}": ' + " ".join(parts) + " Nothing was scored.")
    return records, blank_rows, label_map_used, sorted(mapped_nonstandard), sorted(custom_used), question_rows


def tally(records):
    counted = Counter(category for category, _ in records)
    return {category: counted.get(category, 0) for category in CATEGORIES}


def base_of(counts):
    return counts["very"] + counts["somewhat"] + counts["not"]


def analyse(args):
    if args.benefit_col and args.benefit_match_col:
        raise InputError("Pass --benefit-col or --benefit-match-col, not both.")
    if args.core_benefit and not args.benefit_col:
        raise InputError("--core-benefit needs --benefit-col.")
    if not 0 < args.benchmark < 100:
        raise InputError("--benchmark must be between 0 and 100 (a percentage).")
    if 0 < args.confidence < 1:
        args.confidence *= 100  # 0.95 means 95%
    if not 50 <= args.confidence < 100:
        raise InputError("--confidence must be a level such as 95 or 0.95, at least 50%.")
    if args.min_base < 1:
        raise InputError("--min-base must be 1 or more.")
    if args.account_benchmark is not None and not args.account_col:
        raise InputError("--account-benchmark needs --account-col.")
    if args.account_benchmark is not None and not 0 < args.account_benchmark < 100:
        raise InputError("--account-benchmark must be between 0 and 100 (a percentage).")
    if bool(args.input) == bool(args.counts):
        raise InputError("Give a CSV file or --counts very=..,somewhat=..,not=.. (one of the two).")
    segment_cols = args.segment_col or []
    if args.focus_segments and len(segment_cols) != 1:
        raise InputError("--focus-segments needs exactly one --segment-col.")
    if args.period_col and args.previous_counts:
        raise InputError("Pass --period-col or --previous-counts, not both.")
    if bool(args.period_col) != bool(args.compare):
        raise InputError('--period-col and --compare "EARLIER,LATER" go together: the order of periods is not guessed.')
    if args.id_col and not args.period_col:
        raise InputError("--id-col is used to find people who answered in both waves; it needs --period-col.")

    z = z_for(args.confidence)
    notes = []
    columns = {
        "answer": None, "segments": [], "benefit": None, "benefit_match": None, "period": None, "account": None,
        "id": None,
    }
    question_rows = 0
    if args.counts:
        needs_rows = {
            "--answer-col": args.answer_col, "--segment-col": segment_cols, "--benefit-col": args.benefit_col,
            "--benefit-match-col": args.benefit_match_col, "--period-col": args.period_col,
            "--account-col": args.account_col, "--map": args.map,
        }
        used = [name for name, value in needs_rows.items() if value]
        if used:
            raise InputError(f"{', '.join(used)} need a CSV of respondents; --counts has totals only.")
        given = parse_counts(args.counts, "--counts")
        blank = given.pop("blank")
        counts = {category: given[category] for category in CATEGORIES}
        records, all_records = None, None
        rows_read, label_map_used, mapped_nonstandard, custom_used = None, {}, [], []
        source = "--counts"
    else:
        custom = parse_map(args.map)
        fieldnames, rows = read_rows(args.input, args.delimiter or ",", args.delimiter is not None, notes)
        columns["answer"] = (
            find_column(fieldnames, args.answer_col, "Answer") if args.answer_col else detect_answer_column(fieldnames)
        )
        columns["segments"] = [find_column(fieldnames, name, "Segment") for name in segment_cols]
        for key, name, what in (
            ("benefit", args.benefit_col, "Benefit"),
            ("benefit_match", args.benefit_match_col, "Benefit-match"),
            ("period", args.period_col, "Period"),
            ("account", args.account_col, "Account"),
            ("id", args.id_col, "Respondent id"),
        ):
            if name:
                columns[key] = find_column(fieldnames, name, what)
        all_records, blank_rows, label_map_used, mapped_nonstandard, custom_used, question_rows = classify(
            rows, columns["answer"], custom
        )
        records = all_records
        rows_read = len(rows)
        source = args.input

    # The 40% benchmark belongs to Ellis's question and four options. Labels the script recognises carry
    # that wording; labels mapped by hand (codes, other words) and typed counts cannot show it, so the
    # verdict needs --ellis-wording, given once the user has confirmed the question and options.
    if mapped_nonstandard:
        comparable, wording = False, "non-standard"
    elif (custom_used or args.counts) and not args.ellis_wording:
        comparable, wording = False, "unconfirmed"
    else:
        comparable, wording = True, "ellis"

    comparison = None
    scope = None
    if columns["period"]:
        comparison, by_period = period_comparison(all_records, columns["period"], columns["id"], args, z, comparable)
        later = comparison["later"]["period"]
        records = by_period[later]
        blank_rows = [row for row in blank_rows if (row.get(columns["period"]) or "").strip() == later]
        pooled = tally(all_records)
        scope = {
            "period": later,
            "note": (
                f'The score, segments, benefits and accounts below are for the later wave, "{later}", only. '
                f"The file holds {sum(pooled.values())} answers in all."
            ),
            "pooled": score_block(pooled["very"], base_of(pooled), z, args.benchmark, args.min_base, comparable),
        }
    if records is not None:
        counts = tally(records)
        blank = len(blank_rows)
    base = base_of(counts)
    if base == 0:
        raise InputError(
            f"No score: 0 current-user answers ({counts['na']} N/A, {blank} blank). "
            "Every respondent said they no longer use the product or left the question empty, "
            "so the sample did not reach current users. Re-sample people who used the product "
            "recently (sources.md, \"Who to survey\")."
        )

    overall = score_block(counts["very"], base, z, args.benchmark, args.min_base, comparable)
    answered = base + counts["na"]
    flags = list(notes)
    if mapped_nonstandard:
        flags.append(
            "Non-standard answer wording ("
            + ", ".join(f'"{label}"' for label in mapped_nonstandard)
            + f"): the score is not comparable with the {args.benchmark:g}% benchmark. Use it as your own baseline."
        )
    elif wording == "unconfirmed":
        what = (
            "The counts were typed in" if args.counts
            else "Answer labels were mapped by hand (" + ", ".join(f'"{label}"' for label in custom_used) + ")"
        )
        flags.append(
            f"{what}, so the script cannot see the question or its options. No verdict against "
            f"{args.benchmark:g}% until the user confirms the question was Ellis's (\"How would you feel if you "
            "could no longer use ...?\") with his four options; then re-run with --ellis-wording."
        )
    if overall["small_base"]:
        flags.append(
            f"Base of {base} is below the suggested minimum of {args.min_base}: "
            "treat the score as a rough signal, not a measurement."
        )
    if counts["na"]:
        flags.append(
            f"{counts['na']} respondents ({100 * counts['na'] / answered:.1f}% of those who answered) no longer "
            "use the product. They are outside the base; check how the sample was drawn."
        )
    if blank:
        flags.append(f"{blank} rows had no answer to the question and were left out.")
    if question_rows:
        flags.append(
            f"{question_rows} rows repeat the column header or the question text (a second header row) and were "
            "skipped."
        )

    result = {
        "input": {
            "source": source,
            "rows": rows_read,
            "answer_column": columns["answer"],
            "segment_columns": columns["segments"],
            "benefit_column": columns["benefit"],
            "benefit_match_column": columns["benefit_match"],
            "period_column": columns["period"],
            "account_column": columns["account"],
            "id_column": columns["id"],
            "question_text_rows_skipped": question_rows,
        },
        "denominator_rule": (
            "Score = very disappointed / (very + somewhat + not disappointed). "
            '"N/A, I no longer use it" and blank answers are outside the base: the test is '
            "defined on current users, and Ellis and Vohra do not say how to treat N/A. "
            "The share with N/A kept in the base is shown beside it."
        ),
        "denominator_practice": DENOMINATOR_PRACTICE,
        "label_map_used": dict(sorted(label_map_used.items())),
        "counts": dict(counts, blank=blank),
        "confidence_pct": args.confidence,
        "interval_method": "Wilson score interval, no continuity correction",
        "benchmark_pct": args.benchmark,
        "benchmark_comparable": comparable,
        "wording": wording,
        "min_base": args.min_base,
        "score": overall,
        "pct_with_na_in_base": round(100 * counts["very"] / answered, 1),
        "verdict_text": verdict_text(overall, args.benchmark, args.confidence, wording),
        "flags": flags,
    }
    if scope:
        result["scope"] = scope

    if args.invited is not None:
        if args.invited < answered:
            raise InputError(
                f"--invited {args.invited} is smaller than the {answered} people who answered the question."
            )
        rate = 100 * answered / args.invited
        result["response_rate"] = {
            "invited": args.invited,
            "answered": answered,
            "pct": round(rate, 1),
            "low": rate < LOW_RESPONSE_RATE,
        }
        if rate < LOW_RESPONSE_RATE:
            flags.append(
                f"Response rate {rate:.1f}% is under {LOW_RESPONSE_RATE:g}%. The rate alone does not say which way "
                "the score is biased: compare the people who answered with those invited on activity or tenure, "
                "if those records exist, before trusting the score."
            )

    if columns["segments"]:
        tables = [
            {"column": column, "segments": segment_table(records, column, z, args, comparable)}
            for column in columns["segments"]
        ]
        result["segment_tables"] = tables
        scored = sum(1 for table in tables for seg in table["segments"] if seg["pct"] is not None)
        if scored > 1:
            note = MULTIPLE_COMPARISON_NOTE if comparable else MULTIPLE_COMPARISON_NOTE_NO_BENCHMARK
            result["multiple_comparison_note"] = note.format(n=scored, conf=args.confidence)
        if args.focus_segments:
            segments = tables[0]["segments"]
            wanted = list(dict.fromkeys(name.strip() for name in args.focus_segments.split(",") if name.strip()))
            if not wanted:
                raise InputError('--focus-segments is empty: name one or more segments, like "Founder,Manager".')
            known = {seg["segment"] for seg in segments}
            missing = [name for name in wanted if name not in known]
            if missing:
                raise InputError(
                    "--focus-segments names not found in column "
                    f'"{tables[0]["column"]}": {", ".join(missing)}. Found: {", ".join(sorted(known))}'
                )
            kept = [seg for seg in segments if seg["segment"] in wanted]
            focus = score_block(
                sum(seg["very"] for seg in kept), sum(seg["base"] for seg in kept),
                z, args.benchmark, args.min_base, comparable,
            )
            focus["segments"] = wanted
            if focus["pct"] is None:
                focus["direction"] = "no_base"
            else:
                diff = focus["very"] / focus["base"] - overall["very"] / overall["base"]
                focus["direction"] = "higher" if diff > 0 else "lower" if diff < 0 else "same"
            result["focus"] = focus

    if columns["benefit"]:
        result.update(benefit_tables(records, columns["benefit"], args.core_benefit))
    if columns["benefit_match"]:
        result["somewhat_split"] = match_split(records, columns["benefit_match"])
    if columns["account"]:
        result["accounts"] = account_block(records, columns["account"], z, args, comparable)
    if comparison:
        result["comparison"] = comparison
    elif args.previous_counts:
        earlier = parse_counts(args.previous_counts, "--previous-counts")
        result["comparison"] = comparison_block(
            "previous", {key: earlier[key] for key in CATEGORIES}, "current", counts, args, z, comparable
        )
    return result


def segment_table(records, segment_col, z, args, comparable=True):
    by_segment = {}
    for category, row in records:
        name = (row.get(segment_col) or "").strip() or BLANK_SEGMENT
        by_segment.setdefault(name, Counter())[category] += 1
    table = []
    for name, counted in by_segment.items():
        base = counted["very"] + counted["somewhat"] + counted["not"]
        block = score_block(counted["very"], base, z, args.benchmark, args.min_base, comparable)
        block.update(
            segment=name,
            somewhat=counted["somewhat"],
            **{"not": counted["not"]},
            na=counted["na"],
            share_of_very_pct=None,
        )
        table.append(block)
    total_very = sum(seg["very"] for seg in table)
    for seg in table:
        if total_very:
            seg["share_of_very_pct"] = round(100 * seg["very"] / total_very, 1)
    table.sort(key=lambda seg: (-(seg["pct"] if seg["pct"] is not None else -1), seg["segment"]))
    return table


def account_block(records, account_col, z, args, comparable):
    """One vote per account. The vote rule is this skill's convention (sources.md, "Several segment columns,
    accounts"). The 40% benchmark was set for users, so the account share is descriptive unless the user
    gives an account-level target with --account-benchmark."""
    by_account = {}
    no_id = Counter()
    for category, row in records:
        name = (row.get(account_col) or "").strip()
        if not name:
            no_id[category] += 1
            continue
        by_account.setdefault(name, Counter())[category] += 1
    very = base = outside = 0
    for counted in by_account.values():
        in_base = counted["very"] + counted["somewhat"] + counted["not"]
        if in_base == 0:
            outside += 1
            continue
        base += 1
        if 2 * counted["very"] > in_base:
            very += 1
    target = args.account_benchmark
    block = score_block(very, base, z, target if target is not None else args.benchmark, args.min_base, comparable)
    if base and target is None:
        block["verdict"] = "descriptive"
    block.update(
        accounts=len(by_account),
        accounts_outside_base=outside,
        respondents_without_account=sum(no_id.values()),
        account_benchmark_pct=target,
        vote_rule=(
            "One vote per account: an account counts as very disappointed when more than half of its "
            "current-user respondents answered very disappointed (a tie does not count). Accounts whose "
            "respondents all answered N/A are outside the base. Respondents with no account id are left out "
            "of the account score and counted. This rule is the skill's convention, not Ellis's or Vohra's."
        ),
    )
    return block


def period_comparison(records, period_col, id_col, args, z, comparable):
    names = [name.strip() for name in args.compare.split(",")]
    if len(names) != 2 or not all(names) or names[0] == names[1]:
        raise InputError('--compare expects two different period names: "EARLIER,LATER".')
    by_period = {}
    no_period = 0
    for category, row in records:
        name = (row.get(period_col) or "").strip()
        if not name:
            no_period += 1
            continue
        by_period.setdefault(name, []).append((category, row))
    missing = [name for name in names if name not in by_period]
    if missing:
        raise InputError(
            f'--compare period not found in column "{period_col}": {", ".join(missing)}. '
            f"Found: {', '.join(sorted(by_period)) or 'none'}"
        )
    block = comparison_block(
        names[0], tally(by_period[names[0]]), names[1], tally(by_period[names[1]]), args, z, comparable
    )
    block["rows_without_period"] = no_period
    block["other_periods"] = sorted(name for name in by_period if name not in names)
    if id_col:
        ids = [{(row.get(id_col) or "").strip() for _, row in by_period[name]} - {""} for name in names]
        shared = len(ids[0] & ids[1])
        block["respondents_in_both"] = shared
        if shared:
            block["verdict"] = "not_independent"
            block["verdict_text"] = (
                f"Not compared: {shared} respondent ids answered in both waves. The interval assumes different "
                "people in each wave (Superhuman never surveyed anyone twice); keep one answer per person, or "
                "treat the later wave as a new baseline."
            )
    return block, by_period


def comparison_block(earlier_name, earlier, later_name, later, args, z, comparable):
    n1, n2 = base_of(earlier), base_of(later)
    for name, n in ((earlier_name, n1), (later_name, n2)):
        if n == 0:
            raise InputError(f'Cannot compare: "{name}" has no current-user answers.')
    d, low, high = newcombe_diff(earlier["very"], n1, later["very"], n2, z)
    if low > 0:
        verdict = "increased"
    elif high < 0:
        verdict = "decreased"
    else:
        verdict = "cannot_tell"
    span = f"{100 * low:+.1f} to {100 * high:+.1f} points"
    if verdict == "cannot_tell":
        text = (
            f"Cannot tell: the score moved {100 * d:+.1f} points, but the {args.confidence:g}% interval for the "
            f"change ({span}) includes 0, so these two samples do not show a change."
        )
    else:
        text = (
            f"{verdict.capitalize()}: {100 * d:+.1f} points, and the whole {args.confidence:g}% interval for the "
            f"change ({span}) is on one side of 0."
        )
    return {
        "earlier": dict(score_block(earlier["very"], n1, z, args.benchmark, args.min_base, comparable), period=earlier_name),
        "later": dict(score_block(later["very"], n2, z, args.benchmark, args.min_base, comparable), period=later_name),
        "change_points": round(100 * d, 1),
        "ci_low_points": round(100 * low, 1),
        "ci_high_points": round(100 * high, 1),
        "method": "Newcombe (1998) hybrid score interval for two independent proportions",
        "verdict": verdict,
        "verdict_text": text,
        "rule": COMPARE_RULE,
    }


def benefit_tables(records, benefit_col, core_benefit):
    display = {}

    def benefit_of(row):
        """Benefit codes are compared after normalizing; the first spelling seen is the one shown."""
        raw = (row.get(benefit_col) or "").strip()
        key = normalize(raw)
        if key:
            display.setdefault(key, raw)
        return key

    coded = [(category, benefit_of(row)) for category, row in records]
    very = Counter(key for category, key in coded if category == "very")
    very_blank = very.pop("", 0)
    ranked = sorted(very.items(), key=lambda item: (-item[1], display[item[0]]))
    if core_benefit:
        core = normalize(core_benefit)
        if core not in display:
            raise InputError(
                f'--core-benefit "{core_benefit.strip()}" does not appear in column "{benefit_col}". '
                f"Values found: {', '.join(sorted(display.values()))}"
            )
        how = "given with --core-benefit"
    else:
        if not ranked:
            raise InputError(
                f'Column "{benefit_col}" is empty for every very-disappointed respondent, so there '
                "is no core benefit to match against. Code the open answers first or pass --core-benefit."
            )
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            tied = [display[key] for key, count in ranked if count == ranked[0][1]]
            raise InputError(
                "Tie for the most common benefit among very-disappointed respondents ("
                + ", ".join(tied)
                + "). Pass --core-benefit to choose one."
            )
        core = ranked[0][0]
        how = "most common benefit among very-disappointed respondents"
    match = no_match = unknown = 0
    held_back = Counter()
    for category, key in coded:
        if category != "somewhat":
            continue
        if not key:
            unknown += 1
        elif key == core:
            match += 1
        else:
            no_match += 1
            held_back[key] += 1
    return {
        "benefits_among_very": {
            "counts": [{"benefit": display[key], "n": count} for key, count in ranked],
            "blank": very_blank,
        },
        "core_benefit": {"value": display[core], "chosen": how},
        "somewhat_split": {
            "somewhat": match + no_match + unknown,
            "benefit_matches": match,
            "benefit_differs": no_match,
            "benefit_unknown": unknown,
            "other_benefits": [
                {"benefit": display[key], "n": count}
                for key, count in sorted(held_back.items(), key=lambda item: (-item[1], display[item[0]]))
            ],
        },
    }


def match_split(records, match_col):
    match = no_match = unknown = 0
    bad = Counter()
    for category, row in records:
        if category != "somewhat":
            continue  # only the somewhat-disappointed rows are read, so other rows may hold anything
        raw = (row.get(match_col) or "").strip()
        norm = raw.lower()
        if raw and norm not in YES and norm not in NO:
            bad[raw] += 1
            continue
        if not raw:
            unknown += 1
        elif norm in YES:
            match += 1
        elif norm in NO:
            no_match += 1
    if bad:
        listing = "; ".join(f'"{label}" ({count})' for label, count in sorted(bad.items()))
        raise InputError(
            f'Column "{match_col}" must hold yes/no (or true/false, 1/0) on somewhat-disappointed rows. Found: {listing}.'
        )
    return {
        "somewhat": match + no_match + unknown,
        "benefit_matches": match,
        "benefit_differs": no_match,
        "benefit_unknown": unknown,
    }


def verdict_text(score, benchmark, confidence, wording="ellis"):
    span = f"{score['ci_low_pct']:.1f}% to {score['ci_high_pct']:.1f}%"
    b = f"{benchmark:g}%"
    if score["verdict"] == "not_comparable" and wording == "unconfirmed":
        return (
            f"Not compared with the {b} benchmark yet: the question and its options are not confirmed as "
            f"Ellis's (pass --ellis-wording once they are). {confidence:g}% interval: {span}."
        )
    if score["verdict"] == "not_comparable":
        return (
            f"Not compared with the {b} benchmark: the answer wording is not Ellis's. "
            f"The score and its {confidence:g}% interval ({span}) are a baseline for your own later waves."
        )
    if score["verdict"] == "above":
        return (
            f"Above the {b} benchmark: the whole {confidence:g}% interval ({span}) is over {b}."
        )
    if score["verdict"] == "below":
        return (
            f"Below the {b} benchmark: the whole {confidence:g}% interval ({span}) is under {b}."
        )
    side = "at or above" if score["pct"] >= benchmark else "below"
    return (
        f"Cannot tell: the observed {score['pct']:.1f}% is {side} {b}, but the {confidence:g}% "
        f"interval ({span}) includes {b}, so this sample cannot place the true share on either side."
    )


VERDICT_SHORT = {
    "above": "above",
    "below": "below",
    "cannot_tell": "cannot tell",
    "no_base": "no base",
    "not_comparable": "not compared",
    "descriptive": "no target",
}


def one_line(block, confidence):
    return (
        f"{block['pct']:.1f}%  ({block['very']} of {block['base']})  {confidence:g}% interval "
        f"{block['ci_low_pct']:.1f}% to {block['ci_high_pct']:.1f}%"
    )


def render(result):
    score = result["score"]
    counts = result["counts"]
    conf = result["confidence_pct"]
    out = []
    out.append("PMF survey score (Sean Ellis test)")
    out.append("")
    out.append(
        f"Very disappointed: {score['pct']:.1f}%  ({score['very']} of {score['base']})   "
        f"{conf:g}% interval {score['ci_low_pct']:.1f}% to {score['ci_high_pct']:.1f}% (Wilson)"
    )
    out.append(result["verdict_text"])
    if "scope" in result:
        pooled = result["scope"]["pooled"]
        out.append(result["scope"]["note"])
        out.append(f"  All waves pooled (for reference, not a wave result): {one_line(pooled, conf)}")
    out.append("")
    if result["input"]["rows"] is None:
        out.append("Input: counts given with --counts")
    else:
        out.append(f"Answer column: {result['input']['answer_column']}   Rows read: {result['input']['rows']}")
    for category in CATEGORIES:
        out.append(f"  {CATEGORY_LABELS[category]:<26}{counts[category]:>6}")
    out.append(f"  {'Blank':<26}{counts['blank']:>6}")
    out.append("")
    out.append("Denominator: " + result["denominator_rule"])
    out.append(f"With N/A kept in the base: {result['pct_with_na_in_base']:.1f}%")
    out.append(result["denominator_practice"])
    if "response_rate" in result:
        rate = result["response_rate"]
        out.append("")
        out.append(f"Response rate: {rate['pct']:.1f}%  ({rate['answered']} answered of {rate['invited']} invited)")
    if result["flags"]:
        out.append("")
        out.append("Flags:")
        out.extend(f"  - {flag}" for flag in result["flags"])
    for table in result.get("segment_tables", []):
        out.append("")
        out.append(f"Segments by {table['column']} (small base = under {result['min_base']})")
        header = f"  {'Segment':<24}{'Base':>6}{'Very':>6}{'% very':>9}  {'Interval':<17}{'vs ' + format(result['benchmark_pct'], 'g') + '%':<13}{'Share of very':>14}  Flag"
        out.append(header)
        for seg in table["segments"]:
            if seg["pct"] is None:
                pct, span = "-", "-"
            else:
                pct = f"{seg['pct']:.1f}%"
                span = f"{seg['ci_low_pct']:.1f}%-{seg['ci_high_pct']:.1f}%"
            share = "-" if seg["share_of_very_pct"] is None else f"{seg['share_of_very_pct']:.1f}%"
            flag = "small base" if seg["small_base"] else ""
            out.append(
                f"  {seg['segment'][:23]:<24}{seg['base']:>6}{seg['very']:>6}{pct:>9}  {span:<17}"
                f"{VERDICT_SHORT[seg['verdict']]:<13}{share:>14}  {flag}"
            )
    if "multiple_comparison_note" in result:
        out.append("")
        out.append("Caution: " + result["multiple_comparison_note"])
    if "focus" in result:
        focus = result["focus"]
        out.append("")
        if focus["pct"] is None:
            out.append(
                f"Focus segments ({', '.join(focus['segments'])}): no current-user answers (all N/A or blank), "
                "so no score."
            )
        else:
            out.append(
                f"Focus segments ({', '.join(focus['segments'])}): {one_line(focus, conf)}  "
                f"[{VERDICT_SHORT[focus['verdict']]}]" + ("  small base" if focus["small_base"] else "")
            )
            out.append(
                f"  {focus['direction'].capitalize()} than the overall {score['pct']:.1f}%. If these segments were "
                "picked after seeing their scores, the choice itself pushes the focus score up; confirm it on "
                "the next wave."
            )
    if "accounts" in result:
        acc = result["accounts"]
        out.append("")
        out.append(
            f"Accounts: {acc['accounts']} accounts behind {score['base'] + counts['na'] - acc['respondents_without_account']} respondents "
            f"(accounts outside the base: {acc['accounts_outside_base']}; respondents with no account id: {acc['respondents_without_account']})"
        )
        if acc["pct"] is None:
            out.append("One vote per account: no account with a current-user answer.")
        else:
            target = (
                f"against the account target {acc['account_benchmark_pct']:g}%"
                if acc["account_benchmark_pct"] is not None
                else f"descriptive: the {result['benchmark_pct']:g}% benchmark is for users, not accounts"
            )
            out.append(
                f"One vote per account: {one_line(acc, conf)}  [{VERDICT_SHORT[acc['verdict']]}; {target}]"
                + ("  small base" if acc["small_base"] else "")
            )
        out.append("  " + acc["vote_rule"])
    if "comparison" in result:
        cmp_ = result["comparison"]
        out.append("")
        out.append("Change between waves")
        for key in ("earlier", "later"):
            block = cmp_[key]
            out.append(
                f"  {block['period'][:20]:<22}{one_line(block, conf)}" + ("  small base" if block["small_base"] else "")
            )
        out.append("  " + cmp_["verdict_text"])
        out.append(f"  Method: {cmp_['method']}.")
        out.append("  " + cmp_["rule"])
        if cmp_.get("rows_without_period"):
            out.append(f"  {cmp_['rows_without_period']} answers had no period and are not in either wave.")
        if cmp_.get("other_periods"):
            out.append(f"  Periods not compared: {', '.join(cmp_['other_periods'])}")
    if "benefits_among_very" in result:
        out.append("")
        out.append("Main benefit among very-disappointed respondents")
        for item in result["benefits_among_very"]["counts"]:
            out.append(f"  {item['benefit'][:40]:<42}{item['n']:>5}")
        if result["benefits_among_very"]["blank"]:
            out.append(f"  {'(blank)':<42}{result['benefits_among_very']['blank']:>5}")
        out.append(
            f"Core benefit: {result['core_benefit']['value']} ({result['core_benefit']['chosen']})"
        )
    if "somewhat_split" in result:
        split = result["somewhat_split"]
        out.append("")
        out.append(f"Somewhat disappointed: {split['somewhat']}")
        out.append(f"  Main benefit matches the core benefit    {split['benefit_matches']:>5}   read their improvement answers first")
        out.append(f"  Main benefit differs                     {split['benefit_differs']:>5}")
        out.append(f"  Benefit not recorded                     {split['benefit_unknown']:>5}")
        for item in split.get("other_benefits", []):
            out.append(f"    differs: {item['benefit'][:36]:<38}{item['n']:>5}")
    return "\n".join(out)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Score and segment a Sean Ellis PMF survey (the 'very disappointed' test) from a CSV or from counts.",
    )
    parser.add_argument("input", nargs="?", help="CSV file, one row per respondent, with a header row")
    parser.add_argument("--counts", metavar="very=N,somewhat=N,not=N[,na=N][,blank=N]", help="score totals directly, without a CSV")
    parser.add_argument("--answer-col", help="column with the disappointment answer (default: the one column whose header contains 'disappoint', 'no longer use' or 'pmf')")
    parser.add_argument("--segment-col", action="append", help="persona or segment column; repeat for several")
    parser.add_argument("--focus-segments", help="comma-separated segment names to re-score together (needs one --segment-col)")
    parser.add_argument("--benefit-col", help="column with each respondent's coded main benefit")
    parser.add_argument("--core-benefit", help="the core benefit to match against (default: the most common among very-disappointed respondents)")
    parser.add_argument("--benefit-match-col", help="yes/no column: does this respondent's main benefit match the core benefit")
    parser.add_argument("--period-col", help="wave or period column; needs --compare")
    parser.add_argument("--compare", metavar="EARLIER,LATER", help="the two period values to compare, earlier first")
    parser.add_argument("--previous-counts", metavar="very=N,somewhat=N,not=N", help="an earlier wave as counts, compared with this input")
    parser.add_argument("--account-col", help="account or company id column (B2B): also score one vote per account")
    parser.add_argument("--account-benchmark", type=float, help="an account-level target in percent, from the user (default: none, the account share is descriptive)")
    parser.add_argument("--id-col", help="respondent id column: with --period-col, finds people who answered in both waves")
    parser.add_argument("--ellis-wording", action="store_true", help="the user confirmed the question and its four options were Ellis's; needed for a benchmark verdict with --counts or hand-mapped labels")
    parser.add_argument("--invited", type=int, help="number of people invited, to report the response rate")
    parser.add_argument("--map", action="append", metavar="LABEL=CATEGORY", help="map an answer label to very, somewhat, not or na; repeat as needed")
    parser.add_argument("--benchmark", type=float, default=DEFAULT_BENCHMARK, help="benchmark in percent (default 40)")
    parser.add_argument("--confidence", type=float, default=95.0, help="confidence level, 95 or 0.95 (default 95)")
    parser.add_argument("--min-base", type=int, default=DEFAULT_MIN_BASE, help="bases under this are flagged as small (default 30)")
    parser.add_argument("--delimiter", help="CSV delimiter, one character (default: comma; a header with no comma but semicolons, tabs or pipes is read with that delimiter)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    names = {"comma": ",", "semicolon": ";", "tab": "\t", "\\t": "\t", "pipe": "|"}
    if args.delimiter is not None:
        args.delimiter = names.get(args.delimiter.lower(), args.delimiter)
    if args.delimiter is not None and len(args.delimiter) != 1:
        print("pmf-survey: --delimiter must be one character", file=sys.stderr)
        return 2
    try:
        result = analyse(args)
    except InputError as exc:
        print(f"pmf-survey: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
