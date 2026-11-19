"""Tests for scripts/likert_analysis.py. Run from the skill folder: python3 -m unittest discover -s tests

Expected values come from fixtures/*.expected.json: published examples (Kromrey et al. 2008 for alpha and
its Feldt interval; Hollander and Wolfe 1973 via R's wilcox.test example for Mann-Whitney) or synthetic data
worked out by independent methods (fixtures/README.md).
"""
import importlib.util
import itertools
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "likert_analysis.py"


def load_module():
    spec = importlib.util.spec_from_file_location("likert_analysis", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(module)
    return module


M = load_module()


def run(*args):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                          check=False)


def run_json(*args):
    proc = run(*args, "--json")
    if proc.returncode != 0:
        raise AssertionError(f"exit {proc.returncode}: {proc.stderr}")
    return json.loads(proc.stdout)


def expected(name):
    return json.loads((FIXTURES / f"{name}.expected.json").read_text())


def write(tmp, name, text, encoding="utf-8"):
    path = pathlib.Path(tmp) / name
    path.write_bytes(text.encode(encoding))
    return path


def hoyt_alpha(matrix):
    """Independent check: Hoyt (1941) reliability from a persons x items ANOVA, 1 - MS_residual / MS_persons."""
    n, k = len(matrix), len(matrix[0])
    grand = sum(map(sum, matrix)) / (n * k)
    ss_persons = k * sum((sum(r) / k - grand) ** 2 for r in matrix)
    ss_items = n * sum((sum(r[j] for r in matrix) / n - grand) ** 2 for j in range(k))
    ss_total = sum((x - grand) ** 2 for r in matrix for x in r)
    ss_resid = ss_total - ss_persons - ss_items
    return 1 - (ss_resid / ((n - 1) * (k - 1))) / (ss_persons / (n - 1))


class PublishedExamplesTest(unittest.TestCase):
    def test_kromrey_alpha_and_feldt_interval(self):
        exp = expected("kromrey_2008")
        out = run_json(FIXTURES / "kromrey_2008.input.csv", "--items", "X1,X2,X3,X4,X5", "--scale", "0-1", "--alpha")
        rel = out["reliability"]
        self.assertEqual((rel["n_complete"], rel["k"]), (exp["n"], exp["k"]))
        self.assertAlmostEqual(rel["alpha"], exp["alpha"], delta=0.0005)
        self.assertAlmostEqual(rel["alpha_ci"][0], exp["feldt_ci"][0], delta=0.0005)
        self.assertAlmostEqual(rel["alpha_ci"][1], exp["feldt_ci"][1], delta=0.0005)

    def test_alpha_matches_hoyt_anova(self):
        rows = [[int(c) for c in s] for s in ["10000", "11000", "11100", "11110", "11111", "00000"] * 2]
        self.assertAlmostEqual(M.cronbach_alpha(rows), hoyt_alpha(rows), delta=1e-12)

    def test_mann_whitney_hollander_wolfe(self):
        exp = expected("mann_whitney_hollander_wolfe")
        got = M.mann_whitney(exp["x"], exp["y"])
        self.assertEqual(got["u"], exp["w"])
        self.assertEqual(got["method"], "exact")
        self.assertAlmostEqual(got["p_value"], exp["p_two_sided"], delta=0.00005)

    def test_exact_conditional_matches_brute_force(self):
        for x, y in (([5, 4, 4, 3, 5], [2, 3, 3, 4, 1, 3]), ([3, 3, 3, 4], [3, 3, 2, 2, 4]),
                     ([1, 2, 2, 5, 5, 4], [2, 2, 3, 3, 3, 1, 5])):
            combined = x + y
            ranks = M.midranks(combined)
            observed = sum(ranks[: len(x)])
            sums = [sum(ranks[i] for i in c) for c in itertools.combinations(range(len(combined)), len(x))]
            below = sum(1 for s in sums if s <= observed + 1e-9) / len(sums)
            above = sum(1 for s in sums if s >= observed - 1e-9) / len(sums)
            got = M.mann_whitney(x, y)
            self.assertEqual(got["method"], "exact conditional on ties")
            self.assertAlmostEqual(got["p_value"], min(1.0, 2 * min(below, above)), delta=1e-12)

    def test_f_quantile_round_trip(self):
        for q, d1, d2 in ((0.975, 11, 44), (0.025, 11, 44), (0.5, 3, 7), (0.95, 1, 200)):
            self.assertAlmostEqual(M.f_cdf(M.f_quantile(q, d1, d2), d1, d2), q, delta=1e-10)


class EngagementFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exp = expected("engagement")
        cls.args = [FIXTURES / "engagement.input.csv", "--items-prefix", "eng_", "--scale", "1-5"]
        cls.raw = run_json(*cls.args, "--alpha")
        cls.fixed = run_json(*cls.args, "--alpha", "--reverse", "eng_3", "--group-col", "team",
                             "--compare", "north", "south", "--mw-method", "normal")

    def test_labels_scale_and_exclusions(self):
        self.assertEqual(self.raw["input"]["labels"]["source"], "agree5")
        self.assertEqual((self.raw["scale"]["min"], self.raw["scale"]["max"]), (1, 5))
        self.assertEqual(self.raw["input"]["cells_excluded"], self.exp["excluded"])
        self.assertEqual(self.raw["scale"]["neutral_point"], 3)

    def test_item_distributions_boxes_and_means(self):
        got = {s["item"]: s for s in self.raw["items"]}
        for name, want in self.exp["items"].items():
            self.assertEqual(got[name]["n"], want["n"])
            self.assertEqual(got[name]["distribution"], want["distribution"])
            self.assertEqual(got[name]["top_box"], want["top_box"])
            self.assertAlmostEqual(got[name]["mean"], want["mean"], delta=1e-6)
        eng1 = got["eng_1"]
        for g, w in zip(eng1["top_box_ci"], self.exp["items"]["eng_1"]["top_box_ci"]):
            self.assertAlmostEqual(g, w, delta=1e-3)
        self.assertEqual(eng1["median"], 3)
        d = eng1["diverging"]
        self.assertAlmostEqual(d["negative"] + d["neutral"] + d["positive"], 100.0, delta=1e-9)

    def test_reverse_item_is_detected_then_fixed(self):
        rel = self.raw["reliability"]
        self.assertAlmostEqual(rel["alpha"], self.exp["alpha_raw"], delta=1e-6)
        worst = min(rel["per_item"], key=lambda e: e["corrected_item_total_r"])
        self.assertEqual(worst["item"], "eng_3")
        self.assertTrue(any("--reverse" in w and "eng_3" in w for w in self.raw["warnings"]))
        fixed = self.fixed["reliability"]
        self.assertAlmostEqual(fixed["alpha"], self.exp["alpha_with_eng_3_reversed"], delta=1e-6)
        self.assertEqual(fixed["n_complete"], self.exp["n_complete"])
        self.assertTrue(all(e["corrected_item_total_r"] > 0 for e in fixed["per_item"]))
        self.assertLess(fixed["alpha_ci"][0], fixed["alpha"])
        self.assertGreater(fixed["alpha_ci"][1], fixed["alpha"])

    def test_unreversed_scale_is_not_compared_and_negative_alpha_warned(self):
        out = run_json(*self.args, "--alpha", "--group-col", "team", "--compare", "north", "south")
        scale = next(t for t in out["comparisons"] if t["item"] == "(scale score)")
        self.assertFalse(scale["tested"])
        self.assertIn("reverse coding", scale["note"])
        self.assertTrue(any("Alpha is negative" in w for w in out["warnings"]))

    def test_alpha_if_deleted_matches_recomputation(self):
        # Alpha-if-deleted keeps the listwise sample of the full scale. Deleting eng_2 or eng_3 leaves that sample
        # unchanged (the two incomplete respondents skipped eng_1 and eng_4), so a fresh run must agree.
        for entry in self.fixed["reliability"]["per_item"]:
            if entry["item"] not in ("eng_2", "eng_3"):
                continue
            items = [i for i in ("eng_1", "eng_2", "eng_3", "eng_4") if i != entry["item"]]
            out = run_json(*self.args, "--reverse", "eng_3", "--scale-items", ",".join(items))
            self.assertAlmostEqual(entry["alpha_if_deleted"], out["reliability"]["alpha"], delta=1e-12)

    def test_group_comparisons_normal_approximation(self):
        tests = {t["item"]: t for t in self.fixed["comparisons"]}
        # Item tests compare the answers as given: --reverse changes only the reliability check and scale score.
        for item, want in self.exp["north_vs_south_as_answered"].items():
            self.assertEqual(tests[item]["u"], want["u"])
            self.assertAlmostEqual(tests[item]["z"], want["z"], delta=1e-6)
            self.assertAlmostEqual(tests[item]["p_value"], want["p_value"], delta=1e-6)
        self.assertIn("(scale score)", tests)
        self.assertEqual(tests["(scale score)"]["test"], "Welch t")

    def test_default_is_exact_for_small_groups_and_holm(self):
        out = run_json(*self.args, "--reverse", "eng_3", "--alpha", "--group-col", "team", "--compare", "north",
                       "south", "--adjust", "holm")
        item_tests = [t for t in out["comparisons"] if t["item"].startswith("eng_")]
        self.assertTrue(all(t["test"] == "Mann-Whitney (exact conditional on ties)" for t in item_tests))
        # Holm covers every reported test: 4 rank tests, 4 top-box tests and the scale-score Welch test.
        family = [t for t in out["comparisons"] if t.get("tested")] + [t["top_box"] for t in item_tests]
        self.assertEqual(len(family), 9)
        self.assertEqual({t["family_size"] for t in family}, {9})
        ordered = sorted(family, key=lambda t: t["p_value"])
        running = 0.0
        for rank, t in enumerate(ordered):
            running = max(running, min(1.0, (9 - rank) * t["p_value"]))
            self.assertAlmostEqual(t["p_adjusted"], running, delta=1e-12)
        eng_2 = next(t for t in item_tests if t["item"] == "eng_2")
        self.assertEqual(eng_2["verdict"], "not significant")  # significant when Holm skipped the top-box tests

    def test_table_out_and_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "t" / "div.csv"
            run_json(*self.args, "--table-out", path)
            lines = path.read_text().splitlines()
            self.assertTrue(lines[0].startswith("item,n,unreadable,reversed_in_scale_score,pct_1"))
            self.assertEqual(len(lines), 5)
            copy = pathlib.Path(tmp) / "in.csv"
            copy.write_bytes((FIXTURES / "engagement.input.csv").read_bytes())
            self.assertEqual(run(copy, "--items-prefix", "eng_", "--scale", "1-5", "--table-out", copy).returncode, 2)
            self.assertEqual(copy.read_bytes(), (FIXTURES / "engagement.input.csv").read_bytes())
        proc = run(*self.args, "--alpha", "--reverse", "eng_3")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Cronbach's alpha 0.882", proc.stdout)

    def test_deterministic(self):
        args = (*self.args, "--group-col", "team", "--pairwise", "--alpha", "--json")
        self.assertEqual(run(*args).stdout, run(*args).stdout)


