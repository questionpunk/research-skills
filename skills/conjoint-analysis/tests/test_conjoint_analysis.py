"""Tests for scripts/conjoint_analysis.py. Run from the skill folder: python3 -m unittest discover -s tests

Published examples reproduced: the SAS "Choice of Chocolate Candies" conditional logit (Kuhfeld 2010; data in
SAS sample "Discrete Choice 1"). Independent re-derivations: the logit maximum found by a derivative-free
search, part-worth recovery from a known simulated logit, and the OLS identity AMCE = difference in marginal
means for one randomized attribute (Hainmueller, Hopkins and Yamamoto 2014). The Chapman and Feit (2015)
minivan check is described in fixtures/README.md (dataset not shipped).
"""
import csv
import importlib.util
import json
import math
import pathlib
import subprocess
import sys
import tempfile
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "fixtures"
SCRIPT = SKILL / "scripts" / "conjoint_analysis.py"
PLAN = ["--design", FIXTURES / "plan_design.csv", "--spec", FIXTURES / "plan_spec.txt"]
PRICE = "Price per week"


def load_module():
    spec = importlib.util.spec_from_file_location("conjoint_analysis", SCRIPT)
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


def coef(out, name, group=0):
    return next(c for c in out["groups"][group]["coefficients"] if c["name"] == name)


class CandyPublishedTest(unittest.TestCase):
    """Kuhfeld (2010), Choice of Chocolate Candies: Dark 1.38629, Soft -2.19722, Nuts 0.84730
    (= ln 4, ln 1/9, ln 7/3), standard errors 0.79057, 1.05409, 0.69007."""

    @classmethod
    def setUpClass(cls):
        cls.out = run_json(FIXTURES / "candy_stacked.csv", "--spec", FIXTURES / "candy_spec.txt")

    def test_estimates(self):
        self.assertAlmostEqual(coef(self.out, "Chocolate: Dark")["estimate"], 1.38629, places=5)
        self.assertAlmostEqual(coef(self.out, "Center: Soft")["estimate"], -2.19722, places=5)
        self.assertAlmostEqual(coef(self.out, "Nuts: Nuts")["estimate"], 0.84730, places=5)
        self.assertAlmostEqual(coef(self.out, "Chocolate: Dark")["estimate"], math.log(4), places=9)

    def test_model_standard_errors(self):
        # Closed form: one set of the full 2^3 factorial, so each SE is 1 / sqrt(n p (1 - p)).
        self.assertAlmostEqual(coef(self.out, "Chocolate: Dark")["se_model"], 0.79057, places=5)
        self.assertAlmostEqual(coef(self.out, "Center: Soft")["se_model"], 1.05409, places=5)
        self.assertAlmostEqual(coef(self.out, "Nuts: Nuts")["se_model"], 0.69007, places=5)

    def test_importance_by_hand(self):
        # Centred part-worths are +/- half of each coefficient; importance = |b| / sum |b|.
        b = [math.log(4), math.log(9), math.log(7 / 3)]
        est = self.out["groups"][0]["estimates"]
        self.assertAlmostEqual(est["imp | Chocolate"]["value"], 100 * b[0] / sum(b), places=6)
        self.assertAlmostEqual(est["pw | Center | Soft"]["value"], -math.log(9) / 2, places=9)

    def test_simulator_by_hand(self):
        out = run_json(FIXTURES / "candy_stacked.csv", "--spec", FIXTURES / "candy_spec.txt",
                       "--product", "A: Chocolate=Dark; Center=Chewy; Nuts=Nuts",
                       "--product", "B: Chocolate=Milk; Center=Soft; Nuts=No Nuts")
        ua, ub = math.log(4) + math.log(7 / 3), -math.log(9)
        want = 100 * math.exp(ua) / (math.exp(ua) + math.exp(ub))
        est = out["groups"][0]["estimates"]
        self.assertAlmostEqual(est["share | A"]["value"], want, places=6)
        self.assertAlmostEqual(est["share | A"]["value"] + est["share | B"]["value"], 100.0, places=9)


