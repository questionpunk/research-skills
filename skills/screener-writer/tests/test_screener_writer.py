"""Tests for scripts/screener_writer.py. Run from the skill folder: python3 -m unittest discover -s tests

Published example: the bad and good screener questions in Whitenton (2019), Nielsen Norman Group ("Do you play
online games?" versus a multiple-choice question with plausible distractors). Independent re-derivation: quota
feasibility checked by enumerating every allocation of a small total across cells.
"""
import importlib.util
import itertools
import json
import pathlib
import random
import subprocess
import sys
import tempfile
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "screener_writer.py"


def load_module():
    spec = importlib.util.spec_from_file_location("screener_writer", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(module)
    return module


M = load_module()


def run(*args, stdin=None):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                          check=False, input=stdin)


def run_json(*args):
    proc = run(*args, "--json")
    if proc.returncode != 0:
        raise AssertionError(f"exit {proc.returncode}: {proc.stderr}")
    return json.loads(proc.stdout)


def rules(out, severity=None):
    return sorted(f["rule"] for f in out["findings"] if severity is None or f["severity"] == severity)


SKELETON = """# Screener: test
study: survey

## Criteria
- C1: Uses a tool

## Questions
"""


class FixtureTest(unittest.TestCase):
    def test_good_screener_has_no_errors_or_warnings(self):
        out = run_json(FIXTURES / "good.md")
        self.assertEqual(rules(out, "error"), [])
        self.assertEqual(rules(out, "warning"), [])
        self.assertEqual(out["quotas"][0]["sum_min"], 10)
        self.assertEqual(out["quotas"][0]["sum_max"], 16)
        self.assertTrue(out["quotas"][0]["feasible"])

    def test_json_and_markdown_agree(self):
        md, js = run_json(FIXTURES / "good.md"), run_json(FIXTURES / "good.json")
        self.assertEqual(md["findings"], js["findings"])
        self.assertEqual(md["routing"], js["routing"])

    def test_bad_screener_finds_every_planted_mistake(self):
        exp = json.loads((FIXTURES / "bad.expected.json").read_text())["findings"]
        out = run_json(FIXTURES / "bad.md")
        self.assertEqual(sorted([f["rule"], f["where"]] for f in out["findings"]), exp)

    def test_strict_exit_code(self):
        self.assertEqual(run(FIXTURES / "bad.md", "--strict").returncode, 1)
        self.assertEqual(run(FIXTURES / "good.md", "--strict").returncode, 0)


class PublishedNNgroupTest(unittest.TestCase):
    """Whitenton (2019): 'Do you play online games?' reveals the topic and is a yes/no question; a question
    with plausible distractors (walking, ride sharing, taxis) is the recommended form."""

    @classmethod
    def setUpClass(cls):
        cls.out = run_json(FIXTURES / "nngroup_examples.md")

    def test_yes_no_question_is_flagged(self):
        q1 = sorted(f["rule"] for f in self.out["findings"] if f["where"] == "Q1")
        self.assertEqual(q1, ["SC08", "SC11"])

    def test_distractor_question_passes(self):
        q2 = sorted(f["rule"] for f in self.out["findings"] if f["where"] == "Q2")
        self.assertEqual(q2, ["SC16"])


class QuotaFeasibilityTest(unittest.TestCase):
    def test_matches_enumeration(self):
        rng = random.Random(4)
        for _ in range(150):
            k = rng.randint(1, 3)
            cells = []
            for _ in range(k):
                lo = rng.randint(0, 4)
                cells.append((lo, lo + rng.randint(0, 4)))
            total = rng.randint(1, 12)
            brute = any(sum(alloc) == total and all(lo <= a <= hi for a, (lo, hi) in zip(alloc, cells))
                        for alloc in itertools.product(range(13), repeat=k))
            opts = "; ".join(f'"o{i}" {lo}-{hi}' for i, (lo, hi) in enumerate(cells))
            options = "\n".join(f"- o{i} -> continue" for i in range(k)) + "\n- none of these -> terminate"
            text = (SKELETON.replace("## Questions", f"## Quotas\ntotal: {total}\n- Group (Q2): {opts}\n\n## Questions")
                    + "### Q1 [single] (C1)\nWhich?\n- a -> qualify\n- b -> continue\n- c -> continue\n- d -> terminate\n"
                    + f"### Q2 [single]\nSize?\n{options}\n")
            doc = M.parse_markdown(text)
            _, quotas = M.lint(doc)
            self.assertEqual(quotas[0]["feasible"], brute, (cells, total))


