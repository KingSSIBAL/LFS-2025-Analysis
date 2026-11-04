---
layout: default
title: "Mathematical Methodology & Survey Variance Design — Philippine LFS 2025"
description: "Exact point estimators, 117-domain PSU reconstruction, two-stage finite population corrections, Taylor series linearization, and Small Area Estimation remedies for the 2025 Philippine Labor Force Survey."
---

# Mathematical Methodology & Survey Variance Design

[$\leftarrow$ Back to Main Report](index.html)

This page documents the exact estimators, domain-reconstruction rules, two-stage Taylor series linearization formulas, and small-domain variance reduction methods implemented in [`tables.py`](https://github.com/KingSSIBAL/LFS-2025-Analysis/blob/main/tables.py) and [`lfs_view.sql`](https://github.com/KingSSIBAL/LFS-2025-Analysis/blob/main/lfs_view.sql) for the 2025 Philippine Labor Force Survey (LFS) Public Use Files (PUF). All formulas follow the Philippine Statistics Authority (PSA) *Technical Notes on the Labor Force Survey* (pp. 1–9).

<nav aria-label="Methodology Contents">
<strong>Contents</strong>
<ol>
  <li><a href="#estimators">Core point estimators (counts, rates, and shares)</a></li>
  <li><a href="#aggregation">Multi-round aggregation (annual &amp; quarterly averages)</a></li>
  <li><a href="#design">Reconstructing the 117 Master Sample domains &amp; PSUs</a></li>
  <li><a href="#variance">Two-stage stratified cluster variance (totals)</a></li>
  <li><a href="#taylor">Taylor series linearization for ratio standard errors</a></li>
  <li><a href="#reliability">Reliability bands (CV), small-cell algebra &amp; CI overlap</a></li>
  <li><a href="#remedies">Statistical remedies for high-CV ("unreliable") small domains</a></li>
  <li><a href="#example">Worked numerical walkthrough</a></li>
</ol>
</nav>

## 1. Core Point Estimators (Counts, Rates, and Shares) {#estimators}

Let <span>$S_m$</span> denote the sample of respondents in survey month <span>$m \in \{1, \dots, 12\}$</span> who are aged $15$ and over, employed (<span>$\texttt{PUFNEWEMPSTAT}_i = 1$</span>), and have a valid industry code (<span>$\texttt{PUFC16\_PKB}_i \neq \text{null}$</span>). Each respondent $i$ carries a final calibrated person weight <span>$w_i = \texttt{PUFPWGTPRV}_i$</span> reflecting base selection probabilities, non-response adjustments, and post-stratification to projected age-sex population totals.

### Weighted Domain Totals

For any demographic, sectoral, or regional subgroup <span>$d \subseteq S_m$</span>, the monthly weighted totals for **employed** (<span>$\hat{X}_{m,d}$</span>) and **underemployed** (<span>$\hat{Y}_{m,d}$</span>) persons are:

$$
\hat{X}_{m,d} = \sum_{i \in d} w_i
$$

$$
\hat{Y}_{m,d} = \sum_{i \in d} w_i \, \mathbb{I}(\texttt{PUFC20\_PWMORE}_i = 1)
$$

where $\mathbb{I}(\cdot)$ is the indicator function equal to $1$ if the respondent wants more hours of work in their present job or an additional job, and $0$ otherwise.

Underemployed workers are partitioned into **visibly underemployed** (worked less than $40$ hours during the reference week, including those "with a job, not at work" where <span>$\texttt{PUFC19\_PHOURS}_i$</span> is null or $0$) and **invisibly underemployed** (worked $40$ hours or more):

$$
\hat{Y}_{m,d}^{\text{vis}} = \sum_{i \in d} w_i \, \mathbb{I}\!\left(\texttt{pwmore}_i = 1 \land (\texttt{phours}_i \text{ is null} \lor \texttt{phours}_i < 40)\right)
$$

$$
\hat{Y}_{m,d}^{\text{inv}} = \sum_{i \in d} w_i \, \mathbb{I}\!\left(\texttt{pwmore}_i = 1 \land \texttt{phours}_i \ge 40\right)
$$

such that:

$$
\hat{Y}_{m,d} = \hat{Y}_{m,d}^{\text{vis}} + \hat{Y}_{m,d}^{\text{inv}}
$$

Published headcount tables divide these totals by $10^3$ to report figures in thousands.

### Disambiguating the Four Percentage Metrics

Because headcount concentration and individual vulnerability move in opposite directions across sectors, the tables and figures distinguish four ratios:

| Metric Name | Column Name in CSVs | Mathematical Definition | Interpretation |
|---|---|---|---|
| **1. Within-Group Underemployment Rate** | `underemp_rate_pct` | <span>$\hat{R}_{m,d} = \frac{\hat{Y}_{m,d}}{\hat{X}_{m,d}} \times 100$</span> | Share of *employed workers in group* $d$ who want more hours (vulnerability/incidence rate). |
| **2. Within-Group Visible / Invisible Rates** | `visible_rate_pct`, `invisible_rate_pct` | <span>$\hat{R}_{m,d}^{\text{vis}} = \frac{\hat{Y}_{m,d}^{\text{vis}}}{\hat{X}_{m,d}} \times 100$</span>, <span>$\hat{R}_{m,d}^{\text{inv}} = \frac{\hat{Y}_{m,d}^{\text{inv}}}{\hat{X}_{m,d}} \times 100$</span> | Additive components of the group rate (<span>$\hat{R}_{m,d} = \hat{R}_{m,d}^{\text{vis}} + \hat{R}_{m,d}^{\text{inv}}$</span>), plotted in Figure 1B. |
| **3. Visible / Invisible Share of Underemployed** | `visible_share_within_group_pct` | <span>$\hat{S}_{m,d}^{\text{vis}} = \frac{\hat{Y}_{m,d}^{\text{vis}}}{\hat{Y}_{m,d}} \times 100$</span>, <span>$\hat{S}_{m,d}^{\text{inv}} = \frac{\hat{Y}_{m,d}^{\text{inv}}}{\hat{Y}_{m,d}} \times 100$</span> | Share of *underemployed workers in group* $d$ working $<40$ hrs vs. $\ge 40$ hrs (<span>$\hat{S}_{m,d}^{\text{vis}} + \hat{S}_{m,d}^{\text{inv}} = 100\%$</span>). |
| **4. Share of National / Sector Pool** | `share_of_national_underemp_pct` | <span>$\hat{P}_{m,d}^{\text{nat}} = \frac{\hat{Y}_{m,d}}{\sum_{d'} \hat{Y}_{m,d'}} \times 100$</span> | Group $d$'s share of the entire national underemployed pool ($5.8\text{M}$). |

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
2. **Neighbor-PSU Stratum Assignment (`psu_frame`):** Each household is assigned the modal province/HUC of work (<span>$\texttt{PUFC12A\_PROVMUN}$</span>) of its employed members, and each PSU takes the modal domain <span>$s_{m,a}$</span> of its households. Because $\texttt{PUFHHNUM}$ is sorted geographically by residence domain, any PSU whose workplace-mode domain differs from two agreeing adjacent neighbors (<span>$s_{m,a-1} = s_{m,a+1} \neq s_{m,a}$</span>) represents cross-border commuters ($248$ PSUs across 2025) and is reassigned to the residence stratum <span>$p = s_{m,a-1}$</span>.
3. **Second-Stage Finite Population Correction (<span>$1 - f_{2,p,a}$</span>):** Let <span>$b_{p,a}$</span> be the number of sampled households in PSU $a$ of stratum $p$. Following PSA Technical Notes (p. 3), where each PSU contains approximately $100$ to $400$ households, the frame size of each PSU is approximated by the midpoint <span>$B_{p,a} = \max(b_{p,a}, 250)$</span>, giving the second-stage FPC factor:

$$
1 - f_{2,p,a} = 1 - \frac{b_{p,a}}{\max(b_{p,a}, 250)}
$$

4. **First-Stage Sampling Fraction (<span>$f_{1,p}$</span>):** Let <span>$a_p$</span> be the number of sampled PSUs in stratum $p$, and let <span>$\hat{H}_{p,a} = \sum_{h=1}^{b_{p,a}} w_{p,a,h}$</span> be the weighted household count of PSU $a$. The total number of frame PSUs in stratum $p$ is estimated as <span>$\hat{A}_p = \max\!\left(a_p, \frac{1}{250}\sum_{a=1}^{a_p} \hat{H}_{p,a}\right)$</span>, yielding the first-stage sampling fraction:

$$
f_{1,p} = \frac{a_p}{\hat{A}_p}, \qquad 1 - f_{1,p} = 1 - \frac{a_p}{\hat{A}_p}
$$

## 4. Two-Stage Stratified Cluster Variance (Totals) {#variance}

For any target subgroup $d$ in month $m$, let <span>$y_{p,a,h}$</span> be the weighted underemployed total in household $h$, PSU $a$, and stratum $p$, and let <span>$x_{p,a,h}$</span> be the corresponding household employed total:

$$
y_{p,a,h} = \sum_{i \in (p,a,h) \cap d} w_i \, \mathbb{I}(\texttt{pwmore}_i = 1), \qquad x_{p,a,h} = \sum_{i \in (p,a,h) \cap d} w_i
$$

Define the PSU-level sums and cross-products across the <span>$b_{p,a}$</span> households in PSU $(p,a)$:

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

Identical expressions yield the denominator variance <span>$V(\hat{X}_{m,d})$</span> and the bilinear covariance <span>$\text{Cov}(\hat{X}_{m,d}, \hat{Y}_{m,d})$</span>.

## 5. Taylor Series Linearization for Ratio Standard Errors {#taylor}

Because the underemployment rate <span>$\hat{R}_{d} = \hat{Y}_{d} / \hat{X}_{d}$</span> is a ratio of two random survey totals, its variance is approximated via first-order Taylor series linearization around the population expectations (PSA Technical Notes, p. 8b):

$$
V(\hat{R}_d) \approx \frac{1}{\hat{X}_d^2} \Big( V(\hat{Y}_d) + r_d^2 \, V(\hat{X}_d) - 2 r_d \, \text{Cov}(\hat{Y}_d, \hat{X}_d) \Big)
$$

where <span>$r_d = \hat{R}_d / 100 \in [0, 1]$</span> is the rate expressed as a proportion.

For multi-round averages across $K$ rounds ($K = 12$ annual or $K = 4$ quarterly), where rounds are treated as independent cross-sections in the absence of panel household identifiers across PUF files, the variance sums across months and scales by $1/K^2$:

$$
\text{SE}(\bar{Y}_d) = \frac{\sqrt{\max\!\left(0,\, \sum_{m \in \mathcal{M}} V(\hat{Y}_{m,d})\right)}}{K \times 10^3} \quad \text{(in thousands)}
$$

$$
\text{SE}(\bar{R}_d) = \frac{\sqrt{\max\!\left(0,\, \sum_{m \in \mathcal{M}} V(\hat{Y}_{m,d}) + r_d^2 \sum_{m \in \mathcal{M}} V(\hat{X}_{m,d}) - 2 r_d \sum_{m \in \mathcal{M}} \text{Cov}(\hat{Y}_{m,d}, \hat{X}_{m,d})\right)}}{\sum_{m \in \mathcal{M}} \hat{X}_{m,d}} \times 100 \quad \text{(in percentage points)}
$$

*(Note on rotational panel covariance: If longitudinal household panel identifiers were available across rounds, the true variance of the $K$-round mean would include positive serial covariance terms $2 \sum_{m < m'} \text{Cov}(\hat{Y}_{m,d}, \hat{Y}_{m',d})$.)*

