"""Tests for scripts/gabor_granger_analysis.py. Run from the skill folder: python3 -m unittest discover -s tests

Expected values come from fixtures/*.expected.json (hand-worked in fixtures/README.md), from a published
example (SurveyMonkey's Gabor-Granger guide; Newcombe 1998 Table I), or are re-derived here by a second
method (Wilson limits by bisection on the score statistic, isotonic regression by the max-min formula).
"""
import importlib.util
import json
import math
import pathlib
import random
import subprocess
import sys
import tempfile
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "gabor_granger_analysis.py"
Z95 = 1.959963984540054


def load_module():
    spec = importlib.util.spec_from_file_location("gabor_granger_analysis", SCRIPT)
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


class PublishedSurveyMonkeyTest(unittest.TestCase):
    def test_counts_reproduce_revenue_index_and_peak(self):
        exp = expected("surveymonkey_published")
        out = run_json("--counts", exp["counts"], "--base", exp["base"], "--counts-sample", "same",
                       "--bootstrap", 0)
        g = out["groups"][0]
        for row, take, rev in zip(g["prices"], exp["take_rates"], exp["revenue_index"]):
            self.assertAlmostEqual(row["take_rate"], take, places=12)
            self.assertAlmostEqual(row["revenue_index"], rev, places=10)
        self.assertEqual(g["optimum"]["price"], exp["optimum"])
        self.assertTrue(g["optimum"]["named"])
        self.assertEqual(out["counts"]["read"], exp["base"])  # 200 people, not 5 x 200


class WilsonTest(unittest.TestCase):
    def test_newcombe_1998_table_1(self):
        # Newcombe (1998) Stat Med 17:857-872, Table I, method 3 (Wilson, no continuity correction).
        cases = [(81, 263, 0.2553, 0.3662), (15, 148, 0.0624, 0.1605), (0, 20, 0.0, 0.1611), (1, 29, 0.0061, 0.1718)]
        for x, n, low, high in cases:
            got = M.wilson(x, n, Z95)
            self.assertAlmostEqual(got[0], low, delta=0.00005)
            self.assertAlmostEqual(got[1], high, delta=0.00005)

    def test_wilson_matches_bisection_on_score_statistic(self):
        # Independent check: the Wilson limits are the p where |x/n - p| / sqrt(p(1-p)/n) = z.
        def bisect(x, n, lo, hi, upper):
            f = lambda p: abs(x / n - p) / math.sqrt(p * (1 - p) / n) - Z95
            for _ in range(200):
                mid = (lo + hi) / 2
                if (f(mid) > 0) == upper:
                    hi = mid
                else:
                    lo = mid
            return (lo + hi) / 2
        for x, n in ((15, 21), (19, 21), (3, 21), (7, 10)):
            low, high = M.wilson(x, n, Z95)
            self.assertAlmostEqual(low, bisect(x, n, 1e-12, x / n, False), places=9)
            self.assertAlmostEqual(high, bisect(x, n, x / n, 1 - 1e-12, True), places=9)
        self.assertAlmostEqual(M.wilson(15, 21, Z95)[0], 0.5004, places=4)
        self.assertAlmostEqual(M.wilson(15, 21, Z95)[1], 0.8619, places=4)


class PavaTest(unittest.TestCase):
    def test_hand_example(self):
        # Increasing isotonic fit of 1,3,2,4,3,5 is 1,2.5,2.5,3.5,3.5,5; negate for the decreasing fit.
        got = M.pava_decreasing([-1, -3, -2, -4, -3, -5], [1] * 6)
        for g, w in zip(got, [-1, -2.5, -2.5, -3.5, -3.5, -5]):
            self.assertAlmostEqual(g, w, places=12)

    def test_matches_max_min_formula(self):
        # Independent check: the non-increasing weighted isotonic fit is
        # f_i = min over s <= i of max over t >= i of the weighted mean of values s..t.
        rng = random.Random(7)
        for _ in range(200):
            k = rng.randint(1, 7)
            values = [rng.random() for _ in range(k)]
            weights = [rng.randint(1, 30) for _ in range(k)]

            def avg(s, t):
                return sum(values[j] * weights[j] for j in range(s, t + 1)) / sum(weights[s:t + 1])
            want = [min(max(avg(s, t) for t in range(i, k)) for s in range(i + 1)) for i in range(k)]
            got = M.pava_decreasing(values, weights)
            for g, w in zip(got, want):
                self.assertAlmostEqual(g, w, places=12)