class InputAndEdgeCaseTest(unittest.TestCase):
    def test_encodings_delimiters_qualtrics(self):
        text = (FIXTURES / "engagement.input.csv").read_text()
        reference = run_json(FIXTURES / "engagement.input.csv", "--items-prefix", "eng_", "--scale", "1-5")["items"]
        lines = text.splitlines()
        width = len(lines[0].split(","))
        qualtrics = "\n".join([lines[0], ",".join(["question"] * width),
                               ",".join('"{""ImportId"":""QID%d""}"' % i for i in range(width))] + lines[1:]) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            for name, body, enc in (("bom.csv", "﻿" + text.replace("\n", "\r\n"), "utf-8"),
                                    ("u16.csv", text, "utf-16"), ("tab.csv", text.replace(",", "\t"), "utf-8"),
                                    ("q.csv", qualtrics, "utf-8")):
                got = run_json(write(tmp, name, body, enc), "--items-prefix", "eng_", "--scale", "1-5")["items"]
                self.assertEqual([g["distribution"] for g in got], [r["distribution"] for r in reference], name)

    def test_refuses_unreadable_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = write(tmp, "b.csv", "q1,q2\n" + "4,5\n" * 9 + "Love it,8\n")
            proc = run(bad, "--items", "q1,q2", "--scale", "1-5")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("more than 5%", proc.stderr)
            out = run_json(bad, "--items", "q1,q2", "--scale", "1-5", "--allow-unreadable")
            self.assertEqual(out["input"]["cells_excluded"], {"non_numeric": 1, "out_of_range": 1})
            dup = write(tmp, "d.csv", "q1,q1\n1,2\n")
            self.assertIn("more than one column named", run(dup, "--items", "q1").stderr)

    def test_items_must_be_named(self):
        proc = run(FIXTURES / "engagement.input.csv")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--items", proc.stderr)

    def test_single_respondent_and_all_same(self):
        with tempfile.TemporaryDirectory() as tmp:
            one = run_json(write(tmp, "o.csv", "q1,q2\n4,5\n"), "--items", "q1,q2", "--scale", "1-5", "--alpha")
            self.assertEqual(one["items"][0]["n"], 1)
            self.assertNotIn("mean_ci", one["items"][0])
            self.assertIn("at least 3", one["reliability"]["note"])
            same = run_json(write(tmp, "s.csv", "q1,q2\n" + "3,3\n" * 6), "--items", "q1,q2", "--scale", "1-5",
                            "--alpha")
            self.assertEqual(same["items"][0]["mean_ci"], [3.0, 3.0])
            self.assertIn("undefined", same["reliability"]["note"])
            self.assertTrue(any("every answer is the same" in w for w in same["warnings"]))

    def test_even_median_and_four_point_scale(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(write(tmp, "f.csv", "q\n1\n2\n3\n4\n"), "--items", "q", "--scale", "1-4")
            item = out["items"][0]
            self.assertEqual(item["median"], 2.5)
            self.assertIn("median_note", item)
            self.assertIsNone(out["scale"]["neutral_point"])
            self.assertEqual(item["top_box_points"], [3, 4])
            self.assertEqual(item["diverging"]["neutral"], 0.0)

    def test_tiny_groups_get_no_verdict_and_one_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "g.csv", "g,q\na,5\na,4\nb,1\nb,2\nb,2\nb,3\nb,1\n")
            out = run_json(path, "--items", "q", "--scale", "1-5", "--group-col", "g", "--compare", "a", "b")
            self.assertFalse(out["comparisons"][0]["tested"])
            single = run_json(write(tmp, "s.csv", "g,q\na,5\na,4\n"), "--items", "q", "--scale", "1-5",
                              "--group-col", "g", "--pairwise")
            self.assertTrue(any("Only one group" in w for w in single["warnings"]))

    def test_seven_point_box_and_custom_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(write(tmp, "s.csv", "q\n7\n6\n5\n4\n1\n"), "--items", "q", "--scale", "1-7")
            self.assertEqual(out["items"][0]["top_box_points"], [6, 7])
            out = run_json(write(tmp, "s3.csv", "q\n7\n6\n5\n4\n1\n"), "--items", "q", "--scale", "1-7", "--box", "3")
            self.assertEqual(out["items"][0]["top_box"], 3)
            freq = run_json(write(tmp, "fr.csv", "q\nNever\nOften\nAlways\nSometimes\n"), "--items", "q")
            self.assertEqual(freq["input"]["labels"]["source"], "frequency5")
            custom = run_json(write(tmp, "c.csv", "q\nLow\nHigh\nMid\n"), "--items", "q", "--labels",
                              "Low=1,Mid=2,High=3")
            self.assertEqual(custom["items"][0]["mean"], 2.0)


