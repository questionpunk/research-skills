"""Tests for scripts/pmf_survey.py. Run from the skill folder: python3 -m unittest discover -s tests

Expected values come from fixtures/*.expected.json, worked out by hand in fixtures/README.md.
"""
import csv
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "pmf_survey.py"

sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location("pmf_survey", SCRIPT)
pmf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pmf)


def run(*args):
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *map(str, args)],
        capture_output=True,
        text=True,
    )


def run_json(*args):
    proc = run(*args, "--json")
    if proc.returncode != 0:
        raise AssertionError(f"exit {proc.returncode}: {proc.stderr}")
    return json.loads(proc.stdout)


def expected(case):
    return json.loads((FIXTURES / f"{case}.expected.json").read_text(encoding="utf-8"))


class WilsonTest(unittest.TestCase):
    def test_wilson_matches_nist_worked_example(self):
        # NIST/SEMATECH e-Handbook 7.2.4.1: p-hat 0.13, N 200, z 1.645 -> lower limit 0.09577.
        low, _ = pmf.wilson(26, 200, 1.645)
        self.assertAlmostEqual(low, 0.09577, places=5)

    def test_wilson_zero_successes_closed_form(self):
        z = 1.96
        low, high = pmf.wilson(0, 20, z)
        self.assertEqual(low, 0.0)
        self.assertAlmostEqual(high, z * z / (20 + z * z), places=10)
        self.assertAlmostEqual(high, 0.1611, places=4)

    def test_wilson_all_successes_stays_in_range(self):
        low, high = pmf.wilson(10, 10, 1.96)
        self.assertEqual(high, 1.0)
        self.assertAlmostEqual(low, 10 / (10 + 1.96 * 1.96), places=10)

    def test_z_for_95(self):
        self.assertAlmostEqual(pmf.z_for(95), 1.959964, places=5)