class ElasticityTest(unittest.TestCase):
    def test_midpoint_textbook_example(self):
        # Price 4 -> 6, quantity 120 -> 80: (-40/100) / (2/5) = -1.0 (midpoint method).
        self.assertAlmostEqual(M.arc_elasticity(4, 120, 6, 80), -1.0, places=12)

    def test_undefined_when_no_demand(self):
        self.assertIsNone(M.arc_elasticity(10, 0, 20, 0))


class WideBasicTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exp = expected("wide_basic")
        cls.out = run_json(FIXTURES / "wide_basic.input.csv", "--bootstrap", 0)
        cls.profit = run_json(FIXTURES / "wide_basic.input.csv", "--unit-cost", cls.exp["unit_cost"],
                              "--bootstrap", 0)

    def test_counts(self):
        c = self.out["counts"]
        self.assertEqual(c["read"], self.exp["read"])
        self.assertEqual(c["inconsistent"], self.exp["inconsistent"])
        self.assertEqual(c["analysed"], self.exp["analysed"])
        self.assertEqual(c["imputed_cells"], self.exp["imputed_cells"])

    def test_curve_and_optimum(self):
        g = self.out["groups"][0]
        self.assertEqual([r["buyers"] for r in g["prices"]], self.exp["buyers"])
        for r, rev in zip(g["prices"], self.exp["revenue_index"]):
            self.assertEqual(r["n"], self.exp["n"])
            self.assertAlmostEqual(r["revenue_index"], rev, places=12)
        self.assertEqual(g["optimum"]["price"], self.exp["revenue_optimum"])
        self.assertAlmostEqual(g["prices"][0]["arc_elasticity_to_next"], self.exp["arc_elasticity_10_20"], places=12)
        self.assertAlmostEqual(g["prices"][1]["ci_low"], M.wilson(15, 21, Z95)[0], places=12)

    def test_unit_cost_moves_the_optimum(self):
        g = self.profit["groups"][0]
        for r, want in zip(g["prices"], self.exp["profit_index"]):
            self.assertAlmostEqual(r["profit_index"], want, places=12)
        self.assertEqual(g["optimum"]["price"], self.exp["profit_optimum"])
        self.assertEqual(g["optimum"]["objective"], "profit")

    def test_keep_inconsistent(self):
        out = run_json(FIXTURES / "wide_basic.input.csv", "--inconsistent", "keep", "--bootstrap", 0)
        self.assertEqual(out["counts"]["analysed"], 22)

    def test_segments(self):
        out = run_json(FIXTURES / "wide_basic.input.csv", "--segment", "plan", "--bootstrap", 0)
        labels = [g["label"] for g in out["groups"]]
        self.assertEqual(labels, ["All respondents", "plan = basic", "plan = pro"])
        self.assertEqual(sum(g["respondents"] for g in out["groups"][1:]), 21)


class QualtricsIntentTest(unittest.TestCase):
    def test_top2_from_labels_and_question_text_prices(self):
        exp = expected("qualtrics_intent")
        out = run_json(FIXTURES / "qualtrics_intent.input.csv", "--bootstrap", 0)
        g = out["groups"][0]
        self.assertEqual([r["price"] for r in g["prices"]], [9.99, 14.99, 19.99])
        for r, t in zip(g["prices"], exp["take_top2"]):
            self.assertAlmostEqual(r["take_rate"], t, places=12)
        self.assertEqual(g["optimum"]["price"], exp["optimum_top2"])
        self.assertTrue(any("Qualtrics" in n for n in out["notes"]))

    def test_calibrated_weights(self):
        exp = expected("qualtrics_intent")
        out = run_json(FIXTURES / "qualtrics_intent.input.csv", "--intent-weights", exp["weights"],
                       "--bootstrap", 50)
        g = out["groups"][0]
        for r, t in zip(g["prices"], exp["take_weighted"]):
            self.assertAlmostEqual(r["take_rate"], t, places=12)
            # Bootstrap interval of the raw calibrated take rate, so it brackets the value it sits beside.
            self.assertLessEqual(r["ci_low"], t)
            self.assertGreaterEqual(r["ci_high"], t)
        self.assertEqual(g["optimum"]["price"], exp["optimum_weighted"])
        self.assertFalse(out["binary"])

    def test_top_box(self):
        out = run_json(FIXTURES / "qualtrics_intent.input.csv", "--buy-box", 1, "--bootstrap", 0)
        self.assertAlmostEqual(out["groups"][0]["prices"][0]["take_rate"], 0.4, places=12)


