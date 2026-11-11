"""Survey data: PUF -> Parquet, the analysis view and variance design, all tables and their standard errors."""
from pathlib import Path
import re

import duckdb
import numpy as np
import pandas as pd

# ==============================================================================
# CONFIGURATION & PATHS
# ==============================================================================
ROOT_DIR = Path(__file__).resolve().parent
PUF_DIR = ROOT_DIR / "data" / "puf"
PSA_DIR = ROOT_DIR / "data" / "psa_special_release"
PARQUET_PATH = PUF_DIR / "LFS_PUF_2025_Consolidated.parquet"
# Province boundaries (WGS84), merged from faeldon/philippines-json-maps latest/geojson/regions/lowres (MIT).
VIEW_SQL = ROOT_DIR / "lfs_view.sql"
GEO_PATH = ROOT_DIR / "data" / "geo" / "ph_provinces_lowres.geojson"
OUT_DIR = ROOT_DIR / "output"
FIG_DIR = OUT_DIR / "figures"
TAB_DIR = OUT_DIR / "tables"
for _d in (PUF_DIR, OUT_DIR, FIG_DIR, TAB_DIR):
    _d.mkdir(parents=True, exist_ok=True)

QUARTERLY_MONTHS = ["January", "April", "July", "October"]
MONTHLY_MONTHS = ["February", "March", "May", "June", "August", "September", "November", "December"]

SECTOR_ORDER = ["Agriculture, Forestry, and Fisheries", "Industry", "Services"]
SECTOR_SHORT = {
    "Agriculture, Forestry, and Fisheries": "Agriculture (AFF)",
    "Industry": "Industry",
    "Services": "Services",
}
SECTOR_COLORS = {"Agriculture, Forestry, and Fisheries": "#2ca25f", "Industry": "#636363", "Services": "#2b5c8f"}
SEX_COLORS = {"Male": "#2b5c8f", "Female": "#d95f02"}

EDUC_ORDER = [
    "No grade completed",
    "Elementary Undergraduate",
    "Elementary Graduate",
    "Junior High Undergraduate",
    "Junior High Completed",
    "Senior High Undergraduate",
    "Senior High Graduate",
    "Post Secondary Undergraduate",
    "Post Secondary Graduate",
    "College Undergraduate",
    "College Graduate",
]

# PSGC region code -> (display name, keyword found in PSA table labels); listed in PSA publication order
REGIONS = [
    ("13", "NCR", "National Capital"),
    ("14", "CAR", "Cordillera"),
    ("01", "Region I (Ilocos)", "Ilocos"),
    ("02", "Region II (Cagayan Valley)", "Cagayan Valley"),
    ("03", "Region III (Central Luzon)", "Central Luzon"),
    ("04", "Region IV-A (CALABARZON)", "CALABARZON"),
    ("17", "MIMAROPA", "MIMAROPA"),
    ("05", "Region V (Bicol)", "Bicol"),
    ("06", "Region VI (Western Visayas)", "Western Visayas"),
    ("18", "NIR (Negros Island)", "Negros Island"),
    ("07", "Region VII (Central Visayas)", "Central Visayas"),
    ("08", "Region VIII (Eastern Visayas)", "Eastern Visayas"),
    ("09", "Region IX (Zamboanga Peninsula)", "Zamboanga"),
    ("10", "Region X (Northern Mindanao)", "Northern Mindanao"),
    ("11", "Region XI (Davao)", "Davao"),
    ("12", "Region XII (SOCCSKSARGEN)", "SOCCSKSARGEN"),
    ("16", "Region XIII (Caraga)", "Caraga"),
    ("19", "BARMM", "BARMM|Bangsamoro"),  # PSA wraps this name over two rows; either line may hold the numbers
]
WORK_REGION_NOTE = (
    "NOT CHECKABLE vs PSA: region of WORKPLACE (from province-of-work code, all 12 months). "
    "PSA publishes region of residence only, and only for Jan/Apr/Jul/Oct (4 replicates); the other 8 months have "
    "1 replicate, designed for national estimates only (PSA LFS Technical Notes), so monthly regional rows are noisy."
)


# ==============================================================================
# STEP 1: CONSOLIDATE 12 LFS PUF 2025 CSVs TO PARQUET VIA DUCKDB
# ==============================================================================
def resolve_files(folder: Path, months: list[str]) -> list[str]:
    """Locate each monthly LFS PUF CSV file (case-insensitive extension) or raise FileNotFoundError."""
    paths = []
    for month in months:
        matches = sorted(folder.glob(f"LFS PUF {month} 2025.[cC][sS][vV]"))
        if not matches:
            raise FileNotFoundError(f"Missing file: 'LFS PUF {month} 2025.CSV' in {folder.resolve()}")
        paths.append(str(matches[0]))
    return paths


