# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.1.0",
#     "matplotlib>=3.9.0",
#     "numpy>=1.26.0",
#     "openpyxl>=3.1.5",
#     "pandas>=2.2.0",
#     "pyarrow>=17.0.0",
#     "seaborn>=0.13.0",
#     "xlrd>=2.0.1",
# ]
# ///
"""Philippine LFS 2025: underemployment by sector, sex, age, education and region, validated against PSA.
Source tags like [TN p.8] point to the SOURCES list at the end of these notes.

CODE (run `uv run lfs.py`)
  lfs.py        these notes + the run order
  tables.py     PUF -> Parquet, all tables, standard errors, reliability flags, psa_check notes
  lfs_view.sql  the analysis view (definitions, recodes) and the variance design (117 strata, PSUs, FPC)
  psa.py        reads PSA's published tables and checks every comparable figure and SE against ours
  figures.py    all figures, including the regional map

PIPELINE
  1. Stack the 12 monthly PUF CSVs into one Parquet (monthly and quarterly questionnaires number questions
     differently) [PUF], [DICT].
  2. Build one row per employed person aged 15+ with PSA's own definitions:
       population    = 15+ excluding overseas workers [TN p.1]
       employed      = PUFNEWEMPSTAT 1 (PSA's derived status) [TN p.1], [DICT]
       underemployed = employed and wants more hours (PUFC20_PWMORE = 1) [TN p.1-2]
       visible       = underemployed and worked < 40 hours (incl. "with a job, not at work") [TN p.2]
       invisible     = underemployed and worked 40+ hours (the rest of the underemployed) [TN p.1-2]
       weight        = PUFPWGTPRV (final calibrated person weight) [TN p.5-6], [DICT]
       counts        = SUM(weight) [TN p.6-7]; rates = ratio of weighted totals R = Y/X [TN p.7]
  3. Tables: annual = mean of the 12 monthly estimates (equals the mean of PSA's 12 monthly finals exactly [SR]).
     R* region of residence uses only Jan/Apr/Jul/Oct: 4 replicates, "National and Regional Level Estimate"
     [TN p.2, p.4]. W* region of workplace uses all 12 months.
  4. Every table gets psa_check (is it verified against PSA, and why/why not) plus a standard error, CV and a
     reliability flag computed with the Technical Notes formulas for totals and ratios [TN p.8].
  5. Every number PSA publishes in its final Special Release tables is recomputed and compared (4,229 checks) [SR].

WHAT MATCHES PSA (2025 PUF run, B = 250; every run re-checks the point estimates and SEs, and stops if off)
  All point estimates (counts, rates, distributions): 3,576 monthly + 77 annual + 576 regional checks, 0 failures [SR].
  Tolerance is 1.0k / 0.05 pp only because PSA prints rounded values (largest gap 0.25k = PSA rounding a % to 3 dp).
  Standard errors of underemployed vs. the "Standard Error" columns of the same PSA tables [SR]:
    national, 12 months:    median 0.999x PSA, range 0.973-1.020x (run stops if any month is > 5% off)
    regional, 72 cells:     median 0.992x PSA, range 0.875-1.040x (run stops if any cell is > 15% off)
    Only July is low (regional median 0.969x vs. ~0.992x in Jan/Apr/Oct); worst cell CAR July 0.875x. See B below.

WHY WE CANNOT MATCH PSA 100%
  Point estimates
  - Annual 2025p release [SR-A]: 11.3k below the mean of PSA's own 12 monthly finals. "p" = preliminary; final
    estimates come out about six months after collection [TN p.9], so it is reported as INFO, not pass/fail.
  Standard errors (the PUF removes design information PSA uses internally)
  - Province/HUC of residence is the sampling stratum (117 domains treated as strata [TN p.3, p.8]) but the PUF has
    only region, and only in quarterly rounds [DICT]. We infer it from the province of WORK of each PSU's workers,
    then repair it from neighbouring PSUs: PSUs are listed in geographic order within each domain [TN p.3], and
    household IDs follow that order. Commuter-heavy PSUs or PSUs at a domain boundary can still be misassigned.
  - PSU codes repeat across domains [DICT]; we rebuild PSUs as runs of consecutive households with the same
    replicate + PSU code. We get 2,965 PSUs in January vs. 2,940 in the design table [TN p.4], so a few are split.
  - B_pa (housing units in each PSU) and A_p (PSUs in each domain) are frame counts [TN p.5] that are not released.
    The base weight is (A_p / a_p) x (B_pa / b_pa) [TN p.5], so the weight only reveals their product, never each
    one. We use B = 250, the midpoint of "about 100 to 400 households" per PSU [TN p.3], and A_p = weighted
    households / 250. This drives the largest gaps: July (largest sample, so the FPC matters most) is 2.7% below
    PSA; Aug/Dec ~2% above.
  - Weights are adjusted for non-response and calibrated to projected age-sex population totals [TN p.5-6]. The PUF
    gives only the final weight, not the adjustment factors, so their small effect on variance cannot be reproduced.
  - The 2nd-stage unit is the housing unit; in a housing unit with more than 3 households only 3 are sampled
    [TN p.3, p.5]. The PUF has no housing-unit ID, so we treat each household as its own sampled unit. Households
    sharing a housing unit are alike, so this slightly understates within-PSU clustering.
  - PSA computes SEs "using statistical programs" with Taylor linearization [TN p.7]; the exact software settings
    (e.g. how single-PSU strata are handled) are not published. We give such strata zero variance.
  Things PSA does not publish at all (only checked by adding up to totals that ARE checked) [SR]
  - Underemployment by education; sector x sex/age/education; region x age/sector/education underemployment.
  - Anything by region of WORKPLACE (W* tables), and any regional figure for the 8 non-quarterly months
    (those rounds have 1 replicate, designed for national estimates only [TN p.2, p.4]).
  Reliability flag cut-offs (CV <= 10% reliable, 10-20% use with caution, > 20% unreliable) are NOT in the
  Technical Notes. They follow the bands used in PSA/NSCB small-area poverty statistics [CV]; check the exact
  PSA document before citing them in a paper.

SOURCES
  [TN]   PSA, "Technical Notes: Labor Force Survey" (docs/Technical Notes -LFS_0.pdf). Page numbers are the PDF's own
         "Page X of 11": p.1-2 concepts; p.2-4 sampling design, domains, replicates; p.5-6 weights; p.6-7 totals and
         ratios; p.7-8 sampling error formulas; p.9 release of final estimates.
  [PUF]  PSA, LFS Public Use Files, January-December 2025 (data/puf/, original zips in data/zips/).
  [DICT] PSA, LFS 2025 PUF data dictionaries and CSPro dictionaries (docs/metadata/*.xlsx, *.dcf); questionnaires
         in docs/questionnaires/.
  [SR]   PSA, LFS Special Release, final statistical tables ("f"), each 2025 round (data/psa_special_release/).
  [SR-A] PSA, 2025 Annual LFS release, Table 2, "Annual 2025p" column (data/psa_special_release/00_Annual__*).
  [GEO]  Province boundaries for the region map: faeldon/philippines-json-maps, latest/geojson/regions/lowres (MIT
         licence), merged into data/geo/ph_provinces_lowres.geojson. Each province is coloured by the region the 2025
         PUF assigns it (Sulu = BARMM in 2025, although the boundary file already places it in Region IX).
  [CV]   CV bands as used for PSA/NSCB provincial and small-area poverty estimates; see e.g. PIDS/EconStor
         discussion papers on Philippine small-area poverty estimation. Secondary source, not verified against a
         PSA issuance.
"""

