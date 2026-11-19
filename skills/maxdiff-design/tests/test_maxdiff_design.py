"""Tests for scripts/maxdiff_design.py. Run from the skill folder: python3 -m unittest discover -s tests"""
import csv
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "maxdiff_design.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def run_json(*args):
    result = run(*args, "--json")
    return result.returncode, json.loads(result.stdout)


def statuses(report, status):
    return [c["name"] for c in report["criteria"] if c["status"] == status]


class CheckFixturesTest(unittest.TestCase):
    """--check against designs whose diagnostics were worked out by hand (fixtures/README.md)."""

    def assert_matches(self, case, expected_exit, *extra):
        expected = json.loads((FIXTURES / f"{case}.expected.json").read_text())
        code, report = run_json("--check", FIXTURES / f"{case}.input.csv", *extra)
        self.assertEqual(code, expected_exit)
        d = report["diagnostics"]
        self.assertEqual(report["mode"], "check")
        self.assertEqual({k: report["parameters"][k] for k in expected["parameters"]}, expected["parameters"])
        self.assertEqual(report["is_bibd"], expected["is_bibd"])
        self.assertEqual(report["meets_criteria"], expected["meets_criteria"])
        self.assertAlmostEqual(d["times_shown_per_respondent"], expected["times_shown_per_respondent"], places=4)
        self.assertEqual(d["item_frequency"]["overall"], expected["item_frequency"])
        for key, value in expected["pair_frequency"].items():
            self.assertAlmostEqual(d["pair_frequency"][key], value, places=4, msg=key)
        self.assertEqual(d["position_frequency"]["overall"], expected["position_frequency"])
        self.assertEqual(d["connectivity"], expected["connectivity"])
        self.assertEqual(d["item_correlation"], expected["item_correlation"])
        self.assertEqual(statuses(report, "fail"), expected["statuses"]["fail"])
        self.assertEqual(statuses(report, "warn"), expected["statuses"]["warn"])
        return report

    def test_bibd_7_3_1(self):
        self.assert_matches("bibd_7_3_1", 0)

    def test_bibd_7_3_1_with_items_file(self):
        self.assert_matches("bibd_7_3_1", 0, FIXTURES / "items7.input.txt")

    def test_bibd_7_4_2(self):
        self.assert_matches("bibd_7_4_2", 0)

    def test_affine_plane_of_order_3(self):
        self.assert_matches("affine_9_3", 0)

    def test_published_bibd_in_wide_layout_with_ids(self):
        # The find.BIB(trt = 7, k = 4, b = 7) design printed in the support.BWS manual.
        report = self.assert_matches("published_bws_7_4", 0, FIXTURES / "fruit7.input.txt")
        self.assertTrue(any("wide layout" in note for note in report["notes"]))
        self.assertTrue(any("1-based ids" in note for note in report["notes"]))

    def test_unbalanced_is_flagged(self):
        report = self.assert_matches("unbalanced", 1)
        self.assertEqual(report["diagnostics"]["item_frequency"]["worst_version_range"], 2)
        self.assertEqual(report["diagnostics"]["position_frequency"]["max_spread"], 3)

    def test_unbalanced_text_report_says_so(self):
        result = run("--check", FIXTURES / "unbalanced.input.csv")
        self.assertEqual(result.returncode, 1)
        self.assertIn("DOES NOT meet the balance criteria", result.stdout)
        self.assertIn("FAIL  connectivity", result.stdout)

    def test_item_missing_from_design_fails_one_way(self):
        with tempfile.TemporaryDirectory() as tmp:
            items = pathlib.Path(tmp) / "items.txt"
            items.write_text("A\nB\nC\nD\nE\nF\nG\nH\n")
            code, report = run_json("--check", FIXTURES / "bibd_7_3_1.input.csv", items)
        self.assertEqual(code, 1)
        self.assertEqual(report["diagnostics"]["item_frequency"]["overall"]["H"], 0)
        self.assertIn("one-way balance within each version", statuses(report, "fail"))
        self.assertIn("connectivity", statuses(report, "fail"))


