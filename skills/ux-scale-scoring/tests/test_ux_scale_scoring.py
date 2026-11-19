"""Tests for scripts/ux_scale_scoring.py. Run from the skill folder: python3 -m unittest discover -s tests

Expected values come from fixtures/*.expected.json: Brooke's (1996) published scored example, or synthetic
data worked out by an independent method (fixtures/README.md).
"""
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
SCRIPT = SKILL / "scripts" / "ux_scale_scoring.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ux_scale_scoring", SCRIPT)
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


def write(tmp, name, text, encoding="utf-8"):
    path = pathlib.Path(tmp) / name
    path.write_bytes(text.encode(encoding))
    return path


def sus_csv(rows, prefix="sus_"):
    header = ",".join(f"{prefix}{i}" for i in range(1, 11))
    return header + "\n" + "\n".join(",".join(map(str, r)) for r in rows) + "\n"


class BrookeExampleTest(unittest.TestCase):
    def test_published_score_55(self):
        exp = expected("brooke_1996")
        out = run_json(FIXTURES / "brooke_1996.input.csv", "--instrument", "sus")
        self.assertEqual(out["input"]["items"], [f"SUS{i}" for i in range(1, 11)])
        self.assertEqual(out["overall"]["mean"], exp["sus"])
        self.assertEqual(out["overall"]["grade"], exp["grade"])
        self.assertEqual(out["overall"]["adjective"], exp["adjective"])
        self.assertNotIn("ci", out["overall"])  # one participant: no interval

    def test_independent_formula(self):
        # Sauro's form of the same score: ((sum odd - 5) + (25 - sum even)) * 2.5.
        for values in ([5, 4, 2, 1, 2, 3, 2, 4, 5, 2], [1] * 10, [5] * 10, [5, 1] * 5, [1, 5] * 5, [3] * 10):
            want = ((sum(values[0::2]) - 5) + (25 - sum(values[1::2]))) * 2.5
            self.assertEqual(M.score_row("sus", values, (1, 5), False), want)
        self.assertEqual(M.score_row("sus", [5, 1] * 5, (1, 5), False), 100.0)
        self.assertEqual(M.score_row("sus", [1, 5] * 5, (1, 5), False), 0.0)
        self.assertEqual(M.score_row("sus-positive", [5] * 10, (1, 5), False), 100.0)


class TwoDesignsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exp = expected("two_designs")
        cls.args = [FIXTURES / "two_designs.input.csv", "--instrument", "sus", "--group-col", "design"]
        cls.out = run_json(*cls.args, "--compare", "A", "B", "--target", "68")
        # The one-sample t on all 24 rows as one sample: without --group-col (with it, the pooled line is not tested).
        cls.target = run_json(FIXTURES / "two_designs.input.csv", "--instrument", "sus", "--target", "68", "--tail",
                              "above")
        cls.paired = run_json(*cls.args, "--compare", "A", "B", "--paired", "--id-col", "participant")

    def test_group_means_intervals_and_grades(self):
        groups = by_label(self.out["groups"])
        for name in ("A", "B"):
            got, want = groups[name], self.exp[name]
            self.assertEqual(got["n"], want["n"])
            self.assertAlmostEqual(got["mean"], want["mean"], delta=1e-9)
            self.assertAlmostEqual(got["sd"], want["sd"], delta=1e-5)
            for g, w in zip(got["ci"], want["ci"]):
                self.assertAlmostEqual(g, w, delta=1e-4)
            self.assertEqual(got["grade"], want["grade"])
        self.assertAlmostEqual(groups["A"]["percentile"], self.exp["A"]["percentile"], delta=1e-3)
        o = self.out["overall"]
        self.assertAlmostEqual(o["mean"], self.exp["overall"]["mean"], delta=1e-9)
        for g, w in zip(o["ci"], self.exp["overall"]["ci"]):
            self.assertAlmostEqual(g, w, delta=1e-4)

    def test_welch(self):
        c, want = self.out["comparisons"][0], self.exp["welch"]
        self.assertEqual(c["kind"], "independent")
        for key in ("difference", "t", "df", "p_value"):
            self.assertAlmostEqual(c[key], want[key], delta=1e-5, msg=key)
        self.assertEqual(c["verdict"], "significant")

    def test_paired(self):
        c, want = self.paired["comparisons"][0], self.exp["paired"]
        self.assertEqual((c["kind"], c["pairs"]), ("paired", 12))
        self.assertAlmostEqual(c["t"], want["t"], delta=1e-5)
        self.assertAlmostEqual(c["sd_difference"], want["sd_difference"], delta=1e-6)
        self.assertAlmostEqual(c["p_value"], want["p_value"], delta=1e-9)
        for g, w in zip(c["ci"], want["ci"]):
            self.assertAlmostEqual(g, w, delta=1e-4)

    def test_target_one_tailed(self):
        got = self.target["target"][0]
        self.assertEqual(got["label"], "Overall")
        self.assertAlmostEqual(got["t"], self.exp["overall_vs_68_above"]["t"], delta=1e-6)
        self.assertAlmostEqual(got["p_value"], self.exp["overall_vs_68_above"]["p_value"], delta=1e-6)
        self.assertFalse(got["significant"])

    def test_checks(self):
        checks = self.out["checks"]
        self.assertLess(checks["odd_even_correlation"], 0)
        self.assertEqual(checks["straight_lined"], 1)
        self.assertEqual(checks["agree_with_both_tones"], 0)

    def test_scores_out_and_input_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "out" / "scores.csv"
            run_json(*self.args, "--id-col", "participant", "--scores-out", path)
            lines = path.read_text().splitlines()
            self.assertEqual(lines[0], "id,group,score,items_imputed")
            self.assertEqual(len(lines), 25)
            copy = pathlib.Path(tmp) / "in.csv"
            copy.write_bytes((FIXTURES / "two_designs.input.csv").read_bytes())
            proc = run(copy, "--instrument", "sus", "--scores-out", copy)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(copy.read_bytes(), (FIXTURES / "two_designs.input.csv").read_bytes())

    def test_readable_output(self):
        proc = run(*self.args, "--compare", "A", "B")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("A: n = 12; mean 76.2 (65.1 to 87.4)", proc.stdout)
        self.assertIn("p = 0.0201: significant", proc.stdout)

    def test_independent_test_warns_when_same_people(self):
        out = run_json(*self.args, "--compare", "A", "B", "--id-col", "participant")
        self.assertTrue(any("--paired" in w for w in out["warnings"]))


