"""Tests for scripts/van_westendorp_analysis.py. Run from the skill folder: python3 -m unittest discover -s tests

Expected values come from fixtures/*.expected.json, which were worked out by hand (fixtures/README.md) or
taken from a published example. None of them were produced by the script.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
import xml.dom.minidom

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "van_westendorp_analysis.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def analyse(case, *extra):
    expected = json.loads((FIXTURES / f"{case}.expected.json").read_text())
    args = extra if extra else expected.get("args", [])
    proc = run(FIXTURES / expected.get("input", f"{case}.input.csv"), "--json", *args)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    return json.loads(proc.stdout), expected


class FixtureCase(unittest.TestCase):
    def assert_subset(self, expected, actual, path=""):
        """Every key in expected must match actual; numbers to 6 decimals."""
        for key, want in expected.items():
            got = actual[key]
            where = f"{path}.{key}"
            if isinstance(want, dict):
                self.assert_subset(want, got, where)
            elif isinstance(want, float) or (isinstance(want, int) and not isinstance(want, bool)):
                self.assertAlmostEqual(got, want, places=6, msg=where)
            elif isinstance(want, list) and want and isinstance(want[0], (int, float)):
                self.assertEqual(len(got), len(want), where)
                for g, w in zip(got, want):
                    self.assertAlmostEqual(g, w, places=6, msg=where)
            else:
                self.assertEqual(got, want, where)

    def assert_counts(self, result, counts):
        n = result["respondents"]["weight_total"]
        self.assertEqual([row["price"] for row in result["curves"]], [float(p) for p in counts["price"]])
        for key in ("too_cheap", "cheap", "expensive", "too_expensive"):
            self.assertEqual([round(row[key] * n) for row in result["curves"]], counts[key], key)

    def assert_curve(self, rows, expected_rows):
        for got, want in zip(rows, expected_rows):
            self.assert_subset(want, got, f"price {want['price']}")


class HandWorkedFixtures(FixtureCase):
    def test_basic_points_range_and_curves(self):
        result, expected = analyse("basic")
        for key in ("respondents", "price_points", "acceptable_range", "alternative_range"):
            self.assert_subset(expected[key], result[key], key)
        self.assert_counts(result, expected["curve_counts_of_10"])
        self.assertEqual(result["conventions"]["pmc"], "too cheap x not cheap")
        self.assertEqual(result["conventions"]["pme"], "too expensive x not expensive")

    def test_basic_narrower_definition_swaps_the_ranges(self):
        result, expected = analyse("basic", "--range-definition", "narrower")
        self.assert_subset({"low": 8.0, "high": 11.0, "definition": "narrower"}, result["acceptable_range"])
        self.assert_subset({"low": 7.5, "high": 11.5, "definition": "original"}, result["alternative_range"])
        self.assertEqual(result["price_points"]["pmc"]["status"], "exact")
        self.assertEqual(result["conventions"]["pmc"], "too cheap x expensive")
        self.assert_subset(expected["price_points"]["opp"], result["price_points"]["opp"])
        self.assert_subset(expected["price_points"]["ipp"], result["price_points"]["ipp"])

    def test_inconsistent_respondents_are_excluded_and_counted(self):
        result, expected = analyse("inconsistent")
        self.assert_subset(expected["respondents"], result["respondents"], "respondents")
        self.assert_subset(expected["price_points"], result["price_points"], "price_points")
        self.assertFalse(result["respondents"]["inconsistent_kept"])
        joined = " ".join(result["warnings"])
        self.assertIn("2 inconsistent respondent(s) excluded", joined)
        self.assertIn("1 respondent(s) left out", joined)

    def test_inconsistent_text_output_names_the_count_and_ids(self):
        proc = run(FIXTURES / "inconsistent.input.csv")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertRegex(proc.stdout, r"inconsistent\s+2\s+\(excluded")
        self.assertIn("R11, R12", proc.stdout)

    def test_keep_inconsistent_keeps_them_and_says_so(self):
        result, expected = analyse("inconsistent", "--keep-inconsistent")
        self.assertEqual(result["respondents"]["analysed"], expected["keep_inconsistent"]["analysed"])
        self.assertTrue(result["respondents"]["inconsistent_kept"])
        self.assertAlmostEqual(result["price_points"]["opp"]["price"], expected["keep_inconsistent"]["opp"], places=6)
        self.assertIn("KEPT", " ".join(result["warnings"]))

    def test_nms_trial_and_revenue_curves(self):
        result, expected = analyse("nms")
        self.assertEqual(result["nms"]["n"], expected["nms"]["n"])
        self.assert_curve(result["nms"]["curve"], expected["nms"]["curve"])
        self.assert_subset(expected["nms"]["trial_max"], result["nms"]["trial_max"])
        self.assert_subset(expected["nms"]["revenue_max"], result["nms"]["revenue_max"])
        self.assertEqual(result["nms"]["weights"], {"5": 0.7, "4": 0.5, "3": 0.3, "2": 0.1, "1": 0.0})

    def test_nms_modified_variant_holds_the_cheap_probability(self):
        result, expected = analyse("nms", "--nms-variant", "modified")
        self.assert_curve(result["nms"]["curve"], expected["modified_variant_curve"])
        self.assert_subset(expected["modified_variant_revenue_max"], result["nms"]["revenue_max"])

    def test_nms_revenue_peak_between_observed_prices(self):
        result, expected = analyse("nms_interior")
        self.assert_curve(result["nms"]["curve"], expected["nms"]["curve"])
        for key in ("trial_max", "revenue_max", "revenue_max_on_grid"):
            self.assert_subset(expected["nms"][key], result["nms"][key], key)

    def test_flat_segment_reports_midpoint_interval_and_warning(self):
        result, expected = analyse("nms_interior")
        self.assert_subset(expected["price_points"]["opp"], result["price_points"]["opp"])
        self.assertIn("coincide from 20.00 to 30.00", " ".join(result["warnings"]))


class PublishedExamples(FixtureCase):
    def test_conjointly_manual_calculation(self):
        result, expected = analyse("conjointly_published")
        for key in ("respondents", "price_points", "acceptable_range", "alternative_range"):
            self.assert_subset(expected[key], result[key], key)
        self.assert_counts(result, expected["curve_counts_of_10"])
        self.assertIn("same price to two neighbouring questions", " ".join(result["warnings"]))

    def test_conjointly_strict_excludes_the_tied_respondent(self):
        result, expected = analyse("conjointly_published", "--strict")
        self.assert_subset(expected["strict"], result["respondents"])

    def test_orme_smith_nms_example(self):
        result, expected = analyse("orme_smith")
        self.assert_curve(result["nms"]["curve"], expected["nms"]["curve"])
        self.assert_subset(expected["nms"]["trial_max"], result["nms"]["trial_max"])
        self.assert_subset(expected["nms"]["revenue_max"], result["nms"]["revenue_max"])


class SecondPassFixtures(FixtureCase):
    def test_r_conventions_current_preset(self):
        _, expected = analyse("r_conventions")
        for block in ("compat_r", "compat_r_1_3_0"):
            result, _ = analyse("r_conventions", *expected[block]["args"])
            self.assert_subset(expected[block]["price_points"], result["price_points"], block)
            self.assert_subset(expected[block]["alternative_range"], result["alternative_range"], block)
            self.assert_counts(result, expected[block]["curve_counts_of_10"])
            self.assertIn("too cheap < cheap", result["respondents"]["consistency_rule"])
            self.assertEqual(result["conventions"]["compat"], expected[block]["args"][1])

    def test_r_conventions_explicit_flags(self):
        _, expected = analyse("r_conventions")
        result, _ = analyse("r_conventions", *expected["explicit_flags"]["args"])
        self.assert_subset(expected["explicit_flags"]["price_points"], result["price_points"])
        self.assertEqual(result["conventions"]["tie"], "min")
        self.assertIn("none", result["conventions"]["interpolation"])

    def test_segments(self):
        result, expected = analyse("segments")
        self.assert_subset(expected["price_points"], result["price_points"], "overall")
        self.assertEqual(list(result["segments"]), ["starter", "team"])
        self.assert_subset(expected["segments"], result["segments"], "segments")
        for seg in result["segments"].values():
            self.assertTrue(any("Small sample: n = 5" in w for w in seg["warnings"]))
        text = run(FIXTURES / "segments.input.csv", "--segment", "plan").stdout
        self.assertIn("By segment (plan)", text)
        self.assertRegex(text, r"starter\s+5\s+5\.00\s+6\.50\s+7\.33\s+8\.67")

    def test_tie_rules_on_a_flat_run(self):
        _, expected = analyse("segments")
        for rule, want in expected["starter_opp_by_tie"].items():
            result, _ = analyse("segments", "--segment", "plan", "--tie", rule)
            self.assertAlmostEqual(result["segments"]["starter"]["price_points"]["opp"]["price"], want, places=6)
        _, expected = analyse("tie_run")
        for rule, want in expected["opp_by_tie"].items():
            result, _ = analyse("tie_run", "--tie", rule)
            self.assertAlmostEqual(result["price_points"]["opp"]["price"], want, places=6, msg=rule)
            self.assertEqual(result["price_points"]["opp"]["interval"], [2.0, 5.0])

    def test_weights(self):
        result, expected = analyse("weighted")
        self.assert_subset(expected["respondents"], result["respondents"])
        self.assert_subset(expected["price_points"], result["price_points"])
        self.assert_counts(result, expected["weighted_counts_of_6"])
        self.assert_curve(result["nms"]["curve"], expected["nms"]["curve"])
        self.assert_subset(expected["nms"]["trial_max"], result["nms"]["trial_max"])
        self.assert_subset(expected["nms"]["revenue_max"], result["nms"]["revenue_max"])
        unweighted, _ = analyse("weighted", "--no-nms")
        self.assert_subset(expected["unweighted_ipp"], unweighted["price_points"]["ipp"])

    def test_three_question_variant(self):
        result, expected = analyse("three_question")
        for key in ("questions", "respondents", "price_points", "acceptable_range", "alternative_range"):
            self.assert_subset({key: expected[key]}, result)
        self.assertEqual(result["price_points"]["ipp"]["alias"], "IDP")
        self.assertIn("Three-question variant", " ".join(result["warnings"]))
        text = run(FIXTURES / "three_question.input.csv").stdout
        self.assertIn("needs the too-cheap question", text)

    def test_price_limits_exclude_and_count(self):
        _, expected = analyse("basic")
        result, _ = analyse("basic", "--max-price", "18")
        self.assert_subset(expected["max_price_18"], result)
        self.assertIn("2 respondent(s) excluded: a price above 18.00", " ".join(result["warnings"]))
        result, _ = analyse("basic", "--min-price", "3")
        self.assert_subset(expected["min_price_3"], result)

    def test_shares_at_a_candidate_price(self):
        result, expected = analyse("basic", "--at", "9", "--at", "9.5")
        for got, want in zip(result["at"], expected["at"]):
            self.assert_subset(want, got, f"at {want['price']}")

    def test_curves_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "curves.csv"
            proc = run(FIXTURES / "basic.input.csv", "--curves-csv", out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            lines = out.read_text().splitlines()
        expected = json.loads((FIXTURES / "basic.expected.json").read_text())["curve_counts_of_10"]
        self.assertEqual(lines[0], "price,too_cheap,cheap,expensive,too_expensive,not_cheap,not_expensive")
        self.assertEqual(len(lines), 16)
        for i, line in enumerate(lines[1:]):
            cells = [float(c) for c in line.split(",")]
            want = [expected[k][i] for k in ("price", "too_cheap", "cheap", "expensive", "too_expensive")]
            self.assertEqual(cells[0], want[0])
            self.assertEqual([round(c * 10) for c in cells[1:5]], want[1:])
            self.assertAlmostEqual(cells[5], 1 - cells[2], places=6)
            self.assertAlmostEqual(cells[6], 1 - cells[3], places=6)

    def test_bootstrap_is_seeded_and_brackets_the_estimate(self):
        first = run(FIXTURES / "basic.input.csv", "--json", "--bootstrap", "300", "--seed", "7").stdout
        again = run(FIXTURES / "basic.input.csv", "--json", "--bootstrap", "300", "--seed", "7").stdout
        self.assertEqual(first, again)
        other = run(FIXTURES / "basic.input.csv", "--json", "--bootstrap", "300", "--seed", "8").stdout
        self.assertNotEqual(first, other)
        result = json.loads(first)
        self.assertEqual(result["bootstrap"]["resamples"], 300)
        for key, interval in result["bootstrap"]["intervals"].items():
            price = result["price_points"][key]["price"]
            self.assertLessEqual(interval["low"], price, key)
            self.assertGreaterEqual(interval["high"], price, key)
        self.assertIsNone(json.loads(run(FIXTURES / "basic.input.csv", "--json").stdout)["bootstrap"])

    def test_ipp_below_opp_is_flagged(self):
        result, expected = analyse("ipp_below_opp")
        self.assert_subset(expected["price_points"], result["price_points"])
        self.assertIn("IPP is below OPP", " ".join(result["warnings"]))

    def test_range_without_width_is_flagged(self):
        result, expected = analyse("no_width")
        self.assert_subset(expected["price_points"], result["price_points"])
        self.assertIn("PMC equals PME", " ".join(result["warnings"]))

    def test_nms_presets_and_end_probabilities(self):
        _, expected = analyse("nms")
        result, _ = analyse("nms", "--nms-preset", "orme-cpg")
        self.assert_curve(result["nms"]["curve"], expected["preset_orme_cpg_curve"])
        self.assertEqual(result["nms"]["weights"]["5"], 0.75)
        result, _ = analyse("nms", "--nms-too-cheap-prob", "0.2")
        self.assert_curve(result["nms"]["curve"], expected["too_cheap_prob_0_2_curve"])
        proc = run(FIXTURES / "nms.input.csv", "--nms-preset", "fifths", "--nms-weights", "1,1,1,1,1")
        self.assertEqual(proc.returncode, 2)

    def test_both_ranges_and_idp_alias_are_printed(self):
        text = run(FIXTURES / "basic.input.csv").stdout
        self.assertIn("Acceptable price range, original definition (too cheap x not cheap; too expensive x not "
                      "expensive): 7.50 to 11.50", text)
        self.assertIn("Acceptable price range, narrower definition (too cheap x expensive; too expensive x cheap): "
                      "8.00 to 11.00", text)
        self.assertIn("(IDP)", text)


class EdgeCases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, text, name="in.csv"):
        path = pathlib.Path(self.tmp.name) / name
        path.write_text(text, encoding="utf-8")
        return path

    def fails(self, text, *args, contains):
        proc = run(self.write(text), *args)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertEqual(proc.stdout, "")
        self.assertIn(contains, proc.stderr)

    def test_small_sample_warning_and_min_n(self):
        result = json.loads(run(FIXTURES / "basic.input.csv", "--json").stdout)
        self.assertTrue(any("Small sample" in w and "below 100" in w for w in result["warnings"]))
        result = json.loads(run(FIXTURES / "basic.input.csv", "--json", "--min-n", "10").stdout)
        self.assertFalse(any("Small sample" in w for w in result["warnings"]))

    def test_curves_that_do_not_cross(self):
        text = "too_cheap,cheap,expensive,too_expensive\n10,10,1,1\n10,10,1,1\n"
        proc = run(self.write(text), "--json", "--keep-inconsistent")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["price_points"]["pmc"]["status"], "no_crossing")
        self.assertIsNone(result["price_points"]["pmc"]["price"])
        self.assertIsNone(result["acceptable_range"]["low"])
        self.assertTrue(any("PMC" in w and "do not cross" in w for w in result["warnings"]))

    def test_all_respondents_inconsistent_is_an_error(self):
        self.fails("too_cheap,cheap,expensive,too_expensive\n9,5,3,1\n", contains="no respondent is left")

    def test_missing_column_is_an_error(self):
        self.fails("a,b,c,d\n1,2,3,4\n", contains="no column found for the 'cheap' price")

    def test_ambiguous_column_is_an_error(self):
        self.fails("too cheap,cheap,cheap price,expensive,too expensive\n1,2,2,3,4\n", contains="several columns")

    def test_unknown_named_column_is_an_error(self):
        self.fails("too_cheap,cheap,expensive,too_expensive\n1,2,3,4\n", "--cheap", "bargain", contains="is not in the file")

    def test_non_numeric_price_is_an_error_with_the_line(self):
        self.fails("too_cheap,cheap,expensive,too_expensive\n1,2,abc,4\n", contains="line 2, column 'expensive'")

    def test_zero_and_negative_prices_are_flagged_not_changed(self):
        text = "too_cheap,cheap,expensive,too_expensive\n-1,2,3,4\n0,2,3,4\n1,2,3,4\n"
        result = json.loads(run(self.write(text), "--json").stdout)
        self.assertEqual(result["respondents"]["analysed"], 3)
        self.assertEqual(result["price_summary"]["too_cheap"]["min"], -1.0)
        self.assertIn("2 analysed respondent(s) gave a price of zero or less", " ".join(result["warnings"]))
        result = json.loads(run(self.write(text), "--json", "--min-price", "0.01").stdout)
        self.assertEqual(result["respondents"]["outside_price_limits"], 2)

    def test_currency_codes_are_accepted_and_mixed_markers_flagged(self):
        text = 'too_cheap,cheap,expensive,too_expensive\n10 USD,USD 20,30USD,"1,040 USD"\n10 kr,20 kr,30 kr,€40\n'
        result = json.loads(run(self.write(text), "--json").stdout)
        self.assertEqual(result["respondents"]["analysed"], 2)
        self.assertEqual(result["price_summary"]["too_expensive"]["max"], 1040.0)
        self.assertEqual(result["currency_markers"], ["KR", "USD", "€"])
        self.assertIn("different currency markers", " ".join(result["warnings"]))
        self.fails("too_cheap,cheap,expensive,too_expensive\n1,2,3,USD\n", contains="'USD' is not a price")

    def test_decimal_comma_is_not_guessed(self):
        text = "too_cheap;cheap;expensive;too_expensive\n1,5;2,5;3,5;4,5\n"
        self.fails(text, contains="--decimal comma")
        proc = run(self.write(text), "--decimal", "comma", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["curves"][0]["price"], 1.5)

    def test_currency_symbols_thousands_and_na_tokens(self):
        text = 'tc,cheap,expensive,te\n"$1,000","$1,500","$2,000","$2,500"\nNA,1,2,3\n'
        self.fails(text, contains="'NA' is not a price")
        proc = run(self.write(text), "--na", "NA", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["respondents"]["incomplete"], 1)
        self.assertEqual(result["curves"][0]["price"], 1000.0)

    def test_named_columns_override_detection(self):
        text = "q1,q2,q3,q4\n1,2,3,4\n2,3,4,5\n"
        proc = run(self.write(text), "--too-cheap", "q1", "--cheap", "q2", "--expensive", "q3",
                   "--too-expensive", "q4", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["columns"]["expensive"], "q3")

    def test_intent_off_scale_is_an_error(self):
        text = "too_cheap,cheap,expensive,too_expensive,intent_cheap,intent_expensive\n1,2,3,4,7,1\n"
        self.fails(text, contains="not on the purchase-intent scale")

    def test_single_intent_column_is_an_error_unless_no_nms(self):
        text = "too_cheap,cheap,expensive,too_expensive,intent_cheap\n1,2,3,4,5\n"
        self.fails(text, contains="needs both")
        proc = run(self.write(text), "--no-nms", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(json.loads(proc.stdout)["nms"])

    def test_weights_must_match_the_scale(self):
        text = "too_cheap,cheap,expensive,too_expensive,intent_cheap,intent_expensive\n1,2,3,4,5,1\n"
        self.fails(text, "--nms-weights", "0.7,0.5", contains="same number")

    def test_missing_and_reversed_intent_are_reported(self):
        text = ("too_cheap,cheap,expensive,too_expensive,intent_cheap,intent_expensive\n"
                "1,2,3,4,2,5\n1,2,3,4,,3\n")
        result = json.loads(run(self.write(text), "--json").stdout)
        self.assertEqual(result["nms"]["n"], 1)
        joined = " ".join(result["warnings"])
        self.assertIn("1 analysed respondent(s) left out", joined)
        self.assertIn("higher purchase intent at their expensive price", joined)

    def test_tied_cheap_and_expensive_price_uses_the_mean_intent(self):
        text = "too_cheap,cheap,expensive,too_expensive,intent_cheap,intent_expensive\n1,2,2,4,5,3\n"
        result = json.loads(run(self.write(text), "--json").stdout)
        at_two = [row for row in result["nms"]["curve"] if row["price"] == 2.0][0]
        self.assertAlmostEqual(at_two["trial"], 0.5, places=9)

    def test_chart_is_well_formed_svg(self):
        out = pathlib.Path(self.tmp.name) / "chart.svg"
        proc = run(FIXTURES / "nms.input.csv", "--chart", out)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        doc = xml.dom.minidom.parse(str(out))
        self.assertEqual(doc.documentElement.tagName, "svg")
        self.assertEqual(len(doc.getElementsByTagName("polyline")), 6)
        self.assertIn("Chart written to", proc.stdout)

    def test_output_is_deterministic(self):
        first = run(FIXTURES / "nms.input.csv", "--json").stdout
        self.assertEqual(first, run(FIXTURES / "nms.input.csv", "--json").stdout)

    def test_empty_file_and_missing_file(self):
        self.fails("", contains="empty")
        proc = run(pathlib.Path(self.tmp.name) / "nope.csv")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("cannot read", proc.stderr)


if __name__ == "__main__":
    unittest.main()
