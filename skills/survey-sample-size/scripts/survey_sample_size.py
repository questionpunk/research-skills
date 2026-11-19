#!/usr/bin/env python3
"""Survey sample size: how many responses a survey needs, and what a given n can support.

Standard library only, Python 3.9+. No network, no randomness. Every n is rounded up.
Formulas and thresholds are cited in references/sources.md.

Usage: python3 scripts/survey_sample_size.py SUBCOMMAND [options] [--json]

  proportion  n for a margin of error on a percentage, or the margin (or interval) a given n gives
  mean        n for a margin of error on a mean, or the margin a given n gives
  compare     two groups: n per group, power for a given n, or the smallest detectable difference
  gap         margin of error for the gap between two answers to one question in the same sample
  check       what a given n supports: overall margin, smallest subgroup, detectable difference
  subgroups   total n and a quota table so every reported subgroup reaches its base or margin
  invites     invitations to send for a target number of completes
  nps         Net Promoter Score: n for a margin in NPS points, the margin of an n, or n per group to compare two scores
  maxdiff     MaxDiff rules of thumb (sets per respondent, respondents)
  conjoint    choice-based conjoint rules of thumb (respondents)
  interviews  planning range for interviews or focus groups (guidance, not a formula)
  saturation  saturation check from new codes per interview (Guest, Namey and Chen 2020)
"""
import argparse
import csv
import json
import math
import re
import sys
from statistics import NormalDist

EXIT_BAD_INPUT = 2
EPS = 1e-9

# Rules of thumb and conventions (references/sources.md).
CONJOINT_MIN_REPRESENTATIONS = 500  # Johnson's rule, Orme ch. 7: n*t*a/c >= 500
CONJOINT_BETTER_REPRESENTATIONS = 1000  # Orme ch. 7: "1,000 or more" is better
CONJOINT_MIN_TOTAL = 300  # Orme ch. 7: at least 300 when subgroups are not compared
CHOICE_MIN_PER_SUBGROUP = 200  # Orme ch. 7 (conjoint), Sawtooth MaxDiff guidelines
MAXDIFF_MIN_TOTAL = 300  # Sawtooth MaxDiff sample-size blog: at least 300 in total
MAXDIFF_MIN_PER_SUBGROUP = 200  # ... and at least 200 in every separately reported subgroup
MAXDIFF_MANY_ITEMS = 30  # ... raise both above about 30 items (doubled at 60 items in its example)
MAXDIFF_PER_SET = 4  # same default as the maxdiff-design skill: 4, or 3 for 6 or 7 items
MAXDIFF_TIMES_SHOWN = 3  # Sawtooth: each item 3 times per respondent, sets = 3K/k
MAXDIFF_MIN_TIMES_SHOWN = 2  # Sawtooth warns below 2 times per respondent
MAXDIFF_MIN_EXPOSURES = 500  # Sawtooth manual: each item seen at least 500 times
MAXDIFF_BETTER_EXPOSURES = 1000  # ... and preferably 1000 times
NPS_DEFAULT_VARIANCE = 0.67  # Lewis and Sauro 2021c: a realistic maximum of the NPS variance (range 0.40-0.76)
SUBGROUP_MIN_BASE = 100  # Sudman 1976: 100 or more per major subgroup
SMALL_COUNT = 10  # under 10 expected responses in the smaller category: Wilson, not Wald
INTERVIEW_RANGES = {  # per fairly homogeneous segment
    ("interviews", "codes"): (9, 17, "Hennink and Kaiser 2022: saturation within 9-17 interviews"),
    ("interviews", "meaning"): (16, 24, "Hennink, Kaiser and Marconi 2017: meaning saturation at 16 to 24 interviews"),
    ("focus-groups", "codes"): (4, 8, "Hennink and Kaiser 2022: saturation within 4-8 focus group discussions"),
}
SATURATION_BASE = 4  # Guest, Namey and Chen 2020: default base size of four interviews
SATURATION_RUN = 2  # ... run length two (or three)
SATURATION_THRESHOLD = 0.05  # ... <=5% (or 0%) new information
# Subcommands whose statement carries a sampling margin or confidence level (relabelled by --opt-in).
OPT_IN_LABELLED = ("proportion", "mean", "compare", "gap", "check", "subgroups", "nps")
TABLE_MARGINS = (0.01, 0.02, 0.03, 0.04, 0.05, 0.07, 0.10)
TABLE_DIFFERENCES = (0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20)
TABLE_D = (0.1, 0.2, 0.3, 0.4, 0.5, 0.8)
TABLE_N_FACTORS = (0.5, 1, 2, 4)
NPS_TABLE_MARGINS = (0.03, 0.05, 0.07, 0.10)  # +/-3, 5, 7 and 10 NPS points
NPS_TABLE_DIFFERENCES = (0.05, 0.10, 0.15, 0.20)  # 5, 10, 15 and 20 NPS points
Z_DIGITS = 6  # z printed as 1.959964, not 1.96: the script computes with the exact quantile


class InputError(Exception):
    """Bad input: reported on stderr with exit status 2."""


def z_value(probability):
    """Standard normal quantile."""
    return NormalDist().inv_cdf(probability)


def phi(value):
    """Standard normal cumulative probability."""
    return NormalDist().cdf(value)


def ceil_n(value):
    """Round a sample size up; the epsilon keeps 385.0000000001 from becoming 386."""
    return int(math.ceil(value - EPS))


def pct(value):
    """0.05 -> '5', 0.075 -> '7.5' (for sentences)."""
    return "%g" % round(value * 100, 2)


def fraction(value, name, allow_zero=False, allow_one=False):
    """Validate a number given as a proportion between 0 and 1."""
    low_ok = value >= 0 if allow_zero else value > 0
    high_ok = value <= 1 if allow_one else value < 1
    if not (low_ok and high_ok):
        hint = ""
        if 1 <= value <= 100:
            hint = " (give a proportion, not a percentage: did you mean %g?)" % (value / 100.0)
        low = "at least 0" if allow_zero else "above 0"
        high = "at most 1" if allow_one else "below 1"
        raise InputError("%s must be %s and %s, got %g%s" % (name, low, high, value, hint))
    return value


def positive(value, name):
    if value is None or not value > 0:
        raise InputError("%s must be greater than 0, got %s" % (name, value))
    return value


def check_population(population):
    if population is not None and population < 2:
        raise InputError("--population must be at least 2, got %s" % population)
    return population


def resolve_deff(args):
    """Design effect from --deff, or from --icc with --cluster-size, or from --weight-cv."""
    icc = getattr(args, "icc", None)
    cluster = getattr(args, "cluster_size", None)
    weight_cv = getattr(args, "weight_cv", None)
    given = [args.deff is not None, icc is not None or cluster is not None, weight_cv is not None]
    if sum(given) > 1:
        raise InputError("give one of --deff, --icc with --cluster-size, or --weight-cv; if both clustering and weighting apply, work out the combined design effect and pass it as --deff")
    if icc is not None or cluster is not None:
        if icc is None or cluster is None:
            raise InputError("--icc and --cluster-size go together")
        fraction(icc, "--icc", allow_zero=True, allow_one=True)
        if cluster < 1:
            raise InputError("--cluster-size must be at least 1, got %g" % cluster)
        return 1.0 + (cluster - 1.0) * icc, "clustering: 1 + (%g - 1) x %g" % (cluster, icc)
    if weight_cv is not None:
        if weight_cv < 0:
            raise InputError("--weight-cv must be 0 or more, got %g" % weight_cv)
        return 1.0 + weight_cv * weight_cv, "weighting (Kish): 1 + %g^2" % weight_cv
    deff = 1.0 if args.deff is None else args.deff
    if deff < 1:
        raise InputError("--deff must be 1 or more (1 means a simple random sample), got %g" % deff)
    return deff, "given"


def deff_text(deff, how):
    if deff == 1:
        return "Design effect 1: no weighting or clustering. If the data will be weighted, pass --deff or --weight-cv."
    return "Design effect %g (%s): required n is multiplied by it, a given n divided by it." % (round(deff, 4), how)


def fpc_n(n0, population):
    """Finite population correction for a required n (Cochran): n0 / (1 + (n0 - 1) / N)."""
    return n0 / (1.0 + (n0 - 1.0) / population)


def fpc_factor(n, population):
    """Finite population correction for a standard error: sqrt((N - n) / (N - 1))."""
    return math.sqrt((population - n) / (population - 1.0))


def interval_n(n0, population, deff, notes=None):
    """Inflate by the design effect, then apply the finite population correction, and round up.

    With m = n0 deff, n = m N / (N - 1 + m) solves e = z sqrt(p q deff / n) sqrt((N - n)/(N - 1)) exactly,
    so the n returned and the margin the reverse command prints for it agree.
    """
    m = n0 * deff
    n = ceil_n(fpc_n(m, population) if population else m)
    if population and n >= population:
        n = int(population)
        if notes is not None:
            notes.append("The required n reaches the whole population of %d: survey everyone (a census)." % population)
    elif population and n0 / population < 0.05 and notes is not None:
        notes.append("n is under 5% of the population, so the finite population correction barely changes it.")
    return n


def interval_assumptions(confidence, deff, how, population):
    out = [
        "Confidence level %g%% (two-sided), normal approximation." % (confidence * 100),
        "Simple random sample from the population the result is reported for. For an opt-in or "
        "convenience sample the margin of error is a rough guide, not a guarantee.",
        deff_text(deff, how),
    ]
    if population:
        out.append("Finite population correction for a population of %d." % population)
    else:
        out.append("Large population: no finite population correction.")
    return out


def wald_margin(p, n, z, deff, population):
    se = math.sqrt(p * (1 - p) / (n / deff))
    if population:
        se *= fpc_factor(n, population)
    return z * se


def wilson_interval(p, n, z):
    """Wilson (1927) score interval for a proportion p observed (or expected) in n responses."""
    z2 = z * z
    denominator = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / denominator
    half = z / denominator * math.sqrt(p * (1 - p) / n + z2 / (4.0 * n * n))
    return max(0.0, centre - half), min(1.0, centre + half)


def achieved_margin(p, n, z, deff, population):
    """The precision the reverse proportion command reports for n: 0 for a census, the larger distance from p
    to an end of the Wilson interval when the smaller category expects under 10 responses, else the Wald margin."""
    if population and n >= population:
        return 0.0
    if (n / deff) * min(p, 1 - p) < SMALL_COUNT:
        low, high = wilson_interval(p, n / deff, z)
        return max(p - low, high - p)
    return wald_margin(p, n, z, deff, population)


def describe_sample(population, deff):
    text = "a simple random sample"
    text += " from a population of %d" % population if population else " from a large population"
    if deff != 1:
        text += ", with a design effect of %g" % round(deff, 4)
    return text


