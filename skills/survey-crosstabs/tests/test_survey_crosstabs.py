"""Tests for scripts/survey_crosstabs.py. Run from the skill folder: python3 -m unittest discover -s tests

Expected values come from published examples (Agresti 2007; the R documentation for chisq.test and
fisher.test; Benjamini and Hochberg 1995) or from an independent computation in base R
(fixtures/README.md), not from the script.
"""
import csv
import importlib.util
import json
import math
import pathlib
import subprocess
import sys
import tempfile
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "survey_crosstabs.py"

spec = importlib.util.spec_from_file_location("survey_crosstabs", SCRIPT)
xt = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(xt)


def run(*args):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                          check=False)


def run_json(*args):
    proc = run(*args, "--json")
    if proc.returncode != 0:
        raise AssertionError(f"exit {proc.returncode}: {proc.stderr}")
    return json.loads(proc.stdout)


def write_csv(rows, encoding="utf-8", delimiter=",", newline="\n"):
    handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding=encoding, newline="")
    writer = csv.writer(handle, delimiter=delimiter, lineterminator=newline)
    writer.writerows(rows)
    handle.close()
    return handle.name


def row(table, label):
    return next(r for r in table["rows"] if r["label"] == label)


def col_index(table, label):
    return next(i for i, c in enumerate(table["columns"]) if c["label"] == label)


class PublishedExamples(unittest.TestCase):
    def test_agresti_party_by_gender_chi_square(self):
        # Agresti (2007) Table 2.5; R chisq.test example: X-squared = 30.07, df = 2, p = 2.954e-07.
        t = run_json(FIXTURES / "agresti_party_gender.input.csv", "--count-col", "count", "--rows", "party",
                     "--banner", "gender")["tables"][0]
        self.assertAlmostEqual(t["chi_square"]["statistic"], 30.0701490958, places=6)
        self.assertEqual(t["chi_square"]["df"], 2)
        self.assertAlmostEqual(t["chi_square"]["p"], 2.95358918321e-07, delta=1e-12)
        self.assertEqual(t["columns"][0]["n"], 2757)

    def test_aspirin_two_proportion_z(self):
        # Physicians' Health Study (Agresti 2007, Table 2.3): z = 5.00; R prop.test(correct=FALSE) X2 = 25.0139.
        t = run_json(FIXTURES / "aspirin_mi.input.csv", "--count-col", "count", "--rows", "heart_attack",
                     "--banner", "group")["tables"][0]
        test = next(x for x in t["tests"] if x["row"] == "Yes")
        self.assertAlmostEqual(test["z"] ** 2, 25.0138839672, places=6)
        self.assertAlmostEqual(test["p"], 5.69189697374e-07, delta=1e-12)
        self.assertEqual(t["tests_run"], 1, "two answers: one comparison, counted once")
        placebo = col_index(t, "Placebo")
        self.assertIn("A", row(t, "Yes")["cells"][placebo]["letters"])  # Aspirin is column A (alphabetical)

    def test_benjamini_hochberg_1995_example(self):
        # BH (1995) p. 295: 15 p-values; BH at 0.05 rejects 4, Bonferroni rejects 3. Adjusted values from R p.adjust.
        p = [0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298, 0.0344, 0.0459, 0.3240, 0.4262, 0.5719,
             0.6528, 0.7590, 1.000]
        bh = xt.adjust_pvalues(p, "bh")
        self.assertEqual(sum(1 for v in bh if v < 0.05), 4)
        for got, want in zip(bh, [0.0015, 0.003, 0.0095, 0.035625, 0.0603, 0.0638571428571, 0.0638571428571,
                                  0.0645, 0.0765, 0.486, 0.581181818182, 0.714875, 0.753230769231,
                                  0.813214285714, 1]):
            self.assertAlmostEqual(got, want, places=9)
        holm = xt.adjust_pvalues(p, "holm")
        for got, want in zip(holm, [0.0015, 0.0056, 0.0247, 0.114, 0.2211, 0.278, 0.278, 0.278, 0.3213, 1, 1,
                                    1, 1, 1, 1]):
            self.assertAlmostEqual(got, want, places=9)
        self.assertEqual(sum(1 for v in xt.adjust_pvalues(p, "bonferroni") if v < 0.05), 3)

    def test_fisher_tea_tasting(self):
        # Fisher's tea-tasting table (R fisher.test example): two-sided p = 0.4857.
        self.assertAlmostEqual(xt.fisher_exact(3, 4, 1, 4), 0.4857142857, places=8)


class IndependentChecks(unittest.TestCase):
    def test_chi_square_tail_matches_known_critical_values(self):
        for x, df in [(3.841458821, 1), (5.991464547, 2), (18.30703805, 10), (43.77297183, 30)]:
            self.assertAlmostEqual(xt.chi2_sf(x, df), 0.05, places=8)

    def test_z_squared_equals_two_by_two_chi_square(self):
        # Re-derivation: the pooled two-proportion z squared is Pearson's X2 on the 2x2 table.
        p, _, z = xt.pair_test(30 / 80, 80, 45 / 90, 90, 30, 80, 45, 90, False, "z")
        obs = [[30, 45], [50, 45]]
        tot = 170
        x2 = sum((obs[i][j] - sum(obs[i]) * (obs[0][j] + obs[1][j]) / tot) ** 2
                 / (sum(obs[i]) * (obs[0][j] + obs[1][j]) / tot) for i in range(2) for j in range(2))
        self.assertAlmostEqual(z * z, x2, places=10)
        self.assertAlmostEqual(p, xt.chi2_sf(x2, 1), places=10)

    def test_kish_effective_n_equals_n_over_one_plus_cv_squared(self):
        w = [1, 1, 2, 2, 3, 0.5]
        n = len(w)
        mean = sum(w) / n
        cv2 = sum((x - mean) ** 2 for x in w) / n / mean ** 2
        self.assertAlmostEqual(xt.kish(sum(w), sum(x * x for x in w)), n / (1 + cv2), places=12)
        self.assertAlmostEqual(xt.kish(6, 10), 3.6)

    def test_wilson_interval_textbook(self):
        # 30 of 40 (csat-ces-analysis fixture, hand-worked): 59.81% to 85.81%.
        lo, hi = xt.wilson(0.75, 40, xt.z_for(0.95))
        self.assertAlmostEqual(lo, 0.598061, places=5)
        self.assertAlmostEqual(hi, 0.858129, places=5)


