"""Tests for scripts/survey_bias_check.py. Run from the skill folder: python3 -m unittest discover -s tests"""
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "survey_bias_check.py"

spec = importlib.util.spec_from_file_location("survey_bias_check", SCRIPT)
sbc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sbc)


def run_cli(*args, stdin=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, input=stdin)


def lint_text(markdown, **kwargs):
    questions, _, intro = sbc.parse_markdown(markdown)
    sbc.infer_types(questions)
    findings, length, unchecked = sbc.lint(questions, intro=intro, **kwargs)
    return findings, length, unchecked


def rules(findings):
    return sorted({f["rule"] for f in findings})


def one(stem, options=()):
    text = "1. %s\n" % stem + "".join("   - %s\n" % o for o in options)
    return lint_text(text)[0]


AGREE5 = ["Strongly agree", "Agree", "Neither agree nor disagree", "Disagree", "Strongly disagree"]
SAT5 = ["Very satisfied", "Somewhat satisfied", "Neither satisfied nor dissatisfied", "Somewhat dissatisfied",
        "Very dissatisfied"]


class FixtureTest(unittest.TestCase):
    def check(self, name, source):
        expected = json.loads((FIXTURES / (name + ".expected.json")).read_text())
        result = run_cli(str(FIXTURES / source), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        got = json.loads(result.stdout)
        self.assertEqual(got["questions"], expected["questions"])
        fields = ("question", "line", "rule", "kind", "severity", "match")
        key = lambda f: (f["question"], f["rule"], f["kind"])
        self.assertEqual(sorted(([f[k] for k in fields] for f in got["findings"]), key=str),
                         sorted(([f[k] for k in fields] for f in expected["findings"]), key=str))
        self.assertEqual(len({key(f) for f in got["findings"]}), len(got["findings"]))
        self.assertEqual({k: got["summary"][k] for k in expected["summary"]}, expected["summary"])
        for k, v in expected["length"].items():
            self.assertAlmostEqual(got["length"][k], v, places=2)
        for f in got["findings"]:
            self.assertTrue(f["why"] and f["name"])

    def test_flawed_questionnaire_matches_hand_list(self):
        self.check("flawed", "flawed.input.md")

    def test_clean_questionnaire_has_no_findings(self):
        self.check("clean", "clean.input.md")

    def test_json_input_matches_hand_list(self):
        self.check("mini", "mini.input.json")

    def test_second_flawed_questionnaire_matches_hand_list(self):
        self.check("gaps", "gaps.input.md")

    def test_second_clean_questionnaire_has_no_findings(self):
        self.check("gaps_clean", "gaps_clean.input.md")

    def test_unnumbered_input(self):
        self.check("unnumbered", "unnumbered.input.txt")
        got = json.loads(run_cli(str(FIXTURES / "unnumbered.input.txt"), "--json").stdout)
        self.assertEqual(len(got["warnings"]), 1)
        self.assertIn("no question numbers", got["warnings"][0])
        self.assertTrue(got["has_intro"])

    def test_every_rule_except_length_fires_in_the_flawed_fixtures(self):
        fired = set()
        for name in ("flawed.input.md", "gaps.input.md"):
            fired |= set(rules(json.loads(run_cli(str(FIXTURES / name), "--json").stdout)["findings"]))
        self.assertEqual(sorted(fired), sorted(set(sbc.RULES) - {"SB015"}))

    def test_long_fixture_is_over_ideal_length(self):
        got = json.loads(run_cli(str(FIXTURES / "long.input.json"), "--json").stdout)
        self.assertEqual([(f["rule"], f["kind"], f["severity"]) for f in got["findings"]], [("SB015", "over_ideal", "low")])
        self.assertEqual(got["length"]["points"], 81.0)  # 27 open questions x 3 points
        self.assertAlmostEqual(got["length"]["minutes"], 10.12, places=2)


class RangeTest(unittest.TestCase):
    def test_hand_worked_range_cases(self):
        cases = json.loads((FIXTURES / "ranges.cases.json").read_text())["cases"]
        self.assertGreaterEqual(len(cases), 12)
        for case in cases:
            with self.subTest(case["name"]):
                self.assertEqual([list(p) for p in sbc.check_ranges(case["options"])], case["expected"])

    def test_numeric_rating_scale_is_not_a_range_set(self):
        stem = "How likely are you to recommend us to a friend or colleague?"
        self.assertEqual(rules(one(stem, [str(n) for n in range(11)])), ["SB020"])
        labelled = ["0 - Not at all likely"] + [str(n) for n in range(1, 10)] + ["10 - Extremely likely"]
        self.assertEqual(one(stem, labelled), [])

    def test_mixed_labels_are_not_treated_as_ranges(self):
        self.assertEqual(rules(one("Which plan are you on?", ["Free", "Team 1-10", "Team 10-50"])), [])


class LengthTest(unittest.TestCase):
    def test_over_maximum_is_medium(self):
        text = "".join("%d. What did you think of part %d?\n" % (i, i) for i in range(1, 55))  # 54 x 3 = 162 points
        findings, length, _ = lint_text(text)
        self.assertEqual(length["minutes"], 20.25)
        self.assertEqual([(f["rule"], f["kind"], f["severity"]) for f in findings], [("SB015", "over_maximum", "medium")])

    def test_exactly_ten_minutes_is_not_flagged(self):
        text = "".join("%d. Do you own a car?\n   - Yes\n   - No\n" % i for i in range(1, 81))  # 80 points
        findings, length, _ = lint_text(text)
        self.assertEqual(length["minutes"], 10.0)
        self.assertEqual(findings, [])

    def test_points_by_type(self):
        text = ("1. How many people live in your home? [number]\n"
                "2. Pick the tools you use. Select all that apply.\n" + "".join("   - Tool %s\n" % c for c in "ABCDEF") +
                "   - None of these\n"
                "3. Read this first. It is long. It has three sentences. Why did you join?\n")
        _, length, _ = lint_text(text, ignore={"SB011"})
        # number 2 + multi 7 options / 2 = 3.5 + open 3 plus 4 sentences // 3 = 1  -> 9.5 points
        self.assertEqual(length["points"], 9.5)
        self.assertEqual(length["seconds"], 71.2)


class NegativeTest(unittest.TestCase):
    """Clean wording that sits next to a rule and must NOT be flagged."""

    CLEAN = [
        ("Have you ever used a password manager?", ["Yes", "No"]),
        ("Which of the following best describes your current role?", ["Engineer", "Designer", "Other"]),
        ("How would you rate the checkout process?", ["Very good", "Good", "Neither good nor poor", "Poor", "Very poor"]),
        ("How would you describe your experience in a few words?", []),
        ("How often did you exercise in the past 7 days?", ["0 days", "1-2 days", "3-4 days", "5-7 days"]),
        ("Do you support or oppose the proposal?",
         ["Strongly support", "Somewhat support", "Neither support nor oppose", "Somewhat oppose", "Strongly oppose"]),
        ("Overall, how satisfied or dissatisfied are you with delivery?", SAT5),
        ("Did you read the terms and conditions before you signed up?", ["Yes", "No"]),
        ("How clear was the invoice, where 1 is unclear and 5 is very clear?", ["1", "2", "3", "4", "5"]),
        ("Is the price between 5 and 10 dollars fair?", ["Yes", "No"]),
        ("To what extent do you agree or disagree with the statement?", []),
        ("How important is price when you choose a supplier?",
         ["Not at all important", "Slightly important", "Moderately important", "Very important", "Extremely important"]),
        ("How useful was the guide?", ["Not at all useful", "Slightly useful", "Moderately useful", "Very useful", "Extremely useful"]),
        ("Does your team use an applicant tracking system (ATS)?", ["Yes", "No", "Not sure"]),
        ("Which US state do you live in?", []),
        ("Did the IT team resolve your request?", ["Yes", "No"]),
        ("What is one thing we could do better?", []),
        ("Which of these did you not receive?", ["Invoice", "Receipt", "Contract", "Other", "None of these"]),
        ("How much do you spend on software each month?", ["Under $50", "$50-$99", "$100-$499", "$500 or more"]),
        ("WHAT IS YOUR FAVOURITE FEATURE?", []),
        ("How many great-grandchildren do you have?", ["0", "1-2", "3 or more"]),
        ("Why or why not?", []),
        ("How many people are on your team, including you?", ["Just me", "2-5", "6-20", "21 or more"]),
        ("In the past 30 days, when did you last log in?", ["Today", "This week", "This month", "Longer ago", "Not once"]),
        ("How satisfied or dissatisfied are you with our customer support?", SAT5 + ["I have not contacted support"]),
        ("How long have you been a customer?", ["Less than 6 months", "6 months to 1 year", "1-2 years", "3 or more years"]),
        ("How much do you trust the information on our website?", ["A great deal", "A fair amount", "Not very much", "Not at all"]),
        ("How did you first hear about us?", ["Search engine", "Social media", "Friend or family member", "Advertisement", "Other"]),
        ("In which year did you start using the product?", ["2023", "2024", "2025", "2026"]),
    ]

    def test_clean_questions_are_not_flagged(self):
        for stem, options in self.CLEAN:
            with self.subTest(stem):
                self.assertEqual([(f["rule"], f["match"]) for f in one(stem, options)], [])

    def test_fixed_phrase_and_defined_acronym(self):
        self.assertEqual(one("Is the Net Promoter Score (NPS) reported in your health and safety review?", ["Yes", "No"]), [])

    def test_or_is_only_checked_on_rating_and_yes_no_questions(self):
        self.assertEqual(one("Which do you use more, email or chat?", ["Email", "Chat"]), [])
        self.assertEqual(rules(one("Was the agent polite or helpful?", ["Yes", "No"])), ["SB001"])

    def test_single_negation_outside_yes_no_and_agree_is_not_flagged(self):
        self.assertEqual(one("What did you not like about the trial?"), [])

    def test_consistent_scales_are_not_flagged(self):
        text = "1. The app is fast.\n" + "".join("   - %s\n" % o for o in AGREE5) + \
               "2. The app is stable.\n" + "".join("   - %s\n" % o for o in AGREE5 + ["Don't know"])
        self.assertEqual(rules(lint_text(text)[0]), ["SB014"])

    def test_complete_list_with_other_and_ten_options(self):
        options = ["Option %s" % c for c in "ABCDEFGHIJ"] + ["Other"]
        self.assertEqual(one("Which option did you pick?", options), [])

    def test_demographics_at_the_end_with_prefer_not_to_say(self):
        text = ("1. Do you own a bicycle?\n   - Yes\n   - No\n"
                "2. What is your gender? *\n   - Woman\n   - Man\n   - Non-binary\n   - Prefer not to say\n"
                "3. What is your religion? *\n   - Option A\n   - Option B\n   - Other\n   - Prefer not to say\n")
        self.assertEqual(lint_text(text)[0], [])

    def test_survey_of_only_demographics_has_no_opening_finding(self):
        self.assertEqual(one("What is your age?", ["18-34", "35-54", "55+"]), [])


class PositiveTest(unittest.TestCase):
    def test_each_wording_rule(self):
        cases = {
            "SB001": ("Overall, how satisfied or dissatisfied are you with our pricing and support?", SAT5),
            "SB002": ("Most people like the redesign. What do you think of it?", []),
            "SB003": ("Does everyone on your team use the app?", []),
            "SB004": ("Imagine a version with offline mode. What do you think of it?", []),
            "SB006": ("Do you regularly back up your files?", ["Yes", "No"]),
            "SB007": ("How do you track MRR today?", []),
            "SB008": ("What is the " + " ".join(["word"] * 17) + " extra?", []),
        }
        for rule, (stem, options) in cases.items():
            with self.subTest(rule):
                self.assertEqual(rules(one(stem, options)), [rule])

    def test_twenty_words_is_not_long(self):
        self.assertEqual(one("What is the " + " ".join(["word"] * 17)), [])

    def test_pew_double_negative_example(self):
        findings = one("Do you favor or oppose not allowing gays and lesbians to legally marry?",
                       ["Favor", "Oppose"])
        self.assertIn(("SB005", "double"), [(f["rule"], f["kind"]) for f in findings])

    def test_established_unbalanced_scale_is_low_severity(self):
        findings = one("How is your health in general?", ["Excellent", "Very good", "Good", "Fair", "Poor"])
        self.assertEqual([(f["rule"], f["severity"]) for f in findings if f["rule"] == "SB009"], [("SB009", "low")])

    def test_not_satisfied_counts_as_negative(self):
        findings = one("How satisfied are you with onboarding?", ["Very satisfied", "Satisfied", "Not satisfied"])
        self.assertEqual([f["match"] for f in findings if f["rule"] == "SB009"], ["2 positive vs 1 negative labels"])

    def test_required_sensitive_without_opt_out(self):
        text = "1. Do you own a bicycle?\n   - Yes\n   - No\n2. What is your religion? (required)\n   - Option A\n   - Option B\n"
        self.assertEqual([(f["rule"], f["kind"]) for f in lint_text(text)[0]], [("SB016", "required")])

    def test_more_than_ten_options(self):
        options = ["Option %s" % c for c in "ABCDEFGHIJK"] + ["Other"]
        self.assertEqual([f["match"] for f in one("Which option did you pick?", options)], ["11 options"])
        self.assertEqual(lint_text("1. Pick one.\n" + "".join("   - %s\n" % o for o in options), max_options=11)[0], [])

    def test_non_english_question_is_marked_unchecked(self):
        findings, _, unchecked = lint_text("1. ¿Con qué frecuencia utiliza siempre nuestra aplicación móvil?\n")
        self.assertEqual(findings, [])
        self.assertEqual([u["question"] for u in unchecked], ["1"])


def pairs(findings):
    return sorted((f["rule"], f["kind"]) for f in findings)


class NewRuleTest(unittest.TestCase):
    """SB017 to SB027: a positive and a negative case for each."""

    def test_sb017_reference_period(self):
        self.assertEqual(pairs(one("How many times did you call support?")), [("SB017", "no_period")])
        self.assertEqual(pairs(one("Have you contacted support?")), [("SB017", "no_period")])
        self.assertEqual(pairs(one("In the last year, how many hours did you spend in meetings?")), [("SB017", "long_window")])
        for stem in ["How many times did you call support in the past 30 days?", "How long have you been a customer?",
                     "Have you ever contacted support?", "Have you heard of our loyalty scheme?",
                     "How many hours a day do you spend in meetings?", "In the past 12 months, did you move home?"]:
            with self.subTest(stem):
                self.assertEqual(one(stem), [])

    def test_sb018_assumption(self):
        often = ["Daily", "Weekly", "Monthly"]
        self.assertEqual(pairs(one("How often do you use the report each month?", often)), [("SB018", "behaviour")])
        self.assertEqual(pairs(one("Why did you cancel in the past year?", ["Price", "Quality", "Service"])),
                         [("SB018", "behaviour")])
        self.assertIn(("SB018", "experience"), pairs(one("How satisfied or dissatisfied are you with the reports?", SAT5)))
        # a zero option, a 'does not apply' option, 'overall', or an earlier filter question each clear it
        self.assertEqual(one("How often do you use the report each month?", often + ["Never"]), [])
        self.assertEqual(one("How satisfied or dissatisfied are you with the reports?", SAT5 + ["Not applicable"]), [])
        self.assertEqual(one("Overall, how satisfied or dissatisfied are you with us?", SAT5), [])
        text = ("1. Have you used the reports in the past 30 days?\n   - Yes\n   - No\n"
                "2. How satisfied or dissatisfied are you with the reports?\n" + "".join("   - %s\n" % o for o in SAT5))
        self.assertEqual(lint_text(text)[0], [])
        self.assertEqual(one("Why did you cancel in the past year?"), [])  # open question: not checked

    def test_sb019_stem_and_options(self):
        self.assertEqual(pairs(one("Overall, how satisfied are you with us?", ["Yes", "No"])), [("SB019", "mismatch")])
        self.assertEqual(pairs(one("How likely or unlikely are you to renew?", SAT5)), [("SB019", "mismatch")])
        self.assertEqual(pairs(one("Overall, how satisfied are you with us?", SAT5)), [("SB019", "one_sided")])
        self.assertEqual(pairs(one("Is the app easy to use?", ["Very satisfied", "Satisfied", "Dissatisfied"])),
                         [("SB009", "balance"), ("SB019", "closed_stem")])
        likely = ["Very likely", "Somewhat likely", "Neither likely nor unlikely", "Somewhat unlikely", "Very unlikely"]
        self.assertEqual(one("How likely or unlikely are you to renew?", likely), [])
        self.assertEqual(one("Overall, how satisfied are you with us?",
                             ["Not at all satisfied", "Slightly satisfied", "Moderately satisfied", "Very satisfied"]), [])
        self.assertNotIn("SB019", rules(one("Is the app easy or difficult to use?", ["Very easy", "Easy", "Difficult", "Very difficult"])))
        self.assertNotIn("SB019", rules(one("Do you agree that the app is fast?", AGREE5)))

    def test_sb020_unlabelled_scale(self):
        five = ["1", "2", "3", "4", "5"]
        self.assertEqual(pairs(one("Rate the checkout.", five)), [("SB020", "unlabelled")])
        self.assertEqual(pairs(one("Rate the checkout. [scale]")), [("SB020", "unlabelled")])
        self.assertEqual(one("Rate the checkout, where 1 means very poor and 5 means very good.", five), [])
        self.assertEqual(one("Rate the checkout.", ["1 - Very poor", "2", "3", "4", "5 - Very good"]), [])
        self.assertEqual(one("How many cars does your household own?", ["0", "1", "2", "3"]), [])
        self.assertEqual(one("In which year did you join?", ["2023", "2024", "2025"]), [])

    def test_sb021_sensitive_behaviour(self):
        for stem in ["Have you ever cheated on your taxes?", "Did you vote in the last election?",
                     "In the past 7 days, on how many days did you drink alcohol?"]:
            with self.subTest(stem):
                self.assertEqual(rules(one(stem)), ["SB021"])
        for stem in ["Do you drink water during a workout?", "Do you take the stairs at work?",
                     "Which drug store do you shop at?"]:
            with self.subTest(stem):
                self.assertEqual(one(stem), [])

    def test_sb022_combined_opt_out(self):
        base = ["Slack", "Teams"]
        for label in ["None / Other", "Don't know / Prefer not to say", "N/A or other"]:
            with self.subTest(label):
                self.assertIn(("SB022", "combined"), pairs(one("Which tool do you use?", base + [label])))
        for label in ["Don't know / Not sure", "Other (please specify)", "I don't use a chat tool or other software",
                      "None of these"]:
            with self.subTest(label):
                self.assertNotIn("SB022", rules(one("Which tool do you use?", base + [label])))

    def test_sb023_mental_computation(self):
        self.assertEqual(pairs(one("What is your average monthly spend as a percentage of income?")),
                         [("SB023", "computation")])
        self.assertEqual(pairs(one("How much do you spend on travel per year? [number]")), [("SB023", "computation")])
        self.assertEqual(one("How much did you spend on travel last month? [number]"), [])
        self.assertEqual(one("What do you think of the average commute in your city?"), [])  # not asking for a number

    def test_sb024_introduction(self):
        body = "1. Do you own a bicycle?\n   - Yes\n   - No\n"
        self.assertEqual(pairs(lint_text("Most people love cycling. We hope to show that it is popular.\n" + body)[0]),
                         [("SB024", "leading"), ("SB024", "no_time_estimate")])
        self.assertEqual(pairs(lint_text("Thank you for taking part.\n" + body)[0]), [("SB024", "no_time_estimate")])
        for intro in ["This takes about 3 minutes.", "There are 5 questions.", "It takes a couple of minutes.",
                      "It takes 2-3 min."]:
            with self.subTest(intro):
                self.assertEqual(lint_text(intro + "\n" + body)[0], [])
        self.assertEqual(lint_text("# A heading is not an introduction\n" + body)[0], [])

    def test_sb024_json_intro(self):
        payload = json.dumps({"intro": "Experts say cycling is good.", "questions": [{"text": "Do you own a bicycle?", "options": ["Yes", "No"]}]})
        got = json.loads(run_cli("-", "--json", stdin=payload).stdout)
        self.assertEqual(pairs(got["findings"]), [("SB024", "leading"), ("SB024", "no_time_estimate")])
        self.assertEqual(run_cli("-", stdin='{"intro": 5, "questions": [{"text": "Q?"}]}').returncode, 2)

    def grid(self, rows):
        return ("1. How satisfied or dissatisfied are you with each part overall?\n"
                + "".join("   %s) Part %s\n" % (c, c.upper()) for c in "abcdefghijklmnop"[:rows])
                + "".join("   - %s\n" % o for o in SAT5))

    def test_sb025_grid_rows(self):
        self.assertEqual(pairs(lint_text(self.grid(11))[0]), [("SB025", "grid_rows")])
        self.assertEqual(lint_text(self.grid(10))[0], [])
        self.assertEqual(pairs(lint_text(self.grid(6), max_grid_rows=5)[0]), [("SB025", "grid_rows")])

    def test_sb025_open_questions(self):
        closed = "1. Do you own a bicycle?\n   - Yes\n   - No\n"
        opens = "".join("%d. What else about topic %d?\n" % (n, n) for n in range(2, 6))
        self.assertEqual(pairs(lint_text(closed + opens)[0]), [("SB025", "open_count")])
        self.assertEqual(lint_text(closed + "2. What else?\n3. Why?\n4. What next?\n")[0], [])
        self.assertEqual(lint_text(closed + opens, max_open=4)[0], [])
        self.assertEqual(pairs(lint_text("1. What do you want?\n2. Do you own a bicycle?\n   - Yes\n   - No\n")[0]),
                         [("SB025", "open_first")])
        # a paste of bare questions has no known question types, so the open-question rules stay silent
        self.assertEqual(lint_text("".join("%d. What about part %d?\n" % (n, n) for n in range(1, 7)))[0], [])

    def test_sb026_syntax_load(self):
        self.assertEqual(pairs(one("If you own a car, how much did you spend on it last month, excluding fuel? [number]")),
                         [("SB026", "load")])
        self.assertEqual(one("How much did you spend on your car last month, excluding fuel? [number]"), [])
        self.assertEqual(one("If you own a car, how much did you spend on it last month? [number]"), [])

    def test_sb027_even_point_scale_is_a_note(self):
        four = ["Very satisfied", "Somewhat satisfied", "Somewhat dissatisfied", "Very dissatisfied"]
        found = one("Overall, how satisfied or dissatisfied are you with us?", four)
        self.assertEqual([(f["rule"], f["severity"]) for f in found], [("SB027", "info")])
        text = "1. Overall, how satisfied or dissatisfied are you with us?\n" + "".join("   - %s\n" % o for o in four)
        strict = run_cli("-", "--strict", stdin=text)
        self.assertEqual(strict.returncode, 0)  # a note alone does not fail --strict
        self.assertIn("1 note(s)", strict.stdout)
        self.assertEqual(one("Overall, how satisfied or dissatisfied are you with us?", SAT5), [])


class ThirdPassTest(unittest.TestCase):
    """Cases from the lead's unseen questionnaires. Expectations written before the rules were changed."""

    CLOSED = "2. Do you own a bicycle?\n   - Yes\n   - No\n"

    def test_numeric_entry_is_not_an_open_question(self):
        for stem in ["In the last 7 days, on how many days did you visit the gym?", "What is your age?",
                     "How much did you pay for your last visit?", "How long did you wait at reception yesterday?",
                     "In which year did you join?"]:
            with self.subTest(stem):
                findings, length, _ = lint_text("1. %s\n" % stem + self.CLOSED)
                self.assertNotIn("SB025", rules(findings))
                self.assertEqual(length["points"], 3.0)  # numeric entry 2 + single choice 1
                self.assertEqual(length["points_by_type"], {"number": 2.0, "single": 1.0})

    def test_open_text_first_is_still_flagged(self):
        for stem in ["What do you want from the gym?", "Why did you join?", "Tell us about your last visit.",
                     "How much do you like the new lockers?"]:
            with self.subTest(stem):
                findings, length, _ = lint_text("1. %s\n" % stem + self.CLOSED)
                self.assertEqual(pairs(findings), [("SB025", "open_first")])
                self.assertEqual(length["points"], 4.0)  # open 3 + single choice 1

    def test_numeric_entries_do_not_count_as_open_questions(self):
        numbers = "".join("%d. In the past 7 days, how many times did you use room %d?\n" % (n, n) for n in range(3, 8))
        self.assertEqual(lint_text("1. Do you own a car?\n   - Yes\n   - No\n" + self.CLOSED + numbers)[0], [])

    def test_which_do_you_use_needs_other_and_none(self):
        short = ["Treadmill", "Rowing machine", "Free weights"]
        self.assertEqual(pairs(one("Which equipment do you use?", short)), [("SB011", "none"), ("SB011", "other")])
        self.assertEqual(pairs(one("Which of these devices do you own?", ["Phone", "Tablet"])),
                         [("SB011", "none"), ("SB011", "other")])
        self.assertEqual(pairs(one("Which equipment have you used in the past 7 days?", short + ["Other"])),
                         [("SB011", "none")])
        self.assertEqual([f["severity"] for f in one("Which equipment do you use?", short)], ["low", "low"])

    def test_which_questions_that_are_complete_or_ordered_stay_clean(self):
        short = ["Treadmill", "Rowing machine", "Free weights"]
        self.assertEqual(one("Which equipment do you use?", short + ["Other (please specify)", "None of these"]), [])
        self.assertEqual(one("Which do you use more, email or chat?", ["Email", "Chat"]), [])
        self.assertEqual(one("Which machine do you use most?", short), [])
        self.assertEqual(one("Which gym location is closest to your home?", short), [])
        self.assertEqual(one("Which plan length do you have?", ["1 month", "3 months", "12 months"]), [])
        self.assertEqual(one("How often do you use the pool each week?", ["Never", "Once", "Twice", "More often"]), [])

    def test_amount_ladder_without_a_zero_end(self):
        found = one("How much do you like the new lockers?", ["A lot", "Quite a lot", "Somewhat", "Not much"])
        self.assertEqual([(f["rule"], f["kind"], f["severity"], f["match"]) for f in found],
                         [("SB009", "ladder", "medium", "2 high vs 1 low labels, no zero point")])
        self.assertEqual(pairs(one("How important is price to you?", ["Extremely", "Very", "Somewhat", "Slightly"])),
                         [("SB009", "ladder")])

    def test_genuine_unipolar_scales_stay_clean(self):
        for options in (["Not at all", "Slightly", "Moderately", "Very", "Extremely"],
                        ["Extremely important", "Very important", "Moderately important", "Slightly important", "Not at all important"],
                        ["A great deal", "A fair amount", "Not very much", "Not at all"],
                        ["Very", "Somewhat", "Not very"],
                        ["A lot", "Somewhat", "A little", "Not at all"]):
            with self.subTest(options[0]):
                self.assertEqual(one("How much does price matter to you?", options), [])


class FlagTest(unittest.TestCase):
    def test_phone_mode(self):
        text = ("1. Which colour do you prefer?\n" + "".join("   - Colour %s\n" % c for c in "ABCDEF") + "   - Other\n")
        self.assertEqual(json.loads(run_cli("-", "--json", stdin=text).stdout)["summary"]["total"], 0)
        phone = json.loads(run_cli("-", "--json", "--mode", "phone", stdin=text).stdout)
        self.assertEqual(pairs(phone["findings"]), [("SB013", "count")])
        self.assertEqual(phone["length"]["minutes"], 0.19)  # 1 point / 8 x 1.5 = 0.1875
        self.assertEqual(json.loads(run_cli("-", "--json", "--mode", "phone", "--max-options", "6", stdin=text).stdout)["summary"]["total"], 0)

    def test_expert_audience_silences_jargon(self):
        text = "1. How do you track MRR today?\n"
        self.assertEqual(json.loads(run_cli("-", "--json", stdin=text).stdout)["summary"]["low"], 1)
        self.assertEqual(json.loads(run_cli("-", "--json", "--audience", "expert", stdin=text).stdout)["findings"], [])

    def test_keep_marks_findings_and_leaves_them_out_of_the_count(self):
        got = json.loads(run_cli(str(FIXTURES / "flawed.input.md"), "--json", "--keep", "Q11,12").stdout)
        kept = [f for f in got["findings"] if f["status"] == "keep as is"]
        self.assertEqual(sorted({f["question"] for f in kept}), ["11", "11b", "12"])
        self.assertEqual(got["summary"]["kept"], 6)   # Q11: 1, Q11b: 1, Q12: 3 findings and 1 note
        self.assertEqual(got["summary"]["total"], 22)  # 27 - 5
        self.assertEqual(got["summary"]["info"], 0)
        self.assertIn("[keep as is]", run_cli(str(FIXTURES / "flawed.input.md"), "--keep", "Q12").stdout)

    def test_keep_unknown_question_is_an_error(self):
        result = run_cli(str(FIXTURES / "clean.input.md"), "--keep", "Q99")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not in the input", result.stderr)

    def test_unnumbered_lines_that_are_not_questions_are_reported(self):
        got = json.loads(run_cli("-", "--json", stdin="Do you own a car?\n- Yes\n- No\nThe app is fast\n- Yes\n- No\n").stdout)
        self.assertEqual(got["questions"], 1)
        self.assertTrue(any("not recognised" in w for w in got["warnings"]))


class ParserTest(unittest.TestCase):
    def test_markdown_variants(self):
        text = ("Intro text that is ignored.\n\n"
                "**Q1. Pick the tools you use (select all that apply) [required]**\n"
                "* Hammer\n+ Saw\n( ) None of these\n\n"
                "2) How was it? [scale]\n   continued on a second line\n- Good\n- Poor\n   A note after the options.\n")
        questions, warnings, intro = sbc.parse_markdown(text)
        self.assertEqual(warnings, [])
        self.assertEqual(intro, {"text": "Intro text that is ignored.", "line": 1})
        self.assertEqual([q["id"] for q in questions], ["1", "2"])
        self.assertTrue(questions[0]["required"])
        self.assertEqual(questions[0]["text"], "Pick the tools you use (select all that apply)")
        self.assertEqual([o["text"] for o in questions[0]["options"]], ["Hammer", "Saw", "None of these"])
        self.assertEqual(questions[1]["type"], "scale")
        self.assertEqual(questions[1]["text"], "How was it? continued on a second line")
        self.assertEqual(len(questions[1]["options"]), 2)

    def test_stdin_and_text_output(self):
        result = run_cli("-", stdin="1. Do you always floss?\n   - Yes\n   - No\n")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Q1 (line 1)  SB003  medium  absolute", result.stdout)
        self.assertIn("match: always", result.stdout)
        self.assertIn("Estimated length: 1.0 points", result.stdout)
        self.assertIn("candidates", result.stdout)
        self.assertIn("does not replace a pretest", result.stdout)
        self.assertIn("No introduction text was given", result.stdout)

    def test_strict_exit_codes(self):
        self.assertEqual(run_cli(str(FIXTURES / "flawed.input.md"), "--strict").returncode, 1)
        self.assertEqual(run_cli(str(FIXTURES / "clean.input.md"), "--strict").returncode, 0)
        self.assertEqual(run_cli(str(FIXTURES / "flawed.input.md")).returncode, 0)

    def test_ignore_and_list_rules(self):
        got = json.loads(run_cli(str(FIXTURES / "flawed.input.md"), "--json", "--ignore", "sb011,SB016").stdout)
        self.assertEqual(got["summary"]["total"], 22)
        listed = run_cli("--list-rules").stdout
        for rule in sbc.RULES:
            self.assertIn(rule, listed)

    def test_warnings_for_duplicate_numbers_and_single_option(self):
        got = json.loads(run_cli("-", "--json", stdin="1. Colour?\n   - Red\n1. Size?\n").stdout)
        self.assertEqual(len(got["warnings"]), 2)


class BadInputTest(unittest.TestCase):
    def assert_error(self, result, text):
        self.assertEqual(result.returncode, 2)
        self.assertIn(text, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_missing_file(self):
        self.assert_error(run_cli("/nonexistent/survey.md"), "cannot read")

    def test_empty_input(self):
        self.assert_error(run_cli("-", stdin="  \n"), "input is empty")

    def test_no_questions(self):
        self.assert_error(run_cli("-", stdin="Just a paragraph with no numbered questions.\n"), "no questions found")

    def test_invalid_json(self):
        self.assert_error(run_cli("-", "--format", "json", stdin='{"questions": ['), "not valid JSON")

    def test_json_shape_errors(self):
        for payload, message in [('{"title": "x"}', "list of questions"), ('[{"options": ["a"]}]', 'has no "text"'),
                                 ('[{"text": "Q?", "type": "matrix"}]', "unknown type"),
                                 ('[{"text": "Q?", "options": "Yes"}]', "must be a list"),
                                 ('[{"text": "Q?", "options": [null]}]', "needs text"), ('["Q?"]', "not an object")]:
            with self.subTest(payload):
                self.assert_error(run_cli("-", "--format", "json", stdin=payload), message)

    def test_unknown_ignore_rule(self):
        self.assert_error(run_cli(str(FIXTURES / "clean.input.md"), "--ignore", "SB999"), "unknown rule ID")

    def test_no_input_argument(self):
        self.assertEqual(run_cli().returncode, 2)

    def test_binary_file(self):
        with tempfile.NamedTemporaryFile(suffix=".md") as handle:
            handle.write(b"\xff\xfe\x00\x01")
            handle.flush()
            self.assert_error(run_cli(handle.name), "cannot read")


def cli_json(*args, stdin=None):
    result = run_cli(*args, "--json", stdin=stdin)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def kinds(report):
    return [(f["question"], f["rule"], f["kind"]) for f in report["findings"]]


class ReviewFixTest(unittest.TestCase):
    """Regressions for the 2026-11-19 review findings; each failed on the version reviewed."""

    def test_bom_does_not_turn_the_first_question_into_an_introduction(self):
        got = cli_json("-", stdin="\ufeff1. Did you attend?\n- Yes\n- No\n2. Did you return?\n- Yes\n- No\n")
        self.assertEqual((got["questions"], got["has_intro"]), (2, False))

    def test_bom_json_file_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "bom.json"
            path.write_bytes(b'\xef\xbb\xbf[{"text": "Did you attend?", "options": ["Yes", "No"]}]')
            self.assertEqual(cli_json(str(path))["questions"], 1)

    def test_wide_range_overlaps_every_range_it_contains_and_invents_no_gap(self):
        self.assertEqual(sbc.check_ranges(["0-100", "10-20", "30-40"]),
                         [("overlap", "0-100 / 10-20"), ("overlap", "0-100 / 30-40")])

    def test_cents_in_the_stem_make_whole_dollar_ranges_gapped(self):
        self.assertEqual(sbc.check_ranges(["$0-$10", "$11-$20"], "How much, in dollars and cents?"),
                         [("gap", "$0-$10 / $11-$20")])
        self.assertEqual(sbc.check_ranges(["$0-$10", "$11-$20"], "How much did you spend?"), [])

    def test_continuous_measure_with_integer_adjacent_ranges(self):
        stem = "How many hours did you sleep last night?"
        found = one(stem, ["Less than 5 hours", "5-6 hours", "7-8 hours", "More than 8 hours"])
        self.assertEqual([(f["rule"], f["kind"], f["severity"]) for f in found], [("SB010", "continuous_gap", "medium")])
        self.assertEqual(one(stem, ["Less than 5 hours", "5 to under 7 hours", "7 to under 9 hours", "9 hours or more"]), [])

    def test_ranges_are_checked_when_one_option_is_in_words(self):
        found = one("How many times did you visit in the past 30 days?", ["0", "1-5", "5-10", "More than 10", "It varies"])
        self.assertEqual([(f["rule"], f["kind"]) for f in found], [("SB010", "overlap")])

    def test_negative_bounds_are_parsed(self):
        found = one("What was the temperature?", ["-10 to -1", "0 to 10", "20 or more"])
        self.assertEqual([(f["rule"], f["kind"], f["match"]) for f in found], [("SB010", "gap", "0 to 10 / 20 or more")])

    def test_introduction_counts_toward_length(self):
        intro = " ".join("This is sentence %d." % i for i in range(30))
        got = cli_json("-", stdin=intro + "\n1. Did you attend?\n- Yes\n- No\n")
        self.assertEqual((got["length"]["points"], got["length"]["seconds"]), (11.0, 82.5))

    def test_route_skip_leaves_questions_out_of_the_length(self):
        text = "1. Did you attend?\n- Yes\n- No\n2. Why not?\n3. What did you like?\n"
        self.assertEqual(cli_json("-", stdin=text)["length"]["points"], 7.0)
        got = cli_json("-", "--route-skip", "Q2", stdin=text)
        self.assertEqual((got["length"]["points"], got["length"]["route_skipped"]), (4.0, ["2"]))
        self.assertEqual(got["length"]["minutes_rounded"], 0.5)

    def test_json_required_must_be_a_real_boolean(self):
        payload = '[{"text": "What is your income?", "required": "false", "options": ["Under 10", "10 or more"]}]'
        self.assertNotIn("SB016", rules(cli_json("-", stdin=payload)["findings"]))
        result = run_cli("-", "--json", stdin='[{"text": "Q?", "required": "maybe"}]')
        self.assertEqual(result.returncode, 2)
        self.assertIn('"required"', result.stderr)

    def test_json_type_that_is_not_text_is_an_input_error(self):
        result = run_cli("-", "--json", stdin='[{"text": "Q?", "type": []}]')
        self.assertEqual(result.returncode, 2)
        self.assertIn('"type" must be text', result.stderr)

    def test_keep_matches_an_exact_q_id(self):
        payload = '[{"id": "Q7", "text": "How satisfied are you with the app?", "options": ["Yes", "No"]}]'
        got = cli_json("-", "--keep", "Q7", stdin=payload)
        self.assertTrue(got["findings"])
        self.assertEqual({f["status"] for f in got["findings"]}, {"keep as is"})

    def test_short_non_latin_and_german_questions_are_unchecked(self):
        self.assertEqual(len(cli_json("-", stdin="1. ご意見は？\n")["unchecked"]), 1)
        got = cli_json("-", stdin="1. Was ist Ihr Alter in Jahren?\n- 18-24\n- 25 oder mehr\n")
        self.assertEqual(len(got["unchecked"]), 1)
        self.assertFalse(sbc.is_english("Wie zufrieden sind Sie mit der App insgesamt und was fehlt?"))
        self.assertTrue(sbc.is_english("The pricing is not clear."))

    def test_language_flag_overrides_detection(self):
        text = "1. Do you always read the notes?\n- Yes\n- No\n"
        self.assertEqual(len(cli_json("-", "--language", "other", stdin=text)["unchecked"]), 1)
        self.assertIn("SB003", rules(cli_json("-", "--language", "en", stdin="1. Always lesen?\n- Ja\n- Nein\n")["findings"]))

    def test_tied_scale_directions_are_not_called_a_majority(self):
        text = ("1. How satisfied or dissatisfied are you?\n- Very satisfied\n- Neither\n- Very dissatisfied\n"
                "2. How easy or difficult was it?\n- Very difficult\n- Neither\n- Very easy\n")
        found = [f for f in lint_text(text)[0] if f["rule"] == "SB012"]
        self.assertEqual(len(found), 1)
        self.assertNotIn("most scales", found[0]["why"])
        self.assertIn("split evenly", found[0]["why"])

    def test_duplicate_option_is_flagged(self):
        found = one("Did it work?", ["Yes", "Yes"])
        self.assertEqual([(f["rule"], f["severity"], f["match"]) for f in found], [("SB028", "high", "Yes")])

    def test_lettered_options_without_bullets_are_options(self):
        got = cli_json("-", stdin="1. What is your age?\n   a) 18-25\n   b) 25-34\n   c) 35 or older\n")
        self.assertEqual(kinds(got), [("1", "SB010", "overlap")])
        self.assertIn("lettered lines", got["warnings"][0])

    def test_numbered_options_under_a_question_are_options(self):
        got = cli_json("-", stdin="1. How satisfied or dissatisfied are you with the app?\n"
                                  "   1) Very satisfied\n   2) Somewhat satisfied\n   3) Very dissatisfied\n")
        self.assertEqual(got["questions"], 1)
        self.assertIn(("1", "SB009", "balance"), kinds(got))

    def test_unmarked_option_lines_are_read_as_options(self):
        got = cli_json("-", stdin="1. How satisfied or dissatisfied are you with the app?\n"
                                  "Very satisfied\nSatisfied\nSomewhat satisfied\nDissatisfied\n")
        self.assertIn(("1", "SB009", "balance"), kinds(got))
        self.assertTrue(any("unmarked lines" in w for w in got["warnings"]))

    def test_respondent_view_from_survey_from_decision(self):
        text = ("We are planning the timetable. It takes about 2 minutes. Answers are combined.\n\n"
                "1. In the last 4 weeks, how many times did you visit the studio? Enter 0 if none.\n"
                "   [number]\n   (If 0: that is all we need. Thank you.)\n"
                "2. In the last 3 months, how many times did you want to pause a delivery? Enter 0 if never.\n"
                "   [number, 0 to 3]\n   (If 0, go to question 4.)\n"
                "3. Where was your most recent workout?\n   - At home\n   - Outdoors\n   - At a gym\n   - Somewhere else\n"
                "4. What was the main reason? (optional)\n   [text]\n\nThank you. Your answers help us plan.\n")
        got = cli_json("-", stdin=text)
        self.assertEqual(got["findings"], [])
        self.assertEqual(got["length"]["points_by_type"], {"intro": 1.0, "number": 4.0, "open": 3.0, "single": 1.0})
        self.assertTrue(any("skip logic" in w for w in got["warnings"]))

    def test_qsf_convert_markdown_is_read_with_tags_types_and_rows(self):
        text = ("# Pulse\n\n## Main\n\n### welcome [info]\nWelcome. It takes 2 minutes.\n\n"
                "### used [single] required\nDo you always use it?\n\n- Yes {code:1}\n- No {code:0}\n\n"
                "> skip: if \"No\" -> end of survey\n\n"
                "### grid [matrix]\nHow much do you agree or disagree with each statement?\n\nRows:\n- It is fast\n"
                "- It is stable\n\nColumns:\n- Disagree\n- Neither agree nor disagree\n- Agree\n\n"
                "### nps [nps]\nHow likely are you to recommend us to a friend or colleague?\n")
        got = cli_json("-", stdin=text)
        self.assertEqual((got["questions"], got["has_intro"]), (3, True))
        self.assertEqual(sorted(kinds(got)), [("grid", "SB014", "grid"), ("used", "SB003", "absolute")])
        self.assertTrue(any("qsf-convert" in w for w in got["warnings"]))
        self.assertEqual(got["length"]["points_by_type"], {"grid": 2.0, "intro": 1.0, "single": 2.0})

    def test_hypothetical_advice_does_not_call_intent_an_upper_bound(self):
        found = one("Would you pay $20 per month for a team plan?", ["Yes", "No"])
        self.assertNotIn("upper bound", " ".join(f["why"] for f in found))


if __name__ == "__main__":
    unittest.main()
