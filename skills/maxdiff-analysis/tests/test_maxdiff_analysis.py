"""Tests for scripts/maxdiff_analysis.py. Run from the skill folder: python3 -m unittest discover -s tests

Every expected number below is worked out in fixtures/README.md without the script (hand arithmetic or a
closed-form maximum-likelihood estimate), except the synthetic recovery test, which compares the estimates
with the known utilities the generator used.
"""
import importlib.util
import json
import math
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "maxdiff_analysis.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mda = _load("maxdiff_analysis", SCRIPT)
generator = _load("generate_fixtures", FIXTURES / "generate_fixtures.py")


def analyse(*argv):
    """Run the analysis in-process and return the report dict."""
    return mda.run(mda.build_parser().parse_args([str(a) for a in argv]))


def by_item(group):
    return {row["item"]: row for row in group["items"]}


def cli(*argv):
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *[str(a) for a in argv]], capture_output=True, text=True
    )


class CountingTest(unittest.TestCase):
    """fixtures/README.md, "counts": 3 respondents x 4 sets of 3 items, counted by hand."""

    EXPECTED = {  # item: (shown, best, worst)
        "A": (9, 6, 1),
        "B": (9, 3, 3),
        "C": (9, 2, 3),
        "D": (9, 1, 5),
    }

    def check_counts(self, report):
        rows = by_item(report["overall"])
        for item, (shown, best, worst) in self.EXPECTED.items():
            row = rows[item]
            self.assertEqual((row["shown"], row["best"], row["worst"]), (shown, best, worst), item)
            self.assertAlmostEqual(row["best_rate"], best / shown, places=12)
            self.assertAlmostEqual(row["worst_rate"], worst / shown, places=12)
        self.assertAlmostEqual(rows["A"]["bw_score"], 5 / 9, places=12)
        self.assertAlmostEqual(rows["B"]["bw_score"], 0.0, places=12)
        self.assertAlmostEqual(rows["C"]["bw_score"], -1 / 9, places=12)
        self.assertAlmostEqual(rows["D"]["bw_score"], -4 / 9, places=12)

    def test_long_format_counts(self):
        report = analyse(FIXTURES / "counts.input.csv", "--no-logit", "--bootstrap", 0)
        self.check_counts(report)
        self.assertEqual(report["input"]["format"], "long")
        self.assertEqual(report["input"]["sets_valid"], 12)
        self.assertEqual(report["input"]["sets_excluded"], 0)
        self.assertEqual([row["item"] for row in report["overall"]["items"]], ["A", "B", "C", "D"])
        self.assertEqual([row["rank"] for row in report["overall"]["items"]], [1, 2, 3, 4])
        self.assertEqual(report["overall"]["logit"]["status"], "skipped")
        self.assertIsNone(report["overall"]["items"][0]["share"])

    def test_wide_format_gives_the_same_counts(self):
        report = analyse(FIXTURES / "counts_wide.input.csv", "--no-logit", "--bootstrap", 0)
        self.assertEqual(report["input"]["format"], "wide")
        self.check_counts(report)

    def test_design_file_gives_the_same_counts(self):
        report = analyse(
            FIXTURES / "counts_responses.input.csv", "--design", FIXTURES / "counts_design.csv",
            "--no-logit", "--bootstrap", 0,
        )
        self.check_counts(report)

    def test_position_coded_choices_with_design(self):
        report = analyse(
            FIXTURES / "counts_positions.input.csv", "--design", FIXTURES / "counts_design.csv",
            "--choice-coding", "position", "--no-logit", "--bootstrap", 0,
        )
        self.check_counts(report)

    def test_one_row_per_respondent_with_design(self):
        report = analyse(
            FIXTURES / "counts_by_respondent.input.csv", "--design", FIXTURES / "counts_design.csv",
            "--no-logit", "--bootstrap", 0,
        )
        self.assertEqual(report["input"]["format"], "respondent")
        self.assertEqual(report["input"]["sets_valid"], 12)
        self.check_counts(report)

    def test_delimited_shown_items_cell(self):
        report = analyse(FIXTURES / "counts_cell.input.csv", "--shown-col", "set_items", "--no-logit", "--bootstrap", 0)
        self.assertEqual(report["input"]["format"], "wide")
        self.check_counts(report)
        by_position = analyse(FIXTURES / "counts_cell.input.csv", "--shown-col", "set_items", "--shown-sep", ";",
                              "--no-logit", "--bootstrap", 0, "--segment-col", "segment")
        self.assertEqual(by_position["segments"]["smb"]["n_respondents"], 2)

    def test_three_input_shapes_agree_on_the_logit(self):
        long = analyse(FIXTURES / "counts.input.csv", "--bootstrap", 0)
        wide = analyse(FIXTURES / "counts_wide.input.csv", "--bootstrap", 0)
        joined = analyse(
            FIXTURES / "counts_responses.input.csv", "--design", FIXTURES / "counts_design.csv", "--bootstrap", 0
        )
        for other in (wide, joined):
            for item, row in by_item(long["overall"]).items():
                self.assertAlmostEqual(row["utility"], by_item(other["overall"])[item]["utility"], places=9)

    def test_segment_counts(self):
        report = analyse(FIXTURES / "counts.input.csv", "--segment-col", "segment", "--bootstrap", 0)
        smb, ent = by_item(report["segments"]["smb"]), by_item(report["segments"]["ent"])
        self.assertEqual(report["segments"]["smb"]["n_respondents"], 2)
        self.assertEqual(report["segments"]["ent"]["n_respondents"], 1)
        for item, expected in {"A": 3 / 6, "B": 3 / 6, "C": -1 / 6, "D": -5 / 6}.items():
            self.assertAlmostEqual(smb[item]["bw_score"], expected, places=12)
        for item, expected in {"A": 2 / 3, "B": -1.0, "C": 0.0, "D": 1 / 3}.items():
            self.assertAlmostEqual(ent[item]["bw_score"], expected, places=12)
        # A and B tie on the counting score in smb but the logit separates them, so ranks follow shares.
        self.assertEqual(report["segments"]["smb"]["ranked_by"], "share")

    def test_segment_difference_and_adjacent_pairs(self):
        # fixtures/README.md, "differences": ent minus smb on the counting score, by hand.
        report = analyse(FIXTURES / "counts.input.csv", "--segment-col", "segment", "--bootstrap", 200, "--no-logit")
        (block,) = report["segment_differences"]
        self.assertEqual(block["segments"], ["ent", "smb"])
        self.assertEqual(block["metric"], "bw_score")
        rows = {row["item"]: row for row in block["items"]}
        for item, expected in {"A": 1 / 6, "B": -3 / 2, "C": 1 / 6, "D": 7 / 6}.items():
            self.assertAlmostEqual(rows[item]["difference"], expected, places=12)
        # ent has one respondent: a bootstrap cannot resample one person, so ent has no intervals and the
        # differences with it get none either (a zero-width interval would mark every gap as real).
        self.assertIsNone(rows["B"]["difference_ci"])
        self.assertIsNone(rows["B"]["excludes_zero"])
        self.assertTrue(any("Segment ent: Only 1 respondent" in w for w in report["warnings"]))
        pairs = report["segments"]["ent"]["adjacent_pairs"]
        self.assertEqual([(p["higher"], p["lower"]) for p in pairs], [("A", "D"), ("D", "C"), ("C", "B")])
        self.assertAlmostEqual(pairs[0]["difference"], 1 / 3, places=12)
        self.assertIsNone(pairs[0]["difference_ci"])
        overall = report["overall"]["adjacent_pairs"]
        self.assertAlmostEqual(overall[0]["difference"], 5 / 9, places=12)
        self.assertEqual(overall[0]["metric"], "bw_score")

    def test_many_failed_replicates_withhold_logit_intervals(self):
        report = analyse(FIXTURES / "counts.input.csv", "--bootstrap", 200)
        boot = report["overall"]["bootstrap"]
        self.assertGreater(boot["logit_replicates_failed_share"], mda.MAX_FAILED_REPLICATE_SHARE)
        self.assertEqual(boot["logit_replicates_failed"], round(200 * boot["logit_replicates_failed_share"]))
        self.assertEqual(boot["logit_intervals"], "unreliable")
        for row in report["overall"]["items"]:
            self.assertIsNone(row["share_ci"])
            self.assertIsNone(row["utility_ci"])
            self.assertIsNotNone(row["bw_score_ci"])
            self.assertIsNotNone(row["share"])
        self.assertTrue(any("intervals are unreliable" in w for w in report["warnings"]))
        self.assertEqual(report["overall"]["adjacent_pairs"][0]["metric"], "bw_score")

    def test_segment_below_minimum_base_is_flagged(self):
        report = analyse(FIXTURES / "counts.input.csv", "--segment-col", "segment", "--bootstrap", 0)
        self.assertTrue(report["segments"]["smb"]["below_min_base"])
        self.assertTrue(any("Segment smb: Base of 2 respondents is below 200" in w for w in report["warnings"]))
        relaxed = analyse(FIXTURES / "counts.input.csv", "--segment-col", "segment", "--bootstrap", 0, "--min-base", 2)
        self.assertNotIn("below_min_base", relaxed["segments"]["smb"])
        self.assertTrue(relaxed["segments"]["ent"]["below_min_base"])

    def test_segment_with_separation_keeps_counts_and_reports_why(self):
        # In segment "ent", B is worst in all three of its sets and never best.
        report = analyse(FIXTURES / "counts.input.csv", "--segment-col", "segment", "--bootstrap", 0)
        ent = report["segments"]["ent"]
        self.assertEqual(ent["logit"]["status"], "not_estimated")
        self.assertIn("separation", ent["logit"]["reason"])
        self.assertIn("[B]", ent["logit"]["reason"])
        self.assertEqual(ent["ranked_by"], "bw_score")
        self.assertEqual([row["item"] for row in ent["items"]], ["A", "D", "C", "B"])
        self.assertEqual(report["overall"]["logit"]["status"], "ok")

    def test_respondent_scores(self):
        report = analyse(FIXTURES / "counts.input.csv", "--no-logit", "--bootstrap", 0,
                         "--respondent-scores", "--segment-col", "segment")
        people = {p["respondent"]: p for p in report["respondents"]}
        self.assertEqual(people["r1"]["sets"], 4)
        self.assertEqual(people["r1"]["segment"], "smb")
        for item, expected in {"A": 1.0, "B": 1 / 3, "C": -1 / 3, "D": -1.0}.items():
            self.assertAlmostEqual(people["r1"]["bw_score"][item], expected, places=12)
        for item, expected in {"A": 2 / 3, "B": -1.0, "C": 0.0, "D": 1 / 3}.items():
            self.assertAlmostEqual(people["r3"]["bw_score"][item], expected, places=12)
        self.assertNotIn("respondents", analyse(FIXTURES / "counts.input.csv", "--no-logit", "--bootstrap", 0))