class BasicFixture(unittest.TestCase):
    """fixtures/basic.input.csv against base R (fixtures/README.md section 3)."""

    @classmethod
    def setUpClass(cls):
        cls.out = run_json(FIXTURES / "basic.input.csv", "--rows", "satisfaction", "--banner", "plan", "--means")
        cls.t = cls.out["tables"][0]
        cls.w = run_json(FIXTURES / "basic.input.csv", "--rows", "satisfaction", "--banner", "plan", "--means",
                         "--weight", "weight")

    def test_bases_and_missing(self):
        t = self.t
        self.assertEqual([c["n"] for c in t["columns"]], [132, 50, 60, 20])
        self.assertEqual(t["blank_row"], 3)
        self.assertEqual(t["blank_banner"], 2)

    def test_label_prefixed_values_merge_and_keep_their_label(self):
        labels = [r["label"] for r in self.t["rows"] if r["kind"] == "category"]
        self.assertEqual(labels, ["1 - Very dissatisfied", "2 - Dissatisfied", "3 - Neutral", "4 - Satisfied",
                                  "5 - Very satisfied"])

    def test_chi_square_matches_r(self):
        cs = self.t["chi_square"]
        self.assertAlmostEqual(cs["statistic"], 19.4063888182, places=6)
        self.assertEqual(cs["df"], 8)
        self.assertAlmostEqual(cs["p"], 0.0128310352945, places=9)

    def test_pairwise_p_and_holm_family_match_r(self):
        tests = {(x["row"], x["a"], x["b"]): x for x in self.t["tests"]}
        want_p = {"1 - Very dissatisfied": 0.0758317885739, "3 - Neutral": 0.0966008673592,
                  "4 - Satisfied": 0.117941635388, "5 - Very satisfied": 0.00364060873165}
        for label, p in want_p.items():
            self.assertAlmostEqual(tests[(label, "A", "B")]["p"], p, places=9)
        self.assertAlmostEqual(tests[("5 - Very satisfied", "A", "B")]["p_adj"], 0.0182030436583, places=9)
        self.assertAlmostEqual(tests[("Mean", "A", "B")]["p"], 0.000138580622238, places=9)
        self.assertAlmostEqual(tests[("Mean", "A", "B")]["p_adj"], 0.000831483733426, places=9)
        self.assertEqual(self.t["tests_run"], 6)
        pro = col_index(self.t, "Pro")
        self.assertEqual(row(self.t, "5 - Very satisfied")["cells"][pro]["letters"], ["A"])
        self.assertEqual(self.t["mean_row"]["cells"][pro]["letters"], ["A"])

    def test_small_base_column_is_flagged_and_not_tested(self):
        team = col_index(self.t, "Team")
        self.assertTrue(self.t["columns"][team]["small_base"])
        self.assertTrue(all(x["p"] is None for x in self.t["tests"] if "C" in (x["a"], x["b"])))

    def test_weighted_percent_kish_n_and_z_match_r(self):
        t = self.w["tables"][0]
        free, pro = col_index(t, "Free"), col_index(t, "Pro")
        self.assertAlmostEqual(t["columns"][free]["weighted_base"], 70.2, places=9)
        self.assertAlmostEqual(t["columns"][free]["n_eff"], 48.0315789474, places=8)
        self.assertAlmostEqual(t["columns"][pro]["n_eff"], 57.6470588235, places=8)
        self.assertAlmostEqual(row(t, "5 - Very satisfied")["cells"][free]["pct"], 0.102564102564, places=10)
        self.assertAlmostEqual(t["mean_row"]["cells"][pro]["mean"], 3.76428571429, places=9)
        test = next(x for x in t["tests"] if x["row"] == "5 - Very satisfied" and x["a"] == "A")
        self.assertAlmostEqual(test["z"], -2.83695943935, places=8)
        self.assertAlmostEqual(self.w["weights"]["n_eff"], 125.410522455, places=7)

    def test_unit_weights_equal_unweighted_and_scale_does_not_matter(self):
        rows = list(csv.reader((FIXTURES / "basic.input.csv").read_text(encoding="utf-8").splitlines()))
        ones = write_csv([rows[0] + ["one", "big"]] + [r + ["1", str(float(r[4]) * 7)] for r in rows[1:]])
        a = run_json(ones, "--rows", "satisfaction", "--banner", "plan", "--weight", "one")["tables"][0]
        self.assertAlmostEqual(a["chi_square"]["statistic"], self.t["chi_square"]["statistic"], places=9)
        b = run_json(ones, "--rows", "satisfaction", "--banner", "plan", "--weight", "big")["tables"][0]
        c = self.w["tables"][0]
        self.assertAlmostEqual(b["chi_square"]["statistic"], c["chi_square"]["statistic"], places=9)
        for tb, tc in zip(b["tests"], c["tests"]):
            if tc["p"] is not None:
                self.assertAlmostEqual(tb["p"], tc["p"], places=10)

    def test_net_row(self):
        t = run_json(FIXTURES / "basic.input.csv", "--rows", "satisfaction", "--banner", "plan", "--net",
                     "satisfaction:Top 2=4;5")["tables"][0]
        net = row(t, "NET Top 2")
        self.assertAlmostEqual(net["cells"][col_index(t, "Free")]["pct"], 15 / 50)
        self.assertAlmostEqual(net["cells"][col_index(t, "Pro")]["pct"], 40 / 60)

    def test_multi_select(self):
        t = run_json(FIXTURES / "basic.input.csv", "--rows", "features", "--multi", "features", "--banner",
                     "plan")["tables"][0]
        self.assertEqual(t["type"], "multi")
        self.assertIsNone(t["chi_square"])
        total = sum(r["cells"][0]["pct"] for r in t["rows"])
        self.assertGreater(total, 1.0)