def cmd_proportion(args):
    if args.x is not None and args.n is None:
        raise InputError("--x (an observed count) needs --n")
    if args.margin is None and args.n is None:
        raise InputError("give --margin (to get n), --n (to get the margin of error), or both")
    confidence = fraction(args.confidence, "--confidence")
    deff, how = resolve_deff(args)
    population = check_population(args.population)
    if args.x is not None:
        if args.p is not None:
            raise InputError("give --x or --p, not both")
        if args.x < 0 or args.x > args.n:
            raise InputError("--x must be between 0 and --n, got %d of %s" % (args.x, args.n))
        p = args.x / float(positive(args.n, "--n"))
    else:
        p = fraction(0.5 if args.p is None else args.p, "--p")
    z = z_value(0.5 + confidence / 2.0)
    notes = []
    result = {"z": round(z, Z_DIGITS)}
    assumptions = ["Proportion p = %g%s." % (round(p, 4), " (the most cautious value: it gives the largest n)" if p == 0.5 else "")]
    assumptions += interval_assumptions(confidence, deff, how, population)
    sample = describe_sample(population, deff)
    statement = ""
    if args.margin is not None:
        margin = fraction(args.margin, "--margin")
        if not 0 < p < 1:
            raise InputError("an observed proportion of %g cannot be used to plan n; pass --p instead of --x" % p)
        n0 = z * z * p * (1 - p) / (margin * margin)
        result["n_infinite_population"] = round(n0, 2)
        n_req = interval_n(n0, population, deff, notes)
        # The first whole n the reverse command calls sufficient, checked in both directions.
        while n_req > 1 and achieved_margin(p, n_req - 1, z, deff, population) <= margin + EPS:
            n_req -= 1
        while achieved_margin(p, n_req, z, deff, population) > margin + EPS and not (population and n_req >= population):
            n_req += 1
        result["n_required"] = n_req
        if (n_req / deff) * min(p, 1 - p) < SMALL_COUNT and not (population and n_req >= population):
            result["planning_method"] = "wilson"
            notes.append("Under %d expected responses in the smaller category: n is the smallest that keeps the Wilson score interval within +/-%s points of %s%% on both sides, because the +/- (Wald) formula claims far too much precision there (Brown, Cai and DasGupta 2001)." % (SMALL_COUNT, pct(margin), pct(p)))
            statement = (
                "A sample of %d completed responses keeps the %g%% Wilson score interval for a proportion of %s%% within +/-%s percentage points on both sides, "
                "assuming %s (with fewer than %d expected responses in the smaller category a +/- margin from Cochran's formula would overstate the precision)."
                % (n_req, confidence * 100, pct(p), pct(margin), sample, SMALL_COUNT)
            )
        else:
            result["planning_method"] = "wald"
            statement = (
                "A sample of %d completed responses gives a margin of error of +/-%s percentage points at %g%% confidence for a proportion of %s%%, "
                "assuming %s (Cochran's formula, n = z^2 p(1-p)/e^2%s)."
                % (n_req, pct(margin), confidence * 100, pct(p), sample, " with the finite population correction" if population else "")
            )
    if args.n is not None:
        n = positive(args.n, "--n")
        if population and n > population:
            raise InputError("--n (%d) is larger than --population (%d)" % (n, population))
        n_eff = n / deff
        result["n"] = n
        if population and n == population:
            result.update({"interval_method": "census", "estimate": round(p, 4), "margin_of_error": 0.0})
            notes.append("Every member of the population responded: the percentage is exact, with no sampling error. Nonresponse to the question and measurement error still apply.")
            if args.margin is None:
                statement = "With all %d members of the population responding, %s is the population's percentage itself: there is no sampling error to report." % (
                    n, "%s%%" % pct(p) if args.x is not None else "every percentage")
        elif args.x is not None or n_eff * min(p, 1 - p) < SMALL_COUNT:
            low, high = wilson_interval(p, n_eff, z)
            result.update({"interval_method": "wilson", "estimate": round(p, 4), "interval_low": round(low, 4), "interval_high": round(high, 4)})
            notes.append("Wilson score interval: with fewer than %d expected responses in the smaller category a symmetric +/- margin is misleading. Report the interval, or the raw count." % SMALL_COUNT)
            if population:
                notes.append("The finite population correction is not applied to the Wilson interval: it treats the %d responses as drawn from a much larger population, so with %d of %d sampled it is wider than the true interval." % (n, n, population))
            if args.margin is None:
                statement = "With %d responses, an estimate of %s%% has a %g%% confidence interval from %s%% to %s%% (Wilson score interval), assuming %s." % (
                    n, pct(p), confidence * 100, pct(low), pct(high), sample)
        else:
            margin_given = wald_margin(p, n, z, deff, population)
            result["interval_method"] = "wald"
            result["margin_of_error"] = round(margin_given, 4)
            if args.margin is None:
                statement = "With %d responses, a result of %s%% has a margin of error of +/-%s percentage points at %g%% confidence, assuming %s (e = z sqrt(p(1-p)/n))." % (
                    n, pct(p), pct(margin_given), confidence * 100, sample)
        if args.margin is not None:
            result["sufficient"] = achieved_margin(p, n, z, deff, population) <= margin + EPS
    if args.table:
        if args.margin is None and 0 < p < 1:
            rows = []
            for factor in TABLE_N_FACTORS:
                n_row = max(1, int(round(args.n * factor)))
                if population and n_row > population:
                    continue
                rows.append({"n": n_row, "margin_of_error": round(wald_margin(p, n_row, z, deff, population), 4)})
            result["table"] = rows
        elif 0 < p < 1:
            result["table"] = [{"margin": m, "n_required": interval_n(z * z * p * (1 - p) / (m * m), population, deff)} for m in TABLE_MARGINS]
            if any(row["n_required"] / deff * min(p, 1 - p) < SMALL_COUNT for row in result["table"]):
                notes.append("Table rows with under %d expected responses in the smaller category use Cochran's formula only; run each margin on its own for the Wilson-based n." % SMALL_COUNT)
    return {
        "inputs": {"margin": args.margin, "n": args.n, "x": args.x, "p": round(p, 6), "confidence": confidence, "population": population, "deff": round(deff, 4)},
        "result": result,
        "statement": statement,
        "assumptions": assumptions,
        "notes": notes,
        "formula": "n0 = z^2 p(1-p) / e^2; m = n0 deff; with a population N: n = m / (1 + (m - 1)/N). "
        "Reverse: e = z sqrt(p(1-p) deff / n) sqrt((N - n)/(N - 1)); Wilson score interval when n min(p, 1-p) < 10 or a count is given; "
        "planning in that region takes the smallest n whose Wilson interval stays within +/-e of p.",
        "sources": ["Cochran 1977, Sampling Techniques, ch. 4", "Israel 1992, Determining Sample Size", "Kish 1965, Survey Sampling (design effect)", "Wilson 1927, JASA 22(158) (score interval)", "Brown, Cai and DasGupta 2001, Statistical Science 16(2)"],
    }


def cmd_mean(args):
    if args.margin is None and args.n is None:
        raise InputError("give --margin (to get n), --n (to get the margin of error), or both")
    confidence = fraction(args.confidence, "--confidence")
    sd = positive(args.sd, "--sd")
    deff, how = resolve_deff(args)
    population = check_population(args.population)
    z = z_value(0.5 + confidence / 2.0)
    notes = []
    result = {"z": round(z, Z_DIGITS)}
    assumptions = ["Standard deviation %g, in the same units as the margin; it is a planning guess, so check it against a pilot or an earlier wave." % sd]
    assumptions += interval_assumptions(confidence, deff, how, population)
    sample = describe_sample(population, deff)
    statement = ""
    if args.margin is not None:
        margin = positive(args.margin, "--margin")
        n0 = (z * sd / margin) ** 2
        result["n_infinite_population"] = round(n0, 2)
        n_req = interval_n(n0, population, deff, notes)

        def mean_margin(count):
            if population and count >= population:
                return 0.0
            return z * sd / math.sqrt(count / deff) * (fpc_factor(count, population) if population else 1.0)

        while n_req > 1 and mean_margin(n_req - 1) <= margin + EPS:
            n_req -= 1
        while mean_margin(n_req) > margin + EPS and not (population and n_req >= population):
            n_req += 1
        result["n_required"] = n_req
        statement = "A sample of %d completed responses gives a margin of error of +/-%g on the mean at %g%% confidence, assuming a standard deviation of %g and %s (n = (z SD/e)^2)." % (
            result["n_required"], margin, confidence * 100, sd, sample)
    if args.n is not None:
        n = positive(args.n, "--n")
        if population and n > population:
            raise InputError("--n (%d) is larger than --population (%d)" % (n, population))
        se = sd / math.sqrt(n / deff)
        if population:
            se *= fpc_factor(n, population)
        result["n"] = n
        result["margin_of_error"] = round(z * se, 4)
        if population and n == population:
            result["interval_method"] = "census"
            notes.append("Every member of the population responded: the mean is exact, with no sampling error.")
        if n < 30 and not (population and n == population):
            notes.append("n is under 30: use a t interval when you analyse, which is wider than this normal approximation.")
        if args.margin is not None:
            result["sufficient"] = n >= result["n_required"]
        else:
            statement = "With %d responses, the mean has a margin of error of +/-%g at %g%% confidence, assuming a standard deviation of %g and %s (e = z SD/sqrt(n))." % (
                n, round(z * se, 4), confidence * 100, sd, sample)
    return {
        "inputs": {"margin": args.margin, "n": args.n, "sd": sd, "confidence": confidence, "population": population, "deff": round(deff, 4)},
        "result": result,
        "statement": statement,
        "assumptions": assumptions,
        "notes": notes,
        "formula": "n0 = (z sd / e)^2; m = n0 deff; with a population N: n = m / (1 + (m - 1)/N). "
        "Reverse: e = z sd sqrt(deff / n) sqrt((N - n)/(N - 1)).",
        "sources": ["Cochran 1977, Sampling Techniques, ch. 4", "Illowsky and Dean, Introductory Statistics (OpenStax), section 8.1"],
    }