def build_consolidated_parquet(con: duckdb.DuckDBPyConnection, force_rebuild: bool = False) -> None:
    """Stack all 12 monthly PUF CSVs into a ZSTD Parquet file with mtime invalidation and atomic write."""
    p_str = PARQUET_PATH.as_posix().replace("'", "''")
    csv_candidates = list(PUF_DIR.glob("LFS PUF * 2025.[cC][sS][vV]"))

    if PARQUET_PATH.exists() and not force_rebuild:
        parquet_mtime = PARQUET_PATH.stat().st_mtime
        stale = bool(csv_candidates) and any(f.stat().st_mtime > parquet_mtime for f in csv_candidates)
        if not stale:
            try:
                rows = con.sql(f"SELECT COUNT(*) FROM '{p_str}'").fetchone()[0]
                if rows > 0:
                    print(f"[1/3] Using existing Parquet: {PARQUET_PATH} ({rows:,} rows)")
                    return
            except duckdb.Error:
                print("[1/3] Cached Parquet unreadable; rebuilding from source CSVs...")
        else:
            print("[1/3] Source PUF CSVs are newer than cached Parquet; rebuilding...")

    print("[1/3] Consolidating 12 LFS PUF 2025 CSV files into Parquet...")
    q_files = resolve_files(PUF_DIR, QUARTERLY_MONTHS)
    m_files = resolve_files(PUF_DIR, MONTHLY_MONTHS)

    tmp_path = PARQUET_PATH.with_suffix(".parquet.tmp")
    tmp_str = tmp_path.as_posix().replace("'", "''")
    # Quarterly rounds use the long questionnaire (has PUFREG + extra questions); monthly rounds use a short one whose
    # question numbers are shifted (e.g. PUFC19_PWMORE there = PUFC20_PWMORE here). Rename monthly to quarterly names;
    # columns monthly rounds lack (PUFREG etc.) become NULL. Everything is read as text and cast later.
    try:
        con.execute(
            "COPY ("
            "  WITH combined AS ("
            "    SELECT * FROM read_csv($q_files, all_varchar = true)"
            "    UNION ALL BY NAME "
            "    SELECT "
            "      PUFHHNUM, PUFPWGTPRV, PUFSVYMO, PUFSVYYR, PUFPSU, PUFRPL, "
            "      PUFHHSIZE, PUFC01_LNO, PUFC03_REL, PUFC04_SEX, PUFC05_AGE, PUFC06_MSTAT, PUFC07_GRADE, "
            "      PUFC08_CONWR AS PUFC10_CONWR, PUFC09_WORK AS PUFC11_WORK, PUFC09A_WORK AS PUFC11A_ARRANGEMENT, "
            "      PUFC10_JOB AS PUFC12_JOB, PUFC11A_PROVMUN AS PUFC12A_PROVMUN, PUFC13_PROCC AS PUFC14_PROCC, "
            "      PUFC15_PKB AS PUFC16_PKB, PUFC16_NATEM AS PUFC17_NATEM, PUFC17_PNWHRS AS PUFC18_PNWHRS, "
            "      PUFC18_PHOURS AS PUFC19_PHOURS, PUFC19_PWMORE AS PUFC20_PWMORE, PUFC20_PLADDW AS PUFC21_PLADDW, "
            "      PUFC20B_FTWORK AS PUFC22_PFWRK, PUFC21_PCLASS AS PUFC23_PCLASS, PUFC22_OJOB AS PUFC26_OJOB, "
            "      PUFC23_THOURS AS PUFC28_THOURS, PUFC24_WWM48H AS PUFC29_WWM48H, PUFC25_LOOKW AS PUFC30_LOOKW, "
            "      PUFC25B_FTWORK AS PUFC31_FLWRK, PUFC26_WYNOT AS PUFC34_WYNOT, PUFC27_AVAIL AS PUFC36_AVAIL, "
            "      PUFC28_PREVJOB AS PUFC38_PREVJOB, PUFC29_YEAR AS PUFC39_YEAR, PUFC29_MONTH AS PUFC39_MONTH, "
            "      PUFC31_POCC AS PUFC41_POCC, PUFC33_QKB AS PUFC43_QKB, PUFNEWEMPSTAT, PUFURB2020 "
            "    FROM read_csv($m_files, all_varchar = true)"
            "  ) "
            "  SELECT * FROM combined "
            "  ORDER BY TRY_CAST(TRIM(PUFSVYYR) AS INTEGER), TRY_CAST(TRIM(PUFSVYMO) AS INTEGER), "
            "           TRY_CAST(TRIM(PUFHHNUM) AS BIGINT), TRY_CAST(TRIM(PUFC01_LNO) AS INTEGER)"
            f") TO '{tmp_str}' (FORMAT PARQUET, COMPRESSION ZSTD);",
            {"q_files": q_files, "m_files": m_files},
        )
        rows = con.sql(f"SELECT COUNT(*) FROM '{tmp_str}'").fetchone()[0]
        tmp_path.replace(PARQUET_PATH)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    print(f"      Saved {PARQUET_PATH} ({rows:,} rows)")