class ClosedFormLogitTest(unittest.TestCase):
    """fixtures/README.md, "logit_pairs" and "logit_sequential": maximum-likelihood values derived by hand."""

    def test_pairs_sequential_model(self):
        report = analyse(FIXTURES / "logit_pairs.input.csv", "--bootstrap", 0)
        logit = report["overall"]["logit"]
        self.assertEqual(logit["reference_item"], "B")
        self.assertAlmostEqual(logit["reference_coded"]["A"]["utility"], math.log(3), places=8)
        self.assertAlmostEqual(logit["reference_coded"]["A"]["se"], math.sqrt(1 / 15 + 1 / 5), places=8)
        self.assertAlmostEqual(logit["log_likelihood"], 15 * math.log(0.75) + 5 * math.log(0.25), places=8)
        self.assertAlmostEqual(logit["log_likelihood_null"], 20 * math.log(0.5), places=8)
        rows = by_item(report["overall"])
        self.assertAlmostEqual(rows["A"]["utility"], math.log(3) / 2, places=8)
        self.assertAlmostEqual(rows["B"]["utility"], -math.log(3) / 2, places=8)
        self.assertAlmostEqual(rows["A"]["utility_se"], math.sqrt(1 / 15 + 1 / 5) / 2, places=8)
        self.assertAlmostEqual(rows["A"]["share"], 75.0, places=6)
        self.assertAlmostEqual(rows["B"]["share"], 25.0, places=6)
        self.assertAlmostEqual(rows["A"]["bw_score"], 0.5, places=12)

    def test_pairs_fit_statistics(self):
        # 40 choice tasks: 20 best choices (15 at p = 0.75, 5 at 0.25) and 20 worst choices that have
        # one alternative left (probability 1). Under random choice: 20 at 1/2 and 20 at 1.
        logit = analyse(FIXTURES / "logit_pairs.input.csv", "--bootstrap", 0)["overall"]["logit"]
        self.assertEqual(logit["choice_tasks"], 40)
        self.assertAlmostEqual(logit["rlh"], (0.75 ** 15 * 0.25 ** 5) ** (1 / 40), places=10)  # 0.754902
        self.assertAlmostEqual(logit["rlh"], 0.754902, places=6)
        self.assertAlmostEqual(logit["rlh_chance"], math.sqrt(0.5), places=10)  # 0.707107
        self.assertAlmostEqual(logit["mcfadden_r2"], 1 - 11.246703 / 13.862944, places=6)  # 0.188722
        self.assertAlmostEqual(logit["lr_chi_square"], 2 * (13.862944 - 11.246703), places=5)  # 5.232482
        self.assertEqual(logit["lr_degrees_of_freedom"], 1)
        # Best-only: 20 tasks, chance 1/2.
        best_only = analyse(FIXTURES / "logit_pairs.input.csv", "--bootstrap", 0, "--model", "best-only")
        self.assertEqual(best_only["overall"]["logit"]["choice_tasks"], 20)
        self.assertAlmostEqual(best_only["overall"]["logit"]["rlh_chance"], 0.5, places=10)
        self.assertAlmostEqual(best_only["overall"]["logit"]["rlh"], (0.75 ** 15 * 0.25 ** 5) ** (1 / 20), places=10)

    def test_sequential_fit_statistics(self):
        logit = analyse(FIXTURES / "logit_sequential.input.csv", "--bootstrap", 0)["overall"]["logit"]
        counts = [20, 40, 6, 24, 5, 10]
        loglik = sum(n * math.log(n / 105) for n in counts)  # saturated: fitted = observed proportions
        self.assertAlmostEqual(logit["log_likelihood"], loglik, places=8)
        self.assertAlmostEqual(logit["log_likelihood_null"], 105 * math.log(1 / 6), places=8)
        self.assertAlmostEqual(logit["rlh_chance"], math.sqrt(1 / 6), places=10)  # sqrt(1/3 * 1/2)
        self.assertAlmostEqual(logit["rlh"], math.exp(loglik / 210), places=10)
        self.assertEqual(logit["lr_degrees_of_freedom"], 2)
        marginal = analyse(FIXTURES / "logit_sequential.input.csv", "--bootstrap", 0, "--model", "marginal")
        self.assertAlmostEqual(marginal["overall"]["logit"]["rlh_chance"], 1 / 3, places=10)

    def test_pairs_probability_scale(self):
        report = analyse(FIXTURES / "logit_pairs.input.csv", "--bootstrap", 0, "--share-scale", "probability")
        rows = by_item(report["overall"])
        root3 = math.sqrt(3)
        self.assertAlmostEqual(rows["A"]["share"], 100 * root3 / (root3 + 1), places=6)  # 63.40
        self.assertAlmostEqual(rows["B"]["share"], 100 / (root3 + 1), places=6)  # 36.60

    def test_pairs_marginal_model(self):
        # With two items, "B is worst out of {A, B}" has the same probability as "A is best", so the
        # likelihood is the best-choice likelihood squared: same estimate, half the variance.
        report = analyse(FIXTURES / "logit_pairs.input.csv", "--bootstrap", 0, "--model", "marginal")
        coded = report["overall"]["logit"]["reference_coded"]
        self.assertAlmostEqual(coded["A"]["utility"], math.log(3), places=8)
        # The doubled information is not real (the worst choice repeats the best one), so the model SE and
        # the chi-square test are withheld for this composite likelihood.
        self.assertIsNone(coded["A"]["se"])
        self.assertIsNone(report["overall"]["logit"]["lr_chi_square"])
        self.assertIsNone(report["overall"]["items"][0]["utility_se"])

    def test_marginal_model_on_synthetic_data_is_close_to_sequential(self):
        sequential = by_item(analyse(FIXTURES / "synthetic.input.csv", "--bootstrap", 0)["overall"])
        marginal = analyse(FIXTURES / "synthetic.input.csv", "--bootstrap", 0, "--model", "marginal")
        self.assertEqual([row["item"] for row in marginal["overall"]["items"]], sorted(generator.TRUE_UTILITIES))
        for item, row in by_item(marginal["overall"]).items():
            self.assertLess(abs(row["utility"] - sequential[item]["utility"]), 0.25, item)

    def test_sequential_model_recovers_exact_utilities(self):
        report = analyse(FIXTURES / "logit_sequential.input.csv", "--bootstrap", 0)
        logit = report["overall"]["logit"]
        coded = logit["reference_coded"]
        self.assertAlmostEqual(coded["A"]["utility"], 2 * math.log(2), places=8)
        self.assertAlmostEqual(coded["B"]["utility"], math.log(2), places=8)
        self.assertEqual(coded["C"]["utility"], 0.0)
        # Information matrix worked by hand: I_AA = 3554/105, I_BB = 800/21, I_AB = -430/21.
        i_aa, i_bb, i_ab = 3554 / 105, 800 / 21, -430 / 21
        det = i_aa * i_bb - i_ab * i_ab
        self.assertAlmostEqual(coded["A"]["se"], math.sqrt(i_bb / det), places=8)  # 0.209236
        self.assertAlmostEqual(coded["B"]["se"], math.sqrt(i_aa / det), places=8)  # 0.197226
        self.assertAlmostEqual(coded["A"]["se"], 0.209236, places=6)
        self.assertAlmostEqual(coded["B"]["se"], 0.197226, places=6)
        rows = by_item(report["overall"])
        self.assertAlmostEqual(rows["A"]["utility"], math.log(2), places=8)
        self.assertAlmostEqual(rows["B"]["utility"], 0.0, places=8)
        self.assertAlmostEqual(rows["C"]["utility"], -math.log(2), places=8)
        self.assertAlmostEqual(rows["A"]["share"], 400 / 7, places=6)
        self.assertAlmostEqual(rows["B"]["share"], 200 / 7, places=6)
        self.assertAlmostEqual(rows["C"]["share"], 100 / 7, places=6)
        # Zero-centred SE by hand: Var(u_A - mean) with mean = (u_A + u_B + 0)/3.
        v_aa, v_bb, v_ab = i_bb / det, i_aa / det, -i_ab / det
        var_a = (4 * v_aa + v_bb - 4 * v_ab) / 9
        var_c = (v_aa + v_bb + 2 * v_ab) / 9
        self.assertAlmostEqual(rows["A"]["utility_se"], math.sqrt(var_a), places=8)
        self.assertAlmostEqual(rows["C"]["utility_se"], math.sqrt(var_c), places=8)
        # Counting scores from the same table: A (60 - 11)/105, B (30 - 30)/105, C (15 - 64)/105.
        self.assertAlmostEqual(rows["A"]["bw_score"], 49 / 105, places=12)
        self.assertAlmostEqual(rows["B"]["bw_score"], 0.0, places=12)
        self.assertAlmostEqual(rows["C"]["bw_score"], -49 / 105, places=12)

    def test_best_only_model_equals_log_share_ratios(self):
        report = analyse(FIXTURES / "logit_sequential.input.csv", "--bootstrap", 0, "--model", "best-only")
        coded = report["overall"]["logit"]["reference_coded"]
        self.assertAlmostEqual(coded["A"]["utility"], math.log(60 / 15), places=8)
        self.assertAlmostEqual(coded["B"]["utility"], math.log(30 / 15), places=8)
        self.assertAlmostEqual(coded["A"]["se"], math.sqrt(1 / 60 + 1 / 15), places=8)
        self.assertAlmostEqual(coded["B"]["se"], math.sqrt(1 / 30 + 1 / 15), places=8)
        rows = by_item(report["overall"])
        self.assertAlmostEqual(rows["A"]["share"], 100 * 60 / 105, places=6)