class OtherInstrumentsTest(unittest.TestCase):
    def test_umux_lite(self):
        exp = expected("umux_lite")
        out = run_json(FIXTURES / "umux_lite.input.csv", "--instrument", "umux-lite")
        o = out["overall"]
        self.assertAlmostEqual(o["mean"], exp["mean"], delta=1e-9)
        self.assertAlmostEqual(o["sd"], exp["sd"], delta=1e-5)
        for g, w in zip(o["ci"], exp["ci"]):
            self.assertAlmostEqual(g, w, delta=1e-4)
        self.assertAlmostEqual(o["sus_equivalent"], exp["sus_equivalent"], delta=1e-9)
        self.assertEqual(o["sus_equivalent_benchmarks"]["grade"], "B")
        self.assertEqual(o["grade"], "A")  # the raw score, read on the SUS grades, leads

    def test_umux_lite_five_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "u5.csv", "capabilities,ease\n5,5\n3,4\n")
            out = run_json(path, "--instrument", "umux-lite", "--scale", "1-5")
            self.assertAlmostEqual(out["overall"]["mean"], (100 + 62.5) / 2, delta=1e-9)

    def test_tlx(self):
        exp = expected("tlx")
        out = run_json(FIXTURES / "tlx.input.csv", "--instrument", "tlx", "--group-col", "task")
        self.assertFalse(out["scale"]["higher_is_better"])
        groups = by_label(out["groups"])
        self.assertAlmostEqual(groups["t1"]["mean"], exp["t1"]["mean"], delta=1e-9)
        self.assertAlmostEqual(groups["t2"]["sd"], exp["t2"]["sd"], delta=1e-5)
        self.assertAlmostEqual(out["overall"]["mean"], exp["overall_mean"], delta=1e-5)

    def test_tlx_21_point_and_reverse_performance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "t.csv", "mental,physical,temporal,performance,effort,frustration\n21,1,11,1,11,1\n")
            out = run_json(path, "--instrument", "tlx", "--scale", "1-21")
            self.assertAlmostEqual(out["overall"]["mean"], (100 + 0 + 50 + 0 + 50 + 0) / 6, delta=1e-9)
            out = run_json(path, "--instrument", "tlx", "--scale", "1-21", "--reverse-performance")
            self.assertAlmostEqual(out["overall"]["mean"], (100 + 0 + 50 + 100 + 50 + 0) / 6, delta=1e-9)

    def test_seq_with_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "s.csv", "task,seq\nt1,Very easy\nt1,6\nt1,5 - Somewhat easy\nt2,Very difficult\nt2,3\n")
            out = run_json(path, "--instrument", "seq", "--group-col", "task")
            groups = by_label(out["groups"])
            self.assertAlmostEqual(groups["t1"]["mean"], 6.0, delta=1e-12)
            self.assertAlmostEqual(groups["t2"]["mean"], 2.0, delta=1e-12)
            self.assertLessEqual(groups["t1"]["ci"][1], 7)  # clipped to the scale


