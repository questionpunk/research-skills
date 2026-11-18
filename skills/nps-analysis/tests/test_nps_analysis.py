"""Tests for scripts/nps_analysis.py. Run from the skill folder: python3 -m unittest discover -s tests

Expected values come from fixtures/*.expected.json, which were worked out by hand (fixtures/README.md) or
taken from a published example, not from the script.
"""
import csv
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "nps_analysis.py"
POINTS = 0.01  # hand values are rounded to two decimals of a point


def run(*args):
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *map(str, args)], capture_output=True, text=True, check=False
    )


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
        cls.args = [FIXTURES / "basic.input.csv", "--segment-col", "plan", "--period-col", "quarter"]
        cls.out = run_json(*cls.args, "--compare", "smb", "enterprise", "--comment-col", "comment")
        cls.wald = run_json(*cls.args, "--compare", "smb", "enterprise", "--interval", "wald")

    def assert_group(self, got, want, method="adjusted_wald"):
        for key in ("n", "promoters", "passives", "detractors"):
            self.assertEqual(got[key], want[key], key)
        self.assertAlmostEqual(got["nps"], want["nps"], delta=POINTS)
        if method in want:
            self.assertAlmostEqual(got["ci_low"], want[method]["ci_low"], delta=POINTS)
            self.assertAlmostEqual(got["ci_high"], want[method]["ci_high"], delta=POINTS)

    def test_score_column_is_auto_detected_and_reported(self):
        self.assertEqual(self.out["input"]["score_col"], "nps_score")
        self.assertEqual(self.out["input"]["score_col_source"], "auto-detected")
        self.assertEqual(self.out["input"]["scale"], "0-10")

    def test_overall_nps_and_adjusted_wald_interval(self):
        self.assert_group(self.out["overall"], self.exp["overall"])

    def test_overall_wald_interval(self):
        self.assert_group(self.wald["overall"], self.exp["overall"], "wald")

    def test_overall_is_pooled_not_the_mean_of_segments(self):
        segments = self.out["segments"]
        mean_of_segments = sum(s["nps"] for s in segments) / len(segments)
        self.assertNotAlmostEqual(self.out["overall"]["nps"], mean_of_segments, delta=1)

    def test_segments(self):
        got = by_label(self.out["segments"])
        for name, want in self.exp["segments"].items():
            self.assert_group(got[name], want)

    def test_periods(self):
        got = by_label(self.out["periods"])
        for name, want in self.exp["periods"].items():
            self.assert_group(got[name], want)

    def test_two_segment_comparison_adjusted_wald(self):
        want = self.exp["smb_vs_enterprise"]
        got = next(c for c in self.out["comparisons"] if c["kind"] == "segment")
        self.assertAlmostEqual(got["difference"], want["difference"], delta=POINTS)
        aw = want["adjusted_wald"]
        self.assertAlmostEqual(got["difference_adjusted"], aw["difference_adjusted"], delta=POINTS)
        self.assertAlmostEqual(got["z"], aw["z"], delta=0.001)
        self.assertAlmostEqual(got["p_value"], aw["p_value"], delta=0.0001)
        self.assertAlmostEqual(got["ci_low"], aw["ci_low"], delta=POINTS)
        self.assertAlmostEqual(got["ci_high"], aw["ci_high"], delta=POINTS)
        self.assertTrue(got["significant"])
        self.assertEqual(got["verdict"], "significant")
        self.assertTrue(got["small_base"])

    def test_two_segment_comparison_wald(self):
        want = self.exp["smb_vs_enterprise"]["wald"]
        got = next(c for c in self.wald["comparisons"] if c["kind"] == "segment")
        self.assertAlmostEqual(got["z"], want["z"], delta=0.001)
        self.assertAlmostEqual(got["p_value"], want["p_value"], delta=0.0001)
        self.assertAlmostEqual(got["ci_low"], want["ci_low"], delta=POINTS)
        self.assertAlmostEqual(got["ci_high"], want["ci_high"], delta=POINTS)

    def test_trend_compares_consecutive_periods(self):
        want = self.exp["q3_vs_q2"]
        got = next(c for c in self.out["comparisons"] if c["kind"] == "trend")
        self.assertEqual((got["a"], got["b"]), ("2026-Q3", "2026-Q2"))
        self.assertAlmostEqual(got["difference"], want["difference"], delta=POINTS)
        self.assertAlmostEqual(got["z"], want["adjusted_wald"]["z"], delta=0.001)
        self.assertAlmostEqual(got["p_value"], want["adjusted_wald"]["p_value"], delta=0.0001)
        self.assertFalse(got["significant"])
        self.assertEqual(got["verdict"], "underpowered")  # not significant on a small base

    def test_not_significant_on_a_large_enough_base(self):
        out = run_json(*self.args, "--min-base", "10")
        got = next(c for c in out["comparisons"] if c["kind"] == "trend")
        self.assertEqual(got["verdict"], "not significant")

    def test_compare_periods_replaces_the_duplicate_trend_test(self):
        out = run_json(*self.args, "--compare-periods", "2026-Q2", "2026-Q3")
        self.assertEqual([c["kind"] for c in out["comparisons"]], ["period"])
        self.assertAlmostEqual(out["comparisons"][0]["difference"], 30.0, delta=POINTS)

    def test_small_base_and_untested_multiplicity_warnings(self):
        self.assertTrue(self.out["overall"]["small_base"])
        text = " ".join(self.out["warnings"])
        self.assertIn("Small base", text)
        self.assertIn("2 tests were run without a multiple-comparison adjustment", text)
        self.assertIn("independent samples", text)

    def test_min_base_is_configurable(self):
        out = run_json(FIXTURES / "basic.input.csv", "--min-base", "30")
        self.assertFalse(out["overall"]["small_base"])

    def test_comment_counts_have_denominators(self):
        self.assertEqual(
            {k: v for k, v in self.out["comments"].items() if k != "written_to"}, self.exp["comments"]
        )

    def test_comments_out_csv_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = pathlib.Path(tmp) / "comments.csv"
            json_path = pathlib.Path(tmp) / "comments.json"
            run_json(FIXTURES / "basic.input.csv", "--comment-col", "comment", "--comments-out", csv_path)
            run_json(
                FIXTURES / "basic.input.csv", "--comment-col", "comment", "--segment-col", "plan",
                "--comments-out", json_path,
            )
            with open(csv_path, newline="") as handle:
                rows = list(csv.DictReader(handle))
            payload = json.loads(json_path.read_text())
        self.assertEqual(len(rows), 13 + 8 + 10)
        self.assertEqual(rows[0]["group"], "detractor")
        self.assertTrue(all(r["comment"] for r in rows))
        self.assertTrue(all((int(r["score"]) <= 6) == (r["group"] == "detractor") for r in rows))
        self.assertEqual(payload["detractors"]["respondents"], 12)
        self.assertEqual(len(payload["detractors"]["comments"]), 10)
        self.assertIn(payload["promoters"]["comments"][0]["segment"], ("smb", "enterprise"))

    def test_readable_output(self):
        proc = run(*self.args, "--compare", "smb", "enterprise")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Overall", proc.stdout)
        self.assertIn("+15.0", proc.stdout)
        self.assertIn("-11.3 to +39.2", proc.stdout)
        self.assertIn("p = 0.0140", proc.stdout)

    def test_output_is_deterministic(self):
        first = run(*self.args, "--pairwise", "--json").stdout
        self.assertEqual(first, run(*self.args, "--pairwise", "--json").stdout)