class Anonymity(unittest.TestCase):
    def test_employee_fixture(self):
        t = run_json(FIXTURES / "employee_pulse.input.csv", "--rows", "engaged", "--banner", "team",
                     "--anonymity")["tables"][0]
        hidden = {c["label"] for c in t["columns"] if c["suppressed"]}
        # Legal (3) is under 5; hidden alone it would be Total minus the other groups, so the smallest other
        # group (Operations, 6) is hidden with it.
        self.assertEqual(hidden, {"Legal", "Operations"})
        for c in t["columns"]:
            if c["suppressed"]:
                self.assertIsNone(c["n"])
        eng, sales = col_index(t, "Engineering"), col_index(t, "Sales")
        self.assertTrue(row(t, "Disagree")["cells"][eng]["suppressed"])  # 3 < 5
        self.assertTrue(row(t, "Neutral")["cells"][eng]["suppressed"])  # complementary
        self.assertFalse(row(t, "Agree")["cells"][eng]["suppressed"])
        self.assertTrue(row(t, "Neutral")["cells"][sales]["suppressed"])
        for r in t["rows"]:
            for cell in r["cells"]:
                if cell["suppressed"]:
                    self.assertIsNone(cell["count"])
                    self.assertIsNone(cell["pct"])
        # The tested groups have hidden cells, so the chi-square is withheld (it could be inverted).
        self.assertIsNone(t["chi_square"]["statistic"])
        assert_nothing_recoverable(self, t, 5, FIXTURES / "employee_pulse.input.csv", "engaged", "team")

    def test_no_hidden_value_can_be_derived(self):
        rows = [["team", "q"]]
        for team, counts in {"A": [2, 9, 9], "B": [6, 7, 7], "C": [5, 6, 0]}.items():
            for ans, n in zip(["x", "y", "z"], counts):
                rows += [[team, ans]] * n
        t = run_json(write_csv(rows), "--rows", "q", "--banner", "team", "--anonymity", "5")["tables"][0]
        cats = [r for r in t["rows"] if r["kind"] == "category"]
        for ci, col in enumerate(t["columns"]):
            if not col["suppressed"]:
                self.assertNotEqual(sum(1 for r in cats if r["cells"][ci]["suppressed"]), 1, col["label"])
        for r in cats:
            if not r["cells"][0]["suppressed"]:
                self.assertNotEqual(sum(1 for c in r["cells"][1:] if c["suppressed"]), 1, r["label"])

    def test_custom_k_and_off_by_default(self):
        t = run_json(FIXTURES / "employee_pulse.input.csv", "--rows", "engaged", "--banner", "team")["tables"][0]
        self.assertFalse(any(c["suppressed"] for c in t["columns"]))
        t = run_json(FIXTURES / "employee_pulse.input.csv", "--rows", "engaged", "--banner", "team",
                     "--anonymity", "13")["tables"][0]
        self.assertEqual({c["label"] for c in t["columns"] if c["suppressed"]}, {"Legal", "Operations", "Sales"})


# ------------------------------------------------------------------------------------------------ disclosure check
# An attacker independent of the script: enumerate every integer table that agrees with what the JSON prints and
# see which hidden values are pinned down. Kept separate from the script's own network check on purpose.

