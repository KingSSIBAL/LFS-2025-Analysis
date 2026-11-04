---
layout: default
title: "Underemployment in the Philippines, 2025 — PSA Labor Force Survey Analysis"
description: "Stratified analysis of underemployment by sector, sex, age, education, and region from the 12 monthly 2025 Philippine Labor Force Survey Public Use Files (4,229 official PSA checks verified)."
---

# Underemployment in the Philippines, 2025

Analysis of the 12 monthly 2025 Labor Force Survey Public Use Files (Philippine Statistics Authority). Every figure PSA publishes was recomputed and matches.

| Report Metadata | Specification |
|---|---|
| **Microdata Source** | PSA Labor Force Survey (LFS) Public Use Files, January–December 2025 (12 rounds) |
| **Target Population** | Employed persons aged $15+$ excluding overseas workers ($\bar{X} = 49.0\text{M}$ average per month) |
| **Sampling & Variance Design** | 2023 Geo-enabled Master Sample: $117$ province/HUC strata, contiguous PSU clustering, $2$-stage FPC ($B = 250$), Taylor series linearization |
| **Official Validation** | $4,229 / 4,229$ published PSA Special Release figures matched ($3,576$ monthly, $77$ annual, $576$ regional) |
| **Methodology & Derivations** | [**Mathematical Methodology & Variance Design (`methodology.html`)**](methodology.html) · [**Source Code (`lfs.py`)**](https://github.com/KingSSIBAL/LFS-2025-Analysis/blob/main/lfs.py) |

<nav aria-label="Contents">
<strong>Contents</strong>
<ul style="list-style: none; padding-left: 0;">
  <li><a href="#findings">Key findings</a></li>
  <li><a href="#sector">1. By broad sector</a></li>
  <li><a href="#who">2. Who is underemployed</a></li>
  <li><a href="#visible">3. Visible vs. invisible</a></li>
  <li><a href="#monthly">4. Monthly pattern</a></li>
  <li><a href="#region">5. By region</a></li>
  <li><a href="#deeper">6. Deeper breakdowns</a></li>
  <li><a href="#trust">Can these numbers be trusted?</a></li>
  <li><a href="#limits">Limits</a></li>
  <li><a href="#data">Data, math, and code</a></li>
</ul>
</nav>

**Key terms.** *Underemployed*: employed, but wants more hours of work. *Visibly underemployed*: worked under $40$ hours. *Invisibly underemployed*: already worked $40$ hours or more and still wants more. *Group rate* ($\hat{Y}_d / \hat{X}_d$): underemployed as a share of the employed in that group. *Pool share* ($\hat{Y}_d / \hat{Y}$): a group's share of all $5.8\text{M}$ underemployed workers nationally. *Visible share* ($\hat{Y}_d^{\text{vis}} / \hat{Y}_d$): the share of a group's underemployed who work under $40$ hours. See [**Mathematical Methodology & Variance Design**](methodology.html) for the exact formulas.

Annual figures are the average of the 12 monthly rounds. Regional figures are the average of the 4 quarterly rounds (January, April, July, October), the only rounds designed for regional estimates.

## Key findings {#findings}

| Finding | Number | Detail |
|---|---|---|
| Underemployed, average per month | 5.8 million | $11.9\%$ of 49.0 million employed |
| Highest-rate sector: agriculture | $17.5\%$ | 3 in 4 of them work under 40 hours |
| Largest group: services | $51\%$ | of all underemployed, but the lowest rate ($9.8\%$) |
| Men vs. women | $13.3\%$ vs. $9.9\%$ | men are two-thirds of the underemployed |
| No schooling vs. college graduates | $18.6\%$ vs. $6.7\%$ | the rate falls steadily with education |
| Peak vs. low month | $14.8\%$ vs. $8.0\%$ | July vs. December |
| Highest vs. lowest region | $28.8\%$ vs. $5.3\%$ | SOCCSKSARGEN vs. Davao |

**The main message:** the sector with the most underemployed workers (services) is not the sector where workers are most likely to be underemployed (agriculture).

*Tip: click any figure to expand it in place (press Esc to close). Hatched bars mark cells with $\text{CV} \in (10\%, 20\%]$ (`*`, use with caution) or $\text{CV} > 20\%$ (`**`, unreliable).*

## 1. By broad sector {#sector}

[![Two charts. Left: underemployed by sector, split into visible and invisible. Right: underemployment rate by sector, agriculture highest at 17.5%.](output/figures/fig1_broad_sector_overview_2panel.png)](output/figures/fig1_broad_sector_overview_2panel.png)

**Services hold half of the underemployed ($51\%$), but agriculture has the highest rate ($17.5\%$).** In agriculture, 3 in 4 underemployed workers work under $40$ hours; in services and industry, visible and invisible underemployment split almost evenly.

## 2. Who is underemployed (Research Question 1) {#who}

[![Four bar charts of the number underemployed by age group, sex, education and sector, with each group's share of the total.](output/figures/fig_RQ1_total_underemployment_4panel.png)](output/figures/fig_RQ1_total_underemployment_4panel.png)

**Men make up two-thirds of the underemployed pool and face a higher within-group rate than women ($13.3\%$ vs. $9.9\%$).** While the chart above plots each group's headcount and share of the $5.8\text{M}$ national pool, the within-group vulnerability rate falls steadily with schooling—from $18.6\%$ (no grade completed) to $6.7\%$ (college graduates). Post-secondary undergraduates (`**`, $\text{CV} = 22.7\%$) have too small a sample to read reliably. By age, the rate stays at $11\text{–}13\%$ until dropping to $7.8\%$ at $65$ and over.

## 3. Visible vs. invisible underemployment (Research Question 2) {#visible}

[![Four paired bar charts comparing visibly and invisibly underemployed workers by age group, sex, education and sector.](output/figures/fig_RQ2_visible_invisible_4panel.png)](output/figures/fig_RQ2_visible_invisible_4panel.png)

**Underemployed college graduates mostly work full time already:** only $37\%$ of underemployed graduates work under $40$ hours (visibly underemployed), compared with $77\%$ in agriculture and $77\%$ among workers aged $65$ and over.

## 4. Monthly pattern (Research Question 3) {#monthly}

[![Left: monthly number underemployed split into visible and invisible. Right: monthly visible and invisible shares with the national rate as a line, peaking in July.](output/figures/fig_RQ3_monthly_number_and_distribution.png)](output/figures/fig_RQ3_monthly_number_and_distribution.png)

**The rate peaks in July ($14.8\%$) and April ($14.6\%$) and hits its low in December ($8.0\%$).** Monthly standard errors run $0.2\text{–}1.0$ percentage points, ruling out sampling noise. April reflects dry-season farm slack, July reflects monsoon disruptions to outdoor hours, and December reflects holiday retail demand and 13th-month pay.

[![Two line charts of monthly underemployed number and rate for agriculture, industry and services.](output/figures/fig2_monthly_sector_trends_2panel.png)](output/figures/fig2_monthly_sector_trends_2panel.png)

**All three sectors move together:** each peaks in July and bottoms out in December. Agriculture ranges from $13.7\%$ to $22.0\%$, services from $6.0\%$ to $12.4\%$.

[![Three stacked bar charts, one per sector, of monthly visibly and invisibly underemployed workers.](output/figures/fig3_monthly_visible_invisible_by_sector.png)](output/figures/fig3_monthly_visible_invisible_by_sector.png)

**Visible (short-hour) underemployment drives the April and July spikes across all sectors, while invisible (full-time) underemployment forms a steadier baseline.**

## 5. By region {#region}

[![Map of the Philippines shaded by regional underemployment rate, next to a ranked bar chart of the 18 regions with 95% confidence intervals.](output/figures/fig8_region_map.png)](output/figures/fig8_region_map.png)

**Regions differ five-fold: SOCCSKSARGEN ($28.8\%$), MIMAROPA ($24.5\%$), and Bicol ($23.5\%$) rank highest; Davao ($5.3\%$) and NCR ($7.4\%$) rank lowest.** Whiskers show $95\%$ confidence intervals; non-overlapping intervals indicate conservative, statistically distinct pairs (slight overlaps can still differ at the $5\%$ level; see the [math notes](methodology.html#reliability)).

**Residence vs. workplace:** When underemployed workers are counted by their *region of workplace* (`W*` tables) instead of residence (`R*` tables), cross-border commuting shifts the metropolitan numbers substantially—NCR's underemployed count is $19\%$ higher by workplace than by residence, while CALABARZON's is $11\%$ lower.

## 6. Deeper breakdowns {#deeper}

[![Underemployed number and rate by sector and sex.](output/figures/fig4_sector_by_sex_2panel.png)](output/figures/fig4_sector_by_sex_2panel.png)

**The gap between men and women is widest in agriculture ($19.0\%$ vs. $13.4\%$).** In services, the rates sit close ($10.5\%$ vs. $9.2\%$) and headcounts are nearly equal.

[![Underemployed number and rate by age group and sector.](output/figures/fig5_sector_by_age_2panel.png)](output/figures/fig5_sector_by_age_2panel.png)

**Agricultural workers aged 25–34 face the highest rate of any age group in any sector ($21.7\%$).**

[![Underemployed number and rate by highest grade completed and sector.](output/figures/fig6_sector_by_education_2panel.png)](output/figures/fig6_sector_by_education_2panel.png)

**Education lowers the rate in industry and services, but much less in agriculture:** college graduates in agriculture still face a $15.3\%$ rate. Hatched bars flag small cells with high sampling variance (`*` $\text{CV} \in (10\%, 20\%]$, `**` $\text{CV} > 20\%$, such as no schooling in industry).

[![Underemployed number by age group and sex, one chart per sector.](output/figures/fig7_sector_age_sex_3way.png)](output/figures/fig7_sector_age_sex_3way.png)

**The largest single demographic cell is men aged 25–34 in services (457,000 a month).**

**What the breakdowns mean together:** Underemployment in the Philippines is two distinct problems under one headline number—an *hours-shortage* problem in agriculture (where $77\%$ of the underemployed work under $40$ hours and rates spike during the April dry season and July monsoon) and an *earnings-adequacy* problem in services and among college graduates (where $63\%$ of the underemployed already work $40+$ hours a week).

## Can these numbers be trusted? {#trust}

- **Every published PSA figure is reproduced:** 4,229 checks against PSA's final Special Release tables match within rounding (3,576 monthly, 77 annual, 576 regional).
- **Standard errors follow the PSA Technical Notes:** computed SEs are $0.999\times$ PSA's published values nationally (median of 12 months) and $0.992\times$ regionally (median of 72 cells).
- **Every table and chart carries a reliability flag:** $\text{CV} \le 10\%$ reliable, $10\text{–}20\%$ (`*`) use with caution, $> 20\%$ (`**`) unreliable. The only unreliable headline cell is post-secondary undergraduates ($\text{CV} = 22.7\%$).

## Limits {#limits}

- Multi-way breakdowns (by education, sector $\times$ sex/age/education, and region $\times$ age/sector/education) have no published PSA table and are verified by summing to checked margins.
- Region of **workplace** tables (`W*`) cannot be checked against PSA's published tables, which report region of residence only.
- Annual and regional averages treat the monthly Public Use Files as independent samples across rounds ($V(\bar{Y}) = \frac{1}{K^2}\sum_{m=1}^{K} V(\hat{Y}_m)$) because household panel identifiers across rounds are not released in the public microdata.
- Standard errors cannot match PSA's to the last decimal because the Public Use Files omit survey design details documented in the [**Mathematical Methodology**](methodology.html#design) and at the top of [`lfs.py`](https://github.com/KingSSIBAL/LFS-2025-Analysis/blob/main/lfs.py).

## Data, math, and code {#data}

- **Mathematical formulas & survey design:** [**Mathematical Methodology & Variance Design (`methodology.html`)**](methodology.html)
- **All tables:** [Excel workbook](output/LFS_2025_Stratified_Underemployment_Tables.xlsx) · [CSV files](https://github.com/KingSSIBAL/LFS-2025-Analysis/tree/main/output/tables)
- **Code and how to re-run:** [repository README](https://github.com/KingSSIBAL/LFS-2025-Analysis#readme)
- **Data:** Philippine Statistics Authority, Labor Force Survey 2025 Public Use Files and Special Release tables. Map boundaries: [faeldon/philippines-json-maps](https://github.com/faeldon/philippines-json-maps) (MIT).

<footer>The analysis and any errors are ours, not PSA's.</footer>

<style>
  a[href$=".png"] img { cursor: zoom-in; }
  dialog#lightbox { max-width: 95vw; max-height: 95vh; padding: 0; border: none; background: transparent; }
  dialog#lightbox::backdrop { background: rgba(0, 0, 0, 0.82); cursor: zoom-out; }
  dialog#lightbox img { display: block; max-width: 95vw; max-height: 95vh; width: auto; height: auto; background: #fff; border-radius: 4px; cursor: zoom-out; }
</style>

<dialog id="lightbox" aria-label="Expanded figure">
  <img id="lightbox-img" alt="">
</dialog>

<script>
  const dialog = document.getElementById('lightbox');
  const dialogImg = document.getElementById('lightbox-img');
  // shortcut: delegates all .png clicks on document, assumes all report figures end in .png
  document.addEventListener('click', (e) => {
    const link = e.target.closest('a[href$=".png"]');
    if (!link || e.metaKey || e.ctrlKey) return;
    e.preventDefault();
    const thumb = link.querySelector('img');
    dialogImg.src = link.href;
    dialogImg.alt = thumb ? thumb.alt : '';
    dialog.showModal();
  });
  dialog.addEventListener('click', () => dialog.close());
</script>
<script>
  window.MathJax = {
    tex: { inlineMath: [['$', '$'], ['\\(', '\\)']], displayMath: [['$$', '$$'], ['\\[', '\\]']] }
  };
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>