class RulesTest(unittest.TestCase):
    def lint(self, body, header=SKELETON):
        doc = M.parse_markdown(header + body)
        findings, _ = M.lint(doc)
        return sorted((f["rule"], f["where"]) for f in findings)

    def test_unreachable_and_goto(self):
        found = self.lint("### Q1 [single] (C1)\nWhich?\n- a -> qualify\n- b -> goto Q3\n- c -> continue\n"
                          "- d -> terminate\n### Q2 [single]\nX?\n- x -> goto Q9\n- y -> continue\n"
                          "### Q3 [open]\nTell us.\n")
        self.assertIn(("SC04", "Q2"), found)
        self.assertNotIn(("SC05", "Q2"), found)
        found = self.lint("### Q1 [single] (C1)\nWhich?\n- a -> goto Q3\n- b -> goto Q3\n- c -> terminate\n"
                          "### Q2 [single]\nX?\n- x -> continue\n- y -> continue\n### Q3 [open]\nTell us.\n")
        self.assertIn(("SC05", "Q2"), found)

    def test_nobody_qualifies(self):
        found = self.lint("### Q1 [single] (C1)\nWhich?\n- a -> terminate\n- b -> terminate\n")
        self.assertIn(("SC06", "Q1"), found)
        self.assertIn(("SC06", "screener"), found)

    def test_too_few_distractors(self):
        found = self.lint("### Q1 [single] (C1)\nWhich?\n- a -> qualify\n- b -> terminate\n- None of these -> terminate\n")
        self.assertIn(("SC09", "Q1"), found)

    def test_qualifying_option_always_first(self):
        q = "### Q{n} [single] (C1)\nWhich?\n- right -> qualify\n- w1 -> continue\n- w2 -> continue\n- w3 -> terminate\n"
        found = self.lint(q.format(n=1) + q.format(n=2))
        self.assertIn(("SC10", "screener"), found)

    def test_numeric_ranges(self):
        found = self.lint("### Q1 [numeric] (C1)\nHow many?\n- 0-4 -> terminate\n- 6-10 -> qualify\n- 11 or more -> qualify\n")
        self.assertIn(("SC14", "Q1"), found)
        detail = [f for f in M.lint(M.parse_markdown(SKELETON + "### Q1 [numeric] (C1)\nHow many?\n- 0-4 -> "
                                                     "terminate\n- 6-10 -> qualify\n"))[0] if f["rule"] == "SC14"]
        self.assertIn("nothing covers 5 to 5", detail[0]["detail"])
        self.assertEqual(M.range_problems(["Under 5", "5-9", "10 or more"]), [])
        self.assertEqual(M.range_problems(["1-49 employees", "50-999 employees", "1,000 or more employees"]), [])

    def test_quota_question_needs_no_distractors(self):
        header = SKELETON.replace("## Questions", '## Quotas\ntotal: 4\n- Shift (Q1): "Day" 2-2; "Night" 2-2\n\n'
                                                   '## Questions')
        found = self.lint("### Q1 [single] (C1)\nWhich shift do you usually work?\n- Day -> qualify\n"
                          "- Night -> qualify\n- Not working now -> terminate\n", header=header)
        self.assertNotIn(("SC09", "Q1"), found)

    def test_terminating_decoy_replaces_select_all_check(self):
        body = ("### Q1 [multi] (C1)\nWhich have you used?\n- a -> qualify\n- b -> continue\n- c -> continue\n"
                "- d -> continue\n- None of these -> terminate\n")
        self.assertIn(("SC16", "Q1"), self.lint(body))
        self.assertNotIn(("SC16", "Q1"), self.lint(body.replace("- d -> continue", "- Zentrix Planner -> terminate")))

    def test_screens_nothing(self):
        found = self.lint("### Q1 [single] (C1)\nWhich?\n- a -> continue\n- b -> continue\n")
        self.assertIn(("SC07", "Q1"), found)

    def test_leading_wording(self):
        found = self.lint("### Q1 [single] (C1)\nDon't you think meetings are too long?\n- a -> qualify\n- b -> continue\n"
                          "- c -> continue\n- d -> terminate\n")
        self.assertIn(("SC12", "Q1"), found)

    def test_prolific_note(self):
        found = self.lint("### Q1 [open]\nTell us.\n", header=SKELETON.replace("study: survey",
                                                                              "study: survey\nplatform: Prolific"))
        self.assertIn(("SC20", "screener"), found)

    def test_quota_cell_errors(self):
        header = SKELETON.replace("## Questions", '## Quotas\ntotal: 6\n- G (Q1): "a" 2-4; "a" 1-2; "zzz" 1-1; '
                                                   '"d" 1-1\n\n## Questions')
        found = self.lint("### Q1 [single] (C1)\nWhich?\n- a -> qualify\n- b -> continue\n- c -> continue\n"
                          "- d -> terminate\n", header=header)
        self.assertEqual(sum(1 for r in found if r[0] == "SC17"), 3)
        self.assertIn(("SC18", "quota G"), found)


