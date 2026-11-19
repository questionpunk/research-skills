# Independent reference values for the fixtures (base R only). Run from fixtures/: Rscript r_reference.R
options(digits=12)
M <- as.table(rbind(c(762, 327, 468), c(484, 239, 477)))
r <- chisq.test(M); cat("agresti X2", r$statistic, "p", r$p.value, "\n")
r <- prop.test(c(189,104), c(11034,11037), correct=FALSE); cat("aspirin X2", r$statistic, "p", r$p.value, "\n")
p <- c(0.0001,0.0004,0.0019,0.0095,0.0201,0.0278,0.0298,0.0344,0.0459,0.3240,0.4262,0.5719,0.6528,0.7590,1.000)
cat("BH", p.adjust(p,"BH"), "\n"); cat("holm", p.adjust(p,"holm"), "\n")
d <- read.csv("basic.input.csv", stringsAsFactors=FALSE)
d$s <- as.integer(substr(d$satisfaction,1,1))
dd <- d[!is.na(d$s) & d$plan!="",]
tab <- table(dd$s, dd$plan); print(tab)
r <- chisq.test(tab); cat("basic X2", r$statistic, "df", r$parameter, "p", r$p.value, "\n")
ps <- c()
for (k in 1:5) { a <- sum(dd$s==k & dd$plan=="Free"); b <- sum(dd$s==k & dd$plan=="Pro")
  pt <- prop.test(c(a,b), c(sum(dd$plan=="Free"), sum(dd$plan=="Pro")), correct=FALSE); ps <- c(ps, pt$p.value)
  cat("cat",k,"Free",a/sum(dd$plan=="Free"),"Pro",b/sum(dd$plan=="Pro"),"p",pt$p.value,"\n") }
tt <- t.test(dd$s[dd$plan=="Free"], dd$s[dd$plan=="Pro"]); cat("welch p", tt$p.value, "means", tt$estimate, "\n")
cat("holm family", p.adjust(c(ps, tt$p.value), "holm"), "\n")
# weighted
for (pl in c("Free","Pro","Team")) { x <- dd[dd$plan==pl,]; W <- sum(x$weight); neff <- W^2/sum(x$weight^2)
  cat(pl, "W", W, "neff", neff, "pct5", sum(x$weight[x$s==5])/W, "wmean", sum(x$weight*x$s)/W, "\n") }
f <- dd[dd$plan=="Free",]; g <- dd[dd$plan=="Pro",]
n1 <- sum(f$weight)^2/sum(f$weight^2); n2 <- sum(g$weight)^2/sum(g$weight^2)
p1 <- sum(f$weight[f$s==5])/sum(f$weight); p2 <- sum(g$weight[g$s==5])/sum(g$weight)
pp <- (n1*p1+n2*p2)/(n1+n2); z <- (p1-p2)/sqrt(pp*(1-pp)*(1/n1+1/n2)); cat("weighted z cat5", z, "p", 2*pnorm(-abs(z)), "\n")
all <- d[!is.na(d$weight),]; cat("overall neff", sum(all$weight)^2/sum(all$weight^2), "\n")
