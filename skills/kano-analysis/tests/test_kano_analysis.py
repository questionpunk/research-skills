"""Tests for scripts/kano_analysis.py. Run from the skill folder: python3 -m unittest discover -s tests

Expected values come from published examples (Berger et al. 1993, Fig. 16; Matzler and Hinterhuber 1998,
Table 2; Raverta and Loera 2026, Table 2) and a hand-worked ten-respondent example (fixtures/README.md), not
from the script.
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
SCRIPT = SKILL / "scripts" / "kano_analysis.py"

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("kano_analysis", SCRIPT)
ka = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ka)


def run(*args):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                          check=False)


def run_json(*args):
    proc = run(*args, "--json")
    if proc.returncode != 0:
        raise AssertionError(f"exit {proc.returncode}: {proc.stderr}")
    return json.loads(proc.stdout)


def write_csv(rows, encoding="utf-8", delimiter=",", newline="\n"):
    handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding=encoding, newline="")
    csv.writer(handle, delimiter=delimiter, lineterminator=newline).writerows(rows)
    handle.close()
    return handle.name


def feature(res, name, segment=None):
    feats = res["overall"] if segment is None else res["segments"][segment]
    return next(f for f in feats if f["feature"] == name)


class EvaluationTable(unittest.TestCase):
    def test_table_matches_an_independent_derivation_from_kanos_definitions(self):
        # Kano et al. (1984) / Berger et al. (1993): satisfied by presence and dissatisfied by absence = O;
        # satisfied by presence, tolerant of absence = A; tolerant of presence, dissatisfied by absence = M;
        # tolerant both ways = I; same extreme both ways = Q; any other pattern = R.
        def derive(f, d):
            like, dislike, middle = 1, 5, (2, 3, 4)
            if f == d and f in (like, dislike):
                return "Q"
            if f == like and d == dislike:
                return "O"
            if f == like and d in middle:
                return "A"
            if f in middle and d == dislike:
                return "M"
            if f in middle and d in middle:
                return "I"
            return "R"

        for f in range(1, 6):
            for d in range(1, 6):
                self.assertEqual(ka.classify(f, d), derive(f, d), (f, d))


class PublishedExamples(unittest.TestCase):
    def test_berger_fig16_better_worse_all_seven_rows(self):
        # Berger et al. (1993) p. 18, Fig. 16: A, M, O, I counts and the printed Better and Worse.
        res = run_json("analyze", "--counts", FIXTURES / "berger_fig16.input.csv")
        printed = {"CR6": (0.77, -0.48), "CR5": (0.64, -0.44), "CR4": (0.77, -0.31), "CR3": (0.69, -0.21),
                   "CR2": (0.73, -0.17), "CR1": (0.40, -0.04), "CR7": (0.75, -0.02)}
        for cr, (better, worse) in printed.items():
            f = feature(res, f"Berger {cr}")
            self.assertAlmostEqual(f["better"], better, delta=0.005, msg=cr)
            self.assertAlmostEqual(f["worse"], worse, delta=0.005, msg=cr)
        self.assertAlmostEqual(feature(res, "Berger CR6")["better"], 88 / 114, places=12)

    def test_matzler_hinterhuber_edge_grip_coefficients(self):
        # Matzler and Hinterhuber (1998) p. 34, Table 2: rounded percentages A 7, O 33, M 50, I 10 and the printed
        # 0.40 and -0.83. Percentages, not counts: only the coefficients and the category are checked.
        res = run_json("analyze", "--counts", FIXTURES / "matzler_table2_percentages.input.csv")
        f = feature(res, "Edge grip (percentages)")
        self.assertAlmostEqual(f["better"], 0.40, places=12)
        self.assertAlmostEqual(f["worse"], -0.83, places=12)
        self.assertEqual(f["category"], "M")

    def test_raverta_loera_fong_thresholds(self):
        # Raverta and Loera (2026), Table 2, n = 107: the two most frequent counts and Fong's verdict, as recorded
        # by QuestionPunk's method spec. Only a, b and n enter the test, so the other counts are not needed.
        want = {"taste": (42, 41, 11.761, False), "save money": (63, 24, 11.86, True),
                "made in your country": (52, 42, 11.98, False)}
        for name, (a, b, threshold, significant) in want.items():
            result = ka.fong(a, b, 107)
            self.assertAlmostEqual(result["threshold"], threshold, delta=0.006, msg=name)
            self.assertEqual(result["significant"], significant, name)


class WorkedExample(unittest.TestCase):
    """Ten respondents, two features (fixtures/README.md section 2)."""

    def check(self, res):
        save = feature(res, "Save progress and resume later")
        self.assertEqual(save["counts"], {"A": 0, "O": 1, "M": 7, "I": 2, "R": 0, "Q": 0})
        self.assertEqual(save["category"], "M")
        self.assertAlmostEqual(save["better"], 0.10)
        self.assertAlmostEqual(save["worse"], -0.80)
        self.assertAlmostEqual(save["fong"]["threshold"], 1.65 * (9 * 11 / 20) ** 0.5, places=12)
        self.assertTrue(save["fong"]["significant"])
        dark = feature(res, "Dark mode")
        self.assertEqual(dark["counts"], {"A": 4, "O": 4, "M": 0, "I": 0, "R": 1, "Q": 1})
        self.assertEqual(dark["category"], "O")
        self.assertEqual(dark["tied_with"], ["O", "A"])
        self.assertAlmostEqual(dark["better"], 1.0)
        self.assertAlmostEqual(dark["worse"], -0.5)
        self.assertFalse(dark["fong"]["significant"])
        self.assertAlmostEqual(dark["fong"]["threshold"], 3.615, places=3)

    def test_questionpunk_export_headers(self):
        res = run_json("analyze", FIXTURES / "spec_example.input.csv")
        self.assertIn("QuestionPunk export", res["input"]["source"])
        self.check(res)

    def test_questionpunk_answer_text_with_importance_and_segments(self):
        res = run_json("analyze", FIXTURES / "spec_example_answer_text.input.csv", "--qp-answer-col", "Q3",
                       "--segment-col", "plan")
        self.check(res)
        save = feature(res, "Save progress and resume later")
        self.assertAlmostEqual(save["importance"]["mean"], sum(i % 9 + 1 for i in range(10)) / 10)
        self.assertAlmostEqual(save["importance"]["better_weighted"], 0.10 * (4.6 - 1) / 8)
        self.assertEqual(feature(res, "Dark mode", "pro")["n"], 5)
        self.assertEqual(set(res["segments"]), {"free", "pro"})

    def test_pair_flags_long_format_and_label_text(self):
        labels = ka.BERGER_ENGLISH
        save = [(2, 5), (3, 5), (2, 5), (4, 5), (2, 5), (3, 5), (2, 5), (1, 5), (3, 3), (2, 4)]
        dark = [(1, 5), (1, 3), (1, 5), (1, 4), (1, 2), (1, 5), (1, 3), (1, 5), (1, 1), (3, 1)]
        wide = [["id", "a1", "a2", "b1", "b2"]] + [
            [str(i), labels[s[0] - 1], labels[s[1] - 1], str(d[0]), str(d[1])] for i, (s, d) in enumerate(zip(save, dark))]
        res = run_json("analyze", write_csv(wide), "--pair", "Save progress and resume later=a1,a2",
                       "--pair", "Dark mode=b1,b2")
        self.check(res)
        long = [["id", "feature", "f", "d"]]
        for i, (s, d) in enumerate(zip(save, dark)):
            long += [[str(i), "Save progress and resume later", s[0], s[1]], [str(i), "Dark mode", d[0], d[1]]]
        res = run_json("analyze", write_csv(long), "--long", "--feature-col", "feature", "--functional-col", "f",
                       "--dysfunctional-col", "d")
        self.check(res)

    def test_custom_columns_fixture_with_pair_flags(self):
        # The SKILL.md --pair example: the same ten respondents under column names nothing detects.
        res = run_json("analyze", FIXTURES / "custom_columns.input.csv", "--pair",
                       "Save progress and resume later=save_like,save_without,save_importance",
                       "--pair", "Dark mode=dark_like,dark_without", "--segment-col", "plan")
        self.check(res)
        self.assertAlmostEqual(feature(res, "Save progress and resume later")["importance"]["mean"], 4.6)
        self.assertEqual(feature(res, "Dark mode", "pro")["n"], 5)

    def test_suffix_detection_and_reversed_codes(self):
        save = [(2, 5), (3, 5), (2, 5), (4, 5), (2, 5), (3, 5), (2, 5), (1, 5), (3, 3), (2, 4)]
        rows = [["save_f", "save_d"]] + [[str(6 - f), str(6 - d)] for f, d in save]
        res = run_json("analyze", write_csv(rows), "--code-order", "dislike-first")
        self.assertEqual(feature(res, "save")["category"], "M")
        wrong = run_json("analyze", write_csv(rows))
        self.assertEqual(feature(wrong, "save")["category"], "R")
        self.assertTrue(any("dislike-first" in w for w in wrong["warnings"]))


class EdgeCases(unittest.TestCase):
    def test_one_respondent_all_same_and_blank_feature(self):
        res = run_json("analyze", write_csv([["x_f", "x_d", "y_f", "y_d"], ["1", "5", "", ""]]))
        x = feature(res, "x")
        self.assertEqual((x["n"], x["category"], x["better"], x["worse"]), (1, "O", 1.0, -1.0))
        self.assertIn("small base (n = 1)", x["notes"])
        y = feature(res, "y")
        self.assertEqual(y["n"], 0)
        self.assertIsNone(y["category"])
        same = run_json("analyze", write_csv([["x_f", "x_d"]] + [["3", "3"]] * 40))
        x = feature(same, "x")
        self.assertEqual((x["category"], x["better"], x["worse"]), ("I", 0.0, 0.0))
        self.assertTrue(x["fong"]["significant"])

    def test_all_questionable_has_no_coefficients(self):
        res = run_json("analyze", write_csv([["x_f", "x_d"]] + [["1", "1"]] * 5))
        x = feature(res, "x")
        self.assertEqual(x["category"], "Q")
        self.assertIsNone(x["better"])
        self.assertTrue(any("questionable" in n for n in x["notes"]))

    def test_refusals(self):
        self.assertEqual(run("analyze", write_csv([["q", "q"], ["1", "2"]])).returncode, 2)
        self.assertEqual(run("analyze", write_csv([["x_f", "x_d"]])).returncode, 2)
        self.assertEqual(run("analyze", write_csv([["a", "b"], ["1", "2"]])).returncode, 2)
        proc = run("analyze", write_csv([["x_f", "y_d"], ["1", "2"]]))
        self.assertEqual(proc.returncode, 2)
        bad = [["x_f", "x_d"]] + [["1", "5"]] * 17 + [["maybe", "5"], ["1", "sometimes"], ["often", "5"]]
        proc = run("analyze", write_csv(bad))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--allow-unreadable", proc.stderr)
        res = run_json("analyze", write_csv(bad), "--allow-unreadable")
        self.assertEqual(feature(res, "x")["n"], 17)

    def test_incomplete_pairs_are_left_out_and_counted(self):
        res = run_json("analyze", write_csv([["x_f", "x_d"], ["1", "5"], ["1", ""], ["", "5"]]))
        self.assertEqual(feature(res, "x")["n"], 1)
        self.assertTrue(any("one half" in n for n in res["input"]["notes"]))

    def test_encodings_delimiters_qualtrics(self):
        rows = [["id", "x_f", "x_d"]] + [[str(i), "2", "5"] for i in range(12)]
        for path in (write_csv(rows, encoding="utf-8-sig"), write_csv(rows, encoding="utf-16"),
                     write_csv(rows, newline="\r\n"), write_csv(rows, delimiter=";"), write_csv(rows, delimiter="\t")):
            self.assertEqual(feature(run_json("analyze", path), "x")["counts"]["M"], 12)
        q = [rows[0], ["ID", "X functional", "X dysfunctional"],
             ['{"ImportId":"a"}', '{"ImportId":"b"}', '{"ImportId":"c"}']] + rows[1:]
        self.assertEqual(feature(run_json("analyze", write_csv(q)), "x")["n"], 12)

    def test_chart_is_written_and_never_overwrites(self):
        out = os.path.join(tempfile.mkdtemp(), "k.svg")
        run_json("analyze", FIXTURES / "spec_example.input.csv", "--chart", out)
        self.assertIn("<svg", pathlib.Path(out).read_text())
        self.assertEqual(run("analyze", FIXTURES / "spec_example.input.csv", "--chart", out).returncode, 2)


class ReviewRegressions(unittest.TestCase):
    """Failures found in review (2026-11-19); each test failed before its fix."""

    def test_segment_value_named_all_is_not_merged_into_overall(self):
        res = run_json("analyze", write_csv([["x_f", "x_d", "g"], ["1", "5", "All"], ["3", "5", "Pro"]]),
                       "--segment-col", "g")
        overall = res["overall"][0]
        self.assertEqual((overall["n"], overall["counts"]["O"], overall["counts"]["M"]), (2, 1, 1))
        self.assertEqual(overall["category"], "M")  # O and M tie; M > O
        self.assertEqual(feature(res, "x", "All")["n"], 1)
        self.assertEqual(set(res["segments"]), {"All", "Pro"})

    def test_long_format_counts_respondents_by_id_not_rows(self):
        rows = [["id", "feature", "f", "d"], ["1", "X", "1", "5"], ["1", "Y", "3", "5"]]
        args = ("--long", "--feature-col", "feature", "--functional-col", "f", "--dysfunctional-col", "d")
        res = run_json("analyze", write_csv(rows), *args)
        self.assertIsNone(res["input"]["respondents"])
        self.assertEqual(res["input"]["rows"], 2)
        res = run_json("analyze", write_csv(rows), *args, "--respondent-col", "id")
        self.assertEqual(res["input"]["respondents"], 1)
        dup = rows + [["1", "X", "3", "3"]]
        proc = run("analyze", write_csv(dup), *args, "--respondent-col", "id")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("more than one answer", proc.stderr)

    def test_fractional_codes_and_importance_are_not_truncated(self):
        self.assertEqual(ka.read_answer("1.9", False), (None, "unreadable"))
        self.assertEqual(ka.read_answer("2.5", False), (None, "unreadable"))
        self.assertEqual(ka.read_answer("1.0", False), (1, None))
        self.assertEqual(ka.read_answer("5. I dislike it", False), (5, None))
        self.assertEqual(ka.read_importance("7.5"), "bad")
        self.assertEqual(ka.read_importance("7.0"), 7)
        proc = run("analyze", write_csv([["x_f", "x_d"], ["1.9", "5.4"]]))
        self.assertEqual(proc.returncode, 2)

    def test_counts_file_refuses_nan_blank_fraction_duplicates_and_no_rows(self):
        head = ["feature", "A", "O", "M", "I", "R", "Q"]
        for bad in (["X", "NaN", "1", "1", "1", "0", "0"], ["X", "", "1", "1", "1", "0", "0"],
                    ["X", "1.5", "1", "1", "1", "0", "0"], ["X", "inf", "1", "1", "1", "0", "0"]):
            proc = run("analyze", "--counts", write_csv([head, bad]))
            self.assertEqual(proc.returncode, 2, bad)
            self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(run("analyze", "--counts", write_csv([head])).returncode, 2)
        dup = [head, ["X", "2", "0", "0", "0", "0", "0"], ["X", "0", "0", "1", "0", "0", "0"]]
        proc = run("analyze", "--counts", write_csv(dup))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("more than once", proc.stderr)
        whole = write_csv([head, ["X", "2.0", "0", "1", "0", "0", "0"]])
        self.assertEqual(feature(run_json("analyze", "--counts", whole), "X")["counts"]["A"], 2)

    def test_repeated_pair_reused_column_and_orphan_export_column_are_refused(self):
        path = write_csv([["a", "b", "c"], ["1", "5", "3"]])
        self.assertEqual(run("analyze", path, "--pair", "X=a,b", "--pair", "X=a,b").returncode, 2)
        self.assertEqual(run("analyze", path, "--pair", "X=a,b", "--pair", "Y=a,c").returncode, 2)
        orphan = write_csv([["id", "Q3 | A: functional", "Q3 | A: dysfunctional", "Q3 | B: functional"],
                            ["r1", "1", "5", "2"]])
        proc = run("analyze", orphan)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("B", proc.stderr)
        twice = write_csv([["x_f", "x functional", "x_d"], ["1", "1", "5"]])
        self.assertEqual(run("analyze", twice).returncode, 2)

    def test_confidence_level_is_validated_and_labelled(self):
        path = write_csv([["x_f", "x_d"], ["1", "5"], ["3", "3"]])
        out = run("analyze", path, "--confidence", "80").stdout
        self.assertIn("80% Wilson", out)
        self.assertNotIn("95%", out)
        for bad in ("100", "0", "-5", "nan", "150"):
            proc = run("analyze", path, "--confidence", bad)
            self.assertEqual(proc.returncode, 2, bad)
            self.assertNotIn("Traceback", proc.stderr)

    def test_chart_never_replaces_an_input_file(self):
        folder = tempfile.mkdtemp()
        counts = os.path.join(folder, "counts.csv")
        pathlib.Path(counts).write_text("feature,A,O,M,I,R,Q\nX,2,0,1,0,0,0\n")
        proc = run("analyze", "--counts", counts, "--chart", counts, "--overwrite")
        self.assertEqual(proc.returncode, 2)
        self.assertTrue(pathlib.Path(counts).read_text().startswith("feature"))
        answers = os.path.join(folder, "answers.csv")
        pathlib.Path(answers).write_text("x_f,x_d\n1,5\n")
        link = os.path.join(folder, "link.csv")
        os.symlink(answers, link)
        proc = run("analyze", link, "--chart", answers, "--overwrite")
        self.assertEqual(proc.returncode, 2)
        self.assertTrue(pathlib.Path(answers).read_text().startswith("x_f"))

    def test_unterminated_quote_is_refused_with_its_line(self):
        path = write_csv([["x_f", "x_d"]])
        with open(path, "a", encoding="utf-8") as fh:
            fh.write('1,"5\n2,5\n3,5\n')
        proc = run("analyze", path, "--allow-unreadable")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("line", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_bad_bytes_after_a_bom_are_an_input_error(self):
        handle = tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False)
        handle.write(b"\xef\xbb\xbfx_f,x_d\n1,5\xff\n")
        handle.close()
        proc = run("analyze", handle.name)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)

    def test_reversed_codes_warning_on_mostly_indifferent_data(self):
        # True answers: three features M or I, two O; coded 1 = dislike but read as 1 = like.
        rows = [["a_f", "a_d", "b_f", "b_d", "c_f", "c_d", "d_f", "d_d", "e_f", "e_d"]]
        for i in range(20):
            true = [(3, 5), (2, 5), (4, 5), (1, 5), (1, 5)] if i % 2 else [(3, 3), (3, 4), (2, 3), (1, 5), (1, 5)]
            rows.append([str(6 - x) for pair in true for x in pair])
        res = run_json("analyze", write_csv(rows))
        self.assertEqual(sum(f["category"] == "R" for f in res["overall"]), 2)
        self.assertTrue(any("dislike-first" in w for w in res["warnings"]))

    def test_questionable_note_does_not_blame_swapped_questions(self):
        # (1,1) and (5,5) stay Q when the questions or the code order are swapped.
        res = run_json("analyze", write_csv([["x_f", "x_d"]] + [["1", "1"]] * 5))
        text = " ".join(feature(res, "x")["notes"] + res["warnings"])
        self.assertNotIn("swap", text)

    def test_double_negative_in_dysfunctional_question_is_flagged(self):
        path = write_csv([["feature", "functional", "dysfunctional"],
                          ["Ads", "If the app had no ads, how would you feel?",
                           "If the app did not have no ads, how would you feel?"]])
        issues = run_json("design", "--wording", path)["items"][0]["issues"]
        self.assertTrue(any("double negative" in i for i in issues))

    def test_first_run_example_in_skill_md(self):
        out = run("analyze", FIXTURES / "spec_example.input.csv").stdout
        self.assertIn("| Save progress and resume later | 10 (10) | must-be | yes |", out)
        self.assertIn("| Dark mode | 10 (8) | one-dimensional (tie with A) | no (O vs A) |", out)


class SecondReviewRegressions(unittest.TestCase):
    """Second review (2026-11-19); each test failed before its fix."""

    def test_unrecognised_label_after_a_code_is_unreadable_not_the_code(self):
        for text in ("1 - Strongly disagree", "1 - Das stoert mich sehr", "4 - Other (please specify)"):
            self.assertEqual(ka.read_answer(text, False), (None, "unreadable"), text)
        self.assertEqual(ka.read_answer("1 (like)", False), (1, None))
        self.assertEqual(ka.read_answer("5 - I dislike it", False), (5, None))

    def test_pair_columns_with_commas_and_empty_feature_name(self):
        path = write_csv([["id", "If the app had dark mode, how?", "If not, how?"], ["r1", "1", "5"]])
        res = run_json("analyze", path, "--pair", 'Dark="If the app had dark mode, how?","If not, how?"')
        self.assertEqual(feature(res, "Dark")["category"], "O")
        self.assertEqual(run("analyze", write_csv([["a", "b"], ["1", "5"]]), "--pair", "=a,b").returncode, 2)

    def test_generic_suffix_columns_without_a_partner_are_ignored_with_a_note(self):
        res = run_json("analyze", write_csv([["account_has", "Cohort D", "dark_mode_f", "dark_mode_d"],
                                             ["1", "x", "1", "5"]]))
        self.assertEqual(feature(res, "dark_mode")["n"], 1)
        self.assertTrue(any("account_has" in n for n in res["input"]["notes"]))
        res = run_json("analyze", write_csv([["sync_has", "sync_has_not"], ["1", "5"]]))
        self.assertEqual(feature(res, "sync")["category"], "O")
        self.assertEqual(run("analyze", write_csv([["x functional", "y_f", "y_d"], ["1", "1", "5"]])).returncode, 2)

    def test_reverse_warning_suggests_code_order_only_for_numeric_answers(self):
        res = run_json("analyze", "--counts", write_csv([["feature", "A", "O", "M", "I", "R", "Q"],
                                                        ["X", "0", "0", "0", "1", "9", "0"]]))
        self.assertTrue(res["warnings"])
        self.assertFalse(any("--code-order" in w for w in res["warnings"]))
        self.assertNotIn("coded", run("analyze", "--counts", write_csv([["feature", "A", "O", "M", "I", "R", "Q"],
                                                                         ["X", "1", "0", "0", "1", "0", "0"]])).stdout)
        text = [["x_f", "x_d"]] + [["I dislike it that way", "I like it that way"]] * 5
        self.assertFalse(any("--code-order" in w for w in run_json("analyze", write_csv(text))["warnings"]))
        numbers = [["x_f", "x_d"]] + [["5", "1"]] * 5
        self.assertTrue(any("--code-order" in w for w in run_json("analyze", write_csv(numbers))["warnings"]))

    def test_design_checks_ampersand_case_and_curly_apostrophe(self):
        res = run_json("design", "--features", "Sync & share;Q&A board;Export AND print")
        issues = {i["feature"]: i["issues"] for i in res["items"]}
        self.assertTrue(any("two things" in i for i in issues["Sync & share"]))
        self.assertFalse(any("two things" in i for i in issues["Q&A board"]))
        self.assertTrue(any("two things" in i for i in issues["Export AND print"]))
        path = write_csv([["feature", "functional", "dysfunctional"],
                          ["Sync", "If notes sync, how do you feel?", "If notes didn\u2019t sync, how do you feel?"]])
        self.assertFalse(any("no negation" in i for i in run_json("design", "--wording", path)["items"][0]["issues"]))

    def test_excel_quirks(self):
        self.assertEqual(feature(run_json("analyze", write_csv([["id", "x_f", "x_d", "", ""], ["1", "1", "5", "", ""]])),
                                 "x")["n"], 1)
        sep = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
        sep.write("sep=;\nx_f;x_d\n1;5\n2;5\n")
        sep.close()
        self.assertEqual(feature(run_json("analyze", sep.name), "x")["n"], 2)
        rows = write_csv([["x_f", "x_d"], ["1", "5"], ["2", "5"], ["3", "5"]])
        self.assertEqual(run("analyze", rows, "--skip-rows", "-1").returncode, 2)
        locked = write_csv([["x_f", "x_d"], ["1", "5"]])
        os.chmod(locked, 0)
        try:
            if not os.access(locked, os.R_OK):
                proc = run("analyze", locked)
                self.assertEqual(proc.returncode, 2)
                self.assertNotIn("Traceback", proc.stderr)
        finally:
            os.chmod(locked, 0o644)

    def test_feature_names_differing_only_in_case_are_one_feature(self):
        rows = [["id", "feature", "f", "d"], ["1", "Dark mode", "1", "5"], ["2", "Dark Mode", "1", "5"]]
        res = run_json("analyze", write_csv(rows), "--long", "--feature-col", "feature", "--functional-col", "f",
                       "--dysfunctional-col", "d")
        self.assertEqual([(f["feature"], f["n"]) for f in res["overall"]], [("Dark mode", 2)])

    def test_flags_that_do_not_apply_are_refused(self):
        counts = write_csv([["feature", "A", "O", "M", "I", "R", "Q"], ["X", "1", "0", "0", "0", "0", "0"]])
        answers = write_csv([["x_f", "x_d", "g"], ["1", "5", "a"]])
        for args in (("--counts", counts, "--segment-col", "g"), ("--counts", counts, "--code-order", "dislike-first"),
                     (answers, "--counts", counts), (answers, "--long", "--pair", "X=x_f,x_d"),
                     (answers, "--qp-answer-col", "g", "--pair", "X=x_f,x_d"), (answers, "--feature-col", "g")):
            self.assertEqual(run("analyze", *args).returncode, 2, args)
        self.assertEqual(run("design", "--features", "A", "--wording", answers).returncode, 2)

    def test_chart_labels_stay_inside_and_bad_folder_is_an_input_error(self):
        out = os.path.join(tempfile.mkdtemp(), "k.svg")
        run_json("analyze", FIXTURES / "spec_example.input.csv", "--chart", out)
        svg = pathlib.Path(out).read_text()
        self.assertIn('text-anchor="end">Save progress and resume later</text>', svg)
        proc = run("analyze", FIXTURES / "spec_example.input.csv", "--chart", os.path.join(out + "-missing", "k.svg"))
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)

    def test_hyphenated_label_text(self):
        self.assertEqual(ka.read_answer("It must-be that way", False), (2, None))

    def test_answer_accounting(self):
        res = run_json("analyze", write_csv([["x_f", "x_d"]] + [["1", "5"]] * 30 + [["1", "maybe"]]),
                       "--allow-unreadable")
        notes = " ".join(res["input"]["notes"])
        self.assertIn("could not be read", notes)
        self.assertNotIn("one half", notes)
        qp = write_csv([["id", "Q3"]] + [[str(i), "X: 1 / 5"] for i in range(19)] + [["19", "X: 1 / "], ["20", "junk"]])
        res = run_json("analyze", qp, "--qp-answer-col", "Q3", "--allow-unreadable")
        notes = " ".join(res["input"]["notes"])
        self.assertIn("one half", notes)
        self.assertIn("2 answer(s) could not be read", notes)
        seg = run_json("analyze", write_csv([["x_f", "x_d", "g"], ["1", "5", "NA"], ["1", "5", ""], ["1", "5", "a"]]),
                       "--segment-col", "g")
        self.assertEqual(set(seg["segments"]), {"a"})
        self.assertTrue(any("2 row(s) have no g" in n for n in seg["input"]["notes"]))
        long = write_csv([["feature", "f", "d"], ["X", "1", "5"], ["", "1", "5"]])
        res = run_json("analyze", long, "--long", "--feature-col", "feature", "--functional-col", "f",
                       "--dysfunctional-col", "d")
        self.assertTrue(any("no feature" in n for n in res["input"]["notes"]))

    def test_importance_on_a_shorter_scale_is_noted(self):
        rows = [["x_f", "x_d", "x_imp"]] + [["1", "5", str(i % 5 + 1)] for i in range(12)]
        self.assertTrue(any("1-9" in n for n in run_json("analyze", write_csv(rows))["input"]["notes"]))

    def test_tie_for_second_place_is_shown(self):
        res = run("analyze", "--counts", write_csv([["feature", "A", "O", "M", "I", "R", "Q"],
                                                    ["X", "40", "35", "35", "0", "0", "0"]]))
        self.assertIn("no (A vs M/O)", res.stdout)
        self.assertIn("z = 1.65", res.stdout)

    def test_no_negative_zero_and_pipes_in_names_are_escaped(self):
        res = run_json("analyze", write_csv([["x_f", "x_d", "x_imp"]] + [["1", "3", "1"]] * 3))
        x = feature(res, "x")
        self.assertEqual(str(x["worse_ci"][1]), "0.0")
        self.assertEqual(str(x["worse"]), "0.0")
        out = run("analyze", "--counts", write_csv([["feature", "A", "O", "M", "I", "R", "Q"],
                                                   ["A|B", "1", "0", "0", "0", "0", "0"]])).stdout
        self.assertIn("| A\\|B |", out)

    def test_long_format_fixture_from_skill_md(self):
        res = run_json("analyze", FIXTURES / "long_format.input.csv", "--long", "--feature-col", "feature",
                       "--functional-col", "functional", "--dysfunctional-col", "dysfunctional",
                       "--respondent-col", "respondent")
        self.assertEqual(res["input"]["respondents"], 10)
        WorkedExample.check(self, res)

    def test_nul_bytes_and_design_feature_names(self):
        handle = tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False)
        handle.write(b"x\x00_\x00f\x00")
        handle.close()
        self.assertIn("UTF-16", run("analyze", handle.name).stderr)
        self.assertEqual(run("design", "--features", "Dark mode;dark mode").returncode, 2)
        res = run_json("design", "--features", "(survey)")
        self.assertEqual(res["items"][0]["feature"], "(survey)")


class Design(unittest.TestCase):
    def test_generated_pairs_and_checks(self):
        res = run_json("design", "--features", "Dark mode;Export and share", "--product", "the app", "--importance")
        first = res["items"][0]
        self.assertEqual(first["functional"], "If the app had dark mode, how would you feel?")
        self.assertIn("did not have", first["dysfunctional"])
        self.assertEqual(first["issues"], [])
        self.assertTrue(any("two things" in i for i in res["items"][1]["issues"]))
        self.assertEqual(res["answers"][0], "I like it that way")

    def test_wording_file_checks(self):
        path = write_csv([["feature", "functional", "dysfunctional"],
                          ["Sync", "If notes sync across devices, how do you feel?",
                           "If notes sync across devices, how do you feel?"]])
        issues = run_json("design", "--wording", path)["items"][0]["issues"]
        self.assertTrue(any("no negation" in i for i in issues))
        self.assertTrue(any("identical" in i for i in issues))


if __name__ == "__main__":
    unittest.main()