class SyntheticRecoveryTest(unittest.TestCase):
    """fixtures/README.md, "synthetic": 120 simulated respondents with known utilities."""

    TOLERANCE = 0.25  # about three model standard errors (0.08) for this sample

    @classmethod
    def setUpClass(cls):
        cls.report = analyse(FIXTURES / "synthetic.input.csv", "--bootstrap", 100, "--segment-col", "segment")

    def test_fixture_file_matches_its_generator(self):
        for name, build in generator.FILES.items():
            self.assertEqual((FIXTURES / name).read_text(encoding="utf-8"), generator.render(build()), name)

    def test_utilities_recovered_within_tolerance(self):
        rows = by_item(self.report["overall"])
        truth = generator.TRUE_UTILITIES
        self.assertAlmostEqual(sum(truth.values()), 0.0, places=12)
        for item, true_value in truth.items():
            self.assertLess(abs(rows[item]["utility"] - true_value), self.TOLERANCE, item)
            self.assertLess(rows[item]["utility_se"], 0.1, item)

    def test_rank_order_recovered(self):
        expected = sorted(generator.TRUE_UTILITIES, key=generator.TRUE_UTILITIES.get, reverse=True)
        self.assertEqual([row["item"] for row in self.report["overall"]["items"]], expected)
        self.assertEqual([row["rank"] for row in self.report["overall"]["items"]], list(range(1, 10)))
        by_count = sorted(self.report["overall"]["items"], key=lambda row: -row["bw_score"])
        self.assertEqual([row["item"] for row in by_count], expected)

    def test_balanced_design_and_shares(self):
        rows = self.report["overall"]["items"]
        self.assertEqual({row["shown"] for row in rows}, {480})
        self.assertAlmostEqual(sum(row["share"] for row in rows), 100.0, places=9)
        self.assertAlmostEqual(sum(row["utility"] for row in rows), 0.0, places=9)
        self.assertAlmostEqual(sum(row["bw_score"] for row in rows), 0.0, places=9)
        self.assertFalse(any("not shown equally often" in w for w in self.report["warnings"]))

    def test_intervals_bracket_the_estimates(self):
        self.assertEqual(self.report["overall"]["bootstrap"]["replicates"], 100)
        self.assertEqual(self.report["overall"]["bootstrap"]["logit_replicates_failed"], 0)
        for row in self.report["overall"]["items"]:
            for key in ("bw_score", "utility", "share"):
                low, high = row[key + "_ci"]
                self.assertLess(low, row[key])
                self.assertGreater(high, row[key])

    def test_items_in_natural_order_and_average_share(self):
        self.assertEqual(self.report["overall"]["logit"]["reference_item"], "item9")
        self.assertAlmostEqual(self.report["overall"]["average_share"], 100 / 9, places=12)
        self.assertEqual(self.report["overall"]["bootstrap"]["logit_intervals"], "ok")
        self.assertEqual(self.report["overall"]["bootstrap"]["logit_replicates_failed_share"], 0.0)

    def test_adjacent_pairs_and_segment_differences_on_shares(self):
        pairs = self.report["overall"]["adjacent_pairs"]
        self.assertEqual(len(pairs), 8)
        self.assertEqual((pairs[0]["higher"], pairs[0]["lower"], pairs[0]["metric"]), ("item1", "item2", "share"))
        rows = by_item(self.report["overall"])
        self.assertAlmostEqual(pairs[0]["difference"], rows["item1"]["share"] - rows["item2"]["share"], places=12)
        self.assertEqual(pairs[0]["prob_higher_above"], 1.0)
        self.assertGreater(pairs[0]["difference_ci"][0], 0)
        for pair in pairs:
            self.assertTrue(0.5 <= pair["prob_higher_above"] <= 1.0)
            self.assertLess(pair["difference_ci"][0], pair["difference"])
            self.assertGreater(pair["difference_ci"][1], pair["difference"])
        (block,) = self.report["segment_differences"]
        self.assertEqual(block["segments"], ["new", "returning"])
        self.assertEqual(block["metric"], "share")
        new, returning = by_item(self.report["segments"]["new"]), by_item(self.report["segments"]["returning"])
        self.assertAlmostEqual(sum(row["difference"] for row in block["items"]), 0.0, places=9)
        for row in block["items"]:
            self.assertAlmostEqual(row["difference"], new[row["item"]]["share"] - returning[row["item"]]["share"], places=12)
            self.assertLess(row["difference_ci"][0], row["difference_ci"][1])

    def test_segments_have_logit_and_flag(self):
        for name in ("new", "returning"):
            group = self.report["segments"][name]
            self.assertEqual(group["n_respondents"], 60)
            self.assertEqual(group["logit"]["status"], "ok")
            self.assertTrue(group["below_min_base"])
            self.assertEqual(group["items"][0]["item"], "item1")

    def test_same_seed_same_result_and_other_seed_differs(self):
        args = [FIXTURES / "synthetic.input.csv", "--bootstrap", 30]
        first, again = analyse(*args, "--seed", 7), analyse(*args, "--seed", 7)
        other = analyse(*args, "--seed", 8)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(again, sort_keys=True))
        self.assertNotEqual(first["overall"]["items"][0]["share_ci"], other["overall"]["items"][0]["share_ci"])
        self.assertEqual(first["overall"]["items"][0]["share"], other["overall"]["items"][0]["share"])