class TwoGroupTest:
    """n for group 1 is (z_a s0 + z_b s1)^2 / effect^2 (+ a correction); group 2 is ratio times that."""

    def __init__(self, method, ratio, z_alpha, z_beta, continuity=False, sides=2):
        self.sides = sides
        self.method = method
        self.ratio = ratio
        self.z_alpha = z_alpha
        self.z_beta = z_beta
        self.continuity = continuity
        self.k = 1.0 + 1.0 / ratio

    def parts(self, p1, p2):
        """(effect, s0, s1) for two proportions."""
        separate = math.sqrt(p1 * (1 - p1) + p2 * (1 - p2) / self.ratio)
        if self.method == "arcsine":
            effect = abs(2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2)))
            return effect, math.sqrt(self.k), math.sqrt(self.k)
        if self.method == "pooled":
            p_bar = (p1 + self.ratio * p2) / (1.0 + self.ratio)
            return abs(p1 - p2), math.sqrt(self.k * p_bar * (1 - p_bar)), separate
        if self.method == "baseline":
            return abs(p1 - p2), math.sqrt(self.k * p1 * (1 - p1)), separate
        return abs(p1 - p2), separate, separate

    def n_from_parts(self, effect, s0, s1):
        n = (self.z_alpha * s0 + self.z_beta * s1) ** 2 / effect**2
        if self.continuity:
            n = n / 4.0 * (1 + math.sqrt(1 + 2.0 * self.k / (n * effect))) ** 2
        return n

    def power_from_parts(self, effect, s0, s1, n):
        if self.continuity:
            shift = self.k / (2.0 * effect)
            if n <= shift:
                return 0.0
            n = (n - shift) ** 2 / n
        power = phi((effect * math.sqrt(n) - self.z_alpha * s0) / s1)
        if self.sides == 2:
            # A two-sided test also rejects in the wrong direction (R's strict = TRUE).
            power += phi((-effect * math.sqrt(n) - self.z_alpha * s0) / s1)
        return power

    def n_props(self, p1, p2):
        return self.n_from_parts(*self.parts(p1, p2))

    def power_props(self, p1, p2, n):
        effect, s0, s1 = self.parts(p1, p2)
        return self.power_from_parts(effect, s0, s1, n)

    def correction(self):
        """Guenther's small-sample correction for a t test, per group 1."""
        return self.z_alpha**2 / (2.0 * (1.0 + self.ratio))

    def n_standardised(self, effect, t_test):
        root_k = math.sqrt(self.k)
        return self.n_from_parts(effect, root_k, root_k) + (self.correction() if t_test else 0.0)

    def power_standardised(self, effect, n, t_test):
        n = n - (self.correction() if t_test else 0.0)
        if n <= 0:
            return 0.0
        power = phi(effect * math.sqrt(n / self.k) - self.z_alpha)
        if self.sides == 2:
            power += phi(-effect * math.sqrt(n / self.k) - self.z_alpha)
        return power

    def detectable_standardised(self, n, t_test):
        n = n - (self.correction() if t_test else 0.0)
        if n <= 0:
            return None
        return (self.z_alpha + self.z_beta) * math.sqrt(self.k / n)

    def detectable_p2(self, p1, n, direction):
        """Bisection for the p2 nearest p1 whose required n for group 1 is at most n."""
        edge = 1.0 - 1e-9 if direction == "up" else 1e-9
        if self.n_props(p1, edge) > n:
            return None
        near, far = p1, edge
        for _ in range(200):
            mid = (near + far) / 2.0
            if self.n_props(p1, mid) > n:
                near = mid
            else:
                far = mid
        return far


def group_sizes(raw_n1, ratio, deff):
    n1 = ceil_n(raw_n1 * deff)
    n2 = ceil_n(raw_n1 * ratio * deff)
    return n1, n2


def cmd_compare(args):
    alpha = fraction(args.alpha, "--alpha")
    power = fraction(args.power, "--power")
    if power <= 0.5:
        raise InputError("--power must be above 0.5, got %g" % power)
    deff, how = resolve_deff(args)
    comparisons = positive(args.comparisons, "--comparisons")
    alpha_each = alpha / comparisons
    z_alpha = z_value(1 - alpha_each / args.sides)
    z_beta = z_value(power)
    if args.n is not None:
        positive(args.n, "--n")
    if args.n2 is not None:
        positive(args.n2, "--n2")
        if args.n is None:
            raise InputError("--n2 needs --n (the size of group 1)")
        if args.ratio is not None:
            raise InputError("give --ratio or --n2, not both")
        ratio = args.n2 / float(args.n)
    else:
        ratio = 1.0 if args.ratio is None else positive(args.ratio, "--ratio")
    equal = abs(ratio - 1.0) < EPS
    sided = "two-sided" if args.sides == 2 else "one-sided"
    notes = []
    result = {"z_alpha": round(z_alpha, Z_DIGITS), "z_beta": round(z_beta, Z_DIGITS)}
    assumptions = ["Significance level alpha = %g, %s; power %g%%." % (alpha, sided, power * 100)]
    if comparisons > 1:
        result["alpha_per_comparison"] = round(alpha_each, 6)
        assumptions.append(
            "Bonferroni correction for %d comparisons: each is tested at alpha/%d = %g. It is conservative (it asks for somewhat more than needed), more so when the comparisons are correlated."
            % (comparisons, comparisons, round(alpha_each, 6)))
    else:
        assumptions.append("One planned comparison. For several, pass --comparisons m: K - 1 for K groups against one control, K(K - 1)/2 for all pairs.")
    assumptions.append(
        "Two independent groups, %s, each a simple random sample. The same respondents measured twice need a paired test (McNemar's test or a paired t test), which this does not size."
        % ("equal sizes" if equal else "group 2 = %g x group 1" % round(ratio, 4)))
    assumptions.append(deff_text(deff, how))

    kinds = [args.p1 is not None or args.p2 is not None or args.lift is not None, args.h is not None, args.d is not None or args.diff is not None or args.sd is not None]
    if sum(kinds) > 1:
        raise InputError("give proportions (--p1 with --p2 or --lift), or --h, or means (--d, or --diff with --sd), not both")
    is_props, is_h = kinds[0], kinds[1]
    method = args.variance
    if args.continuity and (not is_props or method == "arcsine"):
        raise InputError("--continuity applies to proportions with --variance pooled, unpooled or baseline")
    test = TwoGroupTest(method, ratio, z_alpha, z_beta, args.continuity, args.sides)
    inputs = {"alpha": alpha, "power": power, "sides": args.sides, "comparisons": comparisons, "ratio": round(ratio, 6), "deff": round(deff, 4), "n": args.n}
    n_given = None if args.n is None else args.n / deff
    key_n = "n_per_group" if equal else "n_group_1"
    tail = "alpha %g %s%s, power %g%%" % (alpha, sided, " with a Bonferroni correction for %d comparisons" % comparisons if comparisons > 1 else "", power * 100)
    statement = ""

    def report_n(raw):
        n1, n2 = group_sizes(raw, ratio, deff)
        result[key_n + "_unrounded"] = round(raw, 2)
        result[key_n] = n1
        if not equal:
            result["n_group_2"] = n2
        result["n_total"] = n1 + n2
        return n1, n2

    def sizes_text(n1, n2):
        return "%d completed responses per group (%d in total)" % (n1, n1 + n2) if equal else "%d and %d completed responses in the two groups (%d in total)" % (n1, n2, n1 + n2)

    def report_power(value):
        result["power_at_n"] = round(value, 3)
        if args.sides == 2:
            notes.append("Two-sided power counts a significant result in either direction (R power.prop.test with strict = TRUE); R's default strict = FALSE leaves out the small chance of rejecting in the wrong direction. The required n uses the usual one-tail approximation, so power at that n can be slightly above the target.")
        result["sufficient"] = args.n >= result[key_n]
        notes.append("Power here is for the difference you assume before fielding. Do not compute it afterwards from the observed difference: that only restates the p-value.")

    if is_props:
        if args.p1 is None:
            raise InputError("--p1 is required for a comparison of proportions")
        p1 = fraction(args.p1, "--p1")
        if args.p2 is not None and args.lift is not None:
            raise InputError("give --p2 or --lift, not both")
        p2 = args.p2
        if args.lift is not None:
            if args.lift == 0:
                raise InputError("--lift is 0: there is no difference to detect")
            p2 = p1 * (1 + args.lift)
            if not 0 < p2 < 1:
                raise InputError("--lift %g on --p1 %g gives p2 = %g, which is not a proportion" % (args.lift, p1, p2))
            result["p2_from_lift"] = round(p2, 4)
        inputs.update({"p1": p1, "p2": args.p2, "lift": args.lift, "variance": method, "continuity": args.continuity})
        described = {
            "pooled": ("n1 = [z_a sqrt((1 + 1/r) pbar qbar) + z_b sqrt(p1 q1 + p2 q2 / r)]^2 / (p1 - p2)^2, pbar = (p1 + r p2)/(1 + r), n2 = r n1",
                       "Normal-approximation test; pooled variance under the null, separate variances under the alternative (Fleiss, Levin and Paik).", "the pooled-variance normal approximation"),
            "unpooled": ("n1 = (z_a + z_b)^2 (p1 q1 + p2 q2 / r) / (p1 - p2)^2, n2 = r n1",
                         "Normal-approximation test with separate (unpooled) variances under both hypotheses.", "the unpooled-variance normal approximation"),
            "baseline": ("n1 = [z_a sqrt((1 + 1/r) p1 q1) + z_b sqrt(p1 q1 + p2 q2 / r)]^2 / (p1 - p2)^2, n2 = r n1",
                         "Null variance from the baseline p1 alone, separate variances under the alternative (the formula in Evan Miller's A/B calculator, which rounds to the nearest whole number; this rounds up).", "the baseline-variance normal approximation"),
            "arcsine": ("n1 = (1 + 1/r) (z_a + z_b)^2 / h^2, h = |2 asin(sqrt(p1)) - 2 asin(sqrt(p2))|, n2 = r n1",
                        "Arcsine-transformed proportions, Cohen's effect size h (as in R pwr.2p.test).", "Cohen's arcsine effect size h"),
        }[method]
        formula = described[0]
        assumptions.append(described[1])
        if args.continuity:
            formula += "; then n1' = (n1/4) [1 + sqrt(1 + 2 (1 + 1/r)/(n1 |p1 - p2|))]^2"
            assumptions.append("Continuity correction applied (for a continuity-corrected chi-square or Fisher's exact test).")
        elif method != "arcsine":
            assumptions.append("No continuity correction (pass --continuity if the analysis will use one).")
        if p2 is not None:
            p2 = fraction(p2, "--p2")
            if p1 == p2:
                raise InputError("--p1 and --p2 are equal: there is no difference to detect")
            raw = test.n_props(p1, p2)
            result["difference"] = round(abs(p1 - p2), 4)
            n1, n2 = report_n(raw)
            # Expected counts in each group's smaller category, each at its own group size.
            if min(raw * min(p1, 1 - p1), raw * ratio * min(p2, 1 - p2)) < 5:
                notes.append("Fewer than 5 expected responses in a cell: the normal approximation is poor; plan with an exact method.")
            statement = "%s are needed to detect a difference between %s%% and %s%% (%s, %s%s)." % (
                sizes_text(n1, n2).capitalize(), pct(p1), pct(p2), tail, described[2], ", continuity-corrected" if args.continuity else "")
            if args.n is not None:
                report_power(test.power_props(p1, p2, n_given))
            if args.table:
                rows = []
                for step in TABLE_DIFFERENCES:
                    p_row = p1 + step if p2 > p1 else p1 - step
                    if 0 < p_row < 1:
                        row = {"p2": round(p_row, 4), "difference": step, key_n: group_sizes(test.n_props(p1, p_row), ratio, deff)[0]}
                        if args.n is not None:
                            row["power_at_n"] = round(test.power_props(p1, p_row, n_given), 3)
                        rows.append(row)
                result["table"] = rows
        elif args.n is not None:
            found = test.detectable_p2(p1, n_given, args.direction)
            if found is None:
                raise InputError("with n = %d in group 1 no %s difference from p1 = %g is detectable at this alpha and power" % (args.n, "upward" if args.direction == "up" else "downward", p1))
            result["detectable_p2"] = round(found, 4)
            result["minimum_detectable_difference"] = round(abs(found - p1), 4)
            assumptions.append("Smallest detectable difference searched %s from p1 = %g." % ("upward" if args.direction == "up" else "downward", p1))
            statement = "With %d responses in %s, the smallest difference from %s%% detectable is %s percentage points (%s, %s)." % (
                args.n, "each group" if equal else "group 1 and %d in group 2" % int(round(args.n * ratio)), pct(p1), pct(abs(found - p1)), tail, described[2])
        else:
            raise InputError("give --p2 or --lift (to get n), --n (to get the smallest detectable difference), or both (to get power)")
        sources = ["Fleiss, Levin and Paik 2003, Statistical Methods for Rates and Proportions, ch. 4", "R stats::power.prop.test (same uncorrected pooled formula)"]
        if method == "arcsine":
            sources = ["Cohen 1988, Statistical Power Analysis for the Behavioral Sciences, ch. 6", "Champely, pwr package vignette (pwr.2p.test, pwr.2p2n.test)"]
        if method == "baseline":
            sources.append("Evan Miller, Sample Size Calculator (page source)")
    else:
        if args.d is not None and (args.diff is not None or args.sd is not None):
            raise InputError("give --d, or --diff with --sd, not both")
        if (args.diff is None) != (args.sd is None):
            raise InputError("--diff and --sd go together")
        t_test = not is_h
        if is_h:
            effect, name = args.h, "h"
            formula = "n1 = (1 + 1/r) (z_a + z_b)^2 / h^2, n2 = r n1"
            assumptions.append("Arcsine-transformed proportions, Cohen's effect size h (as in R pwr.2p.test).")
            sources = ["Cohen 1988, Statistical Power Analysis for the Behavioral Sciences, ch. 6", "Champely, pwr package vignette (pwr.2p.test, pwr.2p2n.test)"]
            what = "an effect size of h = %g"
        else:
            name = "d"
            formula = "n1 = (1 + 1/r) (z_a + z_b)^2 / d^2 + z_a^2 / (2 (1 + r)), d = difference / SD, n2 = r n1"
            assumptions.append("Two-sample t test, equal standard deviations in both groups; normal-approximation n plus Guenther's small-sample correction (z_a^2/4 per group when the groups are equal).")
            sources = ["Cohen 1988, Statistical Power Analysis for the Behavioral Sciences, ch. 2", "Guenther 1981, The American Statistician 35(4)"]
            what = "a difference between two means of d = %g standard deviations"
            if args.diff is not None:
                sd = positive(args.sd, "--sd")
                if args.diff == 0:
                    raise InputError("--diff is 0: there is no difference to detect")
                effect = abs(args.diff) / sd
            else:
                effect = args.d
        inputs.update({"d": args.d, "diff": args.diff, "sd": args.sd, "h": args.h})
        if effect is not None:
            effect = abs(effect)
            if not effect > 0:
                raise InputError("--%s must not be 0: there is no difference to detect" % name)
            result["effect_size_" + name] = round(effect, 4)
            if t_test:
                result[key_n + "_normal_approximation"] = ceil_n(test.n_standardised(effect, False) * deff)
            n1, n2 = report_n(test.n_standardised(effect, t_test))
            statement = "%s are needed to detect %s (%s%s)." % (
                sizes_text(n1, n2).capitalize(), what % round(effect, 4), tail, ", two-sample t test, normal approximation with Guenther's correction" if t_test else ", normal approximation")
            if args.n is not None:
                report_power(test.power_standardised(effect, n_given, t_test))
            if args.table and t_test:
                rows = []
                for d_row in TABLE_D:
                    row = {"d": d_row, key_n: group_sizes(test.n_standardised(d_row, True), ratio, deff)[0]}
                    if args.n is not None:
                        row["power_at_n"] = round(test.power_standardised(d_row, n_given, True), 3)
                    rows.append(row)
                result["table"] = rows
        elif args.n is not None:
            found = test.detectable_standardised(n_given, True)
            if found is None:
                raise InputError("--n is too small to compute a detectable difference")
            result["minimum_detectable_d"] = round(found, 4)
            notes.append("d is the difference in standard deviations: multiply by the SD of your scale to get scale points.")
            statement = "With %d responses in %s, the smallest difference between two means detectable is d = %g standard deviations (%s, two-sample t test)." % (
                args.n, "each group" if equal else "group 1 and %d in group 2" % int(round(args.n * ratio)), round(found, 4), tail)
        else:
            raise InputError("give --p1 with --p2 or --lift (proportions), --d or --diff with --sd (means), or --n for the reverse")
    return {"inputs": inputs, "result": result, "statement": statement, "assumptions": assumptions, "notes": notes, "formula": formula, "sources": sources}


