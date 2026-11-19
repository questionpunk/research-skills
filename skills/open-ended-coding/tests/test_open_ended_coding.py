"""Tests for scripts/open_ended_coding.py. Run from the skill folder: python3 -m unittest discover -s tests

Every expected number below is worked out by hand or taken from a published example;
fixtures/README.md shows the arithmetic and the citations.
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
SCRIPT = SKILL / "scripts" / "open_ended_coding.py"

spec = importlib.util.spec_from_file_location("open_ended_coding", SCRIPT)
oec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oec)


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def run_json(*args):
    done = run(*args, "--json")
    if done.returncode not in (0, 1):
        raise AssertionError(f"exit {done.returncode}: {done.stderr}")
    return json.loads(done.stdout)


def labels_from_table(both, a_only, b_only, neither):
    a = [1] * (both + a_only) + [0] * (b_only + neither)
    b = [1] * both + [0] * a_only + [1] * b_only + [0] * neither
    return a, b


class KappaTest(unittest.TestCase):
    def test_grant_proposals_example(self):
        # Wikipedia, "Cohen's kappa", simple example: p_o 0.70, p_e 0.50, kappa 0.40
        p_o, p_e, kappa = oec.cohen_kappa(*labels_from_table(20, 5, 10, 15))
        self.assertAlmostEqual(float(p_o), 0.70)
        self.assertAlmostEqual(float(p_e), 0.50)
        self.assertAlmostEqual(float(kappa), 0.40)
        out = run_json("agreement", FIXTURES / "kappa_grants_a.csv", FIXTURES / "kappa_grants_b.csv")
        self.assertEqual(out["overall"]["units"], 50)
        self.assertEqual(out["single_coded"]["kappa"], 0.4)
        self.assertEqual(out["single_coded"]["percent_agreement"], 70.0)
        self.assertEqual(out["single_coded"]["landis_koch"], "fair")
        self.assertEqual(out["single_coded"]["mchugh"], "weak")
        self.assertEqual(out["single_coded"]["alpha"], 0.4)  # 1 - 99*15/(55*45), by hand
        self.assertIsNone(out["overall"]["pooled_kappa"])  # not pooled when codes mirror each other

    def test_same_agreement_different_kappa(self):
        # Wikipedia, "Cohen's kappa": both tables agree on 60%, kappa 0.1304 and 0.2593
        _, p_e1, k1 = oec.cohen_kappa(*labels_from_table(45, 15, 25, 15))
        _, p_e2, k2 = oec.cohen_kappa(*labels_from_table(25, 35, 5, 35))
        self.assertAlmostEqual(float(p_e1), 0.54)
        self.assertAlmostEqual(float(p_e2), 0.46)
        self.assertAlmostEqual(float(k1), 0.1304, places=4)
        self.assertAlmostEqual(float(k2), 0.2593, places=4)

    def test_undefined_when_expected_agreement_is_one(self):
        p_o, p_e, kappa = oec.cohen_kappa([0, 0, 0], [0, 0, 0])
        self.assertEqual((p_o, p_e), (1, 1))
        self.assertIsNone(kappa)
        self.assertIsNone(oec.krippendorff_alpha_nominal([[0, 0], [0, 0], [0, 0]]))

    def test_constant_but_opposite_coders_give_zero(self):
        _, p_e, kappa = oec.cohen_kappa([1, 1, 1], [0, 0, 0])
        self.assertEqual(p_e, 0)
        self.assertEqual(kappa, 0)

    def test_band_edges(self):
        self.assertEqual(oec.landis_koch(-0.01), "poor")
        self.assertEqual(oec.landis_koch(0.20), "slight")
        self.assertEqual(oec.landis_koch(0.41), "moderate")
        self.assertEqual(oec.landis_koch(0.80), "substantial")
        self.assertEqual(oec.landis_koch(0.81), "almost perfect")
        self.assertEqual(oec.mchugh(0.59), "weak")
        self.assertEqual(oec.mchugh(0.60), "moderate")
        self.assertEqual(oec.mchugh(0.91), "almost perfect")
        self.assertEqual(oec.krippendorff_band(0.8), "meets 0.800")
        self.assertEqual(oec.krippendorff_band(0.667), "tentative only (0.667 to 0.800)")
        self.assertEqual(oec.krippendorff_band(0.666), "below 0.667")
        self.assertIsNone(oec.landis_koch(None))


class KrippendorffTest(unittest.TestCase):
    """Krippendorff (2011), Computing Krippendorff's Alpha-Reliability, examples A, B and C."""

    def test_example_a_binary(self):
        out = run_json("agreement", FIXTURES / "krippendorff_a_meg.csv", FIXTURES / "krippendorff_a_owen.csv")
        self.assertAlmostEqual(out["single_coded"]["alpha"], 0.095, places=3)  # published
        self.assertAlmostEqual(out["single_coded"]["kappa"], 0.0909, places=4)  # by hand
        one = next(c for c in out["per_code"] if c["code"] == "ONE")
        self.assertEqual((one["both"], one["a_only"], one["b_only"], one["neither"]), (1, 1, 3, 5))
        self.assertAlmostEqual(one["alpha"], 0.095, places=3)
        self.assertEqual(one["expected_agreement"], 0.56)

    def test_example_b_nominal(self):
        out = run_json("agreement", FIXTURES / "krippendorff_b_ben.csv", FIXTURES / "krippendorff_b_gerry.csv")
        self.assertAlmostEqual(out["single_coded"]["alpha"], 0.692, places=3)  # published
        self.assertAlmostEqual(out["single_coded"]["kappa"], 0.6842, places=4)  # by hand
        self.assertEqual(out["single_coded"]["percent_agreement"], 75.0)
        self.assertEqual(out["single_coded"]["krippendorff_band"], "tentative only (0.667 to 0.800)")

    def test_example_c_four_observers_missing_data(self):
        a = [1, 2, 3, 3, 2, 1, 4, 1, 2, None, None, None]
        b = [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, None, 3]
        c = [None, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, None]
        d = [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, None]
        units = [[v for v in unit if v is not None] for unit in zip(a, b, c, d)]
        self.assertAlmostEqual(float(oec.krippendorff_alpha_nominal(units)), 0.743, places=3)