def feasible_values(t):
    """Brute force: every integer table consistent with what a single-choice JSON table prints.

    Unknowns are the hidden cells of each answer row (group cells, the no-banner remainder and a hidden Total).
    A reader knows every printed count, that hidden cells in a shown group or in Total are at least 1 (zeros are
    printed), that a hidden group has at least one member, and that the no-banner remainder has blank_banner
    people. Returns {(row index, column index or "blank"): set of possible values}.
    """
    cols = t["columns"]
    rows = [r for r in t["rows"] if r["kind"] == "category"]
    total_n = cols[0]["n"]
    g = list(range(1, len(cols)))
    shown_base = {j: cols[j]["n"] for j in g if cols[j]["n"] is not None}
    hidden_groups = [j for j in g if cols[j]["n"] is None]
    blank = t["blank_banner"]
    hidden_total_sum = total_n - sum(r["cells"][0]["count"] for r in rows if r["cells"][0]["count"] is not None)
    keys = []  # per row: list of (key, lower bound)
    fixed = []  # per row: known part of the row sum
    for i, r in enumerate(rows):
        ks = [((i, j), 0 if cols[j]["n"] is None else 1) for j in g if r["cells"][j]["count"] is None]
        if blank:
            ks.append(((i, "blank"), 0))
        keys.append(ks)
        fixed.append(sum(r["cells"][j]["count"] for j in g if r["cells"][j]["count"] is not None))
    possible = {}

    def comps(total, lbs):
        if not lbs:
            if total == 0:
                yield ()
            return
        lo = lbs[0]
        rest = sum(lbs[1:])
        for v in range(lo, total - rest + 1):
            for tail in comps(total - v, lbs[1:]):
                yield (v,) + tail

    def walk(i, sums, chosen, hidden_total_left):
        if i == len(rows):
            if hidden_total_left != 0:
                return
            for j, n in shown_base.items():
                if sums.get(j, 0) != n:
                    return
            if blank and sums.get("blank", 0) != blank:
                return
            if any(sums.get(j, 0) < 1 for j in hidden_groups):
                return
            for key, v in chosen:
                possible.setdefault(key, set()).add(v)
            return
        tcount = rows[i]["cells"][0]["count"]
        if tcount is None:
            totals = range(max(1, fixed[i]), fixed[i] + hidden_total_left + 1)
        else:
            totals = [tcount]
        for tot in totals:
            residual = tot - fixed[i]
            if residual < 0:
                continue
            left = hidden_total_left - (tot if tcount is None else 0)
            if left < 0:
                continue
            ks = keys[i]
            for vals in comps(residual, [lb for _, lb in ks]):
                new = dict(sums)
                ok = True
                for (key, _), v in zip(ks, vals):
                    j = key[1]
                    new[j] = new.get(j, 0) + v
                    if j in shown_base and new[j] > shown_base[j]:
                        ok = False
                    if j == "blank" and new[j] > blank:
                        ok = False
                if ok:
                    walk(i + 1, new, chosen + list(zip([key for key, _ in ks], vals)), left)

    start = {j: sum(r["cells"][j]["count"] for r in rows if r["cells"][j]["count"] is not None) for j in shown_base}
    walk(0, start, [], hidden_total_sum)
    return possible


def true_counts(path, row_col, banner_col):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        data = list(csv.DictReader(handle))
    counts = {}
    for d in data:
        counts[(d[banner_col].strip(), d[row_col].strip())] = counts.get((d[banner_col].strip(), d[row_col].strip()), 0) + 1
    return counts


def assert_nothing_recoverable(test, t, k, path, row_col, banner_col):
    """No hidden count of 1 to k-1 has a single possible value, and no hidden group of fewer than k people (or
    the no-banner remainder) can only have given one answer, given everything the table prints."""
    counts = true_counts(path, row_col, banner_col)
    cats = [r for r in t["rows"] if r["kind"] == "category"]
    poss = feasible_values(t)
    everyone_same = any(r["cells"][0]["count"] == t["columns"][0]["n"] for r in cats)
    for j, col in enumerate(t["columns"]):
        if j == 0:
            continue
        for i, r in enumerate(cats):
            if r["cells"][j]["suppressed"]:
                value = counts.get((col["label"], r["label"]), 0)
                test.assertIn(value, poss.get((i, j), set()), "attacker model rejects the true table")
                if 0 < value < k:
                    test.assertGreater(len(poss[(i, j)]), 1, f"{col['label']} / {r['label']} = {value} is recoverable")
        n_true = sum(v for (g, _), v in counts.items() if g == col["label"])
        if col["suppressed"] and 0 < n_true < k and not everyone_same:
            rows_possible = {i for i in range(len(cats)) if max(poss.get((i, j), {0})) > 0}
            test.assertGreater(len(rows_possible), 1, f"everyone in hidden {col['label']} gave one answer")
    if 0 < t["blank_banner"] < k and not everyone_same:
        rows_possible = {i for i in range(len(cats)) if max(poss.get((i, "blank"), {0})) > 0}
        test.assertGreater(len(rows_possible), 1, "the no-banner remainder gave one answer")


def table_csv(groups, answers, blank=()):
    """groups: {group: [count per answer]}; blank: answers of people with no group."""
    rows = [["team", "q"]]
    for g, counts in groups.items():
        for a, n in zip(answers, counts):
            rows += [[g, a]] * n
    rows += [["", a] for a in blank]
    return write_csv(rows)


