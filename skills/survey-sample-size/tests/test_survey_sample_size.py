"""Tests for scripts/survey_sample_size.py. Run from the skill folder: python3 -m unittest discover -s tests"""
import json
import pathlib
import subprocess
import sys
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "survey_sample_size.py"


def run(*argv):
    return subprocess.run([sys.executable, "-B", str(SCRIPT)] + list(argv), capture_output=True, text=True)


def result(*argv):
    proc = run(*argv, "--json")
    if proc.returncode != 0:
        raise AssertionError("exit %d: %s" % (proc.returncode, proc.stderr))
    return json.loads(proc.stdout)


class FixtureTest(unittest.TestCase):
    """Every case in fixtures/cases.json; the expected values are derived in fixtures/README.md."""

    def test_fixtures_match_expected(self):
        cases = json.loads((FIXTURES / "cases.json").read_text())["cases"]
        self.assertGreaterEqual(len(cases), 75)
        for case in cases:
            with self.subTest(case=case["id"]):
                got = result(*case["argv"])["result"]
                for key, expected in case["expected"].items():
                    value = got
                    for part in key.split("."):
                        self.assertIn(part, value)
                        value = value[part]
                    if isinstance(expected, float):
                        self.assertAlmostEqual(value, expected, places=case.get("places", 3))
                    else:
                        self.assertEqual(value, expected)

    def test_every_fixture_is_documented(self):
        readme = (FIXTURES / "README.md").read_text()
        for case in json.loads((FIXTURES / "cases.json").read_text())["cases"]:
            self.assertIn("| %s |" % case["id"], readme)


class OutputTest(unittest.TestCase):
    def test_json_shape_is_fixed(self):
        report = result("proportion", "--margin", "0.05")
        self.assertEqual(list(report), ["subcommand", "inputs", "result", "statement", "assumptions", "notes", "formula", "sources"])

    def test_defaults_are_stated(self):
        text = run("proportion", "--margin", "0.05").stdout
        self.assertIn("p = 0.5", text)
        self.assertIn("95%", text)
        self.assertIn("Simple random sample", text)
        self.assertIn("Responses needed: 385", text)

    def test_rules_of_thumb_are_labelled(self):
        for argv in (["maxdiff", "--items", "20"], ["conjoint", "--tasks", "10", "--alternatives", "3", "--levels", "3,4"]):
            report = result(*argv)
            self.assertIs(report["result"]["rule_of_thumb"], True)
            self.assertIn("not a power calculation", report["assumptions"][0])

    def test_output_is_deterministic(self):
        argv = ["compare", "--p1", "0.5", "--n", "388"]
        self.assertEqual(run(*argv).stdout, run(*argv).stdout)


class RoundingTest(unittest.TestCase):
    def test_n_is_rounded_up_never_to_nearest(self):
        # 384.15 and 322.39 would both round down to the nearest integer.
        self.assertEqual(result("proportion", "--margin", "0.05")["result"]["n_required"], 385)
        self.assertEqual(result("proportion", "--margin", "0.05", "--population", "2000")["result"]["n_required"], 323)

    def test_exact_integer_is_not_bumped(self):
        self.assertEqual(result("invites", "--completes", "100", "--response-rate", "0.1")["result"]["invitations"], 1000)
        self.assertEqual(result("subgroups", "--share", "0.25", "--min-base", "200")["result"]["n_total"], 800)

    def test_required_n_is_sufficient_for_its_own_margin(self):
        for margin in ("0.02", "0.04", "0.07", "0.1"):
            n = result("proportion", "--margin", margin)["result"]["n_required"]
            back = result("proportion", "--n", str(n))["result"]["margin_of_error"]
            self.assertLessEqual(back, float(margin) + 1e-4)