class FixtureTest(unittest.TestCase):
    def assert_score(self, got, want):
        for key in ("very", "base", "verdict", "small_base"):
            self.assertEqual(got[key], want[key], key)
        for key in ("pct", "ci_low_pct", "ci_high_pct"):
            self.assertAlmostEqual(got[key], want[key], delta=0.1001, msg=key)

    def test_basic(self):
        want = expected("basic")
        got = run_json(FIXTURES / "basic.input.csv")
        self.assertEqual(got["counts"], want["counts"])
        self.assert_score(got["score"], want["score"])
        self.assertAlmostEqual(got["pct_with_na_in_base"], want["pct_with_na_in_base"], delta=0.1001)
        self.assertEqual(got["input"]["answer_column"], "How would you feel if you could no longer use Acme?")
        self.assertIn("outside the base", got["denominator_rule"])
        self.assertTrue(got["verdict_text"].startswith("Cannot tell"))

    def test_segments_benefits_and_focus(self):
        want = expected("segments")
        got = run_json(
            FIXTURES / "segments.input.csv",
            "--segment-col", "persona",
            "--benefit-col", "main_benefit",
            "--focus-segments", "Founder,Manager",
        )
        self.assertEqual(got["counts"], want["counts"])
        self.assert_score(got["score"], want["score"])
        self.assertAlmostEqual(got["pct_with_na_in_base"], want["pct_with_na_in_base"], delta=0.1001)
        self.assertEqual(got["segment_tables"][0]["column"], "persona")
        got_segments = got["segment_tables"][0]["segments"]
        self.assertEqual([s["segment"] for s in got_segments], [s["segment"] for s in want["segments"]])
        for got_seg, want_seg in zip(got_segments, want["segments"]):
            self.assert_score(got_seg, want_seg)
            self.assertEqual(got_seg["na"], want_seg["na"])
            self.assertAlmostEqual(got_seg["share_of_very_pct"], want_seg["share_of_very_pct"], delta=0.1001)
        self.assert_score(got["focus"], want["focus"])
        self.assertEqual(got["focus"]["segments"], want["focus"]["segments"])
        self.assertEqual(got["benefits_among_very"]["counts"], want["benefits_among_very"])
        self.assertEqual(got["core_benefit"]["value"], want["core_benefit"])
        for key, value in want["somewhat_split"].items():
            self.assertEqual(got["somewhat_split"][key], value, key)

    def test_small_n_is_flagged_and_cannot_tell(self):
        want = expected("small_n")
        got = run_json(FIXTURES / "small_n.input.csv")
        self.assertEqual(got["counts"], want["counts"])
        self.assert_score(got["score"], want["score"])
        self.assertTrue(any("below the suggested minimum of 30" in flag for flag in got["flags"]))

    def test_label_variants_are_mapped(self):
        want = expected("labels")
        got = run_json(FIXTURES / "labels.input.csv")
        self.assertEqual(got["counts"], want["counts"])
        self.assert_score(got["score"], want["score"])
        self.assertAlmostEqual(got["pct_with_na_in_base"], want["pct_with_na_in_base"], delta=0.1001)
        self.assertEqual(got["label_map_used"]["I no longer use it"], "na")

    def test_codes_need_a_map(self):
        want = expected("coded")
        proc = run(FIXTURES / "coded.input.csv")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        for label in want["unknown_labels_without_map"]:
            self.assertIn(f'"{label}"', proc.stderr)
        args = [arg for pair in want["map"] for arg in ("--map", pair)]
        got = run_json(FIXTURES / "coded.input.csv", *args)
        self.assertEqual(got["counts"], want["counts"])
        self.assert_score(got["score"], want["score"])

    def test_bad_labels_error_lists_them(self):
        want = expected("bad_labels")
        proc = run(FIXTURES / "bad_labels.input.csv")
        self.assertEqual(proc.returncode, want["exit_code"])
        self.assertEqual(proc.stdout, "")
        nonstandard_part, unknown_part = proc.stderr.split("Unknown answer labels")
        self.assertIn("Non-standard answer wording", nonstandard_part)
        for label in want["nonstandard_labels"]:
            self.assertIn(label, nonstandard_part)
            self.assertNotIn(label, unknown_part)
        for label in want["unknown_labels"]:
            self.assertIn(label, unknown_part)
            self.assertNotIn(label, nonstandard_part)
        self.assertIn("Nothing was scored", proc.stderr)

    def test_all_na_gives_no_score(self):
        want = expected("all_na")
        proc = run(FIXTURES / "all_na.input.csv", "--json")
        self.assertEqual(proc.returncode, want["exit_code"])
        self.assertEqual(proc.stdout, "")
        for text in want["stderr_contains"]:
            self.assertIn(text, proc.stderr)

    def test_benefit_match_column(self):
        want = expected("benefit_match")
        got = run_json(FIXTURES / "benefit_match.input.csv", "--benefit-match-col", "benefit_match")
        self.assertEqual(got["counts"], want["counts"])
        self.assertEqual(got["somewhat_split"], want["somewhat_split"])