class MonadicAndMaxPriceTest(unittest.TestCase):
    def test_monadic_pava(self):
        exp = expected("monadic_long")
        out = run_json(FIXTURES / "monadic_long.input.csv", "--long", "--price-col", "price", "--answer-col",
                       "would_buy", "--bootstrap", 0)
        g = out["groups"][0]
        for r, raw, mono, rev in zip(g["prices"], exp["raw"], exp["monotone"], exp["revenue_index"]):
            self.assertAlmostEqual(r["take_rate"], raw, places=12)
            self.assertAlmostEqual(r["monotone_take_rate"], mono, places=12)
            self.assertAlmostEqual(r["revenue_index"], rev, places=12)
        self.assertEqual(g["optimum"]["price"], exp["optimum"])
        self.assertEqual(out["counts"]["imputed_cells"], 0)
        self.assertTrue(any("pools" in w for w in g["warnings"]))

    def test_max_price(self):
        exp = expected("max_price")
        out = run_json(FIXTURES / "max_price.input.csv", "--max-price-col", "highest_price", "--prices", "10,20,30",
                       "--bootstrap", 0)
        self.assertEqual(out["counts"]["read"], exp["read"])
        self.assertEqual(out["counts"]["analysed"], exp["analysed"])
        g = out["groups"][0]
        for r, t in zip(g["prices"], exp["take"]):
            self.assertAlmostEqual(r["take_rate"], t, places=12)
        self.assertEqual(g["optimum"]["price"], exp["optimum"])


class EdgeCaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_header_only_is_refused(self):
        path = write(self.tmp.name, "a.csv", "price_10,price_20\n")
        proc = run(path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("n = 0", proc.stderr)

    def test_single_respondent_names_no_optimum(self):
        path = write(self.tmp.name, "a.csv", "price_10,price_20\nyes,no\n")
        out = run_json(path, "--bootstrap", 0)
        self.assertFalse(out["groups"][0]["optimum"]["named"])

    def test_everyone_buys_everywhere_flags_ladder_ceiling(self):
        path = write(self.tmp.name, "a.csv", "price_10,price_20\n" + "yes,yes\n" * 12)
        g = run_json(path, "--bootstrap", 0)["groups"][0]
        self.assertEqual(g["optimum"]["price"], 20)
        self.assertTrue(g["optimum"]["at_highest_price"])
        self.assertTrue(any("same take rate" in w for w in g["warnings"]))

    def test_nobody_buys(self):
        path = write(self.tmp.name, "a.csv", "price_10,price_20\n" + "no,no\n" * 12)
        g = run_json(path, "--bootstrap", 0)["groups"][0]
        self.assertFalse(g["optimum"]["named"])

    def test_tie_is_reported(self):
        # 10 x 0.6 = 6 and 20 x 0.3 = 6: an exact tie in the revenue index.
        rows = "yes,yes\n" * 3 + "yes,no\n" * 3 + "no,no\n" * 4
        path = write(self.tmp.name, "a.csv", "price_10,price_20\n" + rows)
        g = run_json(path, "--bootstrap", 0)["groups"][0]
        self.assertEqual(g["optimum"]["price"], 10)
        self.assertEqual(g["optimum"]["tied_with"], [20])

    def test_numeric_scale_needs_direction(self):
        path = write(self.tmp.name, "a.csv", "price_10,price_20\n5,3\n4,2\n")
        proc = run(path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--intent-scale", proc.stderr)
        out = run_json(path, "--intent-scale", "5,4,3,2,1", "--bootstrap", 0)
        self.assertEqual([r["take_rate"] for r in out["groups"][0]["prices"]], [1.0, 0.0])

    def test_reversed_scale(self):
        path = write(self.tmp.name, "a.csv", "price_10,price_20\n1,3\n2,4\n")
        out = run_json(path, "--intent-scale", "1,2,3,4,5", "--bootstrap", 0)
        self.assertEqual([r["take_rate"] for r in out["groups"][0]["prices"]], [1.0, 0.0])

    def test_unreadable_answers_refused_above_5_percent(self):
        path = write(self.tmp.name, "a.csv", "price_10,price_20\n" + "yes,no\n" * 8 + "maybe,no\n" * 2)
        proc = run(path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("could not be read", proc.stderr)
        out = run_json(path, "--allow-unreadable", "--bootstrap", 0)
        self.assertEqual(out["counts"]["unreadable_answers"], 2)

    def test_duplicate_headers_refused(self):
        path = write(self.tmp.name, "a.csv", "price_10,price_10\nyes,no\n")
        self.assertEqual(run(path).returncode, 2)

    def test_utf16_and_tab(self):
        path = write(self.tmp.name, "a.csv", "$10\t$20\r\n" + "yes\tno\r\n" * 3, encoding="utf-16")
        out = run_json(path, "--bootstrap", 0)
        self.assertEqual(out["groups"][0]["prices"][0]["n"], 3)

    def test_unknown_price_columns_refused_with_column_list(self):
        path = write(self.tmp.name, "a.csv", "q1,q2\nyes,no\n")
        proc = run(path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--price-cols", proc.stderr)
        out = run_json(path, "--price-cols", "q1=10,q2=20", "--bootstrap", 0)
        self.assertEqual(out["prices_tested"], [10.0, 20.0])

    def test_decimal_comma_price_cols(self):
        path = write(self.tmp.name, "a.csv", "a;b\nyes;no\n")
        out = run_json(path, "--price-cols", "a=9,99;b=14,99", "--decimal", "comma", "--bootstrap", 0)
        self.assertEqual(out["prices_tested"], [9.99, 14.99])

    def test_one_segment_value(self):
        path = write(self.tmp.name, "a.csv", "seg,price_10,price_20\n" + "x,yes,no\n" * 10 + "x,yes,yes\n" * 2)
        out = run_json(path, "--segment", "seg", "--bootstrap", 0)
        self.assertTrue(any("Only one value" in n for n in out["notes"]))

    def test_never_overwrites_input(self):
        path = write(self.tmp.name, "a.csv", "price_10,price_20\n" + "yes,no\n" * 10)
        before = path.read_bytes()
        proc = run(path, "--curves-csv", path)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(path.read_bytes(), before)

    def test_bootstrap_is_deterministic(self):
        a = run_json(FIXTURES / "wide_basic.input.csv", "--bootstrap", 100, "--seed", 3)
        b = run_json(FIXTURES / "wide_basic.input.csv", "--bootstrap", 100, "--seed", 3)
        self.assertEqual(a["groups"][0]["bootstrap"], b["groups"][0]["bootstrap"])
        shares = a["groups"][0]["bootstrap"]["optimum_share"]
        self.assertAlmostEqual(sum(shares.values()), 1.0, places=12)

    def test_text_report_runs(self):
        proc = run(FIXTURES / "wide_basic.input.csv", "--bootstrap", 20)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Revenue-maximizing tested price: 20.00", proc.stdout)


def long_csv(tmp, rows, header="price,answer"):
    return write(tmp, "long.csv", header + "\n" + "".join(r + "\n" for r in rows))


class ReviewRegressionTest(unittest.TestCase):
    """Cases from the 2026-11-19 reviews; each failed before its fix."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_negative_intent_contractions_and_curly_apostrophes(self):
        for label, point in [("Definitely will not buy", 1), ("Definitely wouldn't buy", 1),
                             ("Definitely won\u2019t buy", 1), ("Probably will not buy", 2),
                             ("Probably wouldn\u2019t buy", 2), ("Probably won't buy", 2),
                             ("Neither likely nor unlikely", 3), ("Definitely would buy", 5),
                             ("Probably would buy", 4), ("Definitely, but not at this price", None)]:
            self.assertEqual(M.word_point(label), point, label)
        path = write(self.tmp.name, "a.csv", "price_10;price_20\n"
                     + "Definitely wouldn\u2019t buy;Probably wouldn't buy\n" * 10)
        g = run_json(path, "--bootstrap", 0)["groups"][0]
        self.assertEqual([r["take_rate"] for r in g["prices"]], [0.0, 0.0])
        self.assertFalse(g["optimum"]["named"])

    def test_seven_point_labels_need_the_label_order(self):
        labels = ["Extremely likely", "Very likely", "Somewhat likely", "Neither likely nor unlikely",
                  "Somewhat unlikely", "Very unlikely", "Extremely unlikely"]
        rows = "".join(f"{labels[i % 7]},{labels[(i + 2) % 7]}\n" for i in range(14))
        path = write(self.tmp.name, "a.csv", "price_10,price_20\n" + rows)
        proc = run(path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("7-point", proc.stderr)
        out = run_json(path, "--intent-scale", "|".join(labels), "--buy-box", 2, "--design", "full", "--inconsistent",
                       "keep", "--bootstrap", 0)
        # Top-2 box of 7 points: extremely + very likely only (4 of 14 at each price).
        self.assertAlmostEqual(out["groups"][0]["prices"][0]["take_rate"], 4 / 14, places=12)

    def test_two_codes_read_as_yes_no(self):
        path = write(self.tmp.name, "a.csv", "price_10,price_20\n1,2\n1,1\n2,2\n")
        proc = run(path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--intent-scale 1,2", proc.stderr)
        out = run_json(path, "--intent-scale", "1,2", "--bootstrap", 0)
        self.assertEqual([r["take_rate"] for r in out["groups"][0]["prices"]], [2 / 3, 1 / 3])

    def test_ladder_bootstrap_resamples_respondents_not_answer_patterns(self):
        # Adaptive ladder, nothing filled: each asked-price pattern is homogeneous, so resampling within patterns
        # gave a zero-width interval at 20 (Gemini, Opus).
        rows = ["a{},15,yes".format(i) for i in range(10)] + ["a{},20,no".format(i) for i in range(10)]
        rows += ["b{},20,yes".format(i) for i in range(10)] + ["b{},25,no".format(i) for i in range(10)]
        path = long_csv(self.tmp.name, rows, "rid,price,answer")
        out = run_json(path, "--long", "--price-col", "price", "--answer-col", "answer", "--id-col", "rid",
                       "--design", "adaptive", "--no-impute", "--bootstrap", 200)
        boot = out["groups"][0]["bootstrap"]
        self.assertEqual(boot["resampling"], "respondents")
        low, high = boot["take_rate_intervals"]["20"]
        self.assertGreater(high - low, 0.1)

    def test_counts_need_the_sample_type(self):
        base = ["--counts", "10:190,15:164,20:118,25:74,30:36", "--base", 200, "--bootstrap", 0]
        self.assertEqual(run(*base).returncode, 2)
        self.assertEqual(run_json(*base, "--counts-sample", "separate")["counts"]["read"], 1000)
        same = run_json(*base, "--counts-sample", "same")
        self.assertEqual(same["counts"]["read"], 200)
        self.assertEqual(same["groups"][0]["respondents"], 200)
        rising = run("--counts", "10:50,20:60", "--base", 100, "--counts-sample", "same")
        self.assertEqual(rising.returncode, 2)
        self.assertIn("buyers rise", rising.stderr)

    def test_counts_thousands_separators_need_semicolons(self):
        out = run_json("--counts", "999:120;1,299:85;1,499:40", "--base", "1,000", "--counts-sample", "same",
                       "--bootstrap", 0)
        self.assertEqual(out["prices_tested"], [999.0, 1299.0, 1499.0])
        self.assertEqual(out["counts"]["read"], 1000)
        proc = run("--counts", "999:120,1,299:85", "--base", 200, "--counts-sample", "same")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("';'", proc.stderr)

    def test_design_is_not_inferred_from_a_few_blanks(self):
        path = write(self.tmp.name, "a.csv", "price_10,price_20\n,yes\nno,\nyes,no\n")
        proc = run(path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--design", proc.stderr)
        out = run_json(path, "--design", "full", "--bootstrap", 0)
        self.assertEqual(out["counts"]["imputed_cells"], 0)
        self.assertEqual([r["n"] for r in out["groups"][0]["prices"]], [2, 2])
        self.assertEqual(run(path, "--design", "monadic").returncode, 2)

    def test_filled_cells_reported_separately(self):
        out = run_json(FIXTURES / "wide_basic.input.csv", "--bootstrap", 0)
        rows = out["groups"][0]["prices"]
        self.assertEqual([r["n"] for r in rows], [21] * 4)
        self.assertEqual([r["n_observed"] for r in rows], [20, 21, 21, 20])
        self.assertTrue(any("filled" in w for w in out["warnings"]))

    def test_calibrated_intervals_sit_on_the_raw_rate(self):
        rows = ["10,Definitely would not buy"] * 10 + ["20,Definitely would buy"] * 10
        path = long_csv(self.tmp.name, rows)
        out = run_json(path, "--long", "--price-col", "price", "--answer-col", "answer", "--intent-weights",
                       "1,0.5,0.2,0.1,0", "--bootstrap", 50)
        r10, r20 = out["groups"][0]["prices"]
        self.assertEqual((r10["take_rate"], r10["ci_low"], r10["ci_high"]), (0.0, 0.0, 0.0))
        self.assertEqual((r20["ci_low"], r20["ci_high"]), (1.0, 1.0))
        self.assertEqual((r10["monotone_ci_low"], r10["monotone_ci_high"]), (0.5, 0.5))
        csv_path = pathlib.Path(self.tmp.name) / "curves.csv"
        run_json(path, "--long", "--price-col", "price", "--answer-col", "answer", "--intent-weights",
                 "1,0.5,0.2,0.1,0", "--bootstrap", 20, "--curves-csv", csv_path)
        self.assertIn("0.0,0.0", csv_path.read_text())

    def test_interval_label_follows_confidence(self):
        proc = run(FIXTURES / "wide_basic.input.csv", "--bootstrap", 0, "--confidence", 0.9)
        self.assertIn("90% CI", proc.stdout)
        self.assertNotIn("95% CI", proc.stdout)
        self.assertEqual(run_json(FIXTURES / "wide_basic.input.csv", "--bootstrap", 0, "--confidence", 0.9)
                         ["confidence"], 0.9)

    def test_respondent_ids_are_validated(self):
        wide = write(self.tmp.name, "w.csv", "rid,price_10,price_20\nr1,yes,no\nr1,no,no\n")
        self.assertIn("more than one row", run(wide, "--id-col", "rid").stderr)
        self.assertIn("not found", run(wide, "--id-col", "ridd").stderr)
        blank = long_csv(self.tmp.name, [",10,yes", ",20,no"], "rid,price,answer")
        self.assertIn("blank", run(blank, "--long", "--price-col", "price", "--answer-col", "answer",
                                   "--id-col", "rid").stderr)
        seg = long_csv(self.tmp.name, ["r1,a,10,yes", "r1,b,20,no"], "rid,seg,price,answer")
        self.assertIn("one segment", run(seg, "--long", "--price-col", "price", "--answer-col", "answer",
                                         "--id-col", "rid", "--segment", "seg").stderr)

    def test_tie_is_not_blamed_on_pooling_and_splits_bootstrap_votes(self):
        g = run_json("--counts", "10:10,20:5", "--base", 10, "--counts-sample", "separate",
                     "--bootstrap", 0)["groups"][0]
        self.assertTrue(g["optimum"]["tied_with"])
        self.assertFalse(any("pools" in w for w in g["warnings"]))
        # Every replicate ties exactly (value 1 at 10, 0.5 at 20 for everyone): the vote splits evenly.
        rows = ["10,Definitely would buy"] * 10 + ["20,Probably would buy"] * 10
        path = long_csv(self.tmp.name, rows)
        boot = run_json(path, "--long", "--price-col", "price", "--answer-col", "answer", "--intent-weights",
                        "1,0.5,0.2,0.1,0", "--bootstrap", 20)["groups"][0]["bootstrap"]
        self.assertEqual(boot["optimum_share"], {"10": 0.5, "20": 0.5})

    def test_bad_numbers_and_bytes_exit_2(self):
        self.assertEqual(run("--counts", "10:5,20:3", "--base", 10, "--counts-sample", "same", "--unit-cost",
                             "nan").returncode, 2)
        path = pathlib.Path(self.tmp.name) / "bom.csv"
        path.write_bytes(b"\xef\xbb\xbfprice_10,price_20\n\xff,1\n")
        proc = run(path)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(run(FIXTURES / "wide_basic.input.csv", "--skip-rows", -1).returncode, 2)
        self.assertEqual(run(FIXTURES / "wide_basic.input.csv", "--long", "--max-price-col", "x").returncode, 2)

    def test_negative_highest_price_is_a_missing_code(self):
        path = write(self.tmp.name, "a.csv", "hp\n" + "20\n" * 10 + "-99\n" * 10)
        out = run_json(path, "--max-price-col", "hp", "--prices", "10,20", "--bootstrap", 0, "--allow-unreadable")
        self.assertEqual(out["counts"]["analysed"], 10)
        self.assertEqual(out["counts"]["read"], 20)
        self.assertEqual(out["groups"][0]["prices"][0]["take_rate"], 1.0)

    def test_number_formats(self):
        self.assertIsNone(M.parse_number("9.99", "comma"))
        self.assertEqual(M.parse_number("1.299,50", "comma"), 1299.5)
        self.assertEqual(M.parse_number("US$1,299", "dot"), 1299.0)
        self.assertEqual(M.parse_number("1\u00a0299 \u20ac", "dot"), 1299.0)
        self.assertEqual(M.fmt_price(0.001), "0.001")
        path = write(self.tmp.name, "a.csv", "$999.50,\"$1,299.50\"\nyes,no\n")
        self.assertEqual(run_json(path, "--bootstrap", 0)["prices_tested"], [999.5, 1299.5])

    def test_question_numbers_are_not_prices(self):
        path = write(self.tmp.name, "a.csv", "P1,P2,P3\nyes,no,no\n")
        proc = run(path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("could not tell which columns are prices", proc.stderr)

    def test_raw_curve_optimum_is_named_when_pooling_moves_it(self):
        rows = ["5,yes"] * 4 + ["5,no"] * 16 + ["10,yes"] * 16 + ["10,no"] * 4 + ["15,yes"] * 9 + ["15,no"] * 11
        path = long_csv(self.tmp.name, rows)
        g = run_json(path, "--long", "--price-col", "price", "--answer-col", "answer", "--bootstrap", 0)["groups"][0]
        self.assertEqual(g["optimum"]["price"], 15)
        self.assertTrue(any("raw (unpooled)" in w and "10.00" in w for w in g["warnings"]))

    def test_weights_flag_rising_value_as_inconsistent(self):
        path = write(self.tmp.name, "a.csv", "rid,price_10,price_20\n"
                     + "r,Probably would buy,Definitely would buy\n" + "s,Definitely would buy,Probably would buy\n" * 11)
        out = run_json(path, "--intent-weights", "0.8,0.4,0.15,0.05,0", "--bootstrap", 0)
        self.assertEqual(out["counts"]["inconsistent"], 1)

    def test_optimum_interval_names_tested_prices(self):
        self.assertEqual(M.nearest_rank([15.0] * 975 + [20.0] * 25, 97.5), 15.0)
        boot = run_json(FIXTURES / "wide_basic.input.csv", "--bootstrap", 100)["groups"][0]["bootstrap"]
        self.assertTrue(set(boot["optimum_interval"]) <= {10.0, 20.0, 30.0, 40.0})

    def test_quoted_line_break_and_tab_name(self):
        text = ('Q1;Q2\n"Would you buy it\nat $10?";"Would you buy it at $20?"\n'
                '{"ImportId":"QID1"};{"ImportId":"QID2"}\n' + "yes;no\n" * 3)
        out = run_json(write(self.tmp.name, "q.csv", text), "--bootstrap", 0)
        self.assertEqual(out["prices_tested"], [10.0, 20.0])
        tab = write(self.tmp.name, "t.csv", "$10\t$20\n" + "yes\tno\n" * 3)
        self.assertIn("Delimiter detected: tab.", run_json(tab, "--bootstrap", 0)["notes"])


if __name__ == "__main__":
    unittest.main()