class ReviewRegressionTest(unittest.TestCase):
    """Cases from the 2026-11-19 review. Each failed on the version before the fix."""

    def test_given_scale_picks_the_matching_label_map(self):
        # --scale 1-7 used to read "Agree" and "Neutral" with the 5-point map: top box 0%, mean 3.5.
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(write(tmp, "a.csv", "q\nAgree\nNeutral\n"), "--items", "q", "--scale", "1-7")
            self.assertEqual(out["input"]["labels"]["source"], "agree7")
            self.assertEqual(out["items"][0]["mean"], 5.0)
            self.assertEqual(out["items"][0]["pct_top_box"], 50.0)

    def test_labels_map_sets_the_scale(self):
        # Low=1,Mid=2,High=3 used to be read on an inferred 1-5 scale: top box 0% instead of 33.3%.
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(write(tmp, "c.csv", "q\nLow\nMid\nHigh\n"), "--items", "q", "--labels", "Low=1,Mid=2,High=3")
            self.assertEqual((out["scale"]["min"], out["scale"]["max"]), (1, 3))
            self.assertAlmostEqual(out["items"][0]["pct_top_box"], 100 / 3, delta=1e-9)
            proc = run(write(tmp, "x.csv", "q\nLow\n"), "--items", "q", "--labels", "Low=X")
            self.assertEqual(proc.returncode, 2)
            self.assertNotIn("Traceback", proc.stderr)

    def test_numeric_scale_is_never_guessed(self):
        # 1-4 answers from a 5-point item used to become a 1-4 scale with the midpoint in the top box.
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "n.csv", "q\n" + "1\n2\n3\n4\n" * 2)
            proc = run(path, "--items", "q")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("--scale", proc.stderr)
            self.assertEqual(run_json(path, "--items", "q", "--scale", "1-5")["items"][0]["pct_top_box"], 25.0)

    def test_five_point_somewhat_labels(self):
        # Strongly/somewhat/neither labels used to be read as the 7-point map (top box = strongly agree only).
        text = "q\nStrongly disagree\nSomewhat disagree\nNeither agree nor disagree\nSomewhat agree\nStrongly agree\nSomewhat agree\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "s.csv", text)
            self.assertEqual(run(path, "--items", "q").returncode, 2)
            out = run_json(path, "--items", "q", "--scale", "1-5")
            self.assertEqual(out["input"]["labels"]["source"], "agree5-somewhat")
            self.assertAlmostEqual(out["items"][0]["pct_top_box"], 50.0, delta=1e-9)
            four = run_json(write(tmp, "f.csv", "q\nStrongly disagree\nDisagree\nAgree\nStrongly agree\n"),
                            "--items", "q", "--scale", "1-4")
            self.assertEqual(four["input"]["labels"]["source"], "agree4")  # could never be chosen before

    def test_reverse_keeps_items_as_answered(self):
        out = run_json(FIXTURES / "engagement.input.csv", "--items-prefix", "eng_", "--scale", "1-5",
                       "--reverse", "eng_3", "--alpha")
        eng_3 = next(s for s in out["items"] if s["item"] == "eng_3")
        self.assertEqual(eng_3["top_box"], 9)  # 9 of 40 agreed; reversing used to show the 20 who disagreed
        self.assertTrue(eng_3["reversed_in_scale_score"])
        self.assertAlmostEqual(out["reliability"]["alpha"], expected("engagement")["alpha_with_eng_3_reversed"],
                               delta=1e-6)

    def test_reliability_needs_two_distinct_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "r.csv", "q\n1\n2\n3\n")
            for chosen in ("q,q", ","):
                proc = run(path, "--items", "q", "--scale", "1-5", "--scale-items", chosen)
                self.assertEqual(proc.returncode, 2, chosen)
                self.assertNotIn("Traceback", proc.stderr)

    def test_item_total_correlations_shown_when_alpha_undefined(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(write(tmp, "o.csv", "a,b\n1,5\n2,4\n3,3\n4,2\n5,1\n"), "--items", "a,b", "--scale", "1-5",
                           "--alpha")
            rel = out["reliability"]
            self.assertNotIn("alpha", rel)
            self.assertEqual([round(e["corrected_item_total_r"], 9) for e in rel["per_item"]], [-1.0, -1.0])
            self.assertEqual(rel["direction_problem"], ["a", "b"])

    def test_effect_size_label_counts_ties_as_half(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "t.csv", "g,q\n" + "a,3\nb,3\n" * 5)
            proc = run(path, "--items", "q", "--scale", "1-5", "--group-col", "g", "--compare", "a", "b")
            self.assertIn("P(A > B) + half P(A = B) = 0.50", proc.stdout)
            self.assertNotIn("underpowered", proc.stdout)

    def test_unipolar_scales_have_no_neutral(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(write(tmp, "f.csv", "q\nSometimes\nSometimes\nNever\nAlways\n"), "--items", "q")
            self.assertEqual(out["scale"]["polarity"], "unipolar")
            self.assertIsNone(out["scale"]["neutral_point"])
            self.assertEqual(out["scale"]["region_labels"], ["low", "middle", "high"])
            flagged = run_json(write(tmp, "n.csv", "q\n1\n3\n5\n"), "--items", "q", "--scale", "1-5", "--unipolar")
            self.assertIsNone(flagged["scale"]["neutral_point"])

    def test_bars_share_a_centre_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run(write(tmp, "b.csv", "a,b\n1,5\n1,5\n2,4\n3,3\n"), "--items", "a,b", "--scale", "1-5")
            bars = [line.split("   ", 1)[1] for line in proc.stdout.splitlines() if line.startswith("      ")]
            self.assertEqual(len({b.index("|") for b in bars}), 1)

    def test_box_width_and_far_tail_p(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "q.csv", "q\n1\n2\n3\n4\n5\n")
            for width in ("-1", "0"):
                self.assertEqual(run(path, "--items", "q", "--scale", "1-5", "--box", width).returncode, 2)
            big = write(tmp, "big.csv", "g,q\n" + "a,1\nb,5\n" * 100)
            out = run_json(big, "--items", "q", "--scale", "1-5", "--group-col", "g", "--compare", "a", "b")
            self.assertGreater(out["comparisons"][0]["p_value"], 0.0)  # 3.5e-45, used to print 0.0

    def test_unreadable_item_is_stopped_and_kept_in_the_table(self):
        # One wholly unreadable item among 20 is exactly 5% of cells: it used to pass and vanish from the export.
        header = ",".join(f"q{i}" for i in range(20))
        good = ",".join(["3"] * 19)
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "w.csv", header + "\n" + (good + ",oops\n") * 10)
            items = header
            proc = run(path, "--items", items, "--scale", "1-5")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("q19", proc.stderr)
            table = pathlib.Path(tmp) / "t.csv"
            out = run_json(path, "--items", items, "--scale", "1-5", "--allow-unreadable", "--table-out", table)
            self.assertEqual(out["items"][19]["unreadable"], 10)
            self.assertIn("q19,0,10", table.read_text())

    def test_welch_needs_five_per_side(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "w.csv", "g,a,b\nx,1,2\nx,2,3\ny,4,5\ny,5,4\n")
            out = run_json(path, "--items", "a,b", "--scale", "1-5", "--alpha", "--group-col", "g", "--compare", "x", "y")
            scale = next(t for t in out["comparisons"] if t["item"] == "(scale score)")
            self.assertFalse(scale["tested"])

    def test_labelled_non_answer_words_are_points(self):
        # --labels "None=1,..." used to drop every "None" as a non-answer, so a whole point vanished.
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "n.csv", "q\nNone\nNone\nA little\nA lot\n")
            out = run_json(path, "--items", "q", "--labels", "None=1,A little=2,Some=3,A lot=4")
            self.assertEqual(out["items"][0]["n"], 4)
            self.assertEqual(out["items"][0]["distribution"]["1"], 2)

    def test_blank_group_left_out_of_pairwise(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = "g,q\n" + "a,4\na,5\nb,2\nb,1\n,3\n,3\n" * 5
            out = run_json(write(tmp, "g.csv", rows), "--items", "q", "--scale", "1-5", "--group-col", "g", "--pairwise")
            self.assertEqual({(t["a"], t["b"]) for t in out["comparisons"]}, {("a", "b")})
            self.assertEqual(run(write(tmp, "g2.csv", rows), "--items", "q", "--scale", "1-5", "--group-col", "g",
                                 "--compare", "a", "a").returncode, 2)

    def test_groups_are_printed_and_keys_match(self):
        proc = run(FIXTURES / "engagement.input.csv", "--items-prefix", "eng_", "--scale", "1-5", "--alpha",
                   "--reverse", "eng_3", "--group-col", "team", "--compare", "north", "south")
        self.assertIn("Group north (n = 20); scale score mean", proc.stdout)
        out = run_json(FIXTURES / "engagement.input.csv", "--items-prefix", "eng_", "--scale", "1-5", "--alpha",
                       "--reverse", "eng_3", "--group-col", "team", "--compare", "north", "south")
        scale = next(t for t in out["comparisons"] if t["item"] == "(scale score)")
        self.assertIn("n_a", scale)


class QaPolishRegressionTest(unittest.TestCase):
    """Usability fixes from the 2026-11-19 end-to-end QA."""

    def test_labelled_numbers_with_both_end_labels_set_the_scale(self):
        rows = "q1,q2\n1 - Strongly disagree,2 - Disagree\n5 - Strongly agree,4 - Agree\n3 - Neutral,3\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "l.csv", rows)
            out = run_json(path, "--items", "q1,q2")
            self.assertEqual((out["scale"]["min"], out["scale"]["max"]), (1, 5))
            self.assertIn("from the labelled answers", out["scale"]["source"])
            self.assertIn("from the labelled answers", run(path, "--items", "q1,q2").stdout)
            short = run(write(tmp, "s.csv", "q1\n2 - Disagree\n5 - Strongly agree\n"), "--items", "q1")
            self.assertEqual(short.returncode, 2)
            self.assertIn("does not read as an end point", short.stderr)


if __name__ == "__main__":
    unittest.main()