class PitfallTest(unittest.TestCase):
    def test_fpc_is_negligible_for_a_large_population(self):
        report = result("proportion", "--margin", "0.05", "--population", "10000000")
        self.assertEqual(report["result"]["n_required"], 385)
        self.assertTrue(any("barely changes" in note for note in report["notes"]))

    def test_small_population_becomes_a_census(self):
        report = result("proportion", "--margin", "0.01", "--population", "50", "--deff", "2")
        self.assertEqual(report["result"]["n_required"], 50)
        self.assertTrue(any("census" in note for note in report["notes"]))

    def test_design_effect_widens_the_margin(self):
        plain = result("proportion", "--n", "400")["result"]["margin_of_error"]
        weighted = result("proportion", "--n", "400", "--deff", "2")["result"]["margin_of_error"]
        self.assertAlmostEqual(weighted, 0.0693, places=3)  # 0.049 x sqrt(2)
        self.assertGreater(weighted, plain)

    def test_small_count_gets_an_interval_not_a_symmetric_margin(self):
        report = result("proportion", "--n", "80", "--p", "0.05")  # 4 expected responses
        self.assertEqual(report["result"]["interval_method"], "wilson")
        self.assertNotIn("margin_of_error", report["result"])
        low, high = report["result"]["interval_low"], report["result"]["interval_high"]
        self.assertGreater(high - 0.05, 0.05 - low)  # asymmetric
        self.assertTrue(any("Wilson" in note for note in report["notes"]))

    def test_zero_count_interval_starts_at_zero(self):
        got = result("proportion", "--n", "20", "--x", "0")["result"]
        self.assertEqual(got["interval_low"], 0.0)
        self.assertAlmostEqual(got["interval_high"], 0.1611, places=3)  # z^2/(n + z^2) = 3.8416/23.8416

    def test_bonferroni_is_reported_as_conservative(self):
        report = result("compare", "--p1", "0.5", "--p2", "0.6", "--comparisons", "3")
        self.assertTrue(any("conservative" in line for line in report["assumptions"]))

    def test_paired_designs_are_named_as_out_of_scope(self):
        report = result("compare", "--p1", "0.5", "--p2", "0.6")
        self.assertTrue(any("paired" in line for line in report["assumptions"]))

    def test_power_output_warns_against_post_hoc_use(self):
        report = result("compare", "--p1", "0.5", "--p2", "0.6", "--n", "100")
        self.assertTrue(any("observed difference" in note for note in report["notes"]))

    def test_power_rises_with_n_and_reaches_target_at_required_n(self):
        powers = [result("compare", "--p1", "0.3", "--p2", "0.4", "--n", str(n))["result"]["power_at_n"] for n in (100, 200, 400)]
        self.assertEqual(powers, sorted(powers))
        needed = result("compare", "--p1", "0.3", "--p2", "0.4")["result"]["n_per_group"]
        for method in ("pooled", "unpooled", "baseline", "arcsine"):
            needed = result("compare", "--p1", "0.3", "--p2", "0.4", "--variance", method)["result"]["n_per_group"]
            at = result("compare", "--p1", "0.3", "--p2", "0.4", "--variance", method, "--n", str(needed))["result"]
            self.assertGreaterEqual(at["power_at_n"], 0.8)
            self.assertTrue(at["sufficient"])

    def test_ratio_one_equals_the_default_and_n2_equals_ratio(self):
        default = result("compare", "--p1", "0.35", "--p2", "0.5")["result"]
        self.assertEqual(result("compare", "--p1", "0.35", "--p2", "0.5", "--ratio", "1")["result"], default)
        by_ratio = result("compare", "--p1", "0.35", "--p2", "0.5", "--n", "100", "--ratio", "2")["result"]
        by_n2 = result("compare", "--p1", "0.35", "--p2", "0.5", "--n", "100", "--n2", "200")["result"]
        self.assertEqual(by_ratio["power_at_n"], by_n2["power_at_n"])

    def test_unequal_groups_need_more_in_total(self):
        equal = result("compare", "--p1", "0.35", "--p2", "0.5")["result"]["n_total"]
        unequal = result("compare", "--p1", "0.35", "--p2", "0.5", "--ratio", "2")["result"]["n_total"]
        self.assertGreater(unequal, equal)

    def test_quota_table_has_a_row_per_named_subgroup(self):
        got = result("subgroups", "--share", "A=0.50", "B=0.35", "C=0.15", "--margin", "0.10")["result"]
        rows = {row["subgroup"]: row for row in got["quota_table"]}
        self.assertEqual([rows[k]["required_total"] for k in "ABC"], [194, 278, 647])
        self.assertAlmostEqual(rows["A"]["expected_n"], 323.5, places=1)
        self.assertAlmostEqual(rows["B"]["expected_n"], 226.45, delta=0.06)
        self.assertAlmostEqual(rows["C"]["expected_n"], 97.05, delta=0.06)
        self.assertAlmostEqual(rows["A"]["margin_of_error"], 0.0545, places=3)
        self.assertAlmostEqual(rows["B"]["margin_of_error"], 0.0651, places=3)
        self.assertAlmostEqual(rows["C"]["margin_of_error"], 0.0995, places=3)

    def test_sensitivity_tables(self):
        rows = result("proportion", "--margin", "0.05", "--table")["result"]["table"]
        self.assertEqual([(r["margin"], r["n_required"]) for r in rows],
                         [(0.01, 9604), (0.02, 2401), (0.03, 1068), (0.04, 601), (0.05, 385), (0.07, 196), (0.1, 97)])
        rows = result("proportion", "--n", "80", "--table")["result"]["table"]
        self.assertEqual([r["n"] for r in rows], [40, 80, 160, 320])
        self.assertAlmostEqual(rows[0]["margin_of_error"], 0.1549, places=3)  # 1.96 x sqrt(0.25/40)
        self.assertAlmostEqual(rows[3]["margin_of_error"], 0.0548, places=3)  # 1.96 x sqrt(0.25/320)
        rows = {r["d"]: r["n_per_group"] for r in result("compare", "--d", "0.5", "--table")["result"]["table"]}
        self.assertEqual((rows[0.2], rows[0.5], rows[0.8]), (394, 64, 26))
        rows = {r["difference"]: r["n_per_group"] for r in result("compare", "--p1", "0.5", "--p2", "0.6", "--table")["result"]["table"]}
        self.assertEqual((rows[0.1], rows[0.15]), (388, 170))  # C2, and 0.50 vs 0.65 mirrors C1 (0.35 vs 0.50)

    def test_check_detectable_difference_is_bracketed(self):
        halves = result("check", "--n", "80")["result"]["two_equal_halves"]
        self.assertGreater(halves["detectable_p2"], 0.79)  # 0.79 needs 41.5 per group (fixtures/README.md, Q1)
        self.assertLess(halves["detectable_p2"], 0.80)  # 0.80 needs 38.5

    def test_saturation_reads_a_csv(self):
        from_file = result("saturation", "--file", str(FIXTURES / "saturation_guest2020.csv"))["result"]
        from_list = result("saturation", "--new-codes", "20,10,5,2,4,3,1,0")["result"]
        self.assertEqual(from_file, from_list)
        self.assertEqual([run["new_information"] for run in from_file["runs"]], [0.1892, 0.1081, 0.027])

    def test_every_report_has_a_statement(self):
        cases = json.loads((FIXTURES / "cases.json").read_text())["cases"]
        for case in cases:
            with self.subTest(case=case["id"]):
                statement = result(*case["argv"])["statement"]
                self.assertTrue(statement.endswith("."))
                self.assertGreater(len(statement), 40)

    def test_interview_ranges_are_labelled_guidance(self):
        report = result("interviews", "--segments", "2")
        self.assertIn("not a formula", report["assumptions"][0])

    def test_subgroup_result_warns_that_it_is_an_expectation(self):
        report = result("subgroups", "--share", "0.15")
        self.assertTrue(any("quota" in note for note in report["notes"]))

    def test_sparse_maxdiff_is_flagged(self):
        report = result("maxdiff", "--items", "60", "--per-set", "5", "--sets", "12")
        self.assertTrue(any("sparse" in note for note in report["notes"]))

    def test_one_sided_needs_fewer_than_two_sided(self):
        two = result("compare", "--p1", "0.5", "--p2", "0.7")["result"]["n_per_group"]
        one = result("compare", "--p1", "0.5", "--p2", "0.7", "--sides", "1")["result"]["n_per_group"]
        self.assertLess(one, two)

    def test_compare_is_symmetric_in_the_two_groups(self):
        a = result("compare", "--p1", "0.4", "--p2", "0.5")["result"]["n_per_group"]
        b = result("compare", "--p1", "0.5", "--p2", "0.4")["result"]["n_per_group"]
        self.assertEqual(a, b)

    def test_detectable_p2_needs_at_most_the_given_n(self):
        for direction in ("up", "down"):
            got = result("compare", "--p1", "0.3", "--n", "150", "--direction", direction)["result"]
            p2 = got["detectable_p2"]
            self.assertEqual(p2 > 0.3, direction == "up")
            needed = result("compare", "--p1", "0.3", "--p2", str(p2))["result"]["n_per_group"]
            self.assertLessEqual(needed, 151)  # p2 is printed to 4 places

    def test_invites_defaults_are_reported(self):
        report = result("invites", "--completes", "100", "--response-rate", "0.1")
        self.assertTrue(any("Taken as 100%" in note for note in report["notes"]))


