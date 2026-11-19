#!/usr/bin/env python3
"""NPS analysis: Net Promoter Score with a confidence interval, comparisons between segments, periods and a
benchmark, a mix-shift decomposition, and comments split by promoter, passive and detractor.

Standard library only, Python 3.9+. No network. Formulas and thresholds: references/sources.md.

Usage:
  python3 scripts/nps_analysis.py responses.csv
  python3 scripts/nps_analysis.py --counts 61,30,16 --benchmark 30 --tail above
  python3 scripts/nps_analysis.py responses.csv --segment-col plan --pairwise --adjust holm
  python3 scripts/nps_analysis.py responses.csv --segment-col plan --period-col quarter --compare-periods 2026-Q2 2026-Q3
  python3 scripts/nps_analysis.py responses.csv --comment-col comment --comments-out comments.csv --json

Input is one of: a CSV with one row per respondent; a CSV of counts (columns promoters, passives, detractors,
optionally a segment and a period column); or --counts P,A,D (or eleven counts for the scores 0 to 10).

Exit codes: 0 success, 2 bad input or a refused calculation (the message says what to fix).
"""
import argparse
import csv
import datetime
import io
import itertools
import json
import math
import os
import re
import sys
from statistics import NormalDist

# Category boundaries per scale. 0-10 is the Net Promoter standard (Reichheld 2003). The 1-10 and 1-5
# mappings are the ones tested by Sauro (2017); they are non-standard and only used on request.
SCALES = {
    "0-10": {"min": 0, "max": 10, "promoter_min": 9, "detractor_max": 6},
    "1-10": {"min": 1, "max": 10, "promoter_min": 9, "detractor_max": 6},
    "1-5": {"min": 1, "max": 5, "promoter_min": 5, "detractor_max": 3},
}
# Adjusted Wald AW(3, T) (Rocks 2016): add 3/4 to promoters and to detractors, 3/2 to passives, so 3 to n.
AW_ADD_EXTREME = 0.75
AW_ADD_N = 3.0
DEFAULT_MIN_BASE = 100  # Pew Research Center reporting rule, see references/sources.md
TARGET_MARGIN = 0.10  # 10 points: the margin Pew's rule is built on, used for the "n needed" hint
NO_ZERO_STOP_N = 200  # convention of this skill, see references/sources.md "Scale checks"
# Rocks (2016) Table 1 evaluates interval coverage from n = 5 up. Below that no verdict is given.
MIN_N_FOR_TEST = 5
# Convention of this skill (references/sources.md "Scale checks"): stop when more than 5% of the non-blank
# answers are not scores, because a whole answer category is probably being dropped.
NON_NUMERIC_STOP_SHARE = 0.05
# An answer exported with its scale label, such as "10 - Extremely likely" or "0 = Not at all likely".
LABELLED_SCORE_RE = re.compile(r"^\s*(\d{1,2})\s*(?:[-\u2013\u2014:=(]\s*)?[^\W\d_]")
# Common ways of writing "no answer". They are excluded and counted like any non-numeric value but do not
# trigger the NON_NUMERIC_STOP_SHARE stop, which is meant for scores the script failed to read.
NON_ANSWER_RE = re.compile(
    r"^(n/?a|na|none|-+|\.|\?|don'?t know|do not know|dk|not applicable|prefer not to (say|answer)|refused|"
    r"skipped|no answer|no opinion)$",
    re.I,
)
# Qualtrics adds <question>_NPS_GROUP: the computed category, not the 0-10 answer.
NPS_GROUP_RE = re.compile(r"nps[ _-]?group", re.I)
SCORE_NAME_RE = re.compile(r"nps|recommend|ltr|likelihood|score|rating", re.I)
STRONG_SCORE_NAME_RE = re.compile(r"nps|recommend|ltr", re.I)
COUNT_COLUMNS = {
    "promoter": re.compile(r"^promoters?$", re.I),
    "passive": re.compile(r"^(passives?|neutrals?)$", re.I),
    "detractor": re.compile(r"^detractors?$", re.I),
}
GROUPS = ("promoter", "passive", "detractor")
RECODE = {"promoter": 100, "passive": 0, "detractor": -100}
BLANK_LABEL = "(blank)"
DELIMITER_NAMES = {"comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|", "\\t": "\t"}
# Period labels the script can put in time order without being told (anything else needs --period-order).
PERIOD_PATTERNS = (
    (re.compile(r"^(\d{4})-(\d{2})-(\d{2})$"), lambda m: (int(m[1]), int(m[2]), int(m[3]))),
    (re.compile(r"^(\d{4})-(\d{2})$"), lambda m: (int(m[1]), int(m[2]), 0)),
    (re.compile(r"^(\d{4})[ -]?Q([1-4])$", re.I), lambda m: (int(m[1]), 3 * int(m[2]) - 2, 0)),
    (re.compile(r"^Q([1-4])[ -]?(\d{4})$", re.I), lambda m: (int(m[2]), 3 * int(m[1]) - 2, 0)),
    (re.compile(r"^(\d{4})$"), lambda m: (int(m[1]), 0, 0)),
)
MAX_EXAMPLES = 5


class InputError(Exception):
    """Bad input or a calculation the script refuses to do."""


# ---------------------------------------------------------------- statistics

def z_for(confidence):
    return NormalDist().inv_cdf(1 - (1 - confidence) / 2)


def _beta_cf(a, b, x):
    """Continued fraction for the incomplete beta function (modified Lentz method)."""
    tiny = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1.0)
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        for numerator in (
            m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m)),
            -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1)),
        ):
            d = 1.0 + numerator * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + numerator / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1.0) < 1e-14:
            break
    return h


def regularized_beta(a, b, x):
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    log_front = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(log_front) * _beta_cf(a, b, x) / a
    return 1.0 - math.exp(log_front) * _beta_cf(b, a, 1 - x) / b


def t_two_sided_p(t_stat, df):
    """P(|T| >= |t|) for Student's t with df degrees of freedom: I_x(df/2, 1/2) at x = df/(df + t^2)."""
    return regularized_beta(df / 2.0, 0.5, df / (df + t_stat * t_stat))


def t_critical(confidence, df):
    """Two-sided critical value, found by bisection on the p-value."""
    low, high = 0.0, 1e6
    for _ in range(200):
        mid = (low + high) / 2
        if t_two_sided_p(mid, df) > 1 - confidence:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def moments(n, promoters, detractors, method):
    """Return (nps, variance, n_used) as proportions; adjusted per AW(3, T) unless method is 'wald'."""
    if method == "adjusted-wald":
        n_used = n + AW_ADD_N
        p_pro = (promoters + AW_ADD_EXTREME) / n_used
        p_det = (detractors + AW_ADD_EXTREME) / n_used
    else:
        n_used = float(n)
        p_pro = promoters / n_used
        p_det = detractors / n_used
    nps = p_pro - p_det
    return nps, max(p_pro + p_det - nps * nps, 0.0), n_used