# ==============================================================================
# STEP 2: CREATE ANALYTICAL VIEW (WITH EXACT 1-11 PUFC07_GRADE RECODE)
# ==============================================================================
# Technical Notes pp. 3-4: 117 sampling domains = 81 provinces + Manila (39) + Isabela City (97) + Cotabato City (98)
# + 15 NCR 2nd-4th district HUCs & Pateros (74xx-76xx) + 17 HUCs outside NCR listed below.
_HUCS_OUTSIDE_NCR = (
    "('0202','1102','2217','2226','2230','2402','3022','3504','3747',"
    "'4305','4501','5316','5401','5624','6303','7107','7332')"
)
_DOM_EXPR = (
    f"CASE WHEN LEFT(TRIM(PUFC12A_PROVMUN), 2) IN ('74','75','76') OR TRIM(PUFC12A_PROVMUN) IN {_HUCS_OUTSIDE_NCR} "
    "THEN TRIM(PUFC12A_PROVMUN) ELSE LEFT(TRIM(PUFC12A_PROVMUN), 2) END"
)


def create_analytical_view(con: duckdb.DuckDBPyConnection) -> None:
    """Execute lfs_view.sql to build the 117-domain variance design (hh_psu, psu_frame, stratum_frame) and view."""
    region_rows = ", ".join(f"('{c}', '{n.replace(chr(39), chr(39)*2)}', {i})" for i, (c, n, _) in enumerate(REGIONS, 1))
    con.execute(f"CREATE OR REPLACE TABLE region_names AS SELECT * FROM (VALUES {region_rows}) t(rcode, rname, rord)")

    # Targeted token replacement avoids str.format() KeyError if SQL comments or regexes contain curly braces
    sql = (
        VIEW_SQL.read_text(encoding="utf-8")
        .replace("{parquet}", PARQUET_PATH.as_posix().replace("'", "''"))
        .replace("{dom}", _DOM_EXPR)
    )
    con.execute(sql)

    n_domains = con.sql("SELECT COUNT(*) FROM work_dom_region").fetchone()[0]
    if n_domains != 117:
        raise ValueError(f"Expected all 117 Master Sample domains in work_dom_region, got {n_domains}")
    null_strata = con.sql("SELECT COUNT(*) FROM psu_frame WHERE strat IS NULL").fetchone()[0]
    if null_strata != 0:
        raise ValueError(f"Every PSU requires an assigned stratum; found {null_strata} NULL strata")


# ==============================================================================
# STEP 3: COMPUTE STRATIFIED TABLES (ANNUAL AVERAGE + MONTHLY GRANULAR)
# ==============================================================================
_WEIGHTED_SUMS = (
    "COUNT(*) AS n_unweighted, SUM(wgt) AS emp, "
    "COALESCE(SUM(wgt) FILTER (WHERE pwmore = '1'), 0) AS und, "
    "COALESCE(SUM(wgt) FILTER (WHERE underemp_type LIKE 'Visibly%'), 0) AS vis, "
    "COALESCE(SUM(wgt) FILTER (WHERE underemp_type LIKE 'Invisibly%'), 0) AS inv"
)