def cmd_gap(args):
    confidence = fraction(args.confidence, "--confidence")
    p1 = fraction(args.p1, "--p1")
    p2 = fraction(args.p2, "--p2")
    if p1 + p2 > 1 + EPS:
        raise InputError("--p1 and --p2 are two answers to the same question, so they cannot sum to more than 1")
    deff, how = resolve_deff(args)
    n = positive(args.n, "--n")
    if n / deff <= 1:
        raise InputError("--n is too small")
    z = z_value(0.5 + confidence / 2.0)
    variance_term = p1 + p2 - (p1 - p2) ** 2
    margin = z * math.sqrt(variance_term / (n / deff - 1.0))
    difference = abs(p1 - p2)
    result = {"difference": round(difference, 4), "margin_of_error_of_difference": round(margin, 4), "difference_exceeds_margin": difference > margin}
    if difference > 0:
        result["n_for_this_gap_to_exceed_margin"] = ceil_n((z * z * variance_term / difference**2 + 1.0) * deff)
    single = z * math.sqrt(0.25 / (n / deff))
    statement = "In a sample of %d, the gap between %s%% and %s%% (%s points) has a margin of error of +/-%s points at %g%% confidence, so the gap is %s the margin (difference of two shares of one question, multinomial variance)." % (
        n, pct(p1), pct(p2), pct(difference), pct(margin), confidence * 100, "outside" if difference > margin else "within")
    return {
        "inputs": {"p1": p1, "p2": p2, "n": n, "confidence": confidence, "deff": round(deff, 4)},
        "result": result,
        "statement": statement,
        "assumptions": [
            "Both shares come from the same question in the same sample (one answer per respondent), so they are negatively correlated.",
            "Confidence level %g%% (two-sided), simple random sample." % (confidence * 100),
            deff_text(deff, how),
        ],
        "notes": ["The margin for the gap is not the survey's usual margin (+/-%s points here) and not twice it; it depends on how much of the sample chose either answer." % pct(single)],
        "formula": "e = z sqrt((p1 + p2 - (p1 - p2)^2) / (n - 1))",
        "sources": ["Franklin 2007, The 'Margin of Error' for Differences in Polls (adapted from Kish 1965, pp. 498-501)"],
    }


def parse_shares(items):
    """'0.15' or 'name=0.15' -> [(name, share)]."""
    out = []
    for index, item in enumerate(items, 1):
        name, _, value = item.rpartition("=")
        try:
            share = float(value)
        except ValueError:
            raise InputError("--share takes numbers or name=number, got %r" % item)
        out.append((name or "subgroup %d" % index, fraction(share, "--share", allow_one=True)))
    return out


def cmd_subgroups(args):
    shares = parse_shares(args.share)
    confidence = fraction(args.confidence, "--confidence")
    deff, how = resolve_deff(args)
    z = z_value(0.5 + confidence / 2.0)
    if args.margin is not None:
        if args.min_base is not None:
            raise InputError("give --margin or --min-base, not both")
        margin = fraction(args.margin, "--margin")
        min_base = ceil_n(z * z * 0.25 / (margin * margin) * deff)
        base_text = "Base per subgroup %d: the n for +/-%s points at p = 0.5, %g%% confidence%s." % (
            min_base, pct(margin), confidence * 100, ", times the design effect %g" % round(deff, 4) if deff != 1 else "")
    else:
        min_base = positive(SUBGROUP_MIN_BASE if args.min_base is None else args.min_base, "--min-base")
        base_text = "Minimum base %d per reported subgroup%s." % (min_base, " (Sudman's rule for major subgroups)" if min_base == SUBGROUP_MIN_BASE else "")
    smallest_name, smallest = min(shares, key=lambda item: item[1])
    total = ceil_n(min_base / smallest)
    table = []
    for name, share in shares:
        expected = total * share
        table.append({
            "subgroup": name,
            "share": share,
            "required_total": ceil_n(min_base / share),
            "expected_n": round(expected, 1),
            "margin_of_error": round(z * math.sqrt(0.25 * deff / expected), 4),
        })
    notes = ["These are expected counts. Without a quota the smallest subgroup lands below %d about half the time: set quotas at the expected n, or add a margin." % min_base]
    if len(shares) > 1 and sum(share for _, share in shares) > 1 + EPS:
        notes.append("The shares sum to more than 1: fine for overlapping subgroups, a mistake for exclusive ones.")
    result = {
        "smallest_share": smallest,
        "min_base": min_base,
        "n_total": total,
        "expected_smallest_subgroup": round(total * smallest, 1),
        "subgroup_margin_of_error_at_min_base": round(z * math.sqrt(0.25 * deff / min_base), 4),
        "quota_table": table,
    }
    statement = "A total of %d completed responses gives an expected %d or more in every reported subgroup (smallest: %s at %s%% of the sample), which is +/-%s percentage points at %g%% confidence within that subgroup." % (
        total, min_base, smallest_name, pct(smallest), pct(result["subgroup_margin_of_error_at_min_base"]), confidence * 100)
    return {
        "inputs": {"shares": [share for _, share in shares], "names": [name for name, _ in shares], "min_base": args.min_base, "margin": args.margin, "confidence": confidence, "deff": round(deff, 4)},
        "result": result,
        "statement": statement,
        "assumptions": [
            base_text,
            "Each subgroup's share of completes equals the share given here; no quota or oversample.",
            "Margins of error: p = 0.5, %g%% confidence, simple random sample within the subgroup." % (confidence * 100),
            deff_text(deff, how),
        ],
        "notes": notes,
        "formula": "required total for a subgroup = base / its share; n_total = the largest of these",
        "sources": ["Sudman 1976, Applied Sampling (100 per major subgroup, 20 to 50 per minor one)", "Cochran 1977, Sampling Techniques, ch. 4 (margin of error)"],
    }