class IndependentMaximumTest(unittest.TestCase):
    def test_newton_matches_derivative_free_search(self):
        # Fit the plan data, then confirm no coordinate move of 1e-3 raises the log-likelihood and that a
        # cyclic golden-section search started at zero reaches the same maximum.
        args = M.build_parser().parse_args([str(FIXTURES / "plan_responses.csv"), *map(str, PLAN),
                                            "--price-attr", PRICE])
        data = M.load(args)
        model = M.Model(data.attrs, data.levels, [PRICE], data.has_none)
        tasks = M.pool_tasks(model, data.respondents, sorted(data.respondents))
        res = M.fit(tasks, model.p, unit_scale=model.scale)
        ll = lambda b: M.evaluate(b, tasks, model.p, False)[0]
        for i in range(model.p):
            for d in (-1e-3, 1e-3):
                b = list(res["beta"])
                b[i] += d
                self.assertLess(ll(b), res["loglik"])
        beta = [0.0] * model.p
        phi = (math.sqrt(5) - 1) / 2
        for _ in range(150):
            for i in range(model.p):
                lo, hi = beta[i] - 0.5 / model.scale[i], beta[i] + 0.5 / model.scale[i]
                for _ in range(40):
                    a, c = hi - phi * (hi - lo), lo + phi * (hi - lo)
                    ba, bc = list(beta), list(beta)
                    ba[i], bc[i] = a, c
                    if ll(ba) > ll(bc):
                        hi = c
                    else:
                        lo = a
                beta[i] = (lo + hi) / 2
        self.assertAlmostEqual(ll(beta), res["loglik"], delta=1e-3)


class PlanRecoveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = run_json(FIXTURES / "plan_responses.csv", *PLAN, "--price-attr", PRICE, "--segment", "segment",
                           "--product", "A: Brand=GreenPlate; Meals per week=3; Delivery=Weekly; Price per week=$55",
                           "--product", "B: Brand=HomeChef; Meals per week=4; Delivery=Every two weeks; "
                                        "Price per week=$50")

    def test_counts(self):
        c = self.out["counts"]
        self.assertEqual((c["respondents_used"], c["tasks_used"], c["tasks_excluded"]), (400, 3200, {}))

    def test_recovers_true_utilities(self):
        # The fixture was simulated from GreenPlate +0.3, HomeChef -0.2, 3 meals +0.5, 4 meals +0.6, two-weekly
        # -0.4, price -0.05 per dollar, none -3.0 (fixtures/generate_fixtures.py). Each estimate within 3 SE.
        truth = {"Brand: GreenPlate": 0.3, "Brand: HomeChef": -0.2, "Meals per week: 3": 0.5,
                 "Meals per week: 4": 0.6, "Delivery: Every two weeks": -0.4, "Price per week (per unit)": -0.05}
        for name, value in truth.items():
            c = coef(self.out, name)
            self.assertLess(abs(c["estimate"] - value), 3 * c["se_robust"], name)

    def test_wtp_is_ratio(self):
        b = {c["name"]: c["estimate"] for c in self.out["groups"][0]["coefficients"]}
        est = self.out["groups"][0]["estimates"]
        self.assertAlmostEqual(est["wtp | Brand | GreenPlate"]["value"],
                               -b["Brand: GreenPlate"] / b["Price per week (per unit)"], places=9)

    def test_shares_include_none_and_sum_to_100(self):
        est = self.out["groups"][0]["estimates"]
        total = sum(v["value"] for k, v in est.items() if k.startswith("share"))
        self.assertAlmostEqual(total, 100.0, places=9)
        self.assertIn("share | None", est)

    def test_segments_and_wald_test(self):
        labels = [g["label"] for g in self.out["groups"]]
        self.assertEqual(labels, ["All respondents", "segment = family", "segment = single"])
        t = self.out["segment_test"]
        self.assertEqual(t["method"], "cluster-robust Wald")
        self.assertEqual(t["df"], 7)  # 2 brand + 2 meals + 1 delivery + 1 price + 1 none, times (2 - 1)
        # Two segments: (b1 - b2)' (V1 + V2)^-1 (b1 - b2), recomputed from the reported robust covariances is not
        # possible from JSON (only SEs), so check the statistic is positive and the p-value is in range.
        self.assertGreater(t["statistic"], 0)
        self.assertTrue(0 <= t["p_value"] <= 1)
        self.assertTrue(any("Small base" in w for w in self.out["groups"][1]["warnings"]))

    def test_wide_responses_give_the_same_fit(self):
        with tempfile.TemporaryDirectory() as tmp:
            wide = pathlib.Path(tmp) / "wide.csv"
            rows = {}
            with open(FIXTURES / "plan_responses.csv", newline="") as handle:
                for r in csv.DictReader(handle):
                    rows.setdefault((r["respondent"], r["version"]), {})[r["task"]] = r["choice"]
            with open(wide, "w", newline="") as handle:
                w = csv.writer(handle)
                w.writerow(["respondent", "version"] + [f"task{t}" for t in range(1, 9)])
                for (rid, v), ch in rows.items():
                    w.writerow([rid, v] + [ch[str(t)] for t in range(1, 9)])
            out = run_json(wide, *PLAN, "--price-attr", PRICE)
        self.assertAlmostEqual(out["groups"][0]["fit"]["loglik"], self.out["groups"][0]["fit"]["loglik"], places=6)

    def test_bootstrap_is_deterministic(self):
        a = run_json(FIXTURES / "candy_stacked.csv", "--bootstrap", 30, "--seed", 4)
        b = run_json(FIXTURES / "candy_stacked.csv", "--bootstrap", 30, "--seed", 4)
        self.assertEqual(a["groups"][0]["estimates"], b["groups"][0]["estimates"])