def build_stratified_query(
    select_cols: str, group_cols: str, order_cols: str, partition_clause: str = "",
    divisor: float = 12.0, where: str = "", with_n: bool = False,
) -> str:
    """Build SQL for multi-round (annual K=12 or quarterly K=4) stratified point estimates."""
    d = f"{divisor:.1f}"
    n_col = "n_unweighted, " if with_n else ""
    return (
        f"WITH b AS (SELECT {group_cols}, {_WEIGHTED_SUMS} FROM lfs_employed_2025 "
        f"  WHERE broad_sector != 'Not Reported' {where} GROUP BY {group_cols}) "
        f"SELECT {select_cols}, {n_col}"
        f"  emp / {d} / 1e3 AS avg_employed_k, und / {d} / 1e3 AS avg_underemp_k, "
        f"  vis / {d} / 1e3 AS avg_visible_k, inv / {d} / 1e3 AS avg_invisible_k, "
        "  und * 100.0 / NULLIF(emp, 0) AS underemp_rate_pct, "
        "  vis * 100.0 / NULLIF(emp, 0) AS visible_rate_pct, "
        "  inv * 100.0 / NULLIF(emp, 0) AS invisible_rate_pct, "
        "  vis * 100.0 / NULLIF(und, 0) AS visible_share_within_group_pct, "
        "  inv * 100.0 / NULLIF(und, 0) AS invisible_share_within_group_pct, "
        "  vis * 100.0 / NULLIF(SUM(vis) OVER (), 0) AS dist_visible_pct, "
        "  inv * 100.0 / NULLIF(SUM(inv) OVER (), 0) AS dist_invisible_pct, "
        f"  und * 100.0 / NULLIF(SUM(und) OVER ({partition_clause}), 0) AS share_of_sector_underemp_pct, "
        "  und * 100.0 / NULLIF(SUM(und) OVER (), 0) AS share_of_national_underemp_pct "
        f"FROM b ORDER BY {order_cols}"
    )


def build_monthly_stratified_query(
    select_cols: str, group_cols: str, order_cols: str, partition_by_sector: bool = True,
    where: str = "", partition: str | None = None, with_n: bool = False,
) -> str:
    """Build SQL for balanced monthly/quarterly panels (zero-count cells preserved so K-month means match annual)."""
    sector_part = partition or ("PARTITION BY month_num, broad_sector" if partition_by_sector else "PARTITION BY month_num")
    n_col = "n_unweighted, " if with_n else ""
    cols = [c.strip() for c in group_cols.split(",") if c.strip()]
    c_cols = ", ".join(f"c.{c}" for c in cols)
    mc_cols = ", ".join(f"m_c.{c}" for c in cols)
    join_cond = " AND ".join(f"a.{c} IS NOT DISTINCT FROM m_c.{c}" for c in ["month_num", "month_name", *cols])

    return (
        f"WITH filtered AS ("
        f"  SELECT * FROM lfs_employed_2025 WHERE broad_sector != 'Not Reported' {where}"
        f"), "
        f"months AS (SELECT DISTINCT month_num, month_name FROM filtered), "
        f"cats AS (SELECT DISTINCT {group_cols} FROM filtered), "
        f"m_c AS (SELECT m.month_num, m.month_name, {c_cols} FROM months m CROSS JOIN cats c), "
        f"agg AS ("
        f"  SELECT month_num, month_name, {group_cols}, {_WEIGHTED_SUMS} "
        f"  FROM filtered GROUP BY month_num, month_name, {group_cols}"
        f"), "
        f"b AS ("
        f"  SELECT m_c.month_num, m_c.month_name, {mc_cols}, "
        f"    COALESCE(a.n_unweighted, 0) AS n_unweighted, "
        f"    COALESCE(a.emp, 0.0) AS emp, COALESCE(a.und, 0.0) AS und, "
        f"    COALESCE(a.vis, 0.0) AS vis, COALESCE(a.inv, 0.0) AS inv "
        f"  FROM m_c LEFT JOIN agg a ON {join_cond}"
        f") "
        f"SELECT month_num, month_name, {select_cols}, {n_col}"
        "  emp / 1e3 AS employed_k, und / 1e3 AS underemp_k, vis / 1e3 AS visible_k, inv / 1e3 AS invisible_k, "
        "  und * 100.0 / NULLIF(emp, 0) AS underemp_rate_pct, "
        "  vis * 100.0 / NULLIF(und, 0) AS visible_share_pct, "
        "  inv * 100.0 / NULLIF(und, 0) AS invisible_share_pct, "
        "  vis * 100.0 / NULLIF(SUM(vis) OVER (PARTITION BY month_num), 0) AS monthly_dist_visible_pct, "
        "  inv * 100.0 / NULLIF(SUM(inv) OVER (PARTITION BY month_num), 0) AS monthly_dist_invisible_pct, "
        f"  und * 100.0 / NULLIF(SUM(und) OVER ({sector_part}), 0) AS share_of_sector_underemp_pct, "
        "  und * 100.0 / NULLIF(SUM(und) OVER (PARTITION BY month_num), 0) AS share_of_national_underemp_pct "
        f"FROM b ORDER BY month_num, {order_cols}"
    )


