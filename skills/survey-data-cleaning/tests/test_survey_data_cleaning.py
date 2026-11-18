"""Tests for scripts/survey_data_cleaning.py. Run from the skill folder: python3 -m unittest discover -s tests

Expected values come from fixtures/README.md (worked out by hand), not from the script.
"""
import csv
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "survey_data_cleaning.py"
PLANTED = FIXTURES / "planted.input.csv"
CLEAN = FIXTURES / "clean.input.csv"

CONFIG = [
    "--grid", "sat=g1..g6",
    "--grid", "brand=b1,b2,b3,b4",
    "--attention", "ac1=Strongly disagree",
    "--attention", "ac2=4",
    "--open-cols", "open_feedback",
    "--rule", "exp_gt_age: years_experience > age",
    "--rule", 'never_but_sessions: uses_product == "Never" and sessions_per_week > 0',
]

# fixtures/README.md, "Expected flags"
EXPECTED = {
    "R01": ["open_text_candidate"],
    "R04": ["speeder", "attention_fail", "open_text_candidate"],
    "R05": ["inconsistent"],
    "R06": ["straightliner"],
    "R08": ["duplicate"],
    "R09": ["straightliner"],
    "R10": ["open_text_candidate"],
    "R11": ["open_text_candidate"],
    "R13": ["duplicate"],
    "R14": ["inconsistent"],
    "R15": ["open_text_candidate"],
    "R16": ["duplicate"],
    "R18": ["high_missing"],
    "R19": ["open_text_candidate"],
    "R20": ["speeder", "straightliner", "attention_fail", "open_text_candidate", "inconsistent"],
}


def run(args, out_dir):
    return subprocess.run([sys.executable, str(SCRIPT)] + [str(a) for a in args] + ["--out-dir", str(out_dir)], capture_output=True, text=True)


def write_csv(folder, name, rows):
    path = pathlib.Path(folder) / name
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    return path


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = pathlib.Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def summary(self, args):
        p = run(list(args) + ["--json"], self.out)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def check(self, summary, name):
        return next(c for c in summary["checks"] if c["check"] == name)

    def flags_file(self, stem):
        with open(self.out / f"{stem}.flags.csv", newline="", encoding="utf-8") as f:
            return {r["id"]: r for r in csv.DictReader(f)}