class CheckDefectsTest(unittest.TestCase):
    def check_text(self, text, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "design.csv"
            path.write_text(text)
            result = run("--check", path, *extra, "--json")
        return result

    def test_repeated_item_in_a_set_fails(self):
        text = "version,set,position,item\n" + "".join(
            f"1,{s},{p},{i}\n" for s, row in enumerate(["AAB", "BCD", "CDA", "DBC"], 1) for p, i in enumerate(row, 1))
        result = self.check_text(text)
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertIn("no item repeated within a set", statuses(report, "fail"))
        self.assertEqual(report["diagnostics"]["repeats_within_set"], 1)

    def test_unequal_set_sizes_fail(self):
        text = "version,set,position,item\n1,1,1,A\n1,1,2,B\n1,1,3,C\n1,2,1,A\n1,2,2,D\n"
        result = self.check_text(text)
        self.assertEqual(result.returncode, 1)
        self.assertIn("same shape in every set and version", statuses(json.loads(result.stdout), "fail"))

    def test_fixed_order_gets_positional_warning(self):
        # The (7,3,1) design with each set sorted alphabetically: balanced, but A is always first.
        sets = ["ABD", "BCE", "CDF", "DEG", "AEF", "BFG", "ACG"]
        text = "version,set,position,item\n" + "".join(
            f"1,{s},{p},{i}\n" for s, row in enumerate(sets, 1) for p, i in enumerate(row, 1))
        result = self.check_text(text)
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(report["is_bibd"])
        self.assertEqual(statuses(report, "warn"), ["positional balance"])
        self.assertEqual(report["diagnostics"]["position_frequency"]["overall"]["A"], [3, 0, 0])

    def test_header_is_case_insensitive_and_bom_tolerant(self):
        text = "﻿Version,Set,Position,Item\n" + (FIXTURES / "bibd_7_3_1.input.csv").read_text().split("\n", 1)[1]
        result = self.check_text(text)
        self.assertEqual(result.returncode, 0)

    def test_bad_inputs_exit_2_with_a_message(self):
        cases = {
            "missing column": "version,set,item\n1,1,A\n",
            "no set column": "version,item1,item2\n1,A,B\n",
            "not a number": "version,set,position,item\n1,x,1,A\n",
            "empty item": "version,set,position,item\n1,1,1,\n",
            "no rows": "version,set,position,item\n",
            "empty file": "",
            "zero position": "version,set,position,item\n1,1,0,A\n",
        }
        for name, text in cases.items():
            with self.subTest(name):
                result = self.check_text(text)
                self.assertEqual(result.returncode, 2)
                self.assertIn("maxdiff-design:", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_missing_file(self):
        result = run("--check", FIXTURES / "nope.csv")
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot read design file", result.stderr)

    def test_check_rejects_generation_options(self):
        result = run("--check", FIXTURES / "bibd_7_3_1.input.csv", "--per-set", "3")
        self.assertEqual(result.returncode, 2)


class GenerateTest(unittest.TestCase):
    def test_recommends_3k_over_k_and_uses_cyclic_bibd(self):
        code, report = run_json(FIXTURES / "items7.input.txt", "--per-set", "3")
        self.assertEqual(code, 0)
        self.assertEqual(report["parameters"], {"items": 7, "items_per_set": 3, "sets_per_version": 7, "versions": 10, "seed": 1})
        self.assertIn("Default 10", report["versions_rule"])
        self.assertIn("300", report["versions_rule"])
        self.assertEqual(report["recommendation"]["minimum_sets_for_3_exposures"], 7)
        self.assertEqual(report["method"], "cyclic-bibd")
        self.assertTrue(report["is_bibd"])
        d = report["diagnostics"]
        self.assertEqual(set(d["item_frequency"]["overall"].values()), {30})
        self.assertEqual((d["pair_frequency"]["min"], d["pair_frequency"]["max"]), (10, 10))
        self.assertEqual(d["pair_frequency"]["worst_version_range"], 0)
        self.assertEqual(d["position_frequency"]["max_spread"], 0)
        self.assertEqual(statuses(report, "fail") + statuses(report, "warn"), [])

    def test_each_version_of_the_cyclic_design_is_a_7_3_1_bibd(self):
        _code, report = run_json("--items", 7, "--per-set", 3, "--versions", 3)
        for version in (1, 2, 3):
            sets = {}
            for row in report["design"]:
                if row["version"] == version:
                    sets.setdefault(row["set"], set()).add(row["item"])
            self.assertEqual(len(sets), 7)
            pairs = {}
            for members in sets.values():
                self.assertEqual(len(members), 3)
                for a in members:
                    for b in members:
                        if a < b:
                            pairs[(a, b)] = pairs.get((a, b), 0) + 1
            self.assertEqual(len(pairs), 21)
            self.assertEqual(set(pairs.values()), {1})

    def test_7_4_2(self):
        code, report = run_json("--items", 7, "--per-set", 4, "--sets", 7, "--versions", 1)
        self.assertEqual(code, 0)
        self.assertEqual(report["method"], "cyclic-bibd")
        self.assertEqual((report["diagnostics"]["pair_frequency"]["min"], report["diagnostics"]["pair_frequency"]["max"]), (2, 2))
        self.assertEqual(set(report["diagnostics"]["item_frequency"]["overall"].values()), {4})

    def assert_every_pair_once_per_version(self, report, n_items, per_set, n_sets):
        versions = {}
        for row in report["design"]:
            versions.setdefault(row["version"], {}).setdefault(row["set"], set()).add(row["item"])
        for sets in versions.values():
            self.assertEqual(len(sets), n_sets)
            pairs = {}
            for members in sets.values():
                self.assertEqual(len(members), per_set)
                for a in members:
                    for b in members:
                        if a < b:
                            pairs[(a, b)] = pairs.get((a, b), 0) + 1
            self.assertEqual(len(pairs), n_items * (n_items - 1) // 2)
            self.assertEqual(set(pairs.values()), {1})

    def test_affine_plane_25_items_is_an_exact_bibd(self):
        code, report = run_json("--items", 25, "--per-set", 5, "--sets", 30, "--versions", 2)
        self.assertEqual(code, 0)
        self.assertEqual(report["method"], "affine-bibd")
        self.assertTrue(report["is_bibd"])
        d = report["diagnostics"]
        # r = b k / v = 30 x 5 / 25 = 6 per version; lambda = r (k - 1) / (v - 1) = 6 x 4 / 24 = 1.
        self.assertEqual(set(d["item_frequency"]["overall"].values()), {12})
        self.assertEqual((d["pair_frequency"]["min"], d["pair_frequency"]["max"], d["pair_frequency"]["pairs"]), (2, 2, 300))
        self.assertEqual(d["pair_frequency"]["pairs_never_together"], 0)
        self.assertLessEqual(d["position_frequency"]["max_spread"], 1)
        self.assert_every_pair_once_per_version(report, 25, 5, 30)

    def test_affine_plane_9_items(self):
        code, report = run_json("--items", 9, "--per-set", 3, "--sets", 12, "--versions", 3)
        self.assertEqual(code, 0)
        self.assertEqual(report["method"], "affine-bibd")
        self.assertEqual(set(report["diagnostics"]["item_frequency"]["overall"].values()), {12})
        self.assert_every_pair_once_per_version(report, 9, 3, 12)
        _code, default = run_json("--items", 9, "--per-set", 3, "--versions", 1)
        self.assertTrue(any("--sets 12" in note for note in default["notes"]))

    def test_affine_needs_a_prime_order(self):
        _code, report = run_json("--items", 16, "--per-set", 4, "--sets", 20, "--versions", 1)
        self.assertEqual(report["method"], "randomized-search")

    def test_wide_and_item_id_output_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            items = FIXTURES / "fruit7.input.txt"
            long_ids = run(items, "--per-set", 3, "--versions", 2, "--item-id", "--csv").stdout
            rows = list(csv.reader(io.StringIO(long_ids)))
            self.assertEqual(rows[0], ["version", "set", "position", "item", "item_id"])
            names = (FIXTURES / "fruit7.input.txt").read_text().split()
            self.assertTrue(all(names[int(r[4]) - 1] == r[3] for r in rows[1:]))
            reference = json.loads(run(items, "--per-set", 3, "--versions", 2, "--json").stdout)
            for flags in (["--wide"], ["--wide", "--item-id"], ["--item-id"]):
                with self.subTest(flags):
                    out = pathlib.Path(tmp) / "design.csv"
                    self.assertEqual(run(items, "--per-set", 3, "--versions", 2, "--out", out, *flags).returncode, 0)
                    if "--wide" in flags:
                        self.assertEqual(out.read_text().splitlines()[0], "version,set,item1,item2,item3")
                    code, checked = run_json("--check", out, items)
                    self.assertEqual(code, 0)
                    self.assertEqual(checked["diagnostics"], reference["diagnostics"])

    def test_wide_aliases_and_missing_version_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "d.csv"
            path.write_text("Task,Alt1,Alt2,Alt3\n1,A,B,D\n2,B,C,E\n3,C,D,F\n4,D,E,G\n5,E,F,A\n6,F,G,B\n7,G,A,C\n")
            code, report = run_json("--check", path)
        self.assertEqual(code, 0)
        self.assertTrue(report["is_bibd"])
        self.assertEqual(report["parameters"]["versions"], 1)

    def test_item_id_out_of_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "d.csv"
            path.write_text("version,set,item1,item2,item3\n1,1,1,2,9\n")
            result = run("--check", path, FIXTURES / "fruit7.input.txt")
        self.assertEqual(result.returncode, 2)
        self.assertIn("outside 1..7", result.stderr)

    def test_respondents_sparse_design(self):
        # 60 items, 5 per set, 12 sets: 1 exposure per respondent, so N exposures per item in total.
        args = ["--items", 60, "--per-set", 5, "--sets", 12, "--versions", 6]
        _code, big = run_json(*args, "--respondents", 700)
        self.assertEqual(big["sample"]["exposures_per_item"], 700.0)
        self.assertIn("above the minimum of 500", big["sample"]["exposures_verdict"])
        self.assertNotIn("times each item is shown per respondent", statuses(big, "warn"))
        _code, small = run_json(*args, "--respondents", 300)
        self.assertEqual(small["sample"]["exposures_per_item"], 300.0)
        self.assertIn("under the minimum of 500", small["sample"]["exposures_verdict"])
        self.assertIn("times each item is shown per respondent", statuses(small, "warn"))
        _code, none = run_json(*args)
        self.assertIsNone(none["sample"])

    def test_respondents_standard_design_and_length(self):
        _code, report = run_json("--items", 12, "--per-set", 4, "--respondents", 300)
        # 300 respondents x 9 sets x 4 / 12 items = 900 exposures per item; 9 sets x 20 s = 3.0 minutes.
        self.assertEqual(report["sample"]["exposures_per_item"], 900.0)
        self.assertEqual(report["length_estimate"], {"seconds_per_set": 20, "minutes": 3.0,
                                                     "basis": "assumed, not a sourced figure: time a pilot"})
        _code, timed = run_json("--items", 12, "--per-set", 4, "--seconds-per-set", 30)
        self.assertEqual(timed["length_estimate"]["minutes"], 4.5)

    def test_more_than_seven_per_set_cites_discover(self):
        _code, report = run_json("--items", 20, "--per-set", 8, "--versions", 1)
        detail = [c["detail"] for c in report["criteria"] if c["name"] == "items per set"][0]
        self.assertIn("Discover warns above 7", detail)

    def test_complete_design(self):
        code, report = run_json("--items", 6, "--per-set", 3, "--sets", 20, "--versions", 1)
        self.assertEqual(code, 0)
        self.assertEqual(report["method"], "complete-bibd")
        self.assertTrue(report["is_bibd"])
        self.assertEqual(set(report["diagnostics"]["item_frequency"]["overall"].values()), {10})
        self.assertEqual((report["diagnostics"]["pair_frequency"]["min"], report["diagnostics"]["pair_frequency"]["max"]), (4, 4))
        self.assertLessEqual(report["diagnostics"]["position_frequency"]["max_spread"], 1)

    def test_randomized_search_20_items(self):
        code, report = run_json("--items", 20, "--per-set", 5, "--versions", 3, "--seed", 7)
        self.assertEqual(code, 0)
        self.assertEqual(report["method"], "randomized-search")
        self.assertEqual(report["parameters"]["sets_per_version"], 12)
        d = report["diagnostics"]
        self.assertEqual(set(d["item_frequency"]["overall"].values()), {9})
        self.assertEqual(d["item_frequency"]["worst_version_range"], 0)
        self.assertEqual(d["times_shown_per_respondent"], 3.0)
        self.assertLessEqual(d["position_frequency"]["max_spread"], 1)
        self.assertEqual(d["connectivity"], {"overall_components": 1, "versions_connected": 3, "versions": 3})
        self.assertEqual(d["repeats_within_set"], 0)
        self.assertLessEqual(d["pair_frequency"]["worst_version_range"], 2)
        self.assertEqual(statuses(report, "fail"), [])

    def test_sets_round_up_and_frequencies_stay_within_one(self):
        code, report = run_json("--items", 10, "--per-set", 4, "--versions", 5)
        self.assertEqual(code, 0)
        self.assertEqual(report["parameters"]["sets_per_version"], 8)
        d = report["diagnostics"]
        self.assertEqual(d["item_frequency"]["worst_version_range"], 1)
        self.assertEqual(d["times_shown_per_respondent"], 3.2)
        # 5 versions x 32 slots = 160 = 10 items x 16: the extra appearances rotate, so totals are equal.
        self.assertEqual(set(d["item_frequency"]["overall"].values()), {16})

    def test_default_per_set(self):
        _code, report = run_json("--items", 12)
        self.assertEqual(report["parameters"]["items_per_set"], 4)
        self.assertEqual(report["parameters"]["sets_per_version"], 9)
        self.assertIn("--per-set not given: using 4", report["notes"])
        _code, report = run_json("--items", 7)
        self.assertEqual(report["parameters"]["items_per_set"], 3)

    def test_exposures_option(self):
        _code, report = run_json("--items", 20, "--per-set", 4, "--exposures", 4, "--versions", 1)
        self.assertEqual(report["parameters"]["sets_per_version"], 20)
        self.assertEqual(report["diagnostics"]["times_shown_per_respondent"], 4.0)

    def test_same_seed_same_design_and_other_seed_differs(self):
        first = run("--items", 12, "--per-set", 4, "--seed", 42, "--csv")
        second = run("--items", 12, "--per-set", 4, "--seed", 42, "--csv")
        other = run("--items", 12, "--per-set", 4, "--seed", 43, "--csv")
        self.assertEqual(first.returncode, 0)
        self.assertEqual(first.stdout, second.stdout)
        self.assertNotEqual(first.stdout, other.stdout)

    def test_csv_layout_and_round_trip_through_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            items = pathlib.Path(tmp) / "items.txt"
            items.write_text("Price, per seat\nSingle sign-on\n\"Quoted\" exports\nAudit log\nAPI access\nPriority support\nCustom roles\nSandbox\n")
            out = pathlib.Path(tmp) / "design.csv"
            made = run(items, "--per-set", 4, "--versions", 2, "--out", out)
            self.assertEqual(made.returncode, 0)
            self.assertIn("Design written to", made.stdout)
            rows = list(csv.reader(io.StringIO(out.read_text())))
            self.assertEqual(rows[0], ["version", "set", "position", "item"])
            self.assertEqual(len(rows) - 1, 2 * 6 * 4)
            self.assertIn("Price, per seat", {r[3] for r in rows[1:]})
            generated = json.loads(run(items, "--per-set", 4, "--versions", 2, "--json").stdout)
            code, checked = run_json("--check", out, items)
            self.assertEqual(code, 0)
            self.assertEqual(checked["diagnostics"], generated["diagnostics"])
            self.assertEqual(checked["criteria"], generated["criteria"])

    def test_sparse_design_warns_but_covers_every_item(self):
        code, report = run_json("--items", 60, "--per-set", 5, "--sets", 12, "--versions", 6)
        self.assertEqual(code, 0)
        d = report["diagnostics"]
        self.assertEqual(d["times_shown_per_respondent"], 1.0)
        self.assertEqual(set(d["item_frequency"]["overall"].values()), {6})
        self.assertIn("times each item is shown per respondent", statuses(report, "warn"))
        self.assertIn("connectivity", statuses(report, "warn"))
        self.assertTrue(any("more than 30 items" in note for note in report["notes"]))

    def test_too_few_sets_to_connect_fails(self):
        code, report = run_json("--items", 12, "--per-set", 3, "--sets", 2, "--versions", 1)
        self.assertEqual(code, 1)
        self.assertIn("connectivity", statuses(report, "fail"))

    def test_more_than_half_and_more_than_five_warn(self):
        _code, report = run_json("--items", 10, "--per-set", 6, "--versions", 1)
        detail = [c["detail"] for c in report["criteria"] if c["name"] == "items per set"][0]
        self.assertIn("more than half", detail)
        self.assertIn("more than 5", detail)

    def test_bibd_hint(self):
        _code, report = run_json("--items", 13, "--per-set", 4, "--versions", 1)
        self.assertEqual(report["parameters"]["sets_per_version"], 10)
        self.assertTrue(any("--sets 13" in note for note in report["notes"]))

    def test_bad_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            dup = pathlib.Path(tmp) / "dup.txt"
            dup.write_text("Speed\nPrice\nspeed\n")
            empty = pathlib.Path(tmp) / "empty.txt"
            empty.write_text("\n\n")
            cases = [
                ([], "give an items file"),
                (["--items", 2, "--per-set", 2], "at least 3 items"),
                (["--items", 8, "--per-set", 8], "must be smaller than the number of items"),
                (["--items", 8, "--per-set", 1], "at least 3"),
                (["--items", 5], "give --per-set yourself"),
                (["--items", 8, "--sets", 0], "--sets must be 1 or more"),
                (["--items", 8, "--versions", 0], "--versions must be 1 or more"),
                (["--items", 8, "--respondents", 0], "--respondents must be 1 or more"),
                ([dup], "repeats item 1"),
                ([empty], "has no items"),
                ([FIXTURES / "items7.input.txt", "--items", 7], "not both"),
                ([pathlib.Path(tmp) / "missing.txt"], "cannot read items file"),
            ]
            for args, message in cases:
                with self.subTest(message):
                    result = run(*args)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(message, result.stderr)
                    self.assertEqual(result.stdout, "")


class ConstructionTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import maxdiff_design
        self.module = maxdiff_design

    def tearDown(self):
        sys.path.remove(str(SCRIPT.parent))

    def test_known_difference_sets(self):
        self.assertEqual(self.module.find_difference_set(7, 3), [0, 1, 3])
        self.assertEqual(self.module.find_difference_set(13, 4), [0, 1, 3, 9])
        self.assertIsNone(self.module.find_difference_set(8, 4))
        # lambda = 6 x 5 / 15 = 2 is whole, yet no (16, 6, 2) difference set is cyclic.
        self.assertIsNone(self.module.find_difference_set(16, 6))

    def test_affine_plane_lines(self):
        lines = self.module.affine_plane_sets(3)
        self.assertEqual(len(lines), 12)
        self.assertEqual(self.module.affine_order(25, 5), 5)
        self.assertEqual(self.module.affine_order(16, 4), 0)
        self.assertEqual(self.module.affine_order(24, 5), 0)

    def test_recommended_sets(self):
        self.assertEqual(self.module.recommended_sets(20, 4), 15)
        self.assertEqual(self.module.recommended_sets(20, 5), 12)
        self.assertEqual(self.module.recommended_sets(10, 4), 8)
        self.assertEqual(self.module.recommended_sets(20, 4, 5), 25)


class ReviewRegressionTest(unittest.TestCase):
    """Defects found in the 2026-11 review; each test failed before its fix."""

    def check_text(self, text, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "design.csv"
            path.write_text(text)
            return run("--check", path, *extra, "--json")

    def test_a_set_of_one_item_fails(self):
        result = self.check_text("set,item1\n1,A\n")
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["is_bibd"])
        self.assertIn("each set offers a choice", statuses(report, "fail"))

    def test_sets_holding_every_item_are_not_an_incomplete_design(self):
        result = self.check_text("set,item1,item2,item3\n1,A,B,C\n2,B,C,A\n3,C,A,B\n")
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["is_bibd"])
        self.assertIn("each set offers a choice", statuses(report, "fail"))

    def test_wide_layout_keeps_the_column_number_as_position(self):
        result = self.check_text("set,item1,item2,item3,item4\n1,A,,B,C\n2,B,,C,A\n3,C,,A,B\n4,D,,A,B\n")
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual([row["position"] for row in report["design"][:3]], [1, 3, 4])
        self.assertIn("same shape in every set and version", statuses(report, "fail"))

    def test_trailing_empty_columns_still_read(self):
        result = self.check_text("set,item1,item2,item3,item4\n" + "".join(
            f"{s},{','.join(row)},\n" for s, row in enumerate(["ABD", "BCE", "CDF", "DEG", "AEF", "BFG", "ACG"], 1)))
        self.assertNotIn("same shape in every set and version", statuses(json.loads(result.stdout), "fail"))

    def test_two_columns_for_one_position_or_one_name_are_rejected(self):
        for text in ("set,item1,item_1,item2\n1,A,B,C\n", "set,Item1,item1,item2\n1,A,B,C\n"):
            with self.subTest(text):
                result = self.check_text(text)
                self.assertEqual(result.returncode, 2)
                self.assertIn("maxdiff-design:", result.stderr)

    def test_semicolon_and_tab_delimited_designs_are_read(self):
        body = (FIXTURES / "bibd_7_3_1.input.csv").read_text()
        for delimiter in (";", "\t"):
            with self.subTest(repr(delimiter)):
                result = self.check_text(body.replace(",", delimiter))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(json.loads(result.stdout)["is_bibd"])

    def test_search_message_follows_its_own_diagnostics(self):
        code, report = run_json("--items", 13, "--per-set", 3, "--sets", 26, "--versions", 1)
        self.assertTrue(report["is_bibd"])
        self.assertIn("came out as an exact BIBD", report["method_detail"])
        code, report = run_json("--items", 19, "--per-set", 3, "--sets", 57, "--versions", 1)
        self.assertIn("not proof none exists", report["method_detail"])
        self.assertNotIn("no simple exact BIBD", report["method_detail"])

    def test_items_left_out_of_a_version_are_a_headline_warning(self):
        result = run("--items", 12, "--per-set", 4, "--sets", 2, "--versions", 3)
        self.assertIn("WARN  every item in every version", result.stdout)
        self.assertIn("1.00 means two items are always shown together", result.stdout)
        self.assertIn("with 5 WARN line(s)", result.stdout)


class GeminiReviewRegressionTest(unittest.TestCase):
    """Defects from the second (Gemini) review of 2026-11-19; each test failed before its fix."""

    def check_text(self, text, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "design.csv"
            path.write_text(text, encoding="utf-8")
            return run("--check", path, *extra, "--json")

    def test_two_per_set_is_a_paired_comparison_and_fails(self):
        pairs = ["AB", "AC", "AD", "AE", "AF", "BC", "BD", "BE", "BF", "CD", "CE", "CF", "DE", "DF", "EF"]
        text = "set,item1,item2\n" + "".join(f"{s},{a},{b}\n" for s, (a, b) in enumerate(pairs, 1))
        result = self.check_text(text)
        self.assertEqual(result.returncode, 1)
        self.assertIn("items per set", statuses(json.loads(result.stdout), "fail"))
        generated = run("--items", 8, "--per-set", 2)
        self.assertEqual(generated.returncode, 2)
        self.assertIn("at least 3", generated.stderr)

    def test_respondent_column_is_read_as_the_version(self):
        text = "respondent,set,item1,item2,item3\n1,1,A,B,C\n1,2,D,E,F\n2,1,A,D,E\n2,2,B,C,F\n"
        result = self.check_text(text)
        report = json.loads(result.stdout)
        self.assertEqual(report["parameters"]["versions"], 2)
        self.assertEqual(report["diagnostics"]["repeats_within_set"], 0)
        self.assertNotIn("same shape in every set and version", statuses(report, "fail"))

    def test_a_set_number_repeated_in_one_version_of_a_wide_file_is_rejected(self):
        result = self.check_text("id,set,item1,item2,item3\n7,1,A,B,C\n8,1,D,E,F\n")
        self.assertEqual(result.returncode, 2)
        self.assertIn("set 1 appears more than once in version 1", result.stderr)

    def test_excel_sep_line_is_read_as_the_delimiter(self):
        body = (FIXTURES / "bibd_7_3_1.input.csv").read_text().replace(",", ";")
        result = self.check_text("sep=;\n" + body)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["is_bibd"])

    def test_a_set_repeated_inside_a_version_warns(self):
        fano = ["ABD", "BCE", "CDF", "DEG", "EFA", "FGB", "GAC"]
        text = "set,item1,item2,item3\n" + "".join(
            f"{s},{','.join(row)}\n" for s, row in enumerate(fano + fano, 1))
        report = json.loads(self.check_text(text).stdout)
        self.assertIn("no set repeated within a version", statuses(report, "warn"))
        self.assertEqual(report["diagnostics"]["repeated_sets_within_versions"], 7)

    def test_generated_versions_do_not_repeat_a_set(self):
        for args in ((7, 3, 14), (8, 3, 16), (6, 3, 12), (10, 3, 20)):
            with self.subTest(args):
                code, report = run_json("--items", args[0], "--per-set", args[1], "--sets", args[2], "--versions", 3)
                self.assertEqual(report["diagnostics"]["repeated_sets_within_versions"], 0)
                self.assertNotIn("no set repeated within a version", statuses(report, "warn"))
                self.assertEqual(code, 0)

    def test_sample_rules_follow_the_sources(self):
        # 40 items, 5 per set, 4 sets: half an exposure per respondent; 600 respondents does not make that fine.
        _code, sparse = run_json("--items", 40, "--per-set", 5, "--sets", 4, "--respondents", 600)
        self.assertNotIn("acceptable at 600", sparse["sample"]["per_respondent_rule"])
        self.assertIn("under 1", sparse["sample"]["per_respondent_rule"])
        # A standard design with 3 exposures is not sparse: the 500/1000 rule does not apply.
        _code, standard = run_json("--items", 12, "--per-set", 4, "--respondents", 300)
        self.assertNotIn("under the preferred 1000", standard["sample"]["exposures_verdict"])
        self.assertIn("300", standard["sample"]["total_verdict"])
        _code, tiny = run_json("--items", 12, "--per-set", 4, "--respondents", 20)
        self.assertNotIn("fits any sample size", tiny["sample"]["per_respondent_rule"])
        self.assertIn("under the 300", tiny["sample"]["total_verdict"])
        # Above 30 items the 300 floor rises in proportion (600 at 60 items).
        _code, long_list = run_json("--items", 60, "--per-set", 5, "--sets", 12, "--versions", 2, "--respondents", 500)
        self.assertIn("600", long_list["sample"]["total_verdict"])

    def test_unicode_digit_item_cell_is_bad_input_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            items = pathlib.Path(tmp) / "items.txt"
            items.write_text("A\nB\nC\nD\nE\nF\n")
            result = self.check_text("set,item1,item2,item3\n1,1,\u00b2,3\n", items)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn(result.returncode, (1, 2))

    def test_versions_rule_states_the_segmentation_trade_off(self):
        _code, report = run_json("--items", 12)
        self.assertNotIn("so use 1 when", report["versions_rule"])
        self.assertIn("HB", report["versions_rule"])

    def test_pairs_without_a_correlation_are_reported(self):
        # A is in every set, so its correlations with the other items are undefined.
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "design.csv"
            path.write_text("set,item1,item2,item3\n1,A,B,C\n2,D,A,E\n3,B,D,A\n4,C,E,A\n")
            text = run("--check", path).stdout
        self.assertIn("4 pairs have no correlation", text)

    def test_within_version_position_gap_is_reported(self):
        # A is first in both sets of version 1, second in version 2 and third in version 3: balanced overall,
        # but every respondent of version 1 sees A on top.
        sets = {1: ["ABC", "ADE"], 2: ["BAC", "DAE"], 3: ["BCA", "DEA"]}
        rows = [f"{v},{s},{p},{item}" for v, pair in sets.items() for s, row in enumerate(pair, 1)
                for p, item in enumerate(row, 1)]
        report = json.loads(self.check_text("version,set,position,item\n" + "\n".join(rows) + "\n").stdout)
        self.assertEqual(report["diagnostics"]["position_frequency"]["overall"]["A"], [2, 2, 2])
        self.assertEqual(report["diagnostics"]["position_frequency"]["worst_version_spread"], 2)

if __name__ == "__main__":
    unittest.main()