class MiscodingChecksTest(unittest.TestCase):
    POSITIVE = [[5, 5, 4, 5, 5, 4, 5, 5, 4, 5], [4, 4, 4, 4, 3, 4, 4, 4, 4, 4], [2, 2, 3, 2, 2, 3, 2, 2, 2, 3],
                [3, 3, 3, 4, 3, 3, 3, 3, 4, 3], [5, 4, 5, 5, 4, 5, 5, 4, 5, 5], [1, 2, 1, 1, 2, 1, 2, 1, 1, 2],
                [4, 5, 4, 4, 5, 4, 4, 4, 5, 4], [3, 2, 3, 3, 2, 3, 3, 3, 2, 3], [2, 1, 2, 2, 1, 2, 2, 2, 1, 1],
                [5, 5, 5, 4, 5, 5, 5, 4, 5, 5]]

    def test_all_positive_data_scored_as_standard_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "pos.csv", sus_csv(self.POSITIVE))
            out = run_json(path, "--instrument", "sus")
            self.assertGreater(out["checks"]["odd_even_correlation"], 0.1)
            self.assertTrue(any("sus-positive" in w for w in out["warnings"]))
            self.assertGreater(out["checks"]["agree_with_both_tones"], 0)
            dropped = run_json(path, "--instrument", "sus", "--drop-flagged")
            self.assertLess(dropped["overall"]["n"], 10)
            fine = run_json(path, "--instrument", "sus-positive")
            self.assertFalse(any("Odd and even" in w for w in fine["warnings"]))
            self.assertAlmostEqual(fine["overall"]["mean"],
                                   sum(2.5 * sum(v - 1 for v in r) for r in self.POSITIVE) / 10, delta=1e-9)

    def test_standard_data_scored_as_positive_is_flagged(self):
        rows = [[r[i] if i % 2 == 0 else 6 - r[i] for i in range(10)] for r in self.POSITIVE]
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(write(tmp, "std.csv", sus_csv(rows)), "--instrument", "sus-positive")
            self.assertTrue(any("--instrument sus." in w for w in out["warnings"]))