class PlantedFixtureTest(Base):
    def setUp(self):
        super().setUp()
        self.s = self.summary([PLANTED] + CONFIG)

    def test_flags_per_respondent_match_the_readme(self):
        got = {r["id"]: r["flags"] for r in self.s["respondents"]}
        self.assertEqual(got, EXPECTED)
        self.assertEqual(self.s["flag_count_distribution"], {"0": 5, "1": 13, "3": 1, "5": 1})

    def test_speeders_median_and_cutoff(self):
        c = self.check(self.s, "speeder")
        self.assertEqual((c["median"], c["cutoff"]), (600, 200))
        self.assertEqual(c["ids"], ["R04", "R20"])  # R11 sits exactly on the cut-off and is not flagged
        self.assertEqual(c["n_not_evaluable"], 1)  # R15 has no duration

    def test_speed_fraction_can_be_changed(self):
        s = self.summary([PLANTED, "--speed-fraction", "0.5"])
        c = self.check(s, "speeder")
        self.assertEqual(c["cutoff"], 300)
        self.assertEqual(c["ids"], ["R04", "R11", "R20"])

    def test_straightlining_default_and_fraction(self):
        self.assertEqual(self.check(self.s, "straightliner")["ids"], ["R06", "R09", "R20"])
        s = self.summary([PLANTED, "--grid", "sat=g1..g6", "--longstring-fraction", "0.5"])
        c = self.check(s, "straightliner")
        self.assertEqual(c["grids"]["sat"]["threshold"], 4)  # more than half of 6
        self.assertEqual(c["ids"], ["R06", "R12", "R20"])
        s = self.summary([PLANTED, "--grid", "brand=b1..b4", "--longstring-min", "3"])
        self.assertEqual(self.check(s, "straightliner")["ids"], ["R03", "R09"])

    def test_duplicates(self):
        self.assertEqual(self.check(self.s, "duplicate")["ids"], ["R08", "R13", "R16"])
        rows = self.flags_file("planted.input")
        self.assertIn("row identical to R07", rows["R08"]["details"])
        self.assertIn("shared IP is not proof", rows["R13"]["details"])
        self.assertIn("same email as R05", rows["R16"]["details"])
        self.assertEqual(rows["R07"]["duplicate"], "0")  # the first of a group is kept unflagged
        s = self.summary([PLANTED, "--dup-cols", "email"])
        self.assertEqual(self.check(s, "duplicate")["ids"], ["R08", "R16"])

    def test_attention_checks(self):
        c = self.check(self.s, "attention_fail")
        self.assertEqual((c["min_fails"], c["ids"]), (2, ["R04", "R20"]))
        s = self.summary([PLANTED, "--attention", "ac1=Strongly disagree", "--attention", "ac2=4", "--attention-min-fails", "1"])
        self.assertEqual(self.check(s, "attention_fail")["ids"], ["R04", "R14", "R17", "R20"])
        s = self.summary([PLANTED, "--attention", "ac1=Strongly disagree"])
        self.assertEqual(self.check(s, "attention_fail")["min_fails"], 1)  # one check given: one failure flags

    def test_open_text_candidates_and_reasons(self):
        self.assertEqual(self.check(self.s, "open_text_candidate")["ids"], ["R01", "R04", "R10", "R11", "R15", "R19", "R20"])
        rows = self.flags_file("planted.input")
        for rid, reason in [("R01", "same_text_as R19"), ("R04", "repeated_chars"), ("R04", "no_vowels"), ("R10", "too_short"), ("R15", "no_vowels"), ("R20", "keyboard_run")]:
            self.assertIn(reason, rows[rid]["details"])
        self.assertEqual(rows["R18"]["open_text_candidate"], "0")  # a blank answer is non-response, not gibberish

    def test_inconsistency_rules(self):
        c = self.check(self.s, "inconsistent")
        self.assertEqual(c["ids"], ["R05", "R14", "R20"])
        self.assertEqual(c["not_evaluable"], {"exp_gt_age": ["R09", "R18"], "never_but_sessions": ["R18"]})
        self.assertEqual(self.flags_file("planted.input")["R18"]["inconsistent"], "")  # not evaluable is blank, not 0

    def test_item_nonresponse(self):
        c = self.check(self.s, "high_missing")
        self.assertEqual((c["n_item_columns"], c["ids"]), (17, ["R18"]))
        rows = self.flags_file("planted.input")
        self.assertEqual(rows["R18"]["missing_share"], "0.5294")
        self.assertEqual(rows["R03"]["missing_share"], "0.0588")

    def test_skipped_checks_are_blank_not_zero(self):
        s = self.summary([PLANTED])
        self.assertEqual(self.check(s, "straightliner")["status"], "skipped")
        self.assertEqual(self.flags_file("planted.input")["R01"]["straightliner"], "")

    def test_no_clean_file_without_a_drop_rule(self):
        self.assertIsNone(self.s["drop"])
        self.assertFalse((self.out / "planted.input.clean.csv").exists())
        self.assertFalse((self.out / "planted.input.removed.csv").exists())
        self.assertIn("No rows removed", (self.out / "planted.input.cleaning-log.md").read_text())