class AgreementTest(unittest.TestCase):
    def setUp(self):
        self.out = run_json(
            "agreement", FIXTURES / "agree_a.csv", FIXTURES / "agree_b.csv", "--codebook", FIXTURES / "codebook.csv"
        )
        self.codes = {c["code"]: c for c in self.out["per_code"]}

    def test_per_code_by_hand(self):
        expected = {  # code: (both, a_only, b_only, neither, % agreement, kappa, alpha, positive agreement)
            "PRICE": (4, 0, 0, 6, 100.0, 1.0, 1.0, 1.0),
            "SUPPORT": (3, 1, 1, 5, 80.0, 0.5833, 0.6042, 0.75),
            "SPEED": (2, 1, 1, 6, 80.0, 0.5238, 0.5476, 0.6667),
            "OTHER": (0, 1, 1, 8, 80.0, -0.1111, -0.0556, 0.0),
        }
        for code, (both, a_only, b_only, neither, agree, kappa, alpha, positive) in expected.items():
            got = self.codes[code]
            self.assertEqual((got["both"], got["a_only"], got["b_only"], got["neither"]), (both, a_only, b_only, neither), code)
            self.assertEqual(got["percent_agreement"], agree, code)
            self.assertAlmostEqual(got["kappa"], kappa, places=4, msg=code)
            self.assertAlmostEqual(got["alpha"], alpha, places=4, msg=code)
            self.assertAlmostEqual(got["positive_agreement"], positive, places=4, msg=code)

    def test_high_agreement_negative_kappa_is_reported(self):
        self.assertEqual(self.codes["OTHER"]["percent_agreement"], 80.0)
        self.assertLess(self.codes["OTHER"]["kappa"], 0)
        self.assertEqual(self.codes["OTHER"]["landis_koch"], "poor")

    def test_code_neither_coder_used(self):
        unused = self.codes["UX"]
        self.assertEqual(unused["percent_agreement"], 100.0)
        self.assertEqual(unused["expected_agreement"], 1.0)
        self.assertIsNone(unused["kappa"])
        self.assertIsNone(unused["alpha"])
        self.assertIsNone(unused["positive_agreement"])
        self.assertIn("neither coder used", unused["kappa_undefined_reason"])
        self.assertIn("UX", self.out["overall"]["codes_with_undefined_kappa"])
        text = run("agreement", FIXTURES / "agree_a.csv", FIXTURES / "agree_b.csv", "--codebook", FIXTURES / "codebook.csv")
        self.assertEqual(text.returncode, 0)
        self.assertIn("undefined", text.stdout)

    def test_overall_by_hand(self):
        overall = self.out["overall"]
        self.assertEqual(overall["units"], 10)
        self.assertEqual(overall["exact_code_set_match"], 6)
        self.assertEqual(overall["exact_code_set_match_pct"], 60.0)
        self.assertAlmostEqual(overall["mean_kappa"], 0.4990, places=4)
        self.assertAlmostEqual(overall["min_kappa"], -0.1111, places=4)
        self.assertEqual(overall["min_kappa_code"], "OTHER")
        self.assertEqual(overall["pooled_decisions"], 40)
        self.assertEqual(overall["pooled_percent_agreement"], 85.0)
        self.assertAlmostEqual(overall["pooled_kappa"], 0.6429, places=4)
        self.assertIsNone(self.out["single_coded"])

    def test_different_rows_is_an_error(self):
        done = run("agreement", FIXTURES / "agree_a.csv", FIXTURES / "kappa_grants_b.csv")
        self.assertEqual(done.returncode, 2)
        self.assertIn("do not hold the same rows", done.stderr)

    def test_full_coded_file_against_a_sample(self):
        # coded.csv has a blank, uncoded row (8) that is not in the sample: it must not stop the comparison
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "second.csv"
            path.write_text("id,codes\n1,PRICE\n2,SUPPORT\n4,SPEED\n9,UX\n14,UX\n", encoding="utf-8")
            self.assertEqual(run("agreement", FIXTURES / "coded.csv", path).returncode, 2)
            out = run_json("agreement", FIXTURES / "coded.csv", path, "--allow-unmatched")
        self.assertEqual(out["overall"]["units"], 5)
        self.assertEqual(out["overall"]["exact_code_set_match"], 3)  # rows 1, 2, 9
        self.assertTrue(any("15 id(s) were not coded by every coder" in note for note in out["notes"]))

    def test_uncoded_row_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "b.csv"
            path.write_text("id,codes\n" + "\n".join(f"{i}," for i in range(1, 11)) + "\n", encoding="utf-8")
            done = run("agreement", FIXTURES / "agree_a.csv", path)
        self.assertEqual(done.returncode, 2)
        self.assertIn("no code", done.stderr)

    def test_rows_blank_for_both_coders_are_left_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name in ("agree_a.csv", "agree_b.csv"):
                path = pathlib.Path(tmp) / name
                path.write_text((FIXTURES / name).read_text(encoding="utf-8") + "11,NO_ANSWER\n12,NO_ANSWER\n", encoding="utf-8")
                paths.append(path)
            out = run_json("agreement", *paths)
        self.assertEqual(out["overall"]["units"], 10)
        self.assertAlmostEqual(next(c for c in out["per_code"] if c["code"] == "SUPPORT")["kappa"], 0.5833, places=4)
        self.assertTrue(any("left out" in note for note in out["notes"]))