class InputAndEdgeCaseTest(unittest.TestCase):
    def test_encodings_delimiters_and_qualtrics(self):
        text = (FIXTURES / "two_designs.input.csv").read_text()
        reference = run_json(FIXTURES / "two_designs.input.csv", "--instrument", "sus")["overall"]["mean"]
        lines = text.splitlines()
        width = len(lines[0].split(","))
        qualtrics = "\n".join([lines[0], ",".join(["text"] * width),
                               ",".join(['"{""ImportId"":""QID%d""}"' % i for i in range(width)])] + lines[1:]) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            for name, body, enc in (("bom.csv", "﻿" + text.replace("\n", "\r\n"), "utf-8"),
                                    ("u16.csv", text, "utf-16"), ("semi.csv", text.replace(",", ";"), "utf-8"),
                                    ("q.csv", qualtrics, "utf-8")):
                out = run_json(write(tmp, name, body, enc), "--instrument", "sus")
                self.assertEqual(out["overall"]["n"], 24, name)
                self.assertAlmostEqual(out["overall"]["mean"], reference, delta=1e-12)

    def test_missing_items_excluded_or_imputed(self):
        rows = sus_csv([[5, 1, 5, 1, 5, 1, 5, 1, 5, 1], [4, 2, 4, 2, 4, 2, 4, 2, 4, ""]])
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "m.csv", rows)
            out = run_json(path, "--instrument", "sus")
            self.assertEqual(out["input"]["excluded"], {"incomplete": 1})
            out = run_json(path, "--instrument", "sus", "--impute-midpoint")
            self.assertEqual(out["overall"]["n"], 2)
            self.assertAlmostEqual(out["overall"]["mean"], (100 + 72.5) / 2, delta=1e-12)

    def test_seven_point_sus_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "s7.csv", sus_csv([[7, 1, 6, 2, 7, 1, 6, 2, 7, 1]] * 5))
            proc = run(path, "--instrument", "sus")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("not the SUS", proc.stderr)
            proc = run(path, "--instrument", "sus", "--scale", "1-7")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("not the SUS", proc.stderr)

    def test_items_must_be_found_or_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "x.csv", "a,b,c\n1,2,3\n")
            proc = run(path, "--instrument", "sus")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("--items", proc.stderr)
            dup = write(tmp, "d.csv", "sus_1,sus_1\n1,2\n")
            self.assertIn("more than one column named", run(dup, "--instrument", "sus").stderr)

    def test_no_scorable_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "e.csv", sus_csv([[""] * 10]))
            proc = run(path, "--instrument", "sus")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("no participant could be scored", proc.stderr)

    def test_all_same_scores_and_one_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = "g," + ",".join(f"sus_{i}" for i in range(1, 11))
            path = write(tmp, "s.csv", header + "\n" + "x,4,2,4,2,4,2,4,2,4,2\n" * 3)
            out = run_json(path, "--instrument", "sus", "--group-col", "g", "--pairwise")
            self.assertEqual(out["overall"]["ci"], [75.0, 75.0])
            self.assertNotIn("comparisons", out)
            self.assertTrue(any("Only one group" in w for w in out["warnings"]))

    def test_small_base_not_significant_is_flagged_not_underpowered(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = "g,sus_" + ",sus_".join(str(i) for i in range(1, 11)) + "\n"
            rows += "a,4,2,4,2,4,2,4,2,4,2\na,4,2,4,2,4,3,4,2,4,2\na,3,2,4,2,4,2,4,2,4,2\n"
            rows += "b,4,2,4,2,3,2,4,2,4,2\nb,4,2,4,2,4,2,4,3,4,2\nb,4,2,4,2,4,2,3,2,4,2\n"
            out = run_json(write(tmp, "u.csv", rows), "--instrument", "sus", "--group-col", "g", "--compare", "a", "b")
            self.assertEqual(out["comparisons"][0]["verdict"], "not significant")
            self.assertTrue(out["comparisons"][0]["small_base"])

    def test_cgs_boundaries_and_percentile_anchor(self):
        self.assertEqual(M.cgs(68)[0], "C")
        self.assertAlmostEqual(M.cgs(68)[1], 41 + (68 - 65) / (71.1 - 65) * 19, delta=1e-9)
        self.assertEqual(M.cgs(84.1)[0], "A+")
        self.assertEqual(M.cgs(84.0)[0], "A")
        self.assertEqual(M.cgs(51.6)[0], "F")
        self.assertEqual(M.cgs(51.7)[0], "D")
        self.assertEqual(M.cgs(100)[1], 100.0)
        self.assertEqual(M.adjective(85.5), "Excellent")
        self.assertTrue(math.isclose(M.cgs(0)[1], 0.0))

    def test_deterministic(self):
        args = (FIXTURES / "two_designs.input.csv", "--instrument", "sus", "--group-col", "design", "--pairwise",
                "--json")
        self.assertEqual(run(*args).stdout, run(*args).stdout)


class ReviewRegressionTest(unittest.TestCase):
    """Cases from the 2026-11-19 review. Each failed on the version before the fix."""

    def test_seven_point_umux_labels_use_the_seven_point_map(self):
        # Two "Strongly agree" answers used to be read with the 5-point map: 66.7 instead of 100.
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(write(tmp, "u.csv", "capabilities,ease\nStrongly agree,Strongly agree\n"),
                           "--instrument", "umux-lite")
            self.assertEqual(out["input"]["labels"]["source"], "agree7")
            self.assertEqual(out["overall"]["mean"], 100.0)
            self.assertAlmostEqual(out["overall"]["sus_equivalent"], 87.9, delta=1e-9)
            self.assertEqual(out["overall"]["grade"], "A+")

    def test_five_point_somewhat_labels(self):
        rows = [["Somewhat agree", "Somewhat disagree"] * 5, ["Strongly agree", "Strongly disagree"] * 5]
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(write(tmp, "s.csv", sus_csv(rows)), "--instrument", "sus")
            self.assertEqual(out["input"]["labels"]["source"], "agree5-somewhat")
            self.assertAlmostEqual(out["overall"]["mean"], 87.5, delta=1e-9)
            self.assertTrue(any("4 = somewhat agree" in n for n in out["notes"]))  # the whole map is printed

    def test_paired_study_gives_no_pooled_inference(self):
        # The pooled 24 rows from 12 people used to be tested against 60 as 24 independent scores (p = 0.047).
        out = run_json(FIXTURES / "two_designs.input.csv", "--instrument", "sus", "--group-col", "design",
                       "--compare", "A", "B", "--id-col", "participant", "--paired", "--target", "60",
                       "--adjust", "holm")
        self.assertNotIn("ci", out["overall"])
        overall = next(t for t in out["target"] if t["label"].startswith("All rows (pooled"))
        self.assertFalse(overall["tested"])
        a = next(t for t in out["target"] if t["label"] == "A")
        self.assertEqual(a["family_size"], 2)
        self.assertAlmostEqual(a["p_adjusted"], 2 * a["p_value"], delta=1e-12)

    def test_blank_ids_are_not_paired(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "p.csv", "participant,design,ease\n,A,7\np1,A,7\n,B,1\np1,B,6\n")
            out = run_json(path, "--instrument", "seq", "--items", "ease", "--group-col", "design", "--compare", "A",
                           "B", "--paired", "--id-col", "participant")
            c = out["comparisons"][0]
            self.assertEqual((c["pairs"], c["no_id_a"], c["no_id_b"]), (1, 1, 1))
            self.assertFalse(c["tested"])

    def test_seq_with_easy_at_the_low_end_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "q.csv", "difficulty\n1 - Very easy\n1 - Very easy\n2 - Easy\n")
            proc = run(path, "--instrument", "seq")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("--seq-reversed", proc.stderr)
            out = run_json(path, "--instrument", "seq", "--seq-reversed")
            self.assertAlmostEqual(out["overall"]["mean"], (7 + 7 + 6) / 3, delta=1e-12)

    def test_identical_scores_have_zero_sd(self):
        # On Python 3.9 the plain float sum left a tiny SD, so ten identical scores gave t = -4e16 against 68.
        self.assertEqual(M.mean_sd([100 * 2 / 12] * 10)[1], 0.0)
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(write(tmp, "c.csv", "capabilities,ease\n" + "2,2\n" * 10), "--instrument", "umux-lite",
                           "--target", "68")
            self.assertFalse(out["target"][0]["tested"])

    def test_imputation_is_capped(self):
        with tempfile.TemporaryDirectory() as tmp:
            # One answered item and nine skipped used to score 55 with --impute-midpoint.
            path = write(tmp, "i.csv", sus_csv([[5] + [""] * 9, [5, 1, 5, 1, 5, 1, 5, 1, 5, ""],
                                                [4, 2, 4, 2, 4, 2, 4, 2, 4, 2]]))
            out = run_json(path, "--instrument", "sus", "--impute-midpoint")
            self.assertEqual(out["overall"]["n"], 2)
            self.assertEqual(out["input"]["excluded"], {"incomplete": 1})
            self.assertEqual(out["complete_case"]["n"], 1)
            more = run_json(path, "--instrument", "sus", "--impute-midpoint", "--max-imputed", "9")
            self.assertEqual(more["overall"]["n"], 3)

    def test_umux_regression_only_on_seven_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(write(tmp, "u5.csv", "capabilities,ease\n5,5\n3,4\n"), "--instrument", "umux-lite",
                           "--scale", "1-5")
            self.assertNotIn("sus_equivalent", out["overall"])
            self.assertIn("grade", out["overall"])

    def test_argument_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "u.csv", "capabilities,ease\nAgree,Agree\n")
            proc = run(path, "--instrument", "umux-lite", "--labels", "Agree=X")
            self.assertEqual(proc.returncode, 2)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertEqual(run(path, "--instrument", "umux-lite", "--target", "nan").returncode, 2)
            self.assertEqual(run(FIXTURES / "two_designs.input.csv", "--instrument", "sus-positive",
                                 "--drop-flagged").returncode, 2)
        tlx = run_json(FIXTURES / "tlx.input.csv", "--instrument", "tlx", "--reverse-performance")
        self.assertIn("reversed", tlx["scale"]["tlx_performance"])

    def test_column_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = "ResponseId," + ",".join(f"Q5_{i}" for i in range(1, 11))
            out = run_json(write(tmp, "q.csv", header + "\nR1,5,1,5,1,5,1,5,1,5,1\n"), "--instrument", "sus")
            self.assertEqual(out["input"]["items"][0], "Q5_1")
            tlx = run_json(write(tmp, "t.csv", "Timestamp,mental,physical,temporal,performance,effort,frustration\n"
                                               "2026,50,10,40,30,60,35\n"), "--instrument", "tlx")
            self.assertEqual(tlx["input"]["items"][2], "temporal")
            umux = run_json(write(tmp, "m.csv", "capabilities,ease,Please explain\n7,7,x\n"), "--instrument",
                            "umux-lite")
            self.assertEqual(umux["input"]["items"], ["capabilities", "ease"])


