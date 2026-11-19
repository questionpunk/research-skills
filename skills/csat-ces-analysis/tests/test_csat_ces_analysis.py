"""Tests for scripts/csat_ces_analysis.py. Run from the skill folder: python3 -m unittest discover -s tests

Expected values come from fixtures/*.expected.json, worked out by hand (fixtures/README.md), taken from a
published example (Newcombe 1998a and 1998b, Fisher 1935), or re-derived here by a second method.
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
SCRIPT = SKILL / "scripts" / "csat_ces_analysis.py"
PCT = 0.01  # published and hand values are given to two decimals of a percent


def load_module():
    spec = importlib.util.spec_from_file_location("csat_ces_analysis", SCRIPT)
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


def by_label(groups):
    return {g["label"]: g for g in groups}


class BasicFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exp = expected("basic")
        cls.out = run_json(FIXTURES / "basic.input.csv", "--scale", "1-5", "--segment-col", "channel", "--period-col", "month",
                           "--compare", "email", "chat", "--comment-col", "comment")

    def assert_close(self, got, want, delta=PCT):
        for g, w in zip(got, want):
            self.assertAlmostEqual(g, w, delta=delta)

    def test_detects_column_scale_and_exclusions(self):
        self.assertEqual(self.out["input"]["score_col"], "csat")
        self.assertEqual((self.out["scale"]["min"], self.out["scale"]["max"]), (1, 5))
        self.assertEqual(self.out["input"]["excluded"], self.exp["excluded"])
        self.assertEqual(self.out["convention"]["positive_points"], [4, 5])

    def test_overall_share_interval_and_mean(self):
        got, want = self.out["overall"], self.exp["overall"]
        for key in ("n", "positive", "negative", "neutral", "distribution"):
            self.assertEqual(got[key], want[key], key)
        self.assertAlmostEqual(got["pct_positive"], want["pct_positive"], delta=1e-9)
        self.assert_close(got["positive_ci"], want["positive_ci"], 1e-3)
        self.assert_close(got["negative_ci"], want["negative_ci"], 1e-3)
        self.assertAlmostEqual(got["mean"], want["mean"], delta=1e-12)
        self.assertAlmostEqual(got["sd"], want["sd"], delta=1e-6)
        self.assert_close(got["mean_ci"], want["mean_ci"], 1e-5)

    def test_segments_and_periods(self):
        for key in ("segments", "periods"):
            got = by_label(self.out[key])
            for name, want in self.exp[key].items():
                self.assertEqual(got[name]["n"], want["n"])
                self.assertEqual(got[name]["positive"], want["positive"])
                self.assert_close(got[name]["positive_ci"], want["positive_ci"], 1e-3)

    def test_segment_comparison(self):
        got = next(c for c in self.out["comparisons"] if c["kind"] == "segment")
        want = self.exp["email_vs_chat"]
        self.assertEqual((got["a"], got["b"]), ("email", "chat"))
        self.assertAlmostEqual(got["difference_pct"], want["difference_pct"], delta=1e-9)
        self.assert_close(got["difference_ci"], want["difference_ci"], 1e-3)
        self.assertAlmostEqual(got["z"], want["z"], delta=1e-6)
        self.assertAlmostEqual(got["p_value"], want["p_value"], delta=1e-6)
        self.assertEqual(got["test"], want["test"])
        self.assertEqual(got["verdict"], want["verdict"])

    def test_trend_is_later_minus_earlier(self):
        got = next(c for c in self.out["comparisons"] if c["kind"] == "trend")
        want = self.exp["oct_vs_sep"]
        self.assertEqual((got["a"], got["b"]), ("2026-10", "2026-09"))
        self.assert_close(got["difference_ci"], want["difference_ci"], 1e-3)
        self.assertAlmostEqual(got["p_value"], want["p_value"], delta=1e-6)

    def test_warns_about_multiplicity_and_small_base(self):
        text = " ".join(self.out["warnings"])
        # One segment test and one trend test: two families of one test each, so nothing to adjust.
        self.assertNotIn("without a multiple-comparison adjustment", text)
        self.assertIn("Small base", text)

    def test_holm_adjustment(self):
        out = run_json(FIXTURES / "basic.input.csv", "--scale", "1-5", "--segment-col", "channel", "--pairwise",
                       "--period-col", "month", "--period-order", "2026-09,2026-10", "--adjust", "holm")
        # Segment and period comparisons are separate families, so a single test in a family is unadjusted.
        for c in out["comparisons"]:
            self.assertEqual(c["family_size"], 1)
            self.assertAlmostEqual(c["p_adjusted"], c["p_value"], delta=1e-12)
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "three.csv"
            rows = ["csat,seg"] + [f"{v},{s}" for s, vals in (("a", "5554443321"), ("b", "5444433221"),
                                                              ("c", "3322211111")) for v in vals]
            path.write_text("\n".join(rows) + "\n")
            out = run_json(path, "--scale", "1-5", "--segment-col", "seg", "--pairwise", "--adjust", "holm")
            ps = sorted(c["p_value"] for c in out["comparisons"])
            adjusted = sorted(c["p_adjusted"] for c in out["comparisons"])
            self.assertEqual({c["family_size"] for c in out["comparisons"]}, {3})
            self.assertAlmostEqual(adjusted[0], 3 * ps[0], delta=1e-12)
            self.assertAlmostEqual(adjusted[1], max(3 * ps[0], 2 * ps[1]), delta=1e-12)
            raw = run_json(path, "--scale", "1-5", "--segment-col", "seg", "--pairwise")
            self.assertIn("3 segment", " ".join(raw["warnings"]))

    def test_comment_counts(self):
        self.assertEqual({k: v for k, v in self.out["comments"].items() if k != "written_to"}, self.exp["comments"])

    def test_comments_out_and_never_overwrites_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "comments.csv"
            run_json(FIXTURES / "basic.input.csv", "--scale", "1-5", "--comment-col", "comment", "--comments-out", path)
            with open(path, newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 16)
            self.assertEqual(rows[0]["group"], "dissatisfied")
            nested = pathlib.Path(tmp) / "new" / "folder" / "c.json"
            proc = run(FIXTURES / "basic.input.csv", "--scale", "1-5", "--comment-col", "comment", "--comments-out", nested)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Written to", proc.stdout)
            self.assertEqual(len(json.loads(nested.read_text())), 16)
            copy = pathlib.Path(tmp) / "in.csv"
            copy.write_bytes((FIXTURES / "basic.input.csv").read_bytes())
            before = copy.read_bytes()
            proc = run(copy, "--scale", "1-5", "--comment-col", "comment", "--comments-out", copy)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(copy.read_bytes(), before)

    def test_readable_output(self):
        proc = run(FIXTURES / "basic.input.csv", "--scale", "1-5", "--segment-col", "channel", "--compare", "email", "chat")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("satisfied 75.0% (59.8% to 85.8%)", proc.stdout)
        self.assertIn("p = 0.1441: not significant (small base", proc.stdout)

    def test_deterministic(self):
        args = (FIXTURES / "basic.input.csv", "--scale", "1-5", "--segment-col", "channel", "--pairwise", "--json")
        self.assertEqual(run(*args).stdout, run(*args).stdout)


class PublishedExamplesTest(unittest.TestCase):
    def test_wilson_matches_newcombe_1998a(self):
        for case in expected("wilson_newcombe_1998a")["cases"]:
            out = run_json("--counts", f"{case['n'] - case['x']},{case['x']}", "--scale", "1-2")
            low, high = out["overall"]["positive_ci"]
            self.assertAlmostEqual(low, case["low"], delta=0.005 + 1e-9, msg=case)
            self.assertAlmostEqual(high, case["high"], delta=0.005 + 1e-9, msg=case)
            if case["x"] == 0:
                self.assertEqual(low, 0.0)

    def test_newcombe_1998b_difference_intervals(self):
        exp = expected("newcombe_good_bad")
        out = run_json(FIXTURES / "newcombe_good_bad.input.csv", "--segment-col", "agent", "--compare", "A", "B")
        self.assertEqual(out["input"]["labels"]["source"], "good-bad")
        self.assertEqual((out["scale"]["min"], out["scale"]["max"]), (1, 2))
        got = out["comparisons"][0]
        self.assertAlmostEqual(got["difference_pct"], exp["A_vs_B"]["difference_pct"], delta=1e-9)
        for g, w in zip(got["difference_ci"], exp["A_vs_B"]["difference_ci"]):
            self.assertAlmostEqual(g, w, delta=0.005 + 1e-9)
        self.assertIsNone(out["overall"]["mean"])  # no mean on a two-point scale

    def test_small_expected_counts_switch_to_fisher(self):
        exp = expected("newcombe_good_bad")["C_vs_D"]
        out = run_json(FIXTURES / "newcombe_good_bad.input.csv", "--segment-col", "agent", "--compare", "C", "D")
        got = out["comparisons"][0]
        self.assertEqual(got["test"], "fisher exact")
        self.assertAlmostEqual(got["p_value"], exp["fisher_p"], delta=1e-6)
        for g, w in zip(got["difference_ci"], exp["difference_ci"]):
            self.assertAlmostEqual(g, w, delta=0.005 + 1e-9)

    def test_fisher_tea_tasting(self):
        self.assertAlmostEqual(M.fisher_exact(3, 4, 1, 4), 34 / 70, delta=1e-12)

    def test_ces7_labels_and_comparison(self):
        exp = expected("ces7")
        out = run_json(FIXTURES / "ces7.input.csv", "--metric", "ces", "--segment-col", "resolution", "--pairwise")
        self.assertEqual(out["input"]["labels"]["source"], exp["labels"])
        self.assertEqual(out["convention"]["positive_points"], [5, 6, 7])
        o = out["overall"]
        self.assertEqual((o["n"], o["positive"], o["negative"]), (30, 17, 8))
        self.assertAlmostEqual(o["mean"], 4.7, delta=1e-12)
        seg = by_label(out["segments"])
        for name in ("first_contact", "repeat_contact"):
            self.assertEqual(seg[name]["positive"], exp[name]["positive"])
            self.assertAlmostEqual(seg[name]["mean"], exp[name]["mean"], delta=1e-6)
            for g, w in zip(seg[name]["positive_ci"], exp[name]["positive_ci"]):
                self.assertAlmostEqual(g, w, delta=1e-3)
        c = out["comparisons"][0]
        self.assertAlmostEqual(c["z"], exp["comparison"]["z"], delta=1e-6)
        self.assertAlmostEqual(c["p_value"], exp["comparison"]["p_value"], delta=1e-6)
        self.assertEqual(c["verdict"], "significant")

    def test_ces5_lower_is_better(self):
        out = run_json("--metric", "ces5", "--counts", "20,30,25,15,10")
        self.assertFalse(out["scale"]["higher_is_better"])
        self.assertEqual(out["convention"]["positive_points"], [1, 2])
        self.assertAlmostEqual(out["overall"]["pct_positive"], 50.0, delta=1e-9)
        self.assertAlmostEqual(out["overall"]["pct_negative"], 25.0, delta=1e-9)
        self.assertAlmostEqual(out["overall"]["mean"], 2.65, delta=1e-12)


class IndependentCheckTest(unittest.TestCase):
    """Re-derive the headline Wilson interval by bisection on the score statistic, not the closed form."""

    def test_wilson_by_bisection(self):
        z = M.z_for(0.95)
        for x, n in ((30, 40), (1, 29), (17, 20), (7, 9), (199, 200)):
            p_hat = x / n

            def excess(p):
                return abs(p_hat - p) - z * math.sqrt(p * (1 - p) / n)

            def root(a, b):
                for _ in range(200):
                    m = (a + b) / 2
                    if (excess(a) > 0) == (excess(m) > 0):
                        a = m
                    else:
                        b = m
                return (a + b) / 2

            low, high = M.wilson(x, n, z)
            self.assertAlmostEqual(low, root(1e-15, p_hat), delta=1e-10)
            self.assertAlmostEqual(high, root(p_hat, 1 - 1e-15), delta=1e-10)

    def test_target_test_agrees_with_wilson(self):
        # The score test rejects a target exactly when it lies outside the Wilson interval.
        low = run_json("--counts", "4,6,10,40,40")["overall"]["positive_ci"][0]  # 71.117 for 80/100
        inside = run_json("--counts", "4,6,10,40,40", "--target", f"{low + 0.01}")
        self.assertFalse(inside["target"]["significant"])
        outside = run_json("--counts", "4,6,10,40,40", "--target", f"{low - 0.01}")
        self.assertTrue(outside["target"]["significant"])


class InputRobustnessTest(unittest.TestCase):
    def write(self, tmp, name, text, encoding="utf-8", newline="\n"):
        path = pathlib.Path(tmp) / name
        path.write_bytes(text.replace("\n", newline).encode(encoding))
        return path

    def base_text(self):
        return (FIXTURES / "basic.input.csv").read_text()

    def overall(self, path, *extra):
        return run_json(path, "--score-col", "csat", "--scale", "1-5", *extra)["overall"]

    def test_bom_crlf_utf16_semicolon_tab(self):
        reference = self.overall(FIXTURES / "basic.input.csv")
        text = self.base_text()
        with tempfile.TemporaryDirectory() as tmp:
            variants = [
                self.write(tmp, "bom.csv", "﻿" + text, "utf-8", "\r\n"),
                self.write(tmp, "u16.csv", text, "utf-16"),
                self.write(tmp, "semi.csv", text.replace(",", ";")),
                self.write(tmp, "tab.csv", text.replace(",", "\t")),
            ]
            for path in variants:
                got = self.overall(path)
                self.assertEqual(got["n"], reference["n"], path.name)
                self.assertEqual(got["distribution"], reference["distribution"], path.name)
            forced = run_json(variants[2], "--score-col", "csat", "--scale", "1-5", "--delimiter", "semicolon")["overall"]
            self.assertEqual(forced["n"], reference["n"])

    def test_qualtrics_three_row_header(self):
        lines = self.base_text().splitlines()
        header = lines[0].split(",")
        qtext = ",".join(f"Question text for {h}" for h in header)
        import_ids = ",".join('"{""ImportId"":""QID%d""}"' % i for i in range(len(header)))
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "q.csv", "\n".join([lines[0], qtext, import_ids] + lines[1:]) + "\n")
            out = run_json(path, "--score-col", "csat", "--scale", "1-5")
            self.assertEqual(out["overall"]["n"], 40)
            self.assertTrue(any("Qualtrics" in n for n in out["notes"]))
            path2 = self.write(tmp, "q2.csv", "\n".join([lines[0], qtext] + lines[1:]) + "\n")
            self.assertEqual(run_json(path2, "--score-col", "csat", "--scale", "1-5", "--skip-rows", "1")["overall"]["n"], 40)

    def test_duplicate_headers_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "d.csv", "csat,csat\n5,4\n")
            proc = run(path)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("more than one column named", proc.stderr)

    def test_refuses_to_drop_more_than_five_percent(self):
        rows = "csat\n" + "5\n" * 18 + "great\nterrible\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "bad.csv", rows)
            proc = run(path, "--scale", "1-5")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("more than 5%", proc.stderr)
            out = run_json(path, "--allow-unreadable", "--scale", "1-5")
            self.assertEqual(out["overall"]["n"], 18)
            self.assertEqual(out["input"]["excluded"]["non_numeric"], 2)

    def test_out_of_range_counts_as_unreadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "r.csv", "csat\n" + "5\n4\n" * 10 + "9\n")
            proc = run(path, "--scale", "1-5")
            self.assertEqual(proc.returncode, 0, proc.stderr)  # 1 of 21 is under 5%
            out = run_json(path, "--scale", "1-5")
            self.assertEqual(out["input"]["excluded"], {"out_of_range": 1})


class EdgeCaseTest(unittest.TestCase):
    def test_empty_file_and_no_valid_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = pathlib.Path(tmp) / "e.csv"
            empty.write_text("")
            self.assertEqual(run(empty).returncode, 2)
            blanks = pathlib.Path(tmp) / "b.csv"
            blanks.write_text("csat,x\n,1\n,2\n")
            proc = run(blanks, "--scale", "1-5")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("no valid answers", proc.stderr)

    def test_single_answer(self):
        out = run_json("--counts", "0,0,0,0,1")
        o = out["overall"]
        self.assertEqual(o["n"], 1)
        self.assertEqual(o["positive_ci"][1], 100.0)
        self.assertIn("fewer than 5", " ".join(o["notes"]))
        self.assertNotIn("mean_ci", o)

    def test_all_same_answer(self):
        out = run_json("--counts", "0,0,0,0,30")
        self.assertEqual(out["overall"]["positive_ci"][1], 100.0)
        self.assertEqual(out["overall"]["mean_ci"], [5.0, 5.0])
        self.assertTrue(any("Every answer is 5" in w for w in out["warnings"]))

    def test_tiny_base_gives_no_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "t.csv"
            path.write_text("csat,seg\n5,a\n4,a\n1,b\n2,b\n5,b\n4,b\n5,b\n")
            out = run_json(path, "--scale", "1-5", "--segment-col", "seg", "--compare", "a", "b")
            self.assertFalse(out["comparisons"][0]["tested"])
            self.assertIn("no verdict", out["comparisons"][0]["note"])

    def test_one_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "o.csv"
            path.write_text("csat,seg\n5,a\n4,a\n3,a\n")
            out = run_json(path, "--scale", "1-5", "--segment-col", "seg", "--pairwise")
            self.assertNotIn("comparisons", out)
            self.assertTrue(any("Only one segment" in w for w in out["warnings"]))

    def test_boundary_points_and_override(self):
        out = run_json("--counts", "1,1,1,1,1", "--positive", "5", "--negative", "1")
        self.assertEqual(out["overall"]["positive"], 1)
        self.assertEqual(out["overall"]["negative"], 1)
        proc = run("--counts", "1,1,1,1,1", "--positive", "3-5", "--negative", "1-3")
        self.assertEqual(proc.returncode, 2)

    def test_counts_length_must_match_scale(self):
        proc = run("--counts", "1,2,3", "--scale", "1-5")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("one count per point", proc.stderr)

    def test_unknown_period_order_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "p.csv"
            path.write_text("csat,when\n5,spring\n4,autumn\n")
            proc = run(path, "--scale", "1-5", "--period-col", "when")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("--period-order", proc.stderr)
            out = run_json(path, "--scale", "1-5", "--period-col", "when", "--period-order", "spring,autumn")
            self.assertEqual([p["label"] for p in out["periods"]], ["spring", "autumn"])

    def test_repeat_ids_warned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "i.csv"
            path.write_text("csat,cust\n5,a\n4,a\n3,b\n")
            out = run_json(path, "--scale", "1-5", "--id-col", "cust")
            self.assertEqual(out["input"]["repeat_answers"], 1)


class ReviewRegressionTest(unittest.TestCase):
    """Cases from the 2026-11-19 review. Each failed on the version before the fix."""

    def csv(self, tmp, text, name="r.csv"):
        path = pathlib.Path(tmp) / name
        path.write_text(text)
        return path

    def test_numeric_scale_is_never_guessed_from_the_answers(self):
        # Fifty 4s and fifty 5s from a 7-point question used to read as 1-5 and 100% satisfied.
        with tempfile.TemporaryDirectory() as tmp:
            path = self.csv(tmp, "csat\n" + "4\n5\n" * 50)
            proc = run(path)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("--scale", proc.stderr)
            self.assertEqual(run_json(path, "--scale", "1-7")["overall"]["pct_positive"], 0.0)
            # A stray 0 among 1-5 answers, and 0/1 answers, used to become a 0-10 scale with 0% satisfied.
            self.assertEqual(run(self.csv(tmp, "csat\n0\n" + "5\n" * 40, "z.csv")).returncode, 2)
            self.assertEqual(run(self.csv(tmp, "csat\n" + "0\n1\n" * 10, "b.csv")).returncode, 2)

    def test_labels_map_sets_the_scale(self):
        # --labels "Thumbs down=1,Thumbs up=2" used to infer 1-5 and report 0% satisfied.
        with tempfile.TemporaryDirectory() as tmp:
            path = self.csv(tmp, "csat\n" + "Thumbs up\n" * 30 + "Thumbs down\n" * 10)
            out = run_json(path, "--labels", "Thumbs down=1,Thumbs up=2")
            self.assertEqual((out["scale"]["min"], out["scale"]["max"]), (1, 2))
            self.assertAlmostEqual(out["overall"]["pct_positive"], 75.0, delta=1e-9)
            self.assertEqual(run(path, "--labels", "Thumbs down=1,Thumbs up=2", "--scale", "1-1").returncode, 2)

    def test_seven_point_satisfaction_labels(self):
        labels = ["Very dissatisfied", "Dissatisfied", "Somewhat dissatisfied", "Neither satisfied nor dissatisfied",
                  "Somewhat satisfied", "Satisfied", "Very satisfied"]
        with tempfile.TemporaryDirectory() as tmp:
            # All seven labels used to collapse into the 5-point map (somewhat satisfied = satisfied).
            out = run_json(self.csv(tmp, "csat\n" + "\n".join(labels) + "\n"))
            self.assertEqual(out["input"]["labels"]["source"], "satisfied7")
            self.assertEqual(out["convention"]["positive_points"], [6, 7])
            # Five labels that fit a 5-point and a 7-point scale: the script asks instead of picking one.
            five = self.csv(tmp, "csat\nVery dissatisfied\nDissatisfied\nNeutral\nSatisfied\nVery satisfied\n", "5.csv")
            proc = run(five)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("more than one answer scale", proc.stderr)
            self.assertEqual(run_json(five, "--scale", "1-5")["overall"]["pct_positive"], 40.0)
            somewhat = self.csv(tmp, "csat\nSomewhat satisfied\nSomewhat satisfied\nVery dissatisfied\n", "s.csv")
            got = run_json(somewhat, "--scale", "1-5")
            self.assertEqual(got["input"]["labels"]["source"], "satisfied5-somewhat")
            self.assertEqual(got["overall"]["positive"], 2)

    def test_ces_refuses_effort_labels_and_follows_seven_point_coding(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Two "Very high effort" answers used to read as 100% easy under --metric ces.
            proc = run(self.csv(tmp, "effort\nVery high effort\nVery high effort\n"), "--metric", "ces")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("--metric ces5", proc.stderr)
            # On a 0-6 coding, the fifth category (4) is easy; it used to fall outside a top-2 box.
            out = run_json(self.csv(tmp, "ces\n" + "4\n" * 20, "z.csv"), "--metric", "ces", "--scale", "0-6")
            self.assertEqual(out["convention"]["positive_points"], [4, 5, 6])
            self.assertEqual(out["overall"]["pct_positive"], 100.0)

    def test_point_ranges_are_validated(self):
        self.assertEqual(run("--counts", "1,1,1,1,1", "--positive", "5-4").returncode, 2)
        self.assertEqual(run("--counts", "1,1,1,1,1", "--positive", "4 to 5").returncode, 2)
        out = run_json("--counts", "1,1,1,1,1", "--scale=-2-2", "--negative=-2--1")
        self.assertEqual(out["convention"]["negative_points"], [-2, -1])
        self.assertEqual(out["overall"]["negative"], 2)

    def test_residual_is_neutral_only_at_the_midpoint(self):
        out = run_json("--counts", "0,0,20,0", "--scale", "1-4")
        self.assertEqual(out["convention"]["middle_label"], "middle (neither box)")
        self.assertEqual(run_json("--counts", "1,1,1,1,1")["convention"]["middle_label"], "neutral")

    def test_target_flags(self):
        self.assertEqual(run("--counts", "4,6,10,40,40", "--target", "80", "--tail", "one").returncode, 2)
        share = run_json("--counts", "4,6,10,40,40", "--target", "0.85")
        self.assertEqual(share["target"]["target_pct"], 85.0)
        tiny = run_json("--counts", "0,0,1,1,1", "--target", "99")["target"]
        self.assertFalse(tiny["tested"])
        self.assertEqual(run("--counts", "1,1,1,1,1", "--target-mean", "nan").returncode, 2)
        far = run_json("--counts", "5,95", "--target", "50")["target"]
        self.assertGreater(far["p_value"], 0.0)  # 2.26e-19, was rounded to 0
        self.assertAlmostEqual(far["p_value"] / 2.2571768119e-19, 1.0, delta=1e-6)

    def test_no_underpowered_verdict(self):
        out = run_json(FIXTURES / "basic.input.csv", "--scale", "1-5", "--segment-col", "channel",
                       "--compare", "email", "chat")
        c = out["comparisons"][0]
        self.assertEqual(c["verdict"], "not significant")
        self.assertTrue(c["small_base"])

    def test_score_column_names_match_whole_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(self.csv(tmp, "id,services,csat\n1,a,5\n"), "--scale", "1-5")
            self.assertEqual(out["input"]["score_col"], "csat")
            proc = run(self.csv(tmp, "id,release,q1\n1,a,5\n", "r2.csv"), "--scale", "1-5")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("could not find the rating column", proc.stderr)

    def test_truncated_utf16_and_excel_sep_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = pathlib.Path(tmp) / "u.csv"
            bad.write_bytes(b"\xff\xfec\x00s\x00a")
            proc = run(bad, "--scale", "1-5")
            self.assertEqual(proc.returncode, 2)
            self.assertNotIn("Traceback", proc.stderr)
            out = run_json(self.csv(tmp, "sep=;\ncsat;x\n5;1\n4;1\n", "s.csv"), "--scale", "1-5")
            self.assertEqual(out["input"]["score_col"], "csat")
            self.assertEqual(out["overall"]["n"], 2)
            tab = run(self.csv(tmp, "csat\tx\n5\t1\n", "t.csv"), "--scale", "1-5")
            self.assertIn("Delimiter detected: tab.", tab.stdout)

    def test_blank_period_and_period_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(self.csv(tmp, "csat,month\n5,2026-09\n4,\n5,2026-10\n"), "--scale", "1-5",
                           "--period-col", "month")
            self.assertEqual(out["overall"]["n"], 3)
            self.assertEqual([p["label"] for p in out["periods"]], ["2026-09", "2026-10"])
            one = run_json(self.csv(tmp, "csat,month\n5,October\n4,October\n", "o.csv"), "--scale", "1-5",
                           "--period-col", "month")
            self.assertEqual([p["label"] for p in one["periods"]], ["October"])
            proc = run(self.csv(tmp, "csat,m\n5,a\n4,b\n", "d.csv"), "--scale", "1-5", "--period-col", "m",
                       "--period-order", "a,b,a")
            self.assertEqual(proc.returncode, 2)

    def test_segment_mix_by_period(self):
        out = run_json(FIXTURES / "basic.input.csv", "--scale", "1-5", "--segment-col", "channel",
                       "--period-col", "month")
        rows = {(r["period"], r["segment"]): r for r in out["segment_by_period"]}
        self.assertEqual(rows[("2026-09", "email")]["n"], 10)
        self.assertAlmostEqual(rows[("2026-09", "email")]["pct_of_period"], 50.0, delta=1e-9)
        self.assertAlmostEqual(rows[("2026-10", "chat")]["pct_positive"], 90.0, delta=1e-9)

    def test_comments_count_answers_and_distinct_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.csv(tmp, "csat,cust,c\n1,a,slow\n2,a,slow again\n5,b,great\n")
            out_path = pathlib.Path(tmp) / "c.csv"
            out = run_json(path, "--scale", "1-5", "--id-col", "cust", "--comment-col", "c", "--comments-out", out_path)
            self.assertEqual(out["comments"]["dissatisfied"], {"answers": 2, "with_comment": 2, "distinct_ids": 1})
            with open(out_path, newline="") as handle:
                self.assertEqual(next(csv.DictReader(handle))["id"], "a")

    def test_zendesk_offered_rows_counted_apart(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(self.csv(tmp, "satisfaction\nGood\nGood\nBad\nOffered\nUnoffered\n"))
            self.assertEqual(out["input"]["excluded"], {"offered_not_rated": 1, "not_offered": 1})
            self.assertAlmostEqual(out["input"]["response_rate_offered"], 0.75, delta=1e-12)

    def test_stray_text_does_not_drop_the_label_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(self.csv(tmp, "csat\n" + "Good\nBad\n" * 20 + "test\n"))
            self.assertEqual(out["input"]["labels"]["source"], "good-bad")
            self.assertEqual(out["input"]["excluded"], {"non_numeric": 1})

    def test_digits_glued_to_text_are_not_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(self.csv(tmp, "csat\n" + "5 - Very satisfied\n4\n" * 20 + "2hrs\n"), "--scale", "1-5")
            self.assertEqual(out["input"]["excluded"], {"non_numeric": 1})
            self.assertTrue(any("5 = Very satisfied" in n for n in out["notes"]))

    def test_group_notes_are_printed(self):
        proc = run("--counts", "0,0,0,0,3")
        self.assertIn("fewer than 5 answers", proc.stdout)
        self.assertIn("every answer is the same", proc.stdout)

    def test_welch_p_not_given_on_tiny_sides(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(self.csv(tmp, "csat,seg\n5,a\n3,a\n1,b\n2,b\n5,b\n4,b\n5,b\n"), "--scale", "1-5",
                           "--segment-col", "seg", "--compare", "a", "b")
            self.assertNotIn("mean_p_value", out["comparisons"][0])

    def test_blank_segment_left_out_of_pairwise(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(self.csv(tmp, "csat,seg\n" + "5,a\n4,a\n2,b\n1,b\n3,\n" * 5), "--scale", "1-5",
                           "--segment-col", "seg", "--pairwise")
            self.assertEqual({(c["a"], c["b"]) for c in out["comparisons"]}, {("a", "b")})


class QaPolishRegressionTest(unittest.TestCase):
    """Usability fixes from the 2026-11-19 end-to-end QA."""

    def write(self, tmp, text):
        path = pathlib.Path(tmp) / "in.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_labelled_numbers_with_both_end_labels_set_the_scale(self):
        rows = ["1 - Very dissatisfied", "2 - Dissatisfied", "3 - Neutral", "4 - Satisfied", "5 - Very satisfied",
                "5 - Very satisfied", "4"]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "csat\n" + "\n".join(rows) + "\n")
            out = run_json(path, "--score-col", "csat")
            self.assertEqual((out["scale"]["min"], out["scale"]["max"]), (1, 5))
            self.assertIn("from the labelled answers", out["scale"]["source"])
            self.assertEqual(out["overall"]["n"], 7)
            self.assertIn("Scale: from the labelled answers", run(path, "--score-col", "csat").stdout)

    def test_labelled_numbers_without_both_end_labels_still_stop(self):
        cases = {"low end missing": ["2 - Dissatisfied", "3 - Neutral", "5 - Very satisfied"],
                 "not very is inner": ["2 - Not very satisfied", "4 - Very satisfied"],
                 "plain number outside": ["1 - Very dissatisfied", "5 - Very satisfied", "7"]}
        with tempfile.TemporaryDirectory() as tmp:
            for name, rows in cases.items():
                proc = run(self.write(tmp, "csat\n" + "\n".join(rows) + "\n"), "--score-col", "csat")
                self.assertEqual(proc.returncode, 2, name)
                self.assertIn("--scale", proc.stderr, name)

    def test_ticket_id_column_is_named_not_called_customers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "ticket_id,csat,comment\nT1,5,great\nT2,1,bad\nT3,4,ok\nT3,2,meh\n")
            args = [path, "--score-col", "csat", "--scale", "1-5", "--id-col", "ticket_id", "--comment-col", "comment"]
            out = run_json(*args)
            self.assertEqual(out["input"]["id_col"], "ticket_id")
            self.assertTrue(any("looks like a ticket or case id" in n for n in out["notes"]))
            self.assertTrue(any("share a 'ticket_id' value" in w for w in out["warnings"]))
            text = run(*args).stdout
            self.assertIn("distinct 'ticket_id' values", text)
            self.assertNotIn("distinct ids", text)
            path = self.write(tmp, "customer,csat\nC1,5\nC2,1\nC2,4\n")
            customer = run_json(path, "--score-col", "csat", "--scale", "1-5", "--id-col", "customer")
        self.assertFalse(any("ticket or case id" in n for n in customer["notes"]))


if __name__ == "__main__":
    unittest.main()