import duckdb
import pandas as pd

from figures import generate_figures, generate_region_map, generate_rq_figures
from psa import verify_against_psa_official
from tables import (OUT_DIR, ROOT_DIR, build_consolidated_parquet, compute_region_tables, compute_rq_tables,
                    compute_tables, create_analytical_view)

if __name__ == "__main__":
    con = duckdb.connect()
    build_consolidated_parquet(con)        # 12 monthly CSVs -> one Parquet
    create_analytical_view(con)            # analysis view + variance design (lfs_view.sql)
    tables = compute_tables(con)           # sector x sex/age/education tables
    region_tables = compute_region_tables(con)
    rq_tables = compute_rq_tables(con)     # research questions 1-3
    generate_figures(tables)
    generate_region_map(con, region_tables)
    generate_rq_figures(rq_tables)
    val_tables = verify_against_psa_official(con, rq_tables["RQ3_Monthly_Overall"], region_tables["R0B_RReg_Quarterly"])

    excel_path = OUT_DIR / "LFS_2025_Stratified_Underemployment_Tables.xlsx"
    readme = pd.DataFrame({"Notes (from lfs.py docstring)": (__doc__ or "").strip().splitlines()})
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        readme.to_excel(writer, sheet_name="README", index=False)  # methods + why we can't match PSA 100%
        for sheet_name, df in {**tables, **region_tables, **rq_tables, **val_tables}.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"\nPipeline complete! Wrote {excel_path.relative_to(ROOT_DIR)} in a single pass.")
