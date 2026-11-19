"""Tests for scripts/conjoint_design.py. Run from the skill folder: python3 -m unittest discover -s tests

Published results reproduced: the Sawtooth sample-size example (3, 6 and 4 levels, 3 concepts, 8 tasks:
n = 500 x 6 / (8 x 3) = 125) and the optimality of the foldover pair design for two-level attributes
(Street and Burgess 2007), which must score 100% relative D-efficiency. Independent re-derivation: the
information matrix rebuilt with effects coding and a determinant by Gaussian elimination.
"""
import csv
import importlib.util
import itertools
import json
import math
import pathlib
import random
import subprocess
import sys
import tempfile
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "conjoint_design.py"


def load_module():
    spec = importlib.util.spec_from_file_location("conjoint_design", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(module)
    return module


M = load_module()


def run(*args):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                          check=False)


def run_json(*args):
    proc = run(*args, "--json")
    if proc.returncode != 0:
        raise AssertionError(f"exit {proc.returncode}: {proc.stderr}")
    return json.loads(proc.stdout)


def det_gauss(a):
    a = [row[:] for row in a]
    n = len(a)
    det = 1.0
    for c in range(n):
        pivot = max(range(c, n), key=lambda r: abs(a[r][c]))
        if abs(a[pivot][c]) < 1e-15:
            return 0.0
        if pivot != c:
            a[c], a[pivot] = a[pivot], a[c]
            det = -det
        det *= a[c][c]
        for r in range(c + 1, n):
            f = a[r][c] / a[c][c]
            for k in range(c, n):
                a[r][k] -= f * a[c][k]
    return det


class SampleSizeTest(unittest.TestCase):
    def test_sawtooth_published_example(self):
        out = run_json("sample-size", "--max-levels", 6, "--tasks", 8, "--concepts", 3)
        self.assertEqual(out["minimum_n_500"], 125)
        self.assertEqual(out["planning_n_1000"], 250)
        self.assertEqual(out["recommended_n"], 300)

    def test_exposures_and_subgroups(self):
        out = run_json("sample-size", "--max-levels", 4, "--tasks", 10, "--concepts", 3, "--respondents", 300,
                       "--subgroups", 3)
        self.assertAlmostEqual(out["exposures_per_level"], 300 * 10 * 3 / 4)
        self.assertEqual(out["recommended_n"], 600)
        self.assertEqual(out["minimum_n_500"], math.ceil(500 * 4 / 30))


