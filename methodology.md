---
title: "Mathematical Methodology & Survey Variance Design — Philippine LFS 2025"
description: "Exact point estimators, 117-domain PSU reconstruction, two-stage finite population corrections, and Taylor series linearization formulas for the 2025 Philippine Labor Force Survey."
permalink: /methods.html
---

# Mathematical Methodology & Survey Variance Design

[$\leftarrow$ Back to Main Report](index.html)

This page documents the exact estimators, domain-reconstruction rules, and two-stage Taylor series linearization formulas implemented in [`tables.py`](https://github.com/KingSSIBAL/LFS-2025-Analysis/blob/main/tables.py) and [`lfs_view.sql`](https://github.com/KingSSIBAL/LFS-2025-Analysis/blob/main/lfs_view.sql) for the 2025 Philippine Labor Force Survey (LFS) Public Use Files (PUF). All formulas follow the Philippine Statistics Authority (PSA) *Technical Notes on the Labor Force Survey* (pp. 1–9).

<nav aria-label="Methodology Contents">
<strong>Contents</strong>
<ol>
  <li><a href="#estimators">Core point estimators (counts, rates, and shares)</a></li>
  <li><a href="#aggregation">Multi-round aggregation (annual &amp; quarterly averages)</a></li>
  <li><a href="#design">Reconstructing the 117 Master Sample domains &amp; PSUs</a></li>
  <li><a href="#variance">Two-stage stratified cluster variance (totals)</a></li>
  <li><a href="#taylor">Taylor series linearization for ratio standard errors</a></li>
  <li><a href="#reliability">Reliability bands (CV) &amp; confidence interval overlap</a></li>
  <li><a href="#example">Worked numerical walkthrough (SOCCSKSARGEN vs. National)</a></li>
</ol>
</nav>

## 1. Core Point Estimators (Counts, Rates, and Shares) {#estimators}

Let $S_m$ denote the sample of respondents in survey month $m \in \{1, \dots, 12\}$ who are aged $15$ and over, employed ($\texttt{PUFNEWEMPSTAT}_i = 1$), and have a valid industry code ($\texttt{PUFC16\_PKB}_i \neq \text{null}$). Each respondent $i$ carries a final calibrated person weight $w_i = \texttt{PUFPWGTPRV}_i$ reflecting base selection probabilities, non-response adjustments, and post-stratification to projected age-sex population totals.

### Weighted Domain Totals

For any demographic, sectoral, or regional subgroup $d \subseteq S_m$, the monthly weighted totals for **employed** ($\hat{X}_{m,d}$) and **underemployed** ($\hat{Y}_{m,d}$) persons are:

$$
\hat{X}_{m,d} = \sum_{i \in d} w_i
$$

$$
\hat{Y}_{m,d} = \sum_{i \in d} w_i \, \mathbb{I}(\texttt{PUFC20\_PWMORE}_i = 1)
$$

where $\mathbb{I}(\cdot)$ is the indicator function equal to $1$ if the respondent wants more hours of work in their present job or an additional job, and $0$ otherwise.

Underemployed workers are partitioned into **visibly underemployed** (worked less than $40$ hours during the reference week, including those "with a job, not at work" where $\texttt{PUFC19\_PHOURS}_i$ is null or $0$) and **invisibly underemployed** (worked $40$ hours or more):

$$
\hat{Y}_{m,d}^{\text{vis}} = \sum_{i \in d} w_i \, \mathbb{I}\!\left(\texttt{pwmore}_i = 1 \land (\texttt{phours}_i \text{ is null} \lor \texttt{phours}_i < 40)\right)
$$

$$
\hat{Y}_{m,d}^{\text{inv}} = \sum_{i \in d} w_i \, \mathbb{I}\!\left(\texttt{pwmore}_i = 1 \land \texttt{phours}_i \ge 40\right)
$$

such that $\hat{Y}_{m,d} = \hat{Y}_{m,d}^{\text{vis}} + \hat{Y}_{m,d}^{\text{inv}}$. Published headcount tables divide these totals by $10^3$ to report figures in thousands.

### Disambiguating the Four Percentage Metrics

Because headcount concentration and individual vulnerability move in opposite directions across sectors, the tables and figures distinguish four ratios:

| Metric Name | Column Name in CSVs | Mathematical Definition | Interpretation |
|---|---|---|---|
| **1. Within-Group Underemployment Rate** | `underemp_rate_pct` | $\hat{R}_{m,d} = \frac{\hat{Y}_{m,d}}{\hat{X}_{m,d}} \times 100$ | Share of *employed workers in group* $d$ who want more hours (vulnerability/incidence rate). |
| **2. Within-Group Visible / Invisible Rates** | `visible_rate_pct`, `invisible_rate_pct` | $\hat{R}_{m,d}^{\text{vis}} = \frac{\hat{Y}_{m,d}^{\text{vis}}}{\hat{X}_{m,d}} \times 100$, $\hat{R}_{m,d}^{\text{inv}} = \frac{\hat{Y}_{m,d}^{\text{inv}}}{\hat{X}_{m,d}} \times 100$ | Additive components of the group rate ($\hat{R}_{m,d} = \hat{R}_{m,d}^{\text{vis}} + \hat{R}_{m,d}^{\text{inv}}$), plotted in Figure 1B. |
| **3. Visible / Invisible Share of Underemployed** | `visible_share_within_group_pct` | $\hat{S}_{m,d}^{\text{vis}} = \frac{\hat{Y}_{m,d}^{\text{vis}}}{\hat{Y}_{m,d}} \times 100$, $\hat{S}_{m,d}^{\text{inv}} = \frac{\hat{Y}_{m,d}^{\text{inv}}}{\hat{Y}_{m,d}} \times 100$ | Share of *underemployed workers in group* $d$ working $<40$ hrs vs. $\ge 40$ hrs ($\hat{S}_{m,d}^{\text{vis}} + \hat{S}_{m,d}^{\text{inv}} = 100\%$). |
| **4. Share of National / Sector Pool** | `share_of_national_underemp_pct` | $\hat{P}_{m,d}^{\text{nat}} = \frac{\hat{Y}_{m,d}}{\sum_{d'} \hat{Y}_{m,d'}} \times 100$ | Group $d$'s share of the entire national underemployed pool ($5.8\text{M}$). |

## 2. Multi-Round Aggregation (Annual & Quarterly Averages) {#aggregation}

Let $\mathcal{M}$ be the set of survey months pooled for an estimate, with cardinality $K = \vert\mathcal{M}\vert$:

* **National and Workplace-Region (`W*`) Annual Tables:** $\mathcal{M} = \{1, 2, \dots, 12\}$, $K = 12$.
* **Residence-Region (`R*`) Quarterly Tables:** $\mathcal{M} = \{1, 4, 7, 10\}$ (January, April, July, October), $K = 4$, as only the quarterly LFS rounds deploy the full $4$-replicate sample designed for regional estimates.

The multi-round average monthly headcount (in thousands) is the arithmetic mean across the $K$ rounds:

$$
\bar{X}_d = \frac{1}{K} \sum_{m \in \mathcal{M}} \frac{\hat{X}_{m,d}}{10^3}, \qquad \bar{Y}_d = \frac{1}{K} \sum_{m \in \mathcal{M}} \frac{\hat{Y}_{m,d}}{10^3}
$$

The annual or quarterly underemployment rate is the ratio of the multi-round average totals:

$$
\bar{R}_d = \frac{\sum_{m \in \mathcal{M}} \hat{Y}_{m,d}}{\sum_{m \in \mathcal{M}} \hat{X}_{m,d}} \times 100 = \frac{\bar{Y}_d}{\bar{X}_d} \times 100
$$

## 3. Reconstructing the 117 Master Sample Domains & PSUs {#design}

The PSA 2023 Geo-enabled Master Sample partitions the Philippines into $117$ sampling domains treated as explicit design strata ($81$ provinces, $33$ Highly Urbanized Cities, and $3$ other urban areas). Because the anonymized PUF omits explicit residence-province codes and reuses PSU numbers across provinces, [`lfs_view.sql`](https://github.com/KingSSIBAL/LFS-2025-Analysis/blob/main/lfs_view.sql) reconstructs the two-stage design in four steps:

1. **Contiguous PSU Identification (`hh_psu`):** Within each month $m$, households are ordered by their sequential household number ($\texttt{PUFHHNUM}$), which follows the geographic ordering of the Master Sample frame. A new Primary Sampling Unit (PSU) cluster $a$ begins whenever the replicate code ($\texttt{PUFRPL}$) or PSU code ($\texttt{PUFPSU}$) changes between consecutive households.
2. **Neighbor-PSU Stratum Assignment (`psu_frame`):** Each household is assigned the modal province/HUC of work ($\texttt{PUFC12A\_PROVMUN}$) of its employed members, and each PSU takes the modal domain $s_{m,a}$ of its households. Because $\texttt{PUFHHNUM}$ is sorted geographically by residence domain, any PSU whose workplace-mode domain differs from two agreeing adjacent neighbors ($s_{m,a-1} = s_{m,a+1} \neq s_{m,a}$) represents cross-border commuters ($248$ PSUs across 2025) and is reassigned to the residence stratum $p = s_{m,a-1}$.
3. **Second-Stage Finite Population Correction ($1 - f_{2,p,a}$):** Let $b_{p,a}$ be the number of sampled households in PSU $a$ of stratum $p$. Following PSA Technical Notes (p. 3), where each PSU contains approximately $100$ to $400$ households, the frame size of each PSU is approximated by the midpoint $B_{p,a} = \max(b_{p,a}, 250)$, giving the second-stage FPC factor:

$$
1 - f_{2,p,a} = 1 - \frac{b_{p,a}}{\max(b_{p,a}, 250)}
$$

4. **First-Stage Sampling Fraction ($f_{1,p}$):** Let $a_p$ be the number of sampled PSUs in stratum $p$, and let $\hat{H}_{p,a} = \sum_{h=1}^{b_{p,a}} w_{p,a,h}$ be the weighted household count of PSU $a$. The total number of frame PSUs in stratum $p$ is estimated as $\hat{A}_p = \max\!\left(a_p, \frac{1}{250}\sum_{a=1}^{a_p} \hat{H}_{p,a}\right)$, yielding the first-stage sampling fraction:

$$
f_{1,p} = \frac{a_p}{\hat{A}_p}, \qquad 1 - f_{1,p} = 1 - \frac{a_p}{\hat{A}_p}
$$

## 4. Two-Stage Stratified Cluster Variance (Totals) {#variance}

For any target subgroup $d$ in month $m$, let $y_{p,a,h} = \sum_{i \in (p,a,h) \cap d} w_i \, \mathbb{I}(\texttt{pwmore}_i = 1)$ be the weighted underemployed total in household $h$, PSU $a$, and stratum $p$, and let $x_{p,a,h} = \sum_{i \in (p,a,h) \cap d} w_i$ be the corresponding household employed total.

Define the PSU-level sums and cross-products across the $b_{p,a}$ households in PSU $(p,a)$:

$$
z_{y,p,a} = \sum_{h=1}^{b_{p,a}} y_{p,a,h}, \qquad q_{yy,p,a} = \sum_{h=1}^{b_{p,a}} y_{p,a,h}^2
$$

$$
z_{x,p,a} = \sum_{h=1}^{b_{p,a}} x_{p,a,h}, \qquad q_{xx,p,a} = \sum_{h=1}^{b_{p,a}} x_{p,a,h}^2, \qquad q_{xy,p,a} = \sum_{h=1}^{b_{p,a}} x_{p,a,h} \, y_{p,a,h}
$$

Following the two-stage variance decomposition in the PSA Technical Notes (p. 8a), the **within-PSU (second-stage) variance** summed across PSUs in stratum $p$ is:

$$
V_{w,p}(y) = \sum_{a=1}^{a_p} \mathbb{I}(b_{p,a} > 1) \left(1 - \frac{b_{p,a}}{\max(b_{p,a}, 250)}\right) \frac{b_{p,a}}{b_{p,a} - 1} \left( q_{yy,p,a} - \frac{z_{y,p,a}^2}{b_{p,a}} \right)
$$

The **between-PSU (first-stage) variance** in stratum $p$ is:

$$
V_{b,p}(y) = \mathbb{I}(a_p > 1) (1 - f_{1,p}) \frac{a_p}{a_p - 1} \left( \sum_{a=1}^{a_p} z_{y,p,a}^2 - \frac{\left(\sum_{a=1}^{a_p} z_{y,p,a}\right)^2}{a_p} \right)
$$

Summing across all $117$ strata combines the first- and second-stage variance components:

$$
V(\hat{Y}_{m,d}) = \sum_{p=1}^{117} \Big( V_{b,p}(y) + f_{1,p} \, V_{w,p}(y) \Big)
$$

Identical expressions yield the denominator variance $V(\hat{X}_{m,d})$ (replacing $q_{yy}, z_y^2$ with $q_{xx}, z_x^2$) and the bilinear covariance $\text{Cov}(\hat{X}_{m,d}, \hat{Y}_{m,d})$ (replacing $q_{yy}$ with $q_{xy}$ and $z_{y,p,a}^2$ with $z_{x,p,a} z_{y,p,a}$).

## 5. Taylor Series Linearization for Ratio Standard Errors {#taylor}

Because the underemployment rate $\hat{R}_{d} = \hat{Y}_{d} / \hat{X}_{d}$ is a ratio of two random survey totals, its variance is approximated via first-order Taylor series linearization around the population expectations (PSA Technical Notes, p. 8b):

$$
V(\hat{R}_d) \approx \frac{1}{\hat{X}_d^2} \Big( V(\hat{Y}_d) + r_d^2 \, V(\hat{X}_d) - 2 r_d \, \text{Cov}(\hat{Y}_d, \hat{X}_d) \Big)
$$

where $r_d = \hat{R}_d / 100 \in [0, 1]$ is the rate expressed as a proportion.

For multi-round averages across $K$ rounds ($K = 12$ annual or $K = 4$ quarterly), where rounds are treated as independent cross-sections in the absence of panel household identifiers across PUF files, the variance sums across months and scales by $1/K^2$:

$$
\text{SE}(\bar{Y}_d) = \frac{\sqrt{\max\!\left(0,\, \sum_{m \in \mathcal{M}} V(\hat{Y}_{m,d})\right)}}{K \times 10^3} \quad \text{(in thousands)}
$$

$$
\text{SE}(\bar{R}_d) = \frac{\sqrt{\max\!\left(0,\, \sum_{m \in \mathcal{M}} V(\hat{Y}_{m,d}) + r_d^2 \sum_{m \in \mathcal{M}} V(\hat{X}_{m,d}) - 2 r_d \sum_{m \in \mathcal{M}} \text{Cov}(\hat{Y}_{m,d}, \hat{X}_{m,d})\right)}}{\sum_{m \in \mathcal{M}} \hat{X}_{m,d}} \times 100 \quad \text{(in percentage points)}
$$

## 6. Reliability Bands (CV) & Confidence Interval Overlap {#reliability}

### Coefficient of Variation (CV)

The relative sampling precision of every headcount estimate is measured by its Coefficient of Variation:

$$
\text{CV}(\bar{Y}_d) = \frac{\text{SE}(\bar{Y}_d)}{\bar{Y}_d} \times 100\%
$$

Following the reliability thresholds used in PSA/NSCB small-area statistics, every table row and chart bar is classified into three bands:

* **Reliable ($\text{CV} \le 10\%$):** Solid bar, no flag.
* **Use with caution ($10\% < \text{CV} \le 20\%$):** Single-hatched bar (`//`) and single asterisk (`*`).
* **Unreliable ($\text{CV} > 20\%$):** Triple-hatched translucent bar (`///`) and double asterisk (`**`).

### Why Slightly Overlapping $95\%$ Confidence Intervals Can Still Differ at $\alpha = 0.05$

In Figure 8 (regional underemployment rates), each region $i$ is plotted with a $95\%$ confidence interval whisker:

$$
\text{CI}_{95\%, i} = \bar{R}_i \pm 1.96 \, \text{SE}(\bar{R}_i)
$$

When comparing two independent regional estimates $\bar{R}_1$ and $\bar{R}_2$ with similar standard errors ($\text{SE}_1 \approx \text{SE}_2 = s$), the standard error of their difference is $\text{SE}(\bar{R}_1 - \bar{R}_2) = \sqrt{s^2 + s^2} = \sqrt{2}\,s$.

* A two-sided test at the $\alpha = 0.05$ significance level rejects equality when:

$$
\vert\bar{R}_1 - \bar{R}_2\vert > 1.96 \sqrt{2}\,s \approx 2.77s
$$

* By contrast, requiring the two $95\%$ confidence intervals **not to overlap at all** requires the distance between point estimates to exceed the sum of both half-intervals:

$$
\vert\bar{R}_1 - \bar{R}_2\vert > 1.96s + 1.96s = 3.92s \implies Z = \frac{3.92s}{\sqrt{2}\,s} \approx 2.77 \implies p \approx 0.0056
$$

Consequently, non-overlapping $95\%$ whiskers provide a conservative visual guarantee of statistical difference ($p \approx 0.006$), while two intervals that overlap by less than $\frac{3.92 - 2.77}{3.92} \approx 29\%$ of a single whisker arm remain statistically distinct at the pairwise $5\%$ level.

## 7. Worked Numerical Walkthrough {#example}

To see how the SQL and Python pipeline transforms raw household weights into a published row with standard errors and reliability flags, consider two contrasting cells from the 2025 tables:

1. **National Annual Headline (`RQ1` / `1A_Sector_Annual` sum, $K = 12$ months):**
   * **Point Estimates:** Across the $12$ monthly rounds, the average weighted employed count is $\bar{X} = 49,000\text{k}$ ($49.0\text{M}$) and the average underemployed count is $\bar{Y} = 5,830\text{k}$ ($5.8\text{M}$).
   * **Headline Rate:**
     $$\bar{R} = \frac{5,830\text{k}}{49,000\text{k}} \times 100 = 11.9\%$$
   * **Precision:** With all $12$ rounds pooled across $117$ strata, the relative standard error is well below $\text{CV} = 1.5\% \le 10\%$, so the estimate is flagged `reliable (CV<=10%)`.

2. **Post-Secondary Undergraduates (`RQ1_RQ2_c_Education`, $K = 12$ months):**
   * **Why it is flagged `**`:** Because post-secondary non-tertiary undergraduates represent a tiny fraction of the Philippine workforce, many PSU clusters contain zero or one respondent in this cell.
   * **CV Calculation:** The two-stage variance formula yields a standard error $\text{SE}(\bar{Y}_d)$ equal to $22.7\%$ of the point estimate $\bar{Y}_d$:
     $$\text{CV}(\bar{Y}_d) = \frac{\text{SE}(\bar{Y}_d)}{\bar{Y}_d} \times 100 = 22.7\% > 20\%$$
   * **Visual & Table Encoding:** Because $\text{CV} > 20\%$, `tables.py` labels the row `unreliable (CV>20%)` and `figures.py` renders the bar with triple hatching (`///`), $45\%$ opacity, and a `**` suffix.

[$\leftarrow$ Back to Main Report](index.html)

<script>
  window.MathJax = {
    tex: { inlineMath: [['$', '$'], ['\\(', '\\)']], displayMath: [['$$', '$$'], ['\\[', '\\]']] }
  };
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>