class BadInputTest(unittest.TestCase):
    def assert_rejected(self, argv, message):
        proc = run(*argv)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertEqual(proc.stdout, "")
        self.assertIn(message, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_percentage_instead_of_proportion(self):
        self.assert_rejected(["proportion", "--margin", "5"], "did you mean 0.05?")
        self.assert_rejected(["proportion", "--margin", "0.05", "--confidence", "95"], "did you mean 0.95?")
        self.assert_rejected(["invites", "--completes", "100", "--response-rate", "20"], "did you mean 0.2?")

    def test_missing_target(self):
        self.assert_rejected(["proportion"], "give --margin")
        self.assert_rejected(["compare"], "give --p1 with --p2")
        self.assert_rejected(["compare", "--p1", "0.5"], "give --p2")

    def test_no_difference_to_detect(self):
        self.assert_rejected(["compare", "--p1", "0.5", "--p2", "0.5"], "no difference")
        self.assert_rejected(["compare", "--diff", "0", "--sd", "1"], "no difference")

    def test_mixed_or_incomplete_compare_inputs(self):
        self.assert_rejected(["compare", "--p1", "0.5", "--d", "0.3"], "not both")
        self.assert_rejected(["compare", "--diff", "5"], "go together")

    def test_out_of_range_values(self):
        self.assert_rejected(["proportion", "--margin", "0.05", "--deff", "0.5"], "--deff must be 1 or more")
        self.assert_rejected(["proportion", "--n", "500", "--population", "200"], "larger than --population")
        self.assert_rejected(["proportion", "--n", "0"], "greater than 0")
        self.assert_rejected(["mean", "--sd", "-1", "--margin", "2"], "greater than 0")
        self.assert_rejected(["compare", "--p1", "0.5", "--p2", "0.6", "--power", "0.4"], "--power must be above 0.5")
        self.assert_rejected(["subgroups", "--share", "0"], "--share")
        self.assert_rejected(["maxdiff", "--items", "10", "--per-set", "10"], "--per-set")
        self.assert_rejected(["conjoint", "--tasks", "10", "--alternatives", "3", "--levels", "3,x"], "--levels")

    def test_undetectable_difference(self):
        self.assert_rejected(["compare", "--p1", "0.5", "--n", "3"], "detectable")

    def test_new_options_reject_bad_input(self):
        self.assert_rejected(["proportion", "--n", "5", "--x", "6"], "--x must be between 0")
        self.assert_rejected(["proportion", "--x", "1"], "needs --n")
        self.assert_rejected(["proportion", "--n", "5", "--x", "1", "--p", "0.2"], "not both")
        self.assert_rejected(["compare", "--p1", "0.5", "--p2", "0.6", "--lift", "0.2"], "not both")
        self.assert_rejected(["compare", "--p1", "0.8", "--lift", "0.5"], "not a proportion")
        self.assert_rejected(["compare", "--p1", "0.5", "--p2", "0.6", "--ratio", "0"], "--ratio")
        self.assert_rejected(["compare", "--p1", "0.5", "--p2", "0.6", "--n", "50", "--n2", "60", "--ratio", "2"], "not both")
        self.assert_rejected(["compare", "--p1", "0.5", "--p2", "0.6", "--n2", "60"], "needs --n")
        self.assert_rejected(["compare", "--p1", "0.5", "--p2", "0.6", "--comparisons", "0"], "--comparisons")
        self.assert_rejected(["compare", "--p1", "0.5", "--p2", "0.6", "--method", "arcsine", "--continuity"], "--continuity applies")
        self.assert_rejected(["proportion", "--margin", "0.05", "--deff", "1.5", "--weight-cv", "0.5"], "give one of")
        self.assert_rejected(["proportion", "--margin", "0.05", "--icc", "0.05"], "go together")
        self.assert_rejected(["subgroups", "--share", "a=x"], "--share takes numbers")
        self.assert_rejected(["subgroups", "--share", "0.2", "--margin", "0.1", "--min-base", "50"], "not both")
        self.assert_rejected(["gap", "--p1", "0.6", "--p2", "0.5", "--n", "400"], "cannot sum to more than 1")
        self.assert_rejected(["invites", "--completes", "100", "--response-rate", "0.1", "--removal-rate", "1"], "--removal-rate")
        self.assert_rejected(["interviews", "--method", "focus-groups", "--goal", "meaning"], "no cited range")

    def test_saturation_rejects_bad_input(self):
        self.assert_rejected(["saturation"], "give --new-codes")
        self.assert_rejected(["saturation", "--new-codes", "5,4,3"], "need at least 6 interviews")
        self.assert_rejected(["saturation", "--new-codes", "0,0,0,0,1,1"], "no codes in the first 4")
        self.assert_rejected(["saturation", "--new-codes", "5,4,x,2,1,0"], "not a whole number")
        self.assert_rejected(["saturation", "--new-codes", "5,4,-1,2,1,0"], "cannot be negative")
        self.assert_rejected(["saturation", "--file", str(FIXTURES / "missing.csv")], "cannot read")

    def test_unknown_subcommand_and_missing_required(self):
        self.assertEqual(run("discover").returncode, 2)
        self.assertEqual(run("mean", "--margin", "2").returncode, 2)
        self.assertEqual(run().returncode, 2)


class ReviewRegressionTest(unittest.TestCase):
    """Defects found in the 2026-11 review; each test failed before its fix."""

    def rejected(self, argv, message):
        proc = run(*argv)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn(message, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_planned_n_is_the_inverse_of_the_reverse_margin(self):
        report = result("proportion", "--margin", "0.05", "--population", "500", "--deff", "2", "--n", "304")
        self.assertEqual(report["result"]["n_required"], 304)
        self.assertTrue(report["result"]["sufficient"])
        report = result("proportion", "--margin", "0.05", "--population", "500", "--deff", "2", "--n", "303")
        self.assertFalse(report["result"]["sufficient"])
        report = result("proportion", "--margin", "0.03", "--population", "300", "--deff", "1.5")
        self.assertEqual(report["result"]["n_required"], 253)
        report = result("mean", "--sd", "1", "--margin", "0.1", "--population", "500", "--deff", "2")
        n = report["result"]["n_required"]
        self.assertLessEqual(result("mean", "--sd", "1", "--n", str(n), "--population", "500", "--deff", "2")["result"]["margin_of_error"], 0.1)
        self.assertGreater(result("mean", "--sd", "1", "--n", str(n - 1), "--population", "500", "--deff", "2")["result"]["margin_of_error"], 0.1)

    def test_rare_outcome_is_planned_on_the_wilson_interval(self):
        report = result("proportion", "--p", "0.001", "--margin", "0.05")
        self.assertEqual(report["result"]["planning_method"], "wilson")
        n = report["result"]["n_required"]
        self.assertGreater(n, 50)
        self.assertIn("Wilson", report["statement"])
        at_n = result("proportion", "--p", "0.001", "--n", str(n))["result"]
        self.assertLessEqual(at_n["interval_high"] - 0.001, 0.05 + 1e-4)
        below = result("proportion", "--p", "0.001", "--n", str(n - 1))["result"]
        self.assertGreater(below["interval_high"] - 0.001, 0.05 - 1e-4)

    def test_a_census_has_no_sampling_error(self):
        report = result("proportion", "--population", "20", "--n", "20", "--x", "3")
        self.assertEqual(report["result"]["interval_method"], "census")
        self.assertEqual(report["result"]["margin_of_error"], 0.0)
        self.assertNotIn("interval_low", report["result"])

    def test_two_sided_power_counts_both_tails(self):
        report = result("compare", "--p1", "0.5", "--p2", "0.5001", "--n", "100")
        self.assertAlmostEqual(report["result"]["power_at_n"], 0.05, places=3)
        one_sided = result("compare", "--p1", "0.5", "--p2", "0.5001", "--n", "100", "--sides", "1")
        self.assertAlmostEqual(one_sided["result"]["power_at_n"], 0.05, places=2)

    def test_opt_in_sample_is_labelled_as_a_benchmark(self):
        report = result("proportion", "--n", "400", "--opt-in")
        self.assertTrue(report["statement"].startswith("Benchmark only"))
        self.assertIn("no design-based margin", report["statement"])
        self.assertNotIn("Benchmark", result("proportion", "--n", "400")["statement"])

    def test_saturation_never_drops_an_interview(self):
        self.rejected(["saturation", "--new-codes", "10,8,7,6,,0,0"], "interview 5 has no count")
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            bom = pathlib.Path(folder) / "bom.csv"
            bom.write_bytes(b"\xef\xbb\xbf10\n8\n7\n6\n0\n0\n")
            self.assertEqual(result("saturation", "--file", str(bom))["result"]["reported_as"], "4+2")
            unnamed = pathlib.Path(folder) / "two.csv"
            unnamed.write_text("id,count\n1,10\n2,8\n3,7\n4,6\n5,0\n6,0\n")
            self.rejected(["saturation", "--file", str(unnamed)], "--column")
            self.assertEqual(result("saturation", "--file", str(unnamed), "--column", "count")["result"]["reported_as"], "4+2")
            semi = pathlib.Path(folder) / "semi.csv"
            semi.write_text("id;new_codes\n1;10\n2;8\n3;7\n4;6\n5;0\n6;0\n")
            self.assertEqual(result("saturation", "--file", str(semi))["result"]["reported_as"], "4+2")

    def test_maxdiff_defaults_match_maxdiff_design(self):
        report = result("maxdiff", "--items", "12")
        self.assertEqual(report["result"]["items_per_set"], 4)
        self.assertEqual(report["result"]["sets_used"], 9)
        self.assertEqual(report["result"]["n_recommended"], 300)
        self.assertEqual(result("maxdiff", "--items", "7")["result"]["items_per_set"], 3)
        self.assertIn("exposures, not respondents", " ".join(result("maxdiff", "--items", "60", "--per-set", "5", "--sets", "12")["assumptions"]))

    def test_non_finite_numbers_are_input_errors(self):
        self.rejected(["proportion", "--margin", "0.05", "--weight-cv", "nan"], "--weight-cv must be a finite number")
        self.rejected(["compare", "--p1", "0.5", "--p2", "inf"], "--p2 must be a finite number")

    def test_nps_needs_its_own_variance(self):
        report = result("nps", "--promoters", "0.4", "--detractors", "0.2", "--margin", "0.05")
        self.assertEqual(report["result"]["n_required"], 861)
        # Lewis and Sauro 2021c: d = 0.10, Var1 + Var2 = 2, 80% power: 1,568 after their -3 (z rounded).
        self.assertEqual(result("nps", "--variance", "1", "--diff", "0.10")["result"]["n_per_group"], 1570)
        margin = result("nps", "--promoters", "0.4", "--detractors", "0.2", "--n", "861")["result"]["margin_of_error"]
        self.assertLessEqual(margin, 0.05)

    def test_check_takes_a_population(self):
        report = result("check", "--n", "323", "--population", "2000")
        self.assertAlmostEqual(report["result"]["overall"]["margin_of_error"], 0.0499, places=4)

    def test_subgroups_apply_the_design_effect(self):
        plain = result("subgroups", "--share", "0.5", "0.5", "--margin", "0.1")
        weighted = result("subgroups", "--share", "0.5", "0.5", "--margin", "0.1", "--deff", "2")
        self.assertEqual(weighted["result"]["min_base"], 2 * 97 - 1)
        self.assertGreater(weighted["result"]["n_total"], plain["result"]["n_total"])

    def test_expected_cells_use_each_group_size(self):
        # 364 in group 1 but 37 in group 2, where 10% expects under 4.
        notes = result("compare", "--p1", "0.3", "--p2", "0.1", "--ratio", "0.1")["notes"]
        self.assertTrue(any("Fewer than 5 expected" in n for n in notes))


if __name__ == "__main__":
    unittest.main()