class QaPolishRegressionTest(unittest.TestCase):
    """Usability fixes from the 2026-11-19 end-to-end QA."""

    def test_labelled_numbers_set_the_scale_when_both_ends_are_labelled(self):
        answers = ["1 - Strongly disagree", "3 - Neutral", "5 - Strongly agree", "4"]
        scale, source, labels, _ = M.resolve_scale_and_labels(answers, None, None, None, (), {})
        self.assertEqual(scale, (1, 5))
        self.assertIn("from the labelled answers", source)
        self.assertIsNone(labels)
        for missing_end in (["2 - Disagree", "5 - Strongly agree"], ["1 - Strongly disagree", "4 - Agree"],
                            ["2 - Not very easy", "4 - Very easy"], ["1 - Strongly disagree", "5 - Strongly agree", "7"]):
            with self.assertRaises(M.InputError):
                M.resolve_scale_and_labels(missing_end, None, None, None, (), {})

    def test_pooled_line_across_independent_groups_is_not_graded(self):
        out = run_json(FIXTURES / "two_designs.input.csv", "--instrument", "sus", "--group-col", "design",
                       "--compare", "A", "B")
        overall = out["overall"]
        self.assertEqual(overall["label"], "All participants (pooled across the design groups)")
        self.assertTrue(overall["pooled_across_groups"])
        for key in ("grade", "grade_range", "percentile", "adjective"):
            self.assertNotIn(key, overall)
        self.assertIn("ci", overall)
        self.assertIn("grade", by_label(out["groups"])["A"])
        text = run(FIXTURES / "two_designs.input.csv", "--instrument", "sus", "--group-col", "design").stdout
        self.assertNotIn("Overall:", text)
        self.assertNotIn("grade C (D to B)", text)

    def test_grade_and_adjective_disagreement_is_explained(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 62.0 and 63.0: grade D and C- sit next to the closest adjective "Good".
            rows = sus_csv([[4, 2, 4, 2, 4, 3, 3, 3, 3, 3], [4, 2, 4, 2, 4, 3, 3, 3, 3, 3], [4, 2, 4, 2, 3, 3, 3, 3, 3, 3]])
            out = run_json(write(tmp, "d.csv", rows), "--instrument", "sus")
            self.assertEqual((out["overall"]["grade"], out["overall"]["adjective"]), ("D", "Good"))
            self.assertTrue(out["overall"]["grade_adjective_differ"])
            self.assertTrue(any("different published schemes" in n for n in out["notes"]))
            agree = run_json(FIXTURES / "brooke_1996.input.csv", "--instrument", "sus")
            self.assertFalse(agree["overall"]["grade_adjective_differ"])
            self.assertFalse(any("different published schemes" in n for n in agree["notes"]))
        self.assertEqual(M.GRADE_ADJECTIVES["D"] & {"Good"}, set())

    def test_impute_midpoint_reports_complete_cases_per_group_and_comparison(self):
        header = "g," + ",".join(f"sus_{i}" for i in range(1, 11))
        body = ["a,5,1,5,1,5,1,5,1,5,1", "a,4,2,4,2,4,2,4,2,4,2", "a,4,1,4,2,5,2,4,1,4,2", "a,4,2,4,,4,2,4,2,4,2",
                "b,3,3,3,3,3,3,3,3,3,3", "b,3,2,3,3,4,3,3,3,3,2", "b,2,3,3,3,3,3,3,4,3,3", "b,3,3,3,3,,3,3,3,3,3"]
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "i.csv", header + "\n" + "\n".join(body) + "\n")
            out = run_json(path, "--instrument", "sus", "--group-col", "g", "--compare", "a", "b", "--impute-midpoint")
            groups = by_label(out["groups"])
            self.assertEqual(groups["a"]["complete_case"]["n"], 3)
            self.assertAlmostEqual(groups["a"]["complete_case"]["mean"], (100 + 75 + 82.5) / 3, delta=1e-9)
            cc = out["comparisons"][0]["complete_case"]
            self.assertTrue(cc["tested"])
            self.assertEqual((cc["n_a"], cc["n_b"]), (3, 3))
            self.assertIn("Complete cases only: ", run(path, "--instrument", "sus", "--group-col", "g", "--compare",
                                                      "a", "b", "--impute-midpoint").stdout)

    def test_one_participant_is_not_told_to_report_an_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(write(tmp, "one.csv", sus_csv([[4, 2, 4, 2, 4, 2, 4, 2, 4, 2]])), "--instrument", "sus")
            self.assertNotIn("ci", out["overall"])
            self.assertFalse(any("Report the interval" in w for w in out["warnings"]))
            self.assertTrue(any(w.startswith("One participant: Overall") for w in out["warnings"]))

    def test_one_sided_compare(self):
        args = [FIXTURES / "two_designs.input.csv", "--instrument", "sus", "--group-col", "design", "--compare", "A", "B"]
        two = run_json(*args)["comparisons"][0]
        above = run_json(*args, "--tail", "above")["comparisons"][0]
        below = run_json(*args, "--tail", "below")["comparisons"][0]
        self.assertEqual(above["tail"], "above")
        self.assertAlmostEqual(above["p_value"], two["p_value"] / 2, delta=1e-12)
        self.assertAlmostEqual(below["p_value"], 1 - two["p_value"] / 2, delta=1e-12)
        self.assertEqual((above["verdict"], below["verdict"]), ("significant", "not significant"))
        self.assertIsNone(above["ci"][1])
        # One-sided 95% bound = two-sided 90% interval's lower end.
        ninety = run_json(*args, "--confidence", "0.90")["comparisons"][0]
        self.assertAlmostEqual(above["ci"][0], ninety["ci"][0], delta=1e-6)
        self.assertEqual(run(*args, "--tail", "above", "--target", "68").returncode, 2)
        pairwise = run(FIXTURES / "two_designs.input.csv", "--instrument", "sus", "--group-col", "design",
                       "--pairwise", "--tail", "above", "--target", "68")
        self.assertEqual(pairwise.returncode, 2)
        self.assertIn("--compare A B", pairwise.stderr)