class CountsTest(unittest.TestCase):
    def counts(self, *extra):
        return run_json("counts", FIXTURES / "coded.csv", "--text-col", "answer", "--codebook", FIXTURES / "codebook.csv", *extra)

    def test_bases_and_shares_by_hand(self):
        out = self.counts("--min-base", 10)
        self.assertEqual(
            (out["all_respondents"], out["answered"], out["no_answer"], out["uncodable"], out["codable"]),
            (20, 17, 3, 2, 15),
        )
        self.assertEqual(out["pct_answered_of_all"], 85.0)
        self.assertEqual(out["pct_no_answer_of_all"], 15.0)
        got = {c["code"]: (c["n"], c["pct_of_all"], c["pct_of_answered"]) for c in out["codes"]}
        self.assertEqual(
            got,
            {
                "PRICE": (7, 35.0, 41.2),
                "SUPPORT": (4, 20.0, 23.5),
                "SPEED": (4, 20.0, 23.5),
                "UX": (3, 15.0, 17.6),
                "OTHER": (1, 5.0, 5.9),
                "UNCODABLE": (2, 10.0, 11.8),
            },
        )
        self.assertEqual([c["code"] for c in out["codes"]], ["PRICE", "SUPPORT", "SPEED", "UX", "OTHER", "UNCODABLE"])
        self.assertEqual(out["code_assignments"], 19)
        self.assertEqual(out["mean_codes_per_codable_answer"], 1.27)
        self.assertTrue(any("more than 100%" in note for note in out["notes"]))
        substantive = sum(c["pct_of_answered"] for c in out["codes"] if c["code"] != "UNCODABLE")
        self.assertGreater(substantive, 100)

    def test_percentages_withheld_on_small_base_by_default(self):
        out = self.counts()
        self.assertEqual(out["min_base"], 30)
        self.assertTrue(out["small_base_answered"])
        self.assertTrue(all(c["pct_of_answered"] is None and c["pct_of_all"] is None for c in out["codes"]))
        self.assertEqual(out["codes"][0]["n"], 7)
        self.assertTrue(any("withheld" in note for note in out["notes"]))
        text = run("counts", FIXTURES / "coded.csv", "--text-col", "answer")
        self.assertIn("--", text.stdout)
        self.assertNotIn("41.2%", text.stdout)

    def test_wide_format_gives_the_same_counts(self):
        wide = run_json("counts", FIXTURES / "coded_wide.csv", "--code-prefix", "code_", "--min-base", 10)
        long = self.counts("--min-base", 10)
        for key in ("all_respondents", "answered", "no_answer", "uncodable", "codable", "codes"):
            self.assertEqual(wide[key], long[key], key)

    def test_segment_cut_by_hand_and_small_base_flag(self):
        out = self.counts("--segment-col", "plan", "--min-base", 9)
        free, paid = out["segments"]["free"], out["segments"]["paid"]
        self.assertEqual((free["all_respondents"], free["answered"], free["no_answer"], free["uncodable"]), (10, 8, 2, 2))
        self.assertEqual((paid["all_respondents"], paid["answered"], paid["no_answer"], paid["uncodable"]), (10, 9, 1, 0))
        paid_codes = {c["code"]: (c["n"], c["pct_of_answered"]) for c in paid["codes"]}
        self.assertEqual(paid_codes["PRICE"], (3, 33.3))
        self.assertEqual(paid_codes["SUPPORT"], (4, 44.4))
        self.assertEqual(paid_codes["SPEED"], (2, 22.2))
        self.assertEqual(paid_codes["UX"], (2, 22.2))
        self.assertEqual(paid_codes["OTHER"], (1, 11.1))
        free_codes = {c["code"]: (c["n"], c["pct_of_answered"]) for c in free["codes"]}
        self.assertTrue(free["small_base_answered"])  # 8 answered, under the minimum of 9
        self.assertFalse(paid["small_base_answered"])
        self.assertEqual(free_codes["PRICE"], (4, None))
        self.assertEqual(free_codes["SUPPORT"], (0, None))
        self.assertTrue(any("free" in note and "do not compare" in note for note in out["notes"]))

    def test_unknown_code_and_uncoded_row_stop_the_count(self):
        done = run("counts", FIXTURES / "coded_bad.csv", "--text-col", "answer", "--codebook", FIXTURES / "codebook.csv")
        self.assertEqual(done.returncode, 2)
        self.assertIn("unknown code 'PRICING'", done.stderr)
        self.assertIn("row 2: no code", done.stderr)
        self.assertEqual(done.stdout, "")

    def test_blank_answer_without_text_column_is_uncoded(self):
        done = run("counts", FIXTURES / "coded.csv")
        self.assertEqual(done.returncode, 2)
        self.assertIn("row 8: no code", done.stderr)

    def test_bad_input(self):
        self.assertEqual(run("counts", FIXTURES / "missing.csv").returncode, 2)
        done = run("counts", FIXTURES / "coded.csv", "--codes-col", "themes")
        self.assertEqual(done.returncode, 2)
        self.assertIn("Columns found", done.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "wide.csv"
            path.write_text("id,code_A\n1,yes\n", encoding="utf-8")
            done = run("counts", path, "--code-prefix", "code_")
            self.assertEqual(done.returncode, 2)
            self.assertIn("expected 0 or 1", done.stderr)
            path.write_text("id,codes\n1,A\n1,B\n", encoding="utf-8")
            done = run("counts", path)
            self.assertEqual(done.returncode, 2)
            self.assertIn("more than once", done.stderr)
            path.write_text("", encoding="utf-8")
            self.assertEqual(run("counts", path).returncode, 2)


class ValidateTest(unittest.TestCase):
    def test_clean_file_passes_with_quotes(self):
        out = run_json(
            "validate", FIXTURES / "coded.csv", "--codebook", FIXTURES / "codebook.csv", "--text-col", "answer",
            "--quotes", FIXTURES / "quotes_ok.csv",
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["warnings"], [])
        self.assertEqual(out["blank_rows_set_to_NO_ANSWER"], 1)
        self.assertEqual(out["quotes_checked"], 3)

    def test_bad_file_lists_every_problem(self):
        done = run("validate", FIXTURES / "coded_bad.csv", "--codebook", FIXTURES / "codebook.csv", "--text-col", "answer", "--json")
        self.assertEqual(done.returncode, 1)
        out = json.loads(done.stdout)
        errors = "\n".join(out["errors"])
        self.assertEqual(len(out["errors"]), 6)
        self.assertIn("row 1: unknown code 'PRICING'", errors)
        self.assertIn("row 2: no code", errors)
        self.assertIn("row 3: the answer is blank but it is coded PRICE", errors)
        self.assertIn("row 4: coded NO_ANSWER but the answer is not blank", errors)
        self.assertIn("row 5: UNCODABLE cannot be combined", errors)
        self.assertIn("row 7: unknown code 'price' (did you mean 'PRICE'?)", errors)
        warnings = "\n".join(out["warnings"])
        self.assertIn("code 'SUPPORT' is in the codebook but no row uses it", warnings)
        self.assertIn("row 6: the answer is 'none'", warnings)

    def test_quotes_must_be_verbatim_and_carry_the_code(self):
        done = run(
            "validate", FIXTURES / "coded.csv", "--codebook", FIXTURES / "codebook.csv", "--text-col", "answer",
            "--quotes", FIXTURES / "quotes_bad.csv", "--json",
        )
        self.assertEqual(done.returncode, 1)
        errors = "\n".join(json.loads(done.stdout)["errors"])
        self.assertIn("quotes line 2: quote is not word for word", errors)
        self.assertIn("quotes line 3: row 12 is not coded 'SUPPORT'", errors)
        self.assertIn("quotes line 4: row id '99' is not in the coded file", errors)

    def test_codebook_format_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "codebook.csv"
            path.write_text("code,label,definition\nPRICE,Price,About price\n", encoding="utf-8")
            done = run("validate", FIXTURES / "coded.csv", "--codebook", path)
            self.assertEqual(done.returncode, 2)
            self.assertIn("missing: include, exclude, example_quote", done.stderr)
            path.write_text(
                "code,label,definition,include,exclude,example_quote\nPRICE,Price,About price,,,\nPRICE,Again,x,y,z,q\n",
                encoding="utf-8",
            )
            done = run("validate", FIXTURES / "agree_a.csv", "--codebook", path, "--json")
            self.assertEqual(done.returncode, 1)
            errors = "\n".join(json.loads(done.stdout)["errors"])
            self.assertIn("code 'PRICE' has an empty 'include'", errors)
            self.assertIn("code 'PRICE' is defined twice", errors)
        self.assertEqual(run("validate", FIXTURES / "coded.csv").returncode, 2)


class SampleTest(unittest.TestCase):
    def sample(self, *extra):
        return run_json("sample", FIXTURES / "coded.csv", "--text-col", "answer", *extra)

    def test_seeded_sample_is_reproducible(self):
        first, again, other = self.sample("--n", 8, "--seed", 42), self.sample("--n", 8, "--seed", 42), self.sample("--n", 8, "--seed", 43)
        self.assertEqual(first["ids"], again["ids"])
        self.assertNotEqual(first["ids"], other["ids"])
        self.assertEqual(len(set(first["ids"])), 8)
        self.assertEqual((first["rows"], first["blank_answers"], first["eligible"], first["seed"]), (20, 3, 17, 42))

    def test_blank_answers_are_left_out_unless_asked(self):
        everything = self.sample("--n", 17)
        self.assertEqual(set(everything["ids"]), {str(i) for i in range(1, 21)} - {"3", "8", "13"})
        self.assertEqual(len(self.sample("--n", 20, "--include-blank")["ids"]), 20)

    def test_fraction_and_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            first_path = pathlib.Path(tmp) / "first.csv"
            first = self.sample("--n", 10, "--seed", 5, "--out", first_path)
            with open(first_path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([r["id"] for r in rows], first["ids"])
            self.assertEqual(list(rows[0]), ["id", "answer"])  # codes are not passed to a second coder
            second = self.sample("--fraction", 0.5, "--seed", 5, "--exclude", first_path)
        self.assertEqual(second["eligible"], 7)
        self.assertEqual(second["sampled"], 4)  # round(7 * 0.5) = 4 (Python rounds 3.5 to even)
        self.assertFalse(set(second["ids"]) & set(first["ids"]))

    def test_asking_for_too_many_is_an_error(self):
        done = run("sample", FIXTURES / "coded.csv", "--text-col", "answer", "--n", 18)
        self.assertEqual(done.returncode, 2)
        self.assertIn("only 17 are eligible", done.stderr)
        self.assertEqual(run("sample", FIXTURES / "coded.csv", "--text-col", "answer").returncode, 2)
        self.assertEqual(run("sample", FIXTURES / "coded.csv", "--text-col", "nope", "--n", 2).returncode, 2)
        self.assertEqual(run("sample", FIXTURES / "coded.csv", "--text-col", "answer", "--fraction", 1.5).returncode, 2)


class ParadoxAndGoldTest(unittest.TestCase):
    """fixtures/README.md, section 7: a person's coding as the reference, an LLM run compared with it."""

    def setUp(self):
        self.out = run_json(
            "agreement", FIXTURES / "gold_llm.csv", "--gold", FIXTURES / "gold_human.csv", "--bootstrap", 0,
            "--coder-info", "anna,human", "--coder-info", "run1,llm,model-x", "--codebook-version", "v2",
        )
        self.codes = {c["code"]: c for c in self.out["per_code"]}

    def test_precision_recall_f1_by_hand(self):
        expected = {  # code: (precision, recall, F1, kappa)
            "PRICE": (0.8333, 1.0, 0.9091, 0.8333),
            "SUPPORT": (1.0, 0.75, 0.8571, 0.8),
            "SPEED": (0.3333, 0.3333, 0.3333, 0.1111),
            "OTHER": (0.0, 0.0, 0.0, -0.0909),
            "UX": (1.0, 1.0, 1.0, 1.0),
        }
        for code, (precision, recall, f1, kappa) in expected.items():
            got = self.codes[code]
            self.assertAlmostEqual(got["precision"], precision, places=4, msg=code)
            self.assertAlmostEqual(got["recall"], recall, places=4, msg=code)
            self.assertAlmostEqual(got["f1"], f1, places=4, msg=code)
            self.assertAlmostEqual(got["kappa"], kappa, places=4, msg=code)

    def test_negative_agreement_and_pabak_by_hand(self):
        self.assertAlmostEqual(self.codes["PRICE"]["negative_agreement"], 0.9231, places=4)  # 12/13
        self.assertAlmostEqual(self.codes["PRICE"]["positive_agreement"], 0.9091, places=4)  # 10/11
        self.assertAlmostEqual(self.codes["PRICE"]["pabak"], 0.8333, places=4)  # 2 * 11/12 - 1
        self.assertAlmostEqual(self.codes["SPEED"]["pabak"], 0.3333, places=4)  # 2 * 8/12 - 1
        self.assertAlmostEqual(self.codes["OTHER"]["negative_agreement"], 0.9091, places=4)  # 20/22
        self.assertAlmostEqual(self.codes["OTHER"]["pabak"], 0.6667, places=4)  # 2 * 10/12 - 1

    def test_high_agreement_low_kappa_flag(self):
        self.assertTrue(self.codes["OTHER"]["high_agreement_low_kappa"])  # 83.3% agreement, kappa -0.09
        self.assertFalse(self.codes["SPEED"]["high_agreement_low_kappa"])  # 66.7% agreement: plainly low
        self.assertFalse(self.codes["PRICE"]["high_agreement_low_kappa"])

    def test_provenance_header(self):
        self.assertEqual(self.out["gold"], "A")
        self.assertEqual(self.out["codebook_version"], "v2")
        self.assertEqual([(c["key"], c["id"], c["kind"], c["model"]) for c in self.out["coders"]],
                         [("A", "anna", "human", None), ("B", "run1", "llm", "model-x")])
        text = run(
            "agreement", FIXTURES / "gold_llm.csv", "--gold", FIXTURES / "gold_human.csv", "--bootstrap", 0,
            "--coder-info", "anna,human", "--coder-info", "run1,llm,model-x", "--codebook-version", "v2",
        ).stdout
        self.assertIn("A = anna (human); B = run1 (LLM, model-x). Reference (gold): A", text)
        self.assertIn("Codebook version: v2", text)
        self.assertIn("McHugh", text)
        self.assertIn("precision", text)

    def test_two_llm_runs_are_not_double_coding(self):
        out = run_json(
            "agreement", FIXTURES / "agree_a.csv", FIXTURES / "agree_b.csv", "--bootstrap", 0,
            "--coder-info", "run1,llm,model-x", "--coder-info", "run2,llm,model-x",
        )
        self.assertTrue(any("not double coding" in note for note in out["notes"]))
        self.assertNotIn("precision", out["per_code"][0])

    def test_bad_coder_info(self):
        base = ("agreement", FIXTURES / "agree_a.csv", FIXTURES / "agree_b.csv", "--bootstrap", 0)
        self.assertEqual(run(*base, "--coder-info", "anna,human").returncode, 2)
        self.assertEqual(run(*base, "--coder-info", "anna,robot", "--coder-info", "b,human").returncode, 2)
        self.assertEqual(run(*base, "--coder-info", "a,llm", "--coder-info", "b,human").returncode, 2)
        self.assertEqual(run("agreement", FIXTURES / "agree_a.csv").returncode, 2)


class BootstrapTest(unittest.TestCase):
    def agreement(self, *extra):
        return run_json("agreement", FIXTURES / "agree_a.csv", FIXTURES / "agree_b.csv", "--codebook", FIXTURES / "codebook.csv", *extra)

    def test_same_seed_same_intervals_and_point_inside(self):
        first, again, other = self.agreement("--seed", 7), self.agreement("--seed", 7), self.agreement("--seed", 8)
        self.assertEqual(first, again)
        self.assertNotEqual(first["overall"]["mean_kappa_ci95"], other["overall"]["mean_kappa_ci95"])
        self.assertEqual(first["bootstrap"]["replicates"], 2000)
        for line in first["per_code"]:
            for stat in ("kappa", "alpha"):
                if line[stat] is None:
                    self.assertIsNone(line[stat + "_ci95"])
                else:
                    low, high = line[stat + "_ci95"]
                    self.assertLessEqual(low, line[stat], line["code"])
                    self.assertGreaterEqual(high, line[stat], line["code"])
        overall = first["overall"]
        for stat in ("mean_kappa", "pooled_kappa", "exact_code_set_match_pct"):
            low, high = overall[stat + "_ci95"]
            self.assertLessEqual(low, overall[stat])
            self.assertGreaterEqual(high, overall[stat])

    def test_band_crossing_is_flagged(self):
        codes = {c["code"]: c for c in self.agreement()["per_code"]}
        self.assertTrue(codes["SUPPORT"]["ci_crosses_band"])  # 10 responses: the interval spans several bands
        self.assertFalse(codes["PRICE"]["ci_crosses_band"])  # perfect agreement in every resample
        self.assertEqual(codes["PRICE"]["kappa_ci95"], [1.0, 1.0])
        text = run("agreement", FIXTURES / "agree_a.csv", FIXTURES / "agree_b.csv").stdout
        self.assertIn("* interval crosses a band", text)
        self.assertIn("95% percentile bootstrap over responses, 2000 replicates, seed 1", text)

    def test_bootstrap_off_and_bad_value(self):
        out = self.agreement("--bootstrap", 0)
        self.assertNotIn("kappa_ci95", out["per_code"][0])
        self.assertEqual(run("agreement", FIXTURES / "agree_a.csv", FIXTURES / "agree_b.csv", "--bootstrap", 5).returncode, 2)

    def test_single_coded_interval_contains_published_values(self):
        out = run_json("agreement", FIXTURES / "krippendorff_b_ben.csv", FIXTURES / "krippendorff_b_gerry.csv")
        low, high = out["single_coded"]["alpha_ci95"]
        self.assertLessEqual(low, 0.692)
        self.assertGreaterEqual(high, 0.692)
        self.assertTrue(out["single_coded"]["ci_crosses_band"])

    def test_percentile_and_interval_helpers(self):
        self.assertEqual(oec.percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50), 3.0)
        self.assertAlmostEqual(oec.percentile([1.0, 2.0, 3.0, 4.0, 5.0], 2.5), 1.1)  # rank 0.1 between 1 and 2
        self.assertIsNone(oec.bootstrap_interval([None, None, None, 0.5], 4))  # fewer than half defined
        self.assertEqual(oec.bootstrap_interval([0.2, 0.4, None, 0.6], 4), [0.21, 0.59])


class MultiCoderTest(unittest.TestCase):
    def test_krippendorff_example_c_from_four_files(self):
        files = [FIXTURES / f"krippendorff_c_{k}.csv" for k in "abcd"]
        self.assertEqual(run("agreement", *files).returncode, 2)  # rows are missing: must be asked for
        out = run_json("agreement", *files, "--allow-unmatched")
        self.assertEqual(out["overall"]["units"], 11)  # unit 12 has one value and cannot be paired
        self.assertAlmostEqual(out["single_coded"]["alpha"], 0.743, places=3)  # published
        low, high = out["single_coded"]["alpha_ci95"]
        self.assertTrue(low <= 0.743 <= high)
        pairs = {p["pair"]: p for p in out["pairwise"]}
        self.assertEqual(len(pairs), 6)
        self.assertEqual(pairs["A-B"]["units"], 9)
        self.assertAlmostEqual(pairs["A-B"]["categorical_kappa"], 0.8448, places=4)  # 49/58, by hand
        self.assertAlmostEqual(pairs["A-D"]["categorical_kappa"], 0.85, places=4)  # 51/60, by hand

    def test_three_coders_alpha_per_code_by_hand(self):
        out = run_json("agreement", FIXTURES / "agree_a.csv", FIXTURES / "agree_b.csv", FIXTURES / "agree_c.csv", "--bootstrap", 200)
        codes = {c["code"]: c for c in out["per_code"]}
        self.assertAlmostEqual(codes["PRICE"]["alpha"], 1.0, places=4)
        self.assertAlmostEqual(codes["SUPPORT"]["alpha"], 0.7315, places=4)  # 1 - 29*2/(12*18)
        self.assertAlmostEqual(codes["SPEED"]["alpha"], 0.6931, places=4)  # 1 - 29*2/(9*21)
        self.assertAlmostEqual(codes["OTHER"]["alpha"], -0.0357, places=4)  # 1 - 29*2/(2*28)
        self.assertEqual(codes["SUPPORT"]["used_by"], {"A": 4, "B": 4, "C": 4})
        self.assertAlmostEqual(codes["SUPPORT"]["min_pairwise_kappa"], 0.5833, places=4)
        self.assertEqual(codes["SUPPORT"]["min_pairwise_kappa_pair"], "A-B")
        self.assertEqual(codes["SUPPORT"]["krippendorff_band"], "tentative only (0.667 to 0.800)")
        low, high = codes["SUPPORT"]["alpha_ci95"]
        self.assertTrue(low <= codes["SUPPORT"]["alpha"] <= high)
        self.assertIsNone(out["single_coded"])
        self.assertEqual([p["pair"] for p in out["pairwise"]], ["A-B", "A-C", "B-C"])

    def test_fast_binary_alpha_equals_the_general_formula(self):
        units = [[True, False, False], [True, True, True], [False, True, True], [False, False], [True], [False, False, False]]
        mismatch = sum(sum(u) * (len(u) - sum(u)) / (len(u) - 1) for u in units if len(u) > 1)
        ones = sum(sum(u) for u in units if len(u) > 1)
        zeros = sum(len(u) - sum(u) for u in units if len(u) > 1)
        self.assertAlmostEqual(oec.alpha_binary_sums(mismatch, ones, zeros), float(oec.krippendorff_alpha_nominal(units)))
        self.assertEqual(oec.alpha_2x2(3, 1, 1, 5), oec.krippendorff_alpha_nominal([[1, 1]] * 3 + [[1, 0]] + [[0, 1]] + [[0, 0]] * 5))
        self.assertIsNone(oec.alpha_binary_sums(0.0, 0, 6))


class DisagreementsAndMergeTest(unittest.TestCase):
    def test_disagreements_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "disagreements.csv"
            out = run_json("agreement", FIXTURES / "agree_a.csv", FIXTURES / "agree_b.csv", "--codebook", FIXTURES / "codebook.csv",
                           "--bootstrap", 0, "--disagreements", path)
            with open(path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(out["disagreements"]["rows"], 4)
        self.assertEqual(list(rows[0]), ["id", "text", "codes_A", "codes_B", "in_dispute", "final_codes"])
        self.assertEqual([(r["id"], r["codes_A"], r["codes_B"], r["in_dispute"]) for r in rows], [
            ("2", "PRICE;SUPPORT", "PRICE", "SUPPORT"),
            ("5", "PRICE", "PRICE;SPEED", "SPEED"),
            ("6", "OTHER", "SUPPORT", "SUPPORT;OTHER"),
            ("9", "SPEED", "OTHER", "SPEED;OTHER"),
        ])
        self.assertTrue(all(r["final_codes"] == "" for r in rows))

    def test_disagreements_carry_the_answer_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            second, path = pathlib.Path(tmp) / "second.csv", pathlib.Path(tmp) / "d.csv"
            second.write_text("id,codes\n1,PRICE\n4,SPEED\n9,UX;SPEED\n", encoding="utf-8")
            run_json("agreement", FIXTURES / "coded.csv", second, "--allow-unmatched", "--text-col", "answer", "--bootstrap", 0, "--disagreements", path)
            with open(path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual([(r["id"], r["text"], r["in_dispute"]) for r in rows], [
            ("4", "The app is slow and the price went up", "PRICE"),
            ("9", "Hard to find the export button", "SPEED"),
        ])

    def test_merge_adjudicated_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            final = pathlib.Path(tmp) / "final.csv"
            out = run_json("merge", FIXTURES / "agree_a.csv", "--adjudicated", FIXTURES / "adjudicated.csv", "--out", final,
                           "--codebook", FIXTURES / "codebook.csv")
            with open(final, newline="", encoding="utf-8") as handle:
                rows = {r["id"]: r["codes"] for r in csv.DictReader(handle)}
            counts = run_json("counts", final, "--min-base", 5)
        self.assertEqual((out["changed"], out["confirmed"], out["pending"]), (["2", "5", "6"], ["9"], []))
        self.assertEqual((rows["2"], rows["5"], rows["6"], rows["9"], rows["1"]), ("PRICE", "PRICE;SPEED", "SUPPORT", "SPEED", "PRICE"))
        self.assertEqual({c["code"]: c["n"] for c in counts["codes"]}, {"PRICE": 4, "SUPPORT": 4, "SPEED": 4, "OTHER": 0, "UNCODABLE": 0})

    def test_merge_refuses_pending_unknown_and_missing_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            adj, final = pathlib.Path(tmp) / "adj.csv", pathlib.Path(tmp) / "final.csv"
            adj.write_text("id,final_codes\n2,PRICE\n5,\n", encoding="utf-8")
            done = run("merge", FIXTURES / "agree_a.csv", "--adjudicated", adj, "--out", final)
            self.assertEqual(done.returncode, 2)
            self.assertIn("have no final_codes", done.stderr)
            self.assertFalse(final.exists())
            out = run_json("merge", FIXTURES / "agree_a.csv", "--adjudicated", adj, "--out", final, "--allow-pending")
            self.assertEqual((out["changed"], out["pending"]), (["2"], ["5"]))
            adj.write_text("id,final_codes\n2,PRICING\n", encoding="utf-8")
            self.assertEqual(run("merge", FIXTURES / "agree_a.csv", "--adjudicated", adj, "--out", final, "--codebook", FIXTURES / "codebook.csv").returncode, 2)
            adj.write_text("id,final_codes\n77,PRICE\n", encoding="utf-8")
            self.assertEqual(run("merge", FIXTURES / "agree_a.csv", "--adjudicated", adj, "--out", final).returncode, 2)


class CountsExtrasTest(unittest.TestCase):
    def counts(self, *extra):
        return run_json("counts", FIXTURES / "coded_sentiment.csv", "--text-col", "answer", "--codebook", FIXTURES / "codebook_nets.csv", *extra)

    def test_wilson_matches_nist_worked_example(self):
        # NIST/SEMATECH e-Handbook 7.2.4.1: p = 0.13, N = 200, z = 1.645 gives a lower limit of 0.09577
        self.assertAlmostEqual(oec.wilson(26, 200, z=1.645)[0], 0.09577, places=5)
        low, high = oec.wilson(0, 20)  # closed form with no successes: 0 to z^2 / (n + z^2)
        self.assertEqual(low, 0.0)
        self.assertAlmostEqual(high, 3.8416 / 23.8416, places=4)

    def test_wilson_intervals_on_shares_by_hand(self):
        out = self.counts("--min-base", 10)
        got = {c["code"]: c["ci95_of_answered"] for c in out["codes"]}
        for code, (low, high) in {"PRICE": (21.6, 64.0), "SUPPORT": (9.6, 47.3)}.items():
            self.assertAlmostEqual(got[code][0], low, delta=0.1)
            self.assertAlmostEqual(got[code][1], high, delta=0.1)
        self.assertTrue(all(c["ci95_of_answered"] is None for c in self.counts()["codes"]))  # base under 30

    def test_nets_count_each_respondent_once(self):
        out = self.counts("--min-base", 10, "--segment-col", "plan")
        nets = {n["net"]: n for n in out["nets"]}
        self.assertEqual((nets["EXPERIENCE"]["n"], nets["EXPERIENCE"]["sum_of_code_counts"]), (10, 11))
        self.assertEqual((nets["EXPERIENCE"]["pct_of_all"], nets["EXPERIENCE"]["pct_of_answered"]), (50.0, 58.8))
        self.assertEqual(nets["EXPERIENCE"]["codes"], ["SUPPORT", "SPEED", "UX"])
        self.assertEqual((nets["COST"]["n"], nets["COST"]["pct_of_answered"]), (7, 41.2))
        self.assertEqual({n["net"]: n["n"] for n in out["segments"]["paid"]["nets"]}, {"COST": 3, "EXPERIENCE": 7})
        self.assertEqual({n["net"]: n["n"] for n in out["segments"]["free"]["nets"]}, {"COST": 4, "EXPERIENCE": 3})
        self.assertTrue(any("not the sum" in note for note in out["notes"]))

    def test_share_of_mentions_is_optional_and_sums_to_100(self):
        out = self.counts("--min-base", 10, "--mentions")
        got = {c["code"]: c["pct_of_mentions"] for c in out["codes"]}
        self.assertEqual(got, {"PRICE": 36.8, "SUPPORT": 21.1, "SPEED": 21.1, "UX": 15.8, "OTHER": 5.3, "UNCODABLE": None})
        self.assertAlmostEqual(sum(v for v in got.values() if v is not None), 100.0, delta=0.2)
        self.assertNotIn("pct_of_mentions", self.counts("--min-base", 10)["codes"][0])

    def test_codebook_health_defaults_and_overrides(self):
        health = self.counts()["health"]
        self.assertEqual(health["rare"], [{"code": "SUPPORT", "n": 4}, {"code": "SPEED", "n": 4}, {"code": "UX", "n": 3}])
        self.assertEqual((health["broad"], health["unused"], health["other_above_threshold"]), ([], [], False))
        self.assertEqual(health["top_pairs"][0], {"codes": ["PRICE", "SPEED"], "n": 2, "smaller_code": "SPEED", "smaller_code_n": 4})
        self.assertEqual([p["n"] for p in health["top_pairs"]], [2, 1, 1])
        strict = self.counts("--rare-below", 4, "--broad-above", 40, "--other-above", 5, "--top-pairs", 1)["health"]
        self.assertEqual(strict["rare"], [{"code": "UX", "n": 3}])
        self.assertEqual(strict["broad"], [{"code": "PRICE", "n": 7}])  # 7 of 17 is 41.2%
        self.assertTrue(strict["other_above_threshold"])  # 1 of 17 is 5.9%
        self.assertEqual(len(strict["top_pairs"]), 1)
        text = run("counts", FIXTURES / "coded.csv", "--text-col", "answer", "--codebook", FIXTURES / "codebook.csv").stdout
        self.assertIn("Codebook health", text)
        self.assertIn("Used fewer than 5 times: SUPPORT (4), SPEED (4), UX (3)", text)

    def test_sentiment_column_is_counted_not_computed(self):
        block = self.counts("--min-base", 10, "--sentiment-col", "sentiment")["sentiment"]
        self.assertEqual(block["base"], 15)
        self.assertEqual({v["value"]: (v["n"], v["pct"]) for v in block["values"]},
                         {"positive": (0, 0.0), "negative": (11, 73.3), "neutral": (2, 13.3), "mixed": (2, 13.3)})
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "bad.csv"
            path.write_text("id,codes,sentiment\n1,PRICE,angry\n2,SPEED,\n", encoding="utf-8")
            done = run("counts", path, "--sentiment-col", "sentiment")
        self.assertEqual(done.returncode, 2)
        self.assertIn("expected one of positive, negative, neutral, mixed", done.stderr)
        self.assertIn("row 2: 'sentiment' is empty", done.stderr)

    def test_codebook_parent_must_not_be_a_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "codebook.csv"
            path.write_text("code,label,definition,include,exclude,example_quote,parent\nA,a,d,i,e,q,B\nB,b,d,i,e,q,\n", encoding="utf-8")
            done = run("counts", FIXTURES / "saturation.csv", "--codebook", path)
        self.assertEqual(done.returncode, 2)
        self.assertIn("is also the name of a code", done.stderr)


class SaturationTest(unittest.TestCase):
    def test_log_by_hand(self):
        out = run_json("saturation", FIXTURES / "saturation.csv", "--base", 4, "--run", 2, "--step", 2)
        self.assertEqual(out["base_codes"], 4)
        self.assertEqual([(b["batch"], b["rows"], b["new_codes"], b["codes_so_far"], b["new_pct_of_base"]) for b in out["batches"]], [
            ("base", "1-4", ["A", "B", "C", "D"], 4, None),
            ("run 1", "5-6", ["E"], 5, 25.0),
            ("run 2", "7-8", [], 5, 0.0),  # OTHER is not a new code
        ])
        self.assertEqual((out["reached_at_run"], out["reached_after_rows"], out["rows_not_evaluated"]), (2, 8, 1))

    def test_rolling_runs_by_default(self):
        # Guest et al. 2020 move the run forward one answer at a time; fixtures/README.md section 12
        out = run_json("saturation", FIXTURES / "saturation.csv", "--base", 4, "--run", 2)
        self.assertEqual(out["step"], 1)
        self.assertEqual([(b["rows"], b["new_codes"], b["new_pct_of_base"]) for b in out["batches"][1:]], [
            ("5-6", ["E"], 25.0), ("6-7", [], 0.0), ("7-8", [], 0.0), ("8-9", ["F"], 25.0),
        ])
        self.assertEqual((out["reached_at_run"], out["reached_after_rows"], out["saturation_point"]), (2, 7, 5))

    def test_uncoded_rows_are_not_saturation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "sat.csv"
            path.write_text("id,codes\n1,A;B\n2,C\n3,\n4,\n", encoding="utf-8")
            done = run("saturation", path, "--base", 2, "--run", 1)
        self.assertEqual(done.returncode, 2)
        self.assertIn("2 row(s) have no code", done.stderr)

    def test_threshold_and_short_file(self):
        out = run_json("saturation", FIXTURES / "saturation.csv", "--base", 4, "--run", 2, "--threshold", 25)
        self.assertEqual(out["reached_at_run"], 1)  # 1 new code on 4 base codes is exactly 25%
        out = run_json("saturation", FIXTURES / "saturation.csv", "--base", 2, "--run", 1, "--threshold", 0)
        self.assertEqual(out["base_codes"], 3)
        self.assertEqual(out["reached_at_run"], 1)  # row 3 adds nothing
        done = run("saturation", FIXTURES / "saturation.csv")
        self.assertEqual(done.returncode, 2)
        self.assertIn("need 75", done.stderr)


class SampleExtrasTest(unittest.TestCase):
    def test_stratified_allocation_by_hand(self):
        # 17 eligible: free 8, paid 9. n = 6: 6*8/17 = 2.82 and 6*9/17 = 3.18, so 2 + 3 and the spare one to free
        self.assertEqual(oec.allocate({"free": 8, "paid": 9}, 6), {"free": 3, "paid": 3})
        self.assertEqual(oec.allocate({"a": 10, "b": 30, "c": 60}, 10), {"a": 1, "b": 3, "c": 6})
        out = run_json("sample", FIXTURES / "coded.csv", "--text-col", "answer", "--n", 6, "--stratify-col", "plan", "--seed", 3)
        self.assertEqual(out["strata"], {"free": {"eligible": 8, "sampled": 3}, "paid": {"eligible": 9, "sampled": 3}})
        self.assertEqual(sum(1 for i in out["ids"] if int(i) % 2), 3)  # odd ids are the free plan
        self.assertEqual(out["ids"], run_json("sample", FIXTURES / "coded.csv", "--text-col", "answer", "--n", 6, "--stratify-col", "plan", "--seed", 3)["ids"])

    def test_top_up_of_rare_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            main, audit = pathlib.Path(tmp) / "s.csv", pathlib.Path(tmp) / "audit.csv"
            out = run_json("sample", FIXTURES / "coded.csv", "--text-col", "answer", "--n", 4, "--seed", 2, "--top-up-min", 2,
                           "--out", main, "--top-up-out", audit)
            with open(main, newline="", encoding="utf-8") as handle:
                main_ids = [r["id"] for r in csv.DictReader(handle)]
            with open(audit, newline="", encoding="utf-8") as handle:
                audit_rows = list(csv.DictReader(handle))
        with open(FIXTURES / "coded.csv", newline="", encoding="utf-8") as handle:
            codes = {r["id"]: r["codes"].split(";") for r in csv.DictReader(handle)}
        available = {"PRICE": 7, "SUPPORT": 4, "SPEED": 4, "UX": 3, "UNCODABLE": 2, "OTHER": 1}
        both = out["ids"] + out["top_up_ids"]
        for code, total in available.items():
            self.assertGreaterEqual(sum(1 for i in both if code in codes[i]), min(2, total), code)
        self.assertEqual(out["requested"], 4)
        # the random sample stays as drawn; the audit rows go to their own file
        self.assertEqual((out["sampled"], main_ids), (4, out["ids"]))
        self.assertEqual(len(out["top_up_ids"]), sum(out["topped_up"].values()))
        self.assertEqual([r["id"] for r in audit_rows], out["top_up_ids"])
        self.assertFalse(set(main_ids) & set(out["top_up_ids"]))
        self.assertEqual(list(audit_rows[0]), ["id", "answer"])  # still blind
        self.assertEqual(run("sample", FIXTURES / "coded.csv", "--text-col", "answer", "--n", 4, "--top-up-min", 2, "--codes-col", "nope").returncode, 2)

    def test_top_up_needs_its_own_file(self):
        done = run("sample", FIXTURES / "coded.csv", "--text-col", "answer", "--n", 4, "--top-up-min", 2)
        self.assertEqual(done.returncode, 2)
        self.assertIn("--top-up-out", done.stderr)


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


class ReviewFixesTest(unittest.TestCase):
    """Regression tests for the 2026-11 review findings; each failed before its fix."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_validate_source_finds_missing_respondents(self):
        coded = write(self.dir / "one.csv", "id,plan,answer,codes\n1,free,Too expensive for what it does,PRICE\n")
        out = run_json("validate", coded, "--codebook", FIXTURES / "codebook.csv", "--text-col", "answer", "--source", FIXTURES / "coded.csv")
        self.assertFalse(out["ok"])
        self.assertTrue(any("19 of 20 source row(s) are missing" in e for e in out["errors"]))

    def test_validate_source_finds_changed_answer_text(self):
        rows = (FIXTURES / "coded.csv").read_text(encoding="utf-8").replace("Too expensive for what it does", "Too expensive")
        coded = write(self.dir / "c.csv", rows)
        out = run_json("validate", coded, "--codebook", FIXTURES / "codebook.csv", "--text-col", "answer", "--source", FIXTURES / "coded.csv")
        self.assertTrue(any("differs from the source" in e and "'1'" in e for e in out["errors"]))
        same = run_json("validate", FIXTURES / "coded.csv", "--codebook", FIXTURES / "codebook.csv", "--text-col", "answer", "--source", FIXTURES / "coded.csv")
        self.assertTrue(same["ok"])

    def second_coder_file(self, swap):
        with open(FIXTURES / "coded.csv", newline="", encoding="utf-8") as handle:
            rows = [r for r in csv.DictReader(handle) if r["id"] in ("1", "2", "4", "5")]
        if swap:  # codes stay, the answers attached to ids 1 and 2 trade places
            rows[0]["answer"], rows[1]["answer"] = rows[1]["answer"], rows[0]["answer"]
        path = self.dir / ("swapped.csv" if swap else "second.csv")
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["id", "answer", "codes"], extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_agreement_rejects_answers_that_differ_between_coders(self):
        done = run("agreement", FIXTURES / "coded.csv", self.second_coder_file(swap=True), "--allow-unmatched", "--text-col", "answer", "--bootstrap", 0)
        self.assertEqual(done.returncode, 2)
        self.assertIn("different answer text", done.stderr)

    def test_agreement_on_the_sample_manifest(self):
        second = self.second_coder_file(swap=False)
        sample = write(self.dir / "sample.csv", "id,answer\n1,Too expensive for what it does\n2,Support took three days to reply\n4,The app is slow and the price went up\n5,ok\n")
        done = run("agreement", FIXTURES / "coded.csv", second, "--sample", sample, "--text-col", "answer", "--bootstrap", 0)
        self.assertEqual(done.returncode, 2)  # row 5 of the sample has other text in the coded files
        self.assertIn("different answer text", done.stderr)
        with open(FIXTURES / "coded.csv", newline="", encoding="utf-8") as handle:
            answer5 = next(r["answer"] for r in csv.DictReader(handle) if r["id"] == "5")
        sample = write(self.dir / "sample.csv", "id,answer\n1,x\n".replace("1,x", "") + "".join(
            f'{i},"{t}"\n' for i, t in (("1", "Too expensive for what it does"), ("2", "Support took three days to reply"),
                                       ("4", "The app is slow and the price went up"), ("5", answer5))))
        out = run_json("agreement", FIXTURES / "coded.csv", second, "--sample", sample, "--text-col", "answer", "--bootstrap", 0)
        self.assertEqual(out["overall"]["units"], 4)
        missing = write(self.dir / "more.csv", sample.read_text(encoding="utf-8") + "6,anything\n")
        done = run("agreement", FIXTURES / "coded.csv", second, "--sample", missing, "--text-col", "answer", "--bootstrap", 0)
        self.assertEqual(done.returncode, 2)
        self.assertIn("sampled id(s) are not coded", done.stderr)

    def test_sample_sizes_follow_the_written_rules(self):
        out = run_json("sample", FIXTURES / "coded.csv", "--text-col", "answer", "--n", 100, "--all-if-fewer")
        self.assertEqual(out["sampled"], 17)  # "100 answered rows, all if fewer"
        out = run_json("sample", FIXTURES / "coded.csv", "--text-col", "answer", "--fraction", 0.2, "--at-least", 30)
        self.assertEqual(out["sampled"], 17)  # "20%, at least 30 (all rows if fewer)"
        out = run_json("sample", FIXTURES / "coded.csv", "--text-col", "answer", "--fraction", 0.2, "--at-least", 5)
        self.assertEqual(out["sampled"], 5)  # 0.2 * 17 = 3, raised to 5
        self.assertEqual(run("sample", FIXTURES / "coded.csv", "--text-col", "answer", "--n", 100).returncode, 2)

    def test_shuffle_writes_a_seeded_random_order(self):
        plain = run_json("sample", FIXTURES / "coded.csv", "--text-col", "answer", "--n", 17)
        mixed = run_json("sample", FIXTURES / "coded.csv", "--text-col", "answer", "--n", 17, "--shuffle", "--seed", 4)
        self.assertEqual(sorted(plain["ids"]), sorted(mixed["ids"]))
        self.assertNotEqual(plain["ids"], mixed["ids"])
        self.assertEqual(mixed["ids"], run_json("sample", FIXTURES / "coded.csv", "--text-col", "answer", "--n", 17, "--shuffle", "--seed", 4)["ids"])

    def test_outputs_never_overwrite_inputs(self):
        coded = write(self.dir / "c.csv", (FIXTURES / "coded.csv").read_text(encoding="utf-8"))
        before = coded.read_text(encoding="utf-8")
        for args in (
            ("sample", coded, "--text-col", "answer", "--n", 2, "--out", coded),
            ("merge", coded, "--adjudicated", FIXTURES / "adjudicated.csv", "--out", coded),
            ("agreement", coded, coded, "--disagreements", coded, "--bootstrap", 0),
        ):
            done = run(*args)
            self.assertEqual(done.returncode, 2, args[0])
            self.assertIn("is also an input file", done.stderr)
        self.assertEqual(coded.read_text(encoding="utf-8"), before)

    def test_quotes_may_be_trimmed_at_the_ends(self):
        quotes = write(self.dir / "q.csv", 'id,code,quote\n1,PRICE,...expensive for what it…\n1,PRICE,"[...] for what it does"\n')
        out = run_json("validate", FIXTURES / "coded.csv", "--codebook", FIXTURES / "codebook.csv", "--text-col", "answer", "--quotes", quotes)
        self.assertEqual(out["errors"], [])
        joined = write(self.dir / "j.csv", "id,code,quote\n1,PRICE,Too expensive ... what it does\n")
        out = run_json("validate", FIXTURES / "coded.csv", "--codebook", FIXTURES / "codebook.csv", "--text-col", "answer", "--quotes", joined)
        self.assertEqual(len(out["errors"]), 1)  # an ellipsis inside a quote is still not word for word

    def test_semicolon_files_are_read(self):
        # a European Excel export: columns separated by ';', so the codes inside a cell use '|'
        with open(FIXTURES / "coded.csv", newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        semi = self.dir / "semi.csv"
        with open(semi, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter=";")
            for row in rows:
                writer.writerow(row[:-1] + [row[-1].replace(";", "|")])
        comma = run_json("counts", FIXTURES / "coded.csv", "--text-col", "answer")
        out = run_json("counts", semi, "--text-col", "answer", "--delimiter", "|")
        self.assertEqual(out["answered"], 17)
        self.assertEqual(out["codes"], comma["codes"])
        explicit = run_json("counts", semi, "--text-col", "answer", "--csv-delimiter", ";", "--code-sep", "|")
        self.assertEqual(explicit["codes"], comma["codes"])

    def test_comma_inside_a_code_is_an_error(self):
        coded = write(self.dir / "c.csv", 'id,answer,codes\n1,a,"PRICE, SPEED"\n2,b,PRICE\n')
        done = run("counts", coded, "--text-col", "answer", "--min-base", 1)
        self.assertEqual(done.returncode, 2)
        self.assertIn("contains a comma", done.stderr)

    def test_merge_batches_into_a_file_without_codes(self):
        responses = write(self.dir / "r.csv", "id,answer\n1,Too pricey\n2,Slow\n3,\n")
        b1 = write(self.dir / "b1.csv", "id,codes\n1,PRICE\n")
        b2 = write(self.dir / "b2.csv", "id,codes\n2,SPEED\n3,NO_ANSWER\n")
        out_path = self.dir / "coded.csv"
        out = run_json("merge", responses, "--adjudicated", b1, "--adjudicated", b2, "--final-col", "codes", "--out", out_path)
        self.assertTrue(out["codes_column_added"])
        self.assertEqual(out["rows_without_codes"], 0)
        with open(out_path, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([(r["id"], r["answer"], r["codes"]) for r in rows], [("1", "Too pricey", "PRICE"), ("2", "Slow", "SPEED"), ("3", "", "NO_ANSWER")])

    def test_counts_names_no_missing_skill(self):
        out = run_json("counts", FIXTURES / "coded.csv", "--text-col", "answer")
        self.assertFalse(any("survey-crosstabs" in note for note in out["notes"]))



class SecondReviewFixesTest(unittest.TestCase):
    """Regression tests for the second (Gemini) review of 2026-11-19; each failed before its fix."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.codebook = write(self.dir / "cb.csv", "code,label,definition,include,exclude,example_quote\nPRICE,Price,d,i,e,a\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_comma_inside_a_quoted_header_does_not_decide_the_delimiter(self):
        question = "If you could change one thing, what would it be?"
        semi = write(self.dir / "semi.csv", f'id;"{question}"\n1;cheaper\n2;faster\n')
        out = run_json("sample", semi, "--text-col", question, "--n", 2)
        self.assertEqual(sorted(out["ids"]), ["1", "2"])

    def test_forced_csv_delimiter_leaves_comma_files_readable(self):
        semi = write(self.dir / "semi.csv", "id;answer\n1;cheaper\n2;faster\n")
        earlier = write(self.dir / "earlier.csv", "id,answer\n1,cheaper\n")
        out = run_json("sample", semi, "--csv-delimiter", ";", "--text-col", "answer", "--n", 1, "--exclude", earlier)
        self.assertEqual(out["ids"], ["2"])

    def test_disagreements_keep_a_custom_id_column(self):
        a = write(self.dir / "a.csv", "rid,answer,codes\n1,a,PRICE\n2,b,SPEED\n")
        b = write(self.dir / "b.csv", "rid,answer,codes\n1,a,PRICE\n2,b,PRICE\n")
        dis = self.dir / "dis.csv"
        run_json("agreement", a, b, "--id-col", "rid", "--text-col", "answer", "--bootstrap", 0, "--disagreements", dis)
        with open(dis, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["rid"], "2")
        rows[0]["final_codes"] = "SPEED"
        with open(dis, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        out = run_json("merge", a, "--id-col", "rid", "--adjudicated", dis, "--out", self.dir / "m.csv")
        self.assertEqual(out["confirmed"], ["2"])

    def test_agreement_text_col_typo_is_an_error_and_missing_columns_are_named(self):
        a = write(self.dir / "a.csv", "id,answer,codes\n1,a,PRICE\n2,b,SPEED\n")
        b = write(self.dir / "b.csv", "id,codes\n1,PRICE\n2,PRICE\n")
        done = run("agreement", a, b, "--text-col", "answers", "--bootstrap", 0)
        self.assertEqual(done.returncode, 2)
        self.assertIn("no file has an answer column named 'answers'", done.stderr)
        out = run_json("agreement", a, b, "--text-col", "answer", "--bootstrap", 0)
        self.assertTrue(any("b.csv" in note and "could not be checked" in note for note in out["notes"]))

    def test_saturation_reads_text_col_and_codebook_and_skips_blanks(self):
        rows = "".join(f"{i},x,C{i}\n" for i in range(1, 6)) + "".join(f"{i},,\n" for i in range(6, 12)) + "12,x,C1\n13,x,C2\n14,x,C3\n"
        sat = write(self.dir / "sat.csv", "id,answer,codes\n" + rows)
        out = run_json("saturation", sat, "--text-col", "answer", "--base", 5, "--run", 3)
        self.assertEqual(out["blank_answers_skipped"], 6)
        self.assertEqual([b["rows"] for b in out["batches"]], ["1-5", "6-8"])
        self.assertEqual(out["reached_at_run"], 1)
        bad = write(self.dir / "bad.csv", "id,codes\n" + "".join(f"{i},C{i}\n" for i in range(1, 6)) + "6,other\n7,\"PRICE, SPEED\"\n8,C1\n")
        done = run("saturation", bad, "--base", 5, "--run", 3)
        self.assertEqual(done.returncode, 2)
        self.assertIn("reserved code must be written 'OTHER'", done.stderr)
        self.assertIn("contains a comma", done.stderr)
        done = run("saturation", sat, "--text-col", "answer", "--base", 5, "--run", 3, "--codebook", self.codebook)
        self.assertEqual(done.returncode, 2)
        self.assertIn("unknown code 'C1'", done.stderr)

    def test_saturation_refuses_a_nan_threshold(self):
        done = run("saturation", FIXTURES / "saturation.csv", "--base", 4, "--run", 2, "--threshold", "nan")
        self.assertEqual(done.returncode, 2)
        self.assertIn("--threshold must not be negative", done.stderr)

    def test_gold_with_three_coders_prints_precision_recall_f1(self):
        gold = write(self.dir / "gold.csv", "id,codes\n1,A\n2,B\n3,A\n4,B\n")
        one = write(self.dir / "one.csv", "id,codes\n1,A\n2,A\n3,A\n4,B\n")
        two = write(self.dir / "two.csv", "id,codes\n1,A\n2,B\n3,B\n4,B\n")
        done = run("agreement", "--gold", gold, one, two, "--bootstrap", 0)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Against the reference coder A: coder B", done.stdout)
        self.assertIn("Against the reference coder A: coder C", done.stdout)
        self.assertNotIn("Against the reference coder B", done.stdout)

    def test_share_of_mentions_withheld_on_a_small_respondent_base(self):
        coded = write(self.dir / "m.csv", "id,codes\n" + "".join(f"{i},A;B\n" for i in range(1, 21)))
        out = run_json("counts", coded, "--mentions")
        self.assertEqual(out["code_assignments"], 40)  # 40 assignments, but only 20 respondents
        self.assertTrue(all(line["pct_of_mentions"] is None for line in out["codes"]))

    def test_code_on_every_row_is_not_reported_as_not_tested(self):
        a = write(self.dir / "a.csv", "id,codes\n1,A\n2,A;B\n3,A\n")
        b = write(self.dir / "b.csv", "id,codes\n1,A\n2,A\n3,A;B\n")
        c = write(self.dir / "c.csv", "id,codes\n1,A\n2,A\n3,A;B\n")
        two = run("agreement", a, b, "--bootstrap", 0).stdout
        line = next(l for l in two.splitlines() if l.startswith("A ") and "undefined" in l and "-" in l)
        self.assertIn("on every row", line)
        self.assertNotIn("not tested", line)
        multi = run("agreement", a, b, c, "--bootstrap", 0).stdout
        line = next(l for l in multi.splitlines() if l.startswith("A "))
        self.assertIn("on every row", line)
        self.assertIn("every coder gave this code to every row", multi)

    def test_validate_source_with_duplicate_ids_and_an_ids_only_check(self):
        coded = write(self.dir / "c.csv", "id,answer,codes\n1,a,PRICE\n2,b,PRICE\n")
        dup = write(self.dir / "dup.csv", "id,answer\n1,a\n1,a\n2,b\n")
        out = run_json("validate", coded, "--codebook", self.codebook, "--text-col", "answer", "--source", dup)
        self.assertFalse(out["ok"])
        self.assertTrue(any("more than once in the source" in e for e in out["errors"]))
        other = write(self.dir / "other.csv", "id,answer\n1,zzz\n2,b\n")
        done = run("validate", coded, "--codebook", self.codebook, "--source", other)
        self.assertIn("ids only", done.stdout)
        self.assertNotIn("ids and answer text", done.stdout)
        done = run("validate", coded, "--codebook", self.codebook, "--source", other, "--source-text-col", "answer")
        self.assertEqual(done.returncode, 2)
        self.assertIn("--source-text-col needs --text-col", done.stderr)

    def test_segment_table_prints_intervals(self):
        rows = "".join(f"{i},{'a' if i <= 30 else 'b'},x,{'PRICE' if i % 2 else 'SPEED'}\n" for i in range(1, 41))
        coded = write(self.dir / "seg.csv", "id,plan,answer,codes\n" + rows)
        out = run("counts", coded, "--text-col", "answer", "--segment-col", "plan").stdout
        self.assertIn("95% interval", out.split("By plan")[1].splitlines()[0])
        price = next(l for l in out.split("By plan")[1].splitlines() if l.startswith("PRICE"))
        self.assertIn("15 (50.0%, 33.2 to 66.8)", price)  # Wilson 15/30
        self.assertIn("5 (--)", price)  # segment b, base 10

    def test_codebook_codes_may_not_hold_spaces_commas_or_the_separator(self):
        bad = write(self.dir / "bad.csv", 'code,label,definition,include,exclude,example_quote\n"PRICE, COST",P,d,i,e,a\nSLOW SUPPORT,S,d,i,e,b\nA;B,X,d,i,e,c\n')
        coded = write(self.dir / "c.csv", "id,answer,codes\n1,a,OTHER\n")
        out = run_json("validate", coded, "--codebook", bad, "--text-col", "answer")
        found = [e for e in out["errors"] if "contains a space, a comma or the code separator" in e]
        self.assertEqual(len(found), 3)

    def test_io_and_empty_separator_errors_exit_2(self):
        coded = write(self.dir / "c.csv", "id,answer,codes\n1,a,PRICE\n")
        for args in (
            ("merge", coded, "--adjudicated", coded, "--final-col", "codes", "--delimiter", "", "--out", self.dir / "x.csv"),
            ("sample", coded, "--text-col", "answer", "--n", 1, "--out", self.dir / "missing" / "o.csv"),
            ("sample", self.dir, "--text-col", "answer", "--n", 1),
        ):
            done = run(*args)
            self.assertEqual(done.returncode, 2, done.stderr)
            self.assertNotIn("Traceback", done.stderr)

    def test_merge_refuses_empty_ids(self):
        coded = write(self.dir / "c.csv", "id,answer,codes\n,a,PRICE\n2,b,PRICE\n")
        adj = write(self.dir / "adj.csv", "id,final_codes\n,SPEED\n")
        done = run("merge", coded, "--adjudicated", adj, "--out", self.dir / "m.csv")
        self.assertEqual(done.returncode, 2)
        self.assertIn("empty id", done.stderr)

    def test_kappa_interval_crossing_mchugh_090_is_flagged(self):
        self.assertFalse(oec.crosses([0.82, 0.95], oec.landis_koch))
        self.assertTrue(oec.kappa_crosses_band([0.82, 0.95]))
        out = run_json("agreement", FIXTURES / "agree_a.csv", FIXTURES / "agree_b.csv", "--bootstrap", 200)
        self.assertIn("pooled_kappa_ci_crosses_band", out["overall"])

    def test_example_quote_may_be_trimmed(self):
        codebook = write(self.dir / "cb.csv", "code,label,definition,include,exclude,example_quote\nPRICE,Price,d,i,e,Too expensive...\n")
        coded = write(self.dir / "c.csv", "id,answer,codes\n1,Too expensive for me,PRICE\n")
        out = run_json("validate", coded, "--codebook", codebook, "--text-col", "answer")
        self.assertEqual(out["warnings"], [])

    def test_coder_info_and_sentiment_validation(self):
        done = run("agreement", FIXTURES / "agree_a.csv", FIXTURES / "agree_b.csv", "--bootstrap", 0,
                   "--coder-info", "a,human,EXTRA", "--coder-info", "b,human")
        self.assertEqual(done.returncode, 2)
        self.assertIn("a human coder takes no model", done.stderr)
        coded = write(self.dir / "s.csv", "id,answer,codes,sent\n1,asdf,UNCODABLE,positive\n2,good,PRICE,positive\n")
        done = run("counts", coded, "--text-col", "answer", "--sentiment-col", "sent", "--min-base", 1)
        self.assertEqual(done.returncode, 2)
        self.assertIn("an uncodable answer", done.stderr)


if __name__ == "__main__":
    unittest.main()