def summarize(label, counts, method, z, min_base):
    n = sum(counts[g] for g in GROUPS)
    out = {
        "label": label,
        "n": n,
        "promoters": counts["promoter"],
        "passives": counts["passive"],
        "detractors": counts["detractor"],
    }
    if n == 0:
        out.update(
            {"nps": None, "ci_low": None, "ci_high": None, "se": None, "small_base": True, "note": "no valid scores"}
        )
        return out
    center, variance, n_used = moments(n, counts["promoter"], counts["detractor"], method)
    se = math.sqrt(variance / n_used)
    out.update(
        {
            "pct_promoters": round(100 * counts["promoter"] / n, 4),
            "pct_passives": round(100 * counts["passive"] / n, 4),
            "pct_detractors": round(100 * counts["detractor"] / n, 4),
            "nps": round(100 * (counts["promoter"] - counts["detractor"]) / n, 4),
            "ci_low": round(max(-100.0, 100 * (center - z * se)), 4),
            "ci_high": round(min(100.0, 100 * (center + z * se)), 4),
            "se": round(100 * se, 4),
            "small_base": n < min_base,
        }
    )
    # Everyone in one end category: a population at that end (+100 or -100) gives this sample with
    # certainty, so no level of confidence can exclude it. Extend the limit to the end (as the exact
    # Clopper-Pearson limit for a proportion with x = n is 1). See references/sources.md "Intervals".
    if counts["promoter"] == n:
        out["ci_high"] = 100.0
    if counts["detractor"] == n:
        out["ci_low"] = -100.0
    if method == "adjusted-wald":
        out["nps_adjusted"] = round(100 * center, 4)
    if n < MIN_N_FOR_TEST:
        out["note"] = (
            f"fewer than {MIN_N_FOR_TEST} responses: the interval's coverage was not evaluated below n = 5 "
            "(Rocks 2016, Table 1); treat it as a rough indication and draw no verdict from it"
        )
    elif variance == 0:
        out["note"] = (
            "variance is 0 (everyone in one category): the Wald interval has zero width and says nothing about "
            "precision; use --interval adjusted-wald"
        )
    if out["small_base"] and z * se > TARGET_MARGIN:
        # n = z^2 * Var / e^2, minus the 3 the adjustment adds (rearranged interval formula).
        needed = z * z * variance / TARGET_MARGIN**2 - (AW_ADD_N if method == "adjusted-wald" else 0)
        out["n_for_10_point_margin"] = max(n + 1, math.ceil(needed))
    return out


INCONCLUSIVE = "inconclusive, small base"
REVERSED_NOTE = (
    "the adjustment, not the data, gives this result: the observed difference is {observed} points but the "
    "adjusted one used by the test is {adjusted} (adding 3 responses moves a small group's score a long "
    "way), so no verdict; show both scores with their intervals (references/sources.md)"
)


def adjustment_reverses(observed, adjusted):
    """True when the adjusted-Wald difference points the other way from the observed one, or the observed one is 0.

    A test that comes out significant only because of the pseudo-counts says nothing about the data."""
    return observed == 0 or (observed > 0) != (adjusted > 0)


def set_verdict(result, alpha):
    """Verdict from the unrounded p-value. P-values are never rounded before a decision; only the text
    output rounds them (fmt_p), and the JSON carries them in full."""
    p_value = result.get("p_adjusted", result["p_value"])
    result["significant"] = p_value < alpha
    if result["significant"]:
        result["verdict"] = "significant"
    elif result.get("small_base"):
        result["verdict"] = INCONCLUSIVE
    else:
        result["verdict"] = "not significant"


def fmt_p(p_value, alpha):
    """Four decimals, or more when four would print a value equal to alpha that is not alpha."""
    text = f"{p_value:.4f}"
    if float(text) == round(alpha, 4) and p_value != alpha:
        text = f"{p_value:.8f}"
    return text


def compare(kind, a, b, method, test, confidence, min_base):
    """Test the difference of two independent NPS values (a minus b)."""
    out = {"kind": kind, "a": a["label"], "b": b["label"], "n_a": a["n"], "n_b": b["n"], "test": test}
    if a["n"] == 0 or b["n"] == 0:
        out.update({"tested": False, "note": "one side has no valid scores"})
        return out
    out["difference"] = round(a["nps"] - b["nps"], 4)
    out["small_base"] = a["n"] < min_base or b["n"] < min_base
    if min(a["n"], b["n"]) < MIN_N_FOR_TEST:
        out.update(
            {
                "tested": False,
                "note": f"fewer than {MIN_N_FOR_TEST} responses on one side: the test was not evaluated below "
                "n = 5 (Rocks 2016, Table 1), so no verdict; show both scores with their intervals",
            }
        )
        return out
    if test == "welch":
        if a["n"] < 2 or b["n"] < 2:
            out.update({"tested": False, "note": "the Welch t-test needs at least 2 responses on each side"})
            return out
        parts = []
        for g in (a, b):
            mean, variance, _ = moments(g["n"], g["promoters"], g["detractors"], "wald")
            parts.append((mean, variance * g["n"] / (g["n"] - 1) / g["n"], g["n"]))  # s^2 / n, s^2 with n - 1
        diff = parts[0][0] - parts[1][0]
        se = math.sqrt(parts[0][1] + parts[1][1])
        if se == 0:
            out.update({"tested": False, "note": "variance is 0 in both groups: the test is undefined"})
            return out
        df = se**4 / sum(v * v / (n - 1) for _, v, n in parts)
        stat = abs(diff) / se
        p_value = t_two_sided_p(stat, df)
        critical = t_critical(confidence, df)
        out.update({"t": round(stat, 4), "df": round(df, 2)})
    else:
        nps_a, var_a, n_a = moments(a["n"], a["promoters"], a["detractors"], method)
        nps_b, var_b, n_b = moments(b["n"], b["promoters"], b["detractors"], method)
        diff = nps_a - nps_b
        se = math.sqrt(var_a / n_a + var_b / n_b)
        if method == "adjusted-wald":
            out["difference_adjusted"] = round(100 * diff, 4)
        if se == 0:
            out.update({"tested": False, "note": "variance is 0 in both groups: the z-test is undefined"})
            return out
        stat = abs(diff) / se
        p_value = 2 * (1 - NormalDist().cdf(stat))
        critical = z_for(confidence)
        out["z"] = round(stat, 4)
        observed = a["nps"] - b["nps"]
        if method == "adjusted-wald" and p_value < 1 - confidence and adjustment_reverses(observed, diff):
            out.update(
                {"tested": False, "note": REVERSED_NOTE.format(observed=fmt(observed), adjusted=fmt(100 * diff))}
            )
            return out
        if method == "wald" and (var_a == 0 or var_b == 0):
            out["note"] = (
                "variance is 0 in one group (everyone in one category): the Wald test treats that score as exact, "
                "so the verdict overstates the certainty; use --interval adjusted-wald"
            )
    out.update(
        {
            "tested": True,
            "se_difference": round(100 * se, 4),
            "p_value": p_value,
            "ci_low": round(max(-200.0, 100 * (diff - critical * se)), 4),
            "ci_high": round(min(200.0, 100 * (diff + critical * se)), 4),
        }
    )
    set_verdict(out, 1 - confidence)
    return out


def adjust_p_values(comparisons, method, alpha):
    """Bonferroni or Holm (1979) adjusted p-values across the tested comparisons, in place."""
    tested = [c for c in comparisons if c.get("tested")]
    m = len(tested)
    if method == "none" or m == 0:
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
        set_verdict(c, alpha)


HYPOTHESES = {
    "two": "the score differs from the benchmark",
    "above": "the score is above the benchmark",
    "below": "the score is below the benchmark",
}