class AnonymityRecovery(unittest.TestCase):
    """Each case below leaked a hidden count before the exact disclosure check (reviews of 2026-11-19)."""

    def check(self, path, k=5, *extra):
        t = run_json(path, "--rows", "q", "--banner", "team", "--anonymity", str(k), *extra)["tables"][0]
        assert_nothing_recoverable(self, t, k, path, "q", "team")
        return t

    def test_chi_square_is_withheld_when_tested_groups_have_hidden_cells(self):
        # Codex: A = 2 of 10 on answer 1, B = 0 of 10; X2 = 20x/(20-x) = 2.22 gave x = 2.
        path = table_csv({"A": [2, 8], "B": [0, 10]}, ["1", "2"])
        t = self.check(path)
        self.assertIsNone(t["chi_square"]["statistic"])
        self.assertNotIn("fisher_p", t["chi_square"])
        self.assertNotIn("X2 =", run(path, "--rows", "q", "--banner", "team", "--anonymity").stdout)
        # Gemini: 9/1 vs 5/5, every cell hidden, X2 = 3.81 picked out the lone dissenter.
        t = self.check(table_csv({"A": [9, 1], "B": [5, 5]}, ["Yes", "No"]))
        self.assertIsNone(t["chi_square"]["statistic"])

    def test_repo_example_table(self):
        # Opus: in this table only A_x = 2 reproduced the printed X2 = 9.14.
        t = self.check(table_csv({"A": [2, 9, 9], "B": [6, 7, 7], "C": [5, 6, 0]}, ["x", "y", "z"]))
        self.assertIsNone(t["chi_square"]["statistic"])

    def test_two_small_hidden_groups_with_one_answer(self):
        # Opus: HR (2) and Legal (2) all Disagree; Total minus the shown groups gave it away.
        t = self.check(table_csv({"Eng": [10, 10], "Sales": [10, 10], "HR": [0, 2], "Legal": [0, 2]},
                                 ["Agree", "Disagree"]))
        hidden = {c["label"] for c in t["columns"] if c["suppressed"]}
        self.assertGreater(len(hidden), 2)

    def test_no_banner_remainder_is_protected(self):
        # Gemini: 2 people with no team both Agree; every group cell was 5 or more, so nothing was hidden.
        self.check(table_csv({"Eng": [5, 5], "Sales": [5, 5]}, ["Agree", "Disagree"], blank=["Agree", "Agree"]))
        self.check(table_csv({"Eng": [6, 5], "Sales": [5, 7]}, ["Agree", "Disagree"], blank=["Disagree"]))

    def test_shown_zeros_do_not_pin_two_hidden_ones(self):
        # Gemini: 12 people, answers 1, 1, 0, 5, 5. Hidden cells are known to be at least 1 when zeros are shown,
        # so 12 - 0 - 5 - 5 = 2 forced both hidden cells to 1.
        self.check(table_csv({"A": [1, 1, 0, 5, 5], "B": [6, 6, 6, 6, 6]}, ["1", "2", "3", "4", "5"]))

    def test_small_total_cell_is_protected(self):
        # A Total cell under k with every other Total cell shown is N minus the rest.
        path = write_csv([["q"]] + [["a"]] * 8 + [["b"]] * 7 + [["c"]] * 2)
        t = run_json(path, "--rows", "q", "--anonymity")["tables"][0]
        hidden = [r["label"] for r in t["rows"] if r["cells"][0]["suppressed"]]
        self.assertGreaterEqual(len(hidden), 2)

    def test_random_tables(self):
        # 60 synthetic tables, fixed seed: every hidden small count keeps at least two possible values.
        import random
        rng = random.Random(20261119)
        for trial in range(60):
            answers = ["a", "b", "c"][: rng.randint(2, 3)]
            groups = {f"g{g}": [rng.choice([0, 0, 1, 2, 3, 4, 5, 6, 8]) for _ in answers]
                      for g in range(rng.randint(2, 4))}
            blank = [rng.choice(answers) for _ in range(rng.choice([0, 0, 0, 1, 2, 3]))]
            path = table_csv(groups, answers, blank)
            proc = run(path, "--rows", "q", "--banner", "team", "--anonymity", "--json")
            if proc.returncode != 0:
                continue
            with self.subTest(trial=trial, groups=groups, blank=blank):
                t = json.loads(proc.stdout)["tables"][0]
                assert_nothing_recoverable(self, t, 5, path, "q", "team")

    def test_random_multi_select_tables(self):
        # Multi-select: each answer row is Total = groups + no-group people; a group's cells are at most its base.
        import itertools
        import random

        def possible(t):
            cols = t["columns"]
            cats = [r for r in t["rows"] if r["kind"] == "category"]
            n_all, blank = cols[0]["n"], t["blank_banner"]
            hidden = [j for j in range(1, len(cols)) if cols[j]["n"] is None]
            mass = n_all - blank - sum(cols[j]["n"] for j in range(1, len(cols)) if cols[j]["n"] is not None)
            per_row = []
            for r in cats:
                unknown = [j for j in range(1, len(cols)) if r["cells"][j]["count"] is None]
                fixed = sum(r["cells"][j]["count"] for j in range(1, len(cols)) if r["cells"][j]["count"] is not None)
                options = []
                for tot in ([r["cells"][0]["count"]] if r["cells"][0]["count"] is not None else range(1, n_all + 1)):
                    ranges = [range(0 if cols[j]["n"] is None else 1, (mass if cols[j]["n"] is None else cols[j]["n"]) + 1)
                              for j in unknown] + [range(0, blank + 1)]
                    options += [dict(zip(unknown + ["blank"], v)) for v in itertools.product(*ranges)
                                if sum(v) == tot - fixed]
                per_row.append(options)
            poss = {}
            for combo in itertools.product(*per_row):
                if sum(max([1] + [c.get(j, 0) for c in combo]) for j in hidden) > mass:
                    continue
                for i, c in enumerate(combo):
                    for j, v in c.items():
                        poss.setdefault((i, j), set()).add(v)
            return poss

        rng = random.Random(7)
        for trial in range(25):
            options = ["a", "b", "c"][: rng.randint(2, 3)]
            rows, true = [["team", "q"]], {}
            for g in range(rng.randint(2, 3)):
                for _ in range(rng.choice([1, 2, 3, 4, 6, 7])):
                    pick = [o for o in options if rng.random() < 0.5] or [options[0]]
                    rows.append([f"g{g}", ";".join(pick)])
                    for o in pick:
                        true[(f"g{g}", o)] = true.get((f"g{g}", o), 0) + 1
            rows += [["", rng.choice(options)] for _ in range(rng.choice([0, 0, 1, 2]))]
            proc = run(write_csv(rows), "--rows", "q", "--multi", "q", "--banner", "team", "--anonymity", "--json")
            if proc.returncode != 0:
                continue
            t = json.loads(proc.stdout)["tables"][0]
            poss = possible(t)
            cats = [r for r in t["rows"] if r["kind"] == "category"]
            for i, r in enumerate(cats):
                for j, col in enumerate(t["columns"]):
                    if j and r["cells"][j]["suppressed"]:
                        value = true.get((col["label"], r["label"]), 0)
                        with self.subTest(trial=trial, cell=(col["label"], r["label"])):
                            self.assertIn(value, poss[(i, j)])
                            if 0 < value < 5:
                                self.assertGreater(len(poss[(i, j)]), 1)

    def test_json_never_carries_a_hidden_base(self):
        # Codex: mean_row.cells[i].n_eff was the hidden group's exact headcount.
        path = write_csv([["q", "g", "n"], ["1", "A", "2"], ["2", "B", "10"], ["1", "B", "9"]])
        out = run_json(path, "--rows", "q", "--banner", "g", "--count-col", "n", "--anonymity", "5", "--means")
        t = out["tables"][0]
        for ci, col in enumerate(t["columns"]):
            if col["suppressed"]:
                self.assertIsNone(col["n"])
                self.assertIsNone(t["mean_row"]["cells"][ci]["n_eff"])
                self.assertEqual(set(col), set(xt.COLUMN_FIELDS))

    def test_whole_sample_under_k_is_refused(self):
        path = write_csv([["q", "g"], ["Yes", "A"], ["No", "A"], ["Yes", "B"]])
        proc = run(path, "--rows", "q", "--banner", "g", "--anonymity")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")

    def test_same_groups_hidden_and_same_letters_in_every_table(self):
        # Opus: a group hidden in one question but shown in another can be subtracted; letters shifted when a
        # group had no answers to one question.
        rows = [["team", "q1", "q2"]]
        rows += [["Alpha", "y", ""]] * 4 + [["Alpha", "n", ""]] * 4
        rows += [["Beta", "y", "y"]] * 6 + [["Beta", "n", "n"]] * 6
        rows += [["Gamma", "y", "y"]] * 6 + [["Gamma", "n", "n"]] * 6
        rows += [["Delta", "y", "y"]] * 2 + [["Delta", "n", "n"]] * 2 + [["Delta", "n", "y"]] * 4
        out = run_json(write_csv(rows), "--rows", "q1", "q2", "--banner", "team", "--anonymity")
        letters = [{c["label"]: c["letter"] for c in t["columns"][1:]} for t in out["tables"]]
        for label, letter in letters[1].items():
            self.assertEqual(letters[0][label], letter)
        hidden = [{c["label"] for c in t["columns"] if c["suppressed"]} for t in out["tables"]]
        shown_everywhere = [{c["label"] for c in t["columns"][1:] if not c["suppressed"]} for t in out["tables"]]
        self.assertFalse(hidden[0] & shown_everywhere[1])
        self.assertFalse(hidden[1] & shown_everywhere[0])
        forced = run_json(write_csv(rows), "--rows", "q1", "--banner", "team", "--anonymity", "--hide",
                          "team=gamma")["tables"][0]
        self.assertTrue(next(c for c in forced["columns"] if c["label"] == "Gamma")["suppressed"])
        self.assertEqual(run(write_csv(rows), "--rows", "q1", "--banner", "team", "--anonymity", "--hide",
                             "team=Nobody").returncode, 2)