class BadInputTest(unittest.TestCase):
    def test_bad_sets_are_counted_by_reason_and_left_out(self):
        report = analyse(FIXTURES / "bad_sets.input.csv", "--no-logit", "--bootstrap", 0)
        self.assertEqual(report["input"]["sets_read"], 20)
        self.assertEqual(report["input"]["sets_valid"], 12)
        self.assertEqual(report["input"]["sets_excluded"], 8)
        self.assertEqual(report["input"]["excluded_by_reason"], {
            "invalid_value": 1,
            "duplicate_item": 1,
            "fewer_than_two_items": 1,
            "best_not_exactly_one": 3,
            "worst_not_exactly_one": 1,
            "best_equals_worst": 1,
        })
        self.assertEqual(report["input"]["respondents_without_valid_sets"], ["r4"])
        self.assertEqual(report["overall"]["n_respondents"], 3)
        self.assertTrue(any("8 of 20 sets (40.0%) were excluded" in w for w in report["warnings"]))
        clean = analyse(FIXTURES / "counts.input.csv", "--no-logit", "--bootstrap", 0)
        self.assertEqual(report["overall"]["items"], clean["overall"]["items"])

    def test_bad_wide_sets(self):
        report = analyse(FIXTURES / "bad_wide.input.csv", "--no-logit", "--bootstrap", 0)
        self.assertEqual(report["input"]["excluded_by_reason"], {
            "duplicate_set": 1, "choice_not_shown": 1, "best_equals_worst": 1,
        })
        self.assertEqual(report["input"]["sets_valid"], 5)

    def test_missing_column_exits_2(self):
        result = cli(FIXTURES / "bad_missing_column.input.csv")
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing column(s) worst", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_missing_file_exits_2(self):
        result = cli(FIXTURES / "does_not_exist.csv")
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot read", result.stderr)

    def test_separation_exits_3_and_counts_still_run(self):
        result = cli(FIXTURES / "bad_separation.input.csv", "--bootstrap", 0)
        self.assertEqual(result.returncode, 3)
        self.assertIn("separation", result.stderr)
        self.assertIn("[D]", result.stderr)
        self.assertIn("--no-logit", result.stderr)
        counts_only = cli(FIXTURES / "bad_separation.input.csv", "--bootstrap", 0, "--no-logit", "--json")
        self.assertEqual(counts_only.returncode, 0)
        rows = by_item(json.loads(counts_only.stdout)["overall"])
        self.assertEqual(rows["D"]["bw_score"], -1.0)

    def test_cli_text_and_json(self):
        text = cli(FIXTURES / "logit_pairs.input.csv", "--bootstrap", 0)
        self.assertEqual(text.returncode, 0)
        self.assertIn("Rank  Item  Shown  Best  Worst  B-W score  Utility     SE  Share %", text.stdout)
        self.assertIn("   1  A        20    15      5     +0.500   +0.549  0.258     75.0", text.stdout)
        self.assertIn("RLH 0.755 (chance 0.707)", text.stdout)
        self.assertIn("Reference-coded utilities (B = 0): A +1.099 (SE 0.516)", text.stdout)
        self.assertIn("Average share: 50.0", text.stdout)
        as_json = cli(FIXTURES / "logit_pairs.input.csv", "--bootstrap", 0, "--json")
        self.assertEqual(json.loads(as_json.stdout)["skill"], "maxdiff-analysis")

    def _write(self, text, name="input.csv"):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        path = pathlib.Path(folder) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_empty_and_header_only_files(self):
        with self.assertRaises(mda.InputError):
            analyse(self._write(""))
        with self.assertRaises(mda.InputError):
            analyse(self._write("respondent,set,item,best,worst\n"))

    def test_all_sets_invalid(self):
        path = self._write("respondent,set,item,best,worst\nr1,1,A,yes,no\nr1,1,B,no,yes\n")
        with self.assertRaises(mda.InputError) as caught:
            analyse(path)
        self.assertIn("invalid_value: 1", str(caught.exception))

    def test_respondent_in_two_segments(self):
        path = self._write(
            "respondent,segment,set,item,best,worst\n"
            "r1,x,1,A,1,0\nr1,x,1,B,0,1\nr1,y,2,A,1,0\nr1,y,2,B,0,1\n"
        )
        with self.assertRaises(mda.InputError) as caught:
            analyse(path, "--segment-col", "segment")
        self.assertIn("two segment values", str(caught.exception))

    def test_unknown_segment_column(self):
        with self.assertRaises(mda.InputError):
            analyse(FIXTURES / "counts.input.csv", "--segment-col", "plan")

    def test_custom_column_names_and_delimiter(self):
        text = (FIXTURES / "counts.input.csv").read_text(encoding="utf-8")
        header, body = text.split("\n", 1)
        path = self._write("id;seg;task;feature;most;least\n" + body.replace(",", ";"))
        report = analyse(path, "--delimiter", ";", "--respondent-col", "id", "--set-col", "task",
                         "--item-col", "feature", "--best-col", "most", "--worst-col", "least",
                         "--no-logit", "--bootstrap", 0)
        self.assertAlmostEqual(by_item(report["overall"])["A"]["bw_score"], 5 / 9, places=12)

    def test_set_missing_from_design_is_excluded(self):
        responses = self._write(
            "respondent,version,set,best,worst\nr1,1,1,A,C\nr1,1,2,A,D\nr3,2,1,A,C\nr2,1,9,A,B\n", "responses.csv"
        )
        report = analyse(responses, "--design", FIXTURES / "counts_design.csv", "--no-logit", "--bootstrap", 0)
        self.assertEqual(report["input"]["excluded_by_reason"], {"set_not_in_design": 2})
        self.assertEqual(report["input"]["sets_valid"], 2)
        self.assertEqual(report["input"]["respondents_without_valid_sets"], ["r3", "r2"])

    def test_position_coding_errors(self):
        responses = self._write(
            "respondent,version,set,best,worst\nr1,1,1,1,3\nr1,1,2,1,4\nr1,1,3,first,3\nr1,1,4,2,2\n", "responses.csv"
        )
        report = analyse(responses, "--design", FIXTURES / "counts_design.csv", "--choice-coding", "position",
                         "--no-logit", "--bootstrap", 0, "--allow-exclusions")
        self.assertEqual(report["input"]["excluded_by_reason"], {
            "invalid_value": 1, "choice_not_shown": 1, "best_equals_worst": 1,
        })
        self.assertEqual(report["input"]["sets_valid"], 1)
        with self.assertRaises(mda.InputError):
            analyse(FIXTURES / "counts.input.csv", "--choice-coding", "position")

    def test_position_coding_in_shown_columns_and_respondent_layout(self):
        wide = self._write("respondent,set,item1,item2,item3,best,worst\nr1,1,A,B,C,1,3\nr1,2,A,B,D,2,1\n")
        report = analyse(wide, "--choice-coding", "position", "--no-logit", "--bootstrap", 0)
        rows = by_item(report["overall"])
        self.assertEqual((rows["A"]["best"], rows["A"]["worst"], rows["B"]["best"], rows["C"]["worst"]), (1, 1, 1, 1))
        per_person = self._write(
            "id,version,best_1,worst_1,best_2,worst_2,best_3,worst_3,best_4,worst_4\n"
            "r1,1,1,3,1,3,1,3,1,3\nr2,1,2,3,1,3,2,1,1,3\nr3,1,1,2,3,2,1,2,2,1\n"
        )
        report = analyse(per_person, "--design", FIXTURES / "counts_design.csv", "--choice-coding", "position",
                         "--respondent-col", "id", "--best-prefix", "best", "--worst-prefix", "worst",
                         "--no-logit", "--bootstrap", 0)
        self.assertEqual(report["input"]["format"], "respondent")
        self.assertAlmostEqual(by_item(report["overall"])["A"]["bw_score"], 5 / 9, places=12)
        self.assertAlmostEqual(by_item(report["overall"])["D"]["bw_score"], -4 / 9, places=12)

    def test_respondent_layout_needs_a_design_and_counts_skipped_sets(self):
        with self.assertRaises(mda.InputError) as caught:
            analyse(FIXTURES / "counts_by_respondent.input.csv")
        self.assertIn("--design", str(caught.exception))
        skipped = self._write("respondent,version,b1,w1,b2,w2\nr1,1,A,C,,\nr2,1,B,C,A,D\n")
        report = analyse(skipped, "--design", FIXTURES / "counts_design.csv", "--no-logit", "--bootstrap", 0)
        self.assertEqual(report["input"]["excluded_by_reason"], {"best_not_exactly_one": 1})
        self.assertEqual(report["input"]["sets_valid"], 3)

    def test_multi_version_design_needs_a_version_column(self):
        design = self._write("version,set,position,item\n1,1,1,A\n1,1,2,B\n2,1,1,B\n2,1,2,C\n", "design.csv")
        responses = self._write("respondent,set,best,worst\nr1,1,A,B\n", "responses.csv")
        with self.assertRaises(mda.InputError) as caught:
            analyse(responses, "--design", design)
        self.assertIn("2 versions", str(caught.exception))

    def test_unbalanced_design_warns(self):
        # A is shown in 3 sets, B and C in 2 each, D in 2.
        path = self._write(
            "respondent,set,item1,item2,item3,best,worst\n"
            "r1,1,A,B,C,A,C\nr1,2,A,B,D,B,D\nr1,3,A,C,D,D,A\n"
        )
        report = analyse(path, "--no-logit", "--bootstrap", 0)
        self.assertTrue(any("not shown equally often (2 to 3 times)" in w for w in report["warnings"]))

    def test_probability_scale_needs_one_set_size(self):
        path = self._write(
            "respondent,set,item1,item2,item3,best,worst\n"
            "r1,1,A,B,C,A,C\nr1,2,A,B,,B,A\nr1,3,B,C,,C,B\nr1,4,A,C,,C,A\n"
        )
        with self.assertRaises(mda.InputError) as caught:
            analyse(path, "--bootstrap", 0, "--share-scale", "probability")
        self.assertIn("--items-per-set", str(caught.exception))
        report = analyse(path, "--bootstrap", 0, "--share-scale", "probability", "--items-per-set", 3)
        self.assertEqual(report["input"]["items_per_set"], "2-3")  # the data's set sizes, not the option
        self.assertIn("a = 3", report["method"]["shares"])
        self.assertTrue(any("Sets show 2 to 3 items" in w for w in report["warnings"]))

    def test_bad_option_values(self):
        for extra in (["--bootstrap", -1], ["--ci", 100], ["--delimiter", "ab"]):
            with self.assertRaises(mda.InputError):
                analyse(FIXTURES / "counts.input.csv", *extra)