## 6. Reliability Bands (CV), Small-Cell Algebra & Confidence Interval Overlap {#reliability}

### Coefficient of Variation (CV)

The relative sampling precision of every headcount estimate is measured by its Coefficient of Variation:

$$
\text{CV}(\bar{Y}_d) = \frac{\text{SE}(\bar{Y}_d)}{\bar{Y}_d} \times 100\%
$$

Following the reliability thresholds used in PSA/NSCB small-area statistics, every table row and chart bar is classified into three bands:

* **Reliable ($\text{CV} \le 10\%$):** Solid bar, no flag.
* **Use with caution ($10\% < \text{CV} \le 20\%$):** Single-hatched bar (`//`) and single asterisk (`*`).
* **Unreliable ($\text{CV} > 20\%$):** Triple-hatched translucent bar (`///`) and double asterisk (`**`).

### Why Rare Subgroups Have High CVs (`*` and `**`): The Mathematics of Small-Cell Variance {#small-cells}

When the data are cross-tabulated into fine demographic cells—such as *Post-Secondary Non-Tertiary Undergraduates* (`RQ1_RQ2_c_Education`) or *No Grade Completed $\times$ Industry* (`5A_Sector_Educ_Annual`)—some cells represent a very small fraction of the national workforce. In a two-stage cluster sample, rare subgroups exhibit high relative variance for two mathematical reasons:

1. **Zero-Heavy PSU Concentration:** Suppose within a stratum $p$ containing $a_p$ sampled PSUs, only one PSU ($a = 1$) happens to contain respondents belonging to rare subgroup $d$, so <span>$z_{y,p,1} > 0$</span> and <span>$z_{y,p,2} = \dots = z_{y,p,a_p} = 0$</span>. Substituting these into the between-PSU sum of squares yields:

$$
\sum_{a=1}^{a_p} z_{y,p,a}^2 - \frac{\left(\sum_{a=1}^{a_p} z_{y,p,a}\right)^2}{a_p} = z_{y,p,1}^2 - \frac{z_{y,p,1}^2}{a_p} = \left(\frac{a_p - 1}{a_p}\right) z_{y,p,1}^2
$$

Multiplying by $\frac{a_p}{a_p - 1}(1 - f_{1,p})$ in the between-PSU variance formula gives:

$$
V_{b,p}(y) = (1 - f_{1,p}) \, z_{y,p,1}^2
$$

Thus, a single non-zero PSU contributes nearly the full square of its weighted total <span>$z_{y,p,1}^2$</span> to the stratum variance ($\text{CV}_{p} \approx \sqrt{1 - f_{1,p}} \approx 100\%$ within that stratum/month).

2. **Small Denominator Scaling ($1 / \sqrt{M_d}$):** Pooled across $K$ rounds and $M_d$ non-empty PSU clusters nationally, the relative standard error scales inversely with the square root of the effective number of non-zero clusters <span>$M_d$</span>:

$$
\text{CV}(\bar{Y}_d) = \frac{\text{SE}(\bar{Y}_d)}{\bar{Y}_d} \propto \frac{1}{\sqrt{M_d}}
$$

Whenever a demographic subgroup has fewer than $M_d \approx 25$ effective non-zero PSU hits across the year, $\text{CV}(\bar{Y}_d)$ exceeds $1 / \sqrt{25} = 20\%$ and is automatically flagged as `unreliable (CV>20%)` (`**`).

### Why Slightly Overlapping $95\%$ Confidence Intervals Can Still Differ at $\alpha = 0.05$

In Figure 8 (regional underemployment rates), each region $i$ is plotted with a $95\%$ confidence interval whisker:

$$
\text{CI}_{95\%, i} = \bar{R}_i \pm 1.96 \, \text{SE}(\bar{R}_i)
$$

When comparing two independent regional estimates <span>$\bar{R}_1$</span> and <span>$\bar{R}_2$</span> with similar standard errors (<span>$\text{SE}_1 \approx \text{SE}_2 = s$</span>), the standard error of their difference is <span>$\text{SE}(\bar{R}_1 - \bar{R}_2) = \sqrt{s^2 + s^2} = \sqrt{2}\,s$</span>.

* A two-sided test at the $\alpha = 0.05$ significance level rejects equality when:

$$
\vert\bar{R}_1 - \bar{R}_2\vert > 1.96 \sqrt{2}\,s \approx 2.77s
$$

* By contrast, requiring the two $95\%$ confidence intervals **not to overlap at all** requires the distance between point estimates to exceed the sum of both half-intervals:

$$
\vert\bar{R}_1 - \bar{R}_2\vert > 1.96s + 1.96s = 3.92s \implies Z = \frac{3.92s}{\sqrt{2}\,s} \approx 2.77 \implies p \approx 0.0056
$$

Consequently, non-overlapping $95\%$ whiskers provide a conservative visual guarantee of statistical difference ($p \approx 0.006$), while two intervals that overlap by less than $\frac{3.92 - 2.77}{3.92} \approx 29\%$ of a single whisker arm remain statistically distinct at the pairwise $5\%$ level.