class ReviewRegressions(unittest.TestCase):
    def test_codes_need_a_delimiter(self):
        path = write_csv([["q"], ["1 week"], ["1 month"], ["1 year"], ["2 years"], ["18 to 24"], ["50k-75k"],
                          ["5 - Very"], ["(4) Good"]])
        t = run_json(path, "--rows", "q")["tables"][0]
        labels = {r["label"] for r in t["rows"]}
        self.assertTrue({"1 week", "1 month", "1 year", "2 years", "18 to 24", "50k-75k"} <= labels)
        self.assertEqual(xt.code_of("5 - Very"), 5)
        self.assertEqual(xt.code_of("(4) Good"), 4)
        self.assertIsNone(xt.code_of("18 to 24"))
        self.assertIsNone(xt.code_of("1 week"))
        two_labels = run_json(write_csv([["q"], ["1. Jan"], ["1. Feb"], ["2. Mar"]]), "--rows", "q")["tables"][0]
        self.assertEqual(len(two_labels["rows"]), 3)

    def test_count_and_weight_numbers(self):
        counts = write_csv([["q", "n"], ["Y", "1,000"], ["N", "1"]])
        self.assertEqual(run_json(counts, "--rows", "q", "--count-col", "n")["input"]["respondents"], 1001)
        weights = write_csv([["q", "w"], ["Y", "1,250"], ["N", "1"]])
        proc = run(weights, "--rows", "q", "--weight", "w")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("1250", proc.stderr)  # the message names both readings
        self.assertIn("1.250", proc.stderr)
        self.assertEqual(xt.parse_number("0,75"), 0.75)
        self.assertEqual(xt.parse_number("1,020,000"), 1020000)

    def test_duplicate_net_is_refused(self):
        path = write_csv([["q"]] + [["Y"]] * 6 + [["N"]] * 4)
        self.assertEqual(run(path, "--rows", "q", "--net", "q:Fav=Y", "--net", "q:Fav=Y").returncode, 2)

    def test_far_tail_p_and_flat_groups(self):
        self.assertGreater(xt.norm_two_sided(13.4), 0)
        path = table_csv({"A": [95, 5], "B": [5, 95]}, ["1", "2"])
        t = run_json(path, "--rows", "q", "--banner", "team")["tables"][0]
        self.assertGreater(t["tests"][0]["p"], 0)
        flat = table_csv({"A": [30, 0], "B": [0, 30]}, ["1", "2"])
        t = run_json(flat, "--rows", "q", "--banner", "team", "--means")["tables"][0]
        mean_test = next(x for x in t["tests"] if x["row"] == "Mean")
        self.assertIsNone(mean_test["p"])
        self.assertFalse(mean_test["significant"])

    def test_rescaled_and_constant_weights(self):
        def weighted(groups, w):
            rows = [["team", "q", "w"]]
            for g, counts in groups.items():
                for a, n in zip(["1", "2"], counts):
                    rows += [[g, a, w]] * n
            return write_csv(rows)
        base = {"A": [10, 20], "B": [20, 10]}
        runs = [run_json(weighted(base, w), "--rows", "q", "--banner", "team", "--weight", "w")["tests_run"]
                for w in ("1", "0.1", "0.3", "7")]
        self.assertEqual(len(set(runs)), 1)
        sparse = {"A": [0, 30], "B": [6, 24]}
        plain = run_json(table_csv(sparse, ["1", "2"]), "--rows", "q", "--banner", "team")["tables"][0]["tests"][0]
        ones = run_json(weighted(sparse, "1"), "--rows", "q", "--banner", "team", "--weight", "w")["tables"][0]
        self.assertAlmostEqual(ones["tests"][0]["p"], plain["p"], places=12)
        proc = run(weighted(base, "0"), "--rows", "q", "--banner", "team", "--weight", "w")
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)

    def test_letters_are_tokens(self):
        rows = [["team", "q"]]
        names = [f"t{i:02d}" for i in range(28)]
        for i, name in enumerate(names):
            yes = 30 if i == 1 else (0 if i == 26 else 15)
            rows += [[name, "Yes"]] * yes + [[name, "No"]] * (30 - yes)
        t = run_json(write_csv(rows), "--rows", "q", "--banner", "team", "--adjust", "none")["tables"][0]
        b = next(i for i, c in enumerate(t["columns"]) if c["letter"] == "B")
        self.assertIn("AA", list(row(t, "Yes")["cells"][b]["letters"]))

    def test_test_none_is_descriptive_only(self):
        t = run_json(table_csv({"A": [10, 20], "B": [20, 10]}, ["1", "2"]), "--rows", "q", "--banner", "team",
                     "--test", "none")["tables"][0]
        self.assertIsNone(t["chi_square"]["statistic"])
        self.assertEqual(t["tests_run"], 0)

    def test_total_is_not_listed_as_untested_small_base(self):
        out = run(table_csv({"A": [5, 5], "B": [5, 5]}, ["1", "2"]), "--rows", "q", "--banner", "team").stdout
        line = next(x for x in out.splitlines() if x.startswith("! Small base"))
        self.assertNotIn("Total", line)

    def test_broken_csv_and_bad_bytes(self):
        handle = tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False)
        handle.write(b'g,q\nEast,"No\nWest,Yes\n')
        handle.close()
        proc = run(handle.name, "--rows", "q", "--banner", "g")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("line 2", proc.stderr)
        handle = tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False)
        handle.write(b"\xef\xbb\xbfg,q\nA,\xff\n")
        handle.close()
        proc = run(handle.name, "--rows", "q")
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)



