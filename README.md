# Underemployment in the Philippines, 2025 (PSA Labor Force Survey)

Who is underemployed (employed but wanting more hours of work), by sector, sex, age, education and region, from
the 12 monthly 2025 LFS Public Use Files. Every figure PSA publishes is recomputed and checked against PSA's final
tables (4,229 checks, all pass). Standard errors follow the PSA Technical Notes.

**Report:** [Live site](https://kingssibal.github.io/LFS-2025-Analysis/) ([`index.md`](index.md) source).

**Methods, sources and why the results can't match PSA 100%:** see the notes at the top of [`lfs.py`](lfs.py)
(also the `README` sheet of the Excel output).

## Outputs (in this repo)
- `output/LFS_2025_Stratified_Underemployment_Tables.xlsx` — all tables, one per sheet; `0A`/`0B` = PSA validation
- `output/tables/*.csv` — the same tables as CSV; each has `psa_check`, `se_underemp_k`, `cv_underemp_pct`, `reliability`
- `output/figures/*.png` — 300-DPI figures (`fig_RQ1_*`, `fig_RQ2_*`, `fig_RQ3_*` answer research questions 1–3)

## Re-running
The PSA microdata isn't in this repo, because the PSA licence doesn't allow redistributing it.
1. Download the 12 **LFS 2025 Public Use Files** from the PSA Data Archive (https://psada.psa.gov.ph).
2. Put the CSVs in `data/puf/` as `LFS PUF <Month> 2025.CSV` (e.g. `LFS PUF January 2025.CSV`).
3. `uv run lfs.py` (needs [uv](https://docs.astral.sh/uv/); dependencies are declared inside `lfs.py`).

PSA's published tables used for validation are included in `data/psa_special_release/`.

Data: Philippine Statistics Authority, Labor Force Survey 2025 Public Use Files. The analysis and any errors are ours.