class DropRuleTest(Base):
    def test_original_is_untouched(self):
        before = hashlib.sha256(PLANTED.read_bytes()).hexdigest()
        s = self.summary([PLANTED] + CONFIG + ["--drop-if", "count>=2"])
        self.assertEqual(hashlib.sha256(PLANTED.read_bytes()).hexdigest(), before)
        self.assertEqual(s["input_sha256"], before)

    def test_count_rule_writes_clean_and_removed_files(self):
        s = self.summary([PLANTED] + CONFIG + ["--drop-if", "count>=2"])
        self.assertEqual(s["drop"]["ids"], ["R04", "R20"])
        self.assertEqual((s["drop"]["n_removed"], s["drop"]["n_kept"]), (2, 18))
        with open(self.out / "planted.input.clean.csv", newline="") as f:
            clean = list(csv.reader(f))
        with open(PLANTED, newline="") as f:
            original = list(csv.reader(f))
        self.assertEqual(clean, [r for r in original if r[0] not in ("R04", "R20")])
        with open(self.out / "planted.input.removed.csv", newline="") as f:
            removed = list(csv.DictReader(f))
        self.assertEqual([r["id"] for r in removed], ["R04", "R20"])
        self.assertIn("count>=2", removed[0]["removed_reason"])
        self.assertIn("speeder, attention_fail, open_text_candidate", removed[0]["removed_reason"])
        log = (self.out / "planted.input.cleaning-log.md").read_text()
        self.assertIn("Removed 2 of 20 (10.0%)", log)
        self.assertIn("with and without", log)

    def test_named_checks_any_and_all(self):
        s = self.summary([PLANTED] + CONFIG + ["--drop-if", "duplicate,speeder+attention_fail"])
        self.assertEqual(s["drop"]["ids"], ["R04", "R08", "R13", "R16", "R20"])

    def test_reviewer_can_clear_a_flag(self):
        s = self.summary([PLANTED] + CONFIG + ["--clear", "R11:open_text_candidate", "--drop-if", "count>=1"])
        self.assertNotIn("R11", s["drop"]["ids"])
        self.assertEqual(s["cleared"], [{"id": "R11", "check": "open_text_candidate"}])
        self.assertIn("R11: open_text_candidate", (self.out / "planted.input.cleaning-log.md").read_text())

    def test_bad_drop_rules(self):
        for rule in ["count>2", "nonsense", "count>=0"]:
            p = run([PLANTED, "--drop-if", rule], self.out)
            self.assertEqual(p.returncode, 2, rule)
            self.assertIn("--drop-if", p.stderr)
        p = run([PLANTED, "--drop-if", "straightliner"], self.out)  # no --grid, so that check did not run
        self.assertEqual(p.returncode, 2)
        self.assertIn("did not run", p.stderr)


class CleanFileTest(Base):
    def test_file_with_no_problems_has_zero_flags(self):
        s = self.summary([CLEAN] + CONFIG + ["--drop-if", "count>=1"])
        self.assertEqual(s["respondents"], [])
        self.assertEqual(s["flag_count_distribution"], {"0": 6})
        self.assertEqual(self.check(s, "speeder")["median"], 610)
        self.assertTrue(all(c["n_flagged"] == 0 for c in s["checks"]))
        self.assertEqual([c["check"] for c in s["checks"] if c["status"] != "run"], ["platform_bot", "platform_ballot_stuffing", "platform_duplicate"])
        self.assertEqual(s["sample"]["warnings"], [])
        self.assertEqual(s["drop"]["n_removed"], 0)
        with open(self.out / "clean.input.clean.csv", newline="") as f, open(CLEAN, newline="") as g:
            self.assertEqual(list(csv.reader(f)), list(csv.reader(g)))