def cmd_check(args):
    n = positive(args.n, "--n")
    confidence = fraction(args.confidence, "--confidence")
    alpha = fraction(args.alpha, "--alpha")
    power = fraction(args.power, "--power")
    if power <= 0.5:
        raise InputError("--power must be above 0.5, got %g" % power)
    p = fraction(args.p, "--p")
    deff, how = resolve_deff(args)
    z = z_value(0.5 + confidence / 2.0)
    notes = []
    n_eff = n / deff
    result = {"n": n}

    population = check_population(args.population)
    if population and n > population:
        raise InputError("--n (%d) is larger than --population (%d)" % (n, population))

    def describe(count, target):
        if count * min(p, 1 - p) < SMALL_COUNT:
            low, high = wilson_interval(p, count, z)
            target.update({"interval_method": "wilson", "interval_low": round(low, 4), "interval_high": round(high, 4)})
            return "a %g%% interval from %s%% to %s%%" % (confidence * 100, pct(low), pct(high))
        target["margin_of_error"] = round(z * math.sqrt(p * (1 - p) / count), 4)
        return "+/-%s points" % pct(target["margin_of_error"])

    overall = {}
    if population and n == population:
        overall.update({"interval_method": "census", "margin_of_error": 0.0})
        overall_text = "no sampling error (every member of the population of %d responded)" % population
    elif population and n_eff * min(p, 1 - p) >= SMALL_COUNT:
        overall["margin_of_error"] = round(wald_margin(p, n, z, deff, population), 4)
        overall_text = "+/-%s points" % pct(overall["margin_of_error"])
    else:
        overall_text = describe(n_eff, overall)
    result["overall"] = overall
    parts = ["overall percentages have %s" % overall_text]
    if args.share:
        name, share = min(parse_shares(args.share), key=lambda item: item[1])
        smallest = {"subgroup": name, "share": share, "expected_n": round(n * share, 1)}
        parts.append("the smallest subgroup (%s, about %d responses) has %s" % (name, int(round(n * share)), describe(n_eff * share, smallest)))
        result["smallest_subgroup"] = smallest
        if n * share < 30:
            notes.append("The smallest subgroup is expected to have under 30 responses: report counts, not percentages, for it.")
    half = n // 2
    test = TwoGroupTest("pooled", 1.0, z_value(1 - alpha / 2.0), z_value(power))
    halves = {"n_per_half": half}
    if half >= 2:
        found = test.detectable_p2(p, half / deff, "up")
        if found is None:
            found = test.detectable_p2(p, half / deff, "down")
        if found is not None:
            halves["detectable_p2"] = round(found, 4)
            halves["minimum_detectable_difference"] = round(abs(found - p), 4)
            parts.append("two halves of %d can detect a difference of %s points or more from %s%%" % (half, pct(abs(found - p)), pct(p)))
        else:
            notes.append("Two halves of %d cannot detect any difference in a percentage at this alpha and power." % half)
        d_min = test.detectable_standardised(half / deff, True)
        if d_min is not None:
            halves["minimum_detectable_d"] = round(d_min, 4)
    result["two_equal_halves"] = halves
    statement = "With n = %d: %s (%g%% confidence; alpha %g two-sided, power %g%%; simple random sample%s)." % (
        n, "; ".join(parts), confidence * 100, alpha, power * 100, "" if deff == 1 else ", design effect %g" % round(deff, 4))
    return {
        "inputs": {"n": n, "shares": args.share, "p": p, "confidence": confidence, "alpha": alpha, "power": power, "deff": round(deff, 4), "population": population},
        "result": result,
        "statement": statement,
        "assumptions": [
            "Percentages near p = %g; %g%% confidence; %s." % (p, confidence * 100, "finite population correction for the overall margin, population %d" % population if population else "large population"),
            "Detectable difference: two independent halves of the sample, alpha %g two-sided, power %g%%, pooled-variance test for percentages and a t test for means (d, in standard deviations)." % (alpha, power * 100),
            "Simple random sample; for an opt-in sample read every margin as a rough guide.",
            deff_text(deff, how),
        ],
        "notes": notes,
        "formula": "e = z sqrt(p(1-p)/n), or the Wilson interval when n min(p, 1-p) < 10; detectable difference from the two-proportion and two-mean formulas of the compare command",
        "sources": ["Cochran 1977, Sampling Techniques, ch. 4", "Wilson 1927, JASA 22(158)", "Fleiss, Levin and Paik 2003, ch. 4", "Guenther 1981, The American Statistician 35(4)"],
    }


def cmd_invites(args):
    completes = positive(args.completes, "--completes")
    removal = fraction(args.removal_rate, "--removal-rate", allow_zero=True)
    rates = [
        ("deliverability", fraction(args.deliverability, "--deliverability", allow_one=True)),
        ("response_rate", fraction(args.response_rate, "--response-rate", allow_one=True)),
        ("incidence", fraction(args.incidence, "--incidence", allow_one=True)),
        ("completion_rate", fraction(args.completion_rate, "--completion-rate", allow_one=True)),
    ]
    to_collect = ceil_n(completes / (1.0 - removal))
    remaining = completes / (1.0 - removal)
    funnel = {"usable_completes": completes, "completes_to_collect": to_collect}
    for name, rate in reversed(rates):
        remaining = remaining / rate
        funnel["needed_before_" + name] = ceil_n(remaining)
    yield_rate = 1.0 - removal
    for _, rate in rates:
        yield_rate *= rate
    invites = ceil_n(completes / yield_rate)
    defaults = [name for name, rate in rates if rate == 1.0]
    notes = []
    if defaults:
        notes.append("Taken as 100%%: %s. Pass a value if any of them is lower." % ", ".join(defaults))
    if removal == 0:
        notes.append("No allowance for responses removed in cleaning; pass --removal-rate with your own rate if you screen for quality.")
    statement = "To end with %d usable completes, send %d invitations (overall yield %s%%: %s%s)." % (
        completes, invites, pct(yield_rate), ", ".join("%s %s%%" % (name.replace("_", " "), pct(rate)) for name, rate in rates if rate != 1.0) or "all rates 100%",
        ", %s%% of completes removed in cleaning" % pct(removal) if removal else "")
    return {
        "inputs": dict([("completes", completes)] + rates + [("removal_rate", removal)]),
        "result": {"invitations": invites, "completes_to_collect": to_collect, "overall_yield": round(yield_rate, 4), "funnel": funnel},
        "statement": statement,
        "assumptions": [
            "Response rate = people who start the survey / invitations delivered.",
            "Incidence = starters who qualify; completion rate = qualified starters who finish.",
            "Removal rate = completed responses dropped in data cleaning; it is your own rate, no default is assumed.",
            "The rates are planning guesses and independent of each other; use your own past sends where you have them.",
        ],
        "notes": notes,
        "formula": "invitations = completes / ((1 - removal rate) x deliverability x response rate x incidence x completion rate)",
        "sources": ["AAPOR Standard Definitions (response, cooperation and eligibility rates)"],
    }


def cmd_nps(args):
    """NPS = share of promoters - share of detractors, scored +1/0/-1 per respondent (Rocks 2016)."""
    confidence = fraction(args.confidence, "--confidence")
    deff, how = resolve_deff(args)
    population = check_population(args.population)
    given = (args.promoters is not None, args.detractors is not None)
    if any(given) and not all(given):
        raise InputError("--promoters and --detractors go together")
    if all(given):
        if args.variance is not None:
            raise InputError("give --promoters with --detractors, or --variance, not both")
        pro = fraction(args.promoters, "--promoters", allow_zero=True)
        det = fraction(args.detractors, "--detractors", allow_zero=True)
        if pro + det > 1 + EPS:
            raise InputError("--promoters and --detractors are shares of one sample and cannot sum to more than 1")
        variance = pro + det - (pro - det) ** 2
        basis = "Variance %g from %s%% promoters and %s%% detractors: p_pro + p_det - NPS^2 (Rocks 2016)." % (round(variance, 4), pct(pro), pct(det))
    elif args.variance is not None:
        variance = fraction(args.variance, "--variance", allow_one=True)
        basis = "Variance %g, as given (the score's variance on the +1/0/-1 scale, at most 1)." % variance
    else:
        variance = NPS_DEFAULT_VARIANCE
        basis = "Variance %g: MeasuringU's realistic maximum (observed 0.40 to 0.76 across 18 data sets; Lewis and Sauro 2021c). Pass --promoters and --detractors from an earlier wave to use your own." % variance
    if not variance > 0:
        raise InputError("the variance is 0 (every answer in one category): there is no sampling spread to plan for")
    z = z_value(0.5 + confidence / 2.0)
    notes = []
    result = {"variance": round(variance, 4), "z": round(z, Z_DIGITS)}
    assumptions = [basis, "NPS in points = 100 x (share of promoters - share of detractors); margins below are in NPS points."]
    sample = describe_sample(population, deff)
    statement = ""
    if args.diff is not None:
        if args.margin is not None:
            raise InputError("give --diff (compare two scores) or --margin (one score), not both")
        alpha = fraction(args.alpha, "--alpha")
        power = fraction(args.power, "--power")
        if power <= 0.5:
            raise InputError("--power must be above 0.5, got %g" % power)
        diff = abs(args.diff)
        if not 0 < diff <= 2:
            raise InputError("--diff is a difference in NPS as a proportion (0.1 = 10 points), above 0 and at most 2")
        z_alpha = z_value(1 - alpha / args.sides)
        z_beta = z_value(power)
        raw = (z_alpha + z_beta) ** 2 * 2 * variance / diff ** 2
        n_group = ceil_n(raw * deff)
        result.update({"difference": diff, "n_per_group": n_group, "n_total": 2 * n_group})
        assumptions += ["Two independent groups of equal size with the same variance; alpha %g %s, power %g%%." % (alpha, "two-sided" if args.sides == 2 else "one-sided", power * 100),
                        deff_text(deff, how)]
        statement = "%d completed responses per group (%d in total) are needed to detect a difference of %s NPS points between two independent groups (alpha %g %s, power %g%%, NPS variance %g; normal approximation)." % (
            n_group, 2 * n_group, pct(diff), alpha, "two-sided" if args.sides == 2 else "one-sided", power * 100, round(variance, 4))
        if args.n is not None:
            n_eff = positive(args.n, "--n") / deff
            shift = diff * math.sqrt(n_eff / (2 * variance))
            achieved = phi(shift - z_alpha) + (phi(-shift - z_alpha) if args.sides == 2 else 0.0)
            result.update({"n": args.n, "power_at_n": round(achieved, 3), "sufficient": args.n >= n_group})
            notes.append("Power is for the difference assumed before fielding, never for an observed one.")
        if args.table:
            rows = []
            for step in NPS_TABLE_DIFFERENCES:
                row = {"difference": step, "n_per_group": ceil_n((z_alpha + z_beta) ** 2 * 2 * variance / step ** 2 * deff)}
                if args.n is not None:
                    shift_row = step * math.sqrt(n_eff / (2 * variance))
                    row["power_at_n"] = round(phi(shift_row - z_alpha) + (phi(-shift_row - z_alpha) if args.sides == 2 else 0.0), 3)
                rows.append(row)
            result["table"] = rows
        notes.append("Lewis and Sauro (2021c) give the same formula and subtract 3 per group when the analysis uses the adjusted-Wald test (which adds 3); this keeps the 3 as a margin.")
        formula = "n per group = (z_a + z_b)^2 (Var1 + Var2) / diff^2 with Var1 = Var2 (Lewis and Sauro 2021c, without their -3)"
        sources = ["Rocks 2016, The American Statistician 70(4) (NPS variance)", "Lewis and Sauro 2021b, How to statistically compare two Net Promoter Scores (MeasuringU)", "Lewis and Sauro 2021c, Sample sizes for comparing Net Promoter Scores (MeasuringU)"]
    else:
        if args.margin is None and args.n is None:
            raise InputError("give --margin (to get n), --n (to get the margin), or --diff (to compare two scores)")
        assumptions += interval_assumptions(confidence, deff, how, population)
        if args.margin is not None:
            margin = fraction(args.margin, "--margin")
            n0 = z * z * variance / (margin * margin)
            result["n_infinite_population"] = round(n0, 2)
            result["n_required"] = interval_n(n0, population, deff, notes)
            statement = "A sample of %d completed responses gives a margin of error of +/-%s NPS points at %g%% confidence, assuming an NPS variance of %g and %s (n = z^2 Var / e^2)." % (
                result["n_required"], pct(margin), confidence * 100, round(variance, 4), sample)
        if args.n is not None:
            n = positive(args.n, "--n")
            if population and n > population:
                raise InputError("--n (%d) is larger than --population (%d)" % (n, population))
            margin_given = z * math.sqrt(variance * deff / n) * (fpc_factor(n, population) if population else 1.0)
            result.update({"n": n, "margin_of_error": round(margin_given, 4)})
            if args.margin is not None:
                result["sufficient"] = margin_given <= args.margin + EPS
            else:
                statement = "With %d responses, an NPS has a margin of error of +/-%s points at %g%% confidence, assuming an NPS variance of %g and %s (e = z sqrt(Var/n))." % (
                    n, pct(margin_given), confidence * 100, round(variance, 4), sample)
            if n < 30:
                notes.append("Under 30 responses: report the adjusted-Wald interval from the nps-analysis skill rather than this normal approximation (Rocks 2016).")
        if args.table:
            if args.margin is None:
                rows = []
                for factor in TABLE_N_FACTORS:
                    n_row = max(1, int(round(args.n * factor)))
                    if population and n_row > population:
                        continue
                    rows.append({"n": n_row, "margin_of_error": round(z * math.sqrt(variance * deff / n_row) * (fpc_factor(n_row, population) if population else 1.0), 4)})
                result["table"] = rows
            else:
                result["table"] = [{"margin": m, "n_required": interval_n(z * z * variance / (m * m), population, deff)} for m in NPS_TABLE_MARGINS]
        formula = "n0 = z^2 Var / e^2, Var = p_pro + p_det - (p_pro - p_det)^2; m = n0 deff; with a population N: n = m / (1 + (m - 1)/N)"
        sources = ["Rocks 2016, The American Statistician 70(4) (NPS variance and Wald interval)", "Lewis and Sauro 2021c, Sample sizes for comparing Net Promoter Scores (MeasuringU)", "Cochran 1977, Sampling Techniques, ch. 4"]
    notes.append("A proportion's +/-5 points (n = 385) is not an NPS's +/-5 points: the NPS is a difference of two shares and needs about %.1f times as many responses at this variance." % (variance / 0.25))
    return {
        "inputs": {"promoters": args.promoters, "detractors": args.detractors, "variance": args.variance, "margin": args.margin, "n": args.n,
                   "diff": args.diff, "confidence": confidence, "population": population, "deff": round(deff, 4)},
        "result": result,
        "statement": statement,
        "assumptions": assumptions,
        "notes": notes,
        "formula": formula,
        "sources": sources,
    }