# Why each output table is / is not checked against the PSA Special Release (first match wins).
# PSA publishes no underemployment by education, and no sector/region crossed with sex, age or education, so those
# rows are verified indirectly by confirming that their cells sum to checked margins.
PSA_CHECK_NOTES = [
    (r"^W", WORK_REGION_NOTE),
    (r"^R[01]", "CHECKED vs PSA quarterly region tables: employed, underemployed, visible/invisible, by sex (Jan/Apr/Jul/Oct and their average)"),
    (r"^R2", "PARTLY: employed by region x sector CHECKED; underemployed by region x sector NOT published by PSA"),
    (r"^R3", "NOT CHECKED: PSA publishes no region x age tables; region totals are checked and rows add up to them"),
    (r"^R4", "PARTLY: employed by region x education CHECKED; underemployed by education NOT published by PSA"),
    (r"Sector_(Sex|Age|Educ)", "NOT CHECKED: PSA publishes no sector x sex/age/education tables; the sector, sex, age and education totals are checked and rows add up to them"),
    (r"Educ", "PARTLY: employed by education CHECKED; underemployed by education NOT published by PSA (rows add up to checked totals)"),
    (r"Major_Ind", "PARTLY: employed by major industry CHECKED (12 months); underemployed by major industry CHECKED only Jan/Apr/Jul/Oct (published only in quarterly releases)"),
    (r"Sector|Broad_Industry", "CHECKED: employed and underemployed by broad sector (12 months); visible/invisible by sector checked in the 8 monthly-format releases only (not published in Jan/Apr/Jul/Oct)"),
    (r"Age", "CHECKED: employed and underemployed by age group (12 months); visible/invisible by age NOT published by PSA"),
    (r"Sex|Overall", "CHECKED: employed, underemployed and visible/invisible (total and by sex), 12 months"),
]
RELIABILITY_DIMS = ["month_num", "region", "work_region", "broad_sector", "major_industry", "sex", "age_group", "educ_group"]