class NumericHelpersTest(unittest.TestCase):
    def test_cholesky_solve(self):
        # [[4, 2], [2, 3]] x = [10, 8] has the solution x = [1.75, 1.5] (by elimination).
        lower = mda.cholesky([[4.0, 2.0], [2.0, 3.0]])
        self.assertAlmostEqual(lower[0][0], 2.0)
        self.assertAlmostEqual(lower[1][0], 1.0)
        self.assertAlmostEqual(lower[1][1], math.sqrt(2.0))
        x = mda.cholesky_solve(lower, [10.0, 8.0])
        self.assertAlmostEqual(x[0], 1.75)
        self.assertAlmostEqual(x[1], 1.5)

    def test_cholesky_rejects_a_singular_matrix(self):
        self.assertIsNone(mda.cholesky([[1.0, 1.0], [1.0, 1.0]]))

    def test_percentile_linear_interpolation(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertAlmostEqual(mda.percentile(values, 50), 3.0)
        self.assertAlmostEqual(mda.percentile(values, 2.5), 1.1)
        self.assertAlmostEqual(mda.percentile(values, 97.5), 4.9)
        self.assertEqual(mda.percentile([7.0], 2.5), 7.0)

    def test_separation_groups(self):
        # 0 > 1 > 2 > 0 is one cycle; item 3 only ever loses.
        k = 4
        cycle = {0 * k + 1, 1 * k + 2, 2 * k + 0}
        self.assertEqual(len(mda.separation_groups(k, cycle | {3 * k + 0, 0 * k + 3})), 1)
        groups = mda.separation_groups(k, cycle | {0 * k + 3})
        self.assertEqual(groups, [[0, 1, 2], [3]])

    def test_shares_formulas(self):
        centred = [math.log(2), 0.0, -math.log(2)]
        preference = mda.shares(centred, "preference", None)
        self.assertAlmostEqual(preference[0], 400 / 7)
        # Probability scale with a = 4: 2/(2+3), 1/(1+3), 0.5/(0.5+3) = 0.4, 0.25, 1/7; sum 111/140.
        probability = mda.shares(centred, "probability", 4)
        self.assertAlmostEqual(probability[0], 100 * 0.4 / (111 / 140))
        self.assertAlmostEqual(probability[1], 100 * 0.25 / (111 / 140))
        self.assertAlmostEqual(sum(probability), 100.0)


class ReviewRegressionTest(unittest.TestCase):
    """Defects found in the 2026-11 review; each test failed before its fix."""

    def _write(self, text, name="input.csv"):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        path = pathlib.Path(folder) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_numbered_columns_out_of_order_keep_their_positions(self):
        path = self._write("respondent,set,item2,item1,item3,best,worst\nr,1,B,A,C,1,3\n")
        report = analyse(path, "--choice-coding", "position", "--no-logit", "--bootstrap", 0)
        self.assertEqual(by_item(report["overall"])["A"]["best"], 1)
        self.assertEqual(by_item(report["overall"])["B"]["best"], 0)
        self.assertEqual(by_item(report["overall"])["C"]["worst"], 1)

    def test_two_columns_for_one_position_are_rejected(self):
        path = self._write("respondent,set,item1,item_1,item2,best,worst\nr,1,A,B,C,A,C\n")
        with self.assertRaises(mda.InputError):
            analyse(path, "--no-logit", "--bootstrap", 0)

    def test_unpaired_or_repeated_task_columns_are_rejected(self):
        text = (FIXTURES / "counts_by_respondent.input.csv").read_text().splitlines()
        cut = "\n".join(",".join(line.split(",")[:10]) for line in text) + "\n"
        with self.assertRaises(mda.InputError) as caught:
            analyse(self._write(cut), "--design", FIXTURES / "counts_design.csv", "--no-logit", "--bootstrap", 0)
        self.assertIn("b4", str(caught.exception))
        path = self._write("respondent,version,b1,b01,w1\nr,1,A,A,C\n")
        with self.assertRaises(mda.InputError):
            analyse(path, "--design", FIXTURES / "counts_design.csv", "--no-logit", "--bootstrap", 0)

    def test_blocks_never_shown_together_are_not_called_separation(self):
        path = self._write("respondent,set,item1,item2,best,worst\n"
                           "r1,1,A,B,A,B\nr2,1,A,B,B,A\nr1,2,C,D,C,D\nr2,2,C,D,D,C\n")
        with self.assertRaises(mda.EstimationError) as caught:
            analyse(path, "--bootstrap", 0)
        self.assertIn("never shown in a set together", str(caught.exception))
        self.assertNotIn("separation", str(caught.exception))
        report = analyse(path, "--bootstrap", 0, "--no-logit")
        self.assertEqual(report["overall"]["item_groups"], [["A", "B"], ["C", "D"]])
        self.assertTrue(any("one overall ranking is not supported" in w for w in report["warnings"]))

    def test_label_with_superscript_digit_sorts(self):
        path = self._write("respondent,set,item,best,worst\nr,1,2\u00b2,1,0\nr,1,b,0,1\n")
        report = analyse(path, "--no-logit", "--bootstrap", 0)
        self.assertEqual(report["input"]["n_items"], 2)

    def test_semicolon_responses_and_a_comma_design(self):
        responses = self._write("respondent;version;set;best;worst\nr1;1;1;1;3\nr1;1;2;1;3\n", "r.csv")
        report = analyse(responses, "--design", FIXTURES / "counts_design.csv", "--choice-coding", "position",
                         "--no-logit", "--bootstrap", 0)
        self.assertEqual(report["input"]["sets_valid"], 2)

    def test_design_keeps_its_own_column_names(self):
        responses = self._write("respondent,version,task,best,worst\nr1,1,1,1,3\nr1,1,2,1,3\n", "r.csv")
        report = analyse(responses, "--design", FIXTURES / "counts_design.csv", "--set-col", "task",
                         "--choice-coding", "position", "--no-logit", "--bootstrap", 0)
        self.assertEqual(report["input"]["sets_valid"], 2)

    def test_one_respondent_gets_no_zero_width_intervals(self):
        report = analyse(FIXTURES / "logit_pairs.input.csv", "--bootstrap", 50, "--no-logit")
        self.assertGreater(report["overall"]["n_respondents"], 1)
        path = self._write("respondent,set,item,best,worst\nr,1,A,1,0\nr,1,B,0,1\nr,1,C,0,0\n"
                           "r,2,A,0,1\nr,2,B,1,0\nr,2,C,0,0\n")
        report = analyse(path, "--bootstrap", 50, "--no-logit")
        self.assertTrue(all(row["bw_score_ci"] is None for row in report["overall"]["items"]))
        self.assertTrue(all(pair["difference_ci"] is None for pair in report["overall"]["adjacent_pairs"]))
        self.assertTrue(any("Only 1 respondent" in w for w in report["warnings"]))

    def test_probability_scale_does_not_overflow(self):
        values = mda.shares([800.0, -800.0], "probability", 4)
        self.assertAlmostEqual(sum(values), 100.0)
        self.assertAlmostEqual(values[0], 100.0)

    def test_items_per_set_zero_is_rejected(self):
        with self.assertRaises(mda.InputError):
            analyse(FIXTURES / "logit_pairs.input.csv", "--bootstrap", 0, "--share-scale", "probability",
                    "--items-per-set", 0)

    def test_nan_position_is_an_invalid_value(self):
        responses = self._write("respondent,version,set,best,worst\nr1,1,1,NaN,3\nr1,1,2,1,3\nr1,1,3,1,2\n", "r.csv")
        report = analyse(responses, "--design", FIXTURES / "counts_design.csv", "--choice-coding", "position",
                         "--no-logit", "--bootstrap", 0)
        self.assertEqual(report["input"]["excluded_by_reason"], {"invalid_value": 1})

    def test_nul_bytes_and_blank_duplicate_headers_are_clear_errors(self):
        with self.assertRaises(mda.InputError) as caught:
            analyse(self._write("respondent,set,item,best,worst\x00\nr,1,A,1,0\n"))
        self.assertIn("NUL", str(caught.exception))
        with self.assertRaises(mda.InputError) as caught:
            analyse(self._write("respondent,set,item,best,worst,,\nr,1,A,1,0,,\n"))
        self.assertIn("(blank)", str(caught.exception))

    def test_best_worst_columns_are_not_mistaken_for_task_columns(self):
        # B1/W1 here are demographic columns; the missing --set-col must not switch to the respondent shape.
        path = self._write("respondent,task,B1,W1,item1,item2,item3,best,worst\nr,1,x,y,A,B,C,A,C\n")
        with self.assertRaises(mda.InputError) as caught:
            analyse(path, "--no-logit", "--bootstrap", 0)
        self.assertIn("missing column(s) set", str(caught.exception))

    def test_conflicting_shown_item_options_are_rejected(self):
        for extra in (["--shown-col", "x", "--shown-cols", "a,b"], ["--design", FIXTURES / "counts_design.csv",
                                                                     "--shown-cols", "item1,item2"]):
            with self.subTest(extra), self.assertRaises(mda.InputError):
                analyse(FIXTURES / "counts_wide.input.csv", *extra, "--no-logit", "--bootstrap", 0)

    def test_most_sets_excluded_stops_with_a_coding_hint(self):
        path = self._write("respondent,set,item1,item2,item3,best,worst\n"
                           "r1,1,A,B,C,1,3\nr1,2,B,C,D,2,1\nr1,3,A,C,D,3,2\n")
        with self.assertRaises(mda.InputError) as caught:
            analyse(path, "--no-logit", "--bootstrap", 0)
        self.assertIn("--choice-coding position", str(caught.exception))
        report = analyse(path, "--no-logit", "--bootstrap", 0, "--choice-coding", "position")
        self.assertEqual(report["input"]["sets_valid"], 3)

    def test_true_false_and_decimal_flags_are_read(self):
        path = self._write("respondent,set,item,best,worst\nr,1,A,TRUE,FALSE\nr,1,B,false,true\n"
                           "r,2,A,0.0,1.0\nr,2,B,1.0,0.0\n")
        report = analyse(path, "--no-logit", "--bootstrap", 0)
        self.assertEqual(report["input"]["sets_valid"], 2)
        self.assertTrue(any("read as 1 and 0" in n for n in report["input"]["notes"]))

    def test_text_report_names_anchoring_and_the_overall_base(self):
        result = subprocess.run([sys.executable, str(SCRIPT), str(FIXTURES / "counts.input.csv"), "--no-logit",
                                 "--bootstrap", "0"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Anchoring: not supported", result.stdout)
        self.assertIn("Hierarchical Bayes:", result.stdout)
        self.assertRegex(result.stdout, r"All respondents \(n=\d+\)  \[below minimum base\]")

    def test_reversed_pair_is_not_called_not_separated(self):
        group = {"items": [], "logit": {"status": "skipped"}, "adjacent_pairs": [
            {"higher": "A", "lower": "B", "metric": "bw_score", "difference": -0.2,
             "difference_ci": [-0.3, -0.1], "verdict": "reversed", "prob_higher_above": 0.0}]}
        text = mda.render_table({**group, "items": [{"rank": 1, "item": "A", "shown": 1, "best": 0, "worst": 0,
                                                     "bw_score": 0, "bw_score_ci": None, "utility": None,
                                                     "utility_ci": None, "utility_se": None, "share": None,
                                                     "share_ci": None}]})
        self.assertIn("reversed", text)
        self.assertNotIn("not separated", text)
        report = analyse(FIXTURES / "synthetic.input.csv", "--bootstrap", 50)
        self.assertTrue(all(pair["verdict"] in ("separated", "not separated", "reversed")
                            for pair in report["overall"]["adjacent_pairs"]))

    def test_rarely_shown_item_gets_no_counting_interval(self):
        lines = ["respondent,set,item,best,worst"]
        for r in range(30):
            lines += [f"r{r},1,A,1,0", f"r{r},1,B,0,1", f"r{r},1,C,0,0"]
        lines += ["r0,2,A,0,0", "r0,2,X,1,0", "r0,2,B,0,1"]
        report = analyse(self._write("\n".join(lines) + "\n"), "--no-logit", "--bootstrap", 200)
        self.assertIsNone(by_item(report["overall"])["X"]["bw_score_ci"])
        self.assertIsNotNone(by_item(report["overall"])["A"]["bw_score_ci"])
        self.assertTrue(any("counting-score" in w and "X" in w for w in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