class BadInputTest(Base):
    def assert_error(self, args, text):
        p = run(args, self.out)
        self.assertEqual(p.returncode, 2, p.stdout)
        self.assertIn(text, p.stderr)
        self.assertEqual(list(self.out.glob("*.flags.csv")), [])

    def test_missing_columns_are_named(self):
        self.assert_error([PLANTED, "--grid", "sat=g1,g9"], "column(s) not in the file: g9")
        self.assert_error([PLANTED, "--attention", "nope=4"], "column(s) not in the file: nope")
        self.assert_error([PLANTED, "--open-cols", "comments"], "column(s) not in the file: comments")
        self.assert_error([PLANTED, "--rule", "tenure > age"], "column(s) not in the file: tenure")
        self.assert_error([PLANTED, "--duration-col", "seconds"], "column(s) not in the file: seconds")
        self.assert_error([PLANTED, "--id-col", "uid"], "column(s) not in the file: uid")
        self.assert_error([PLANTED, "--dup-cols", "phone"], "column(s) not in the file: phone")

    def test_missing_file_and_empty_file(self):
        self.assert_error([self.out / "nope.csv"], "input file not found")
        self.assert_error([write_csv(self.out, "empty.csv", [["id", "q1"]])], "no respondent rows")

    def test_bad_values(self):
        bad = write_csv(self.out, "bad.csv", [["id", "duration", "q1"], ["a", "fast", "1"], ["b", "100", "2"]])
        self.assert_error([bad], "'fast' (id a) is not a number")
        self.assert_error([PLANTED, "--speed-fraction", "1.5"], "between 0 and 1")
        self.assert_error([PLANTED, "--rule", "age >"], "incomplete comparison")
        self.assert_error([PLANTED, "--rule", 'uses_product > "Never"'], "== or !=")
        self.assert_error([PLANTED, "--clear", "R02:speeder"], "is not flagged")
        self.assert_error([write_csv(self.out, "ragged.csv", [["id", "q1"], ["a", "1", "2"]])], "data row 1 has 3 cells")


class EdgeCaseTest(Base):
    def test_duplicate_ids_and_no_duration_column(self):
        path = write_csv(self.out, "e.csv", [["respondent_id", "q1", "q2"], ["a", "1", "2"], ["b", "3", "4"], ["a", "5", "1"]])
        s = self.summary([path])
        self.assertEqual(self.check(s, "speeder")["status"], "skipped")
        self.assertEqual(self.check(s, "duplicate")["n_flagged"], 1)
        with open(self.out / "e.flags.csv", newline="", encoding="utf-8") as f:
            self.assertIn("same respondent_id as a", list(csv.DictReader(f))[2]["details"])

    def test_missing_share_boundary_and_row_numbers_without_an_id(self):
        path = write_csv(self.out, "m.csv", [["q1", "q2", "q3", "q4"], ["1", "2", "", ""], ["1", "", "", ""], ["2", "3", "4", "5"]])
        s = self.summary([path])
        self.assertEqual(self.check(s, "high_missing")["ids"], ["row2"])  # 2 of 4 blank is not above 0.5
        self.assertTrue(any("row number" in note for note in s["notes"]))

    def test_blank_breaks_a_run_and_bracketed_columns_work_in_rules(self):
        path = write_csv(self.out, "g.csv", [["id", "a", "b", "c", "d", "years in role", "age"], ["x", "2", "2", "", "2", "30", "25"], ["y", "2", "2", "2", "2", "3", "25"]])
        s = self.summary([path, "--grid", "g=a..d", "--longstring-min", "3", "--rule", "[years in role] > age - 16"])
        self.assertEqual(self.check(s, "straightliner")["ids"], ["y"])
        self.assertEqual(self.check(s, "inconsistent")["ids"], ["x"])

    def test_ordinary_words_are_not_keyboard_runs(self):
        answers = ["The property is in poverty", "Mehrwert", "www.example.com", "It cost 100000", "hmm"]
        path = write_csv(self.out, "o.csv", [["id", "why"]] + [[f"r{i}", a] for i, a in enumerate(answers)])
        s = self.summary([path, "--open-cols", "why"])
        self.assertEqual(self.check(s, "open_text_candidate")["ids"], ["r4"])  # "hmm": no vowels, a candidate to read


QUALTRICS = FIXTURES / "qualtrics.input.csv"
QCONFIG = ["--grid", "q1=Q1_1..Q1_6", "--open-cols", "Q2", "--item-cols", "Q1_1..Q1_6,Q2"]