def annotate_tables(con: duckdb.DuckDBPyConnection, tables: dict[str, pd.DataFrame]) -> None:
    """Attach psa_check and Technical Notes p. 8(a & b) 2-stage SEs (total, visible, invisible, rate) in place."""
    for name, df in tables.items():
        by = [c for c in RELIABILITY_DIMS if c in df.columns]
        annual = "month_num" not in by
        quarterly = re.match(r"R\d", name) is not None  # residence-region tables: Jan/Apr/Jul/Oct only
        div = (4.0 if quarterly else 12.0) if annual else 1.0
        where = "AND region IS NOT NULL" if quarterly else ""
        g = "".join(f"{c}, " for c in by)

        # Page 8(a) totals + Page 8(b) Taylor ratio SEs across the 117 province/HUC strata with 2-stage FPC
        # (B_tilde = 25 urban / 15 rural from psu_frame.b_frame, with residence-region constraint and island PSU reunion).
        # Computes 2-stage variances for employed (x), total underemployed (y), visibly underemployed (yv),
        # and invisibly underemployed (yi), plus Cov(x, y) for the ratio SE.
        w_term = lambda q, z: (
            f"SUM(CASE WHEN pf.b > 1 THEN (1.0 - pf.b / GREATEST(pf.b, pf.b_frame)) * pf.b / (pf.b - 1.0) "
            f"* ({q} - {z} / pf.b) ELSE 0 END)"
        )
        b_term = lambda s2, s1s1, vw: (
            f"SUM((CASE WHEN sf.a_p > 1 THEN (1.0 - sf.f1) * sf.a_p / (sf.a_p - 1.0) "
            f"* ({s2} - {s1s1} / sf.a_p) ELSE 0 END) + sf.f1 * {vw})"
        )
        se = con.execute(
            f"WITH y_hh AS ("
            f"  SELECT {g}month_num AS m, strat, psu_id, hh, SUM(wgt) AS x, "
            f"    COALESCE(SUM(wgt) FILTER (WHERE pwmore = '1'), 0) AS y, "
            f"    COALESCE(SUM(wgt) FILTER (WHERE underemp_type LIKE 'Visibly%'), 0) AS yv, "
            f"    COALESCE(SUM(wgt) FILTER (WHERE underemp_type LIKE 'Invisibly%'), 0) AS yi "
            f"  FROM lfs_employed_2025 WHERE broad_sector != 'Not Reported' {where} GROUP BY ALL"
            f"), "
            f"p_ag AS ("
            f"  SELECT {g}m, strat, psu_id, "
            f"    SUM(x) AS zx, SUM(y) AS zy, SUM(yv) AS zyv, SUM(yi) AS zyi, "
            f"    SUM(x * x) AS qxx, SUM(y * y) AS qyy, SUM(x * y) AS qxy, "
            f"    SUM(yv * yv) AS qyyv, SUM(yi * yi) AS qyyi "
            f"  FROM y_hh GROUP BY ALL"
            f"), "
            f"h AS ("
            f"  SELECT {g}m, strat, "
            f"    SUM(zx) AS sx1, SUM(zx * zx) AS sx2, "
            f"    SUM(zy) AS sy1, SUM(zy * zy) AS sy2, SUM(zx * zy) AS sxy, "
            f"    SUM(zyv) AS syv1, SUM(zyv * zyv) AS syv2, "
            f"    SUM(zyi) AS syi1, SUM(zyi * zyi) AS syi2, "
            f"    {w_term('qxx', 'zx * zx')} AS vwx, {w_term('qyy', 'zy * zy')} AS vwy, "
            f"    {w_term('qxy', 'zx * zy')} AS cwxy, "
            f"    {w_term('qyyv', 'zyv * zyv')} AS vwyv, {w_term('qyyi', 'zyi * zyi')} AS vwyi "
            f"  FROM p_ag JOIN psu_frame pf USING (m, strat, psu_id) GROUP BY ALL"
            f") "
            f"SELECT {g}"
            f"  {b_term('sx2', 'sx1 * sx1', 'vwx')} AS vx, "
            f"  {b_term('sy2', 'sy1 * sy1', 'vwy')} AS vy, "
            f"  {b_term('sxy', 'sx1 * sy1', 'cwxy')} AS cxy, "
            f"  {b_term('syv2', 'syv1 * syv1', 'vwyv')} AS vy_vis, "
            f"  {b_term('syi2', 'syi1 * syi1', 'vwyi')} AS vy_inv "
            f"FROM h JOIN stratum_frame sf USING (m, strat) GROUP BY ALL"
        ).df()

        prefix = "avg_" if annual else ""
        est = df[f"{prefix}underemp_k"]
        vis_est = df[f"{prefix}visible_k"]
        inv_est = df[f"{prefix}invisible_k"]
        emp = df[f"{prefix}employed_k"] * div * 1e3
        r = (df["underemp_rate_pct"] / 100.0).fillna(0.0)

        var_cols = {"vy": 0.0, "vx": 0.0, "cxy": 0.0, "vy_vis": 0.0, "vy_inv": 0.0}
        mrg = (df[by].merge(se, on=by, how="left") if by else se).fillna(var_cols)
        vy = mrg["vy"].to_numpy()
        vx = mrg["vx"].to_numpy()
        cxy = mrg["cxy"].to_numpy()
        vy_vis = mrg["vy_vis"].to_numpy()
        vy_inv = mrg["vy_inv"].to_numpy()

        df["se_underemp_k"] = np.sqrt(np.maximum(0.0, vy)) / div / 1e3
        df["se_visible_k"] = np.sqrt(np.maximum(0.0, vy_vis)) / div / 1e3
        df["se_invisible_k"] = np.sqrt(np.maximum(0.0, vy_inv)) / div / 1e3

        # Rate SE (p. 8b): R = Y/X -> V(R) ~ [V(Y) + R^2 V(X) - 2R Cov(Y,X)] / X^2
        df["se_underemp_rate_pp"] = (
            np.sqrt(np.maximum(0.0, vy + r * r * vx - 2 * r * cxy)) / emp.where(emp > 0) * 100
        ).round(3)
        df["cv_underemp_pct"] = (df["se_underemp_k"] / est.where(est > 0) * 100).round(1)
        df["cv_visible_pct"] = (df["se_visible_k"] / vis_est.where(vis_est > 0) * 100).round(1)
        df["cv_invisible_pct"] = (df["se_invisible_k"] / inv_est.where(inv_est > 0) * 100).round(1)

        # Distinguish truly empty cells (emp <= 0) from sampled cells whose underemployed estimate is 0
        df["reliability"] = np.select(
            [
                emp <= 0,
                est <= 0,
                df["cv_underemp_pct"] <= 10,
                df["cv_underemp_pct"] <= 20,
            ],
            [
                "no sample",
                "zero estimate (CV undefined)",
                "reliable (CV<=10%)",
                "use with caution (CV 10-20%)",
            ],
            default="unreliable (CV>20%)",
        )
        df.insert(0, "psa_check", next(note for rx, note in PSA_CHECK_NOTES if re.search(rx, name)))