class RouteTest(unittest.TestCase):
    """Regression tests from the 2026-11-19 review: routes that qualify people who fail a criterion."""

    def lint(self, body, header=SKELETON):
        findings, quotas = M.lint(M.parse_markdown(header + body))
        return findings, quotas

    def test_single_select_distractor_routed_to_continue_qualifies_non_targets(self):
        body = ("### Q1 [single] (C1)\nYour role in software decisions?\n- I decide -> qualify\n"
                "- I recommend -> qualify\n- Asked for feedback after it is chosen -> continue\n"
                "- Not involved -> terminate\n")
        findings, _ = self.lint(body)
        sc22 = [f for f in findings if f["rule"] == "SC22"]
        self.assertEqual([f["where"] for f in sc22], ["C1"])
        self.assertIn("Asked for feedback", sc22[0]["detail"])
        findings, _ = self.lint(body.replace("chosen -> continue", "chosen -> terminate"))
        self.assertNotIn("SC22", [f["rule"] for f in findings])

    def test_goto_around_knockout_is_reported(self):
        header = SKELETON.replace("- C1: Uses a tool", "- C1: Uses a tool\n- C2: Manages a team")
        body = ("### Q1 [single] (C1)\nWhich?\n- a -> qualify\n- b -> goto Q3\n- c -> terminate\n- d -> terminate\n"
                "### Q2 [single] (C2)\nTeam?\n- x -> qualify\n- y -> terminate\n- z -> terminate\n"
                "### Q3 [open]\nTell us.\n")
        findings, _ = self.lint(body, header)
        where = sorted(f["where"] for f in findings if f["rule"] == "SC22")
        self.assertEqual(where, ["C1", "C2"])  # 'b' fails C1 and skips C2's question

    def test_exclusion_needs_a_terminate(self):
        header = SKELETON.replace("- C1: Uses a tool", "- C1: Not a market researcher (exclude)")
        body = ("### Q1 [multi] (C1)\nWhich industries?\n- Health -> qualify\n- Retail -> qualify\n"
                "- Market research -> continue\n- None of these -> continue\n")
        findings, _ = self.lint(body, header)
        self.assertIn(("SC23", "C1"), [(f["rule"], f["where"]) for f in findings])

    def test_one_single_select_for_two_criteria_warns(self):
        header = SKELETON.replace("- C1: Uses a tool", "- C1: Employed\n- C2: Not in market research (exclude)")
        body = ("### Q1 [single] (C1, C2)\nWork?\n- Full time in health -> continue\n- Part time -> continue\n"
                "- Full time in market research -> terminate\n")
        findings, _ = self.lint(body, header)
        self.assertIn(("SC24", "Q1"), [(f["rule"], f["where"]) for f in findings])

    def test_quota_on_terminating_option_cannot_fill(self):
        header = SKELETON.replace("## Questions", '## Quotas\ntotal: 2\n- G (Q1): "A" 2\n\n## Questions')
        findings, quotas = self.lint("### Q1 [single] (C1)\nWhich?\n- A -> terminate\n- Other -> continue\n"
                                     "- b -> terminate\n", header)
        self.assertFalse(quotas[0]["feasible"])
        self.assertEqual(quotas[0]["sum_max"], 0)
        text = M.render(M.parse_markdown(header + "### Q1 [single] (C1)\nWhich?\n- A -> terminate\n"
                                         "- Other -> continue\n- b -> terminate\n"), findings, quotas)
        self.assertTrue(text.rstrip().endswith("total 2: cannot fill (see the SC17 findings)"), text)

    def test_quota_cell_whose_route_never_qualifies(self):
        header = SKELETON.replace("## Questions", '## Quotas\ntotal: 4\n- G (Q1): "a" 2-2; "b" 2-2\n\n## Questions')
        body = ("### Q1 [single] (C1)\nWhich?\n- a -> qualify\n- b -> goto Q2\n- c -> terminate\n"
                "### Q2 [single]\nSure?\n- x -> terminate\n- y -> terminate\n")
        findings, quotas = self.lint(body, header)
        self.assertFalse(quotas[0]["feasible"])

    def test_curly_quotes_in_quota_cells(self):
        header = SKELETON.replace("## Questions", "## Quotas\ntotal: 4\n- G (Q1): \u201ca\u201d 2-2; \u201cb\u201d 2-2\n\n"
                                                   "## Questions")
        findings, quotas = self.lint("### Q1 [single] (C1)\nWhich?\n- a -> qualify\n- b -> qualify\n"
                                     "- c -> terminate\n", header)
        self.assertTrue(quotas[0]["feasible"])


