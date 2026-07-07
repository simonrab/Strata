#!/usr/bin/env Rscript
# Pool per-study effect points (yi, vi) with metafor and emit JSON on stdout.
# Usage: Rscript metafor_pool.R <csv_path>
#   csv columns: study_id,label,yi,vi
# Effect-size calculation happens upstream in Python (Cochrane formulas), so this
# script is measure-agnostic: it pools log risk/odds/hazard ratios identically.
# Output JSON is written with base R only (no jsonlite dependency).

suppressMessages(library(metafor))

args <- commandArgs(trailingOnly = TRUE)
csv_path <- args[1]

dat <- read.csv(csv_path, stringsAsFactors = FALSE, colClasses = c(
  study_id = "character", label = "character", yi = "numeric", vi = "numeric"
))

w <- rma(yi, vi, data = dat, method = "REML", test = "z")
k <- rma(yi, vi, data = dat, method = "REML", test = "knha")

wts <- as.numeric(weights(w))              # percent random-effects weights
kk <- w$k

# Prediction interval (metafor uses a t-distribution with k-2 df).
pred_lb <- "null"; pred_ub <- "null"
if (kk >= 5) {
  pr <- predict(w)
  pred_lb <- sprintf("%.10f", pr$pi.lb)
  pred_ub <- sprintf("%.10f", pr$pi.ub)
}

num <- function(x) sprintf("%.10f", as.numeric(x))
vecf <- function(v) paste(sprintf("%.10f", as.numeric(v)), collapse = ", ")
strv <- function(v) paste(sprintf('"%s"', v), collapse = ", ")

cat("{\n")
cat(sprintf('  "engine": "metafor",\n'))
cat(sprintf('  "k": %d,\n', kk))
cat(sprintf('  "est_log": %s,\n', num(w$beta)))
cat(sprintf('  "se_wald_log": %s,\n', num(w$se)))
cat(sprintf('  "se_hksj_log": %s,\n', num(k$se)))
cat(sprintf('  "wald_lb_log": %s,\n', num(w$ci.lb)))
cat(sprintf('  "wald_ub_log": %s,\n', num(w$ci.ub)))
cat(sprintf('  "hksj_lb_log": %s,\n', num(k$ci.lb)))
cat(sprintf('  "hksj_ub_log": %s,\n', num(k$ci.ub)))
cat(sprintf('  "tau2": %s,\n', num(w$tau2)))
cat(sprintf('  "i2": %s,\n', num(w$I2)))
cat(sprintf('  "q": %s,\n', num(w$QE)))
cat(sprintf('  "q_p": %s,\n', num(w$QEp)))
cat(sprintf('  "pred_lb_log": %s,\n', pred_lb))
cat(sprintf('  "pred_ub_log": %s,\n', pred_ub))
cat(sprintf('  "study_id": [%s],\n', strv(dat$study_id)))
cat(sprintf('  "label": [%s],\n', strv(dat$label)))
cat(sprintf('  "yi": [%s],\n', vecf(dat$yi)))
cat(sprintf('  "vi": [%s],\n', vecf(dat$vi)))
cat(sprintf('  "weight": [%s]\n', vecf(wts)))
cat("}\n")