class PublishedExampleTest(unittest.TestCase):
    """Lewis and Sauro (MeasuringU, 2021): GoToMeeting vs WebEx, 90% confidence, published to 2-3 decimals."""

    @classmethod
    def setUpClass(cls):
        cls.exp = expected("measuringu_gtm_webex")
        cls.out = run_json(
            FIXTURES / "measuringu_gtm_webex.input.csv", "--segment-col", "product",
            "--compare", "GoToMeeting", "WebEx", "--confidence", cls.exp["confidence"],
        )

    def test_intervals_match_the_published_table(self):
        got = by_label(self.out["segments"])
        for name in ("GoToMeeting", "WebEx"):
            want = self.exp[name]
            for key in ("n", "promoters", "passives", "detractors"):
                self.assertEqual(got[name][key], want[key])
            for key in ("nps", "nps_adjusted", "ci_low", "ci_high"):
                self.assertAlmostEqual(got[name][key] / 100, want[key], delta=0.005, msg=f"{name} {key}")

    def test_significance_test_matches_the_published_result(self):
        want = self.exp["difference"]
        got = self.out["comparisons"][0]
        self.assertAlmostEqual(got["difference_adjusted"] / 100, want["difference_adjusted"], delta=0.005)
        self.assertAlmostEqual(got["se_difference"] / 100, want["se"], delta=0.0005)
        self.assertAlmostEqual(got["z"], want["z"], delta=0.0005)
        self.assertAlmostEqual(got["p_value"], want["p_value"], delta=0.005)
        self.assertAlmostEqual(got["ci_low"] / 100, want["ci_low"], delta=0.005)
        self.assertAlmostEqual(got["ci_high"] / 100, want["ci_high"], delta=0.005)


class PairwiseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exp = expected("three_segments")
        cls.args = [FIXTURES / "three_segments.input.csv", "--segment-col", "tier", "--pairwise"]

    def p_values(self, out, key):
        return {f"{c['a']}|{c['b']}": c[key] for c in out["comparisons"]}

    def test_all_pairs_unadjusted_with_a_warning(self):
        out = run_json(*self.args)
        got = self.p_values(out, "p_value")
        self.assertEqual(set(got), set(self.exp["p_values"]))
        for pair, want in self.exp["p_values"].items():
            self.assertAlmostEqual(got[pair], want, delta=0.00001)
        self.assertEqual(out["tests_run"], 3)
        self.assertTrue(any("3 tests were run without" in w for w in out["warnings"]))

    def test_bonferroni(self):
        out = run_json(*self.args, "--adjust", "bonferroni")
        got = self.p_values(out, "p_adjusted")
        for pair, want in self.exp["bonferroni"].items():
            self.assertAlmostEqual(got[pair], want, delta=0.00001)
        self.assertFalse(any("without a multiple-comparison" in w for w in out["warnings"]))

    def test_holm(self):
        out = run_json(*self.args, "--adjust", "holm")
        got = self.p_values(out, "p_adjusted")
        for pair, want in self.exp["holm"].items():
            self.assertAlmostEqual(got[pair], want, delta=0.00001)
        verdicts = {f"{c['a']}|{c['b']}": c["significant"] for c in out["comparisons"]}
        self.assertEqual(verdicts, {"free|pro": True, "free|team": False, "pro|team": False})


class EdgeCaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exp = expected("edge_cases")

    def test_all_promoters_adjusted_wald_keeps_a_real_interval(self):
        want = self.exp["all_promoters"]
        full = run_json(FIXTURES / "all_promoters.input.csv")  # no 0 in a small sample: a warning, not a stop
        self.assertTrue(any("No respondent chose 0" in w for w in full["warnings"]))
        out = full["overall"]
        self.assertEqual(out["n"], want["n"])
        self.assertAlmostEqual(out["nps"], want["nps"], delta=POINTS)
        self.assertAlmostEqual(out["ci_low"], want["adjusted_wald"]["ci_low"], delta=POINTS)
        self.assertEqual(out["ci_high"], 100.0)  # clipped at the top of the scale

    def test_all_promoters_wald_has_zero_width_and_says_so(self):
        out = run_json(FIXTURES / "all_promoters.input.csv", "--scale", "0-10", "--interval", "wald")["overall"]
        self.assertEqual((out["ci_low"], out["ci_high"]), (100.0, 100.0))
        self.assertIn("variance is 0", out["note"])

    def test_zero_variance_on_both_sides_is_not_tested(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "zero.csv"
            path.write_text("nps,team\n10,a\n9,a\n0,b\n3,b\n")
            out = run_json(path, "--segment-col", "team", "--compare", "a", "b", "--interval", "wald")
        self.assertFalse(out["comparisons"][0]["tested"])
        self.assertIn("undefined", out["comparisons"][0]["note"])

    def test_single_response(self):
        want = self.exp["single_response"]
        out = run_json(FIXTURES / "single_response.input.csv")
        self.assertEqual(out["overall"]["n"], 1)
        self.assertAlmostEqual(out["overall"]["nps"], want["nps"], delta=POINTS)
        self.assertAlmostEqual(out["overall"]["ci_low"], want["adjusted_wald"]["ci_low"], delta=POINTS)
        self.assertAlmostEqual(out["overall"]["ci_high"], want["adjusted_wald"]["ci_high"], delta=POINTS)
        self.assertTrue(out["overall"]["small_base"])

    def test_empty_segment_is_reported_and_left_out_of_tests(self):
        want = self.exp["empty_segment"]
        out = run_json(FIXTURES / "empty_segment.input.csv", "--segment-col", "team", "--pairwise")
        got = by_label(out["segments"])
        self.assertEqual(got["finance"]["n"], 0)
        self.assertIsNone(got["finance"]["nps"])
        self.assertAlmostEqual(got["sales"]["nps"], want["sales"]["nps"], delta=POINTS)
        self.assertAlmostEqual(got["support"]["nps"], want["support"]["nps"], delta=POINTS)
        self.assertEqual([(c["a"], c["b"]) for c in out["comparisons"]], [("sales", "support")])
        self.assertTrue(any("finance: no valid scores" in w for w in out["warnings"]))

    def test_comparing_an_empty_or_unknown_segment_fails(self):
        base = [FIXTURES / "empty_segment.input.csv", "--segment-col", "team", "--compare", "sales"]
        empty = run(*base, "finance")
        self.assertEqual(empty.returncode, 2)
        self.assertIn("no valid scores", empty.stderr)
        unknown = run(*base, "marketing")
        self.assertEqual(unknown.returncode, 2)
        self.assertIn("not found", unknown.stderr)

    def test_invalid_scores_are_excluded_and_counted(self):
        want = self.exp["dirty"]
        out = run_json(FIXTURES / "dirty.input.csv")
        self.assertEqual(out["input"]["rows_total"], want["rows_total"])
        self.assertEqual(out["input"]["rows_valid"], want["rows_valid"])
        for reason, count in want["excluded"].items():
            self.assertEqual(out["input"]["excluded"][reason], count, reason)
        self.assertAlmostEqual(out["overall"]["nps"], want["nps"], delta=POINTS)
        self.assertEqual(
            [(e["row"], e["reason"]) for e in out["input"]["excluded_examples"]],
            [(8, "non_numeric"), (9, "non_integer"), (10, "out_of_range"), (11, "out_of_range")],
        )
        self.assertTrue(any("5 of 12 rows" in w for w in out["warnings"]))
        readable = run(FIXTURES / "dirty.input.csv").stdout
        self.assertIn("5 excluded", readable)
        self.assertIn("'7.5' (non integer)", readable)

    def test_iso_dates_are_bucketed_and_bad_dates_counted(self):
        out = run_json(FIXTURES / "dates.input.csv", "--period-col", "submitted_at", "--period-grain", "quarter")
        self.assertEqual([p["label"] for p in out["periods"]], ["2026-Q1", "2026-Q2"])
        self.assertEqual([p["n"] for p in out["periods"]], [3, 3])
        self.assertEqual(out["input"]["excluded"]["bad_period"], 1)
        months = run_json(FIXTURES / "dates.input.csv", "--period-col", "submitted_at", "--period-grain", "month")
        self.assertEqual(months["periods"][0]["label"], "2026-01")


class ScaleCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exp = expected("edge_cases")

    def test_one_to_five_is_refused_without_a_flag(self):
        proc = run(FIXTURES / "scale_1_5.input.csv")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("1-5 scale", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_one_to_five_with_the_flag_uses_the_top_box_mapping_and_warns(self):
        want = self.exp["scale_1_5"]
        out = run_json(FIXTURES / "scale_1_5.input.csv", "--scale", "1-5")
        for key in ("promoters", "passives", "detractors"):
            self.assertEqual(out["overall"][key], want[key])
        self.assertAlmostEqual(out["overall"]["nps"], want["nps"], delta=POINTS)
        self.assertTrue(any("not the Net Promoter standard" in w for w in out["warnings"]))

    def test_no_zero_in_a_small_sample_warns_and_computes(self):
        out = run_json(FIXTURES / "scale_1_10.input.csv")
        self.assertEqual(out["input"]["scale"], "0-10")
        self.assertTrue(any("re-run with --scale 1-10" in w for w in out["warnings"]))

    def test_no_zero_and_a_minimum_of_one_in_a_large_sample_is_refused(self):
        proc = run(FIXTURES / "scale_1_10_large.input.csv")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("none of 200 respondents chose 0", proc.stderr)
        self.assertIn("--scale 1-10", proc.stderr)
        self.assertEqual(run_json(FIXTURES / "scale_1_10_large.input.csv", "--scale", "1-10")["overall"]["n"], 200)

    def test_one_to_ten_with_the_flag(self):
        want = self.exp["scale_1_10"]
        out = run_json(FIXTURES / "scale_1_10.input.csv", "--scale", "1-10")
        for key in ("promoters", "passives", "detractors"):
            self.assertEqual(out["overall"][key], want[key])
        self.assertAlmostEqual(out["overall"]["nps"], want["nps"], delta=POINTS)
        self.assertEqual(out["input"]["scale"], "1-10")

    def test_zero_is_out_of_range_on_a_one_to_ten_scale(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "mixed.csv"
            path.write_text("score\n0\n10\n9\n3\n")
            out = run_json(path, "--scale", "1-10")
        self.assertEqual(out["input"]["excluded"]["out_of_range"], 1)
        self.assertEqual(out["overall"]["n"], 3)

    def test_confirmed_zero_to_ten_without_zeros_is_noted(self):
        out = run_json(FIXTURES / "scale_1_10.input.csv", "--scale", "0-10")
        self.assertTrue(any("confirmed with --scale" in w for w in out["warnings"]))


class BadInputTest(unittest.TestCase):
    def write(self, tmp, text):
        path = pathlib.Path(tmp) / "input.csv"
        path.write_text(text)
        return path

    def assert_fails(self, proc, message):
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn(message, proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_missing_file(self):
        self.assert_fails(run(FIXTURES / "nope.csv"), "file not found")

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_fails(run(self.write(tmp, "")), "no header row")

    def test_no_score_column_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_fails(run(self.write(tmp, "id,answer\n1,9\n")), "Pass --score-col")

    def test_ambiguous_score_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "score,rating\n9,4\n0,1\n")
            self.assert_fails(run(path), "more than one column")
            self.assertEqual(run_json(path, "--score-col", "score")["input"]["score_col_source"], "given")

    def test_nps_named_column_wins_over_generic_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "csat_score,nps\n4,9\n5,0\n")
            self.assertEqual(run_json(path)["input"]["score_col"], "nps")

    def test_unknown_columns(self):
        fixture = FIXTURES / "basic.input.csv"
        self.assert_fails(run(fixture, "--score-col", "nope"), "is not a column")
        self.assert_fails(run(fixture, "--segment-col", "nope"), "is not a column")

    def test_no_valid_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_fails(run(self.write(tmp, "nps\nhigh\n12\n\n")), "no whole-number scores")

    def test_options_that_need_a_column(self):
        fixture = FIXTURES / "basic.input.csv"
        self.assert_fails(run(fixture, "--pairwise"), "--pairwise needs --segment-col")
        self.assert_fails(run(fixture, "--compare", "a", "b"), "--compare needs --segment-col")
        self.assert_fails(run(fixture, "--compare-periods", "a", "b"), "needs --period-col")
        self.assert_fails(run(fixture, "--comments-out", "x.csv"), "needs --comment-col")
        self.assert_fails(
            run(fixture, "--comment-col", "comment", "--comments-out", "x.txt"), "must end in .json or .csv"
        )

    def test_bad_confidence(self):
        self.assert_fails(run(FIXTURES / "basic.input.csv", "--confidence", "95"), "between 0 and 1")


class CountsInputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.basic = expected("basic")
        cls.exp = expected("counts_cells")
        cls.cells = [FIXTURES / "counts_cells.input.csv", "--segment-col", "plan", "--period-col", "quarter"]

    def test_three_counts_match_the_respondent_level_result(self):
        want = self.basic["overall"]
        out = run_json("--counts", "18,10,12")
        self.assertEqual(out["input"]["mode"], "counts")
        self.assertAlmostEqual(out["overall"]["nps"], want["nps"], delta=POINTS)
        self.assertAlmostEqual(out["overall"]["ci_low"], want["adjusted_wald"]["ci_low"], delta=POINTS)
        self.assertAlmostEqual(out["overall"]["ci_high"], want["adjusted_wald"]["ci_high"], delta=POINTS)
        self.assertNotIn("score_distribution", out)

    def test_eleven_counts_give_the_same_result_and_a_distribution(self):
        out = run_json("--counts", self.exp["eleven_counts"])
        self.assertEqual((out["overall"]["promoters"], out["overall"]["passives"], out["overall"]["detractors"]), (18, 10, 12))
        self.assertAlmostEqual(out["overall"]["nps"], 15.0, delta=POINTS)
        self.assertEqual(out["score_distribution"]["10"], 10)
        self.assertEqual(out["score_distribution"]["1"], 0)

    def test_counts_csv_with_segment_and_period(self):
        out = run_json(*self.cells, "--compare", "smb", "enterprise")
        self.assertEqual(out["input"]["mode"], "counts-csv")
        self.assertEqual(out["input"]["count_columns"]["passive"], "Neutrals")
        segments, periods = by_label(out["segments"]), by_label(out["periods"])
        for name, want in self.basic["segments"].items():
            self.assertEqual(segments[name]["n"], want["n"])
            self.assertAlmostEqual(segments[name]["nps"], want["nps"], delta=POINTS)
            self.assertAlmostEqual(segments[name]["ci_low"], want["adjusted_wald"]["ci_low"], delta=POINTS)
        for name, want in self.basic["periods"].items():
            self.assertAlmostEqual(periods[name]["nps"], want["nps"], delta=POINTS)
        got = next(c for c in out["comparisons"] if c["kind"] == "segment")
        self.assertAlmostEqual(got["p_value"], self.basic["smb_vs_enterprise"]["adjusted_wald"]["p_value"], delta=0.0001)

    def test_counts_csv_without_group_columns_adds_rows_and_says_so(self):
        out = run_json(FIXTURES / "counts_cells.input.csv")
        self.assertEqual(out["overall"]["n"], 40)
        self.assertTrue(any("all rows were added together" in w for w in out["warnings"]))

    def test_bad_counts(self):
        for args, message in (
            (["--counts", "18,10"], "3 numbers"),
            (["--counts", "18,x,12"], "not a whole, non-negative count"),
            (["--counts", "0,0,0"], "adds up to 0"),
            (["--counts", "18,10,12", "--segment-col", "plan"], "cannot be used with --counts"),
            (["--counts", "18,10,12", "--comment-col", "c"], "needs one row per respondent"),
            (["--counts", "18,10,12", "--scale", "1-5"], "does not apply"),
            ([FIXTURES / "basic.input.csv", "--counts", "18,10,12"], "not both"),
            ([FIXTURES / "counts_bad.input.csv", "--segment-col", "plan"], "row 3, column promoters"),
            ([], "give a CSV file"),
        ):
            proc = run(*args)
            self.assertEqual(proc.returncode, 2, args)
            self.assertIn(message, proc.stderr)

    def test_mix_shift_decomposition(self):
        want = self.exp["mix_shift"]
        for args in (self.cells, [FIXTURES / "basic.input.csv", "--segment-col", "plan", "--period-col", "quarter"]):
            got = run_json(*args)["mix_shift"]
            self.assertEqual((got["earlier"], got["later"]), (want["earlier"], want["later"]))
            for key in ("change", "within_segments", "mix"):
                self.assertAlmostEqual(got[key], want[key], delta=POINTS)
            self.assertAlmostEqual(got["within_segments"] + got["mix"], got["change"], delta=0.001)
            for row in got["segments"]:
                self.assertAlmostEqual(row["within"], want["segments"][row["segment"]]["within"], delta=POINTS)
                self.assertAlmostEqual(row["mix"], want["segments"][row["segment"]]["mix"], delta=POINTS)

    def test_mix_shift_with_a_segment_in_one_period_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "cells.csv"
            path.write_text("seg,period,promoters,passives,detractors\na,p1,5,0,5\na,p2,5,0,5\nb,p2,10,0,0\n")
            got = run_json(path, "--segment-col", "seg", "--period-col", "period")["mix_shift"]
        # p1: only a, NPS 0. p2: a 0 (share 0.5), b +100 (share 0.5) -> +50. Nothing changed within a segment.
        self.assertAlmostEqual(got["change"], 50.0, delta=POINTS)
        self.assertAlmostEqual(got["within_segments"], 0.0, delta=POINTS)
        self.assertAlmostEqual(got["mix"], 50.0, delta=POINTS)

    def test_n_needed_for_a_ten_point_margin(self):
        want = self.exp["n_for_10_point_margin"]
        self.assertEqual(run_json("--counts", "18,10,12")["overall"]["n_for_10_point_margin"], want["adjusted_wald"])
        self.assertEqual(
            run_json("--counts", "18,10,12", "--interval", "wald")["overall"]["n_for_10_point_margin"], want["wald"]
        )
        self.assertNotIn("n_for_10_point_margin", run_json("--counts", "61,30,16")["overall"])

    def test_response_rate(self):
        out = run_json(FIXTURES / "basic.input.csv", "--invited", "200")
        self.assertEqual(out["response"], {"invited": 200, "valid": 40, "response_rate": 20.0})
        self.assertTrue(any("sampling error only" in w for w in out["warnings"]))
        self.assertEqual(run(FIXTURES / "basic.input.csv", "--invited", "10").returncode, 2)

    def test_score_distribution_from_rows(self):
        dist = run_json(FIXTURES / "basic.input.csv")["score_distribution"]
        self.assertEqual(sum(dist.values()), 40)
        self.assertEqual(dist["9"] + dist["10"], 18)
        self.assertEqual(list(dist), [str(i) for i in range(11)])

    def test_readable_tables_show_promoter_and_detractor_shares(self):
        text = run(*self.cells).stdout
        self.assertIn("Prom%", text)
        self.assertIn("Detr%", text)
        self.assertIn("Mix shift, 2026-Q2 to 2026-Q3: change +30.0 = within segments +26.7 + segment mix +3.3", text)
        self.assertIn("cannot detect that without --id-col", text)


class BenchmarkTest(unittest.TestCase):
    """Lewis and Sauro (MeasuringU, 2021): 61 promoters, 30 passives, 16 detractors against three benchmarks."""

    @classmethod
    def setUpClass(cls):
        cls.exp = expected("benchmark_measuringu")

    def test_published_one_tailed_tests(self):
        for want in self.exp["tests"]:
            out = run_json("--counts", self.exp["counts"], "--benchmark", want["benchmark"], "--tail", "one")
            got = out["benchmark"]
            self.assertEqual(out["overall"]["n"], self.exp["n"])
            self.assertAlmostEqual(got["nps_adjusted"] / 100, self.exp["nps_adjusted"], delta=0.005)
            self.assertAlmostEqual(got["se"] / 100, self.exp["se"], delta=0.0005)
            self.assertAlmostEqual(got["z"], want["z"], delta=0.0005)
            self.assertAlmostEqual(got["p_value"], want["p_value"], delta=0.0006)
            self.assertEqual(got["significant"], want["significant"])
            self.assertAlmostEqual(got["lower_bound"] / 100, self.exp["one_sided_lower_bound_95"], delta=0.005)

    def test_two_tailed_is_the_default_and_doubles_the_p_value(self):
        want = self.exp["two_tailed_hand"]
        got = run_json("--counts", self.exp["counts"], "--benchmark", want["benchmark"])["benchmark"]
        self.assertEqual(got["tail"], "two")
        self.assertAlmostEqual(got["p_value"], want["p_value"], delta=0.0001)
        self.assertNotIn("lower_bound", got)

    def test_one_tailed_below_the_benchmark_is_not_significant(self):
        got = run_json("--counts", "16,30,61", "--benchmark", "0", "--tail", "one")["benchmark"]
        self.assertLess(got["z"], 0)
        self.assertGreater(got["p_value"], 0.99)
        self.assertFalse(got["significant"])

    def test_wald_benchmark_against_zero(self):
        want = expected("counts_cells")["wald_benchmark_0"]
        got = run_json("--counts", "18,10,12", "--benchmark", "0", "--interval", "wald")["benchmark"]
        self.assertAlmostEqual(got["z"], want["z"], delta=0.0005)
        self.assertAlmostEqual(got["p_value"], want["p_value"], delta=0.0001)

    def test_bad_benchmark_arguments(self):
        self.assertIn("-100 to 100", run("--counts", "1,1,1", "--benchmark", "0.3x").stderr + run("--counts", "1,1,1", "--benchmark", "300").stderr)
        self.assertIn("--tail needs --benchmark", run("--counts", "1,1,1", "--tail", "one").stderr)

    def test_readable_benchmark_line(self):
        text = run("--counts", self.exp["counts"], "--benchmark", "30", "--tail", "one").stdout
        self.assertIn("z = 1.548, p = 0.0608 (not significant at 95%)", text)


class WelchTest(unittest.TestCase):
    def test_t_distribution_against_table_values(self):
        sys.path.insert(0, str(SCRIPT.parent))
        sys.dont_write_bytecode = True
        import nps_analysis

        # NIST/SEMATECH e-Handbook, table of upper critical values of Student's t (two-sided 0.05 and 0.10).
        for t_value, df, p_two_sided in ((2.228, 10, 0.05), (2.086, 20, 0.05), (2.000, 60, 0.05), (1.690, 35, 0.10)):
            self.assertAlmostEqual(nps_analysis.t_two_sided_p(t_value, df), p_two_sided, delta=0.0002)
        self.assertAlmostEqual(nps_analysis.t_critical(0.95, 9), 2.262, delta=0.0005)
        self.assertAlmostEqual(nps_analysis.t_critical(0.90, 30), 1.697, delta=0.0005)

    def test_welch_on_the_published_data(self):
        want = expected("measuringu_gtm_webex")["welch"]
        out = run_json(
            FIXTURES / "measuringu_gtm_webex.input.csv", "--segment-col", "product",
            "--compare", "GoToMeeting", "WebEx", "--test", "welch",
        )
        got = out["comparisons"][0]
        self.assertEqual(got["test"], "welch")
        self.assertAlmostEqual(got["t"], want["t"], delta=0.001)
        self.assertAlmostEqual(got["df"], want["df"], delta=0.01)
        self.assertAlmostEqual(got["se_difference"], want["se"], delta=0.01)
        self.assertAlmostEqual(got["p_value"], want["p_value_published_rounded"], delta=0.005)
        self.assertNotIn("difference_adjusted", got)
        self.assertIn("Welch t-test", run(
            FIXTURES / "measuringu_gtm_webex.input.csv", "--segment-col", "product", "--pairwise", "--test", "welch"
        ).stdout)

    def test_welch_needs_two_responses_per_side(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "tiny.csv"
            path.write_text("nps,team\n10,a\n0,b\n3,b\n")
            out = run_json(path, "--segment-col", "team", "--compare", "a", "b", "--test", "welch")
        self.assertFalse(out["comparisons"][0]["tested"])


class PairedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exp = expected("paired")
        cls.args = [FIXTURES / "paired.input.csv", "--id-col", "user_id", "--period-col", "wave"]

    def test_shared_respondents_withhold_the_independent_test(self):
        out = run_json(*self.args)
        got = out["comparisons"][0]
        self.assertFalse(got["tested"])
        self.assertEqual(got["shared_respondents"], 10)
        self.assertIn("not independent", got["note"])
        self.assertEqual(out["tests_run"], 0)

    def test_paired_change(self):
        got = run_json(*self.args, "--compare-periods", "wave1", "wave2", "--paired")["paired"]
        for key in ("n_pairs", "only_earlier", "only_later", "moved_up", "unchanged", "moved_down", "df"):
            self.assertEqual(got[key], self.exp[key], key)
        for key in ("mean_change", "sd", "se", "ci_low", "ci_high"):
            self.assertAlmostEqual(got[key], self.exp[key], delta=0.01, msg=key)
        self.assertAlmostEqual(got["t"], self.exp["t"], delta=0.001)
        low, high = self.exp["p_value_between"]
        self.assertTrue(low < got["p_value"] < high)
        self.assertFalse(got["significant"])

    def test_paired_needs_its_columns_and_enough_pairs(self):
        self.assertIn("--paired needs", run(FIXTURES / "basic.input.csv", "--paired").stderr)
        out = run_json(
            FIXTURES / "basic.input.csv", "--id-col", "respondent_id", "--period-col", "quarter",
            "--compare-periods", "2026-Q2", "2026-Q3", "--paired",
        )
        self.assertFalse(out["paired"]["tested"])
        self.assertEqual(out["paired"]["n_pairs"], 0)
        self.assertTrue(out["comparisons"][0]["tested"])  # no shared ids: the independent test runs


class ThemeTest(unittest.TestCase):
    def test_theme_table(self):
        want = expected("themes")
        out = run_json(FIXTURES / "themes.input.csv", "--theme-col", "themes")
        got = {t["theme"]: t for t in out["themes"]}
        self.assertEqual(set(got), {"price", "support", "ease of use"})
        for name in got:
            self.assertEqual(got[name]["coded_respondents"], want["coded_respondents"])
            self.assertEqual(got[name]["mentions"], want[name]["mentions"])
            self.assertAlmostEqual(got[name]["mentioned"]["nps"], want[name]["nps_mentioned"], delta=POINTS)
            self.assertAlmostEqual(got[name]["rest"]["nps"], want[name]["nps_rest"], delta=POINTS)
        price = got["price"]
        self.assertAlmostEqual(price["mentioned"]["ci_low"], want["price"]["ci_low"], delta=POINTS)
        self.assertAlmostEqual(price["mentioned"]["ci_high"], want["price"]["ci_high"], delta=POINTS)
        self.assertAlmostEqual(price["difference"], want["price"]["difference"], delta=POINTS)
        self.assertAlmostEqual(price["ci_low"], want["price"]["diff_ci_low"], delta=POINTS)
        self.assertAlmostEqual(price["ci_high"], want["price"]["diff_ci_high"], delta=POINTS)
        self.assertTrue(any("association" in w for w in out["warnings"]))


if __name__ == "__main__":
    unittest.main()