def benchmark_test(group, benchmark, tail, method, confidence):
    """One-sample z-test of the score against a fixed benchmark (Lewis and Sauro 2021d).

    tail: two, above or below. A benchmark of exactly +100 or -100 is tested exactly: only a sample made
    entirely of promoters (or detractors) is possible under it, so p is 1 or 0 (references/sources.md).
    """
    n = group["n"]
    out = {"benchmark": benchmark, "tail": tail, "n": n, "nps": group["nps"], "hypothesis": HYPOTHESES[tail]}
    center, variance, n_used = moments(n, group["promoters"], group["detractors"], method)
    se = math.sqrt(variance / n_used)
    out["difference"] = round(group["nps"] - benchmark, 4)  # observed score minus the benchmark
    out["se"] = round(100 * se, 4)
    if method == "adjusted-wald":
        out["nps_adjusted"] = round(100 * center, 4)
        out["difference_adjusted"] = round(100 * center - benchmark, 4)  # what the z-test uses
    alpha = 1 - confidence
    if abs(benchmark) == 100:
        end = "promoter" if benchmark == 100 else "detractor"
        possible = group[end + "s"] == n  # the only sample a population at the end can produce
        # A score cannot lie beyond +100 or -100, so "above +100" and "below -100" can never be shown.
        beyond = (tail == "above" and benchmark == 100) or (tail == "below" and benchmark == -100)
        p_value = 1.0 if (possible or beyond) else 0.0
        out.update({"tested": True, "exact": True, "p_value": p_value, "significant": p_value < alpha})
        out["note"] = (
            f"exact test at the end of the scale: a population at {benchmark:+g} would give only "
            f"{end}s, and this sample {'has only' if possible else 'does not have only'} {end}s"
        )
        return out
    if n < MIN_N_FOR_TEST:
        out.update(
            {
                "tested": False,
                "note": f"fewer than {MIN_N_FOR_TEST} responses: the z-test was not evaluated below n = 5 "
                "(Rocks 2016, Table 1), so no verdict",
            }
        )
        return out
    if se == 0:
        out.update({"tested": False, "note": "variance is 0: the test is undefined; use --interval adjusted-wald"})
        return out
    z_stat = (center - benchmark / 100) / se
    upper = 1 - NormalDist().cdf(z_stat)
    p_value = {"above": upper, "below": 1 - upper, "two": 2 * min(upper, 1 - upper)}[tail]
    observed = group["nps"] - benchmark
    if method == "adjusted-wald" and p_value < alpha and adjustment_reverses(observed, z_stat):
        adjusted = fmt(100 * center - benchmark)
        out.update({"tested": False, "note": REVERSED_NOTE.format(observed=fmt(observed), adjusted=adjusted)})
        return out
    out.update({"tested": True, "z": round(z_stat, 4), "p_value": p_value, "significant": p_value < alpha})
    one_sided_z = NormalDist().inv_cdf(confidence)
    if tail == "above":
        out["lower_bound"] = round(max(-100.0, 100 * (center - one_sided_z * se)), 4)
    elif tail == "below":
        out["upper_bound"] = round(min(100.0, 100 * (center + one_sided_z * se)), 4)
    return out


def mix_shift(cells, earlier, later):
    """Split the change in the pooled score between two periods into a within-segment part and a mix part.

    Kitagawa (1955): change = sum(mean share * change in segment NPS) + sum(mean segment NPS * change in share).
    """
    table = {}
    totals = {earlier: 0, later: 0}
    for cell in cells:
        if cell["period"] not in totals:
            continue
        n = sum(cell[g] for g in GROUPS)
        entry = table.setdefault(cell["segment"], {earlier: [0, 0], later: [0, 0]})
        entry[cell["period"]][0] += n
        entry[cell["period"]][1] += cell["promoter"] - cell["detractor"]
        totals[cell["period"]] += n
    if not totals[earlier] or not totals[later]:
        return None
    rows, within_total, mix_total = [], 0.0, 0.0
    for name in sorted(table):
        (n0, net0), (n1, net1) = table[name][earlier], table[name][later]
        if n0 + n1 == 0:
            continue
        share0, share1 = n0 / totals[earlier], n1 / totals[later]
        # A segment present in one period only has no change of its own: all of its effect is mix.
        nps0 = 100 * net0 / n0 if n0 else 100 * net1 / n1
        nps1 = 100 * net1 / n1 if n1 else nps0
        within = (share0 + share1) / 2 * (nps1 - nps0)
        mix = (nps0 + nps1) / 2 * (share1 - share0)
        within_total += within
        mix_total += mix
        rows.append(
            {
                "segment": name,
                "n_earlier": n0,
                "n_later": n1,
                "share_earlier": round(100 * share0, 4),
                "share_later": round(100 * share1, 4),
                "nps_earlier": round(nps0, 4) if n0 else None,
                "nps_later": round(nps1, 4) if n1 else None,
                "within": round(within, 4),
                "mix": round(mix, 4),
            }
        )
    return {
        "earlier": earlier,
        "later": later,
        "change": round(within_total + mix_total, 4),
        "within_segments": round(within_total, 4),
        "mix": round(mix_total, 4),
        "segments": rows,
    }


def paired_change(records, earlier, later, confidence):
    """Per-respondent change in the -100/0/+100 recode for ids answered in both periods (paired t)."""
    seen = {earlier: {}, later: {}}
    duplicates = set()
    for record in records:
        if record["period"] in seen and record["id"]:
            if record["id"] in seen[record["period"]]:
                duplicates.add(record["id"])
            seen[record["period"]][record["id"]] = RECODE[record["group"]]
    both = sorted(i for i in seen[earlier] if i in seen[later] and i not in duplicates)
    changes = [seen[later][i] - seen[earlier][i] for i in both]
    out = {
        "earlier": earlier,
        "later": later,
        "n_pairs": len(changes),
        "only_earlier": sum(1 for i in seen[earlier] if i not in seen[later]),
        "only_later": sum(1 for i in seen[later] if i not in seen[earlier]),
        "ids_with_duplicates_excluded": len(duplicates),
        "moved_up": sum(1 for c in changes if c > 0),
        "unchanged": sum(1 for c in changes if c == 0),
        "moved_down": sum(1 for c in changes if c < 0),
    }
    if len(changes) < 2:
        out.update({"tested": False, "note": "fewer than 2 respondents answered in both periods"})
        return out
    mean = sum(changes) / len(changes)
    sd = math.sqrt(sum((c - mean) ** 2 for c in changes) / (len(changes) - 1))
    out.update({"mean_change": round(mean, 4), "sd": round(sd, 4)})
    if sd == 0:
        out.update({"tested": False, "note": "every respondent changed by the same amount: no test"})
        return out
    se, df = sd / math.sqrt(len(changes)), len(changes) - 1
    critical = t_critical(confidence, df)
    p_value = t_two_sided_p(mean / se, df)
    out.update(
        {
            "tested": True,
            "se": round(se, 4),
            "t": round(abs(mean) / se, 4),
            "df": df,
            "p_value": p_value,
            "ci_low": round(mean - critical * se, 4),
            "ci_high": round(mean + critical * se, 4),
            "significant": p_value < 1 - confidence,
        }
    )
    return out


# ---------------------------------------------------------------- input

def classify(score, scale):
    spec = SCALES[scale]
    if score >= spec["promoter_min"]:
        return "promoter"
    if score <= spec["detractor_max"]:
        return "detractor"
    return "passive"


def parse_score(raw, scale):
    """Return (score, None) or (None, reason). Integer-valued decimals such as '9.0' are accepted, and so
    are answers exported with their scale label ('10 - Extremely likely'); see labelled_score."""
    text = (raw or "").strip()
    if text == "":
        return None, "blank"
    try:
        value = float(text)
    except ValueError:
        match = LABELLED_SCORE_RE.match(text)
        if not match:
            return None, "non_numeric"
        value = float(match.group(1))
    if math.isnan(value) or math.isinf(value):
        return None, "non_numeric"
    if value != int(value):
        return None, "non_integer"
    spec = SCALES[scale]
    if value < spec["min"] or value > spec["max"]:
        return None, "out_of_range"
    return int(value), None


def parse_count(raw, where):
    text = (raw or "").strip()
    if not re.fullmatch(r"\d+", text):
        raise InputError(f"{where}: {raw!r} is not a whole, non-negative count")
    return int(text)


def labelled_score(raw):
    """True when the answer was read from a scale label rather than a bare number."""
    text = (raw or "").strip()
    try:
        float(text)
        return False
    except ValueError:
        return bool(LABELLED_SCORE_RE.match(text))


def nps_group_error(column):
    return InputError(
        f"column {column!r} looks like Qualtrics's computed NPS group (detractor, passive or promoter coded as "
        "small numbers), not the 0-10 answer. Pass the 0-10 question column with --score-col; do not use "
        "--scale to make the group codes fit."
    )


def detect_score_column(headers, taken):
    candidates = [h for h in headers if h not in taken and SCORE_NAME_RE.search(h)]
    groups = [h for h in candidates if NPS_GROUP_RE.search(h)]
    candidates = [h for h in candidates if h not in groups]
    if len(candidates) == 1:
        return candidates[0]
    strong = [h for h in candidates if STRONG_SCORE_NAME_RE.search(h)]
    if len(strong) == 1:
        return strong[0]
    if not candidates:
        if groups:
            raise nps_group_error(groups[0])
        raise InputError(
            "could not find the score column by name. Columns: " + ", ".join(headers) + ". Pass --score-col NAME."
        )
    raise InputError(
        "more than one column could be the score: " + ", ".join(candidates) + ". Pass --score-col NAME."
    )