class GeminiReviewRegressionTest(unittest.TestCase):
    """Cases from the third (Gemini) review, 2026-11-19. Each failed on the version before the fix."""

    def test_reverse_performance_needs_performance_fourth(self):
        # --reverse-performance flipped the fourth --items column, whatever it was.
        text = "m,p,t,e,performance,f\n50,20,40,60,10,30\n60,30,50,70,20,40\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "t.csv", text)
            proc = run(path, "--instrument", "tlx", "--items", "m,p,t,e,performance,f", "--reverse-performance")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("fourth", proc.stderr)
            out = run_json(path, "--instrument", "tlx", "--items", "m,p,t,performance,e,f", "--reverse-performance")
            self.assertAlmostEqual(out["overall"]["mean"], ((50 + 20 + 40 + 90 + 60 + 30) / 6 + (60 + 30 + 50 + 80 + 70 + 40) / 6) / 2)

    def test_seven_point_sus_text_labels_refused(self):
        # 2 "Somewhat" answers in 200 slipped under the 5% rule and "Agree" (6 of 7) was scored as 4 of 5.
        rows = [["Agree", "Disagree"] * 5 for _ in range(20)]
        rows[0][0] = "Somewhat agree"
        rows[1][1] = "Somewhat disagree"
        with tempfile.TemporaryDirectory() as tmp:
            proc = run(write(tmp, "s.csv", sus_csv(rows)), "--instrument", "sus")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("7-point", proc.stderr)

    def test_seven_point_sus_numbers_refused(self):
        # One 6 or 7 for each of 10 of 20 participants is 5% of the cells: they were dropped and the rest scored.
        rows = [[4, 2] * 5 for _ in range(20)]
        for i in range(10):
            rows[i][0] = 6
        with tempfile.TemporaryDirectory() as tmp:
            proc = run(write(tmp, "s.csv", sus_csv(rows)), "--instrument", "sus")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("7-point", proc.stderr)

    def test_seq_negated_anchor_is_not_reversed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "q.csv", "seq\n1 - Not at all easy\n7 - Not difficult at all\n4\n")
            out = run_json(path, "--instrument", "seq")
            self.assertAlmostEqual(out["overall"]["mean"], 4.0)

    def test_seq_reversed_refused_on_text_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "q.csv", "seq\nVery easy\nEasy\nVery difficult\n")
            proc = run(path, "--instrument", "seq", "--seq-reversed")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("--seq-reversed", proc.stderr)

    def test_target_with_groups_leaves_out_pooled_line_and_blank_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "g.csv", "design,seq\nA,6\nA,7\nA,5\nA,6\n,3\n,4\n")
            out = run_json(path, "--instrument", "seq", "--group-col", "design", "--target", "5", "--adjust", "holm")
            pooled = next(t for t in out["target"] if t["label"].startswith("All participants"))
            self.assertFalse(pooled["tested"])
            self.assertFalse(any(t["label"] == "(blank)" for t in out["target"]))
            a = next(t for t in out["target"] if t["label"] == "A")
            self.assertEqual(a["family_size"], 1)
            self.assertNotIn("p_adjusted", a)

    def test_sus_detection_needs_exactly_ten_numbered_columns(self):
        header = ",".join(f"Q{i}" for i in range(1, 16))
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "q.csv", header + "\n" + ",".join(["3"] * 15) + "\n")
            proc = run(path, "--instrument", "sus")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("--items", proc.stderr)
            matrix = ",".join(f"Q5_{i}" for i in range(0, 11))
            proc = run(write(tmp, "m.csv", matrix + "\n" + ",".join(["3"] * 11) + "\n"), "--instrument", "sus")
            self.assertEqual(proc.returncode, 2)

    def test_constant_odd_even_means_have_no_correlation(self):
        # Means like 1.4 are not exact in binary; the float sum left a tiny variance and a correlation of noise.
        for k in range(5, 26):
            for n in (3, 6, 10, 12, 24):
                self.assertIsNone(M.pearson([k / 5] * n, list(range(n))), (k, n))
        rows = [[2, 3, 1, 3, 1, 3, 1, 3, 1, 0 + 3] for _ in range(12)]
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(write(tmp, "s.csv", sus_csv(rows)), "--instrument", "sus")
            self.assertIsNone(out["checks"]["odd_even_correlation"])
            self.assertFalse(any("move together" in w for w in out["warnings"]))

    def test_reversed_agree_labels_stop(self):
        rows = [["1 - Strongly agree", "5 - Strongly disagree"] * 5, ["2 - Agree", "4 - Disagree"] * 5]
        with tempfile.TemporaryDirectory() as tmp:
            proc = run(write(tmp, "s.csv", sus_csv(rows)), "--instrument", "sus")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("agree", proc.stderr)

    def test_drop_flagged_message_and_imputed_count(self):
        rows = [[5, 5, 5, 5, 5, 5, 5, 5, 5, ""], [4, 2, 4, 2, 4, 2, 4, 2, 4, 2], [5, 1, 5, 1, 5, 1, 5, 1, 5, 1]]
        with tempfile.TemporaryDirectory() as tmp:
            out = run_json(write(tmp, "s.csv", sus_csv(rows)), "--instrument", "sus", "--impute-midpoint",
                           "--drop-flagged")
            self.assertEqual(out["input"]["excluded"]["flagged_inconsistent"], 1)
            self.assertEqual(out["input"]["imputed_midpoint"], 0)
            self.assertNotIn("complete_case", out)
            self.assertFalse(any("They are kept" in w for w in out["warnings"]))

    def test_blank_ids_do_not_count_as_shared(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "g.csv", "pid,design,seq\n,A,6\np1,A,7\n,B,3\np2,B,4\n")
            out = run_json(path, "--instrument", "seq", "--group-col", "design", "--id-col", "pid", "--compare", "A", "B")
            self.assertFalse(any("appear in both" in w for w in out["warnings"]))

    def test_number_edge_cases(self):
        self.assertIsNone(M.as_number("0_5"))
        self.assertEqual(M.read_point("NaN", None), (None, "non_answer"))
        with tempfile.TemporaryDirectory() as tmp:
            text = "mental,physical,temporal,performance,effort,frustration\n42.5,10,20,30,40,50\n"
            out = run_json(write(tmp, "t.csv", text), "--instrument", "tlx")
            self.assertAlmostEqual(out["overall"]["mean"], (42.5 + 10 + 20 + 30 + 40 + 50) / 6)

    def test_trailing_blank_header_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = "seq,,\n5,,\n6,,\n"
            out = run_json(write(tmp, "q.csv", text), "--instrument", "seq")
            self.assertEqual(out["overall"]["n"], 2)

    def test_conflicting_flags_stop(self):
        args = [FIXTURES / "two_designs.input.csv", "--instrument", "sus", "--group-col", "design"]
        self.assertEqual(run(*args, "--compare", "A", "B", "--pairwise").returncode, 2)
        self.assertEqual(run(FIXTURES / "brooke_1996.input.csv", "--instrument", "sus", "--tail", "above").returncode, 2)


if __name__ == "__main__":
    unittest.main()