class InputHandling(unittest.TestCase):
    rows = [["id", "seg", "q", "w"]] + [[str(i), "a" if i % 2 else "b", str(1 + i % 3), "1"] for i in range(40)]

    def check_same(self, path, *extra):
        out = run_json(path, "--rows", "q", "--banner", "seg", *extra)["tables"][0]
        self.assertEqual(out["columns"][0]["n"], 40)
        return out

    def test_bom_utf16_crlf_semicolon_tab(self):
        self.check_same(write_csv(self.rows, encoding="utf-8-sig"))
        self.check_same(write_csv(self.rows, encoding="utf-16"))
        self.check_same(write_csv(self.rows, newline="\r\n"))
        self.check_same(write_csv(self.rows, delimiter=";"))
        self.check_same(write_csv(self.rows, delimiter="\t"), "--delimiter", "tab")

    def test_qualtrics_three_row_header(self):
        rows = [self.rows[0], ["ID", "Segment", "Question", "Weight"],
                ['{"ImportId":"a"}', '{"ImportId":"b"}', '{"ImportId":"c"}', '{"ImportId":"d"}']] + self.rows[1:]
        out = run_json(write_csv(rows), "--rows", "q", "--banner", "seg")
        self.assertEqual(out["tables"][0]["columns"][0]["n"], 40)
        self.assertTrue(any("Qualtrics" in n for n in out["input"]["notes"]))

    def test_refusals(self):
        dup = write_csv([["q", "q"], ["1", "2"]])
        self.assertEqual(run(dup, "--rows", "q").returncode, 2)
        empty = write_csv([["q", "seg"]])
        self.assertEqual(run(empty, "--rows", "q", "--banner", "seg").returncode, 2)
        self.assertEqual(run(write_csv(self.rows), "--rows", "nope").returncode, 2)
        self.assertEqual(run(write_csv(self.rows)).returncode, 2)
        bad = [r[:] for r in self.rows]
        for r in bad[1:4]:
            r[3] = "heavy"
        proc = run(write_csv(bad), "--rows", "q", "--banner", "seg", "--weight", "w")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--allow-drop", proc.stderr)
        out = run_json(write_csv(bad), "--rows", "q", "--banner", "seg", "--weight", "w", "--allow-drop")
        self.assertEqual(out["input"]["rows_used"], 37)
        ragged = write_csv([["q", "seg"], ["1", "a", "x"]])
        self.assertEqual(run(ragged, "--rows", "q").returncode, 2)

    def test_tiny_and_degenerate_inputs(self):
        one = run_json(write_csv([["q", "seg"], ["1", "a"]]), "--rows", "q", "--banner", "seg")["tables"][0]
        self.assertEqual(one["columns"][0]["n"], 1)
        self.assertEqual(one["tests_run"], 0)
        same = run_json(write_csv([["q", "seg"]] + [["yes", "a" if i % 2 else "b"] for i in range(80)]),
                        "--rows", "q", "--banner", "seg")["tables"][0]
        self.assertIsNone(same["chi_square"]["statistic"])
        single_seg = run_json(write_csv([["q", "seg"]] + [[str(i % 2), "a"] for i in range(50)]),
                              "--rows", "q", "--banner", "seg")["tables"][0]
        self.assertEqual(single_seg["tests_run"], 0)
        self.assertIsNone(single_seg["chi_square"]["statistic"])
        ties = run_json(write_csv([["q", "seg"]] + [[str(i % 2), "a" if i < 50 else "b"] for i in range(100)]),
                        "--rows", "q", "--banner", "seg")["tables"][0]
        self.assertTrue(all(not t["significant"] for t in ties["tests"]))
        self.assertTrue(all(c["letters"] == [] for r in ties["rows"] for c in r["cells"]))

    def test_list_columns_and_text_report(self):
        out = run_json(FIXTURES / "basic.input.csv", "--list-columns")
        cols = {c["column"]: c for c in out["columns"]}
        self.assertTrue(cols["satisfaction"]["numeric_codes"])
        self.assertTrue(cols["features"]["looks_multi_select"])
        proc = run(FIXTURES / "basic.input.csv", "--rows", "satisfaction", "--banner", "plan")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("| Base (n) |", proc.stdout)

    def test_input_is_never_modified(self):
        path = FIXTURES / "basic.input.csv"
        before = path.read_bytes()
        run(path, "--rows", "satisfaction", "--banner", "plan", "--weight", "weight", "--means")
        self.assertEqual(before, path.read_bytes())