def period_bucket(raw, grain):
    """Return (period, None) or (None, reason): blank_period, or bad_period for an unreadable date."""
    text = (raw or "").strip()
    if not text:
        return None, "blank_period"
    if grain == "as-is":
        return text, None
    try:
        day = datetime.date.fromisoformat(text[:10])
    except ValueError:
        return None, "bad_period"
    if grain == "year":
        return f"{day.year}", None
    if grain == "quarter":
        return f"{day.year}-Q{(day.month - 1) // 3 + 1}", None
    return f"{day.year}-{day.month:02d}", None


def resolve_delimiter(value):
    delimiter = DELIMITER_NAMES.get(value.lower(), value) if value else ","
    if len(delimiter) != 1:
        raise InputError(f"--delimiter takes one character or comma, semicolon, tab or pipe; got {value!r}")
    return delimiter


def read_rows(path, delimiter, warnings, explicit=False):
    """Read a CSV into dicts. Stops on duplicate column names and on rows wider or narrower than the header,
    which a dict would otherwise resolve silently. Detects a semicolon, tab or pipe file when the
    delimiter was not given and the header has no comma."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            text = handle.read()
    except FileNotFoundError:
        raise InputError(f"file not found: {path}")
    except UnicodeDecodeError:
        raise InputError(f"{path} is not UTF-8 text; export it as UTF-8 CSV")
    first_line = text.split("\n", 1)[0]
    if not explicit and delimiter == "," and "," not in first_line:
        found = [d for d in (";", "\t", "|") if d in first_line]
        if len(found) == 1:
            delimiter = found[0]
            warnings.append(f"The file uses {DELIMITER_NAME.get(delimiter, delimiter)} as its delimiter; read it that way.")
    try:
        table = [row for row in csv.reader(io.StringIO(text), delimiter=delimiter) if row]
    except csv.Error as exc:
        raise InputError(f"{path} is not valid CSV: {exc}")
    if not table:
        raise InputError(f"{path} is empty or has no header row")
    headers = [h.strip() for h in table[0]]
    seen, repeated = set(), []
    for header in headers:
        if header in seen and header not in repeated:
            repeated.append(header)
        seen.add(header)
    if repeated:
        raise InputError(
            f"{path} has more than one column named " + ", ".join(repr(h) for h in repeated) + ". Rename them "
            "so each column is unique, then pass the one you mean."
        )
    rows = []
    for index, row in enumerate(table[1:], start=2):
        if len(row) != len(headers):
            hint = "" if len(headers) > 1 else " If the file uses another delimiter, pass --delimiter."
            raise InputError(
                f"{path} row {index} has {len(row)} cells but the header has {len(headers)}; a row may be cut or "
                f"shifted, so values would land in the wrong columns.{hint}"
            )
        rows.append(dict(zip(headers, row)))
    return headers, rows


DELIMITER_NAME = {";": "semicolons", "\t": "tabs", "|": "pipes"}


def order_periods(labels, explicit):
    """Put period labels in time order. Recognised: YYYY-MM-DD, YYYY-MM, YYYY-Qn, Qn YYYY, YYYY, or one
    shared prefix followed by a number (wave1, wave2, ... wave10). Anything else needs --period-order."""
    if explicit:
        order = [p.strip() for p in explicit.split(",") if p.strip()]
        missing = [p for p in labels if p not in order]
        if missing:
            raise InputError(
                "--period-order does not list these periods: " + ", ".join(missing) + ". Periods in the data: "
                + ", ".join(labels)
            )
        return [p for p in order if p in labels]
    for pattern, key in PERIOD_PATTERNS:
        matches = [pattern.match(p) for p in labels]
        if all(matches):
            return [p for _, p in sorted(zip((key(m) for m in matches), labels))]
    numbered = [re.match(r"^(.*?)(\d+)$", p) for p in labels]
    if all(numbered) and len({m.group(1).strip().lower() for m in numbered}) == 1:
        return [p for _, p in sorted(zip((int(m.group(2)) for m in numbered), labels))]
    return None


def check_scale(scores, scale_arg, warnings):
    """Pick the scale. Stop only on strong evidence of another scale; otherwise warn."""
    if scale_arg:
        if scale_arg == "0-10" and 0 not in scores:
            warnings.append("No respondent chose 0; the 0-10 scale was confirmed with --scale, not seen in the data.")
        return scale_arg
    if 0 in scores:
        return "0-10"
    if max(scores) <= 5:
        raise InputError(
            f"the scores run from {min(scores)} to {max(scores)} with no 0: this looks like a 1-5 scale, and NPS "
            "is defined on 0-10. Refusing to compute. If the question really offered 0-10, pass --scale 0-10. "
            "To apply the non-standard top-box mapping anyway (5 = promoter, 1-3 = detractor), pass --scale 1-5."
        )
    if len(scores) >= NO_ZERO_STOP_N and min(scores) == 1:
        raise InputError(
            f"none of {len(scores)} respondents chose 0 and the lowest score is 1: this looks like a 1-10 scale, "
            "and NPS is defined on 0-10. Refusing to guess. Check the question as it was shown, then pass "
            "--scale 0-10 (0 was offered) or --scale 1-10 (non-standard; not comparable with 0-10 scores)."
        )
    warnings.append(
        "No respondent chose 0. Treated as a 0-10 scale; if the question offered 1-10, re-run with --scale 1-10."
    )
    return "0-10"


def reject_row_options(args, what):
    for flag, value in (
        ("--score-col", args.score_col),
        ("--comment-col", args.comment_col),
        ("--comments-out", args.comments_out),
        ("--id-col", args.id_col),
        ("--theme-col", args.theme_col),
    ):
        if value:
            raise InputError(f"{flag} needs one row per respondent; {what} has counts only")
    if args.scale and args.scale != "0-10":
        raise InputError(f"--scale does not apply to {what}: the categories are already assigned")


def load_counts_argument(args):
    for flag, value in (("--segment-col", args.segment_col), ("--period-col", args.period_col)):
        if value:
            raise InputError(f"{flag} cannot be used with --counts; put the counts in a CSV with that column")
    reject_row_options(args, "--counts")
    values = [parse_count(part, "--counts") for part in args.counts.split(",")]
    info = {"mode": "counts", "file": None, "scale": "0-10 (not checked: counts given)"}
    distribution = None
    if len(values) == 3:
        cell = dict(zip(GROUPS, values))
    elif len(values) == 11:
        distribution = {str(score): count for score, count in enumerate(values)}
        cell = {"promoter": sum(values[9:]), "passive": sum(values[7:9]), "detractor": sum(values[:7])}
    else:
        raise InputError(
            "--counts takes 3 numbers (promoters,passives,detractors) or 11 numbers (how many chose 0, 1, ... 10)"
        )
    if sum(cell.values()) == 0:
        raise InputError("--counts adds up to 0 responses")
    cell.update({"segment": None, "period": None})
    return {"info": info, "cells": [cell], "records": None, "distribution": distribution, "segments": [], "periods": []}


def load_counts_csv(args, headers, rows, columns, warnings):
    reject_row_options(args, "a counts CSV")
    cells, segments, periods = [], [], []
    bad_period = 0
    for index, row in enumerate(rows, start=2):
        cell = {g: parse_count(row.get(columns[g]), f"row {index}, column {columns[g]}") for g in GROUPS}
        cell["segment"] = cell["period"] = None
        if args.segment_col:
            cell["segment"] = (row.get(args.segment_col) or "").strip() or BLANK_LABEL
            if cell["segment"] not in segments:
                segments.append(cell["segment"])
        if args.period_col:
            cell["period"], problem = period_bucket(row.get(args.period_col), args.period_grain)
            if problem == "bad_period":
                raise InputError(f"row {index}: period {row.get(args.period_col)!r} is not an ISO date")
            if cell["period"] is not None and cell["period"] not in periods:
                periods.append(cell["period"])
        cells.append(cell)
    if not cells or sum(c[g] for c in cells for g in GROUPS) == 0:
        raise InputError("the counts CSV has no responses")
    if len(cells) > 1 and not (args.segment_col or args.period_col):
        warnings.append(
            f"The counts CSV has {len(cells)} rows and no --segment-col or --period-col: all rows were added together."
        )
    info = {
        "mode": "counts-csv",
        "file": args.input,
        "count_columns": columns,
        "rows_total": len(rows),
        "scale": "0-10 (not checked: counts given)",
    }
    return {"info": info, "cells": cells, "records": None, "distribution": None, "segments": segments, "periods": periods}


def load_respondents(args, headers, rows, warnings):
    taken = {c for c in (args.segment_col, args.period_col, args.comment_col, args.id_col, args.theme_col) if c}
    score_col = args.score_col or detect_score_column(headers, taken)
    if NPS_GROUP_RE.search(score_col):
        raise nps_group_error(score_col)
    # First pass with the widest range so the scale check sees every whole-number answer.
    first = [parse_score(row.get(score_col), "0-10") for row in rows]
    whole = [s for s, _ in first if s is not None]
    non_blank = sum(1 for _, reason in first if reason != "blank")
    non_numeric = [
        row.get(score_col)
        for row, (_, reason) in zip(rows, first)
        if reason == "non_numeric" and not NON_ANSWER_RE.match((row.get(score_col) or "").strip())
    ]
    if not whole:
        raise InputError(f"column {score_col!r} has no whole-number scores between 0 and 10 in {len(rows)} row(s)")
    if non_blank and len(non_numeric) / non_blank > NON_NUMERIC_STOP_SHARE and not args.allow_non_numeric:
        shown = ", ".join(repr(v) for v in list(dict.fromkeys(non_numeric))[:MAX_EXAMPLES])
        raise InputError(
            f"{len(non_numeric)} of {non_blank} non-blank answers in {score_col!r} "
            f"({100 * len(non_numeric) / non_blank:.1f}%) are neither scores nor a usual 'no answer' value, for "
            f"example {shown}. Dropping them could remove a whole answer category. Re-export the column as "
            "numbers, or, if these really are non-answers, re-run with --allow-non-numeric and report them."
        )
    scale = check_scale(whole, args.scale, warnings)
    if scale != "0-10":
        warnings.append(
            f"Scale {scale} is not the Net Promoter standard. The result is not comparable with 0-10 scores or "
            "with published benchmarks; say so wherever the number is shown."
        )
    excluded = {"blank": 0, "non_numeric": 0, "non_integer": 0, "out_of_range": 0}
    no_period = {"blank_period": 0, "bad_period": 0}
    labelled = 0
    examples, period_examples, records, segments, periods = [], [], [], [], []
    for index, row in enumerate(rows, start=2):  # row 1 is the header
        segment = None
        if args.segment_col:
            segment = (row.get(args.segment_col) or "").strip() or BLANK_LABEL
            if segment not in segments:
                segments.append(segment)
        period, period_problem = None, None
        if args.period_col:
            period, period_problem = period_bucket(row.get(args.period_col), args.period_grain)
            if period is not None and period not in periods:
                periods.append(period)
        score, reason = parse_score(row.get(score_col), scale)
        if reason:
            excluded[reason] += 1
            if reason != "blank" and len(examples) < MAX_EXAMPLES:
                examples.append({"row": index, "value": row.get(score_col), "reason": reason})
            continue
        labelled += labelled_score(row.get(score_col))
        if period_problem:
            # A missing or unreadable date leaves the row out of the period analysis only: its score still
            # counts in the overall result and in segments.
            no_period[period_problem] += 1
            if period_problem == "bad_period" and len(period_examples) < MAX_EXAMPLES:
                period_examples.append({"row": index, "value": row.get(args.period_col)})
        records.append(
            {
                "row": index,
                "score": score,
                "group": classify(score, scale),
                "segment": segment,
                "period": period,
                "comment": (row.get(args.comment_col) or "").strip() if args.comment_col else None,
                "id": (row.get(args.id_col) or "").strip() if args.id_col else None,
                "themes": (row.get(args.theme_col) or "").strip() if args.theme_col else None,
            }
        )
    if not records:
        raise InputError("no valid scores left after exclusions: " + json.dumps(excluded))
    if len(rows) - len(records):
        warnings.append(
            f"{len(rows) - len(records)} of {len(rows)} rows ({100 * (len(rows) - len(records)) / len(rows):.1f}%) "
            "were excluded; see the exclusion counts and report them with the score."
        )
    if labelled:
        warnings.append(
            f"{labelled} answers carried their scale label (for example '10 - Extremely likely'); the leading "
            "number was used as the score."
        )
    if args.period_col and sum(no_period.values()):
        warnings.append(
            f"{no_period['blank_period']} valid scores have no period and {no_period['bad_period']} have an "
            "unreadable date. They count in the overall result and segments, but not in the period table, trend "
            "tests or mix shift."
        )
    cells = {}
    for record in records:
        cell = cells.setdefault(
            (record["segment"], record["period"]),
            {"segment": record["segment"], "period": record["period"], "promoter": 0, "passive": 0, "detractor": 0},
        )
        cell[record["group"]] += 1
    spec = SCALES[scale]
    distribution = {str(s): 0 for s in range(spec["min"], spec["max"] + 1)}
    for record in records:
        distribution[str(record["score"])] += 1
    info = {
        "mode": "respondents",
        "file": args.input,
        "score_col": score_col,
        "score_col_source": "given" if args.score_col else "auto-detected",
        "scale": scale,
        "rows_total": len(rows),
        "rows_valid": len(records),
        "rows_excluded": len(rows) - len(records),
        "excluded": excluded,
        "excluded_examples": examples,
        "scores_read_from_labels": labelled,
    }
    if args.period_col:
        info["without_period"] = no_period
        info["bad_period_examples"] = period_examples
    if args.id_col:
        ids = [r["id"] for r in records]
        info["ids"] = {
            "blank": sum(1 for i in ids if not i),
            "repeated": sum(n - 1 for n in _count([i for i in ids if i]).values() if n > 1),
        }
    return {
        "info": info,
        "cells": list(cells.values()),
        "records": records,
        "distribution": distribution,
        "segments": segments,
        "periods": periods,
    }


def _count(items):
    out = {}
    for item in items:
        out[item] = out.get(item, 0) + 1
    return out


def load(args, warnings):
    if args.counts and args.input:
        raise InputError("give either a CSV file or --counts, not both")
    if args.counts:
        return load_counts_argument(args)
    if not args.input:
        raise InputError("give a CSV file, or --counts P,A,D")
    headers, rows = read_rows(args.input, resolve_delimiter(args.delimiter), warnings, args.delimiter is not None)
    for name, value in (
        ("--score-col", args.score_col),
        ("--segment-col", args.segment_col),
        ("--period-col", args.period_col),
        ("--comment-col", args.comment_col),
        ("--id-col", args.id_col),
        ("--theme-col", args.theme_col),
    ):
        if value and value not in headers:
            raise InputError(f"{name} {value!r} is not a column. Columns: {', '.join(headers)}")
    columns = {g: next((h for h in headers if pattern.match(h.strip())), None) for g, pattern in COUNT_COLUMNS.items()}
    if all(columns.values()) and not args.score_col:
        return load_counts_csv(args, headers, rows, columns, warnings)
    return load_respondents(args, headers, rows, warnings)


# ---------------------------------------------------------------- analysis

def check_arguments(args):
    if args.compare and not args.segment_col:
        raise InputError("--compare needs --segment-col")
    if args.pairwise and not args.segment_col:
        raise InputError("--pairwise needs --segment-col")
    if args.compare_periods and not args.period_col:
        raise InputError("--compare-periods needs --period-col")
    if args.comments_out and not args.comment_col:
        raise InputError("--comments-out needs --comment-col")
    if args.comments_out and not args.comments_out.lower().endswith((".json", ".csv")):
        raise InputError("--comments-out must end in .json or .csv")
    if args.paired and not (args.id_col and args.compare_periods):
        raise InputError("--paired needs --id-col and --compare-periods EARLIER LATER")
    if args.period_order and not args.period_col:
        raise InputError("--period-order needs --period-col")
    if args.comments_out and args.input and same_file(args.comments_out, args.input):
        raise InputError("--comments-out points at the input file; write the comments to a new file")
    if 1 < args.confidence < 100:
        args.confidence /= 100  # 95 means 95%
    if not 0 < args.confidence < 1:
        raise InputError("--confidence must be a level such as 0.95 or 95")
    if args.tail == "one":
        args.tail = "above"  # the original spelling of the one-tailed "are we above" test
    if args.min_base < 1:
        raise InputError("--min-base must be at least 1")
    if args.benchmark is not None and not -100 <= args.benchmark <= 100:
        raise InputError("--benchmark is a score in points, from -100 to 100")
    if args.tail and args.benchmark is None:
        raise InputError("--tail needs --benchmark")
    if args.invited is not None and args.invited < 1:
        raise InputError("--invited must be at least 1")


def same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.realpath(a) == os.path.realpath(b)


def analyse(args):
    check_arguments(args)
    warnings = []
    data = load(args, warnings)
    cells, records = data["cells"], data["records"]
    z = z_for(args.confidence)
    alpha = 1 - args.confidence

    def stats_for(label, key=None, value=None):
        counts = dict.fromkeys(GROUPS, 0)
        for cell in cells:
            if key is None or cell[key] == value:
                for g in GROUPS:
                    counts[g] += cell[g]
        return summarize(label, counts, args.interval, z, args.min_base)

    result = {
        "input": data["info"],
        "settings": {
            "confidence": args.confidence,
            "interval": args.interval,
            "test": args.test,
            "min_base": args.min_base,
            "adjust": args.adjust,
            "period_grain": args.period_grain,
        },
        "overall": stats_for("Overall"),
        "segments": [],
        "periods": [],
        "comparisons": [],
        "warnings": warnings,
    }
    if data["distribution"]:
        result["score_distribution"] = data["distribution"]
    if args.invited is not None:
        n = result["overall"]["n"]
        if args.invited < n:
            raise InputError(f"--invited {args.invited} is smaller than the {n} valid responses")
        # Respondents are the rows in the file; valid scores can be fewer. Report both, separately.
        answered = data["info"].get("rows_total", n)
        if args.invited < answered:
            raise InputError(f"--invited {args.invited} is smaller than the {answered} responses in the file")
        result["response"] = {
            "invited": args.invited,
            "responses": answered,
            "valid": n,
            "response_rate": round(100 * answered / args.invited, 4),
            "valid_score_rate": round(100 * n / args.invited, 4),
        }
        warnings.append(
            f"Response rate {100 * answered / args.invited:.1f}% ({answered} of {args.invited} invited); valid "
            f"scores from {100 * n / args.invited:.1f}% of those invited. The interval covers sampling error "
            "only, not the difference between people who answered and people who did not."
        )

    by_segment = {name: stats_for(name, "segment", name) for name in sorted(data["segments"])}
    ordered = order_periods(data["periods"], args.period_order)
    if ordered is None:
        if len(data["periods"]) > 1:
            raise InputError(
                "cannot tell the time order of these periods: " + ", ".join(data["periods"]) + ". Pass "
                "--period-order with them from earliest to latest (comma-separated), or use ISO dates with "
                "--period-grain."
            )
        ordered = data["periods"]
    by_period = {name: stats_for(name, "period", name) for name in ordered}
    result["segments"], result["periods"] = list(by_segment.values()), list(by_period.values())
    groups = [result["overall"]] + result["segments"] + result["periods"]
    for group in groups:
        if group["n"] == 0:
            warnings.append(f"{group['label']}: no valid scores, so no NPS and no comparisons for it.")
    small = [g["label"] for g in groups if 0 < g["n"] < args.min_base]
    if small:
        warnings.append(
            f"Small base (n under {args.min_base}): " + ", ".join(small) + ". Show these with their interval "
            "and call them directional."
        )

    def lookup(table, name, what):
        if name not in table:
            raise InputError(f"{what} {name!r} not found. Available: {', '.join(table) or 'none'}")
        if table[name]["n"] == 0:
            raise InputError(f"{what} {name!r} has no valid scores, so it cannot be compared")
        return table[name]

    def id_overlap(key, first, second):
        """Ids in both groups, and extra answers from ids repeated within either group."""
        if not (records and args.id_col):
            return 0, 0
        ids = {g: [r["id"] for r in records if r[key] == g and r["id"]] for g in (first, second)}
        shared = len(set(ids[first]) & set(ids[second]))
        repeated = sum(len(v) - len(set(v)) for v in ids.values())
        return shared, repeated

    def independent_test(kind, a, b):
        """compare(), unless --id-col shows the two groups are not independent samples."""
        key = "segment" if kind == "segment" else "period"
        shared, repeated = id_overlap(key, a["label"], b["label"])
        if not (shared or repeated):
            return compare(kind, a, b, args.interval, args.test, args.confidence, args.min_base)
        problems = []
        if shared:
            where = "both periods" if key == "period" else "both segments"
            problems.append(f"{shared} respondent ids answered in {where}")
        if repeated:
            problems.append(f"{repeated} extra answers come from ids that answered more than once in one group")
        fix = (
            "use --paired with --compare-periods, or keep one answer per respondent"
            if key == "period"
            else "keep one answer per respondent (and one segment per respondent) before testing"
        )
        return {
            "kind": kind,
            "a": a["label"],
            "b": b["label"],
            "n_a": a["n"],
            "n_b": b["n"],
            "difference": round(a["nps"] - b["nps"], 4) if a["n"] and b["n"] else None,
            "tested": False,
            "shared_respondents": shared,
            "repeated_answers": repeated,
            "note": "; ".join(problems) + ", so the samples are not independent; " + fix,
        }

    def period_comparison(kind, earlier, later):
        return independent_test(kind, later, earlier)

    family = []
    if args.compare:
        a, b = (lookup(by_segment, name, "segment") for name in args.compare)
        family.append(independent_test("segment", a, b))
    if args.pairwise:
        for a, b in itertools.combinations([g for g in result["segments"] if g["n"] > 0], 2):
            if args.compare and {a["label"], b["label"]} == set(args.compare):
                continue
            family.append(independent_test("segment", a, b))
    if args.compare_periods:
        earlier, later = (lookup(by_period, name, "period") for name in args.compare_periods)
        family.append(period_comparison("period", earlier, later))
    usable_periods = [g for g in result["periods"] if g["n"] > 0]
    for earlier, later in zip(usable_periods, usable_periods[1:]):
        if args.compare_periods and [earlier["label"], later["label"]] == list(args.compare_periods):
            continue
        family.append(period_comparison("trend", earlier, later))
    adjust_p_values(family, args.adjust, alpha)
    result["comparisons"] = family
    tested = sum(1 for c in family if c.get("tested"))
    result["tests_run"] = tested
    if tested > 1 and args.adjust == "none":
        warnings.append(
            f"{tested} tests were run without a multiple-comparison adjustment: at alpha {alpha:.2f} about "
            f"{tested * alpha:.1f} would come out significant by chance if nothing differed. Re-run with "
            "--adjust holm, or treat single significant pairs as leads."
        )
    if family:
        warnings.append(
            "The tests assume independent samples. If the same people answered in both groups or periods, "
            "this test is not valid; say so."
        )
    if any(c.get("verdict") == INCONCLUSIVE for c in family):
        warnings.append(
            f"Inconclusive, small base means: not significant, and at least one side has fewer than "
            f"{args.min_base} responses. Read the interval of the difference: a difference anywhere inside it fits "
            "the data. It is not evidence of no difference. (No power calculation was made.)"
        )
    ids = data["info"].get("ids")
    if ids and ids["repeated"]:
        warnings.append(
            f"{ids['repeated']} answers come from respondent ids that appear more than once. Every interval "
            "treats each row as a different person; keep one answer per respondent unless repeats are intended."
        )
    if ids and ids["blank"]:
        warnings.append(f"{ids['blank']} valid scores have a blank id, so overlap among them cannot be checked.")
    if len(usable_periods) > 1 and not args.id_col:
        warnings.append(
            "Period tests assume the periods do not share respondents. Rolling or overlapping windows do; the "
            "script cannot detect that without --id-col. Test only non-overlapping periods."
        )

    if args.benchmark is not None:
        result["benchmark"] = benchmark_test(
            result["overall"], args.benchmark, args.tail or "two", args.interval, args.confidence
        )
        warnings.append(
            "The benchmark test treats the benchmark as a fixed number (a target). If it is an estimate from "
            "another survey (last year's score, an industry study), it has sampling error too: put both sets "
            "of counts in a counts CSV and use --segment-col and --compare instead."
        )
    if args.segment_col and len(usable_periods) > 1:
        pair = list(args.compare_periods) if args.compare_periods else [usable_periods[0]["label"], usable_periods[-1]["label"]]
        shift = mix_shift(cells, pair[0], pair[1])
        if shift:
            result["mix_shift"] = shift
    if args.paired:
        result["paired"] = paired_change(records, args.compare_periods[0], args.compare_periods[1], args.confidence)

    if args.theme_col:
        result["themes"] = theme_table(records, args, z)
        warnings.append(
            "Theme rows describe an association among coded respondents, not a cause; themes overlap and no "
            "multiple-comparison adjustment is applied to them."
        )
    if args.comment_col:
        split = {g: [r for r in records if r["group"] == g and r["comment"]] for g in GROUPS}
        totals = {g: sum(1 for r in records if r["group"] == g) for g in GROUPS}
        result["comments"] = {g + "s": {"respondents": totals[g], "with_comment": len(split[g])} for g in GROUPS}
        if args.comments_out:
            write_comments(args.comments_out, split, totals)
            result["comments"]["written_to"] = args.comments_out
    return result


def theme_table(records, args, z):
    """NPS of respondents coded with a theme against the other coded respondents."""
    coded = []
    for record in records:
        themes = {t.strip() for t in (record["themes"] or "").split(args.theme_sep) if t.strip()}
        if themes:
            coded.append((record["group"], themes))
    rows = []
    for theme in sorted({t for _, themes in coded for t in themes}):
        sides = []
        for label, wanted in (("mentioned", True), ("rest", False)):
            counts = dict.fromkeys(GROUPS, 0)
            for group, themes in coded:
                if (theme in themes) == wanted:
                    counts[group] += 1
            sides.append(summarize(label, counts, args.interval, z, args.min_base))
        gap = compare("theme", sides[0], sides[1], args.interval, "z", args.confidence, args.min_base)
        rows.append(
            {
                "theme": theme,
                "mentions": sides[0]["n"],
                "coded_respondents": len(coded),
                "mentioned": sides[0],
                "rest": sides[1],
                "difference": gap.get("difference"),
                "ci_low": gap.get("ci_low"),
                "ci_high": gap.get("ci_high"),
            }
        )
    return sorted(rows, key=lambda r: (-r["mentions"], r["theme"]))


def write_comments(path, split, totals):
    fields = ["row", "group", "score", "segment", "period", "comment"]
    if path.lower().endswith(".json"):
        payload = {
            g + "s": {
                "respondents": totals[g],
                "with_comment": len(items),
                "comments": [{f: item[f] for f in fields if f != "group"} for item in items],
            }
            for g, items in split.items()
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        return
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for g in ("detractor", "passive", "promoter"):
            for item in split[g]:
                writer.writerow({f: ("" if item[f] is None else item[f]) for f in fields})


# ---------------------------------------------------------------- output

def fmt(value, signed=True):
    if value is None:
        return "n/a"
    return f"{value:+.1f}" if signed else f"{value:.1f}"


def table(rows, level):
    lines = [f"{'Group':<22}{'n':>6}{'Prom%':>7}{'Pass%':>7}{'Detr%':>7}{'NPS':>8}  {level}% interval"]
    for g in rows:
        if g["n"] == 0:
            lines.append(f"{g['label'][:21]:<22}{0:>6}{'':>7}{'':>7}{'':>7}{'n/a':>8}  no valid scores")
            continue
        flag = ""
        if g["n"] < MIN_N_FOR_TEST:
            flag = f"  (n under {MIN_N_FOR_TEST}: rough indication only)"
        elif g["small_base"]:
            flag = "  (small base"
            if "n_for_10_point_margin" in g:
                flag += f"; about n = {g['n_for_10_point_margin']} for +/-10 points"
            flag += ")"
        lines.append(
            f"{g['label'][:21]:<22}{g['n']:>6}{g['pct_promoters']:>7.1f}{g['pct_passives']:>7.1f}"
            f"{g['pct_detractors']:>7.1f}{fmt(g['nps']):>8}  {fmt(g['ci_low'])} to {fmt(g['ci_high'])}{flag}"
        )
    return lines


def render(result):
    info, settings = result["input"], result["settings"]
    level = f"{100 * settings['confidence']:g}"
    alpha = 1 - settings["confidence"]
    lines = []
    if info["mode"] == "respondents":
        lines += [
            f"NPS analysis of {info['file']}",
            f"Score column: {info['score_col']} ({info['score_col_source']}); scale {info['scale']}; "
            f"interval: {settings['interval']}, {level}% confidence",
            f"Rows: {info['rows_total']} read, {info['rows_valid']} used, {info['rows_excluded']} excluded ("
            + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in info["excluded"].items())
            + ")",
        ]
        for example in info["excluded_examples"]:
            lines.append(f"  excluded row {example['row']}: {example['value']!r} ({example['reason'].replace('_', ' ')})")
        if "without_period" in info:
            w = info["without_period"]
            lines.append(
                f"Without a period (kept in the overall result, left out of the period analysis): "
                f"blank {w['blank_period']}, unreadable date {w['bad_period']}"
            )
            for example in info["bad_period_examples"]:
                lines.append(f"  row {example['row']}: date {example['value']!r} not read")
    else:
        source = info["file"] or "--counts"
        lines += [
            f"NPS analysis of counts from {source}",
            f"Scale: {info['scale']}; interval: {settings['interval']}, {level}% confidence",
        ]
    lines.append("")
    lines.extend(table([result["overall"]], level))
    if "score_distribution" in result:
        lines.append("Scores: " + "  ".join(f"{score}:{count}" for score, count in result["score_distribution"].items()))
    if "response" in result:
        r = result["response"]
        lines.append(
            f"Response rate: {r['response_rate']:.1f}% ({r['responses']} of {r['invited']} invited); valid scores "
            f"{r['valid']} ({r['valid_score_rate']:.1f}% of invited)"
        )
    for title, key in (("By segment", "segments"), ("By period", "periods")):
        if result[key]:
            lines.extend(["", title])
            lines.extend(table(result[key], level))
    if "benchmark" in result:
        b = result["benchmark"]
        tail = "two-tailed" if b["tail"] == "two" else f"one-tailed, {b['tail']}"
        lines.extend(["", f"Benchmark {fmt(b['benchmark'])} ({tail}; z-test on the overall score, fixed benchmark)"])
        gaps = f"Observed difference {fmt(b['difference'])} points"
        if "difference_adjusted" in b:
            gaps += f" (adjusted score minus benchmark {fmt(b['difference_adjusted'])}, used by the test)"
        if b.get("tested"):
            verdict = "significant" if b["significant"] else "not significant"
            extra = f"; one-sided lower bound {fmt(b['lower_bound'])}" if "lower_bound" in b else ""
            extra += f"; one-sided upper bound {fmt(b['upper_bound'])}" if "upper_bound" in b else ""
            stat = "exact" if b.get("exact") else f"z = {b['z']:.3f}"
            lines.append(
                f"  H1: {b['hypothesis']}. {gaps}, {stat}, p = {fmt_p(b['p_value'], alpha)} "
                f"({verdict} at {level}%){extra}"
            )
            if b.get("exact"):
                lines.append(f"  {b['note']}")
        else:
            lines.append(f"  H1: {b['hypothesis']}. {gaps}; not tested, {b['note']}")
    if result["comparisons"]:
        name = "Welch t-test on the -100/0/+100 recode" if settings["test"] == "welch" else "z-test on the NPS difference"
        lines.extend(["", f"Comparisons ({name}, independent samples; difference = first minus second)"])
        for c in result["comparisons"]:
            head = f"  [{c['kind']}] {c['a']} vs {c['b']} (n {c['n_a']} vs {c['n_b']})"
            if not c.get("tested"):
                lines.append(f"{head}: not tested, {c['note']}")
                continue
            p_text = f"p = {fmt_p(c['p_value'], alpha)}"
            if "p_adjusted" in c:
                p_text += f", {settings['adjust']}-adjusted p = {fmt_p(c['p_adjusted'], alpha)}"
            stat = f"t = {c['t']:.2f}, df = {c['df']:.1f}" if "t" in c else f"z = {c['z']:.2f}"
            centre = f" (centred on the adjusted difference {fmt(c['difference_adjusted'])})" if "difference_adjusted" in c else ""
            lines.append(
                f"{head}: {fmt(c['difference'])} points, {level}% interval {fmt(c['ci_low'])} to "
                f"{fmt(c['ci_high'])}{centre}, {stat}, {p_text} ({c['verdict']})"
            )
            if c.get("note"):
                lines.append(f"    {c['note']}")
    if "paired" in result:
        p = result["paired"]
        lines.extend(["", f"Paired change, {p['earlier']} to {p['later']} (same respondents, -100/0/+100 recode)"])
        lines.append(
            f"  {p['n_pairs']} answered in both; {p['only_earlier']} only earlier, {p['only_later']} only later; "
            f"up {p['moved_up']}, same {p['unchanged']}, down {p['moved_down']}"
        )
        if p.get("tested"):
            lines.append(
                f"  mean change {fmt(p['mean_change'])} points, {level}% interval {fmt(p['ci_low'])} to "
                f"{fmt(p['ci_high'])}, t = {p['t']:.2f}, df = {p['df']}, p = {fmt_p(p['p_value'], alpha)}"
            )
        else:
            lines.append(f"  not tested, {p['note']}")
    if "mix_shift" in result:
        m = result["mix_shift"]
        lines.extend(
            [
                "",
                f"Mix shift, {m['earlier']} to {m['later']}: change {fmt(m['change'])} = within segments "
                f"{fmt(m['within_segments'])} + segment mix {fmt(m['mix'])}",
            ]
        )
        for s in m["segments"]:
            lines.append(
                f"  {s['segment']}: share {s['share_earlier']:.1f}% -> {s['share_later']:.1f}%, NPS "
                f"{fmt(s['nps_earlier'])} -> {fmt(s['nps_later'])}, within {fmt(s['within'])}, mix {fmt(s['mix'])}"
            )
    if "themes" in result:
        lines.extend(["", "Themes (NPS of coded respondents who mention the theme vs the other coded respondents)"])
        for t in result["themes"]:
            lines.append(
                f"  {t['theme']}: {t['mentions']} of {t['coded_respondents']}; NPS {fmt(t['mentioned']['nps'])} "
                f"({fmt(t['mentioned']['ci_low'])} to {fmt(t['mentioned']['ci_high'])}) vs {fmt(t['rest']['nps'])}; "
                f"difference {fmt(t['difference'])} ({fmt(t['ci_low'])} to {fmt(t['ci_high'])})"
            )
    if "comments" in result:
        lines.extend(["", "Comments (respondents with a comment / respondents in the group)"])
        for key in ("promoters", "passives", "detractors"):
            c = result["comments"][key]
            lines.append(f"  {key}: {c['with_comment']} / {c['respondents']}")
        if "written_to" in result["comments"]:
            lines.append(f"  written to {result['comments']['written_to']}")
    if result["warnings"]:
        lines.extend(["", "Warnings"])
        lines.extend(f"  - {w}" for w in result["warnings"])
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Net Promoter Score with a confidence interval, comparisons and comments split by group.",
    )
    parser.add_argument("input", nargs="?", help="CSV: one row per respondent, or counts (promoters, passives, detractors columns)")
    parser.add_argument("--counts", metavar="P,A,D", help="promoters,passives,detractors, or 11 counts for the scores 0 to 10")
    parser.add_argument("--score-col", help="column with the 0-10 answer (default: detected from the header names)")
    parser.add_argument("--segment-col", help="column to break the score down by")
    parser.add_argument("--period-col", help="column with the period label or an ISO date")
    parser.add_argument(
        "--period-grain",
        choices=["as-is", "month", "quarter", "year"],
        default="as-is",
        help="as-is uses the period value as a label; the others bucket ISO dates (default: as-is)",
    )
    parser.add_argument(
        "--period-order",
        metavar="P1,P2,...",
        help="periods from earliest to latest, when the labels are not dates, YYYY-MM, YYYY-Qn or numbered",
    )
    parser.add_argument("--comment-col", help="column with the open-ended reason")
    parser.add_argument("--comments-out", metavar="PATH", help="write comments split by group to PATH (.csv or .json)")
    parser.add_argument("--id-col", help="respondent id column: detects people who answered in two periods")
    parser.add_argument("--theme-col", help="column with coded themes, to compare NPS with and without each theme")
    parser.add_argument("--theme-sep", default=";", help="separator between themes in --theme-col (default: ;)")
    parser.add_argument(
        "--scale",
        choices=sorted(SCALES),
        help="the scale the question used, when it is not 0-10 or the script could not tell",
    )
    parser.add_argument("--confidence", type=float, default=0.95, help="confidence level, 0.95 or 95 (default: 0.95)")
    parser.add_argument(
        "--interval",
        choices=["adjusted-wald", "wald"],
        default="adjusted-wald",
        help="interval and z-test method (default: adjusted-wald, Rocks 2016 AW(3, T))",
    )
    parser.add_argument(
        "--test",
        choices=["z", "welch"],
        default="z",
        help="two-group test: z on the NPS difference, or Welch t on the -100/0/+100 recode (default: z)",
    )
    parser.add_argument("--compare", nargs=2, metavar=("SEGMENT_A", "SEGMENT_B"), help="test two segments")
    parser.add_argument("--pairwise", action="store_true", help="test every pair of segments")
    parser.add_argument("--compare-periods", nargs=2, metavar=("EARLIER", "LATER"), help="test two periods")
    parser.add_argument("--paired", action="store_true", help="with --id-col and --compare-periods: change per respondent")
    parser.add_argument("--benchmark", type=float, metavar="POINTS", help="test the overall score against this value")
    parser.add_argument(
        "--tail",
        choices=["two", "above", "below", "one"],
        help="benchmark test: two (default), above (one-tailed: is the score above it), below; one = above",
    )
    parser.add_argument(
        "--adjust",
        choices=["none", "bonferroni", "holm"],
        default="none",
        help="multiple-comparison adjustment across all two-group tests in this run (default: none, with a warning)",
    )
    parser.add_argument(
        "--min-base",
        type=int,
        default=DEFAULT_MIN_BASE,
        help=f"flag groups with fewer valid scores than this as a small base (default: {DEFAULT_MIN_BASE})",
    )
    parser.add_argument("--invited", type=int, metavar="N", help="number of people invited, to report the response rate")
    parser.add_argument(
        "--delimiter",
        help="CSV delimiter: a character, or comma, semicolon, tab, pipe (default: comma; a header with no comma "
        "but semicolons, tabs or pipes is read with that delimiter)",
    )
    parser.add_argument(
        "--allow-non-numeric",
        action="store_true",
        help="go on when more than 5%% of the non-blank answers are not scores (they are excluded and counted)",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = analyse(args)
    except InputError as exc:
        print(f"nps-analysis: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