class BehaviourTest(unittest.TestCase):
    def write_csv(self, header, rows):
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8")
        self.addCleanup(pathlib.Path(handle.name).unlink)
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
        handle.close()
        return handle.name

    def scored(self, very, somewhat, not_):
        rows = [["Very disappointed"]] * very + [["Somewhat disappointed"]] * somewhat + [["Not disappointed"]] * not_
        return run_json(self.write_csv(["disappointment"], rows))

    def test_verdict_above_only_when_whole_interval_is_above(self):
        got = self.scored(60, 30, 10)  # 60 of 100
        self.assertEqual(got["score"]["verdict"], "above")
        self.assertTrue(got["verdict_text"].startswith("Above"))

    def test_verdict_below_only_when_whole_interval_is_below(self):
        got = self.scored(20, 40, 40)  # 20 of 100
        self.assertEqual(got["score"]["verdict"], "below")
        self.assertTrue(got["verdict_text"].startswith("Below"))

    def test_point_estimate_over_benchmark_is_not_enough(self):
        got = self.scored(45, 30, 25)  # 45 of 100: interval spans 40
        self.assertEqual(got["score"]["verdict"], "cannot_tell")
        self.assertLess(got["score"]["ci_low_pct"], 40)

    def test_readable_output_states_rule_and_interval(self):
        proc = run(FIXTURES / "basic.input.csv")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("40.0%  (16 of 40)", proc.stdout)
        self.assertIn("(Wilson)", proc.stdout)
        self.assertIn("Denominator:", proc.stdout)
        self.assertIn("With N/A kept in the base: 33.3%", proc.stdout)

    def test_custom_map_overrides_builtin(self):
        path = self.write_csv(["disappointment"], [["Very"], ["Devastated"], ["Meh"], ["Meh"]])
        got = run_json(path, "--map", "Devastated=very", "--map", "meh=not")
        self.assertEqual(got["counts"]["very"], 2)
        self.assertEqual(got["counts"]["not"], 2)

    def test_bad_map_category(self):
        proc = run(FIXTURES / "basic.input.csv", "--map", "Very=love")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("category must be one of", proc.stderr)

    def test_missing_file(self):
        proc = run(FIXTURES / "nope.csv")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("File not found", proc.stderr)

    def test_missing_answer_column_lists_columns(self):
        proc = run(FIXTURES / "basic.input.csv", "--answer-col", "q9")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("respondent_id", proc.stderr)

    def test_ambiguous_answer_column_is_not_guessed(self):
        path = self.write_csv(["pmf_q1", "pmf_q2"], [["Very disappointed", "x"]])
        proc = run(path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--answer-col", proc.stderr)

    def test_no_answer_column_detected(self):
        path = self.write_csv(["id", "q1"], [["1", "Very disappointed"]])
        proc = run(path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--answer-col", proc.stderr)

    def test_header_only_file(self):
        proc = run(self.write_csv(["disappointment"], []))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("no response rows", proc.stderr)

    def test_missing_segment_column(self):
        proc = run(FIXTURES / "segments.input.csv", "--segment-col", "plan")
        self.assertEqual(proc.returncode, 2)
        self.assertIn('"plan" not found', proc.stderr)

    def test_unknown_focus_segment(self):
        proc = run(FIXTURES / "segments.input.csv", "--segment-col", "persona", "--focus-segments", "Founder,CEO")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("CEO", proc.stderr)

    def test_blank_segment_is_kept_and_named(self):
        path = self.write_csv(
            ["disappointment", "persona"],
            [["Very disappointed", "A"], ["Not disappointed", ""], ["Somewhat disappointed", "A"]],
        )
        got = run_json(path, "--segment-col", "persona")
        segments = got["segment_tables"][0]["segments"]
        self.assertIn("(blank)", [seg["segment"] for seg in segments])
        self.assertTrue(all(seg["small_base"] for seg in segments))

    def test_segment_with_only_na_has_no_score(self):
        path = self.write_csv(
            ["disappointment", "persona"],
            [["Very disappointed", "A"], ["N/A", "B"], ["Not disappointed", "A"]],
        )
        got = run_json(path, "--segment-col", "persona")
        seg_b = next(seg for seg in got["segment_tables"][0]["segments"] if seg["segment"] == "B")
        self.assertIsNone(seg_b["pct"])
        self.assertEqual(seg_b["verdict"], "no_base")
        self.assertEqual(run(path, "--segment-col", "persona").returncode, 0)

    def test_benefit_tie_needs_core_benefit(self):
        path = self.write_csv(
            ["disappointment", "benefit"],
            [["Very disappointed", "speed"], ["Very disappointed", "focus"], ["Somewhat disappointed", "focus"]],
        )
        proc = run(path, "--benefit-col", "benefit")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--core-benefit", proc.stderr)
        got = run_json(path, "--benefit-col", "benefit", "--core-benefit", "focus")
        self.assertEqual(got["somewhat_split"]["benefit_matches"], 1)

    def test_bad_benefit_match_value(self):
        path = self.write_csv(["disappointment", "m"], [["Somewhat disappointed", "maybe"]])
        proc = run(path, "--benefit-match-col", "m")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("maybe", proc.stderr)

    def test_benefit_options_are_exclusive(self):
        proc = run(FIXTURES / "segments.input.csv", "--benefit-col", "main_benefit", "--benefit-match-col", "persona")
        self.assertEqual(proc.returncode, 2)

    def test_min_base_and_benchmark_are_configurable(self):
        got = run_json(FIXTURES / "basic.input.csv", "--min-base", "50", "--benchmark", "20")
        self.assertTrue(got["score"]["small_base"])
        self.assertEqual(got["score"]["verdict"], "above")

    def test_output_is_deterministic(self):
        args = (FIXTURES / "segments.input.csv", "--segment-col", "persona", "--benefit-col", "main_benefit", "--json")
        self.assertEqual(run(*args).stdout, run(*args).stdout)


class SecondPassTest(unittest.TestCase):
    """Wave comparison, counts input, several segment columns, accounts, wording, response rate."""

    def assert_block(self, got, want):
        for key, value in want.items():
            if isinstance(value, float):
                self.assertAlmostEqual(got[key], value, delta=0.1001, msg=key)
            else:
                self.assertEqual(got[key], value, key)

    def write_csv(self, header, rows):
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8")
        self.addCleanup(pathlib.Path(handle.name).unlink)
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
        handle.close()
        return handle.name

    # --- benefit codes are matched without regard to case (regression) ---
    def test_benefit_codes_ignore_case_and_spacing(self):
        want = expected("benefit_case")
        got = run_json(FIXTURES / "benefit_case.input.csv", "--benefit-col", "main_benefit")
        self.assertEqual(got["benefits_among_very"]["counts"], want["benefits_among_very"])
        self.assertEqual(got["core_benefit"]["value"], want["core_benefit"])
        for key, value in want["somewhat_split"].items():
            self.assertEqual(got["somewhat_split"][key], value, key)
        self.assertEqual(got["somewhat_split"]["other_benefits"], want["other_benefits"])

    def test_core_benefit_option_ignores_case(self):
        want = expected("benefit_case")["with_core_benefit_FOCUS"]
        got = run_json(FIXTURES / "benefit_case.input.csv", "--benefit-col", "main_benefit", "--core-benefit", "FOCUS")
        self.assertEqual(got["core_benefit"]["value"], "Focus")
        for key, value in want.items():
            self.assertEqual(got["somewhat_split"][key], value, key)

    # --- change between two waves ---
    def test_newcombe_matches_hand_worked_example(self):
        d, low, high = pmf.newcombe_diff(48, 80, 56, 70, 1.96)
        self.assertAlmostEqual(d, 0.2, places=10)
        self.assertAlmostEqual(low, 0.0524, places=4)
        self.assertAlmostEqual(high, 0.3339, places=4)

    def test_newcombe_equals_the_ncss_form(self):
        z = 1.96
        l1, u1 = pmf.wilson(12, 52, z)
        l2, u2 = pmf.wilson(18, 53, z)
        d = 18 / 53 - 12 / 52
        low = d - z * (l2 * (1 - l2) / 53 + u1 * (1 - u1) / 52) ** 0.5
        high = d + z * (u2 * (1 - u2) / 53 + l1 * (1 - l1) / 52) ** 0.5
        got = pmf.newcombe_diff(12, 52, 18, 53, z)
        self.assertAlmostEqual(got[1], low, places=9)
        self.assertAlmostEqual(got[2], high, places=9)

    def test_waves_fixture_cannot_tell(self):
        want = expected("waves")
        got = run_json(FIXTURES / "waves.input.csv", "--period-col", "wave", "--compare", want["compare"])
        self.assertEqual(got["counts"], want["counts"])
        cmp_ = got["comparison"]
        self.assert_block(cmp_["earlier"], want["earlier"])
        self.assert_block(cmp_["later"], want["later"])
        for key in ("change_points", "ci_low_points", "ci_high_points"):
            self.assertAlmostEqual(cmp_[key], want[key], delta=0.1001, msg=key)
        self.assertEqual(cmp_["verdict"], want["verdict"])
        self.assertEqual(cmp_["rows_without_period"], want["rows_without_period"])
        self.assertIn("new baseline", cmp_["rule"])
        self.assertTrue(cmp_["verdict_text"].startswith("Cannot tell"))

    def test_previous_counts_detects_a_clear_change(self):
        got = run_json("--counts", "very=45,somewhat=30,not=25", "--previous-counts", "very=20,somewhat=40,not=40")
        cmp_ = got["comparison"]
        self.assertEqual(cmp_["verdict"], "increased")
        self.assertAlmostEqual(cmp_["change_points"], 25.0, delta=0.1001)
        self.assertAlmostEqual(cmp_["ci_low_points"], 12.1, delta=0.1001)
        self.assertAlmostEqual(cmp_["ci_high_points"], 36.8, delta=0.1001)

    def test_decrease_is_reported_as_decreased(self):
        got = run_json("--counts", "very=20,somewhat=40,not=40", "--previous-counts", "very=45,somewhat=30,not=25")
        self.assertEqual(got["comparison"]["verdict"], "decreased")
        self.assertAlmostEqual(got["comparison"]["ci_high_points"], -12.1, delta=0.1001)

    def test_period_order_is_never_guessed(self):
        proc = run(FIXTURES / "waves.input.csv", "--period-col", "wave")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--compare", proc.stderr)

    def test_unknown_period_lists_those_found(self):
        proc = run(FIXTURES / "waves.input.csv", "--period-col", "wave", "--compare", "2026-Q1,2026-Q3")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("2026-Q3", proc.stderr)
        self.assertIn("2026-Q2", proc.stderr)

    def test_readable_output_shows_the_comparison_rule(self):
        proc = run(FIXTURES / "waves.input.csv", "--period-col", "wave", "--compare", "2026-Q1,2026-Q2")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Change between waves", proc.stdout)
        self.assertIn("new baseline", proc.stdout)
        self.assertIn("2 answers had no period", proc.stdout)

    # --- counts input ---
    def test_counts_input_equals_the_basic_fixture(self):
        want = expected("basic")
        got = run_json("--counts", "very=16,somewhat=14,not=10,na=8,blank=2")
        self.assertEqual(got["counts"], want["counts"])
        from_csv = run_json(FIXTURES / "basic.input.csv")
        self.assertEqual(got["score"], from_csv["score"])
        self.assertEqual(got["pct_with_na_in_base"], from_csv["pct_with_na_in_base"])

    def test_counts_errors(self):
        for bad, text in (
            ("very=16,somewhat=14", "missing: not"),
            ("very=16,somewhat=14,not=x", "not a whole number"),
            ("very=16,somewhat=14,not=3,maybe=2", "unknown key"),
            ("very=16,very=2,somewhat=1,not=1", "given twice"),
            ("very=0,somewhat=0,not=0,na=4", "No score"),
        ):
            proc = run("--counts", bad)
            self.assertEqual(proc.returncode, 2, bad)
            self.assertIn(text, proc.stderr, bad)

    def test_counts_and_file_are_exclusive_and_one_is_required(self):
        self.assertEqual(run(FIXTURES / "basic.input.csv", "--counts", "very=1,somewhat=1,not=1").returncode, 2)
        self.assertEqual(run().returncode, 2)
        proc = run("--counts", "very=1,somewhat=1,not=1", "--segment-col", "persona")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--segment-col", proc.stderr)

    # --- several segment columns ---
    def test_two_segment_columns_and_caution(self):
        want = expected("multi_segment")
        got = run_json(FIXTURES / "multi_segment.input.csv", "--segment-col", "persona", "--segment-col", "plan")
        self.assertEqual([t["column"] for t in got["segment_tables"]], [t["column"] for t in want["tables"]])
        for got_table, want_table in zip(got["segment_tables"], want["tables"]):
            self.assertEqual(len(got_table["segments"]), len(want_table["segments"]))
            for got_seg, want_seg in zip(got_table["segments"], want_table["segments"]):
                self.assert_block(got_seg, want_seg)
        self.assertTrue(got["multiple_comparison_note"].startswith(f'{want["segment_intervals_read"]} segment intervals'))
        text = run(FIXTURES / "multi_segment.input.csv", "--segment-col", "persona", "--segment-col", "plan").stdout
        self.assertIn("Segments by persona", text)
        self.assertIn("Segments by plan", text)
        self.assertIn("by chance", text)

    def test_focus_needs_exactly_one_segment_column(self):
        proc = run(FIXTURES / "multi_segment.input.csv", "--segment-col", "persona", "--segment-col", "plan", "--focus-segments", "Founder")
        self.assertEqual(proc.returncode, 2)

    # --- accounts ---
    def test_one_vote_per_account(self):
        want = expected("accounts")
        got = run_json(FIXTURES / "accounts.input.csv", "--account-col", "account")
        self.assertEqual(got["counts"], want["counts"])
        self.assert_block(got["score"], want["score"])
        self.assert_block(got["accounts"], want["accounts"])
        self.assertIn("skill's convention", got["accounts"]["vote_rule"])
        self.assertIn("One vote per account", run(FIXTURES / "accounts.input.csv", "--account-col", "account").stdout)

    # --- non-standard wording ---
    def test_nonstandard_wording_is_not_an_unknown_label(self):
        want = expected("nonstandard")
        proc = run(FIXTURES / "nonstandard.input.csv")
        self.assertEqual(proc.returncode, want["without_map"]["exit_code"])
        for text in want["without_map"]["stderr_contains"]:
            self.assertIn(text, proc.stderr)
        self.assertNotIn("Unknown answer labels", proc.stderr)

    def test_mapped_nonstandard_wording_drops_the_benchmark_verdict(self):
        want = expected("nonstandard")
        args = [arg for pair in want["map"] for arg in ("--map", pair)]
        got = run_json(FIXTURES / "nonstandard.input.csv", *args)
        self.assert_block(got["score"], want["score"])
        self.assertEqual(got["benchmark_comparable"], want["benchmark_comparable"])
        self.assertTrue(got["verdict_text"].startswith("Not compared"))
        self.assertTrue(any("not comparable" in flag for flag in got["flags"]))

    def test_rating_scale_is_flagged_even_when_mapped(self):
        path = self.write_csv(["pmf_score"], [[str(n)] for n in (1, 2, 3, 4, 5, 5, 4)])
        proc = run(path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Non-standard answer wording", proc.stderr)
        got = run_json(path, "--map", "5=very", "--map", "4=somewhat", "--map", "3=somewhat", "--map", "2=not", "--map", "1=not")
        self.assertFalse(got["benchmark_comparable"])
        self.assertEqual(got["score"]["verdict"], "not_comparable")

    def test_four_numeric_codes_stay_comparable(self):
        got = run_json(FIXTURES / "coded.input.csv", "--map", "1=very", "--map", "2=somewhat", "--map", "3=not", "--map", "4=na")
        self.assertTrue(got["benchmark_comparable"])

    # --- response rate and the denominator note ---
    def test_low_response_rate_is_flagged(self):
        got = run_json("--counts", "very=16,somewhat=14,not=10,na=8", "--invited", "600")
        self.assertEqual(got["response_rate"]["answered"], 48)
        self.assertAlmostEqual(got["response_rate"]["pct"], 8.0, delta=0.05)
        self.assertTrue(got["response_rate"]["low"])
        self.assertTrue(any("under 10%" in flag for flag in got["flags"]))

    def test_normal_response_rate_is_not_flagged(self):
        got = run_json("--counts", "very=16,somewhat=14,not=10,na=8", "--invited", "200")
        self.assertAlmostEqual(got["response_rate"]["pct"], 24.0, delta=0.05)
        self.assertFalse(got["response_rate"]["low"])
        self.assertFalse(any("Response rate" in flag for flag in got["flags"]))

    def test_invited_smaller_than_answered_is_an_error(self):
        proc = run("--counts", "very=16,somewhat=14,not=10", "--invited", "10")
        self.assertEqual(proc.returncode, 2)

    def test_denominator_practice_is_printed(self):
        proc = run(FIXTURES / "basic.input.csv")
        self.assertIn("CRV", proc.stdout)
        self.assertIn("Pendo", proc.stdout)


if __name__ == "__main__":
    unittest.main()