def cmd_maxdiff(args):
    items = args.items
    if items < 4:
        raise InputError("--items must be at least 4, got %d" % items)
    # Same default as maxdiff-design: 4 per set, or 3 when 4 would be more than half the list.
    if args.per_set is not None:
        per_set = args.per_set
    elif items >= 2 * MAXDIFF_PER_SET:
        per_set = MAXDIFF_PER_SET
    else:
        per_set = max(2, min(3, items // 2))
    if per_set < 2 or per_set >= items:
        raise InputError("--per-set must be at least 2 and fewer than --items, got %d" % per_set)
    subgroups = positive(args.subgroups, "--subgroups")
    notes = []
    if args.per_set is None or args.sets is None:
        notes.append("Using %s; if the design is already built (maxdiff-design), pass its --per-set and --sets so this sizes that design." % (
            "the default items per set (%d)" % per_set if args.per_set is None else "the default sets per respondent (3K/k)"))
    if per_set > items / 2.0:
        notes.append("More than half the items appear in each set; Sawtooth advises at most half.")
    if per_set > 5:
        notes.append("More than 5 items per set; Sawtooth recommends 4 or 5.")
    recommended_sets = ceil_n(MAXDIFF_TIMES_SHOWN * items / float(per_set))
    sets = positive(args.sets, "--sets") if args.sets is not None else recommended_sets
    times_shown = sets * per_set / float(items)
    sparse = times_shown < MAXDIFF_MIN_TIMES_SHOWN
    if sparse:
        notes.append("Each respondent sees each item %.2f times (under 2): a sparse design for pooled analysis only, so the 500-exposure rule applies. Scores for individual respondents are not supported." % times_shown)
    elif times_shown < MAXDIFF_TIMES_SHOWN:
        notes.append("Each respondent sees each item %.2f times (under 3): individual-level scores are less precise." % times_shown)
    scale = max(1.0, items / float(MAXDIFF_MANY_ITEMS))
    if scale > 1:
        notes.append("More than %d items: the respondent floors are raised in proportion (x%.2f), following Sawtooth's advice to raise them for long lists (doubled at 60 items)." % (MAXDIFF_MANY_ITEMS, scale))
    per_group = ceil_n(MAXDIFF_MIN_PER_SUBGROUP * scale)
    floor = max(ceil_n(MAXDIFF_MIN_TOTAL * scale), per_group * subgroups if subgroups > 1 else 0)
    n_min = ceil_n(MAXDIFF_MIN_EXPOSURES / times_shown) * subgroups
    n_better = ceil_n(MAXDIFF_BETTER_EXPOSURES / times_shown) * subgroups
    result = {
        "rule_of_thumb": True,
        "items_per_set": per_set,
        "sets_recommended": recommended_sets,
        "sets_used": sets,
        "times_each_item_shown_per_respondent": round(times_shown, 2),
        "sparse_design": sparse,
        "n_for_500_exposures_per_item": n_min,
        "n_for_1000_exposures_per_item": n_better,
        "n_floor": floor,
        "n_recommended": max(floor, n_min) if sparse else floor,
    }
    if args.n is not None:
        n = positive(args.n, "--n")
        result["n"] = n
        result["exposures_per_item_per_subgroup"] = int(round(n * times_shown / subgroups))
        result["sufficient"] = n >= result["n_recommended"]
    rule = "at least %d respondents in total%s" % (ceil_n(MAXDIFF_MIN_TOTAL * scale), " and %d in each of %d subgroups reported" % (per_group, subgroups) if subgroups > 1 else "")
    if sparse:
        rule += ", and, because the design is sparse, each item seen at least 500 times (exposures, not respondents) in each group"
    statement = "For a MaxDiff with %d items shown %d at a time in %d sets, plan at least %d respondents (rule of thumb from Sawtooth Software: %s; not a power calculation)." % (
        items, per_set, sets, result["n_recommended"], rule)
    return {
        "inputs": {"items": items, "per_set": args.per_set, "sets": args.sets, "subgroups": subgroups, "n": args.n},
        "result": result,
        "statement": statement,
        "assumptions": [
            "Rules of thumb from Sawtooth Software, not a power calculation.",
            "Sets per respondent = 3K/k so each of K items is shown 3 times, k items per set.",
            "At least 300 respondents in total and 200 in each subgroup reported separately (the same rule as the maxdiff-design and maxdiff-analysis skills), raised in proportion above 30 items.",
            "Sparse designs (each item under 2 times per respondent, pooled analysis only): each item seen at least 500 times (preferably 1000) within each group analysed. These are item exposures, not respondents.",
            "Totals assume subgroups of equal size; for unequal ones size the smallest with the subgroups command.",
        ],
        "notes": notes,
        "formula": "sets = 3K/k; times shown t = sets x k / K; n >= 300 in total and 200 per subgroup (x K/30 above 30 items); if t < 2, also n >= 500 / t per subgroup",
        "sources": ["Sawtooth Software, MaxDiff sample size calculation best practices (blog)", "Sawtooth Software, MaxDiff calculator and design guidelines", "Sawtooth Software, Lighthouse Studio manual, Designing a MaxDiff study"],
    }


def cmd_conjoint(args):
    tasks = positive(args.tasks, "--tasks")
    alternatives = positive(args.alternatives, "--alternatives")
    subgroups = positive(args.subgroups, "--subgroups")
    try:
        levels = [int(x) for x in args.levels.split(",") if x.strip()]
    except ValueError:
        raise InputError("--levels must be whole numbers separated by commas, for example 3,4,5")
    if not levels or min(levels) < 2:
        raise InputError("--levels needs at least one attribute, each with 2 or more levels")
    if args.two_way:
        if len(levels) < 2:
            raise InputError("--two-way needs at least two attributes in --levels")
        top = sorted(levels, reverse=True)
        cells = top[0] * top[1]
    else:
        cells = max(levels)
    per_respondent = tasks * alternatives / float(cells)
    n_min = ceil_n(CONJOINT_MIN_REPRESENTATIONS / per_respondent) * subgroups
    n_better = ceil_n(CONJOINT_BETTER_REPRESENTATIONS / per_respondent) * subgroups
    floor = CONJOINT_MIN_TOTAL if subgroups == 1 else CHOICE_MIN_PER_SUBGROUP * subgroups
    result = {
        "rule_of_thumb": True,
        "analysis_cells_c": cells,
        "n_for_500_representations": n_min,
        "n_for_1000_representations": n_better,
        "n_floor": floor,
        "n_recommended": max(floor, n_min),
    }
    if args.n is not None:
        n = positive(args.n, "--n")
        result["n"] = n
        result["representations_per_level_per_subgroup"] = int(round(n * per_respondent / subgroups))
        result["sufficient"] = n >= result["n_recommended"]
    statement = "For a choice-based conjoint with %d tasks of %d alternatives and at most %d %s, plan at least %d respondents (Johnson and Orme's rule of thumb n t a / c >= 500, with a floor of %d; not a power calculation)." % (
        tasks, alternatives, cells, "analysis cells" if args.two_way else "levels per attribute", result["n_recommended"], floor)
    return {
        "inputs": {"tasks": tasks, "alternatives": alternatives, "levels": levels, "two_way": args.two_way, "subgroups": subgroups, "n": args.n},
        "result": result,
        "statement": statement,
        "assumptions": [
            "Rules of thumb (Johnson and Orme), not a power calculation; for aggregate choice-based conjoint.",
            "n x tasks x alternatives / c >= 500, alternatives not counting None; c = %s." % ("largest product of levels of two attributes (two-way interactions)" if args.two_way else "largest number of levels in one attribute (main effects)"),
            "500 is a minimum; 1000 representations per level is better.",
            "At least 300 respondents when no subgroups are compared, and about 200 in each subgroup compared (%d here)." % subgroups,
            "The 500 and 1000 counts apply within each subgroup; totals assume subgroups of equal size (for unequal ones size the smallest with the subgroups command).",
        ],
        "notes": [],
        "formula": "per subgroup: n >= 500 c / (t a); floor: 300 overall, or 200 per subgroup compared",
        "sources": ["Orme 2010/2019, Getting Started with Conjoint Analysis, ch. 7, pp. 64-65", "Sawtooth Software, Sample size rules of thumb"],
    }


def cmd_interviews(args):
    segments = positive(args.segments, "--segments")
    key = (args.method, args.goal)
    if key not in INTERVIEW_RANGES:
        raise InputError("no cited range for focus groups with --goal meaning; use --goal codes, or plan interviews")
    low, high, source = INTERVIEW_RANGES[key]
    unit = "interviews" if args.method == "interviews" else "focus groups"
    result = {
        "guidance_not_a_formula": True,
        "per_segment_low": low,
        "per_segment_high": high,
        "segments": segments,
        "total_low": low * segments,
        "total_high": high * segments,
        "first_saturation_check_after": SATURATION_BASE + SATURATION_RUN,
    }
    statement = "Plan %d to %d %s%s as a starting range (%s), and check saturation during fieldwork rather than treating the range as a target." % (
        low * segments, high * segments, unit, " (%d to %d in each of %d segments)" % (low, high, segments) if segments > 1 else "", source)
    return {
        "inputs": {"segments": segments, "method": args.method, "goal": args.goal},
        "result": result,
        "statement": statement,
        "assumptions": [
            "Guidance from published saturation studies, not a formula and not a statistical sample size.",
            "Each segment is fairly homogeneous and the study aim is narrow; broad aims or mixed groups need more.",
            "Goal '%s': %s." % (args.goal, "hearing the range of issues (code saturation)" if args.goal == "codes" else "understanding the issues in depth (meaning saturation)"),
        ],
        "notes": [
            "Assess saturation from interview %d in each segment (saturation command), and stop on evidence, not on the count." % (SATURATION_BASE + SATURATION_RUN),
            "Do not attach percentages or margins of error to these counts. Some methodologists reject fixed counts altogether (see references/sources.md).",
        ],
        "formula": "cited range per segment x number of segments",
        "sources": [source, "Guest, Namey and Chen 2020, PLOS ONE 15(5)"],
    }


def read_new_codes(args):
    if (args.new_codes is None) == (args.file is None):
        raise InputError("give --new-codes (a comma list) or --file (a CSV), one of them")
    if args.new_codes is not None:
        cells = [c.strip() for c in args.new_codes.split(",")]
        while cells and cells[-1] == "":
            cells.pop()  # a trailing comma
    else:
        try:
            with open(args.file, encoding="utf-8-sig", newline="") as handle:
                text = handle.read()
        except OSError as error:
            raise InputError("cannot read %s: %s" % (args.file, error.strerror))
        except UnicodeDecodeError:
            raise InputError("%s is not UTF-8 text" % args.file)
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            raise InputError("%s is empty" % args.file)
        counts = {d: len(next(csv.reader([lines[0]], delimiter=d))) for d in (",", ";", "\t")}
        delimiter = "," if counts[","] == max(counts.values()) else max(counts, key=counts.get)
        rows = list(csv.reader(lines, delimiter=delimiter))
        first = [cell.strip() for cell in rows[0]]
        has_header = any(cell and not re.fullmatch(r"-?\d+(\.\d+)?", cell) for cell in first)
        header = [cell.lower() for cell in first] if has_header else None
        wanted = (args.column or "new_codes").strip().lower()
        if header is not None and wanted in header:
            column = header.index(wanted)
        elif len(first) == 1 and args.column is None:
            column = 0
        else:
            raise InputError("%s has %d columns; name the one with the counts new_codes or pass --column NAME%s" % (
                args.file, len(first), " (found: %s)" % ", ".join(first) if header is not None else ""))
        rows = rows[1:] if has_header else rows
        cells = [row[column].strip() if column < len(row) else "" for row in rows]
    values = []
    for position, cell in enumerate(cells, 1):
        if cell == "":
            raise InputError("interview %d has no count of new codes; give 0 if it added none" % position)
        try:
            value = int(cell)
        except ValueError:
            raise InputError("interview %d: %r is not a whole number of new codes" % (position, cell))
        if value < 0:
            raise InputError("interview %d: the number of new codes cannot be negative" % position)
        values.append(value)
    return values


def cmd_saturation(args):
    codes = read_new_codes(args)
    base = positive(args.base, "--base")
    run = positive(args.run, "--run")
    threshold = fraction(args.threshold, "--threshold", allow_zero=True)
    if len(codes) < base + run:
        raise InputError("need at least %d interviews (base %d + run %d), got %d" % (base + run, base, run, len(codes)))
    base_codes = sum(codes[:base])
    if base_codes == 0:
        raise InputError("no codes in the first %d interviews, so there is no base to compare against" % base)
    runs = []
    reached_at = None
    for start in range(base, len(codes) - run + 1):
        new = sum(codes[start:start + run])
        ratio = new / float(base_codes)
        met = ratio <= threshold + EPS
        runs.append({"interviews": "%d-%d" % (start + 1, start + run), "new_codes": new, "new_information": round(ratio, 4), "threshold_met": met})
        if met:
            reached_at = start
            break
    result = {
        "base_interviews": base,
        "codes_in_base": base_codes,
        "run_length": run,
        "threshold": threshold,
        "interviews_supplied": len(codes),
        "reached": reached_at is not None,
        "runs": runs,
    }
    notes = []
    if reached_at is not None:
        result["saturation_at_interview"] = reached_at
        result["reported_as"] = "%d+%d" % (reached_at, run)
        statement = "Using a base of %d interviews, a run length of %d and a new-information threshold of <=%s%%, saturation was reached at %d+%d interviews: the %d interviews after interview %d added %s%% new codes relative to the %d codes in the base (Guest, Namey and Chen 2020)." % (
            base, run, pct(threshold), reached_at, run, run, reached_at, pct(runs[-1]["new_information"]), base_codes)
        if len(codes) > reached_at + run:
            notes.append("Interviews after number %d were not needed for this check and are ignored." % (reached_at + run))
    else:
        statement = "Using a base of %d interviews, a run length of %d and a new-information threshold of <=%s%%, saturation was not reached in %d interviews: the latest run still added %s%% new codes relative to the %d codes in the base (Guest, Namey and Chen 2020)." % (
            base, run, pct(threshold), len(codes), pct(runs[-1]["new_information"]), base_codes)
        notes.append("Keep interviewing and re-run after each new interview.")
    notes.append("This measures new codes only. It says nothing about depth of meaning, and it does not apply to reflexive thematic analysis.")
    return {
        "inputs": {"new_codes": codes, "base": base, "run": run, "threshold": threshold},
        "result": result,
        "statement": statement,
        "assumptions": [
            "Input: for each interview in the order conducted, the number of codes that appeared for the first time in that interview.",
            "One fairly homogeneous group; run the check per segment.",
            "Base size %d, run length %d, threshold <=%s%% new information; a run length of 3 or a threshold of 0 is stricter." % (base, run, pct(threshold)),
        ],
        "notes": notes,
        "formula": "new information = new codes in a run of interviews / codes in the base interviews; runs move forward one interview at a time; saturation at the interview before the first run at or under the threshold",
        "sources": ["Guest, Namey and Chen 2020, A simple method to assess and report thematic saturation in qualitative research, PLOS ONE 15(5): e0232076"],
    }


LABELS = {
    "n_required": "Responses needed",
    "n_infinite_population": "Before rounding, large population",
    "n": "n given",
    "margin_of_error": "Margin of error (+/-)",
    "sufficient": "Enough",
    "n_per_group": "Responses needed per group",
    "n_group_1": "Responses needed in group 1",
    "n_group_2": "Responses needed in group 2",
    "n_total": "Responses needed in total",
    "power_at_n": "Power at the n given",
    "invitations": "Invitations to send",
    "n_recommended": "Respondents (rule of thumb)",
}


def show(value):
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def render_table(rows, indent):
    keys = list(rows[0])
    widths = [max(len(key.replace("_", " ")), max(len(show(row.get(key, ""))) for row in rows)) for key in keys]
    lines = [indent + "  ".join(key.replace("_", " ").ljust(width) for key, width in zip(keys, widths)).rstrip()]
    for row in rows:
        lines.append(indent + "  ".join(show(row.get(key, "")).ljust(width) for key, width in zip(keys, widths)).rstrip())
    return lines


def render(report):
    lines = ["survey-sample-size: %s" % report["subcommand"], ""]
    for key, value in report["result"].items():
        label = LABELS.get(key, key.replace("_", " "))
        if isinstance(value, dict):
            lines.append("  %s:" % label)
            lines += ["    %s: %s" % (k.replace("_", " "), show(v)) for k, v in value.items()]
        elif isinstance(value, list):
            lines.append("  %s:" % label)
            lines += render_table(value, "    ")
        else:
            lines.append("  %s: %s" % (label, show(value)))
    if report["statement"]:
        lines += ["", "Statement: " + report["statement"]]
    lines += ["", "Assumptions:"] + ["  - " + a for a in report["assumptions"]]
    if report["notes"]:
        lines += ["", "Notes:"] + ["  - " + n for n in report["notes"]]
    lines += ["", "Formula: " + report["formula"], "Sources: " + "; ".join(report["sources"])]
    return "\n".join(lines)


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="print the result as JSON")
    common.add_argument("--opt-in", action="store_true",
                        help="respondents opted in (panel, customer list, social post): label margins as a simple-random-sample benchmark, not a property of this sample")
    parser = argparse.ArgumentParser(description="Survey sample size calculator (see references/sources.md for the formulas).")
    sub = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")
    sub.required = True

    def design_options(p):
        p.add_argument("--deff", type=float, help="design effect from weighting or clustering (default 1)")
        p.add_argument("--icc", type=float, help="intraclass correlation, with --cluster-size: deff = 1 + (m - 1) x icc")
        p.add_argument("--cluster-size", type=float, help="average responses per cluster (m), with --icc")
        p.add_argument("--weight-cv", type=float, help="coefficient of variation of the weights: deff = 1 + cv^2")

    def interval_options(p):
        p.add_argument("--margin", type=float, help="target margin of error (half-width of the confidence interval)")
        p.add_argument("--n", type=int, help="a sample size to check: prints the margin of error it gives")
        p.add_argument("--confidence", type=float, default=0.95, help="confidence level (default 0.95)")
        p.add_argument("--population", type=int, help="population size, for the finite population correction")
        design_options(p)

    p = sub.add_parser("proportion", parents=[common], help="margin of error on a percentage")
    interval_options(p)
    p.add_argument("--p", type=float, help="expected proportion (default 0.5, the most cautious)")
    p.add_argument("--x", type=int, help="observed count with the answer (with --n): prints a Wilson interval for x/n")
    p.add_argument("--table", action="store_true", help="add a sensitivity table (n by margin, or margin by n)")
    p.set_defaults(func=cmd_proportion)

    p = sub.add_parser("mean", parents=[common], help="margin of error on a mean")
    interval_options(p)
    p.add_argument("--sd", type=float, required=True, help="standard deviation of the measure")
    p.set_defaults(func=cmd_mean)

    p = sub.add_parser("compare", parents=[common], help="detect a difference between two independent groups")
    p.add_argument("--p1", type=float, help="proportion in group 1 (the baseline)")
    p.add_argument("--p2", type=float, help="proportion in group 2")
    p.add_argument("--lift", type=float, help="relative change from p1 instead of --p2: 0.2 means p2 = 1.2 x p1")
    p.add_argument("--d", type=float, help="difference between two means in standard deviations (Cohen's d)")
    p.add_argument("--diff", type=float, help="difference between two means in scale units (needs --sd)")
    p.add_argument("--sd", type=float, help="standard deviation of the measure (with --diff)")
    p.add_argument("--h", type=float, help="Cohen's effect size h for two proportions (arcsine scale)")
    p.add_argument("--n", type=int, help="n in group 1 to check: prints power (effect given) or the smallest detectable difference")
    p.add_argument("--n2", type=int, help="n in group 2, with --n, when the groups differ in size")
    p.add_argument("--ratio", type=float, help="group 2 size / group 1 size (default 1)")
    p.add_argument("--alpha", type=float, default=0.05, help="significance level (default 0.05)")
    p.add_argument("--power", type=float, default=0.80, help="power (default 0.80)")
    p.add_argument("--sides", type=int, choices=[1, 2], default=2, help="one- or two-sided test (default 2)")
    p.add_argument("--comparisons", type=int, default=1, help="number of planned comparisons; alpha is divided by it (Bonferroni)")
    p.add_argument("--variance", "--method", dest="variance", choices=["pooled", "unpooled", "baseline", "arcsine"], default="pooled",
                   help="proportions: pooled variance under the null (default), unpooled, baseline (null variance from p1), or arcsine (Cohen's h)")
    p.add_argument("--continuity", action="store_true", help="proportions: apply the continuity correction")
    p.add_argument("--direction", choices=["up", "down"], default="up", help="proportions, reverse: look for p2 above or below p1 (default up)")
    p.add_argument("--table", action="store_true", help="add a sensitivity table (n by difference or by d)")
    design_options(p)
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("gap", parents=[common], help="margin of error for the gap between two answers in the same sample")
    p.add_argument("--p1", type=float, required=True, help="share choosing the first answer")
    p.add_argument("--p2", type=float, required=True, help="share choosing the second answer")
    p.add_argument("--n", type=int, required=True, help="responses to the question")
    p.add_argument("--confidence", type=float, default=0.95, help="confidence level (default 0.95)")
    design_options(p)
    p.set_defaults(func=cmd_gap)

    p = sub.add_parser("check", parents=[common], help="what a given n supports")
    p.add_argument("--n", type=int, required=True, help="the sample size to check")
    p.add_argument("--share", nargs="+", help="shares of the subgroups you will report (0.15 or name=0.15)")
    p.add_argument("--p", type=float, default=0.5, help="proportion the percentages are near (default 0.5)")
    p.add_argument("--confidence", type=float, default=0.95, help="confidence level (default 0.95)")
    p.add_argument("--alpha", type=float, default=0.05, help="significance level for the detectable difference (default 0.05)")
    p.add_argument("--power", type=float, default=0.80, help="power for the detectable difference (default 0.80)")
    p.add_argument("--population", type=int, help="population size: finite population correction for the overall margin")
    design_options(p)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("subgroups", parents=[common], help="total n and quota table so every subgroup reaches its base")
    p.add_argument("--share", nargs="+", required=True, help="share of the sample in each subgroup you will report (0.15 or name=0.15)")
    p.add_argument("--min-base", type=int, help="minimum responses per subgroup (default %d)" % SUBGROUP_MIN_BASE)
    p.add_argument("--margin", type=float, help="target margin of error within every subgroup, instead of --min-base")
    p.add_argument("--confidence", type=float, default=0.95, help="confidence level for the margins (default 0.95)")
    design_options(p)
    p.set_defaults(func=cmd_subgroups)

    p = sub.add_parser("invites", parents=[common], help="invitations needed for a target number of completes")
    p.add_argument("--completes", type=int, required=True, help="usable completed responses needed")
    p.add_argument("--response-rate", type=float, required=True, help="share of delivered invitations that start the survey")
    p.add_argument("--completion-rate", type=float, default=1.0, help="share of qualified starters who finish (default 1)")
    p.add_argument("--incidence", type=float, default=1.0, help="share of starters who qualify (default 1)")
    p.add_argument("--deliverability", type=float, default=1.0, help="share of invitations delivered (default 1)")
    p.add_argument("--removal-rate", type=float, default=0.0, help="share of completes you expect to remove in cleaning (default 0)")
    p.set_defaults(func=cmd_invites)

    p = sub.add_parser("nps", parents=[common], help="Net Promoter Score: margin in NPS points, or n per group to compare two scores")
    p.add_argument("--promoters", type=float, help="expected share of promoters (9-10), for example 0.4")
    p.add_argument("--detractors", type=float, help="expected share of detractors (0-6), for example 0.2")
    p.add_argument("--variance", type=float, help="NPS variance instead of the shares (default %g)" % NPS_DEFAULT_VARIANCE)
    p.add_argument("--margin", type=float, help="target margin in NPS points as a proportion (0.05 = +/-5 points)")
    p.add_argument("--n", type=int, help="a sample size (per group with --diff) to check")
    p.add_argument("--diff", type=float, help="difference in NPS to detect between two groups, as a proportion (0.1 = 10 points)")
    p.add_argument("--confidence", type=float, default=0.95, help="confidence level (default 0.95)")
    p.add_argument("--population", type=int, help="population size, for the finite population correction")
    p.add_argument("--alpha", type=float, default=0.05, help="with --diff: significance level (default 0.05)")
    p.add_argument("--power", type=float, default=0.80, help="with --diff: power (default 0.80)")
    p.add_argument("--sides", type=int, choices=[1, 2], default=2, help="with --diff: one- or two-sided test (default 2)")
    p.add_argument("--table", action="store_true", help="add a sensitivity table: n at +/-3, 5, 7 and 10 points, the margin at other n, or n per group for 5 to 20 point differences")
    design_options(p)
    p.set_defaults(func=cmd_nps)

    p = sub.add_parser("maxdiff", parents=[common], help="MaxDiff rules of thumb")
    p.add_argument("--items", type=int, required=True, help="number of items (K)")
    p.add_argument("--per-set", type=int, help="items shown per set (k); default 4, or 3 for 6 or 7 items (as maxdiff-design)")
    p.add_argument("--sets", type=int, help="sets each respondent answers; default 3K/k")
    p.add_argument("--subgroups", type=int, default=1, help="number of subgroups to compare (default 1)")
    p.add_argument("--n", type=int, help="a sample size to check")
    p.set_defaults(func=cmd_maxdiff)

    p = sub.add_parser("conjoint", parents=[common], help="choice-based conjoint rules of thumb")
    p.add_argument("--tasks", type=int, required=True, help="choice tasks per respondent (t)")
    p.add_argument("--alternatives", type=int, required=True, help="alternatives per task, not counting None (a)")
    p.add_argument("--levels", required=True, help="levels per attribute, comma-separated, for example 3,4,5")
    p.add_argument("--two-way", action="store_true", help="plan for all two-way interactions (c = largest product of two attributes' levels)")
    p.add_argument("--subgroups", type=int, default=1, help="number of subgroups to compare (default 1)")
    p.add_argument("--n", type=int, help="a sample size to check")
    p.set_defaults(func=cmd_conjoint)

    p = sub.add_parser("interviews", parents=[common], help="planning range for interviews or focus groups")
    p.add_argument("--segments", type=int, default=1, help="number of distinct, fairly homogeneous groups (default 1)")
    p.add_argument("--method", choices=["interviews", "focus-groups"], default="interviews", help="default interviews")
    p.add_argument("--goal", choices=["codes", "meaning"], default="codes", help="codes: hear the range of issues (default); meaning: understand them in depth")
    p.set_defaults(func=cmd_interviews)

    p = sub.add_parser("saturation", parents=[common], help="saturation check from new codes per interview")
    p.add_argument("--new-codes", help="new codes per interview, in order, comma-separated: 12,9,8,8,4,3,1,0")
    p.add_argument("--file", help="CSV, one row per interview in order: a single column, or the column new_codes (or --column)")
    p.add_argument("--column", help="name of the column with the counts in --file (default new_codes)")
    p.add_argument("--base", type=int, default=SATURATION_BASE, help="base size (default %d)" % SATURATION_BASE)
    p.add_argument("--run", type=int, default=SATURATION_RUN, help="run length (default %d)" % SATURATION_RUN)
    p.add_argument("--threshold", type=float, default=SATURATION_THRESHOLD, help="new-information threshold (default %g)" % SATURATION_THRESHOLD)
    p.set_defaults(func=cmd_saturation)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        for name, value in vars(args).items():
            if isinstance(value, float) and not math.isfinite(value):
                raise InputError("--%s must be a finite number, got %s" % (name.replace("_", "-"), value))
        report = {"subcommand": args.subcommand}
        report.update(args.func(args))
        if args.opt_in and args.subcommand in OPT_IN_LABELLED:
            report["statement"] = ("Benchmark only, not a margin of error for this sample: " + report["statement"]
                                   + " The respondents opted in rather than being sampled at random, so no design-based margin of error or confidence level applies to them (AAPOR); quote these numbers as what a simple random sample of the same size would give.")
            report["assumptions"].insert(0, "Opt-in sample (--opt-in): the numbers are a simple-random-sample benchmark, not the precision of this sample.")
    except InputError as error:
        sys.stderr.write("survey-sample-size: error: %s\n" % error)
        return EXIT_BAD_INPUT
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