class QualtricsFixtureTest(Base):
    """Expected values: fixtures/README.md, "qualtrics.input.csv"."""

    def test_three_row_header_and_rows_set_aside(self):
        s = self.summary([QUALTRICS] + QCONFIG)
        self.assertEqual((s["n_rows"], s["n_respondents"]), (12, 9))
        self.assertEqual([(x["id"], x["reason"]) for x in s["not_screened"]], [("Q09", "survey preview"), ("Q10", "survey test"), ("Q11", "unfinished")])
        self.assertTrue(any("Qualtrics export detected: 2 extra header row" in note for note in s["notes"]))
        rows = self.flags_file("qualtrics.input")
        self.assertEqual((rows["Q09"]["screened"], rows["Q09"]["straightliner"], rows["Q09"]["flag_count"]), ("no: survey preview", "", ""))
        self.assertEqual(self.check(s, "straightliner")["ids"], ["Q07"])  # the preview and test rows straight-line but are not screened

    def test_speed_overall_and_within_path(self):
        c = self.check(self.summary([QUALTRICS] + QCONFIG), "speeder")
        self.assertEqual((c["median"], round(c["cutoff"], 2), c["ids"]), (580, 193.33, ["Q07", "Q08"]))
        s = self.summary([QUALTRICS] + QCONFIG + ["--speed-by", "path"])
        c = self.check(s, "speeder")
        self.assertEqual(c["groups"]["long"]["median"], 610)
        self.assertEqual((c["groups"]["short"]["median"], c["groups"]["short"]["cutoff"]), (195, 65))
        self.assertEqual(c["ids"], ["Q08"])
        rows = self.flags_file("qualtrics.input")
        self.assertEqual((rows["Q08"]["duration_per_item"], rows["Q07"]["duration_per_item"]), ("8.57", "31.67"))
        s = self.summary([QUALTRICS] + QCONFIG + ["--speed-by", "path", "--min-per-item", "30"])
        self.assertEqual(self.check(s, "speeder")["ids"], ["Q05", "Q08"])

    def test_page_speed_index(self):
        s = self.summary([QUALTRICS, "--page-time-cols", "t_p1,t_p2"])
        self.assertEqual(self.check(s, "speeder")["ids"], ["Q05", "Q06", "Q07", "Q08"])
        s = self.summary([QUALTRICS, "--page-time-cols", "t_p1,t_p2", "--speed-by", "path"])
        self.assertEqual(self.check(s, "speeder")["ids"], ["Q08"])
        rows = self.flags_file("qualtrics.input")
        self.assertEqual((rows["Q08"]["speed_index"], rows["Q07"]["speed_index"]), ("2.72", "1.03"))

    def test_variability_zero_variance_and_patterns(self):
        s = self.summary([QUALTRICS] + QCONFIG)
        rows = self.flags_file("qualtrics.input")
        self.assertEqual((rows["Q07"]["longstring_q1"], rows["Q07"]["irv_q1"]), ("3", "0.0000"))
        self.assertIn("zero variance over 5 answered", rows["Q07"]["details"])
        self.assertEqual(rows["Q02"]["irv_q1"], "0.5477")
        c = self.check(s, "pattern_candidate")
        self.assertEqual((c["ids"], c["counts_toward_flag_count"]), (["Q02", "Q03"], False))
        self.assertIn("repeating block of 2", rows["Q02"]["details"])
        self.assertIn("staircase", rows["Q03"]["details"])
        self.assertEqual(rows["Q02"]["flag_count"], "0")  # report only

    def test_platform_fields_are_report_only(self):
        s = self.summary([QUALTRICS] + QCONFIG)
        bot = self.check(s, "platform_bot")
        self.assertEqual((bot["ids"], bot["n_error"], bot["n_blank"]), (["Q03"], 1, 1))  # Q04 has an error status, Q12 no score
        self.assertEqual(self.check(s, "platform_ballot_stuffing")["ids"], ["Q05"])
        self.assertEqual(self.check(s, "platform_duplicate")["ids"], ["Q06"])
        rows = self.flags_file("qualtrics.input")
        self.assertEqual((rows["Q04"]["platform_bot"], rows["Q03"]["flag_count"], rows["Q06"]["flag_count"]), ("", "0", "0"))
        s = self.summary([PLANTED])
        self.assertEqual(self.check(s, "platform_bot")["status"], "not present")
        self.assertEqual(self.flags_file("planted.input")["R01"]["platform_bot"], "")

    def test_near_duplicate_open_text(self):
        s = self.summary([QUALTRICS] + QCONFIG)
        self.assertEqual(self.check(s, "open_text_candidate")["ids"], ["Q01", "Q05"])
        self.assertIn("similar_text_to Q05 (0.88)", self.flags_file("qualtrics.input")["Q01"]["details"])
        for value in ["0.9", "off"]:
            s = self.summary([QUALTRICS] + QCONFIG + ["--similar-text", value])
            self.assertEqual(self.check(s, "open_text_candidate")["ids"], [])

    def test_sample_summary_overlap_and_warning(self):
        s = self.summary([QUALTRICS] + QCONFIG + ["--speed-by", "path"])
        self.assertEqual(s["flag_count_distribution"], {"0": 5, "1": 4})
        self.assertEqual((s["sample"]["share_with_1_or_more_flags"], s["sample"]["share_with_2_or_more_flags"]), (0.4444, 0.0))
        self.assertEqual(self.check(s, "speeder")["share_flagged"], 0.1111)
        self.assertEqual(s["flag_overlap"], {"pattern_candidate + platform_bot": 1, "open_text_candidate + platform_ballot_stuffing": 1})
        self.assertEqual(len(s["sample"]["warnings"]), 2)  # open_text_candidate and pattern_candidate at 22.2%, above 12%
        s = self.summary([QUALTRICS] + QCONFIG)  # without --speed-by Q07 has two flags
        self.assertEqual(s["flag_overlap"]["speeder + straightliner"], 1)
        s = self.summary([QUALTRICS] + QCONFIG + ["--speed-by", "path", "--warn-share", "0.25"])
        self.assertEqual(s["sample"]["warnings"], [])

    def test_set_before_drop_composition_and_clean_file(self):
        s = self.summary([QUALTRICS] + QCONFIG + ["--speed-by", "path"])
        self.assertEqual(self.check(s, "speeder")["set_before_results"], "not stated")
        s = self.summary([QUALTRICS] + QCONFIG + ["--speed-by", "path", "--set-before", "speeder,drop", "--compare-cols", "region", "--drop-if", "count>=1,not_screened"])
        self.assertEqual(self.check(s, "speeder")["set_before_results"], "yes")
        self.assertEqual(self.check(s, "straightliner")["set_before_results"], "no (post hoc)")
        self.assertEqual((s["drop"]["set_before_results"], s["drop"]["ids"]), ("yes", ["Q01", "Q05", "Q07", "Q08", "Q09", "Q10", "Q11"]))
        self.assertEqual(s["composition"]["columns"]["region"], {"north": {"removed": 5, "kept": 1}, "south": {"removed": 2, "kept": 4}})
        with open(self.out / "qualtrics.input.clean.csv", newline="") as f, open(QUALTRICS, newline="") as g:
            clean, original = list(csv.reader(f)), list(csv.reader(g))
        self.assertEqual(clean[:3], original[:3])  # the three header rows survive
        self.assertEqual([r[7] for r in clean[3:]], ["Q02", "Q03", "Q04", "Q06", "Q12"])
        with open(self.out / "qualtrics.input.removed.csv", newline="") as f:
            removed = {r["ResponseId"]: r["removed_reason"] for r in csv.DictReader(f)}
        self.assertIn("not screened: survey preview", removed["Q09"])
        log = (self.out / "qualtrics.input.cleaning-log.md").read_text()
        self.assertIn("| no (post hoc) |", log)
        self.assertIn("(set before results: yes)", log)
        p = run([QUALTRICS, "--set-before", "speed"], self.out)
        self.assertEqual(p.returncode, 2)