class EfficiencyTest(unittest.TestCase):
    def test_foldover_pairs_are_100_percent(self):
        # 2^3 attributes, pairs: each profile against its foldover (all levels switched).
        levels = {a: ["0", "1"] for a in "ABC"}
        tasks = []
        for i, prof in enumerate(itertools.product("01", repeat=3)):
            if prof[0] == "0":
                fold = tuple("1" if x == "0" else "0" for x in prof)
                tasks.append(("1", str(i), [prof, fold]))
        d = M.diagnostics(list("ABC"), levels, tasks, False)
        self.assertAlmostEqual(d["relative_d_efficiency_pct"], 100.0, places=9)

    def test_latin_square_triples_are_100_percent(self):
        # Two 3-level attributes, sets of 3 with every level once per attribute and every pair once.
        levels = {"A": ["0", "1", "2"], "B": ["0", "1", "2"]}
        tasks = [("1", str(s), [(str(i), str((i + s) % 3)) for i in range(3)]) for s in range(3)]
        d = M.diagnostics(["A", "B"], levels, tasks, False)
        self.assertAlmostEqual(d["relative_d_efficiency_pct"], 100.0, places=9)

    def test_bound_is_never_exceeded(self):
        rng = random.Random(3)
        levels = {"A": ["a", "b", "c"], "B": ["x", "y"], "C": ["1", "2", "3", "4"]}
        for _ in range(30):
            tasks = []
            for t in range(6):
                profs = set()
                while len(profs) < 3:
                    profs.add(tuple(rng.choice(levels[k]) for k in "ABC"))
                tasks.append(("1", str(t), list(profs)))
            d = M.diagnostics(list("ABC"), levels, tasks, False)
            if d["relative_d_efficiency_pct"]:
                self.assertLessEqual(d["relative_d_efficiency_pct"], 100.0 + 1e-9)

    def test_information_matrix_rebuilt_independently(self):
        # Effects coding instead of orthonormal: det changes by a constant factor, so efficiency ratios between
        # two designs must agree. Determinants by Gaussian elimination.
        levels = {"A": ["a", "b", "c"], "B": ["x", "y"]}
        rng = random.Random(9)

        def design():
            return [("1", str(t), [(rng.choice("abc"), rng.choice("xy")) for _ in range(3)]) for t in range(12)]

        def effects_info(tasks):
            def code(prof):
                a = {"a": [1, 0], "b": [0, 1], "c": [-1, -1]}[prof[0]]
                b = {"x": [1], "y": [-1]}[prof[1]]
                return a + b
            info = [[0.0] * 3 for _ in range(3)]
            for _, _, profs in tasks:
                xs = [code(p) for p in profs]
                mean = [sum(x[i] for x in xs) / 3 for i in range(3)]
                for x in xs:
                    for i in range(3):
                        for j in range(3):
                            info[i][j] += (x[i] - mean[i]) * (x[j] - mean[j]) / 3 / len(tasks)
            return info

        d1, d2 = design(), design()
        e1 = M.diagnostics(["A", "B"], levels, d1, False)["relative_d_efficiency_pct"]
        e2 = M.diagnostics(["A", "B"], levels, d2, False)["relative_d_efficiency_pct"]
        ratio_script = e1 / e2
        ratio_indep = (det_gauss(effects_info(d1)) / det_gauss(effects_info(d2))) ** (1 / 3)
        self.assertAlmostEqual(ratio_script, ratio_indep, places=9)


class GenerateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_balanced_design_on_fixture(self):
        out_csv = pathlib.Path(self.tmp.name) / "d.csv"
        out = run_json("design", FIXTURES / "plan_spec.txt", "--tasks", 8, "--concepts", 3, "--none", "--versions",
                       20, "--seed", 7, "--out", out_csv)
        d = out["diagnostics"]
        self.assertEqual((d["versions"], d["tasks_per_version"], d["concepts_per_task"]), (20, 8, 3))
        self.assertTrue(d["none_option"])
        for a in d["attributes"]:
            self.assertLessEqual(a["max_min_ratio"], 1.1, a["name"])
            if not a["overlap_unavoidable"]:
                self.assertEqual(a["tasks_with_overlap_pct"], 0.0, a["name"])
        self.assertGreater(d["relative_d_efficiency_pct"], 90.0)
        # Same seed, same file as the shipped fixture (which conjoint-analysis also uses).
        self.assertEqual(out_csv.read_text(), (FIXTURES / "plan_design.csv").read_text())

    def test_file_format_and_prohibitions(self):
        with open(FIXTURES / "plan_design.csv", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(list(rows[0]), ["version", "task", "concept", "Brand", "Meals per week", "Delivery",
                                         "Price per week"])
        none_rows = [r for r in rows if r["concept"] == "none"]
        self.assertEqual(len(none_rows), 20 * 8)
        self.assertTrue(all(r["Brand"] == "" for r in none_rows))
        self.assertFalse(any(r["Meals per week"] == "4" and r["Price per week"] == "$40" for r in rows))
        tasks = {}
        for r in rows:
            if r["concept"] != "none":
                tasks.setdefault((r["version"], r["task"]), []).append(tuple(list(r.values())[3:]))
        self.assertTrue(all(len(set(v)) == len(v) for v in tasks.values()))

    def test_random_method_is_less_efficient(self):
        bal = run_json("design", FIXTURES / "plan_spec.txt", "--tasks", 8, "--concepts", 3, "--versions", 20)
        rnd = run_json("design", FIXTURES / "plan_spec.txt", "--tasks", 8, "--concepts", 3, "--versions", 20,
                       "--method", "random")
        self.assertGreater(bal["diagnostics"]["relative_d_efficiency_pct"],
                           rnd["diagnostics"]["relative_d_efficiency_pct"])

    def test_check_reads_what_design_writes(self):
        out = run_json("check", FIXTURES / "plan_design.csv", "--spec", FIXTURES / "plan_spec.txt")
        d = out["diagnostics"]
        self.assertEqual(d["prohibited_concepts"], 0)
        self.assertEqual(d["tasks_with_duplicate_concepts"], 0)
        self.assertTrue(d["none_option"])

    def test_check_flags_problems(self):
        path = pathlib.Path(self.tmp.name) / "bad.csv"
        path.write_text("version,task,concept,Color,Size\n1,1,1,Red,S\n1,1,2,Red,S\n1,2,1,Red,L\n1,2,2,Blue,L\n")
        d = run_json("check", path)["diagnostics"]
        self.assertEqual(d["tasks_with_duplicate_concepts"], 1)
        self.assertTrue(any("not level-balanced" in w for w in d["warnings"]))

    def test_json_spec(self):
        spec = pathlib.Path(self.tmp.name) / "s.json"
        spec.write_text(json.dumps({"attributes": [{"name": "A", "levels": ["1", "2"]},
                                                   {"name": "B", "levels": ["x", "y", "z"]}],
                                    "prohibitions": [{"A": "1", "B": "z"}]}))
        out = run_json("design", spec, "--tasks", 4, "--concepts", 2, "--versions", 5)
        self.assertEqual(out["allowed_profiles"], 5)

    def test_impossible_and_bad_specs(self):
        p = pathlib.Path(self.tmp.name)
        (p / "one.txt").write_text("A: only\nB: x | y\n")
        self.assertEqual(run("design", p / "one.txt", "--tasks", 2, "--concepts", 2).returncode, 2)
        (p / "tiny.txt").write_text("A: 1 | 2\n")
        proc = run("design", p / "tiny.txt", "--tasks", 2, "--concepts", 3)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("distinct profiles", proc.stderr)
        (p / "tight.txt").write_text("A: 1 | 2\nB: x | y\nprohibit: A=1 & B=x\nprohibit: A=2 & B=y\n"
                                     "prohibit: A=1 & B=y\n")
        proc = run("design", p / "tight.txt", "--tasks", 2, "--concepts", 2)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("allowed profile", proc.stderr)
        (p / "dup.txt").write_text("A: 1 | 1\n")
        self.assertEqual(run("design", p / "dup.txt", "--tasks", 2, "--concepts", 2).returncode, 2)
        (p / "res.txt").write_text("Task: 1 | 2\n")
        self.assertEqual(run("design", p / "res.txt", "--tasks", 2, "--concepts", 2).returncode, 2)

    def test_never_overwrites_the_spec(self):
        spec = pathlib.Path(self.tmp.name) / "s.txt"
        spec.write_text("A: 1 | 2 | 3\nB: x | y\n")
        before = spec.read_bytes()
        proc = run("design", spec, "--tasks", 2, "--concepts", 2, "--out", spec)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(spec.read_bytes(), before)

    def test_utf16_design_file(self):
        path = pathlib.Path(self.tmp.name) / "u.csv"
        path.write_bytes("version\ttask\tconcept\tA\tB\r\n1\t1\t1\ta\tx\r\n1\t1\t2\tb\ty\r\n".encode("utf-16"))
        d = run_json("check", path)["diagnostics"]
        self.assertEqual(d["concepts_per_task"], 2)

    def test_deterministic(self):
        a = run_json("design", FIXTURES / "plan_spec.txt", "--tasks", 4, "--concepts", 3, "--versions", 3,
                     "--seed", 1)
        b = run_json("design", FIXTURES / "plan_spec.txt", "--tasks", 4, "--concepts", 3, "--versions", 3,
                     "--seed", 1)
        self.assertEqual(a["diagnostics"], b["diagnostics"])


class ReviewRegressionTest(unittest.TestCase):
    """Findings from the 2026-11 reviews; each test failed before its fix."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def write(self, name, text):
        path = self.dir / name
        path.write_text(text)
        return path

    def test_zero_based_concepts_are_concepts_not_none(self):
        path = self.write("z.csv", "version,task,concept,Brand,Price\n1,1,0,A,$1\n1,1,1,B,$2\n1,1,2,C,$3\n"
                                   "1,2,0,B,$3\n1,2,1,C,$1\n1,2,2,A,$2\n1,2,3,,\n")
        d = run_json("check", path)["diagnostics"]
        self.assertEqual(d["concepts_per_task"], 3)
        self.assertEqual(d["concept_rows"], 6)
        self.assertTrue(d["none_option"])  # the blank row is the none option whatever its label

    def test_check_refuses_what_the_analysis_cannot_read(self):
        cases = {
            "dup.csv": ("version,task,concept,A\n1,1,1,x\n1,1,1,y\n", "appears twice"),
            "opt.csv": ("version,task,concept,A\n1,1,Option 1,x\n1,1,1,y\n", "appears twice"),
            "nones.csv": ("version,task,concept,A\n1,1,1,x\n1,1,2,y\n1,1,none,\n1,1,opt-out,\n",
                          "more than one none"),
            "short.csv": ("version,task,concept,A\n1,1,1,x\n1,1,none,\n1,2,1,x\n1,2,2,y\n", "fewer than two"),
            "word.csv": ("version,task,concept,A\n1,1,1,x\n1,1,none,y\n", "leave every attribute blank"),
        }
        for name, (text, message) in cases.items():
            proc = run("check", self.write(name, text))
            self.assertEqual(proc.returncode, 2, name)
            self.assertIn(message, proc.stderr, name)

    def test_none_only_design_with_spec_exits_2(self):
        spec = self.write("s.txt", "Brand: a | b\nPrice: 1 | 2\n")
        proc = run("check", self.write("n.csv", "version,task,concept,Brand,Price\n1,1,none,,\n"), "--spec", spec)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)

    def test_random_draws_concepts_independently(self):
        out_csv = self.dir / "r.csv"
        run_json("design", self.write("b.txt", "A: x | y\n"), "--tasks", 400, "--concepts", 2, "--versions", 1,
                 "--method", "random", "--seed", 5, "--out", out_csv)
        with open(out_csv, newline="") as handle:
            rows = list(csv.DictReader(handle))
        pairs = {}
        for r in rows:
            pairs.setdefault(r["task"], []).append(r["A"])
        same = sum(1 for v in pairs.values() if v[0] == v[1]) / len(pairs)
        self.assertAlmostEqual(same, 0.5, delta=0.08)  # independent draws: identical half the time

    def test_random_is_uniform_over_allowed_profiles(self):
        out_csv = self.dir / "p.csv"
        spec = self.write("p.txt", "Brand: a | b | c\nMeals: 2 | 3 | 4\nPrice: 40 | 50 | 60 | 70\n"
                                   "prohibit: Meals=4 & Price=40\n")
        run_json("design", spec, "--tasks", 10, "--concepts", 3, "--versions", 300, "--method", "random",
                 "--seed", 2, "--out", out_csv)
        with open(out_csv, newline="") as handle:
            rows = list(csv.DictReader(handle))
        n = len(rows)
        self.assertAlmostEqual(sum(r["Meals"] == "4" for r in rows) / n, 9 / 33, delta=0.015)
        self.assertAlmostEqual(sum(r["Price"] == "40" for r in rows) / n, 6 / 33, delta=0.015)

    def test_balanced_overlap_is_not_tied_to_screen_position(self):
        out_csv = self.dir / "pos.csv"
        run_json("design", self.write("pos.txt", "A: x | y\nB: 1 | 2 | 3\n"), "--tasks", 10, "--concepts", 3,
                 "--versions", 40, "--out", out_csv)
        with open(out_csv, newline="") as handle:
            rows = list(csv.DictReader(handle))
        tasks = {}
        for r in rows:
            tasks.setdefault((r["version"], r["task"]), []).append(r["A"])
        share = [sum(v[i] == v[j] for v in tasks.values()) / len(tasks) for i, j in ((0, 1), (0, 2), (1, 2))]
        self.assertLess(max(share) - min(share), 0.15, share)

    def test_singular_design_exits_2_and_writes_nothing(self):
        spec = self.write("imp.txt", "A: 1 | 2\nB: x | y | z\nprohibit: A=1 & B=x\nprohibit: A=1 & B=y\n"
                                     "prohibit: A=1 & B=z\n")
        out_csv = self.dir / "never.csv"
        proc = run("design", spec, "--tasks", 4, "--concepts", 2, "--versions", 3, "--out", out_csv)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("singular", proc.stderr)
        self.assertFalse(out_csv.exists())

    def test_spec_parsing(self):
        out = run_json("design", self.write("sp.txt", "Flavor: Salt and Pepper | Plain\nSize: S | L\n"
                                                      "prohibit: Flavor=Salt and Pepper & Size=L\n"),
                       "--tasks", 2, "--concepts", 2, "--versions", 2)
        self.assertEqual(out["prohibitions"], [{"Flavor": "Salt and Pepper", "Size": "L"}])
        out = run_json("design", self.write("pi.txt", "Prohibited items: None | Liquids\nB: x | y\n"),
                       "--tasks", 2, "--concepts", 2, "--versions", 1)
        self.assertEqual(out["attributes"][0]["name"], "Prohibited items")
        out = run_json("design", self.write("ct.txt", "Price: $1,200, $2,500, $3,000\nB: x | y\n"),
                       "--tasks", 6, "--concepts", 2, "--versions", 2)
        self.assertEqual(out["attributes"][0]["levels"], ["$1,200", "$2,500", "$3,000"])
        for text in ("A: 1 | 2\nB: x | y\nprohibit: A=1\n", "A: 1 | 2\nB: x | y\nprohibit: A=1 & A=2\n"):
            self.assertEqual(run("design", self.write("bad.txt", text), "--tasks", 2, "--concepts", 2).returncode, 2)

    def test_reserved_names_match_conjoint_analysis(self):
        self.assertEqual(M.RESERVED, {"version", "block", "task", "set", "concept", "alt", "alternative",
                                      "respondent", "respondent_id", "resp.id", "id", "responseid", "response_id",
                                      "rid", "chosen", "choice", "segment", "weight", "ques"})
        self.assertNotIn("0", M.NONE_LABELS)
        for name in ("ID", "alt", "ques", "Block"):
            proc = run("design", self.write("r.txt", f"{name}: a | b\nB: x | y\n"), "--tasks", 2, "--concepts", 2)
            self.assertEqual(proc.returncode, 2, name)

    def test_bad_input_exits_2_without_traceback(self):
        good = self.write("g.txt", "A: 1 | 2\nB: x | y\n")
        design = self.write("d.csv", "version,task,concept,A\n1,1,1,x\n1,1,2,y\n")
        calls = [
            ("sample-size", "--max-levels", 4, "--tasks", 10, "--concepts", 3, "--respondents", -10),
            ("sample-size", "--max-levels", 4, "--tasks", 10, "--concepts", 3, "--subgroups", 0),
            ("check", design, "--delimiter", "::"),
            ("design", self.write("n.json", '{"attributes": null}'), "--tasks", 2, "--concepts", 2),
            ("design", self.write("l.json", '{"attributes": [{"name": "A", "levels": "abc"}]}'), "--tasks", 2,
             "--concepts", 2),
            ("design", good, "--tasks", 2, "--concepts", 2, "--versions", 1, "--out", self.dir / "no" / "d.csv"),
            ("check", self.write("bad.csv", b"\xef\xbb\xbfversion\xff".decode("latin-1"))),
        ]
        for call in calls:
            proc = run(*call)
            self.assertEqual(proc.returncode, 2, call)
            self.assertNotIn("Traceback", proc.stderr, call)

    def test_random_low_efficiency_is_not_told_to_switch_method(self):
        out = run_json("design", FIXTURES / "plan_spec.txt", "--tasks", 4, "--concepts", 2, "--versions", 5,
                       "--method", "random", "--seed", 4)
        warnings = " ".join(out["diagnostics"]["warnings"])
        self.assertIn("expected cost of full randomization", warnings)
        self.assertNotIn("rebuild with --method balanced", warnings)

    def test_sample_size_from_actual_allocation(self):
        # Version 1 has 4 tasks, version 2 has 2; level 'c' is shown once in the whole design.
        rows = ["version,task,concept,A,B"]
        for v, t, a1, a2 in ((1, 1, "a", "b"), (1, 2, "b", "a"), (1, 3, "a", "b"), (1, 4, "b", "c"),
                             (2, 1, "a", "b"), (2, 2, "b", "a")):
            rows += [f"{v},{t},1,{a1},x", f"{v},{t},2,{a2},y"]
        out = run_json("check", self.write("u.csv", "\n".join(rows) + "\n"), "--subgroups", 2)
        ss = out["sample_size"]
        self.assertEqual(ss["t"], 2)  # the shortest version, not the longest
        self.assertAlmostEqual(ss["lowest_level_exposures_per_respondent"], 0.5)
        self.assertEqual(ss["minimum_n_500_actual"], 1000)
        self.assertEqual(ss["per_subgroup_n"], 1000)
        self.assertEqual(ss["recommended_n"], 2000)
        self.assertTrue(any("different numbers of tasks" in w for w in out["diagnostics"]["warnings"]))

    def test_strongest_pair_named_and_prohibition_blamed_only_when_linked(self):
        path = self.write("v.csv", "version,task,concept,A,B,C\n1,1,1,a,x,p\n1,1,2,b,y,q\n1,2,1,a,x,q\n"
                                   "1,2,2,b,y,p\n")
        spec = self.write("v.txt", "A: a | b\nB: x | y\nC: p | q\nprohibit: A=a & C=q & B=y\n")
        proc = run("check", path)
        self.assertIn("(A x B)", proc.stdout)
        warnings = run_json("check", path, "--spec", spec)["diagnostics"]["warnings"]
        self.assertTrue(any("A and B are associated" in w and "prohibition links" in w for w in warnings))
        spec2 = self.write("v2.txt", "A: a | b\nB: x | y\nC: p | q\nprohibit: A=b & C=q\n")
        warnings = run_json("check", path, "--spec", spec2)["diagnostics"]["warnings"]
        self.assertTrue(any("A and B are associated" in w and "prohibition" not in w for w in warnings))

    def test_spreadsheet_quirks(self):
        d = run_json("check", self.write("x.csv", "sep=;\nversion;task;concept;A;\n1;1;1;x;\n1;1;2;y;\n"))
        self.assertEqual(d["attributes"], ["A"])
        proc = run("check", self.write("c.csv", "version,task,concept,A,a\n1,1,1,x,x\n1,1,2,y,y\n"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("ignoring case", proc.stderr)


if __name__ == "__main__":
    unittest.main()
