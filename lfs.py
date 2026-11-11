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

CODE
  uv run lfs.py               full build (PUF -> Parquet -> tables -> figures -> PSA validation -> Excel)
  uv run lfs.py --rebuild     force Parquet rebuild from the 12 monthly CSVs before running full build
  uv run lfs.py --plots-only  redraw all 11 figures directly from saved output/tables/*.csv in ~2s

  lfs.py        these notes + the CLI entrypoint and execution order
  tables.py     PUF -> Parquet, all tables, 2-stage standard errors, reliability flags, psa_check notes
  lfs_view.sql  the analysis view (definitions, recodes) and the variance design (117 strata, PSUs, FPC)
  psa.py        reads PSA's published tables and checks every comparable figure and SE against ours
  figures.py    all 300-DPI figures, including the regional map

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
  4. Every table gets psa_check (is it verified against PSA, and why/why not) plus standard errors (total, visible,
     invisible, and rate), CVs, and a reliability flag computed with the Technical Notes formulas [TN p.8].
  5. Every number PSA publishes in its final Special Release tables is recomputed and compared (4,229 point-estimate
     checks in 0A/0B + 84 standard-error checks in 0C_PSA_Validation_SE.csv) [SR].

WHAT MATCHES PSA (2025 PUF run, urban B = 25 / rural B = 15; every run re-checks point estimates and SEs)
  All point estimates (counts, rates, distributions): 3,576 monthly + 77 annual + 576 regional checks, 0 failures [SR].
  Tolerance is 1.0k / 0.05 pp only because PSA prints rounded values (largest gap 0.25k = PSA rounding a % to 3 dp).
  Standard errors of underemployed vs. the "Standard Error" columns of the same PSA tables [SR]:
    national, 12 months:    median 0.9999x PSA (mean 1.0020x, MAPE 0.30%), range 0.997-1.021x (stops if > 5% off)
    regional, 72 cells:     median 0.9992x PSA (mean 0.9996x, MAPE 0.22%), range 0.991-1.040x (stops if > 15% off)
    Quarterly regional medians: Jan 0.9992x, Apr 0.9994x, Jul 0.9974x, Oct 0.9994x.

WHY WE CANNOT MATCH PSA 100%
  Point estimates
  - Annual 2025p release [SR-A]: 11.3k below the mean of PSA's own 12 monthly finals. "p" = preliminary; final
    estimates come out about six months after collection [TN p.9], so it is reported as INFO, not pass/fail.
  Standard errors (the PUF removes design information PSA uses internally)
  - Province/HUC of residence is the sampling stratum (117 domains treated as strata [TN p.3, p.8]) but the PUF has
    only region, and only in quarterly rounds [DICT]. We infer it from the province of WORK of each PSU's workers
    (constrained to the household's residence region PUFREG in quarterly rounds and to the 3-step smoothed region
    block eff_reg in monthly rounds), then repair commuter/empty PSUs using a 3-step neighbor smoother within the
    same region: PSUs are listed in geographic order within each domain [TN p.3], and household IDs follow that order.
  - PSU codes repeat across domains [DICT]; we rebuild PSUs as runs of consecutive households with the same
    replicate + PSU + region code, and reunite split runs that share the same domain, replicate, and PSU code within
    150 household IDs (<= 30 combined households) via gap-and-islands clustering.
  - B_pa (housing units in each PSU) and A_p (PSUs in each domain) are frame counts [TN p.5] that are not released.
    The base weight is (A_p / a_p) x (B_pa / b_pa) [TN p.5], so the weight only reveals their product, never each
    one. We use effective constants urban B_tilde = 25 and rural B_tilde = 15 (from PUFURB2020 [TN p.3, p.7]), and
    A_p = SUM(psu_hh / b_frame) within each month and stratum. We report both the median and mean SE ratio alongside
    the strict cell-by-cell range gate because the median is invariant to single-month sample-size shifts and
    small-cell published rounding quantization.
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
         PUF assigns it (NIR = Negros Occidental, Bacolod, Negros Oriental, Siquijor; Sulu = BARMM in 2025 PUF).
  [CV]   CV bands as used for PSA/NSCB provincial and small-area poverty estimates; see e.g. PIDS/EconStor
         discussion papers on Philippine small-area poverty estimation. Secondary source, not verified against a
         PSA issuance.
"""
import sys

import duckdb
import pandas as pd

from figures import generate_figures, generate_region_map, generate_rq_figures
from psa import verify_against_psa_official
from tables import (
    OUT_DIR,
    PARQUET_PATH,
    ROOT_DIR,
    TAB_DIR,
    _DOM_EXPR,
    build_consolidated_parquet,
    compute_region_tables,
    compute_rq_tables,
    compute_tables,
    create_analytical_view,
)

# Minimum set of saved CSV stems required to redraw all 11 figures in `--plots-only` mode
REQUIRED_PLOT_TABLES = (
    "1A_Sector_Annual",
    "1B_Sector_Monthly",
    "2A_Sector_Sex_Annual",
    "3A_Sector_Age_Annual",
    "4A_Sector_Age_Sex_Annual",
    "5A_Sector_Educ_Annual",
    "R0A_RReg_Qavg",
    "RQ1_RQ2_a_Age",
    "RQ1_RQ2_b_Sex",
    "RQ1_RQ2_c_Education",
    "RQ1_RQ2_d1_Broad_Industry",
    "RQ3_Monthly_Overall",
)


def main(argv: list[str] | None = None) -> int:
    """Run the full 2025 LFS analytical pipeline or fast `--plots-only` figure regeneration."""
    args = set(sys.argv[1:] if argv is None else argv)
    unknown = {a for a in args if a not in {"--plots-only", "--rebuild"}}
    if unknown:
        raise SystemExit(f"Unknown CLI option(s): {sorted(unknown)}. Valid flags: --plots-only, --rebuild")

    with duckdb.connect() as con:
        # shortcut: `uv run lfs.py --plots-only` redraws all 11 figures from output/tables/*.csv in ~2s
        if "--plots-only" in args:
            cached = {p.stem: pd.read_csv(p) for p in TAB_DIR.glob("*.csv")}
            missing = [k for k in REQUIRED_PLOT_TABLES if k not in cached]
            if missing:
                raise FileNotFoundError(
                    f"Cannot run --plots-only; missing CSV table(s) in {TAB_DIR}: {', '.join(missing)}"
                )

            if PARQUET_PATH.exists():
                p_str = PARQUET_PATH.as_posix().replace("'", "''")
                con.execute(
                    "CREATE OR REPLACE TABLE work_dom_region AS "
                    "SELECT work_dom, arg_max(rcode, w) AS wcode FROM ("
                    f"  SELECT {_DOM_EXPR} AS work_dom, TRIM(PUFREG) AS rcode, "
                    "    SUM(TRY_CAST(TRIM(PUFPWGTPRV) AS DOUBLE)) AS w "
                    f"  FROM '{p_str}' "
                    "  WHERE NULLIF(TRIM(PUFREG), '') IS NOT NULL AND TRIM(PUFC12A_PROVMUN) <> '' "
                    "  GROUP BY 1, 2"
                    ") GROUP BY 1"
                )
            else:
                # Fallback mapping when PUF Parquet is absent: NIR ('18' = Negros Occ, Bacolod, Negros Or, Siquijor)
                # under RA 12000, plus Sulu ('66' -> BARMM '19' in the 2025 PUF frame).
                con.execute(
                    "CREATE OR REPLACE TABLE work_dom_region AS "
                    "SELECT * FROM (VALUES "
                    "  ('45', '18'), ('4501', '18'), ('46', '18'), ('61', '18'), ('66', '19')"
                    ") t(work_dom, wcode)"
                )

            generate_figures(cached)
            generate_region_map(con, cached)
            generate_rq_figures(cached)
            print("\nFast plot-only rebuild complete!")
            return 0

        build_consolidated_parquet(con, force_rebuild="--rebuild" in args)
        create_analytical_view(con)
        tables = compute_tables(con)
        region_tables = compute_region_tables(con)
        rq_tables = compute_rq_tables(con)
        generate_figures(tables)
        generate_region_map(con, region_tables)
        generate_rq_figures(rq_tables)
        val_tables = verify_against_psa_official(
            con,
            rq_tables["RQ3_Monthly_Overall"],
            region_tables["R0B_RReg_Quarterly"],
        )

        excel_path = OUT_DIR / "LFS_2025_Stratified_Underemployment_Tables.xlsx"
        readme = pd.DataFrame({"Notes (from lfs.py docstring)": (__doc__ or "").strip().splitlines()})
        tmp_excel = excel_path.with_suffix(".xlsx.tmp")
        try:
            with pd.ExcelWriter(tmp_excel, engine="openpyxl") as writer:
                readme.to_excel(writer, sheet_name="README", index=False)
                for sheet_name, df in {**tables, **region_tables, **rq_tables, **val_tables}.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            tmp_excel.replace(excel_path)
        except Exception:
            tmp_excel.unlink(missing_ok=True)
            raise

        print(f"\nPipeline complete! Wrote {excel_path.relative_to(ROOT_DIR)} in a single pass.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())