class InputToleranceTest(Base):
    ROWS = [["id", "duration", "q1", "why"], ["a", "100", "1", "Tr\u00e8s bien, merci beaucoup"], ["b", "20", "2", "ok"], ["c", "110", "3", "Rien \u00e0 signaler"]]

    def write(self, name, encoding, delimiter):
        path = self.out / name
        with open(path, "w", newline="", encoding=encoding) as f:
            csv.writer(f, delimiter=delimiter).writerows(self.ROWS)
        return path

    def test_encodings_and_delimiters_are_detected_and_reported(self):
        for name, encoding, delimiter, words in [("a.csv", "cp1252", ";", ["Windows-1252", "semicolon"]), ("b.csv", "utf-8-sig", "\t", ["UTF-8 with BOM", "tab"]),
                                                 ("c.csv", "utf-8", ",", ["UTF-8", "comma"])]:
            s = self.summary([self.write(name, encoding, delimiter), "--open-cols", "why"])
            for word in words:
                self.assertIn(word, s["notes"][0])
            self.assertEqual(self.check(s, "speeder")["ids"], ["b"])  # 20 < 100 / 3
            self.assertEqual(self.check(s, "open_text_candidate")["ids"], ["b"])
        self.assertEqual(run([self.write("d.csv", "utf-8", ";"), "--delimiter", "comma", "--open-cols", "why"], self.out).returncode, 2)  # a forced wrong delimiter fails loudly

    def test_blank_header_names_stop_with_the_fix(self):
        path = write_csv(self.out, "sm.csv", [["Respondent ID", "How satisfied are you?", ""], ["", "Price", "Quality"], ["1", "4", "5"]])
        p = run([path], self.out)
        self.assertEqual(p.returncode, 2)
        self.assertIn("blank column names", p.stderr)
        self.assertIn("SurveyMonkey", p.stderr)