class AmceTest(unittest.TestCase):
    def test_amce_equals_difference_in_marginal_means_for_one_attribute(self):
        out = run_json(FIXTURES / "one_attribute_stacked.csv", "--amce")
        a = out["amce"]
        mm = a["marginal_means"]
        for level in ("Green", "Red"):
            self.assertAlmostEqual(a["amce"][f"Color | {level}"]["estimate"],
                                   mm[f"Color | {level}"]["mean"] - mm["Color | Blue"]["mean"], places=12)
        self.assertEqual(a["baseline"], {"Color": "Blue"})

    def test_amce_warns_on_a_balanced_design(self):
        out = run_json(FIXTURES / "plan_responses.csv", *PLAN, "--amce")
        self.assertTrue(out["amce"]["warnings"])


class EdgeCaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, text, encoding="utf-8"):
        path = pathlib.Path(self.tmp.name) / name
        path.write_bytes(text.encode(encoding))
        return path

    def test_header_only(self):
        proc = run(self.write("a.csv", "respondent,task,concept,Color,chosen\n"))
        self.assertEqual(proc.returncode, 2)

    def test_duplicate_headers(self):
        proc = run(self.write("a.csv", "respondent,task,Color,Color,chosen\n1,1,a,a,1\n"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("more than one column", proc.stderr)

    def test_separation_exits_3_with_reason(self):
        rows = "".join(f"{r},1,1,Red,1\n{r},1,2,Blue,0\n" for r in range(1, 6))
        proc = run(self.write("a.csv", "respondent,task,concept,Color,chosen\n" + rows))
        self.assertEqual(proc.returncode, 3)
        self.assertIn("separation", proc.stderr)
        self.assertIn("Never chosen: Color=Blue", proc.stderr)
        out = run_json(self.write("b.csv", "respondent,task,concept,Color,chosen\n" + rows), "--counts-only")
        self.assertEqual(out["groups"][0]["counts"]["Color"]["Red"]["choice_rate"], 1.0)

    def test_one_respondent_uses_model_se(self):
        rows = "1,1,1,Red,1\n1,1,2,Blue,0\n1,2,1,Red,0\n1,2,2,Blue,1\n1,3,1,Red,1\n1,3,2,Blue,0\n"
        out = run_json(self.write("a.csv", "respondent,task,concept,Color,chosen\n" + rows))
        g = out["groups"][0]
        self.assertIn("model-based", g["fit"]["covariance"])
        self.assertAlmostEqual(g["coefficients"][0]["estimate"], math.log(2), places=9)

    def test_one_level_attribute_refused(self):
        rows = "1,1,1,Red,x,1\n1,1,2,Blue,x,0\n"
        proc = run(self.write("a.csv", "respondent,task,concept,Color,Size,chosen\n" + rows))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("only one level", proc.stderr)

    def test_bad_tasks_refused_above_5_percent(self):
        rows = "".join(f"{r},1,1,Red,1\n{r},1,2,Blue,{1 if r < 3 else 0}\n{r},2,1,Red,0\n{r},2,2,Blue,1\n"
                       for r in range(1, 11))
        path = self.write("a.csv", "respondent,task,concept,Color,chosen\n" + rows)
        proc = run(path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not exactly one chosen row", proc.stderr)
        out = run_json(path, "--allow-exclusions")
        self.assertEqual(out["counts"]["tasks_excluded"], {"not exactly one chosen row": 2})

    def test_none_choice_without_none_row(self):
        path = self.write("r.csv", "respondent,version,task,choice\nr1,1,1,none\nr1,1,2,1\n")
        design = self.write("d.csv", "version,task,concept,Color\n1,1,1,Red\n1,1,2,Blue\n1,2,1,Blue\n1,2,2,Red\n")
        proc = run(path, "--design", design)
        self.assertEqual(proc.returncode, 2)
        out = run_json(path, "--design", design, "--none-when-missing-row", "--counts-only")
        self.assertTrue(out["none_option"])

    def test_utf16_semicolon_qualtrics_rows(self):
        text = ("respondent;task;concept;Color;chosen\r\n"
                "Respondent;Task;Concept;Color;Chosen\r\n"
                '{"ImportId":"r"};{"ImportId":"t"};{"ImportId":"c"};{"ImportId":"q"};{"ImportId":"x"}\r\n'
                + "".join(f"{r};1;1;Red;1\r\n{r};1;2;Blue;0\r\n{r};2;1;Red;0\r\n{r};2;2;Blue;1\r\n{r};3;1;Red;1\r\n"
                          f"{r};3;2;Blue;0\r\n" for r in range(1, 4)))
        out = run_json(self.write("a.csv", text, "utf-16"), "--counts-only")
        self.assertEqual(out["counts"]["tasks_used"], 9)
        self.assertTrue(any("Qualtrics" in n for n in out["notes"]))

    def test_simulator_refuses_extrapolation_and_unknown_levels(self):
        proc = run(FIXTURES / "plan_responses.csv", *PLAN, "--price-attr", PRICE, "--product",
                   "A: Brand=GreenPlate; Meals per week=3; Delivery=Weekly; Price per week=$90")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("outside the tested range", proc.stderr)
        proc = run(FIXTURES / "plan_responses.csv", *PLAN, "--product",
                   "A: Brand=Acme; Meals per week=3; Delivery=Weekly; Price per week=$50")
        self.assertEqual(proc.returncode, 2)

    def test_wtp_withheld_when_price_effect_is_not_negative(self):
        # Six of ten respondents pick the dearer option in both tasks: the price effect is positive.
        rows = "".join(f"{r},1,1,a,10,{0 if r <= 6 else 1}\n{r},1,2,b,20,{1 if r <= 6 else 0}\n"
                       f"{r},2,1,a,20,{1 if r <= 6 else 0}\n{r},2,2,b,10,{0 if r <= 6 else 1}\n" for r in range(1, 11))
        out = run_json(self.write("a.csv", "respondent,task,concept,Brand,Price,chosen\n" + rows),
                       "--price-attr", "Price")
        g = out["groups"][0]
        self.assertFalse(any(k.startswith("wtp") for k in g["estimates"]))
        self.assertTrue(any("not clearly negative" in w for w in g["warnings"]))

    def test_one_segment_value(self):
        rows = "".join(f"{r},1,1,Red,1,x\n{r},1,2,Blue,0,x\n{r},2,1,Red,0,x\n{r},2,2,Blue,1,x\n{r},3,1,Blue,0,x\n"
                       f"{r},3,2,Red,1,x\n" for r in range(1, 5))
        out = run_json(self.write("a.csv", "respondent,task,concept,Color,chosen,grp\n" + rows), "--segment", "grp")
        self.assertTrue(any("Only one value" in n for n in out["notes"]))
        self.assertIsNone(out["segment_test"])

    def test_text_report(self):
        proc = run(FIXTURES / "candy_stacked.csv", "--spec", FIXTURES / "candy_spec.txt")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Chocolate: Dark", proc.stdout)


def plan_rows():
    with open(FIXTURES / "plan_design.csv", newline="") as handle:
        return list(csv.reader(handle))


class ReviewRegressionTest(unittest.TestCase):
    """Cases from the November 2026 reviews; each failed before its fix."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, text, encoding="utf-8"):
        path = pathlib.Path(self.tmp.name) / name
        path.write_bytes(text.encode(encoding) if isinstance(text, str) else text)
        return path

    def write_rows(self, name, rows):
        path = pathlib.Path(self.tmp.name) / name
        with open(path, "w", newline="") as handle:
            csv.writer(handle).writerows(rows)
        return path

    def plan_with(self, change_design=None, change_spec=None):
        rows = plan_rows()
        if change_design:
            rows = change_design(rows)
        design = self.write_rows("design.csv", rows)
        spec_text = (FIXTURES / "plan_spec.txt").read_text()
        spec = self.write("spec.txt", change_spec(spec_text) if change_spec else spec_text)
        return ["--design", design, "--spec", spec]

    def test_zero_based_concept_labels_are_concepts(self):
        design = "version,task,concept,Color\n" + "".join(
            f"1,{t},0,{'Red' if t % 2 else 'Blue'}\n1,{t},1,{'Blue' if t % 2 else 'Red'}\n" for t in range(1, 5))
        picks = {1: 0, 2: 1, 3: 0, 4: 0}
        resp = "respondent,task,choice\n" + "".join(f"r{r},{t},{(c + r) % 2}\n" for r in range(1, 7)
                                                     for t, c in picks.items())
        out = run_json(self.write("r.csv", resp), "--design", self.write("d.csv", design))
        self.assertFalse(out["none_option"])
        one_based = design.replace(",0,", ",2,")
        resp1 = "respondent,task,choice\n" + "".join(f"r{r},{t},{(c + r) % 2 or 2}\n" for r in range(1, 7)
                                                      for t, c in picks.items())
        ref = run_json(self.write("r1.csv", resp1), "--design", self.write("d1.csv", one_based))
        self.assertAlmostEqual(out["groups"][0]["fit"]["loglik"], ref["groups"][0]["fit"]["loglik"], places=9)

    def test_choice_zero_is_none_only_without_concept_zero(self):
        design = "version,task,concept,Color\n1,1,1,Red\n1,1,2,Blue\n1,1,none,\n1,2,1,Blue\n1,2,2,Red\n1,2,none,\n"
        resp = "respondent,task,choice\nr1,1,0\nr1,2,1\nr2,1,2\nr2,2,0\n"
        out = run_json(self.write("r.csv", resp), "--design", self.write("d.csv", design), "--counts-only")
        self.assertAlmostEqual(out["groups"][0]["none_chosen_share"], 0.5)

    def test_none_when_missing_row_offers_none_in_every_task(self):
        full = run_json(FIXTURES / "plan_responses.csv", *PLAN, "--counts-only")
        args = self.plan_with(lambda rows: [r for r in rows if r[2] != "none"])
        out = run_json(FIXTURES / "plan_responses.csv", *args, "--none-when-missing-row", "--counts-only")
        self.assertAlmostEqual(out["groups"][0]["none_chosen_share"], full["groups"][0]["none_chosen_share"])
        # Stacked: a task with no chosen row means none; the none option is added to every task.
        rows = "".join(f"{r},1,1,Red,{1 if r < 4 else 0}\n{r},1,2,Blue,0\n{r},2,1,Blue,1\n{r},2,2,Red,0\n"
                       for r in range(1, 6))
        out = run_json(self.write("s.csv", "respondent,task,concept,Color,chosen\n" + rows),
                       "--none-when-missing-row", "--counts-only")
        self.assertAlmostEqual(out["groups"][0]["none_chosen_share"], 0.2)

    def test_thousands_separators_in_prices(self):
        prices = ["$4,000", "$5,000", "$6,000", "$7,000"]
        rows = [["respondent", "task", "concept", "Brand", "Price", "chosen"]]
        for r in range(1, 41):
            for t in range(4):
                a, b = prices[t], prices[(t + 1 + r) % 4]
                if a == b:
                    b = prices[(t + 2) % 4]
                cheap = 1 if M.level_number(a) < M.level_number(b) else 2
                pick = cheap if r % 4 else 3 - cheap
                rows += [[f"r{r}", t, 1, "X" if r % 2 else "Y", a, int(pick == 1)],
                         [f"r{r}", t, 2, "Y" if r % 2 else "X", b, int(pick == 2)]]
        out = run_json(self.write_rows("p.csv", rows), "--price-attr", "Price", "--product",
                       "A: Brand=X; Price=$5,500", "--product", "B: Brand=Y; Price=6,500")
        self.assertEqual(out["linear"]["Price"], {"$4,000": 4000.0, "$5,000": 5000.0, "$6,000": 6000.0,
                                                  "$7,000": 7000.0})
        self.assertLess(coef(out, "Price (per unit)")["estimate"], 0)
        self.assertEqual(M.numbers_in("$1,299"), [1299.0])
        self.assertEqual(M.numbers_in("4,5"), [4.5])
        self.assertEqual(M.numbers_in("Plan-2"), [2.0])
        self.assertEqual(sorted(["$1,000", "$500", "$750"], key=M.natural_key), ["$500", "$750", "$1,000"])

    def test_level_with_two_numbers_refused_as_linear(self):
        rows = "".join(f"{r},1,1,100 GB ($20),1\n{r},1,2,200 GB ($30),0\n" for r in range(1, 4))
        proc = run(self.write("a.csv", "respondent,task,concept,Plan,chosen\n" + rows), "--price-attr", "Plan")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("2 numbers", proc.stderr)

    def test_price_origin_does_not_cause_false_separation(self):
        base = run_json(FIXTURES / "plan_responses.csv", *PLAN, "--price-attr", PRICE)

        def shift(text):
            for v in ("40", "50", "60", "70"):
                text = text.replace(f"${v}", f"${int(v) + 1000}")
            return text
        args = self.plan_with(lambda rows: [[shift(c) for c in r] for r in rows], shift)
        out = run_json(FIXTURES / "plan_responses.csv", *args, "--price-attr", PRICE)
        self.assertAlmostEqual(coef(out, "Price per week (per unit)")["estimate"],
                               coef(base, "Price per week (per unit)")["estimate"], places=6)
        self.assertAlmostEqual(out["groups"][0]["fit"]["loglik"], base["groups"][0]["fit"]["loglik"], places=6)

    def test_zero_price_effect_withholds_wtp_without_crash(self):
        profiles = [("a", "10"), ("a", "20"), ("b", "10"), ("b", "20")]
        rows = "".join(f"r{r},1,{k + 1},{p[0]},{p[1]},{int(k == r)}\n" for r in range(4)
                       for k, p in enumerate(profiles))
        out = run_json(self.write("a.csv", "respondent,task,concept,Brand,Price,chosen\n" + rows),
                       "--price-attr", "Price")
        g = out["groups"][0]
        self.assertFalse(any(k.startswith("wtp") for k in g["estimates"]))
        self.assertTrue(any("not clearly negative" in w for w in g["warnings"]))

    def test_wtp_interval_scales_with_price_units(self):
        base = run_json(FIXTURES / "plan_responses.csv", *PLAN, "--price-attr", PRICE)

        def scale(text):
            for v in ("40", "50", "60", "70"):
                text = text.replace(f"${v}", f"${int(v) * 10000:,}")
            return text
        args = self.plan_with(lambda rows: [[scale(c) for c in r] for r in rows], scale)
        out = run_json(FIXTURES / "plan_responses.csv", *args, "--price-attr", PRICE)
        a = base["groups"][0]["estimates"]["wtp | Brand | GreenPlate"]
        b = out["groups"][0]["estimates"]["wtp | Brand | GreenPlate"]
        self.assertAlmostEqual(b["value"] / a["value"], 10000.0, places=3)
        self.assertAlmostEqual(b["se"] / a["se"], 10000.0, delta=1.0)

    def test_segment_wald_is_clustered(self):
        # 20 people, one task each, then the same people repeating that task 20 times: the same evidence.
        def rows(repeat):
            out = ""
            for r in range(20):
                seg = "a" if r < 10 else "b"
                pick = 1 if (r % 10) < (7 if seg == "a" else 4) else 2
                for t in range(repeat):
                    out += (f"p{r},{t},1,Red,{int(pick == 1)},{seg}\np{r},{t},2,Blue,{int(pick == 2)},{seg}\n"
                            f"p{r},{t + 100},1,Blue,{int(pick == 2)},{seg}\np{r},{t + 100},2,Green,"
                            f"{int(pick == 1)},{seg}\n")
            return "respondent,task,concept,Color,chosen,seg\n" + out
        once = run_json(self.write("a.csv", rows(1)), "--segment", "seg")["segment_test"]
        many = run_json(self.write("b.csv", rows(20)), "--segment", "seg")["segment_test"]
        self.assertAlmostEqual(once["p_value"], many["p_value"], places=6)

    def test_segment_wald_two_groups_formula(self):
        g1 = {"label": "a", "_beta": [1.0, -0.5], "_cov": [[0.04, 0.01], [0.01, 0.09]]}
        g2 = {"label": "b", "_beta": [0.4, 0.1], "_cov": [[0.05, 0.0], [0.0, 0.02]]}
        t = M.segment_wald([g1, g2], 2)
        v = [[0.09, 0.01], [0.01, 0.11]]
        d = [0.6, -0.6]
        inv = M.invert(v)
        expect = sum(d[i] * inv[i][j] * d[j] for i in range(2) for j in range(2))
        self.assertAlmostEqual(t["statistic"], expect, places=10)
        self.assertEqual(t["df"], 2)

    def test_prohibited_product_refused(self):
        for price in ("$40", "40"):
            proc = run(FIXTURES / "plan_responses.csv", *PLAN, "--price-attr", PRICE, "--product",
                       f"A: Brand=FreshBox; Meals per week=4; Delivery=Weekly; Price per week={price}")
            self.assertEqual(proc.returncode, 2, price)
            self.assertIn("prohibited", proc.stderr)

    def test_spec_parsing_matches_conjoint_design(self):
        spec = self.write("s.txt", "Toppings: Salt and Pepper | Plain\nProhibited items: a | b\n"
                                   "Price: $1,200, $2,500\nprohibit: Toppings=Plain & Prohibited items=a\n")
        attrs, rules = M.load_spec(spec)
        self.assertEqual(attrs, [("Toppings", ["Salt and Pepper", "Plain"]), ("Prohibited items", ["a", "b"]),
                                 ("Price", ["$1,200", "$2,500"])])
        self.assertEqual(rules, [{"Toppings": "Plain", "Prohibited items": "a"}])

    def test_reserved_names_match_conjoint_design(self):
        self.assertEqual(M.RESERVED, {"version", "block", "task", "set", "concept", "alt", "alternative",
                                      "respondent", "respondent_id", "resp.id", "id", "responseid", "response_id",
                                      "rid", "chosen", "choice", "segment", "weight", "ques"})
        self.assertNotIn("0", M.NONE_LABELS)
        args = self.plan_with(lambda rows: [["ID" if c == "Delivery" else c for c in rows[0]]] + rows[1:],
                              lambda t: t.replace("Delivery:", "ID:"))
        out = run_json(FIXTURES / "plan_responses.csv", *args, "--counts-only")
        self.assertIn("ID", out["attributes"])
        rows = "".join(f"{r},1,1,Red,1kg,1\n{r},1,2,Blue,2kg,0\n{r},2,1,Blue,1kg,1\n{r},2,2,Red,2kg,0\n"
                       for r in range(1, 4))
        out = run_json(self.write("w.csv", "respondent,task,concept,Color,Weight,chosen\n" + rows), "--counts-only")
        self.assertTrue(any("Weight" in n and "reserved" in n for n in out["notes"]))

    def test_check_duplicate_none_and_short_tasks_in_design(self):
        resp = self.write("r.csv", "respondent,task,choice\nr1,1,1\n")
        bad = self.write("d.csv", "task,concept,Color\n1,1,Red\n1,2,Blue\n1,none,\n1,none,\n")
        proc = run(resp, "--design", bad)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("more than one none row", proc.stderr)
        short = self.write("e.csv", "task,concept,Color\n1,1,Red\n1,none,\n2,1,Blue\n2,2,Red\n")
        proc = run(resp, "--design", short)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("fewer than two concepts", proc.stderr)
        filled = self.write("f.csv", "task,concept,Color\n1,1,Red\n1,none,Blue\n")
        self.assertEqual(run(resp, "--design", filled).returncode, 2)

    def test_segment_marginal_means(self):
        text = (FIXTURES / "one_attribute_stacked.csv").read_text().splitlines()
        rows = [text[0] + ",grp"] + [line + ("," + ("odd" if int(line.split(",")[0][1:]) % 2 else "even"))
                                     for line in text[1:]]
        out = run_json(self.write("a.csv", "\n".join(rows) + "\n"), "--amce", "--segment", "grp")
        segs = out["amce"]["segments"]
        self.assertEqual(sorted(segs), ["even", "odd"])
        d = segs["odd"]["mm_differences"]["Color | Red"]
        self.assertAlmostEqual(d["difference"], segs["odd"]["marginal_means"]["Color | Red"]["mean"]
                               - segs["even"]["marginal_means"]["Color | Red"]["mean"], places=12)
        self.assertIsNotNone(d["se"])

    def test_amce_warns_when_concepts_never_share_a_level(self):
        # One attribute, every pair is Red vs Blue: Cramer's V cannot see this, the overlap check can.
        rows = "".join(f"{r},{t},1,{'Red' if t % 2 else 'Blue'},{int(r % 3 == 0)}\n"
                       f"{r},{t},2,{'Blue' if t % 2 else 'Red'},{int(r % 3 != 0)}\n" for r in range(1, 31)
                       for t in range(1, 5))
        out = run_json(self.write("a.csv", "respondent,task,concept,Color,chosen\n" + rows), "--amce")
        self.assertTrue(any("share a level less often" in w for w in out["amce"]["warnings"]))
        clean = run_json(FIXTURES / "one_attribute_stacked.csv", "--amce")
        self.assertFalse(clean["amce"]["warnings"])

    def test_integer_codes_as_price_get_a_check_note(self):
        rows = "".join(f"{r},1,1,a,1,{int(r % 3 > 0)}\n{r},1,2,b,3,{int(r % 3 == 0)}\n"
                       f"{r},2,1,b,2,{int(r % 4 > 0)}\n{r},2,2,a,4,{int(r % 4 == 0)}\n" for r in range(1, 13))
        out = run_json(self.write("a.csv", "respondent,task,concept,Brand,Price,chosen\n" + rows),
                       "--price-attr", "Price")
        self.assertTrue(any("level codes" in n for n in out["notes"]))

    def test_strict_json_and_ci_label(self):
        rows = "1,1,1,Red,1\n1,1,2,Blue,0\n1,2,1,Red,0\n1,2,2,Blue,1\n"
        proc = run(self.write("a.csv", "respondent,task,concept,Color,chosen\n" + rows), "--amce", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        json.loads(proc.stdout, parse_constant=lambda c: self.fail(f"non-JSON constant {c}"))
        text = run(FIXTURES / "candy_stacked.csv", "--ci", "90").stdout
        self.assertIn("90% CI", text)
        self.assertNotIn("95% CI", text)

    def test_misspelled_column_flag_is_an_error(self):
        proc = run(FIXTURES / "plan_responses.csv", *PLAN, "--version-col", "Vers")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("'Vers'", proc.stderr)

    def test_wide_task_columns_ignore_other_q_columns(self):
        rows = {}
        with open(FIXTURES / "plan_responses.csv", newline="") as handle:
            for r in csv.DictReader(handle):
                rows.setdefault((r["respondent"], r["version"]), {})[r["task"]] = r["choice"]
        table = [["respondent", "version", "Q1", "Q2"] + [f"task{t}" for t in range(1, 9)]]
        table += [[rid, v, "35", "yes"] + [ch[str(t)] for t in range(1, 9)] for (rid, v), ch in rows.items()]
        out = run_json(self.write_rows("w.csv", table), *PLAN, "--counts-only")
        self.assertEqual(out["counts"]["tasks_used"], 3200)

    def test_single_version_with_a_text_label(self):
        design = self.write("d.csv", "version,task,concept,Color\nA,1,1,Red\nA,1,2,Blue\nA,2,1,Blue\nA,2,2,Red\n")
        resp = self.write("r.csv", "respondent,task,choice\nr1,1,1\nr1,2,2\nr2,1,2\nr2,2,1\n")
        out = run_json(resp, "--design", design, "--counts-only")
        self.assertEqual(out["counts"]["tasks_used"], 4)

    def test_sawtooth_zero_coded_none_rows(self):
        rows = "".join(f"{r},1,1,Red,{int(r % 3 == 0)}\n{r},1,2,Blue,{int(r % 3 == 1)}\n{r},1,3,0,{int(r % 3 == 2)}\n"
                       for r in range(1, 10))
        out = run_json(self.write("a.csv", "respondent,task,concept,Color,chosen\n" + rows), "--counts-only")
        self.assertTrue(out["none_option"])
        self.assertEqual(out["attributes"]["Color"], ["Blue", "Red"])

    def test_bad_bytes_and_negative_skip_rows_exit_2(self):
        self.assertEqual(run(self.write("a.csv", b"\xef\xbb\xbfrespondent,task\n\xff\xfe\xfa,1\n")).returncode, 2)
        self.assertEqual(run(FIXTURES / "candy_stacked.csv", "--skip-rows", "-1").returncode, 2)

    def test_separation_message_names_the_failing_segment_levels(self):
        rows = ""
        for r in range(1, 9):
            seg = "x" if r <= 4 else "y"
            for t in range(1, 4):
                red_wins = seg == "x" or (r + t) % 2 == 0
                rows += f"{r},{t},1,Red,{int(red_wins)},{seg}\n{r},{t},2,Blue,{int(not red_wins)},{seg}\n"
        out = run_json(self.write("a.csv", "respondent,task,concept,Color,chosen,seg\n" + rows), "--segment", "seg")
        seg_x = next(g for g in out["groups"] if g["label"] == "seg = x")
        self.assertIn("Never chosen: Color=Blue", seg_x["error"])

    def test_simulator_product_named_none_refused(self):
        proc = run(FIXTURES / "plan_responses.csv", *PLAN, "--product",
                   "None: Brand=FreshBox; Meals per week=3; Delivery=Weekly; Price per week=$50")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