class RegressionTest(unittest.TestCase):
    def test_integer_between_under_and_over_is_a_gap(self):
        self.assertEqual(M.range_problems(["Under 5", "Over 5"]), ["gap: Under 5 / Over 5 (nothing covers 5 to 5)"])
        self.assertEqual(M.range_problems(["Under 5", "5 or more"]), [])
        self.assertEqual(M.range_problems(["0-49.99", "50-99.99", "100 or more"]), [])
        self.assertIn("reversed: 10-5 (the first number is larger than the second)",
                      M.range_problems(["0-4", "10-5"]))

    def test_format_reference_example_lints_clean(self):
        text = (SKILL / "references" / "screener-format.md").read_text()
        block = text.split("```markdown\n", 1)[1].split("```", 1)[0]
        findings, quotas = M.lint(M.parse_markdown(block))
        self.assertEqual([f["rule"] for f in findings if f["severity"] != "info"], [])
        self.assertTrue(quotas[0]["feasible"])

    def test_median_of_two_distractors(self):
        q = "x" * 45
        body = (f"### Q1 [single] (C1) randomize\nWhich?\n- {q} -> qualify\n- {'y' * 10} -> terminate\n"
                f"- {'z' * 30} -> terminate\n")
        findings, _ = M.lint(M.parse_markdown(SKELETON + body))
        self.assertIn("SC10", [f["rule"] for f in findings])  # median 20, not the longer 30

    def test_articulation_flag_needs_an_open_question(self):
        header = SKELETON.replace("study: survey", "study: interview")
        body = "### Q1 [single] (C1) articulation\nWhich?\n- a -> qualify\n- b -> terminate\n- c -> terminate\n"
        findings, _ = M.lint(M.parse_markdown(header + body))
        self.assertIn("SC15", [f["rule"] for f in findings])

    def test_none_detector_variants(self):
        for text in ("None of these", "I haven't used any of these", "I haven\u2019t used any of these",
                     "I have not done any of these", "Not any of the above"):
            self.assertTrue(M.is_none(text), text)
        self.assertFalse(M.is_none("Any of these, weekly"))


