"""Tests for scripts/survey_weighting.py. Run from the skill folder: python3 -m unittest discover -s tests

Expected values come from a published raking example (Battaglia, Hoaglin and Frankel 2009, Exhibit 1), an
independent raking loop in base R (fixtures/r_reference.R), hand arithmetic (fixtures/README.md) and
properties of iterative proportional fitting, not from the script.
"""
import csv
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "survey_weighting.py"

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("survey_weighting", SCRIPT)
sw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sw)


def run(*args):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                          check=False)


def run_json(*args):
    proc = run(*args, "--json")
    if proc.returncode != 0:
        raise AssertionError(f"exit {proc.returncode}: {proc.stderr}")
    return json.loads(proc.stdout)


def tmpdir():
    return tempfile.mkdtemp()


def write_csv(rows, encoding="utf-8", delimiter=",", newline="\n"):
    handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding=encoding, newline="")
    csv.writer(handle, delimiter=delimiter, lineterminator=newline).writerows(rows)
    handle.close()
    return handle.name


def margin(result, variable):
    return {c["category"]: c for m in result["margins"] if m["variable"] == variable for c in m["categories"]}


class Battaglia2009(unittest.TestCase):
    """Exhibit 1 of Battaglia, Hoaglin and Frankel (2009): the joint table of design weights was solved from
    the published iteration-1 margins and the iteration-2 VARIABLE1 margins (fixtures/README.md). The
    iteration-2 VARIABLE2 and iteration-3 margins below were not used in that solve."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_json(FIXTURES / "battaglia_2009.input.csv", "--targets", FIXTURES / "battaglia_2009.targets.csv",
                           "--base-weight", "design_weight", "--history", "--tolerance", "1e-12")
        cls.hist = cls.res["fit"]["history"]

    def margins(self, iteration, variable):
        return next(h["margins"] for h in self.hist if h["iteration"] == iteration and h["variable"] == variable)

    def test_iteration_margins_match_exhibit_1(self):
        published = {
            (1, 0): [15915.87, 10912.05, 18022.90], (1, 1): [32684.74, 30115.56],
            (2, 0): [22102.81, 16442.32, 24255.17], (2, 1): [30708.98, 32091.32],
            (3, 0): [22154.09, 16533.34, 24112.87], (3, 1): [30697.40, 32102.90],
        }
        for (it, var), want in published.items():
            for got, w in zip(self.margins(it, var), want):
                self.assertAlmostEqual(got, w, delta=0.011, msg=f"iteration {it} variable {var + 1}")

    def test_converges_to_control_totals(self):
        m1 = margin(self.res, "variable1")
        for cat, total in {"1": 22154.39, "2": 16533.88, "3": 24112.03}.items():
            self.assertAlmostEqual(m1[cat]["weighted_share"] * 62800.30, total, places=4)
        self.assertAlmostEqual(self.res["weights"]["sum"], 62800.30, places=6)

    def test_tolerance_of_one_stops_with_the_exhibit_weights(self):
        # The macro stops when every margin is within 1 of its control total (share tolerance 1/62800.30). It
        # checks at the start of iteration 3, so it reports "iteration 3"; this script checks at the end of each
        # cycle and reports 2 completed cycles. The weights are the same: their VARIABLE1 margins are the
        # exhibit's iteration-3 calculated margins.
        res = run_json(FIXTURES / "battaglia_2009.input.csv", "--targets", FIXTURES / "battaglia_2009.targets.csv",
                       "--base-weight", "design_weight", "--tolerance", str(1 / 62800.30))
        self.assertEqual(res["fit"]["iterations"], 2)
        m1 = margin(res, "variable1")
        for cat, want in {"1": 22154.09, "2": 16533.34, "3": 24112.87}.items():
            self.assertAlmostEqual(m1[cat]["weighted_share"] * res["weights"]["sum"], want, delta=0.011)


class PanelAgainstR(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = run_json(FIXTURES / "panel.input.csv", "--targets", FIXTURES / "panel.targets.csv", "--estimate",
                           "q1", "--tolerance", "1e-12")

    def test_weights_summary_matches_r(self):
        ws = self.res["weights"]
        self.assertAlmostEqual(ws["min"], 0.504805813932, places=10)
        self.assertAlmostEqual(ws["max"], 2.37479485574, places=10)
        self.assertAlmostEqual(ws["n_eff"], 166.619667509, places=8)
        self.assertAlmostEqual(ws["deff"], 1.20033848939, places=10)
        self.assertAlmostEqual(ws["median"], 0.817101441192, places=10)
        self.assertAlmostEqual(ws["p95"], 1.66743495586, places=10)
        self.assertAlmostEqual(ws["sum"], 200, places=9)

    def test_margins_hit_targets_and_estimate_matches_r(self):
        g = margin(self.res, "gender")
        self.assertAlmostEqual(g["Female"]["weighted_share"], 0.51, places=10)
        self.assertAlmostEqual(g["Female"]["sample_share"], 135 / 200)
        r = margin(self.res, "region")
        self.assertAlmostEqual(r["West"]["weighted_share"], 0.25, places=10)
        yes = next(c for c in self.res["estimates"][0]["categories"] if c["category"] == "Yes")
        self.assertAlmostEqual(yes["weighted_share"], 0.475951220922, places=9)
        self.assertAlmostEqual(yes["unweighted_share"], 83 / 200)

    def test_deff_identity(self):
        # Independent check: Kish deff = 1 + CV^2 (population CV) = n / n_eff.
        ws = self.res["weights"]
        self.assertAlmostEqual(ws["deff"], 1 + ws["cv"] ** 2, places=12)
        self.assertAlmostEqual(ws["deff"], ws["n"] / ws["n_eff"], places=12)

    def test_inline_targets_and_percents_equal_file(self):
        res = run_json(FIXTURES / "panel.input.csv", "--target", "gender:Female=0.51;Male=0.49",
                       "--target", "age_group:18-34=30;35-54=33;55+=37", "--target",
                       "region:north=35;SOUTH=40;West=25", "--tolerance", "1e-12")
        self.assertAlmostEqual(res["weights"]["n_eff"], self.res["weights"]["n_eff"], places=8)


class TwoByTwoProperty(unittest.TestCase):
    def test_raking_preserves_the_odds_ratio(self):
        # IPF on two margins keeps the cross-product ratio of the starting table (Mosteller 1968).
        a, b, c, d = 30, 10, 20, 40
        rows = [["x", "y"]] + [["1", "1"]] * a + [["1", "2"]] * b + [["2", "1"]] * c + [["2", "2"]] * d
        path = write_csv(rows)
        out = os.path.join(tmpdir(), "w.csv")
        run_json(path, "--target", "x:1=70;2=30", "--target", "y:1=45;2=55", "--out", out, "--tolerance", "1e-13")
        cells = {}
        with open(out, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                cells[(r["x"], r["y"])] = cells.get((r["x"], r["y"]), 0.0) + float(r["weight"])
        odds = cells[("1", "1")] * cells[("2", "2")] / (cells[("1", "2")] * cells[("2", "1")])
        self.assertAlmostEqual(odds, (a * d) / (b * c), places=8)
        total = sum(cells.values())
        self.assertAlmostEqual((cells[("1", "1")] + cells[("1", "2")]) / total, 0.70, places=10)
        self.assertAlmostEqual((cells[("1", "1")] + cells[("2", "1")]) / total, 0.45, places=10)


class CellWeighting(unittest.TestCase):
    def test_hand_values(self):
        res = run_json(FIXTURES / "cells.input.csv", "--targets", FIXTURES / "cells.targets.csv", "--estimate", "q1")
        self.assertEqual(res["fit"]["method"], "cell")
        cells = margin(res, "gender x age")
        self.assertAlmostEqual(cells["F x young"]["mean_weight"], 0.8)
        self.assertAlmostEqual(cells["M x young"]["mean_weight"], 2.0)
        self.assertAlmostEqual(cells["M x old"]["mean_weight"], 1.0)
        self.assertAlmostEqual(res["weights"]["n_eff"], 256 / 18.4, places=10)
        yes = next(c for c in res["estimates"][0]["categories"] if c["category"] == "Yes")
        self.assertAlmostEqual(yes["weighted_share"], 6.2 / 16, places=12)
        self.assertTrue(any("fewer than 5" in w for w in res["warnings"]))


class Trimming(unittest.TestCase):
    def test_trim_caps_weights_and_keeps_margins(self):
        res = run_json(FIXTURES / "panel.input.csv", "--targets", FIXTURES / "panel.targets.csv", "--trim-max", "2")
        trim = res["fit"]["trim"]
        self.assertTrue(trim["cap_met"])
        self.assertLessEqual(res["weights"]["max_to_mean"], 2 * (1 + 1e-6))
        for m in res["margins"]:
            for c in m["categories"]:
                self.assertAlmostEqual(c["weighted_share"], c["target_share"], places=4)
        untrimmed = run_json(FIXTURES / "panel.input.csv", "--targets", FIXTURES / "panel.targets.csv")
        self.assertLess(res["weights"]["deff"], untrimmed["weights"]["deff"])


class Refusals(unittest.TestCase):
    def test_output_never_overwrites_input(self):
        src = write_csv([["g"], ["a"], ["b"]])
        before = pathlib.Path(src).read_bytes()
        proc = run(src, "--target", "g:a=50;b=50", "--out", src)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(pathlib.Path(src).read_bytes(), before)
        other = write_csv([["x"]])
        self.assertEqual(run(src, "--target", "g:a=50;b=50", "--out", other).returncode, 2)
        self.assertEqual(run(src, "--target", "g:a=50;b=50", "--out", other, "--overwrite").returncode, 0)

    def test_bad_categories_missing_and_empty_targets(self):
        src = write_csv([["g", "h"], ["a", "x"], ["b", "x"], ["c", "y"], ["", "y"]])
        proc = run(src, "--target", "g:a=50;b=50")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("'c'", proc.stderr)
        res = run_json(src, "--target", "g:a=50;b=50", "--collapse", "g:b=b;c", "--missing", "skip-margin")
        self.assertEqual(margin(res, "g")["b"]["n"], 2)
        proc = run(src, "--target", "g:a=50;b=50", "--collapse", "g:b=b;c")
        self.assertIn("skip-margin", proc.stderr)
        proc = run(src, "--target", "h:x=40;y=40;z=20")
        self.assertIn("no respondents in z", proc.stderr)

    def test_conflicting_margins_do_not_converge(self):
        rows = [["sex", "age"]] + [["F", "young"]] * 10 + [["M", "old"]] * 10
        proc = run(write_csv(rows), "--target", "sex:F=50;M=50", "--target", "age:young=30;old=70")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("did not converge", proc.stderr)

    def test_header_only_duplicate_and_existing_weight_column(self):
        self.assertEqual(run(write_csv([["g"]]), "--target", "g:a=1").returncode, 2)
        self.assertEqual(run(write_csv([["g", "g"], ["a", "a"]]), "--target", "g:a=1").returncode, 2)
        # An existing `weight` column only matters when writing: a dry run reports, --out needs a new name.
        has_weight = write_csv([["g", "weight"], ["a", "1"]])
        self.assertEqual(run(has_weight, "--target", "g:a=1").returncode, 0)
        out = os.path.join(tmpdir(), "w.csv")
        self.assertEqual(run(has_weight, "--target", "g:a=1", "--out", out).returncode, 2)
        self.assertEqual(run(has_weight, "--target", "g:a=1", "--out", out, "--weight-col", "w2").returncode, 0)

    def test_unusable_base_weights(self):
        rows = [["g", "bw"]] + [["a", "1"], ["b", "1"]] * 10 + [["a", "x"], ["b", "-1"]]
        proc = run(write_csv(rows), "--target", "g:a=1;b=1", "--base-weight", "bw")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--allow-drop", proc.stderr)
        res = run_json(write_csv(rows), "--target", "g:a=1;b=1", "--base-weight", "bw", "--allow-drop")
        self.assertEqual(res["input"]["weighted_rows"], 20)


class EdgeAndFormats(unittest.TestCase):
    def test_one_respondent_and_all_same(self):
        res = run_json(write_csv([["g"], ["a"]]), "--target", "g:a=1")
        self.assertAlmostEqual(res["weights"]["n_eff"], 1.0)
        res = run_json(write_csv([["g"]] + [["a"]] * 5), "--target", "g:a=100")
        self.assertAlmostEqual(res["weights"]["deff"], 1.0)

    def test_encodings_delimiters_qualtrics_labels(self):
        rows = [["id", "g"]] + [[str(i), "1 - Female" if i % 3 else "2 - Male"] for i in range(30)]
        targets = ["--target", "g:1=50;2=50"]
        base = run_json(write_csv(rows), *targets)["weights"]["n_eff"]
        for path in (write_csv(rows, encoding="utf-8-sig"), write_csv(rows, encoding="utf-16"),
                     write_csv(rows, newline="\r\n"), write_csv(rows, delimiter=";")):
            self.assertAlmostEqual(run_json(path, *targets)["weights"]["n_eff"], base, places=10)
        q = [rows[0], ["ID", "Gender"], ['{"ImportId":"a"}', '{"ImportId":"b"}']] + rows[1:]
        res = run_json(write_csv(q), *targets)
        self.assertEqual(res["input"]["rows"], 30)

    def test_output_file_has_all_rows_and_full_precision(self):
        out = os.path.join(tmpdir(), "weighted.csv")
        res = run_json(FIXTURES / "panel.input.csv", "--targets", FIXTURES / "panel.targets.csv", "--out", out)
        with open(out, encoding="utf-8") as fh:
            data = list(csv.DictReader(fh))
        self.assertEqual(len(data), 200)
        self.assertAlmostEqual(sum(float(r["weight"]) for r in data), res["weights"]["sum"], places=9)
        self.assertGreater(len(data[0]["weight"]), 8)

    def test_text_report(self):
        proc = run(FIXTURES / "panel.input.csv", "--targets", FIXTURES / "panel.targets.csv")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Kish effective n", proc.stdout)
        self.assertIn("No file written", proc.stdout)


def write_text(text, suffix=".csv", mode="w"):
    handle = tempfile.NamedTemporaryFile(mode, suffix=suffix, delete=False,
                                         **({} if "b" in mode else {"encoding": "utf-8", "newline": ""}))
    handle.write(text)
    handle.close()
    return handle.name


class ReviewRegressions(unittest.TestCase):
    """Each case failed (wrong exit code, wrong number or a traceback) before the fix it names."""

    def test_unterminated_quote_is_refused_with_its_line(self):
        # Before: the open quote swallowed the next record; exit 0 with one respondent instead of two.
        proc = run(write_text('g,q\nA,"yes\nB,no\n'), "--target", "g:A=100")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("line 2", proc.stderr)

    def test_bom_with_invalid_byte_is_an_input_error(self):
        # Before: UnicodeDecodeError traceback, exit 1.
        proc = run(write_text(b"\xef\xbb\xbfg\nA\xff\nB\n", mode="wb"), "--target", "g:A=50;B=50")
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)

    def test_infeasible_zero_targets_are_refused(self):
        # Before: every weight became 0 and the fit was reported as converged with error 0.
        proc = run(write_csv([["g", "h"], ["A", "X"], ["B", "Y"]]), "--target", "g:A=1;B=0", "--target", "h:X=0;Y=1")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("cannot all be met", proc.stderr)

    def test_trimming_keeps_the_final_rake_convergence(self):
        # Before: "converged" with margin error 1.3e-2 against tolerance 1e-6.
        rows = [["a", "b", "bw"], ["1", "1", "50"], ["1", "2", "10"], ["2", "1", "20"], ["2", "2", "20"]]
        proc = run(write_csv(rows), "--base-weight", "bw", "--target", "a:1=60;2=40", "--target", "b:1=70;2=30",
                   "--trim-max", "1.2", "--trim-cycles", "1", "--max-iter", "1")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("after trimming", proc.stderr)

    def test_unmet_cap_and_tiny_weights_are_warned(self):
        # Before: min weight ~1e-22 passed silently and the advice was "consider --trim-max 5" after trimming at 3.
        rows = ([["a", "b", "c"]] + [["1", "1", "1"]] * 40 + [["1", "2", "2"]] * 30 + [["2", "1", "2"]] * 25
                + [["2", "2", "1"]] * 3 + [["1", "1", "2"]] * 2)
        res = run_json(write_csv(rows), "--target", "a:1=30;2=70", "--target", "b:1=20;2=80", "--target",
                       "c:1=70;2=30", "--trim-max", "3")
        self.assertFalse(res["fit"]["trim"]["cap_met"])
        text = " ".join(res["warnings"])
        self.assertIn("cap was not met", text)
        self.assertIn("barely count", text)
        self.assertNotIn("consider --trim-max 5", text)

    def test_target_units_follow_the_header_and_percent_signs(self):
        two = write_csv([["g"], ["A"], ["B"]])
        counts = write_csv([["variable", "category", "count"], ["g", "A", "60"], ["g", "B", "40"]])
        self.assertAlmostEqual(run_json(two, "--targets", counts)["weights"]["sum"], 100)  # before: 2
        proc = run(two, "--target", "g:A=60%;B=30%")  # before: a population of 90, shares 66.7/33.3
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--rescale-targets", proc.stderr)
        res = run_json(two, "--target", "g:A=60%;B=30%", "--rescale-targets")
        self.assertAlmostEqual(margin(res, "g")["A"]["target_share"], 2 / 3)
        self.assertAlmostEqual(res["weights"]["sum"], 2)
        for spec in ("g:A=60;B=38.5", "g:A=0.6;B=0.38"):  # before: taken as counts summing to 98.5 / 0.98
            self.assertEqual(run(two, "--target", spec).returncode, 2)
        self.assertAlmostEqual(run_json(two, "--target", "g:A=60;B=38.5", "--target-unit", "counts")["weights"]["sum"],
                               98.5)

    def test_conflicting_count_totals_and_bad_scale_total_are_refused(self):
        src = write_csv([["g", "h"], ["A", "X"], ["B", "Y"], ["A", "Y"], ["B", "X"]])
        proc = run(src, "--target", "g:A=600;B=400", "--target", "h:X=1000;Y=1000")  # before: used 1000
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--scale-total", proc.stderr)
        res = run_json(src, "--target", "g:A=600;B=400", "--target", "h:X=1000;Y=1000", "--scale-total", "1500")
        self.assertAlmostEqual(res["weights"]["sum"], 1500)
        self.assertEqual(run(src, "--target", "g:A=60;B=40", "--scale-total", "-100").returncode, 2)  # before: -60

    def test_thousands_or_decimal_comma_is_not_guessed(self):
        # Before: "1,020" was read as 1.02, giving Female a 0.1% target.
        proc = run(FIXTURES / "panel.input.csv", "--target", "gender:Female=1,020;Male=980")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("1,020", proc.stderr)
        self.assertEqual(sw.parse_number("1,020,000"), 1020000)
        self.assertEqual(sw.parse_number("51,5"), 51.5)
        res = run_json(FIXTURES / "panel.input.csv", "--target", "gender:Female=51,5;Male=48,5")
        self.assertAlmostEqual(margin(res, "gender")["Female"]["target_share"], 0.515)

    def test_mean_weights_are_on_the_final_scale_and_zero_weights_leave_max_min_undefined(self):
        res = run_json(write_csv([["g"], ["A"], ["B"]]), "--target", "g:A=60;B=40", "--scale-total", "1000")
        self.assertAlmostEqual(margin(res, "g")["A"]["mean_weight"], 600)  # before: 1.2
        res = run_json(write_csv([["g"], ["A"], ["B"], ["C"]]), "--target", "g:A=60;B=40;C=0")
        self.assertIsNone(res["weights"]["max_to_min"])  # before: max over the smallest positive weight
        self.assertEqual(res["weights"]["zero_weights"], 1)

    def test_collapse_can_map_missing_codes_and_blanks(self):
        # Before: refused with "use --collapse" even when --collapse mapped the missing code.
        src = write_csv([["g", "h"], ["A", "X"], ["B", "Y"], ["NA", "X"], ["", "Y"]])
        res = run_json(src, "--target", "g:A=50;B=50", "--collapse", "g:A=NA;(blank)")
        self.assertEqual(margin(res, "g")["A"]["n"], 3)
        cells = write_csv([["g", "h", "target"], ["A", "X", "25"], ["A", "Y", "25"], ["B", "Y", "50"]])
        res = run_json(src, "--targets", cells, "--collapse", "g:A=NA;(blank)")
        self.assertEqual(res["fit"]["method"], "cell")

    def test_estimate_with_no_weighted_base_does_not_crash(self):
        # Before: ZeroDivisionError when everyone answering has weight 0.
        res = run_json(write_csv([["g", "q"], ["A", "yes"], ["B", ""], ["C", ""]]), "--target", "g:A=0;B=50;C=50",
                       "--estimate", "q")
        est = res["estimates"][0]
        self.assertEqual(est["n"], 1)
        self.assertIsNone(est["categories"][0]["weighted_share"])
        self.assertTrue(est["note"])

    def test_out_never_replaces_the_targets_file(self):
        src = write_csv([["g"], ["A"], ["B"]])
        targets = write_csv([["variable", "category", "target"], ["g", "A", "50"], ["g", "B", "50"]])
        before = pathlib.Path(targets).read_bytes()
        proc = run(src, "--targets", targets, "--out", targets, "--overwrite")  # before: replaced, exit 0
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(pathlib.Path(targets).read_bytes(), before)
        out = os.path.join(tmpdir(), "w.csv")
        pathlib.Path(out).write_text("old", encoding="utf-8")
        self.assertEqual(run(src, "--targets", targets, "--out", out, "--overwrite").returncode, 0)
        self.assertTrue(pathlib.Path(out).read_text(encoding="utf-8").startswith("g,weight"))
        self.assertEqual(os.listdir(os.path.dirname(out)), ["w.csv"])  # no temporary file left behind

    def test_estimate_categories_are_keyed_like_crosstabs(self):
        # Before: 'Yes' and 'YES' were merged into one 100% category; survey-crosstabs keeps them apart.
        src = write_csv([["g", "q", "r"], ["Female", "Yes", "1"], ["female", "YES", "1 - Agree"], ["Male", "Yes", "2"]])
        res = run_json(src, "--target", "g:Female=50;Male=50", "--estimate", "q", "r")
        self.assertEqual(sorted(c["category"] for c in res["estimates"][0]["categories"]), ["YES", "Yes"])
        self.assertEqual(sorted(c["category"] for c in res["estimates"][1]["categories"]), ["1 - Agree", "2"])
        self.assertTrue(any("'Female', 'female'" in w for w in res["warnings"]))


class GeminiReviewRegressions(unittest.TestCase):
    """Second review round; each case failed before its fix."""

    def test_numbers_followed_by_words_are_not_answer_codes(self):
        # Before: '18 to 24' and '18 to 34' both keyed as code 18 ("given twice"); '1 week'/'1 year' merged.
        res = run_json(write_csv([["a", "q"], ["18 to 24", "1 week"], ["18 to 34", "1 year"]]),
                       "--target", "a:18 to 24=50;18 to 34=50", "--estimate", "q")
        self.assertEqual(len(res["estimates"][0]["categories"]), 2)
        self.assertEqual(sw.norm("5 - Very satisfied"), sw.norm("5"))
        self.assertEqual(sw.norm("(5) Very satisfied"), "#5")
        self.assertNotEqual(sw.norm("50k-75k"), sw.norm("50k+"))

    def test_collapse_combines_target_categories(self):
        # Before: the targets kept 55-64 and 65+, so the collapsed data value had no target.
        res = run_json(write_csv([["age"], ["55-64"], ["18-54"], ["18-54"]]), "--target",
                       "age:18-54=60;55-64=25;65+=15", "--collapse", "age:55+=55-64;65+")
        self.assertAlmostEqual(margin(res, "age")["55+"]["target_share"], 0.40)
        cells = write_csv([["g", "age", "target"], ["A", "young", "30"], ["A", "old", "20"], ["B", "young", "25"],
                           ["B", "mid", "10"], ["B", "old", "15"]])
        res = run_json(write_csv([["g", "age"], ["A", "young"], ["A", "old"], ["B", "young"], ["B", "old"]]),
                       "--targets", cells, "--collapse", "age:old=mid;old")
        self.assertAlmostEqual(margin(res, "g x age")["B x old"]["target_share"], 0.25)

    def test_existing_weights_can_be_diagnosed_without_targets(self):
        # Before: "give targets" refusal although SKILL.md offers the design effect of existing weights.
        res = run_json(write_csv([["g", "wt"], ["A", "1"], ["B", "3"]]), "--base-weight", "wt")
        self.assertEqual(res["fit"]["method"], "none")
        self.assertAlmostEqual(res["weights"]["deff"], 2 * 10 / 16)
        self.assertAlmostEqual(res["weights"]["sum"], 4)
        self.assertEqual(run(write_csv([["g", "wt"], ["A", "1"]]), "--base-weight", "wt", "--trim-max", "2")
                         .returncode, 2)

    def test_excluded_rows_do_not_change_the_raking_total(self):
        # Before: one excluded base-weight row made every margin rake to the sample sum, not the count total.
        rows = [["g", "h", "bw"], ["A", "X", "1"], ["B", "Y", "1"], ["A", "Y", "1"], ["B", "X", "3"], ["A", "X", ""]]
        res = run_json(write_csv(rows), "--base-weight", "bw", "--allow-drop", "--target", "g:A=600;B=400",
                       "--target", "h:X=500;Y=500", "--history")
        later = [sum(h["margins"]) for h in res["fit"]["history"] if h["iteration"] > 1]
        for total in later:
            self.assertAlmostEqual(total, 1000)

    def test_trim_min_leaves_zero_target_respondents_alone(self):
        # Before: their 0 weights were floored and zeroed again for 50 cycles, then "cap not met".
        rows = [["g", "h"], ["A", "X"], ["B", "Y"], ["C", "X"], ["A", "Y"], ["B", "X"]]
        res = run_json(write_csv(rows), "--target", "g:A=60;B=40;C=0", "--target", "h:X=50;Y=50", "--trim-min", "0.5")
        self.assertTrue(res["fit"]["trim"]["cap_met"])
        self.assertEqual(res["fit"]["trim"]["cycles"], 0)

    def test_cli_values_are_validated(self):
        two = write_csv([["g"], ["A"], ["B"]])
        targets = write_csv([["variable", "category", "target"], ["g", "A", "50"], ["g", "B", "50"]])
        empty = write_csv([["variable", "category", "target"]])
        out_dir = tmpdir()
        for extra in (["--tolerance", "nan"], ["--trim-max", "inf"], ["--skip-rows", "-1"], ["--trim-cycles", "0"],
                      ["--targets", targets], ["--collapse", "G:A=a"], ["--out", out_dir, "--overwrite"]):
            proc = run(two, "--target", "g:A=50;B=50", *extra)
            self.assertEqual(proc.returncode, 2, extra)
            self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(run(two, "--targets", empty).returncode, 2)  # before: exit 0, "Raked on 0 variable(s)"

    def test_target_column_wins_over_unit_aliases(self):
        # Before: a cell file "count,g,target" took `count` as the target column.
        cells = write_csv([["g", "count", "target"], ["A", "5", "60"], ["B", "5", "40"]])
        proc = run(write_csv([["g", "count"], ["A", "5"], ["B", "5"]]), "--targets", cells, "--method", "cell")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_design_effect_of_equal_weights_is_never_below_one(self):
        # Before: n Σw² / (Σw)² gave 0.9999999999999999 for seven weights of 0.1.
        self.assertGreaterEqual(sw.weight_summary([0.1] * 7)["deff"], 1.0)

    def test_labels_with_pipes_do_not_break_the_markdown_table(self):
        proc = run(write_csv([["g", "q"], ["A", "yes|no"], ["B", "x"]]), "--target", "g:A=50;B=50", "--estimate", "q")
        self.assertIn("yes\\|no", proc.stdout)

CROSSTABS = SKILL.parent / "survey-crosstabs" / "scripts" / "survey_crosstabs.py"


class HandOffToCrosstabs(unittest.TestCase):
    """The documented hand-off: weighting writes the file, survey-crosstabs reads it with --weight. Runs only
    when the survey-crosstabs skill sits next to this one (as in the pack); each skill stays self-contained."""

    def setUp(self):
        if not CROSSTABS.exists():
            self.skipTest("survey-crosstabs is not installed next to this skill")

    def crosstabs(self, *args):
        proc = subprocess.run([sys.executable, "-B", str(CROSSTABS), *map(str, args), "--json"], capture_output=True,
                              text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_panel_bases_and_shares_agree(self):
        out = os.path.join(tmpdir(), "weighted.csv")
        res = run_json(FIXTURES / "panel.input.csv", "--targets", FIXTURES / "panel.targets.csv", "--out", out,
                       "--estimate", "q1")
        total = self.crosstabs(out, "--rows", "q1", "--weight", "weight")["tables"][0]
        self.assertEqual(total["columns"][0]["n"], 200)
        self.assertAlmostEqual(total["columns"][0]["n_eff"], res["weights"]["n_eff"], places=6)
        yes = next(r for r in total["rows"] if r["label"] == "Yes")["cells"][0]["pct"]
        want = next(c for c in res["estimates"][0]["categories"] if c["category"] == "Yes")["weighted_share"]
        self.assertAlmostEqual(yes, want, places=9)

    def test_excluded_rows_and_categories_carry_over(self):
        rows = [["g", "q", "bw"], ["Female", "Yes", "1"], ["Female", "YES", "1"], ["Male", "Yes", "2"],
                ["Male", "No", ""]]
        out = os.path.join(tmpdir(), "weighted.csv")
        res = run_json(write_csv(rows), "--target", "g:Female=50;Male=50", "--base-weight", "bw", "--allow-drop",
                       "--estimate", "q", "--out", out)
        with open(out, encoding="utf-8") as fh:
            self.assertEqual([r["weight"] for r in csv.DictReader(fh)][-1], "")  # excluded = blank weight
        table = self.crosstabs(out, "--rows", "q", "--weight", "weight", "--allow-drop")["tables"][0]
        self.assertEqual(table["columns"][0]["n"], res["input"]["weighted_rows"])
        got = {r["label"]: r["cells"][0]["pct"] for r in table["rows"] if r["kind"] == "category"}
        want = {c["category"]: c["weighted_share"] for c in res["estimates"][0]["categories"]}
        self.assertEqual(set(got), set(want))
        for k in want:
            self.assertAlmostEqual(got[k], want[k], places=9)


if __name__ == "__main__":
    unittest.main()
