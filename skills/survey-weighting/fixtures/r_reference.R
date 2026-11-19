# Independent reference values for the panel fixture (base R only). Run from fixtures/: Rscript r_reference.R
options(digits = 12)
d <- read.csv("panel.input.csv", stringsAsFactors = FALSE)
t <- read.csv("panel.targets.csv", stringsAsFactors = FALSE)
w <- rep(1, nrow(d))
for (it in 1:500) {
  for (v in unique(t$variable)) {
    tv <- t[t$variable == v, ]
    share <- tv$target / sum(tv$target)
    for (k in seq_len(nrow(tv))) {
      idx <- d[[v]] == tv$category[k]
      w[idx] <- w[idx] * share[k] * sum(w) / sum(w[idx])
    }
  }
}
w <- w * nrow(d) / sum(w)
cat("weights by first 5 rows:", w[1:5], "\n")
cat("min", min(w), "max", max(w), "\n")
cat("kish n_eff", sum(w)^2 / sum(w^2), "deff", nrow(d) * sum(w^2) / sum(w)^2, "\n")
cat("weighted share q1 Yes", sum(w[d$q1 == "Yes"]) / sum(w), "\n")
cat("quantiles (type 7)", quantile(w, c(0.05, 0.5, 0.95)), "\n")
# cell weights for gender x age_group to the joint shares implied by independence of the two margins
