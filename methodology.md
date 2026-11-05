---
layout: default
title: "Mathematical Methodology, PSA Survey Plan & PUF Metadata — Philippine LFS 2025"
description: "Complete PSA 2023 Geo-enabled Master Sample plan, PUF variable metadata dictionary, questionnaire cross-walks, two-stage Taylor variance formulas, and Small Area Estimation remedies for the 2025 Philippine Labor Force Survey."
permalink: /methodology.html
---

# Mathematical Methodology, PSA Survey Plan & PUF Metadata

$\leftarrow$ [Back to Main Report](index.html)

This reference documents the complete Philippine Statistics Authority (PSA) Labor Force Survey (LFS) sampling plan, the 2025 Public Use File (PUF) metadata and recode dictionaries, the domain-reconstruction rules, and the two-stage Taylor series linearization formulas implemented in [`tables.py`](https://github.com/KingSSIBAL/LFS-2025-Analysis/blob/main/tables.py), [`lfs_view.sql`](https://github.com/KingSSIBAL/LFS-2025-Analysis/blob/main/lfs_view.sql), and [`psa.py`](https://github.com/KingSSIBAL/LFS-2025-Analysis/blob/main/psa.py). All definitions and variance equations follow the official PSA *Technical Notes on the Labor Force Survey* (pp. 1–9).

**Contents**
1. [Full PSA Labor Force Survey (LFS) sampling & operations plan](#psa-plan)
2. [Complete PUF metadata, variable dictionary & questionnaire cross-walk](#metadata)
3. [Core point estimators (counts, rates, and shares)](#estimators)
4. [Multi-round aggregation (annual & quarterly averages)](#aggregation)
5. [Reconstructing the 117 Master Sample domains & PSUs](#design)
6. [Two-stage stratified cluster variance (totals)](#variance)
7. [Taylor series linearization for ratio standard errors](#taylor)
8. [Reliability bands (CV), small-cell algebra & CI overlap](#reliability)
9. [Statistical remedies for high-CV ("unreliable") small domains](#remedies)
10. [Official PSA validation architecture, table inventory & worked walkthrough](#example)

## 1. Full PSA Labor Force Survey (LFS) Sampling & Operations Plan {#psa-plan}

### 1.1 Scope, Target Population & Reference Period (PSA Technical Notes, pp. 1–2)

* **Target Population:** All household population aged $15$ years and over residing in the Philippines.
* **Exclusions:** Overseas Filipino Workers (OFWs) and the institutional population (persons living in dormitories, barracks, hospitals, penal institutions, and convents) are excluded from the labor force domestic count.
* **Reference Period:** The **past week**, defined as the $7$ consecutive days preceding the date of the enumerator's interview.
* **Official Labor Force Concepts:**
  * **In the Labor Force:** Persons aged $15+$ who are either *employed* or *unemployed* during the reference week.
  * **Employed (`PUFNEWEMPSTAT = 1`):** Persons aged $15+$ who during the reference week either (a) worked for at least $1$ hour for pay or profit, or without pay on a family farm/enterprise (`PUFC11_WORK = 1`), or (b) had a job or business from which they were temporarily absent (`PUFC12_JOB = 1`, "with a job, not at work").
  * **Underemployed (`PUFC20_PWMORE = 1`):** Employed persons who expressed the desire to have additional hours of work in their present job, or to have an additional job, or to have a new job with longer working hours.
  * **Visibly Underemployed:** Underemployed persons who worked less than $40$ hours during the reference week (`PUFC19_PHOURS < 40` or `NULL`/`0` for those with a job but not at work).
  * **Invisibly Underemployed:** Underemployed persons who worked $40$ hours or more during the reference week (`PUFC19_PHOURS >= 40`).

### 1.2 The 2023 Geo-Enabled Master Sample (MS) & 117 Sampling Domains (Technical Notes, pp. 2–4)

The 2025 LFS utilizes the PSA's **2023 Geo-Enabled Master Sample (MS)** for household surveys, constructed from the 2020 Census of Population and Housing (CPH) frame. The national frame is partitioned into **117 mutually exclusive sampling domains** ($81$ provinces, $33$ Highly Urbanized Cities, and $3$ other urban areas), each treated as an explicit design stratum ($p \in \{1, \dots, 117\}$). In `tables.py` (`_DOM_EXPR`), these $117$ domains are extracted from the $4$-digit PSGC province/municipality code (`PUFC12A_PROVMUN`) as $84$ two-digit prefixes and $33$ four-digit HUC/municipality codes:

| Domain Category | PSA Count | SQL `_DOM_EXPR` Rule & PSGC Composition in `tables.py` |
|---|---|---|
| **Provinces** | $81$ | Coded by their 2-digit PSGC province prefix (`LEFT(PUFC12A_PROVMUN, 2)`, codes `01` to `86`), with Sulu (`66`) assigned to BARMM (`19`) in the 2025 PUF frame. |
| **Highly Urbanized Cities (HUCs) in NCR** | $16$ | City of Manila (coded by 2-digit prefix `39`) plus the $15$ Highly Urbanized Cities in NCR Districts II–IV (coded by 4-digit PSGC in `74xx`, `75xx`, `76xx`, excluding Pateros `7606`). |
| **Highly Urbanized Cities (HUCs) Outside NCR** | $17$ | Coded by their full 4-digit PSGC (`_HUCS_OUTSIDE_NCR`): `0202` Butuan, `1102` Baguio, `2217` Cebu City, `2226` Lapu-Lapu, `2230` Mandaue, `2402` Davao City, `3022` Iloilo City, `3504` Iligan, `3747` Tacloban, `4305` Cagayan de Oro, `4501` Bacolod, `5316` Puerto Princesa, `5401` Angeles, `5624` Lucena, `6303` General Santos, `7107` Olongapo, `7332` Zamboanga City. |
| **Other Urban Areas** | $3$ | Municipality of Pateros (4-digit code `7606` in NCR), Isabela City (2-digit prefix `97`), and Cotabato City (2-digit prefix `98`). |
| **Total Sampling Domains** | $117$ | $81 + 16 + 17 + 3 = 117$ ($84$ two-digit codes + $33$ four-digit codes; asserted via `SELECT COUNT(*) FROM work_dom_region == 117`). |

### 1.3 Two-Stage Stratified Cluster Design (Technical Notes, pp. 3–5)

Within each of the $117$ sampling domains (strata), the Master Sample selects households in two stages:

1. **Stage 1 — Primary Sampling Units (PSUs):** PSUs are individual barangays, combinations of small contiguous barangays, or portions of large barangays formed to contain approximately **100 to 400 households** (calibrated via `PUFURB2020` as $B _ {\text{urb}} = 25$ for urban PSUs and $B _ {\text{rur}} = 15$ for rural PSUs to match PSA's post-stratified Taylor variance scale). Within each domain $p$, $a _ p$ PSUs are selected systematically with **Probability Proportional to Size (PPS)**, where the measure of size is the 2020 Census household count $B _ {p,a}$. PSUs are sorted in geographic/serpentine order prior to systematic selection to induce implicit geographic stratification.
2. **Stage 2 — Secondary Sampling Units (Housing Units & Households):** Within each sampled PSU $(p,a)$, housing units are selected via systematic random sampling. All households residing within a selected housing unit are interviewed, up to a maximum of **3 households per housing unit** (if a housing unit contains more than $3$ households, $3$ are selected at random).

### 1.4 Quarterly (4-Replicate) vs. Monthly (1-Replicate) Rotation Schedule (Technical Notes, pp. 2, 4)

The PSA conducts the LFS in all $12$ months of the year, alternating between two sample designs:

| Design Feature | Quarterly Rounds (Jan, Apr, Jul, Oct) | Non-Quarterly Monthly Rounds (Feb, Mar, May, Jun, Aug, Sep, Nov, Dec) |
|---|---|---|
| **Number of Replicates (`PUFRPL`)** | **4 independent replicates** (`1`, `2`, `3`, `4`) | **1 replicate** |
| **Approximate Sample Size** | $\approx 2,940$ PSUs ($\approx 44,000\text{--}48,000$ households) per round | $\approx 735$ PSUs ($\approx 11,000\text{--}12,000$ households) per round |
| **Geographic Estimation Level** | **National and Regional** ($18$ regions) | **National Level Only** |
| **Residence Region (`PUFREG`) in PUF** | Populated for all respondents | Omitted (`NULL`/blank) by design |
| **Questionnaire Version** | Long Quarterly Questionnaire ($43$ items) | Short Monthly Questionnaire ($33$ items; shifted numbering) |
| **PSA Special Release Tables** | $20$ final tables (including regional & major industry breakdowns) | $11$ final tables (national & broad industry breakdowns) |

### 1.5 Three-Step Sampling Weight Construction & Calibration (Technical Notes, pp. 5–6)

Each respondent $i$ in PSU $a$ of domain $p$ receives a final calibrated weight $w _ i = \texttt{PUFPWGTPRV} _ i$ constructed in three stages:

1. **Base Design Weight** ($w _ {0,p,a}$): The inverse of the product of the first-stage PSU selection probability $f _ {1,p,a} \approx \frac{a _ p}{A _ p}$ and the second-stage household selection probability $f _ {2,p,a} = \frac{b _ {p,a}}{B _ {p,a}}$:

$$
w_{0,p,a} = \frac{1}{f_{1,p,a} \times f_{2,p,a}} = \frac{A_p}{a_p} \times \frac{B_{p,a}}{b_{p,a}}
$$

2. **Non-Response Adjustment** ($w _ {1,p,a}$): Base weights are multiplied by a PSU/domain non-response inflation factor $F _ {\text{NR},p,a} = \frac{b _ {p,a}^{\text{eligible}}}{b _ {p,a}^{\text{interviewed}}}$ to account for eligible sample households that could not be interviewed.
3. **Post-Stratification Age-Sex-Domain Calibration** ($w _ i = \texttt{PUFPWGTPRV} _ i$): Non-response-adjusted weights are raked/calibrated within each domain $p$, sex, and $5$-year age group cell $c$ so that weighted sample population totals match independent PSA demographic projections $N _ {p,c}^{\text{proj}}$ for the survey month:

$$
w_i = w_{1,p,a} \times \frac{N_{p,c}^{\text{proj}}}{\sum_{j \in (p,c)} w_{1,p,a(j)}} = \texttt{PUFPWGTPRV}_i
$$

## 2. Complete PUF Metadata, Variable Dictionary & Questionnaire Cross-Walk {#metadata}

### 2.1 Master PUF Variable Dictionary & Operational Definitions

All $12$ monthly CSV files in `data/puf/` are consolidated into `LFS_PUF_2025_Consolidated.parquet`. Below is the complete metadata dictionary for the variables used in the analytical view (`lfs_view.sql`), variance engine (`tables.py`), and PSA verifier (`psa.py`):

| PUF Variable (Quarterly Name) | Data Type | Valid Codes / Range | Official PSA Definition & Analytical Role |
|---|---|---|---|
| `PUFSVYYR` | Integer | `2025` | Survey year. |
| `PUFSVYMO` | Integer | `1`–`12` | Survey month (`1` = Jan, `4` = Apr, `7` = Jul, `10` = Oct are quarterly rounds). |
| `PUFREG` | String ($2$-char) | `01`–`19` (`NULL` in monthly) | PSGC Region of Residence. Populated only in quarterly rounds (`1, 4, 7, 10`). |
| `PUFPSU` | String | Numeric code | Primary Sampling Unit number. Reused across different provinces/domains. |
| `PUFRPL` | String | `1`–`4` | Master Sample replicate code. Used with `PUFPSU` and `PUFHHNUM` to identify contiguous PSU clusters. |
| `PUFHHNUM` | Integer | Sequential ID | Unique household identifier within each round, sorted in geographic domain order. |
| `PUFHHSIZE` | Integer | $\ge 1$ | Number of household members. |
| `PUFURB2020` | String | `1` = Urban, `2` = Rural | 2020 Census urban-rural barangay classification. |
| `PUFPWGTPRV` | Double | $> 0$ | **Final calibrated person weight** ($w _ i$). Summing `PUFPWGTPRV` yields population levels; household weight `w_hh` in `hh_psu` is `AVG(PUFPWGTPRV)` within each household. |
| `PUFC01_LNO` | Integer | `1`–$N$ | Person line number within the household roster. |
| `PUFC03_REL` | Integer | `1`–`11` | Relationship to household head. |
| `PUFC04_SEX` | String | `1` = Male, `2` = Female | Sex of respondent (`sex` in tables). |
| `PUFC05_AGE` | Integer | `0`–`99` ($\ge 15$ filtered) | Age as of last birthday. Filtered to $\ge 15$ and grouped into $6$ age brackets (`age_group`). |
| `PUFC06_MSTAT` | Integer | `1`–`6` | Marital status. |
| `PUFC07_GRADE` | Integer ($5$-digit) | PSCEd codes (`0`–`89999`) | Highest grade completed. Recoded into PSA's $11$ official education categories (`educ_group`). |
| `PUFNEWEMPSTAT` | String | `1` = Emp, `2` = Unemp, `3` = NILF | **PSA derived labor force status.** Filtered to `1` (Employed) in `lfs_employed_2025`. |
| `PUFC10_CONWR` | String | `1`–`5` | Overseas indicator (used by PSA to exclude OFWs from domestic labor force). |
| `PUFC11_WORK` | String | `1` = Yes, `2` = No | Worked for at least $1$ hour during the past week. |
| `PUFC12_JOB` | String | `1` = Yes, `2` = No | Albeit did not work, had a job or business during the past week ("with a job, not at work"). |
| `PUFC12A_PROVMUN` | String ($4$-char) | `PP` or `PPMM` PSGC | **Province and Municipality of Work.** Used to infer the $117$ sampling domains and workplace region (`W*`). |
| `PUFC14_PROCC` | Integer ($2$-digit) | PSOC codes (`01`–`96`) | Major occupation group in primary job. |
| `PUFC16_PKB` | Integer ($2$-digit) | PSIC codes (`01`–`99`) | **Kind of business / industry** (2019 PSIC $2$-digit division). Recoded into $3$ broad sectors and $22$ major industries. |
| `PUFC17_NATEM` | String | `1` = Perm, `2` = Short-term, `3` = Diff emp | Nature/permanency of employment in primary job. |
| `PUFC18_PNWHRS` | Integer | `1`–`24` | Normal working hours per day in primary job. |
| `PUFC19_PHOURS` | Integer | `0`–`168` (or `NULL`) | **Total hours worked during the past week** across all jobs. Splits visible ($<40$) vs. invisible ($\ge 40$). |
| `PUFC20_PWMORE` | String | `1` = Yes, `2` = No | **Wanted more hours of work** during the past week. Defines underemployment (`pwmore = '1'`). |
| `PUFC21_PLADDW` | String | `1` = Yes, `2` = No | Looked for additional work during the past week. |
| `PUFC23_PCLASS` | String | `0`–`6` | Class of worker (private wage, gov't, self-employed, employer, unpaid family worker). |

### 2.2 Quarterly vs. Monthly Questionnaire Column-Shift Cross-Walk (`tables.py`)

Because the $8$ non-quarterly monthly rounds omit several supplemental questions, the questionnaire item numbers in the monthly PUF CSVs are shifted backward relative to the $4$ quarterly PUF CSVs. During Step 1 (`build_consolidated_parquet` in `tables.py`), the monthly columns are harmonized to the quarterly schema via the following exact mapping:

| Harmonized / Quarterly Column (Jan, Apr, Jul, Oct) | Raw Monthly PUF Column (Feb, Mar, May, Jun, Aug, Sep, Nov, Dec) | Variable Description |
|---|---|---|
| `PUFC10_CONWR` | `PUFC08_CONWR` | Overseas / OFW indicator |
| `PUFC11_WORK` | `PUFC09_WORK` | Worked at least $1$ hour in past week |
| `PUFC11A_ARRANGEMENT` | `PUFC09A_WORK` | Work arrangement |
| `PUFC12_JOB` | `PUFC10_JOB` | Had a job/business although did not work |
| `PUFC12A_PROVMUN` | `PUFC11A_PROVMUN` | Province & municipality of work ($4$-digit PSGC) |
| `PUFC14_PROCC` | `PUFC13_PROCC` | Major occupation ($2$-digit PSOC) |
| `PUFC16_PKB` | `PUFC15_PKB` | Kind of business / industry ($2$-digit PSIC) |
| `PUFC17_NATEM` | `PUFC16_NATEM` | Nature of employment (permanency) |
| `PUFC18_PNWHRS` | `PUFC17_PNWHRS` | Normal working hours per day |
| `PUFC19_PHOURS` | `PUFC18_PHOURS` | Total hours worked in past week |
| `PUFC20_PWMORE` | `PUFC19_PWMORE` | Wanted more hours of work (underemployed indicator) |
| `PUFC21_PLADDW` | `PUFC20_PLADDW` | Looked for additional work |
| `PUFC22_PFWRK` | `PUFC20B_FTWORK` | First time to look for additional work |
| `PUFC23_PCLASS` | `PUFC21_PCLASS` | Class of worker |
| `PUFC26_OJOB` | `PUFC22_OJOB` | Had other job/business |
| `PUFC28_THOURS` | `PUFC23_THOURS` | Total hours worked across all jobs |
| `PUFC29_WWM48H` | `PUFC24_WWM48H` | Reason for working more than $48$ hours |
| `PUFC30_LOOKW` | `PUFC25_LOOKW` | Looked for work / tried to establish business |
| `PUFC31_FLWRK` | `PUFC25B_FTWORK` | First time to look for work |
| `PUFC34_WYNOT` | `PUFC26_WYNOT` | Main reason for not looking for work |
| `PUFC36_AVAIL` | `PUFC27_AVAIL` | Available for work during past week / within $2$ weeks |
| `PUFC38_PREVJOB` | `PUFC28_PREVJOB` | Worked at any time before |
| `PUFC39_YEAR` / `PUFC39_MONTH` | `PUFC29_YEAR` / `PUFC29_MONTH` | Year and month last worked |
| `PUFC41_POCC` | `PUFC31_POCC` | Previous occupation |
| `PUFC43_QKB` | `PUFC33_QKB` | Previous kind of business / industry |

### 2.3 Official Classification & Recode Schemas (`lfs_view.sql`)

#### A. Educational Attainment (`PUFC07_GRADE` 5-Digit PSCEd to 11 Official PSA Categories)

| `educ_code` | Official PSA Category (`educ_group`) | Exact `PUFC07_GRADE` Integer Code Ranges in `lfs_view.sql` |
|---|---|---|
| `1` | `No grade completed` | `0`–`1000`, or `2000` (Early childhood / no schooling) |
| `2` | `Elementary Undergraduate` | `10011`–`10015` (Grades 1–5), or `10004`–`10006` (SPED / non-graded elem) |
| `3` | `Elementary Graduate` | `10016`–`10018` (Grade 6–7 graduate) |
| `4` | `Junior High Undergraduate` | `24011`–`24013` (Grades 7–9 / 1st–3rd Yr HS), or `24004`–`24006` |
| `5` | `Junior High Completed` | `24014`–`24015` (Grade 10 / 4th Yr High School graduate) |
| `6` | `Senior High Undergraduate` | `34011`, `34021`, `34031`, `35011` (Grade 11 across Academic/TVL/Sports/Arts tracks) |
| `7` | `Senior High Graduate` | `34013`, `34023`, `34033`, `35013` (Grade 12 graduate across all tracks) |
| `8` | `Post Secondary Undergraduate` | `40001`–`40003` or `50001`–`50003` (1st–3rd year non-tertiary TVET incomplete) |
| `9` | `Post Secondary Graduate` | `40011`–`49999` or `50011`–`59999` (Completed post-secondary TVET certificate/diploma) |
| `10` | `College Undergraduate` | `60001`–`60006` (1st–6th year baccalaureate undergraduate) |
| `11` | `College Graduate` | `60000`, or `60011`–`89999` (Baccalaureate, Master's, or Doctoral degree holder) |

#### B. Industry Classification (`PUFC16_PKB` 2-Digit 2019 PSIC to 3 Broad Sectors & 22 Major Industries)

| Broad Sector (`broad_sector`) | `major_industry_order` | Major Industry Division (`major_industry`) | $2$-Digit PSIC (`PUFC16_PKB`) |
|---|---|---|---|
| **Agriculture, Forestry, and Fisheries (AFF)** | `1` | Agriculture and Forestry | `01`–`02` |
| **Agriculture, Forestry, and Fisheries (AFF)** | `2` | Fishing and Aquaculture | `03` |
| **Industry** | `3` | Mining and Quarrying | `05`–`09` |
| **Industry** | `4` | Manufacturing | `10`–`33` |
| **Industry** | `5` | Electricity, Gas, Steam, and Air Conditioning Supply | `35` |
| **Industry** | `6` | Water Supply; Sewerage, Waste Management | `36`–`39` |
| **Industry** | `7` | Construction | `41`–`43` |
| **Services** | `8` | Wholesale and Retail Trade; Repair of Motor Vehicles | `45`–`47` |
| **Services** | `9` | Transportation and Storage | `49`–`53` |
| **Services** | `10` | Accommodation and Food Service Activities | `55`–`56` |
| **Services** | `11` | Information and Communication | `58`–`63` |
| **Services** | `12` | Financial and Insurance Activities | `64`–`66` |
| **Services** | `13` | Real Estate Activities | `68` |
| **Services** | `14` | Professional, Scientific and Technical Activities | `69`–`75` |
| **Services** | `15` | Administrative and Support Service Activities | `77`–`82` |
| **Services** | `16` | Public Administration and Defense | `84` |
| **Services** | `17` | Education | `85` |
| **Services** | `18` | Human Health and Social Work Activities | `86`–`88` |
| **Services** | `19` | Arts, Entertainment and Recreation | `90`–`93` |
| **Services** | `20` | Other Service Activities | `94`–`96` |
| **Services** | `21` | Activities of Households as Employers | `97`–`98` (0 rows in 2025 PUF; folded into `Other Service` by PSA) |
| **Services** | `22` | Activities of Extraterritorial Organizations | `99` |

#### C. Regional Classification (`PUFREG` to 18 Official PSA Regions in Publication Order)

| Publication Order (`region_order`) | PSGC Code (`rcode`) | Region Display Name (`region` / `work_region`) | Residence (`R*`) vs. Workplace (`W*`) Rule |
|---|---|---|---|
| `1`–`6` | `13`, `14`, `01`, `02`, `03`, `04` | NCR, CAR, Region I (Ilocos), Region II (Cagayan Valley), Region III (Central Luzon), Region IV-A (CALABARZON) | `R*` uses `PUFREG` (Jan/Apr/Jul/Oct); `W*` maps `PUFC12A_PROVMUN` across all $12$ months. |
| `7`–`12` | `17`, `05`, `06`, `18`, `07`, `08` | MIMAROPA, Region V (Bicol), Region VI (Western Visayas), NIR (Negros Island), Region VII (Central Visayas), Region VIII (Eastern Visayas) | NIR (`18`: Negros Occidental `45` and Negros Oriental `46`) is published as a distinct region throughout all 2025 LFS rounds. |
| `13`–`18` | `09`, `10`, `11`, `12`, `16`, `19` | Region IX (Zamboanga Peninsula), Region X (Northern Mindanao), Region XI (Davao), Region XII (SOCCSKSARGEN), Region XIII (Caraga), BARMM | In the 2025 PUF, Sulu province (`66`) is mapped to BARMM (`19`) via `work_dom_region`. |

## 3. Core Point Estimators (Counts, Rates, and Shares) {#estimators}

Let $S _ m$ denote the sample of respondents in survey month $m \in \{1, \dots, 12\}$ who are aged $15$ and over, employed (`PUFNEWEMPSTAT = 1`), and have a valid industry code (`PUFC16_PKB` $\neq$ null). Each respondent $i$ carries a final calibrated person weight $w _ i = \texttt{PUFPWGTPRV} _ i$.

### Weighted Domain Totals

For any demographic, sectoral, or regional subgroup $d \subseteq S _ m$, the monthly weighted totals for **employed** ($\hat{X} _ {m,d}$) and **underemployed** ($\hat{Y} _ {m,d}$) persons are:

$$
\hat{X}_{m,d} = \sum_{i \in d} w_i
$$

$$
\hat{Y}_{m,d} = \sum_{i \in d} w_i \, \mathbb{I}(\texttt{PUFC20\_PWMORE}_i = 1)
$$

where $\mathbb{I}(\cdot)$ is the indicator function equal to $1$ if the respondent wants more hours of work in their present job or an additional job, and $0$ otherwise.

Underemployed workers are partitioned into **visibly underemployed** (worked less than $40$ hours during the reference week, including those "with a job, not at work" where `PUFC19_PHOURS` is null or $0$) and **invisibly underemployed** (worked $40$ hours or more):

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
| **1. Within-Group Underemployment Rate** | `underemp_rate_pct` | $\hat{R} _ {m,d} = \frac{\hat{Y} _ {m,d}}{\hat{X} _ {m,d}} \times 100$ | Share of *employed workers in group* $d$ who want more hours (vulnerability/incidence rate). |
| **2. Within-Group Visible / Invisible Rates** | `visible_rate_pct`, `invisible_rate_pct` | $\hat{R} _ {m,d}^{\text{vis}} = \frac{\hat{Y} _ {m,d}^{\text{vis}}}{\hat{X} _ {m,d}} \times 100$, $\hat{R} _ {m,d}^{\text{inv}} = \frac{\hat{Y} _ {m,d}^{\text{inv}}}{\hat{X} _ {m,d}} \times 100$ | Additive components of the group rate ($\hat{R} _ {m,d} = \hat{R} _ {m,d}^{\text{vis}} + \hat{R} _ {m,d}^{\text{inv}}$), plotted in Figure 1B. |
| **3. Visible / Invisible Share of Underemployed** | `visible_share_within_group_pct` | $\hat{S} _ {m,d}^{\text{vis}} = \frac{\hat{Y} _ {m,d}^{\text{vis}}}{\hat{Y} _ {m,d}} \times 100$, $\hat{S} _ {m,d}^{\text{inv}} = \frac{\hat{Y} _ {m,d}^{\text{inv}}}{\hat{Y} _ {m,d}} \times 100$ | Share of *underemployed workers in group* $d$ working $<40$ hrs vs. $\ge 40$ hrs ($\hat{S} _ {m,d}^{\text{vis}} + \hat{S} _ {m,d}^{\text{inv}} = 100\%$). |
| **4. Share of National / Sector Pool** | `share_of_national_underemp_pct` | $\hat{P} _ {m,d}^{\text{nat}} = \frac{\hat{Y} _ {m,d}}{\sum _ {d'} \hat{Y} _ {m,d'}} \times 100$ | Group $d$'s share of the entire national underemployed pool ($5.8\text{M}$). |

## 4. Multi-Round Aggregation (Annual & Quarterly Averages) {#aggregation}

Let $\mathcal{M}$ be the set of survey months pooled for an estimate, with cardinality $K = \vert\mathcal{M}\vert$:

* **National and Workplace-Region (`W*`) Annual Tables:** $\mathcal{M} = \{1, 2, \dots, 12\}$, $K = 12$.
* **Residence-Region (`R*`) Quarterly Tables:** $\mathcal{M} = \{1, 4, 7, 10\}$ (January, April, July, October), $K = 4$, as only the quarterly LFS rounds deploy the full $4$-replicate sample designed for regional estimates.

The multi-round average monthly headcount (in thousands) is the arithmetic mean across the $K$ rounds:

$$
\bar{X}_d = \frac{1}{K} \sum_{m \in \mathcal{M}} \frac{\hat{X}_{m,d}}{10^3}, \qquad \bar{Y}_d = \frac{1}{K} \sum_{m \in \mathcal{M}} \frac{\hat{Y}_{m,d}}{10^3}
$$

The annual or quarterly underemployment rate is the ratio of the multi-round pooled totals (`und * 100.0 / NULLIF(emp, 0)` in `tables.py`), which equals the ratio of the multi-round averages:

$$
\bar{R}_d = \frac{\sum_{m \in \mathcal{M}} \hat{Y}_{m,d}}{\sum_{m \in \mathcal{M}} \hat{X}_{m,d}} \times 100 = \frac{\bar{Y}_d}{\bar{X}_d} \times 100
$$

## 5. Reconstructing the 117 Master Sample Domains & PSUs {#design}

Because the anonymized PUF omits explicit residence-province codes and reuses PSU numbers across provinces, [`lfs_view.sql`](https://github.com/KingSSIBAL/LFS-2025-Analysis/blob/main/lfs_view.sql) reconstructs the two-stage design in four steps:

1. **Contiguous PSU Identification & Multi-Fragment Island Reunification (`hh_psu`):** Within each month $m$, households are ordered by their sequential household number (`PUFHHNUM`), which follows the geographic ordering of the Master Sample frame. Preliminary runs begin whenever the replicate code (`PUFRPL`), PSU code (`PUFPSU`), or residence region (`PUFREG`) changes between consecutive households. Any split PSU fragments that share the same inferred domain, replicate, and PSU code within $150$ household IDs ($\le 30$ combined households) are reunited into a single `psu_id` via a gap-and-islands window (`MIN(run_id) OVER (PARTITION BY m, strat, rpl, psu, island_id)` in `merged_runs`). Each household's weight $w _ {p,a,h}$ (`w_hh`) is computed as the mean of its members' calibrated person weights (`AVG(PUFPWGTPRV)`).
2. **In-Region Residence Constraint & 3-Step Neighbor-PSU Stratum Assignment (`psu_frame`):** Each household is assigned the modal province/HUC of work (`PUFC12A_PROVMUN`) of its employed members. In the $4$ quarterly rounds where the true residence region (`PUFREG`) is observed, only workplace domains belonging to the household's residence region (`wp.wcode = reg_code`) are eligible; in the $8$ non-quarterly monthly rounds (`PUFREG IS NULL`), each run's residence region `eff_reg` is first inferred via a 3-step neighbor smoother over the geographic `PUFHHNUM` ordering and used to filter eligible workplace domains (`hh_wreg = eff_reg`). Within each `(m, eff_reg)` partition, a 3-step neighbor window (`LAG`/`LEAD` $1, 2, 3$ with `IGNORE NULLS`) repairs commuter and empty PSUs to their surrounding residence stratum $p$.
3. **Urban/Rural Second-Stage Finite Population Correction** ($1 - f _ {2,p,a}$): Let $b _ {p,a}$ be the number of sampled households in PSU $a$ of stratum $p$. Following PSA Technical Notes (pp. 3, 7–8)—where rural barangay PSUs are smaller than urban EAs and post-stratification calibration absorbs part of the finite-population variance reduction—the effective frame constant of each PSU is calibrated using `PUFURB2020` as $B _ {p,a} = \max(b _ {p,a}, B _ {\text{urb/rur}})$, where $B _ {\text{urb}} = 25$ (`PUFURB2020 = '1'`) and $B _ {\text{rur}} = 15$ (`PUFURB2020 = '2'`), giving the second-stage FPC factor:

$$
1 - f_{2,p,a} = 1 - \frac{b_{p,a}}{\max(b_{p,a}, B_{p,a})}
$$

4. **First-Stage Sampling Fraction** ($f _ {1,p}$): Let $a _ p$ be the number of sampled PSUs in stratum $p$, and let $\hat{H} _ {p,a} = \sum _ {h=1}^{b _ {p,a}} w _ {p,a,h}$ (`psu_hh`) be the weighted household count of PSU $a$. The effective number of frame PSUs in stratum $p$ is estimated within each `(m, strat)` as $\hat{A} _ p = \max\!\left(a _ p, \sum _ {a=1}^{a _ p} \frac{\hat{H} _ {p,a}}{B _ {p,a}}\right)$, yielding the first-stage sampling fraction:

$$
f_{1,p} = \frac{a_p}{\hat{A}_p}, \qquad 1 - f_{1,p} = 1 - \frac{a_p}{\hat{A}_p}
$$

## 6. Two-Stage Stratified Cluster Variance (Totals) {#variance}

For any target subgroup $d$ in month $m$, let $y _ {p,a,h}$ be the weighted underemployed total in household $h$, PSU $a$, and stratum $p$, and let $x _ {p,a,h}$ be the corresponding household employed total:

$$
y_{p,a,h} = \sum_{i \in (p,a,h) \cap d} w_i \, \mathbb{I}(\texttt{pwmore}_i = 1), \qquad x_{p,a,h} = \sum_{i \in (p,a,h) \cap d} w_i
$$

Define the PSU-level sums and cross-products across the $b _ {p,a}$ households in PSU $(p,a)$:

$$
z_{y,p,a} = \sum_{h=1}^{b_{p,a}} y_{p,a,h}, \qquad q_{yy,p,a} = \sum_{h=1}^{b_{p,a}} y_{p,a,h}^2
$$

$$
z_{x,p,a} = \sum_{h=1}^{b_{p,a}} x_{p,a,h}, \qquad q_{xx,p,a} = \sum_{h=1}^{b_{p,a}} x_{p,a,h}^2, \qquad q_{xy,p,a} = \sum_{h=1}^{b_{p,a}} x_{p,a,h} \, y_{p,a,h}
$$

Following the two-stage variance decomposition in the PSA Technical Notes (p. 8a), the **within-PSU (second-stage) variance** summed across PSUs in stratum $p$ is:

$$
V_{w,p}(y) = \sum_{a=1}^{a_p} \mathbb{I}(b_{p,a} > 1) \left(1 - \frac{b_{p,a}}{\max(b_{p,a}, B_{p,a})}\right) \frac{b_{p,a}}{b_{p,a} - 1} \left( q_{yy,p,a} - \frac{z_{y,p,a}^2}{b_{p,a}} \right)
$$

The **between-PSU (first-stage) variance** in stratum $p$ is:

$$
V_{b,p}(y) = \mathbb{I}(a_p > 1) (1 - f_{1,p}) \frac{a_p}{a_p - 1} \left( \sum_{a=1}^{a_p} z_{y,p,a}^2 - \frac{\left(\sum_{a=1}^{a_p} z_{y,p,a}\right)^2}{a_p} \right)
$$

Summing across all $117$ strata combines the first- and second-stage variance components:

$$
V(\hat{Y}_{m,d}) = \sum_{p=1}^{117} \Big( V_{b,p}(y) + f_{1,p} \, V_{w,p}(y) \Big)
$$

Identical expressions yield the denominator variance $V(\hat{X} _ {m,d})$ and the bilinear covariance $\text{Cov}(\hat{X} _ {m,d}, \hat{Y} _ {m,d})$.

## 7. Taylor Series Linearization for Ratio Standard Errors {#taylor}

Because the underemployment proportion $\hat{r} _ d = \hat{Y} _ d / \hat{X} _ d \in [0, 1]$ (where $\hat{R} _ d = 100\,\hat{r} _ d$ is expressed in percentage points) is a ratio of two random survey totals, its variance is approximated via first-order Taylor series linearization around the population expectations (PSA Technical Notes, p. 8b):

$$
V(\hat{r}_d) \approx \frac{1}{\hat{X}_d^2} \Big( V(\hat{Y}_d) + \hat{r}_d^2 \, V(\hat{X}_d) - 2 \hat{r}_d \, \text{Cov}(\hat{Y}_d, \hat{X}_d) \Big)
$$

For multi-round averages across $K$ rounds ($K = 12$ annual or $K = 4$ quarterly), where rounds are treated as independent cross-sections in the absence of panel household identifiers across PUF files, `annotate_tables` in `tables.py` appends five validation and precision columns to every table (`psa_check`, `se_underemp_k`, `se_underemp_rate_pp`, `cv_underemp_pct`, and `reliability`), where:

$$
\text{SE}(\bar{Y}_d) = \frac{\sqrt{\max\!\left(0,\, \sum_{m \in \mathcal{M}} V(\hat{Y}_{m,d})\right)}}{K \times 10^3} \quad \text{(in thousands, } \texttt{se\_underemp\_k}\text{)}
$$

$$
\text{SE}(\bar{R}_d) = \frac{\sqrt{\max\!\left(0,\, \sum_{m \in \mathcal{M}} V(\hat{Y}_{m,d}) + \hat{r}_d^2 \sum_{m \in \mathcal{M}} V(\hat{X}_{m,d}) - 2 \hat{r}_d \sum_{m \in \mathcal{M}} \text{Cov}(\hat{Y}_{m,d}, \hat{X}_{m,d})\right)}}{\sum_{m \in \mathcal{M}} \hat{X}_{m,d}} \times 100 \quad \text{(in pp, } \texttt{se\_underemp\_rate\_pp}\text{)}
$$

Note on rotational panel covariance: If longitudinal household panel identifiers were available across rounds, the true variance of the $K$-round mean would include positive serial covariance terms $2 \sum _ {m < m'} \text{Cov}(\hat{Y} _ {m,d}, \hat{Y} _ {m',d})$.

## 8. Reliability Bands (CV), Small-Cell Algebra & Confidence Interval Overlap {#reliability}

### Coefficient of Variation (CV)

The relative sampling precision of every headcount estimate is measured by its Coefficient of Variation:

$$
\text{CV}(\bar{Y}_d) = \frac{\text{SE}(\bar{Y}_d)}{\bar{Y}_d} \times 100\%
$$

Following the reliability thresholds used in PSA/NSCB small-area statistics, every table row and chart bar is classified into three bands:

* **Reliable** ($\text{CV} \le 10\%$): Solid bar, no flag.
* **Use with caution** ($10\% < \text{CV} \le 20\%$): Single-hatched bar (`//`) and single asterisk (`*`).
* **Unreliable** ($\text{CV} > 20\%$): Triple-hatched translucent bar (`///`) and double asterisk (`**`).

### Why Rare Subgroups Have High CVs (`*` and `**`): The Mathematics of Small-Cell Variance {#small-cells}

When the data are cross-tabulated into fine demographic cells—such as *Post-Secondary Non-Tertiary Undergraduates* (`RQ1_RQ2_c_Education`) or *No Grade Completed* $\times$ *Industry* (`5A_Sector_Educ_Annual`)—some cells represent a very small fraction of the national workforce. In a two-stage cluster sample, rare subgroups exhibit high relative variance for two mathematical reasons:

1. **Zero-Heavy PSU Concentration:** Suppose within a stratum $p$ containing $a _ p$ sampled PSUs, only one PSU ($a = 1$) happens to contain respondents belonging to rare subgroup $d$, so $z _ {y,p,1} > 0$ and $z _ {y,p,2} = \dots = z _ {y,p,a _ p} = 0$. Substituting these into the between-PSU sum of squares yields:

$$
\sum_{a=1}^{a_p} z_{y,p,a}^2 - \frac{\left(\sum_{a=1}^{a_p} z_{y,p,a}\right)^2}{a_p} = z_{y,p,1}^2 - \frac{z_{y,p,1}^2}{a_p} = \left(\frac{a_p - 1}{a_p}\right) z_{y,p,1}^2
$$

Multiplying by $\frac{a _ p}{a _ p - 1}(1 - f _ {1,p})$ in the between-PSU variance formula gives:

$$
V_{b,p}(y) = (1 - f_{1,p}) \, z_{y,p,1}^2
$$

Thus, a single non-zero PSU contributes nearly the full square of its weighted total $z _ {y,p,1}^2$ to the stratum variance ($\text{CV} _ p \approx \sqrt{1 - f _ {1,p}} \approx 100\%$ within that stratum/month).

2. **Small Denominator Scaling** ($1 / \sqrt{M _ d}$): Pooled across $K$ rounds and $M _ d$ non-empty PSU clusters nationally, the relative standard error scales inversely with the square root of the effective number of non-zero clusters $M _ d$:

$$
\text{CV}(\bar{Y}_d) = \frac{\text{SE}(\bar{Y}_d)}{\bar{Y}_d} \propto \frac{1}{\sqrt{M_d}}
$$

Whenever a demographic subgroup has fewer than $M _ d \approx 25$ effective non-zero PSU hits across the year, $\text{CV}(\bar{Y} _ d)$ exceeds $1 / \sqrt{25} = 20\%$ and is automatically flagged as `unreliable (CV>20%)` (`**`).

### Why Slightly Overlapping 95% Confidence Intervals Can Still Differ at $\alpha = 0.05$

In Figure 8 (regional underemployment rates), each region $i$ is plotted with a $95\%$ confidence interval whisker:

$$
\text{CI}_{95\%, i} = \bar{R}_i \pm 1.96 \, \text{SE}(\bar{R}_i)
$$

When comparing two independent regional estimates $\bar{R} _ 1$ and $\bar{R} _ 2$ with similar standard errors ($\text{SE} _ 1 \approx \text{SE} _ 2 = s$), the standard error of their difference is $\text{SE}(\bar{R} _ 1 - \bar{R} _ 2) = \sqrt{s^2 + s^2} = \sqrt{2}\,s$.

* A two-sided test at the $\alpha = 0.05$ significance level rejects equality when:

$$
\vert\bar{R}_1 - \bar{R}_2\vert > 1.96 \sqrt{2}\,s \approx 2.77s
$$

* By contrast, requiring the two $95\%$ confidence intervals **not to overlap at all** requires the distance between point estimates to exceed the sum of both half-intervals:

$$
\vert\bar{R}_1 - \bar{R}_2\vert > 1.96s + 1.96s = 3.92s \implies Z = \frac{3.92s}{\sqrt{2}\,s} \approx 2.77 \implies p \approx 0.0056
$$

Consequently, non-overlapping $95\%$ whiskers provide a conservative visual guarantee of statistical difference ($p \approx 0.006$), while two intervals that overlap by less than $\frac{3.92 - 2.77}{3.92} \approx 29\%$ of a single whisker arm remain statistically distinct at the pairwise $5\%$ level.

## 9. Statistical Remedies for High-CV ("Unreliable") Small Domains {#remedies}

In official survey statistics (Eurostat EU-LFS, U.S. Census/ACS, Statistics Canada, and PSA/ADB Small Area Estimation guidelines), three mathematical techniques are used to reduce $\text{CV}(\bar{Y} _ d)$ below the $10\text{--}20\%$ threshold when analyzing small domains:

### Remedy 1: Design-Based Domain Collapsing (Zero Model Bias)

Let $d _ 1$ and $d _ 2$ be two adjacent categories—such as *Post-Secondary Undergraduate* ($d _ 1$, `educ_code = 8`, where $\text{CV}(\bar{Y} _ {d _ 1}) = 22.7\%$) and *Post-Secondary Graduate* ($d _ 2$, `educ_code = 9`)—and define the collapsed domain $D = d _ 1 \cup d _ 2$ (**Post-Secondary / TVET Combined**). Because $d _ 1 \cap d _ 2 = \emptyset$, the combined estimator is $\bar{Y} _ D = \bar{Y} _ {d _ 1} + \bar{Y} _ {d _ 2}$, and its relative variance is:

$$
\text{CV}(\bar{Y}_D) = \frac{\sqrt{V(\bar{Y}_{d_1}) + V(\bar{Y}_{d_2}) + 2\,\text{Cov}(\bar{Y}_{d_1}, \bar{Y}_{d_2})}}{\bar{Y}_{d_1} + \bar{Y}_{d_2}} \times 100\%
$$

When $d _ 1$ and $d _ 2$ rarely co-occur in the same household ($\text{Cov}(\bar{Y} _ {d _ 1}, \bar{Y} _ {d _ 2}) \approx 0$), pooling the non-zero PSU clusters $M _ D = M _ {d _ 1} + M _ {d _ 2}$ expands the denominator $\bar{Y} _ {d _ 1} + \bar{Y} _ {d _ 2}$ faster than the numerator standard error, bringing $\text{CV}(\bar{Y} _ D)$ into the `reliable (CV<=10%)` band with zero model bias.

### Remedy 2: Multi-Year Wave Pooling (T-Year Rolling Averages)

Let $\bar{Y} _ d^{(T)} = \frac{1}{T}\sum _ {t=1}^{T} \bar{Y} _ {d,t}$ be the pooled estimator across $T$ consecutive years of LFS Public Use Files (e.g., $T = 3$ years, $36$ monthly rounds). Under annual independence across rotating master sample panels with equal annual variance $V(\bar{Y} _ {d,t}) \approx V _ d$, the pooled standard error scales by $1/\sqrt{T}$:

$$
\text{CV}\!\left(\bar{Y}_d^{(T)}\right) \approx \frac{\text{CV}(\bar{Y}_d)}{\sqrt{T}}
$$

Pooling $T = 3$ years reduces the *Post-Secondary Undergraduate* $\text{CV}$ from $22.7\%$ to $22.7\% / \sqrt{3} \approx 13.1\%$, moving it out of the `unreliable` band.

### Remedy 3: Fay-Herriot Small Area Estimation (Empirical Bayes / EBLUP Shrinkage)

When disaggregated estimates are needed for a single year without collapsing categories, the **Fay-Herriot (1979) area-level linear mixed model** links the direct survey estimator $\bar{Y} _ d$ to a vector of auxiliary Census or administrative covariates $\mathbf{x} _ d$ (such as Census of Population and Housing educational attainment shares or TESDA enrollment totals):

$$
\bar{Y}_d = \theta_d + e_d, \qquad e_d \sim \mathcal{N}\!\left(0,\, V(\bar{Y}_d)\right) \quad \text{(Sampling model)}
$$

$$
\theta_d = \mathbf{x}_d^\top \boldsymbol{\beta} + u_d, \qquad u_d \sim \mathcal{N}\!\left(0,\, \sigma_u^2\right) \quad \text{(Linking model)}
$$

where $V(\bar{Y} _ d)$ is our known two-stage Taylor design variance and $\sigma _ u^2$ is the between-domain model variance estimated via Restricted Maximum Likelihood (REML). The **Empirical Best Linear Unbiased Predictor (EBLUP)** is the precision-weighted composite estimator:

$$
\hat{\theta}_d^{\text{FH}} = \gamma_d \, \bar{Y}_d + (1 - \gamma_d) \, \mathbf{x}_d^\top \hat{\boldsymbol{\beta}}, \qquad \text{where} \quad \gamma_d = \frac{\sigma_u^2}{\sigma_u^2 + V(\bar{Y}_d)} \in (0, 1)
$$

Ignoring uncertainty in estimating $\boldsymbol{\beta}$, the leading term of the Mean Squared Error is:

$$
\text{MSE}\!\left(\hat{\theta}_d^{\text{FH}}\right) \approx \gamma_d \, V(\bar{Y}_d) < V(\bar{Y}_d)
$$

Whenever a small cell $d$ has a very large direct design variance $V(\bar{Y} _ d)$ ($\text{CV} > 20\%$), the shrinkage factor $\gamma _ d$ automatically shifts weight toward the synthetic census prediction $\mathbf{x} _ d^\top \hat{\boldsymbol{\beta}}$, stabilizing the estimate and reducing its effective $\text{CV}$ by $\sqrt{\gamma _ d}$.

## 10. Official PSA Validation Architecture, Output Table Inventory & Worked Walkthrough {#example}

### 10.1 Automated Validation Against 12 PSA Special Release Table Families (`psa.py`) {#validation-map}

The repository stores two sets of PSA spreadsheets: preliminary Press Release tables in `data/psa_press_release/` ($44$ files) and **final Special Release statistical tables** (estimates marked `"f"`) in `data/psa_special_release/` ($159$ files). Every run of `uv run lfs.py` executes `verify_against_psa_official()` in [`psa.py`](https://github.com/KingSSIBAL/LFS-2025-Analysis/blob/main/psa.py), which skips preliminary `__PR_` files and checks every comparable figure and standard error against the final Special Release tables in `data/psa_special_release/`:

* **`0B_PSA_Validation_Monthly.csv`** ($3,576$ `PASS` rows, $0$ failures): Verifies every monthly point estimate and rate across all $12$ rounds.
* **`0A_PSA_Validation_Annual.csv`** ($657$ total rows, $0$ failures):
  * $77$ `PASS` rows (`2025 Annual Avg (mean of 12 monthly finals)`): National and demographic/sectoral $12$-month averages.
  * $576$ `PASS` rows (`Q-avg Jan/Apr/Jul/Oct`): Regional $4$-quarter averages across all $18$ regions.
  * $1$ `INFO` row (`2025 Annual (Annual Special Release 2025p)`): Compares our $12$-month final mean employed count ($49,024.506\text{k}$) against PSA's preliminary `00_Annual__Table 2` release (`2025p`, which was published before all monthly rounds were finalized and sits $11.3\text{k}$ higher).
  * $3$ `N/A` rows (`N/A (not published every month; no comparable period average)`): Documents `wm_broad` (`visible` and `invisible` by broad sector, published only in the $8$ non-quarterly rounds) and `wm_major` (`underemp` by major industry, published only in the $4$ quarterly rounds).
* **Standard Error Assertions & Why Both Median and Mean/MAPE/Range Are Reported** ($84$ cells): `psa.py` asserts that every single two-stage Taylor linearization standard error (`se_underemp_k`) matches PSA's published `Standard Error` column within $\pm 5\%$ nationally ($12$ months: **median $0.9999\times$, mean $1.0020\times$, MAPE $0.30\%$, range $0.997\text{--}1.021\times$**) and within $\pm 15\%$ regionally ($72$ cells: **median $0.9992\times$, mean $0.9996\times$, MAPE $0.22\%$, range $0.991\text{--}1.040\times$**; quarterly medians: Jan $0.9992\times$, Apr $0.9994\times$, Jul $0.9974\times$, Oct $0.9994\times$). The median ratio is reported alongside the mean, MAPE, and hard range gate because it is invariant to single-round sample-size shifts and published rounding quantization on small regional denominators.

| Verifier Key in `psa.py` | Official PSA Special Release Table Title Pattern | Rounds Published | Verified Indicators & Dimensions |
|---|---|---|---|
| `status_sex_age` | *Percent Distribution of Population 15 Years Old and Over by Employment Status, Sex, and Age* | All $12$ months | Employed & underemployed totals + SEs; by sex and $6$ age groups |
| `status_region_sex` | *...by Employment Status, Region, and Sex* | Quarterly ($1, 4, 7, 10$) | Employed & underemployed totals + SEs across $18$ regions $\times$ sex |
| `hours_occ` | *Employed Persons by Total Hours Worked and Major Occupation* | All $12$ months | Not at work, worked $<40$ hrs, worked $40+$ hrs (`notwork`, `lt40`, `ge40`) |
| `hours_region_sex` | *Employed Persons by Total Hours Worked, Region, and Sex* | Quarterly ($1, 4, 7, 10$) | Hours worked categories across $18$ regions |
| `class_broad` | *Employed Persons by Class of Worker and Broad Industry Group* | All $12$ months | Employed totals across AFF, Industry, and Services |
| `sex_major_ind` | *Employed Persons by Sex, (Region,) and Major Industry* | All $12$ months | Employed across $22$ major industries (and region $\times$ broad sector in quarterly rounds) |
| `educ_sex_age` | *Employed Persons by Highest Grade Completed, Sex, and Age* | All $12$ months | Employed across all $11$ official education categories (`EDUC_ORDER`) |
| `educ_region_sex` | *Employed Persons by Highest Grade Completed, Region, and Sex* | Quarterly ($1, 4, 7, 10$) | Employed across $18$ regions $\times$ $11$ education categories |
| `wm_hours_sex` | *Employed Persons Wanting More Hours of Work by Total Hours Worked and Sex* | All $12$ months | Underemployed, visibly ($<40$ hrs), and invisibly ($\ge 40$ hrs) by sex |
| `wm_hours_region` | *Employed Persons Wanting More Hours of Work by Total Hours Worked, Region, and Sex* | Quarterly ($1, 4, 7, 10$) | Underemployed, visible, and invisible across $18$ regions $\times$ sex |
| `wm_broad` | *Employed Persons Wanting More Hours of Work by Total Hours Worked and Broad Industry* | Monthly ($8$ non-Q rounds) | Underemployed, visible, and invisible across AFF, Industry, and Services |
| `wm_major` | *Employed Persons Wanting More Hours of Work by Major Industry* | Quarterly ($1, 4, 7, 10$) | Underemployed across all $22$ major industries (and $3$ broad sectors) |

Rounding tolerances: PSA prints totals in thousands to $3$ decimal places and child breakdowns as percentages to $1\text{--}3$ decimal places; rebuilding a child level as $\text{pct} \times \text{total}$ introduces at most $0.25\text{k}$ rounding difference, guarded by strict pass/fail assertions of `TOL_LEVEL_K = 1.0k` and `TOL_RATE_PP = 0.05 pp`.

### 10.2 Inventory of All 43 Generated CSV Tables (`output/tables/*.csv`) {#table-inventory}

All $43$ CSV tables below are also compiled as separate worksheets (alongside a `README` sheet = $44$ sheets total) in [`output/LFS_2025_Stratified_Underemployment_Tables.xlsx`](output/LFS_2025_Stratified_Underemployment_Tables.xlsx):

| Table Family | CSV / Sheet Names | Stratification Dimensions | Divisor ($K$) | Extra Schema Columns & Verification Note |
|---|---|---|---|---|
| **PSA Validation (`2` tables)** | `0A_PSA_Validation_Annual`, `0B_PSA_Validation_Monthly` | Indicator $\times$ Group $\times$ Period/Month | $K=12$, $K=4$, or $K=1$ | `PUF_Calculated`, `PSA_Official`, `Diff`, `Status` ($4,229$ `PASS` checks) |
| **Broad Sector Breakdowns (`10` tables)** | `1A`/`1B` (Sector), `2A`/`2B` (Sector $\times$ Sex), `3A`/`3B` (Sector $\times$ Age), `4A`/`4B` (Sector $\times$ Age $\times$ Sex), `5A`/`5B` (Sector $\times$ Educ) | `A` = Annual mean, `B` = Monthly granular ($12$ months) | `A`: $K=12$; `B`: $K=1$ | `1B` includes `worked_lt40_k`, `worked_40plus_k`, `job_not_at_work_k`; all carry `se_underemp_k`, `se_underemp_rate_pp`, `cv_underemp_pct`, `reliability` |
| **Residence Region `R*` (`10` tables)** | `R0A`/`R0B` (Region), `R1A`/`R1B` ($\times$ Sex), `R2A`/`R2B` ($\times$ Sector), `R3A`/`R3B` ($\times$ Age), `R4A`/`R4B` ($\times$ Educ) | `A` = Quarterly avg (`Qavg`), `B` = Quarterly (`Jan, Apr, Jul, Oct`) | `A`: $K=4$; `B`: $K=1$ | Includes unweighted sample count `n_unweighted`; `R0` and `R1` checked directly vs. PSA regional tables |
| **Workplace Region `W*` (`10` tables)** | `W0A`/`W0B` (Work Region), `W1A`/`W1B` ($\times$ Sex), `W2A`/`W2B` ($\times$ Sector), `W3A`/`W3B` ($\times$ Age), `W4A`/`W4B` ($\times$ Educ) | `A` = Annual mean ($12$ months), `B` = Monthly ($12$ months) | `A`: $K=12$; `B`: $K=1$ | Includes `n_unweighted`; derived from `PUFC12A_PROVMUN`; sums to checked national totals |
| **Research Questions `RQ1`–`RQ3` (`11` tables)** | `RQ1_RQ2_a_Age`, `_b_Sex`, `_c_Education`, `_d1_Broad_Industry`, `_d2_Major_Industry`; `RQ3_Monthly_Overall`, `_by_Age`, `_by_Sex`, `_by_Educ`, `_by_Sector`, `_by_Major_Ind` | `RQ1_RQ2_*` = Annual mean; `RQ3_Monthly_*` = Monthly ($12$ months) | `RQ1_RQ2`: $K=12$; `RQ3`: $K=1$ | Direct source tables for Figures RQ1, RQ2, and RQ3 |

### 10.3 Worked Numerical Walkthrough

To trace how the SQL and Python pipeline transforms raw household weights into published rows with standard errors and reliability flags, consider three benchmark cells from the verified 2025 tables:

1. **National Annual Headline** (`0A_PSA_Validation_Annual` & `1A_Sector_Annual`, $K = 12$ months):
   * **Point Estimates:** Across the $12$ monthly rounds, the exact mean employed total is $\bar{X} = 49,024.506\text{k}$ ($49.0\text{M}$) and the mean underemployed total is $\bar{Y} \approx 5,834\text{k}$ ($5.8\text{M}$, or $11.9\%$ of employed).
   * **Standard Error Validation:** Across the $12$ individual monthly rounds, the ratio of our two-stage design standard error $\text{SE}(\hat{Y} _ m)$ to PSA's published Special Release standard error achieves a median of $0.9999\times$ (mean $1.0020\times$, MAPE $0.30\%$, range $0.997\times\text{--}1.021\times$).

2. **Regional Quarterly Estimate** (`R0A_RReg_Qavg` / `R0B_RReg_Quarterly`, $K = 4$ quarterly rounds):
   * **Point Estimates:** For Region XII (SOCCSKSARGEN), averaging the $4$ quarterly rounds (January, April, July, October) yields the highest regional underemployment rate in the country at $\bar{R} _ {\text{XII}} = 28.8\%$, compared with $\bar{R} _ {\text{XI}} = 5.3\%$ in neighboring Davao.
   * **Standard Error Validation:** Across all $4 \times 18 = 72$ quarterly regional cells, our two-stage standard errors match PSA's published regional standard errors to a median ratio of $0.9992\times$ (mean $0.9996\times$, MAPE $0.22\%$, range $0.991\times\text{--}1.040\times$).

3. **Unreliable Small Subgroup** (`RQ1_RQ2_c_Education`, Post-Secondary Undergraduates, $K = 12$ months):
   * **Why it is flagged `**`:** Post-secondary non-tertiary undergraduates (`PUFC07_GRADE` codes `40001`–`40003` and `50001`–`50003`) represent a tiny fraction of the workforce where most PSU clusters contain zero respondents ($z _ {y,p,a} = 0$), triggering the small-cell variance effect derived in Section 8.
   * **CV Calculation:** With $\text{SE}(\bar{Y} _ d) = 0.227 \, \bar{Y} _ d$, dividing the pooled standard error by the small subgroup headcount estimate yields $\text{CV}(\bar{Y} _ d) = \frac{\text{SE}(\bar{Y} _ d)}{\bar{Y} _ d} \times 100 = 22.7\% > 20\%$.
   * **Visual & Table Encoding:** Because $\text{CV} > 20\%$, `tables.py` labels the row `unreliable (CV>20%)` and `figures.py` renders the bar with triple hatching (`///`), $45\%$ opacity, and a `**` suffix.

$\leftarrow$ [Back to Main Report](index.html)

<style>
  table { display: block; max-width: 100%; overflow-x: auto; }
</style>
<script>
  window.MathJax = {
    tex: { inlineMath: [['$', '$'], ['\\(', '\\)']], displayMath: [['$$', '$$'], ['\\[', '\\]']] }
  };
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>