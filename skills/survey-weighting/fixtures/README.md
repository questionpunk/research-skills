# Fixtures for survey-weighting

Synthetic samples and one published example. No respondent data. Expected values come from the publication,
from a separate raking loop in base R (`r_reference.R`), or from hand arithmetic below.

## 1. `battaglia_2009.*`: Battaglia, Hoaglin and Frankel (2009), Exhibit 1

The exhibit prints the margins of each raking iteration but not the table of design weights behind them, so the
six design-weight totals (VARIABLE1 × VARIABLE2) were solved from the published numbers:

- m = iteration-1 VARIABLE1 margins: 15,915.87; 10,912.05; 18,022.90. f_i = control_i / m_i with controls
  22,154.39; 16,533.88; 24,112.03.
- g_j = control_j / (iteration-1 VARIABLE2 margin): 30,697.33 / 32,684.74 and 32,102.97 / 30,115.56.
- The iteration-2 VARIABLE1 margins R_i = f_i(g₁x_i1 + g₂(m_i − x_i1)) = 22,102.81; 16,442.32; 24,255.17 give
  x_i1 = (R_i/f_i − g₂m_i)/(g₁ − g₂) and x_i2 = m_i − x_i1:

| VARIABLE1 | VARIABLE2 = 1 | VARIABLE2 = 2 |
|---|---|---|
| 1 | 8,575.735984 | 7,340.134016 |
| 2 | 6,155.799886 | 4,756.250114 |
| 3 | 8,536.312847 | 9,486.587153 |

Consistency check not used in the solve: Σ f_i x_i1 = 32,684.74, the published iteration-1 VARIABLE2 margin.
Each cell is one row of `battaglia_2009.input.csv` with its total as `design_weight`.

Expected (published, not used in the solve): iteration-2 VARIABLE2 margins **30,708.98; 32,091.32**; iteration-3
VARIABLE1 **22,154.09; 16,533.34; 24,112.87**; VARIABLE2 **30,697.40; 32,102.90**; stop at the macro's
iteration 3 with tolerance 1.

## 2. `panel.*`: three-variable raking

200 synthetic respondents: gender (135 F, 65 M), age group (45, 70, 85), region (66, 67, 67), and a yes/no `q1`
drawn with a fixed seed. Targets: gender 51/49, age 30/33/37, region 35/40/25 (percents).

From `r_reference.R` (base R, 500 passes, scaled to mean 1): min weight **0.504806**, max **2.374795**, Kish
n_eff **166.61967**, deff **1.2003385**, weighted share of q1 = Yes **0.4759512** (unweighted 83/200 = 0.415),
weight quantiles (type 7) 5% 0.504806, median **0.817101**, 95% **1.667435**.

## 3. `cells.*`: cell weighting by hand

16 respondents in four gender × age cells (4, 6, 2, 4); targets 20/30/25/25%.
Weights = target share × 16 / cell count: F young 0.2 × 16/4 = **0.8**; F old 0.3 × 16/6 = **0.8**;
M young 0.25 × 16/2 = **2.0**; M old 0.25 × 16/4 = **1.0**.
Σw² = 10 × 0.64 + 2 × 4 + 4 × 1 = 18.4, so n_eff = 16²/18.4 = **13.913**.
q1 = Yes: 2 in F young, 2 in F old, 1 in M young, 1 in M old → (1.6 + 1.6 + 2.0 + 1.0)/16 = **0.3875**.

## 4. Property cases (built in the tests)

- A 2×2 sample (30, 10, 20, 40) raked to 70/30 and 45/55 keeps its odds ratio 30·40/(10·20) = 6.
- Two variables that coincide in the sample (all women young) with conflicting targets must not converge.