def _save_tables(con: duckdb.DuckDBPyConnection, tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Annotate all tables in place with SEs/CVs/notes and write each DataFrame to output/tables/*.csv."""
    annotate_tables(con, tables)
    for name, df in tables.items():
        df.to_csv(TAB_DIR / f"{name}.csv", index=False)
    return tables


def compute_tables(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    """Compute annual and monthly stratified sector x demographic tables (1A through 5B)."""
    print("[2/3] Computing stratified 2025 tables (Annual Average + Monthly)...")
    tables = {
        "1A_Sector_Annual": con.execute(
            build_stratified_query("broad_sector", "broad_sector, sector_order", "sector_order")
        ).df(),
        "1B_Sector_Monthly": con.execute(
            "WITH b AS (SELECT month_num, month_name, broad_sector, sector_order, "
            f"  {_WEIGHTED_SUMS}, "
            "  COALESCE(SUM(wgt) FILTER (WHERE hours_category LIKE 'Worked less than 40%'), 0) AS lt40, "
            "  COALESCE(SUM(wgt) FILTER (WHERE hours_category = 'Worked 40 hours and over'), 0) AS ge40, "
            "  COALESCE(SUM(wgt) FILTER (WHERE hours_category LIKE 'Did not work%'), 0) AS nw "
            "  FROM lfs_employed_2025 WHERE broad_sector != 'Not Reported' GROUP BY ALL) "
            "SELECT month_num, month_name, broad_sector, emp / 1e3 AS employed_k, "
            "  lt40 / 1e3 AS worked_lt40_k, ge40 / 1e3 AS worked_40plus_k, nw / 1e3 AS job_not_at_work_k, "
            "  und / 1e3 AS underemp_k, vis / 1e3 AS visible_k, inv / 1e3 AS invisible_k, "
            "  und * 100.0 / NULLIF(emp, 0) AS underemp_rate_pct, "
            "  vis * 100.0 / NULLIF(und, 0) AS visible_share_pct, "
            "  inv * 100.0 / NULLIF(und, 0) AS invisible_share_pct, "
            "  und * 100.0 / NULLIF(SUM(und) OVER (PARTITION BY month_num), 0) AS share_of_national_underemp_pct "
            "FROM b ORDER BY month_num, sector_order"
        ).df(),
    }
    specs = [
        ("2", "Sex", "broad_sector, sex", "broad_sector, sector_order, sex", "sector_order, sex DESC"),
        ("3", "Age", "broad_sector, age_group", "broad_sector, sector_order, age_group, age_order", "sector_order, age_order"),
        ("4", "Age_Sex", "broad_sector, age_group, sex", "broad_sector, sector_order, age_group, age_order, sex", "sector_order, age_order, sex DESC"),
        ("5", "Educ", "broad_sector, educ_code, educ_group", "broad_sector, sector_order, educ_code, educ_group", "sector_order, educ_code"),
    ]
    for num, tag, sel, grp, order in specs:
        tables[f"{num}A_Sector_{tag}_Annual"] = con.execute(
            build_stratified_query(sel, grp, order, "PARTITION BY broad_sector")
        ).df()
        tables[f"{num}B_Sector_{tag}_Monthly"] = con.execute(build_monthly_stratified_query(sel, grp, order)).df()

    if not np.isclose(
        tables["5A_Sector_Educ_Annual"]["avg_underemp_k"].sum(),
        tables["1A_Sector_Annual"]["avg_underemp_k"].sum(),
    ):
        raise ValueError("5A_Sector_Educ_Annual underemployed sum does not match 1A_Sector_Annual")
    _save_tables(con, tables)
    print(f"      Saved 10 stratified CSV tables in {TAB_DIR}")
    return tables


def compute_region_tables(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    """Compute residence-region (R*, Jan/Apr/Jul/Oct) and workplace-region (W*, 12 months) tables."""
    print("[2b/3] Computing region tables (R = residence, quarterly; W = workplace, monthly, NOT checkable vs PSA)...")
    crosses = {
        "0": ("", "", ""),
        "1_Sex": (", sex", ", sex", ", sex DESC"),
        "2_Sector": (", broad_sector", ", broad_sector, sector_order", ", sector_order"),
        "3_Age": (", age_group", ", age_group, age_order", ", age_order"),
        "4_Educ": (", educ_code, educ_group", ", educ_code, educ_group", ", educ_code"),
    }
    out = {}
    for pre, col, div, avg_lbl, per_lbl in [
        ("R", "region", 4.0, "Qavg", "Quarterly"),
        ("W", "work_region", 12.0, "Annual", "Monthly"),
    ]:
        where = f"AND {col} IS NOT NULL"
        for suf, (sel, grp, order) in crosses.items():
            out[f"{pre}{suf[0]}A_{pre}Reg{suf[1:]}_{avg_lbl}"] = con.execute(build_stratified_query(
                f"{col}{sel}", f"{col}, {col}_order{grp}", f"{col}_order{order}",
                f"PARTITION BY {col}", divisor=div, where=where, with_n=True,
            )).df()
            out[f"{pre}{suf[0]}B_{pre}Reg{suf[1:]}_{per_lbl}"] = con.execute(build_monthly_stratified_query(
                f"{col}{sel}", f"{col}, {col}_order{grp}", f"{col}_order{order}",
                where=where, partition=f"PARTITION BY month_num, {col}", with_n=True,
            )).df()

    # Additivity: every region split must add up to the national underemployed total for the same months
    q_avg = con.execute(
        "SELECT SUM(wgt) FILTER (WHERE pwmore='1') / 4e3 FROM lfs_employed_2025 WHERE region IS NOT NULL"
    ).fetchone()[0]
    a_avg = con.execute("SELECT SUM(wgt) FILTER (WHERE pwmore='1') / 12e3 FROM lfs_employed_2025").fetchone()[0]
    for name, df in out.items():
        if "avg_underemp_k" in df:
            target = q_avg if name.startswith("R") else a_avg
            if not np.isclose(df["avg_underemp_k"].sum(), target):
                raise ValueError(f"Additivity check failed on {name}: sum={df['avg_underemp_k'].sum()} vs {target}")

    q_months = set(con.execute("SELECT DISTINCT month_num FROM lfs_employed_2025 WHERE region IS NOT NULL").df()["month_num"])
    if q_months != {1, 4, 7, 10}:
        raise ValueError(f"Expected residence region in quarterly months {{1, 4, 7, 10}}, got {q_months}")

    unmapped = con.execute("SELECT COUNT(*) FROM lfs_employed_2025 WHERE work_region IS NULL").fetchone()[0]
    if unmapped != 0:
        raise ValueError(f"{unmapped} employed rows have a work province with no region mapping")

    _save_tables(con, out)
    print(f"      Saved {len(out)} region CSV tables. W* tables: {WORK_REGION_NOTE}")
    return out


def compute_rq_tables(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    """Compute direct Research Question 1, 2 (annual) and 3 (monthly) tables."""
    print("[RQ 1-3] Computing tables for Research Questions 1, 2, and 3...")
    dims = [
        ("a_Age", "by_Age", "age_group", "age_group, age_order", "age_order"),
        ("b_Sex", "by_Sex", "sex", "sex", "sex DESC"),
        ("c_Education", "by_Educ", "educ_code, educ_group", "educ_code, educ_group", "educ_code"),
        ("d1_Broad_Industry", "by_Sector", "broad_sector", "broad_sector, sector_order", "sector_order"),
        ("d2_Major_Industry", "by_Major_Ind", "broad_sector, major_industry",
         "broad_sector, sector_order, major_industry, major_industry_order", "sector_order, major_industry_order"),
    ]
    rq_tables = {
        f"RQ1_RQ2_{a}": con.execute(build_stratified_query(sel, grp, order)).df()
        for a, _, sel, grp, order in dims
    }
    rq_tables["RQ3_Monthly_Overall"] = con.execute(
        f"WITH b AS (SELECT month_num, month_name, {_WEIGHTED_SUMS} FROM lfs_employed_2025 GROUP BY month_num, month_name) "
        "SELECT month_num, month_name, emp / 1e3 AS employed_k, und / 1e3 AS underemp_k, "
        "  vis / 1e3 AS visible_k, inv / 1e3 AS invisible_k, und * 100.0 / NULLIF(emp, 0) AS underemp_rate_pct, "
        "  vis * 100.0 / NULLIF(und, 0) AS visible_share_pct, inv * 100.0 / NULLIF(und, 0) AS invisible_share_pct "
        "FROM b ORDER BY month_num"
    ).df()
    for _, m_tag, sel, grp, order in dims:
        rq_tables[f"RQ3_Monthly_{m_tag}"] = con.execute(
            build_monthly_stratified_query(sel, grp, order, partition_by_sector=False)
        ).df()
    return _save_tables(con, rq_tables)