## 7. Statistical Remedies for High-CV ("Unreliable") Small Domains {#remedies}

In official survey statistics (Eurostat EU-LFS, U.S. Census/ACS, Statistics Canada, and PSA/ADB Small Area Estimation guidelines), three mathematical techniques are used to reduce $\text{CV}(\bar{Y}_d)$ below the $10\text{--}20\%$ threshold when analyzing small domains:

### Remedy 1: Design-Based Domain Collapsing (Zero Model Bias)

Let $d_1$ and $d_2$ be two adjacent sparse categories (for example, *Post-Secondary Undergraduate* $d_1$ with $\text{CV} = 22.7\%$ and *Post-Secondary Graduate* $d_2$ with $\text{CV} = 6.9\%$), and define the collapsed domain $D = d_1 \cup d_2$ (**Post-Secondary / TVET Combined**). Because $d_1 \cap d_2 = \emptyset$, the combined estimator is simply $\bar{Y}_D = \bar{Y}_{d_1} + \bar{Y}_{d_2}$, and its relative variance is:

$$
\text{CV}(\bar{Y}_D) = \frac{\sqrt{V(\bar{Y}_{d_1}) + V(\bar{Y}_{d_2}) + 2\,\text{Cov}(\bar{Y}_{d_1}, \bar{Y}_{d_2})}}{\bar{Y}_{d_1} + \bar{Y}_{d_2}} \times 100\%
$$

When $d_1$ and $d_2$ rarely co-occur in the same household ($\text{Cov}(\bar{Y}_{d_1}, \bar{Y}_{d_2}) \approx 0$), the larger denominator $\bar{Y}_{d_1} + \bar{Y}_{d_2}$ dominates, reducing the combined $\text{CV}(\bar{Y}_D)$ to $\approx 6.6\% \le 10\%$ (`reliable`) with zero model bias.

### Remedy 2: Multi-Year Wave Pooling ($T$-Year Rolling Averages)

Let $\bar{Y}_{d}^{(T)} = \frac{1}{T}\sum_{t=1}^{T} \bar{Y}_{d,t}$ be the pooled estimator across $T$ consecutive years of LFS Public Use Files (e.g., $T = 3$ years, $36$ monthly rounds). Under annual independence across rotating master sample panels with equal annual variance $V(\bar{Y}_{d,t}) \approx V_d$, the pooled standard error scales by $1/\sqrt{T}$:

$$
\text{CV}\!\left(\bar{Y}_d^{(T)}\right) \approx \frac{\text{CV}(\bar{Y}_d)}{\sqrt{T}}
$$

Pooling $T = 3$ years reduces the *Post-Secondary Undergraduate* $\text{CV}$ from $22.7\%$ to $22.7\% / \sqrt{3} \approx 13.1\%$, moving it out of the `unreliable` band.

### Remedy 3: Fay-Herriot Small Area Estimation (Empirical Bayes / EBLUP Shrinkage)

When disaggregated estimates are needed for a single year without collapsing categories, the **Fay-Herriot (1979) area-level linear mixed model** links the direct survey estimator $\bar{Y}_d$ to a vector of auxiliary Census or administrative covariates $\mathbf{x}_d$ (such as Census of Population and Housing educational attainment shares or TESDA enrollment totals):

$$
\bar{Y}_d = \theta_d + e_d, \qquad e_d \sim \mathcal{N}\!\left(0,\, V(\bar{Y}_d)\right) \quad \text{(Sampling model)}
$$

$$
\theta_d = \mathbf{x}_d^\top \boldsymbol{\beta} + u_d, \qquad u_d \sim \mathcal{N}\!\left(0,\, \sigma_u^2\right) \quad \text{(Linking model)}
$$

where $V(\bar{Y}_d)$ is our known two-stage Taylor design variance and $\sigma_u^2$ is the between-domain model variance estimated via Restricted Maximum Likelihood (REML). The **Empirical Best Linear Unbiased Predictor (EBLUP)** is the precision-weighted composite estimator:

$$
\hat{\theta}_d^{\text{FH}} = \gamma_d \, \bar{Y}_d + (1 - \gamma_d) \, \mathbf{x}_d^\top \hat{\boldsymbol{\beta}}, \qquad \text{where} \quad \gamma_d = \frac{\sigma_u^2}{\sigma_u^2 + V(\bar{Y}_d)} \in (0, 1)
$$