class GeminiReviewRegressions(unittest.TestCase):
    """Third (Gemini) review, 2026-11-19, findings 5 to 16. Each failed before the fix."""

    def test_constant_weight_other_than_one_leaves_chi_square_unchanged(self):
        rows = [["q", "g", "w"]]
        for g, yes, no in (("A", 30, 20), ("B", 20, 30)):
            rows += [["Yes", g, "2.0"]] * yes + [["No", g, "2.0"]] * no
        t = run_json(write_csv(rows), "--rows", "q", "--banner", "g", "--weight", "w")["tables"][0]
        self.assertAlmostEqual(t["chi_square"]["statistic"], 4.0, places=9)

    def test_cell_note_does_not_split_small_and_complementary_counts(self):
        rows = [["q"]] + [["Yes"]] + [["No"]] * 5 + [["Maybe"]] * 5
        out = run(write_csv(rows), "--rows", "q", "--anonymity", "5").stdout
        self.assertNotIn("complementary cell", out)
        self.assertIn("2 cell(s) hidden", out)

    def test_withheld_table_json_has_no_counts_or_groups(self):
        rows = [["q1", "q2", "team"]] + [["a", "x", "Eng"]] + [["a", "", "Eng"]] * 9 + [["b", "", "Legal"]] * 10
        t = next(t for t in run_json(write_csv(rows), "--rows", "q2", "--banner", "team", "--anonymity", "5")["tables"])
        self.assertTrue(t["withheld"])
        self.assertIsNone(t["blank_row"])
        self.assertEqual(t["columns"], [])

    def test_groups_with_no_answers_stay_listed_under_anonymity(self):
        rows = [["q1", "q2", "team"]] + [["a", "x", "Eng"]] * 10 + [["b", "y", "Sales"]] * 10 + [["b", "", "Legal"]] * 2
        tables = run_json(write_csv(rows), "--rows", "q1", "q2", "--banner", "team", "--anonymity", "5")["tables"]
        q2 = next(t for t in tables if t["row_var"] == "q2")
        self.assertIn("Legal", [c["label"] for c in q2["columns"]])

    def test_repeated_hide_flags_add_up(self):
        rows = [["q", "team"]] + [["Yes", "Legal"]] * 6 + [["No", "Legal"]] * 4 + [["Yes", "HR"]] * 6 \
            + [["No", "HR"]] * 5 + [["Yes", "Eng"]] * 8 + [["No", "Eng"]] * 7
        t = run_json(write_csv(rows), "--rows", "q", "--banner", "team", "--anonymity", "5", "--hide", "team=Legal",
                     "--hide", "team=HR")["tables"][0]
        hidden = {c["label"] for c in t["columns"] if c["suppressed"]}
        self.assertTrue({"Legal", "HR"} <= hidden)
        proc = run(write_csv(rows), "--rows", "q", "--banner", "team", "--order", "q=Yes;No", "--order", "q=No;Yes")
        self.assertEqual(proc.returncode, 2)

    def test_all_zero_counts_stop_cleanly(self):
        rows = [["q", "g", "count", "w"], ["Yes", "A", "0", "1.5"], ["No", "A", "0", "1.2"], ["Yes", "B", "0", "1"]]
        proc = run(write_csv(rows), "--rows", "q", "--banner", "g", "--count-col", "count", "--weight", "w")
        self.assertEqual(proc.returncode, 2, proc.stderr)

    def test_leading_zero_comma_is_a_decimal(self):
        self.assertIsNone(xt.parse_count("0,500"))
        self.assertAlmostEqual(xt.parse_number("0,750"), 0.75)

    def test_cramers_v(self):
        t = run_json(FIXTURES / "agresti_party_gender.input.csv", "--count-col", "count", "--rows", "party",
                     "--banner", "gender")["tables"][0]
        self.assertAlmostEqual(t["chi_square"]["cramers_v"], math.sqrt(30.0701490958 / 2757), places=6)

    def test_pipes_in_labels_do_not_break_the_markdown_table(self):
        rows = [["q", "g"]] + [["Yes | sure", "A"]] * 3 + [["No", "A"]] * 2
        out = run(write_csv(rows), "--rows", "q", "--banner", "g").stdout
        self.assertIn("Yes \\| sure", out)


if __name__ == "__main__":
    unittest.main()
