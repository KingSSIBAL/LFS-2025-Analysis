# Underemployment in the Philippines, 2025 (PSA Labor Force Survey)

Who is underemployed (employed but wanting more hours of work), by sector, sex, age, education and region, from the 12 monthly 2025 LFS Public Use Files. Every figure PSA publishes is recomputed and checked against PSA's final Special Release tables (4,229 point-estimate checks and 84 standard-error checks, all pass). Standard errors follow the PSA Technical Notes ($0.9999\times$ national median, $0.30\%$ MAPE; $0.9992\times$ regional median, $0.22\%$ MAPE).

* **Live Report:** [`index.html`](https://kingssibal.github.io/LFS-2025-Analysis/) (source: [`index.md`](index.md))

* **Mathematical Methodology, PSA Survey Plan & PUF Metadata:** [`methodology.html`](https://kingssibal.github.io/LFS-2025-Analysis/methodology.html) (source: [`methodology.md`](methodology.md))

* **Code & Variance Design Notes:** see [`lfs.py`](lfs.py), [`tables.py`](tables.py), [`lfs_view.sql`](lfs_view.sql), [`psa.py`](psa.py), and [`figures.py`](figures.py) (also written to the `README` sheet of the Excel output).

## Outputs (in this repo)

* `output/LFS_2025_Stratified_Underemployment_Tables.xlsx` — all 44 tables + `README` sheet (45 sheets total); `0A`/`0B` = PSA point-estimate validation, `0C` = PSA standard-error validation

* `output/tables/*.csv` — the 44 tables as CSV; substantive tables carry `psa_check`, `se_underemp_k`, `se_visible_k`, `se_invisible_k`, `se_underemp_rate_pp`, `cv_underemp_pct`, `cv_visible_pct`, `cv_invisible_pct`, and `reliability`

* `output/figures/*.png` — 11 300-DPI figures (`fig1`–`fig8` and `fig_RQ1`–`fig_RQ3`, with CV hatching flags on sparse subgroups)

## Re-running

The PSA microdata is not distributed in this repository under PSA Data Archive terms of use.

1. Download the 12 **LFS 2025 Public Use Files** from the PSA Data Archive (https://psada.psa.gov.ph).

2. Place the CSVs in `data/puf/` named `LFS PUF <Month> 2025.CSV` (e.g. `LFS PUF January 2025.CSV`).

3. Run the full pipeline (PUF $\to$ Parquet $\to$ DuckDB tables $\to$ 11 figures $\to$ 4,229 PSA point checks + 84 SE checks $\to$ Excel):

   ```
   uv run lfs.py
   
   ```

4. Force a fresh Parquet rebuild from the 12 CSVs at any time (otherwise rebuilt automatically whenever a CSV is newer than the cached Parquet):

   ```
   uv run lfs.py --rebuild
   
   ```

5. Redraw all 11 PNG figures in \~2 seconds directly from the saved CSVs in `output/tables/*.csv` without re-running PUF ingestion or Excel validation:

   ```
   uv run lfs.py --plots-only
   
   ```

PSA's published final Special Release tables used for validation are included in `data/psa_special_release/` (preliminary Press Release tables are archived in `data/psa_press_release/`).

Data: Philippine Statistics Authority, Labor Force Survey 2025 Public Use Files. The analysis and any errors are ours.