class GridSizeTest(Base):
    def test_short_grids_are_reported_not_flagged(self):
        s = self.summary([PLANTED, "--grid", "sat=g1..g6", "--grid", "brand=b1..b4", "--min-grid-items", "5"])
        c = self.check(s, "straightliner")
        self.assertEqual(c["ids"], ["R06", "R20"])  # R09 straight-lines the 4-item grid only
        self.assertFalse(c["grids"]["brand"]["flagged"])
        self.assertEqual(self.flags_file("planted.input")["R09"]["longstring_brand"], "4")
        path = write_csv(self.out, "two.csv", [["id", "a", "b"], ["x", "3", "3"], ["y", "1", "2"]])
        s = self.summary([path, "--grid", "g=a,b"])
        self.assertEqual(self.check(s, "straightliner")["ids"], [])  # default minimum is 4 items

    def test_variability_on_the_planted_fixture(self):
        self.summary([PLANTED, "--grid", "sat=g1..g6", "--grid", "brand=b1..b4"])
        rows = self.flags_file("planted.input")
        self.assertEqual((rows["R06"]["irv_sat"], rows["R12"]["irv_sat"], rows["R18"]["irv_brand"]), ("0.0000", "0.8165", ""))
        self.assertEqual(rows["R03"]["straightliner"], "0")  # 1,1,1,blank: three answered, below the minimum of 4


class DocsMatchScriptTest(unittest.TestCase):
    def test_every_option_is_documented_and_every_documented_option_exists(self):
        import importlib.util
        import re

        spec = importlib.util.spec_from_file_location("survey_data_cleaning", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        real = {o for a in module.build_parser()._actions for o in a.option_strings if o.startswith("--")} - {"--help"}
        usage = set(re.findall(r"--[a-z][a-z-]+", (SKILL / "references" / "usage.md").read_text()))
        skill = set(re.findall(r"--[a-z][a-z-]+", (SKILL / "SKILL.md").read_text()))
        self.assertEqual(real - usage, set(), "options missing from references/usage.md")
        self.assertEqual((usage | skill) - real, set(), "documented options the script does not have")
        for name in module.ALL_FLAGS:
            self.assertIn(f"`{name}`", (SKILL / "references" / "usage.md").read_text())


if __name__ == "__main__":
    unittest.main()
