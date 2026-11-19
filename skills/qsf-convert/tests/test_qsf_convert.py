"""Tests for scripts/qsf_convert.py. Run from the skill folder: python3 -m unittest discover -s tests"""
import copy
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "qsf_convert.py"

sys.path.insert(0, str(SCRIPT.parent))
import qsf_convert as qc  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def build(markdown):
    return qc.build_qsf(qc.parse_markdown(markdown), markdown)


def to_md(qsf, **kwargs):
    reader = qc.Reader(copy.deepcopy(qsf), **kwargs)
    text, counts = reader.markdown()
    return text, reader.warnings, counts


def without_comments(markdown):
    return re.sub(r"\n{3,}", "\n\n", qc.strip_comments(markdown)).rstrip("\n") + "\n"


def subset_problems(expected, actual, path="$"):
    """Every field in `expected` must be in `actual` with the same value (lists compared in full, in order)."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected an object, got {actual!r}"]
        out = []
        for key, value in expected.items():
            if value is None:
                if actual.get(key) is not None:
                    out.append(f"{path}.{key}: expected absent, got {actual[key]!r}")
            elif key not in actual:
                out.append(f"{path}.{key}: missing")
            else:
                out += subset_problems(value, actual[key], f"{path}.{key}")
        return out
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return [f"{path}: expected {expected!r}, got {actual!r}"]
        return [p for i, (e, a) in enumerate(zip(expected, actual)) for p in subset_problems(e, a, f"{path}[{i}]")]
    return [] if expected == actual and type(expected) is type(actual) else [f"{path}: expected {expected!r}, got {actual!r}"]


MINIMAL = "# T\n\n## B\n\n### q1 [single]\nPick one\n\n- A\n- B\n"


class MarkdownToQsfFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (FIXTURES / "survey.input.md").read_text(encoding="utf-8")
        cls.expected = json.loads((FIXTURES / "survey.expected.json").read_text(encoding="utf-8"))
        cls.qsf, cls.warnings = build(cls.source)
        cls.elements = cls.qsf["SurveyElements"]

    def payload(self, code):
        return next(e for e in self.elements if e["Element"] == code)["Payload"]

    def test_entry_and_element_order(self):
        self.assertEqual(subset_problems(self.expected["entry"], self.qsf["SurveyEntry"]), [])
        self.assertEqual([e["Element"] for e in self.elements], self.expected["element_codes"])
        self.assertEqual(set(self.qsf["SurveyEntry"]), set(qc.ENTRY_KEYS))

    def test_blocks_page_break_and_skip_logic(self):
        self.assertEqual(subset_problems(self.expected["blocks"], self.payload("BL")), [])

    def test_flow_lists_every_block_but_trash(self):
        flow, expected = self.payload("FL"), self.expected["flow"]
        self.assertEqual((flow["Type"], flow["FlowID"], flow["Properties"]["Count"]), ("Root", "FL_1", expected["Count"]))
        self.assertEqual([n["Type"] for n in flow["Flow"]], expected["node_types"])
        self.assertEqual([n["FlowID"] for n in flow["Flow"]], expected["node_flow_ids"])
        shown = [b["ID"] for b in self.payload("BL") if b["Type"] != "Trash"]
        self.assertEqual([n["ID"] for n in flow["Flow"]], shown)

    def test_questions_match_hand_built_fields(self):
        questions = [e for e in self.elements if e["Element"] == "SQ"]
        self.assertEqual(len(questions), len(self.expected["questions"]))
        for element, expected in zip(questions, self.expected["questions"]):
            self.assertEqual(element["PrimaryAttribute"], expected["QuestionID"])
            self.assertEqual(subset_problems(expected, element["Payload"]), [], expected["QuestionID"])
        for qid, config in self.expected["slider_configuration"].items():
            payload = next(e["Payload"] for e in questions if e["PrimaryAttribute"] == qid)
            self.assertEqual(subset_problems(config, payload["Configuration"]), [])

    def test_question_count_and_response_set(self):
        count = next(e for e in self.elements if e["Element"] == "QC")
        self.assertEqual(count["SecondaryAttribute"], self.expected["question_count"])
        self.assertIsNone(count["Payload"])
        response_set = next(e for e in self.elements if e["Element"] == "RS")
        self.assertEqual(response_set["PrimaryAttribute"], self.qsf["SurveyEntry"]["SurveyActiveResponseSet"])

    def test_ids_are_fifteen_characters_and_one_survey_id(self):
        entry = self.qsf["SurveyEntry"]
        ids = [entry["SurveyID"], entry["SurveyOwnerID"], entry["SurveyActiveResponseSet"]] + [b["ID"] for b in self.payload("BL")]
        for value in ids:
            self.assertRegex(value, r"^(SV|UR|RS|BL)_[0-9A-Za-z]{15}$")
        self.assertEqual({e["SurveyID"] for e in self.elements}, {entry["SurveyID"]})

    def test_passes_own_check_with_no_warnings(self):
        self.assertEqual(qc.validate_qsf(self.qsf), ([], []))

    def test_warns_about_types_seen_in_one_export(self):
        self.assertEqual(len([w for w in self.warnings if "one real export" in w]), 2)

    def test_deterministic(self):
        self.assertEqual(json.dumps(build(self.source)[0]), json.dumps(self.qsf))

    def test_round_trip_is_stable(self):
        markdown, warnings, _ = to_md(self.qsf)
        self.assertEqual(markdown, without_comments(self.source))
        again, _ = build(markdown)
        self.assertEqual(to_md(again)[0], markdown)
        self.assertEqual([w for w in warnings if "survey options" not in w], [])


class QsfToMarkdownFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qsf = json.loads((FIXTURES / "export.input.qsf").read_text(encoding="utf-8"))
        cls.markdown, cls.warnings, cls.counts = to_md(cls.qsf)

    def test_matches_hand_written_markdown(self):
        self.assertEqual(self.markdown, (FIXTURES / "export.expected.md").read_text(encoding="utf-8"))

    def test_reports_everything_it_could_not_represent(self):
        expected = json.loads((FIXTURES / "export.expected-report.json").read_text(encoding="utf-8"))["warnings_contain"]
        for fragment in expected:
            self.assertTrue(any(fragment in w for w in self.warnings), f"no warning contains {fragment!r}")
        self.assertEqual(len(self.warnings), len(expected))

    def test_conversion_report_has_the_fixed_three_parts(self):
        expected = json.loads((FIXTURES / "export.expected-report.json").read_text(encoding="utf-8"))
        reader = qc.Reader(copy.deepcopy(self.qsf))
        reader.markdown()
        report = reader.report
        self.assertEqual(report["questions_in_file"], expected["questions_in_file"])
        self.assertEqual(report["converted"], expected["converted"])
        self.assertEqual([item["id"] for item in report["converted_with_changes"]], expected["converted_with_changes"])
        self.assertEqual({item["id"]: item["reason"] for item in report["not_converted"]}, expected["not_converted"])
        self.assertTrue(all(item["changes"] for item in report["converted_with_changes"]))
        self.assertEqual(len(report["converted"]) + len(report["converted_with_changes"]) + len(report["not_converted"]), 15)
        self.assertEqual(len(report["survey_level"]), 5)
        self.assertIs(report["imported_into_qualtrics"], False)

    def test_counts(self):
        self.assertEqual(self.counts, {"blocks": 3, "questions": 14, "unsupported_questions": 1, "page_breaks": 1})

    def test_codebook_matches_hand_written_csv(self):
        rows = qc.codebook_rows(copy.deepcopy(self.qsf))
        self.assertEqual(qc.codebook_text(rows, "csv"), (FIXTURES / "export.expected-codebook.csv").read_text(encoding="utf-8"))
        table = qc.codebook_text(rows, "md").splitlines()
        self.assertEqual(table[0], "| variable | question_id | block | type | label | values | note |")
        self.assertEqual(len(table), len(rows) + 2)
        self.assertIn("| commute | QID2 | Intro | MC/SAVR/TX | Do you commute to work? | 1=Yes; 2=Sometimes; 0=No |  |", table)

    def test_written_markdown_builds_and_is_stable(self):
        rebuilt, _ = build(self.markdown)
        self.assertEqual(qc.validate_qsf(rebuilt), ([], []))
        again = to_md(rebuilt)[0]
        self.assertEqual(again, without_comments(self.markdown))

    def test_export_passes_validate_with_one_warning(self):
        errors, warnings = qc.validate_qsf(self.qsf)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, ["export tags used more than once: commute"])

    def test_keep_html_keeps_the_span(self):
        markdown, warnings, _ = to_md(self.qsf, keep_html=True)
        self.assertIn('<span style="color:red">Select all</span>', markdown)
        self.assertFalse(any("HTML formatting removed" in w for w in warnings))


class BadMarkdown(unittest.TestCase):
    def fails(self, markdown, fragment):
        with self.assertRaises(qc.ConvertError) as caught:
            qc.parse_markdown(markdown)
        self.assertIn(fragment, str(caught.exception))

    def test_structure_errors(self):
        self.fails("## B\n\n### q1 [text]\nHi\n", "needs a title")
        self.fails("# T\n", "no block")
        self.fails("# T\n\n### q1 [text]\nHi\n", "before any block")
        self.fails("# T\n\n## B\n\nstray words\n", "line 5: text outside a question")
        self.fails("# T\n\n## B\n\n### q1 [text]\n", "no question text")
        self.fails("# T\n\n## B\n\n### q1 [text]\nHi\n\n### q1 [text]\nHi\n", "tag already used")
        self.fails("# T\n\n<!-- open\n\n## B\n", "never closed")

    def test_heading_and_type_errors(self):
        self.fails("# T\n\n## B\n\n### q1 [checkbox]\nHi\n", "unknown question type [checkbox]")
        self.fails("# T\n\n## B\n\n### q1 single\nHi\n", "cannot read question heading")
        self.fails("# T\n\n## B\n\n### q1 [single] mandatory\nHi\n- A\n", "cannot read question heading")
        self.fails("# T\n\n## B\n\n### q1 [single]\nHi\n", "needs at least one")
        self.fails("# T\n\n## B\n\n### q1 [text]\nHi\n- A\n", "takes no '- option' lines")
        self.fails("# T\n\n## B\n\n### q1 [matrix]\nHi\n\nRows:\n- A\n", "needs 'Rows:' and 'Columns:'")
        self.fails("# T\n\n## B\n\n### q1 [info] required\nHi\n", "cannot be 'required'")
        self.fails("# T\n\n## B\n\n### q1 [single]\nHi\n- A {exclusive}\n", "only applies to [multi]")
        self.fails("# T\n\n## B\n\n### q1 [dropdown]\nHi\n- A {text}\n", "only applies to [single] and [multi]")
        self.fails("# T\n\n## B\n\n### q1 [single]\nHi\n- A\nmore text\n", "unexpected text after the options")

    def test_rule_errors(self):
        self.fails(MINIMAL + '\n> skip: if "C" -> end of block\n', "has no option with the exact text 'C'")
        self.fails(MINIMAL + '\n> skip: if "A" -> q9\n', "must be a later question in the same block")
        self.fails(MINIMAL + '\n> skip: when A then stop\n', "cannot read skip rule")
        self.fails(MINIMAL + '\n> jump: somewhere\n', "unknown rule")
        self.fails(MINIMAL + '\n> show if: q1 is "A"\n', "cannot depend on its own question")
        self.fails(MINIMAL + '\n### q2 [text]\nWhy\n\n> show if: q7 is "A"\n', "which does not exist")
        self.fails(MINIMAL + '\n### q2 [text]\nWhy\n\n> show if: q1 is "A" and q1 is "B" or q1 is "A"\n', "not both")
        self.fails(MINIMAL + '\n### q2 [text]\nWhy\n\n### q3 [text]\nX\n\n> show if: q2 is "A"\n', "can only test")
        self.fails(MINIMAL + '\n### q2 [text]\nWhy\n\n> range: 1 to 5\n', "only applies to [slider]")
        self.fails(MINIMAL + '\n### q2 [slider]\nWhy\n- X\n\n> range: 5 to 1\n', "low to high")
        self.fails(MINIMAL + '\n### q2 [nps]\nWhy\n\n> labels: a | b | c\n', "exactly two labels")
        self.fails("# T\n\n## B\n\n### q1 [single]\nPick\n\n- A\n- A\n\n> skip: if \"A\" -> end of block\n", "more than one option")

    def test_skip_to_a_question_in_another_block_is_refused(self):
        self.fails(MINIMAL + '\n> skip: if "A" -> q2\n\n## C\n\n### q2 [text]\nWhy\n', "later question in the same block")


class TextHandling(unittest.TestCase):
    def test_markdown_text_becomes_safe_html(self):
        self.assertEqual(qc.md_to_html("R&D < 5 &amp; <b>x</b>\nline two"), "R&amp;D &lt; 5 &amp; <b>x</b><br>line two")

    def test_html_becomes_markdown_text(self):
        text, dropped = qc.html_to_md('<p>One&nbsp;&amp; two</p><div style="x">Three<br />four &lt;b&gt;</div>')
        self.assertEqual(text, "One & two\n\nThree\nfour &lt;b>")
        self.assertEqual(dropped, ["div"])

    def test_escaped_first_characters_survive_a_round_trip(self):
        markdown = "# T\n\n## B\n\n### q1 [text]\n\\- not an option\n\\> not a rule\n\\# not a heading\n"
        qsf, _ = build(markdown)
        payload = qsf["SurveyElements"][-1]["Payload"]
        self.assertEqual(payload["QuestionText"], "- not an option<br>> not a rule<br># not a heading")
        self.assertEqual(to_md(qsf)[0], markdown)

    def test_quotes_in_option_text_inside_rules(self):
        markdown = '# T\n\n## B\n\n### q1 [single]\nPick\n\n- The "best" one\n- B\n\n> skip: if "The \\"best\\" one" -> end of survey\n'
        qsf, _ = build(markdown)
        self.assertEqual(to_md(qsf)[0], markdown)

    def test_long_text_is_cut_to_99_characters_in_the_description(self):
        qsf, _ = build("# T\n\n## B\n\n### q1 [text]\n" + "word " * 40 + "\n")
        element = qsf["SurveyElements"][-1]
        self.assertEqual(len(element["SecondaryAttribute"]), 99)
        self.assertTrue(element["SecondaryAttribute"].endswith("..."))
        self.assertEqual(element["Payload"]["QuestionText"], ("word " * 40).strip())

    def test_comments_are_ignored_by_to_qsf(self):
        with_comment = MINIMAL.replace("## B", "<!-- note\nover two lines -->\n## B")
        self.assertEqual(json.dumps(build(MINIMAL)[0]["SurveyElements"][-1]["Payload"]), json.dumps(build(with_comment)[0]["SurveyElements"][-1]["Payload"]))


class ReadingExports(unittest.TestCase):
    def base(self):
        return build(MINIMAL + "\n### q2 [text]\nWhy\n")[0]

    def test_block_payload_as_list_or_object(self):
        qsf = self.base()
        as_object = copy.deepcopy(qsf)
        blocks = as_object["SurveyElements"][0]["Payload"]
        as_object["SurveyElements"][0]["Payload"] = {"0": blocks[0], "5": blocks[1]}
        self.assertEqual(to_md(as_object)[0], to_md(qsf)[0])

    def test_mixed_and_or_display_logic_is_reported_not_guessed(self):
        qsf = build(MINIMAL + '\n### q2 [text]\nWhy\n\n> show if: q1 is "A" or q1 is "B"\n')[0]
        logic = qsf["SurveyElements"][-1]["Payload"]["DisplayLogic"]["0"]
        logic["2"] = dict(logic["1"], Conjuction="And")
        markdown, warnings, _ = to_md(qsf)
        self.assertIn("<!-- unsupported display logic on q2", markdown)
        self.assertNotIn("> show if", markdown)
        self.assertTrue(any("display logic not represented" in w for w in warnings))

    def test_second_logic_group_is_reported(self):
        qsf = build(MINIMAL + '\n### q2 [text]\nWhy\n\n> show if: q1 is "A"\n')[0]
        logic = qsf["SurveyElements"][-1]["Payload"]["DisplayLogic"]
        logic["1"] = dict(copy.deepcopy(logic["0"]), Type="AndIf")
        self.assertIn("<!-- unsupported display logic on q2", to_md(qsf)[0])

    def test_question_missing_from_blocks_and_block_missing_from_flow(self):
        qsf = self.base()
        qsf["SurveyElements"][0]["Payload"][0]["BlockElements"].pop()
        warnings = to_md(qsf)[1]
        self.assertTrue(any("sit in no block" in w and "QID2" in w for w in warnings))
        qsf = self.base()
        qsf["SurveyElements"][1]["Payload"]["Flow"] = []
        markdown, warnings, _ = to_md(qsf)
        self.assertNotIn("###", markdown)
        self.assertTrue(any("is not in the survey flow" in w for w in warnings))

    def test_horizontal_layout_and_recodes_are_reported(self):
        qsf = self.base()
        payload = qsf["SurveyElements"][-2]["Payload"]
        payload["Selector"] = "SAHR"
        payload["RecodeValues"] = {"1": "10", "2": "20"}
        markdown, warnings, _ = to_md(qsf)
        self.assertIn("### q1 [single]", markdown)
        self.assertTrue(any("layout SAHR becomes a vertical list" in w for w in warnings))
        self.assertIn("- A {code:10}\n- B {code:20}", markdown)
        self.assertFalse(any("recode" in w for w in warnings))
        rebuilt = build(markdown)[0]["SurveyElements"][-2]["Payload"]
        self.assertEqual(rebuilt["RecodeValues"], {"1": "10", "2": "20"})
        payload["RecodeValues"] = {"1": "x", "2": "x"}
        markdown, warnings, _ = to_md(qsf)
        self.assertNotIn("{code", markdown)
        self.assertTrue(any("choice codes repeat or are not whole numbers" in w for w in warnings))

    def test_choice_key_gaps_are_kept_as_codes(self):
        qsf = self.base()
        payload = qsf["SurveyElements"][-2]["Payload"]
        payload["Choices"] = {"1": {"Display": "A"}, "5": {"Display": "B"}}
        payload["ChoiceOrder"] = [5, 1]
        self.assertIn("- B {code:5}\n- A {code:1}", to_md(qsf)[0])

    def test_side_by_side_dropdown_matrix_and_unknown_kinds(self):
        qsf = build("# T\n\n## B\n\n### m [matrix]\nRate\n\nRows:\n- r1\n\nColumns:\n- c1\n- c2\n")[0]
        payload = qsf["SurveyElements"][-1]["Payload"]
        payload["SubSelector"] = "DL"
        markdown, warnings, _ = to_md(qsf)
        self.assertIn("### m [matrix]", markdown)
        self.assertTrue(any("matrix layout DL becomes a table with one answer per row" in w for w in warnings))
        payload.update({"Selector": "Profile", "SubSelector": "SingleAnswer"})
        reader = qc.Reader(qsf)
        markdown, _ = reader.markdown()
        self.assertIn("<!-- unsupported question QID1 (m): type Matrix/Profile/SingleAnswer", markdown)
        self.assertEqual(reader.report["not_converted"][0]["reason"], "type Matrix/Profile/SingleAnswer is outside the supported set")

    def test_embedded_data_only_when_markdown_can_hold_it(self):
        qsf = build("# T\n\n> embedded: source\n> embedded: wave = 2\n\n## B\n\n### q1 [text]\nHi\n")[0]
        flow = qsf["SurveyElements"][1]["Payload"]
        self.assertEqual(flow["Flow"][0], {"Type": "EmbeddedData", "FlowID": "FL_2", "EmbeddedData": [
            {"Description": "source", "Type": "Recipient", "Field": "source", "VariableType": "String", "DataVisibility": [], "AnalyzeText": False},
            {"Description": "wave", "Type": "Custom", "Field": "wave", "VariableType": "String", "DataVisibility": [], "AnalyzeText": False, "Value": "2"},
        ]})
        self.assertEqual((flow["Flow"][1]["FlowID"], flow["Properties"]["Count"]), ("FL_3", 3))
        self.assertIn("> embedded: source\n> embedded: wave = 2\n", to_md(qsf)[0])
        flow["Flow"][0]["EmbeddedData"][1]["VariableType"] = "Nominal"
        markdown, warnings, _ = to_md(qsf)
        self.assertNotIn("> embedded", markdown)
        self.assertTrue(any("embedded data not represented (source, wave)" in w for w in warnings))

    def test_not_a_qsf(self):
        for text, fragment in (("{oops", "not valid JSON"), ("[]", "not a QSF file"), ('{"SurveyEntry": {}}', "not a QSF file")):
            with self.assertRaises(qc.ConvertError) as caught:
                qc.load_qsf(text)
            self.assertIn(fragment, str(caught.exception))
        with self.assertRaises(qc.ConvertError) as caught:
            qc.Reader({"SurveyEntry": {}, "SurveyElements": []})
        self.assertIn("no 'BL'", str(caught.exception))


class Validate(unittest.TestCase):
    def setUp(self):
        self.qsf = build(MINIMAL + "\n### q2 [text]\nWhy\n")[0]

    def test_errors(self):
        broken = copy.deepcopy(self.qsf)
        broken["SurveyElements"][-1]["PrimaryAttribute"] = "QID9"
        self.assertTrue(any("PrimaryAttribute differs" in e for e in qc.validate_qsf(broken)[0]))
        broken = copy.deepcopy(self.qsf)
        broken["SurveyElements"] = [e for e in broken["SurveyElements"] if e["Element"] != "FL"]
        self.assertIn("expected exactly one FL element, found 0", qc.validate_qsf(broken)[0])
        broken = copy.deepcopy(self.qsf)
        next(e for e in broken["SurveyElements"] if e["Element"] == "QC")["SecondaryAttribute"] = 2
        self.assertEqual(qc.validate_qsf(broken)[0], [])
        next(e for e in broken["SurveyElements"] if e["Element"] == "QC")["SecondaryAttribute"] = "two"
        self.assertTrue(any("QC SecondaryAttribute" in e for e in qc.validate_qsf(broken)[0]))
        broken = copy.deepcopy(self.qsf)
        del broken["SurveyElements"][-1]["Payload"]["Selector"]
        self.assertIn("SQ QID2: Payload.Selector is missing", qc.validate_qsf(broken)[0])
        broken = copy.deepcopy(self.qsf)
        broken["SurveyElements"][-1]["Payload"]["QuestionID"] = broken["SurveyElements"][-1]["PrimaryAttribute"] = "QID1"
        self.assertTrue(any("defined twice" in e for e in qc.validate_qsf(broken)[0]))

    def test_conjunction_spelling(self):
        qsf = build(MINIMAL + '\n### q2 [text]\nWhy\n\n> show if: q1 is "A" or q1 is "B"\n')[0]
        expression = qsf["SurveyElements"][-1]["Payload"]["DisplayLogic"]["0"]["1"]
        self.assertEqual(expression["Conjuction"], "Or")
        expression["Conjunction"] = expression.pop("Conjuction")
        self.assertTrue(any("'Conjuction'" in e for e in qc.validate_qsf(qsf)[0]))

    def test_warnings(self):
        loose = copy.deepcopy(self.qsf)
        loose["SurveyElements"][0]["Payload"][0]["BlockElements"].pop()
        next(e for e in loose["SurveyElements"] if e["Element"] == "QC")["SecondaryAttribute"] = "1"
        loose["SurveyElements"][1]["Payload"]["Flow"] = []
        errors, warnings = qc.validate_qsf(loose)
        self.assertEqual(errors, [])
        for fragment in ("question QID2 is in no block", "QC says 1 but the file defines 2", "is not in the flow"):
            self.assertTrue(any(fragment in w for w in warnings), fragment)

    def test_question_count_may_exceed_the_number_of_questions(self):
        next(e for e in self.qsf["SurveyElements"] if e["Element"] == "QC")["SecondaryAttribute"] = "40"
        self.assertEqual(qc.validate_qsf(self.qsf), ([], []))


class CommandLine(unittest.TestCase):
    def test_to_qsf_writes_one_line_of_ascii_json(self):
        with tempfile.TemporaryDirectory() as folder:
            out = pathlib.Path(folder) / "s.qsf"
            done = run("to-qsf", str(FIXTURES / "survey.input.md"), "-o", str(out))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("Import into a new test survey first", done.stdout)
            raw = out.read_bytes()
            self.assertEqual(raw.count(b"\n"), 1)
            raw.decode("ascii")
            self.assertEqual(run("validate", "--strict", str(out)).returncode, 0)
            back = run("to-md", str(out))
            self.assertEqual(back.returncode, 0, back.stderr)
            self.assertIn("### used [single] required", back.stdout)
            self.assertIn("survey level, not represented: none", back.stderr)  # its options are the ones to-qsf writes
            self.assertIn("conversion report: 12 converted, 0 converted with changes, 0 not converted (of 12 question(s))", back.stderr)

    def test_json_reports(self):
        done = run("to-md", str(FIXTURES / "export.input.qsf"), "--json")
        report = json.loads(done.stdout)
        self.assertEqual(report["summary"]["unsupported_questions"], 1)
        self.assertEqual(set(report["report"]), {"questions_in_file", "converted", "converted_with_changes", "not_converted", "survey_level", "imported_into_qualtrics"})
        self.assertEqual(report["output"], (FIXTURES / "export.expected.md").read_text(encoding="utf-8"))
        self.assertEqual(len(report["warnings"]), 14)
        done = run("to-qsf", str(FIXTURES / "survey.input.md"), "--json")
        report = json.loads(done.stdout)
        self.assertIs(report["imported_into_qualtrics"], False)
        self.assertEqual(report["summary"]["questions"], 12)
        self.assertEqual(json.loads(report["output"])["SurveyEntry"]["SurveyName"], "Product feedback pulse")
        done = run("validate", str(FIXTURES / "export.input.qsf"), "--json")
        self.assertEqual(json.loads(done.stdout)["ok"], True)

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = pathlib.Path(folder) / "bad.md"
            bad.write_text("# T\n\n## B\n\n### q1 [single]\nHi\n", encoding="utf-8")
            done = run("to-qsf", str(bad))
            self.assertEqual((done.returncode, done.stdout), (1, ""))
            self.assertIn("qsf-convert: line 5: question q1", done.stderr)
            self.assertEqual(run("to-md", str(bad)).returncode, 1)
            self.assertEqual(run("validate", str(pathlib.Path(folder) / "missing.qsf")).returncode, 1)
            self.assertEqual(run("to-qsf", str(bad), "-o", str(bad)).returncode, 1)
            broken = json.loads((FIXTURES / "export.input.qsf").read_text(encoding="utf-8"))
            broken["SurveyElements"] = [e for e in broken["SurveyElements"] if e["Element"] != "BL"]
            path = pathlib.Path(folder) / "broken.qsf"
            path.write_text(json.dumps(broken), encoding="utf-8")
            done = run("validate", str(path))
            self.assertEqual(done.returncode, 1)
            self.assertIn("error: expected exactly one BL element, found 0", done.stdout)
        self.assertEqual(run("validate", str(FIXTURES / "export.input.qsf")).returncode, 0)
        self.assertEqual(run("validate", "--strict", str(FIXTURES / "export.input.qsf")).returncode, 1)
        self.assertEqual(run().returncode, 2)


class AdvancedFormatTxt(unittest.TestCase):
    def setUp(self):
        self.source = (FIXTURES / "plain.input.md").read_text(encoding="utf-8")
        self.survey = qc.parse_markdown(self.source)

    def test_matches_hand_written_txt(self):
        text, warnings = qc.build_txt(self.survey)
        self.assertEqual(text, (FIXTURES / "plain.expected.txt").read_text(encoding="utf-8"))
        self.assertEqual(warnings, [])
        self.assertEqual(qc.txt_limits(self.survey), [])

    def test_same_survey_as_qsf_round_trips(self):
        qsf, warnings = build(self.source)
        self.assertEqual(qc.validate_qsf(qsf), ([], []))
        self.assertEqual(to_md(qsf)[0], self.source)
        self.assertEqual(len(warnings), 2)  # [rank] and [sum] rest on one export each
        payloads = {e["Payload"]["DataExportTag"]: e["Payload"] for e in qsf["SurveyElements"] if e["Element"] == "SQ"}
        self.assertEqual(payloads["rating"]["RecodeValues"], {"1": "1", "2": "0", "3": "99"})
        self.assertEqual(payloads["agree"]["RecodeValues"], {"1": "0", "2": "1"})
        self.assertNotIn("RecodeValues", payloads["topics"])
        self.assertEqual([payloads["contact"][k] for k in ("QuestionType", "Selector")], ["TE", "FORM"])
        self.assertEqual(payloads["contact"]["Choices"], {"1": {"Display": "Name"}, "2": {"Display": "Email"}})
        self.assertEqual([payloads["budget"].get(k) for k in ("QuestionType", "Selector", "SubSelector")], ["CS", "VRTL", "TX"])

    def test_auto_picks_txt_only_when_nothing_is_lost(self):
        with tempfile.TemporaryDirectory() as folder:
            out = pathlib.Path(folder) / "survey.qsf"
            done = run("to-qualtrics", str(FIXTURES / "plain.input.md"), "-o", str(out), "--json")
            report = json.loads(done.stdout)
            self.assertEqual((report["format"], report["output_file"]), ("txt", str(out)[:-3] + "txt"))
            self.assertIs(report["imported_into_qualtrics"], False)
            self.assertFalse(out.exists())
            self.assertEqual((pathlib.Path(folder) / "survey.txt").read_text(encoding="utf-8"), (FIXTURES / "plain.expected.txt").read_text(encoding="utf-8"))
            done = run("to-qualtrics", str(FIXTURES / "survey.input.md"), "-o", str(out))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("format: QSF (the survey uses what Advanced Format TXT cannot hold: 'required'; skip logic;", done.stdout)
            self.assertIn("question type [slider]", done.stdout)
            self.assertTrue(out.exists())
        done = run("to-qualtrics", str(FIXTURES / "plain.input.md"))
        self.assertTrue(done.stdout.startswith("[[AdvancedFormat]]"))
        self.assertIn("format: TXT (Qualtrics' documented Advanced Format holds everything in this survey)", done.stderr)
        self.assertIn("Import into a new test survey first", done.stderr)
        self.assertIn("A TXT import ADDS to the survey that is open", done.stderr)

    def test_forced_txt_refuses_types_without_a_tag_and_lists_what_it_drops(self):
        done = run("to-qsf", str(FIXTURES / "survey.input.md"), "--format", "txt")
        self.assertEqual((done.returncode, done.stdout), (1, ""))
        self.assertIn("Advanced Format TXT cannot hold: nps: question type [nps]", done.stderr)
        markdown = MINIMAL.replace("[single]", "[single] required").replace("- B", "- B {text}") + '\n> skip: if "A" -> end of survey\n'
        text, warnings = qc.build_txt(qc.parse_markdown(markdown))
        self.assertEqual(text, "[[AdvancedFormat]]\n\n[[Block:B]]\n\n[[Question:MC:SingleAnswer:Vertical]]\n[[ID:q1]]\nPick one\n[[Choices]]\nA\nB\n")
        self.assertEqual(warnings, [
            "q1: not carried into the TXT file: 'required' (TXT has no validation tags)",
            "q1: not carried into the TXT file: skip logic",
            "q1: not carried into the TXT file: write-in box {text}",
        ])


class SecondPassForward(unittest.TestCase):
    def payload(self, markdown):
        qsf, warnings = build(markdown)
        self.assertEqual(qc.validate_qsf(qsf), ([], []))
        self.assertEqual(to_md(qsf)[0], markdown)
        return qsf["SurveyElements"][-1]["Payload"], warnings

    def test_matrix_text_with_row_export_tags(self):
        payload, _ = self.payload("# T\n\n## B\n\n### h [matrix-text]\nHours\n\nRows:\n- Work {var:h_work}\n- Home {var:h_home}\n\nColumns:\n- Hours\n")
        self.assertEqual([payload[k] for k in ("QuestionType", "Selector", "SubSelector")], ["Matrix", "TE", "Short"])
        self.assertEqual(payload["ChoiceDataExportTags"], {"1": "h_work", "2": "h_home"})
        self.assertEqual(payload["Answers"], {"1": {"Display": "Hours"}})
        self.assertNotIn("WhiteSpace", payload["Configuration"])

    def test_constant_sum_total_and_randomization(self):
        payload, warnings = self.payload("# T\n\n## B\n\n### s [sum]\nSplit\n\n- A\n- B\n\n> total: 100\n> randomize: options\n")
        self.assertEqual(payload["Validation"], {"Settings": {"EnforceRange": "OFF", "Type": "ChoicesTotal", "ChoiceTotal": "100"}})
        self.assertEqual(payload["Randomization"], {"Advanced": None, "TotalRandSubset": "", "Type": "All"})
        self.assertTrue(any("[sum] shape was seen in one real export only" in w for w in warnings))
        payload, _ = self.payload("# T\n\n## B\n\n### m [matrix]\nRate\n\nRows:\n- r1\n- r2\n\nColumns:\n- c1\n\n> randomize: rows\n")
        self.assertEqual(payload["Randomization"]["Type"], "All")

    def test_new_syntax_errors(self):
        def fails(markdown, fragment):
            with self.assertRaises(qc.ConvertError) as caught:
                qc.parse_markdown(markdown)
            self.assertIn(fragment, str(caught.exception))

        fails("# T\n\n## B\n\n### q1 [single]\nPick\n\n- A {code:1}\n- B\n", "give {code:n} to every")
        fails("# T\n\n## B\n\n### q1 [single]\nPick\n\n- A {code:1}\n- B {code:1}\n", "each one different")
        fails("# T\n\n## B\n\n### q1 [rank]\nPick\n\n- A {code:1}\n", "{code:n} applies to")
        fails("# T\n\n## B\n\n### q1 [single]\nPick\n\n- A {var:x}\n", "only applies to matrix rows")
        fails("# T\n\n## B\n\n### q1 [dropdown]\nPick\n\n- A\n\n> randomize: options\n", "write '> randomize: options'")
        fails("# T\n\n## B\n\n### q1 [single]\nPick\n\n- A\n\n> randomize: rows\n", "write '> randomize: options'")
        fails("# T\n\n## B\n\n### q1 [single]\nPick\n\n- A\n\n> total: 10\n", "only applies to [sum]")
        fails("# T\n\n## B\n\n### q1 [sum] required\nSplit\n\n- A\n", "cannot be 'required'")
        fails("# T\n\n> skip: x\n\n## B\n", "before the first block only '> embedded: field'")
        fails("# T\n\n> embedded: a\n> embedded: a\n\n## B\n", "declared twice")


class SecondPassLints(unittest.TestCase):
    def test_logic_pointing_at_a_missing_choice(self):
        qsf = build(MINIMAL + '\n> skip: if "A" -> end of block\n\n### q2 [text]\nWhy\n\n> show if: q1 is "B"\n')[0]
        self.assertEqual(qc.validate_qsf(qsf), ([], []))
        del qsf["SurveyElements"][-2]["Payload"]["Choices"]["2"]
        qsf["SurveyElements"][-2]["Payload"]["ChoiceOrder"] = ["1"]
        qsf["SurveyElements"][0]["Payload"][0]["BlockElements"][0]["SkipLogic"][0]["Locator"] = "q://QID1/SelectableChoice/7"
        errors, warnings = qc.validate_qsf(qsf)
        # a rule that points at a missing choice can never fire: an error since the 2026-11-19 review
        self.assertIn("display logic on QID2 names choice 2 of QID1, which does not exist", errors)
        self.assertIn("skip logic on QID1 names choice 7 of QID1, which does not exist", errors)

    def test_missing_conjuction_and_repeated_flow_ids(self):
        qsf = build(MINIMAL + '\n### q2 [text]\nWhy\n\n> show if: q1 is "A" or q1 is "B"\n\n## C\n\n### q3 [text]\nX\n')[0]
        del qsf["SurveyElements"][-2]["Payload"]["DisplayLogic"]["0"]["1"]["Conjuction"]
        qsf["SurveyElements"][1]["Payload"]["Flow"][1]["FlowID"] = "FL_2"
        errors, warnings = qc.validate_qsf(qsf)
        self.assertEqual(errors, [])
        self.assertIn("SQ QID2: display logic condition 1 has no 'Conjuction' (And/Or) key", warnings)
        self.assertIn("flow IDs repeat", warnings)

    def test_codebook_command(self):
        done = run("codebook", str(FIXTURES / "export.input.qsf"))
        self.assertEqual(done.stdout, (FIXTURES / "export.expected-codebook.csv").read_text(encoding="utf-8"))
        self.assertIn("codebook: 26 variable(s)", done.stderr)
        report = json.loads(run("codebook", str(FIXTURES / "export.input.qsf"), "--json").stdout)
        self.assertEqual((report["variables"], report["rows"][0]["variable"]), (26, "commute"))
        self.assertIn("Check the names against a real data export", report["naming_note"])
        self.assertTrue(run("codebook", str(FIXTURES / "export.input.qsf"), "--format", "md").stdout.startswith("| variable |"))


def run_in(stdin, *args, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, input=stdin, cwd=cwd)


def question_payload(qsf, tag):
    return next(e["Payload"] for e in qsf["SurveyElements"] if e["Element"] == "SQ" and e["Payload"]["DataExportTag"] == tag)


def element(qsf, code):
    return next(e for e in qsf["SurveyElements"] if e["Element"] == code)


class ReviewFixes(unittest.TestCase):
    """Regressions for the 2026-11-19 review findings; each failed on the version reviewed."""

    def test_access_restriction_and_scoring_are_named_in_the_report(self):
        qsf = build(MINIMAL)[0]
        element(qsf, "SO")["Payload"]["SurveyProtection"] = "ByInvitationOnly"
        element(qsf, "SCO")["Payload"]["ScoringCategories"] = [{"ID": "SC_1", "Name": "Score", "Description": ""}]
        reader = qc.Reader(copy.deepcopy(qsf))
        reader.markdown()
        level = " ".join(reader.report["survey_level"])
        self.assertIn("SurveyProtection = 'ByInvitationOnly' (rebuilt: 'PublicSurvey')", level)
        self.assertIn("before fielding", level)
        self.assertIn("scoring is not represented (1 scoring category)", level)

    def test_text_matrix_codebook_has_one_variable_per_box(self):
        qsf = build("# T\n\n## B\n\n### m [matrix-text]\nEnter details\n\nRows:\n- Red\n- Blue\n\nColumns:\n- Time\n- Cost\n")[0]
        rows = qc.codebook_rows(qsf)
        self.assertEqual([r["variable"] for r in rows], ["m_1_1", "m_1_2", "m_2_1", "m_2_2"])
        self.assertEqual({r["values"] for r in rows}, {"(open text)"})

    def test_multi_answer_matrix_and_nps_group_in_the_codebook(self):
        qsf = build("# T\n\n## B\n\n### m [matrix-multi]\nPick\n\nRows:\n- Red\n\nColumns:\n- Car\n- Bike\n\n"
                    "### nps [nps]\nHow likely are you to recommend us?\n")[0]
        names = [r["variable"] for r in qc.codebook_rows(qsf)]
        self.assertEqual(names, ["m_1_1", "m_1_2", "nps", "nps_NPS_GROUP"])

    def test_output_that_is_the_input_by_another_spelling_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            source = pathlib.Path(folder) / "survey.md"
            source.write_text(MINIMAL, encoding="utf-8")
            done = run_in(None, "to-qualtrics", "survey.md", "-o", "./survey.md", cwd=folder)
            self.assertEqual(done.returncode, 1)
            self.assertIn("is the input file", done.stderr)
            self.assertEqual(source.read_text(encoding="utf-8"), MINIMAL)

    def test_a_file_name_the_script_chose_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            (pathlib.Path(folder) / "s.md").write_text(MINIMAL, encoding="utf-8")
            keep = pathlib.Path(folder) / "s.txt"
            keep.write_text("mine", encoding="utf-8")
            done = run_in(None, "to-qualtrics", "s.md", "-o", "s.qsf", cwd=folder)  # auto picks TXT -> s.txt
            self.assertEqual(done.returncode, 1)
            self.assertIn("--force", done.stderr)
            self.assertEqual(keep.read_text(encoding="utf-8"), "mine")
            self.assertEqual(run_in(None, "to-qualtrics", "s.md", "-o", "s.qsf", "--force", cwd=folder).returncode, 0)
            self.assertTrue(keep.read_text(encoding="utf-8").startswith("[[AdvancedFormat]]"))

    def test_repeated_choice_in_choice_order(self):
        qsf = build(MINIMAL)[0]
        question_payload(qsf, "q1")["ChoiceOrder"] = ["1", "1"]
        errors, warnings = qc.validate_qsf(qsf)
        self.assertIn("SQ QID1: ChoiceOrder lists Choices keys more than once: 1", warnings)
        self.assertIn("SQ QID1: ChoiceOrder leaves out Choices keys, which the survey will not show: 2", warnings)
        text, reader_warnings, _ = to_md(qsf)
        self.assertEqual(text.count("- A"), 1)
        self.assertTrue(any("missing from ChoiceOrder were left out: 2 ('B')" in w for w in reader_warnings))

    def test_literal_mark_text_in_an_option_survives_the_round_trip(self):
        qsf = build(MINIMAL)[0]
        question_payload(qsf, "q1")["Choices"]["1"]["Display"] = "First {text}"
        text, _, _ = to_md(qsf)
        self.assertIn("- First \\{text}", text)
        rebuilt = build(text)[0]
        self.assertEqual(question_payload(rebuilt, "q1")["Choices"]["1"], {"Display": "First {text}"})

    def test_display_rule_on_a_later_question_is_refused_and_flagged(self):
        md = '# T\n\n## B\n\n### a [text]\nWhy?\n\n> show if: b is "Yes"\n\n### b [single]\nOk?\n\n- Yes\n- No\n'
        with self.assertRaisesRegex(qc.ConvertError, "comes later"):
            qc.parse_markdown(md)
        qsf = build('# T\n\n## B\n\n### a [text]\nWhy?\n\n---\n\n### b [single]\nOk?\n\n- Yes\n- No\n')[0]
        loc = "q://QID2/SelectableChoice/1"
        question_payload(qsf, "a")["DisplayLogic"] = {"0": {"0": {
            "LogicType": "Question", "QuestionID": "QID2", "QuestionIsInLoop": "no", "ChoiceLocator": loc,
            "Operator": "Selected", "QuestionIDFromLocator": "QID2", "LeftOperand": loc, "Type": "Expression",
            "Description": "If Ok? Yes Is Selected"}, "Type": "If"}, "Type": "BooleanExpression", "inPage": False}
        errors, warnings = qc.validate_qsf(qsf)
        self.assertTrue(any("QID1 (a, question 1) tests QID2 (b, question 2), which comes later" in w for w in warnings))
        text, reader_warnings, _ = to_md(qsf)
        self.assertNotIn("> show if", text)
        self.assertTrue(any("comes after it" in w for w in reader_warnings))

    def test_codes_compare_as_numbers_and_tags_ignore_case(self):
        with self.assertRaisesRegex(qc.ConvertError, "each one different"):
            qc.parse_markdown("# T\n\n## B\n\n### q [single]\nPick\n\n- A {code:01}\n- B {code:1}\n")
        with self.assertRaisesRegex(qc.ConvertError, "upper and lower case"):
            qc.parse_markdown("# T\n\n## B\n\n### Age [text]\nAge?\n\n### age [text]\nAge again?\n")

    def test_nps_can_drive_display_logic_and_reads_back(self):
        md = ('# T\n\n## B\n\n### nps [nps]\nHow likely are you to recommend us?\n\n---\n\n'
              '### why [text]\nWhat is the main reason?\n\n> show if: nps is "0" or nps is "6"\n')
        qsf, warnings = build(md)
        logic = question_payload(qsf, "why")["DisplayLogic"]["0"]
        self.assertEqual([logic[k]["LeftOperand"] for k in ("0", "1")], ["q://QID1/SelectableChoice/0", "q://QID1/SelectableChoice/6"])
        self.assertTrue(any("no export with it was seen" in w for w in warnings))
        self.assertEqual(qc.validate_qsf(qsf), ([], []))
        self.assertIn('> show if: nps is "0" or nps is "6"', to_md(qsf)[0])
        with self.assertRaisesRegex(qc.ConvertError, 'options "0" to "10"'):
            qc.parse_markdown(md.replace('nps is "6"', 'nps is "11"'))

    def test_display_rule_on_the_same_page_is_warned(self):
        warnings = build('# T\n\n## B\n\n### a [single]\nOk?\n\n- Yes\n- No\n\n### b [text]\nWhy?\n\n> show if: a is "No"\n')[1]
        self.assertTrue(any(w.startswith("b: its display rule tests a on the same page") for w in warnings))
        warnings = build('# T\n\n## B\n\n### a [single]\nOk?\n\n- Yes\n- No\n\n---\n\n### b [text]\nWhy?\n\n> show if: a is "No"\n')[1]
        self.assertFalse(any("same page" in w for w in warnings))

    def test_txt_refuses_text_that_reads_as_a_tag(self):
        survey = qc.parse_markdown("# T\n\n## B\n\n### q [single]\nPick\n\n- [[Block:Evil]]\n- B\n")
        with self.assertRaisesRegex(qc.ConvertError, "starting with"):
            qc.build_txt(survey)
        self.assertTrue(any(l["fatal"] and "[[" in l["what"] for l in qc.txt_limits(survey)))

    def test_logic_text_keeps_the_join_between_groups(self):
        logic = {"0": {"0": {"Description": "If A Is Selected"}, "Type": "If"},
                 "1": {"0": {"Description": "If B Is Selected"}, "Type": "Or"}, "Type": "BooleanExpression"}
        self.assertEqual(qc.logic_text(logic), "If A Is Selected OR ( If B Is Selected )")

    def test_standard_input(self):
        done = run_in(MINIMAL, "to-qsf", "-")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(run_in(done.stdout, "validate", "--strict", "-").returncode, 0)



MATRIX = "# T\n\n## B\n\n### m [matrix]\nRate\n\nRows:\n- R1\n- R2\n- R3\n\nColumns:\n- C1\n- C2\n- C3\n"


class GeminiReviewFixes(unittest.TestCase):
    """Regressions for the late 2026-11-19 review findings; each failed on the version reviewed."""

    def reads_back(self, qsf):
        markdown, warnings, _ = to_md(qsf)
        qc.parse_markdown(markdown)  # raises if the Markdown written cannot be read back
        return markdown, warnings

    def test_reordered_matrix_rows_are_reported(self):
        qsf = build(MATRIX)[0]
        question_payload(qsf, "m")["ChoiceOrder"] = ["3", "1", "2"]
        self.assertTrue(any("row ids are not 1..n" in w for w in to_md(qsf)[1]))

    def test_stale_matrix_recode_key_keeps_the_column_codes(self):
        qsf = build(MATRIX)[0]
        payload = question_payload(qsf, "m")
        payload["Answers"] = {"1": {"Display": "C1"}, "2": {"Display": "C2"}, "5": {"Display": "C5"}}
        payload["AnswerOrder"] = ["1", "2", "5"]
        payload["RecodeValues"] = {"1": "1", "2": "2", "5": "5", "6": "6"}  # 6: a deleted column
        markdown = to_md(qsf)[0]
        self.assertIn("- C5 {code:5}", markdown)
        self.assertIn("- C1 {code:1}", markdown)

    def test_text_matrix_column_ids_that_are_not_1_to_n_are_reported(self):
        qsf = build("# T\n\n## B\n\n### m [matrix-text]\nRate\n\nRows:\n- R1\n- R2\n\nColumns:\n- C1\n- C2\n")[0]
        payload = question_payload(qsf, "m")
        payload["Answers"] = {"1": {"Display": "C1"}, "4": {"Display": "C2"}}
        payload["AnswerOrder"] = ["1", "4"]
        self.assertTrue(any("column ids are not 1..n" in w for w in to_md(qsf)[1]))

    def test_choice_ids_are_judged_in_the_order_shown(self):
        source = "# T\n\n## B\n\n### s [rank]\nX\n\n- A\n- B\n"
        qsf = build(source)[0]
        question_payload(qsf, "s")["ChoiceOrder"] = ["2", "1"]
        self.assertTrue(any("choice codes are not 1..n" in w for w in to_md(qsf)[1]))
        qsf = build(source)[0]
        payload = question_payload(qsf, "s")
        payload["Choices"] = {"2": payload["Choices"]["2"], "1": payload["Choices"]["1"]}  # key order only
        self.assertFalse(any("choice codes are not 1..n" in w for w in to_md(qsf)[1]))

    def test_tags_with_attributes_stay_balanced(self):
        self.assertEqual(qc.html_to_md('<div style="text-align:center">Hi</div>', keep_html=True)[0],
                         '<div style="text-align:center">Hi</div>')
        self.assertEqual(qc.html_to_md('<b style="color:red">Hi</b> there')[0], "<b>Hi</b> there")
        self.assertEqual(qc.html_to_md('A<br class="x"/>B')[0], "A\nB")
        text, dropped = qc.html_to_md("<style>p {color: red}</style>Rate <script>x()</script>us")
        self.assertEqual(text, "Rate us")
        self.assertEqual(dropped, ["script", "style"])

    def test_a_less_than_that_opens_no_tag_is_escaped(self):
        self.assertEqual(qc.md_to_html("<None>"), "&lt;None>")
        self.assertEqual(qc.md_to_html("<High school"), "&lt;High school")
        self.assertEqual(qc.md_to_html("R&D; Operations"), "R&amp;D; Operations")
        self.assertEqual(qc.md_to_html("<b>x</b> &copy; <o:p></o:p>"), "<b>x</b> &copy; <o:p></o:p>")
        # Numeric and upper-case references to "<" stay escaped when they would form a tag.
        self.assertEqual(qc.html_to_md("&#60;b&#62;bold &LT;i&GT;")[0], "&lt;b>bold &lt;i>")
        for option in ("<None>", "x<y", "<b>bold</b>"):
            self.assertEqual(qc.html_to_md(qc.md_to_html(option))[0], option)

    def test_missing_output_folder_is_bad_input(self):
        with tempfile.TemporaryDirectory() as folder:
            done = run_in(MINIMAL, "to-qsf", "-", "-o", str(pathlib.Path(folder) / "missing" / "out.qsf"))
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn("cannot write", done.stderr)

    def test_exports_whose_markdown_did_not_read_back(self):
        qsf = build("# T\n\n## B\n\n### n [nps]\nHow likely\n")[0]
        question_payload(qsf, "n")["ColumnLabels"] = [{"Display": "Not likely"}, {"Display": ""}]
        self.assertTrue(any("one of the two is blank" in w for w in self.reads_back(qsf)[1]))
        qsf = build("# T\n\n## B\n\n### s [slider]\nX\n\n- A\n")[0]
        question_payload(qsf, "s")["Configuration"]["CSSliderMax"] = True
        self.reads_back(qsf)
        for field in ({"Field": "src", "Value": "a\rb"}, {"Field": "src", "Value": "a\u2028b"}, {"Value": "1"},
                      {"Field": "foo ", "Value": "1"}):
            qsf = build(MINIMAL)[0]
            flow = element(qsf, "FL")["Payload"]["Flow"]
            flow.insert(0, {"Type": "EmbeddedData", "FlowID": "FL_9",
                            "EmbeddedData": [dict({"Type": "Custom", "VariableType": "String"}, **field)]})
            markdown, warnings = self.reads_back(qsf)
            self.assertNotIn("> embedded", markdown)
            self.assertTrue(any("embedded data not represented" in w for w in warnings))
        qsf = build(MINIMAL)[0]
        element(qsf, "BL")["Payload"][0]["Description"] = "   "
        self.assertIn("## BL_", self.reads_back(qsf)[0])
        qsf = build(MINIMAL)[0]
        qsf["SurveyEntry"]["SurveyName"] = "Survey <!-- draft"
        element(qsf, "BL")["Payload"][0]["Description"] = "Block <!-- 1"
        question_payload(qsf, "q1")["QuestionText"] = "Pick <!-- unclosed"
        markdown = self.reads_back(qsf)[0]
        self.assertTrue(markdown.startswith("# Survey <! -- draft"))

    def test_survey_with_no_block_in_the_flow_is_bad_input(self):
        qsf = build(MINIMAL)[0]
        element(qsf, "FL")["Payload"]["Flow"] = []
        done = run_in(json.dumps(qsf), "to-md", "-")
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn("no block", done.stderr)

    def test_markdown_that_does_not_read_back_is_an_internal_error(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "s.qsf"
            path.write_text(json.dumps(build(MINIMAL)[0]), encoding="utf-8")
            counts = {"blocks": 1, "questions": 1, "unsupported_questions": 0, "page_breaks": 0}
            broken = ("# T\n\n## \n", counts)  # what a whitespace-only block name used to give
            with mock.patch.object(qc.Reader, "markdown", return_value=broken), mock.patch("sys.stderr"):
                self.assertEqual(qc.main(["to-md", str(path)]), 2)


if __name__ == "__main__":
    unittest.main()