Ignoring uncertainty in estimating $\boldsymbol{\beta}$, the leading term of the Mean Squared Error is:

$$
\text{MSE}\!\left(\hat{\theta}_d^{\text{FH}}\right) \approx \gamma_d \, V(\bar{Y}_d) < V(\bar{Y}_d)
$$

Whenever a small cell $d$ has a very large direct design variance $V(\bar{Y}_d)$ ($\text{CV} > 20\%$), the shrinkage factor $\gamma_d$ automatically shifts weight toward the synthetic census prediction $\mathbf{x}_d^\top \hat{\boldsymbol{\beta}}$, stabilizing the estimate and reducing its effective $\text{CV}$ by $\sqrt{\gamma_d}$.

## 8. Worked Numerical Walkthrough {#example}

To trace how the SQL and Python pipeline transforms raw household weights into published rows with standard errors and reliability flags, consider three benchmark cells from the verified 2025 tables:

1. **National Annual Headline (`0A_PSA_Validation_Annual` & `1A_Sector_Annual`, $K = 12$ months):**
   * **Point Estimates:** Across the $12$ monthly rounds, the exact mean employed total is $\bar{X} = 49,024.506\text{k}$ ($49.0\text{M}$) and the mean underemployed total is $\bar{Y} = 5,833.9\text{k}$ ($5.8\text{M}$).
   * **Headline Rate:**
     $$\bar{R} = \frac{5,833.9}{49,024.506} \times 100 = 11.90\%$$
   * **Standard Error Validation:** Across the $12$ individual monthly rounds, the ratio of our two-stage design standard error $\text{SE}(\hat{Y}_m)$ to PSA's published Special Release standard error has a median of $0.9990\times$ (range $0.973\times\text{--}1.020\times$).

2. **Regional Quarterly Estimate (`R0A_RReg_Qavg` / `R0B_RReg_Quarterly`, $K = 4$ quarterly rounds):**
   * **Point Estimates:** For Region XII (SOCCSKSARGEN), averaging the $4$ quarterly rounds (January, April, July, October) yields the highest regional underemployment rate in the country at $\bar{R}_{\text{XII}} = 28.8\%$, compared with $\bar{R}_{\text{XI}} = 5.3\%$ in neighboring Davao.
   * **Standard Error Validation:** Across all $4 \times 18 = 72$ quarterly regional cells, our two-stage standard errors match PSA's published regional standard errors to a median ratio of $0.9918\times$ (range $0.875\times\text{--}1.040\times$).

3. **Unreliable Small Subgroup (`RQ1_RQ2_c_Education`, Post-Secondary Undergraduates, $K = 12$ months):**
   * **Why it is flagged `**`:** Post-secondary non-tertiary undergraduates ($\texttt{PUFC07\_GRADE}$ codes $40001\text{--}40003$ and $50001\text{--}50003$) represent a tiny fraction of the workforce where most PSU clusters contain zero respondents ($z_{y,p,a} = 0$), triggering the small-cell variance effect derived in Section 6.
   * **CV Calculation:** With $\text{SE}(\bar{Y}_d) = 0.227 \, \bar{Y}_d$, dividing the pooled standard error by the small subgroup headcount estimate yields:
     $$\text{CV}(\bar{Y}_d) = \frac{\text{SE}(\bar{Y}_d)}{\bar{Y}_d} \times 100 = \frac{0.227 \, \bar{Y}_d}{\bar{Y}_d} \times 100 = 22.7\% > 20\%$$
   * **Visual & Table Encoding:** Because $\text{CV} > 20\%$, `tables.py` labels the row `unreliable (CV>20%)` and `figures.py` renders the bar with triple hatching (`///`), $45\%$ opacity, and a `**` suffix.

[$\leftarrow$ Back to Main Report](index.html)

<style>
  table { display: block; max-width: 100%; overflow-x: auto; }
</style>
<script>
  window.MathJax = {
    tex: { inlineMath: [['$', '$'], ['\\(', '\\)']], displayMath: [['$$', '$$'], ['\\[', '\\]']] }
  };
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>