class GeminiReviewTest(unittest.TestCase):
    """Regression tests from the Gemini review of 2026-11-19."""

    def rules_for(self, body, header=SKELETON):
        findings, quotas = M.lint(M.parse_markdown(header + body))
        return sorted({(f["rule"], f["where"]) for f in findings}), quotas

    def test_units_starting_with_k_or_m_are_not_thousands_or_millions(self):
        self.assertEqual(M.range_problems(["Under 6 months", "6-12 months", "Over 12 months"]), [])
        self.assertEqual(M.range_problems(["1-5 meetings", "6-10 meetings"]), [])
        self.assertEqual(M.parse_range("10k-50k"), (10000.0, 50000.0))

    def test_criterion_whose_question_screens_nobody_is_an_error(self):
        header = SKELETON.replace("- C1: Uses a tool", "- C1: Not a market researcher (exclude)")
        found, _ = self.rules_for("### Q1 [single] (C1)\nIndustry?\n- Health -> continue\n- Research -> continue\n",
                                  header)
        self.assertIn(("SC23", "C1"), found)
        self.assertIn(("SC22", "C1"), found)
        found, _ = self.rules_for("### Q1 [single] (C1)\nWhich?\n- a -> qualify\n- b -> qualify\n- c -> qualify\n")
        self.assertIn(("SC07", "Q1"), found)
        found, _ = self.rules_for("### Q1 [open]\nTell us.\n".replace("[open]", "[open] (C1)"))
        self.assertIn(("SC07", "C1"), found)

    def test_second_level_screener_heading_keeps_the_header(self):
        doc = M.parse_markdown("## Screener: t\nstudy: interview\ntopic words: Asana\n## Criteria\n- C1: x\n"
                               "## Questions\n### Q1 [open] articulation\nTell us about Asana.\n")
        self.assertEqual((doc["title"], doc["study"], doc["topic_words"]), ("t", "interview", ["Asana"]))

    def test_continue_terminate_single_select_gets_distractor_checks(self):
        found, _ = self.rules_for("### Q1 [single] (C1)\nWork?\n- I manage a team of designers at a large agency "
                                  "-> continue\n- Retired -> terminate\n")
        self.assertIn(("SC09", "Q1"), found)
        self.assertIn(("SC10", "Q1"), found)

    def test_ranges_checked_beside_dont_know(self):
        found, _ = self.rules_for("### Q1 [single] (C1)\nEmployees?\n- 1 to 50 -> continue\n- 50 to 999 -> continue\n"
                                  "- Don't know -> terminate\n")
        self.assertIn(("SC14", "Q1"), found)

    def test_multi_select_tied_to_two_criteria_warns(self):
        header = SKELETON.replace("- C1: Uses a tool", "- C1: Uses Asana\n- C2: Uses Slack")
        found, _ = self.rules_for("### Q1 [multi] (C1, C2)\nUsed?\n- Asana -> qualify\n- Slack -> qualify\n"
                                  "- Zoom -> continue\n- None of these -> terminate\n", header)
        self.assertIn(("SC24", "Q1"), found)
        found, _ = self.rules_for("### Q1 [single] (C1, C1)\nW?\n- a -> qualify\n- b -> terminate\n- c -> terminate\n")
        self.assertNotIn(("SC24", "Q1"), found)

    def test_study_type_matched_by_word(self):
        body = "### Q1 [single] (C1)\nW?\n- a -> qualify\n- b -> terminate\n- c -> terminate\n"
        for study, flagged in (("Interview, 45 minutes", True), ("user interviews", True), ("usability test", True),
                               ("unmoderated usability test", False), ("survey", False)):
            found, _ = self.rules_for(body, SKELETON.replace("study: survey", f"study: {study}"))
            self.assertEqual(("SC15", "screener") in found, flagged, study)

    def test_curly_apostrophes(self):
        found, _ = self.rules_for("### Q1 [single] (C1)\nDon\u2019t you think so?\n- Yes -> qualify\n- No -> terminate\n"
                                  "- Don\u2019t know -> terminate\n")
        self.assertIn(("SC08", "Q1"), found)
        self.assertIn(("SC12", "Q1"), found)

    def test_end_actions_are_refused(self):
        for act in ("end", "qualify and end"):
            with self.assertRaises(M.InputError):
                M.parse_action(act, "x")

    def test_quota_without_total_is_not_feasible(self):
        header = SKELETON.replace("## Questions", '## Quotas\n- G (Q1): "a" 1-2\n\n## Questions')
        _, quotas = self.rules_for("### Q1 [single] (C1)\nW?\n- a -> qualify\n- b -> terminate\n- c -> terminate\n",
                                   header)
        self.assertFalse(quotas[0]["feasible"])

    def test_prolific_platform_variants(self):
        found, _ = self.rules_for("### Q1 [open]\nTell us.\n",
                                  SKELETON.replace("study: survey", "study: survey\nplatform: Prolific (US)"))
        self.assertIn(("SC20", "screener"), found)


class InputTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, text, encoding="utf-8"):
        path = pathlib.Path(self.tmp.name) / "s.md"
        path.write_bytes(text.encode(encoding))
        return path

    def test_refuses_bad_input(self):
        self.assertEqual(run(self.write("# Screener\n\nNo questions here.\n")).returncode, 2)
        self.assertEqual(run(self.write(SKELETON + "### Q1 (C1)\nWhich?\n- a -> qualify\n")).returncode, 2)
        self.assertEqual(run(self.write(SKELETON + "### Q1 [single]\nA?\n- a -> maybe later\n")).returncode, 2)
        dup = SKELETON + "### Q1 [open]\nA?\n### Q1 [open]\nB?\n"
        proc = run(self.write(dup))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("used twice", proc.stderr)
        self.assertEqual(run(pathlib.Path(self.tmp.name) / "missing.md").returncode, 2)
        self.assertEqual(run(self.write(SKELETON + "### Q1 [single] (C1)\nA?\nrequire: a\n- a -> qualify\n")).returncode, 2)

    def test_malformed_json_exits_2_with_location(self):
        for text, where in (('{"questions":[{}]}', "questions[1] needs 'id'"),
                            ('{"questions":[{"id":"Q1","type":"single","options":[{"action":"continue"}]}]}',
                             "Q1 option 1 needs 'text'"),
                            ('{"quotas":{"total":2,"groups":[{"question":"Q1","cells":[{"options":["a"]}]}]},'
                             '"questions":[{"id":"Q1","type":"open"}]}', "needs 'min'")):
            proc = run("-", stdin=text)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertIn(where, proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_utf16_and_stdin(self):
        text = (FIXTURES / "good.md").read_text()
        self.assertEqual(run_json(self.write(text, "utf-16"))["findings"], run_json(FIXTURES / "good.md")["findings"])
        proc = run("-", "--json", stdin=text)
        self.assertEqual(proc.returncode, 0)

    def test_list_rules(self):
        proc = run("--list-rules")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.count("\n"), len(M.RULES))


if __name__ == "__main__":
    unittest.main()
