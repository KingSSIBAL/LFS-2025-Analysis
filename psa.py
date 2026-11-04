"""Read PSA's published Special Release tables and check every comparable figure (and SE) against ours."""
from pathlib import Path
import re

import duckdb
import numpy as np
import pandas as pd

from tables import EDUC_ORDER, PSA_DIR, REGIONS, SECTOR_ORDER, TAB_DIR


# ==============================================================================
# STEP 5: VALIDATE MONTHLY & ANNUAL INDICATORS AGAINST OFFICIAL PSA RELEASES
# ==============================================================================
# Official source: PSA LFS Special Release (Final Statistical Tables, estimates marked "f") in data/psa_special_release/.
# Quarterly rounds (Jan/Apr/Jul/Oct) publish 20 tables, monthly rounds 11 with different numbers, so tables are
# found by the title printed inside the sheet (same wording in both formats).
PSA_TABLES = {
    "status_sex_age": r"Percent Distribution of Population 15 .*Employment Status, Sex,? and Age",
    "status_region_sex": r"Employment Status, Region,? and Sex",
    "hours_occ": r"Employed Persons by Total Hours Worked and Major Occupation",
    "hours_region_sex": r"Employed Persons by Total Hours Worked, Region,? and Sex",
    "class_broad": r"Class of Worker and Broad Industry",
    "sex_major_ind": r"Employed Persons by Sex,? (Region,? )?and Major Industry",
    "educ_sex_age": r"Highest Grade Completed,? (by )?Sex,? and Age",
    "educ_region_sex": r"Highest Grade Completed, Region,? and Sex",
    "wm_hours_sex": r"Wanting More Hours of Work by Total Hours Worked, Sex",
    "wm_hours_region": r"Wanting More Hours of Work by Total Hours Worked, Region",
    "wm_broad": r"Wanting More Hours of Work by Total Hours Worked and Broad Industry",
    "wm_major": r"Wanting More Hours of Work by Major Industry",
}
REQUIRED_ALL = {"status_sex_age", "hours_occ", "class_broad", "sex_major_ind", "educ_sex_age", "wm_hours_sex"}
REQUIRED_QUARTERLY = REQUIRED_ALL | {"status_region_sex", "hours_region_sex", "educ_region_sex", "wm_hours_region", "wm_major"}
REQUIRED_MONTHLY = REQUIRED_ALL | {"wm_broad"}

# (keyword in PSA label, view major_industry name) in view order 1..22: 1-2 AFF, 3-7 Industry, 8-22 Services.
# PSA's "Other service activities" includes PSIC Section T (households as employers); empty in 2025 PUFs (asserted below).
INDUSTRY_KEYS = [
    ("agriculture and forestry", "Agriculture and Forestry"), ("fishing", "Fishing and Aquaculture"),
    ("mining", "Mining and Quarrying"), ("manufacturing", "Manufacturing"),
    ("electricity", "Electricity, Gas, Steam, and Air Conditioning Supply"),
    ("water supply", "Water Supply; Sewerage, Waste Management"), ("construction", "Construction"),
    ("wholesale", "Wholesale and Retail Trade; Repair of Motor Vehicles"), ("transportation", "Transportation and Storage"),
    ("accommodation", "Accommodation and Food Service Activities"), ("information", "Information and Communication"),
    ("financial", "Financial and Insurance Activities"), ("real estate", "Real Estate Activities"),
    ("professional", "Professional, Scientific and Technical Activities"),
    ("administrative", "Administrative and Support Service Activities"),
    ("public administration", "Public Administration and Defense"), ("education", "Education"),
    ("human health", "Human Health and Social Work Activities"), ("arts", "Arts, Entertainment and Recreation"),
    ("other service", "Other Service Activities"), ("households", "Activities of Households as Employers"),
    ("extraterritorial", "Activities of Extraterritorial Organizations"),
]
MEASURES = ["employed", "underemp", "visible", "invisible", "notwork", "lt40", "ge40"]
DIMS = ["sex", "age_group", "educ_group", "major_industry", "broad_sector", "region"]
TOL_LEVEL_K, TOL_RATE_PP = 1.0, 0.05
MONTHS_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
# Tolerances are rounding, not slack: PSA prints levels to 0.001k but children as % to 1-3 dp, so a child level
# rebuilt as % x total can be off by up to ~0.25k. Rates 0.05 pp for the same reason.


def read_psa_blocks(path: Path) -> tuple[str, list[dict]]:
    """(title, blocks). A block = level row in '000, then a 'Total' row, then % child rows (% of the level row)."""
    raw = pd.read_excel(path, header=None)
    title = " ".join(" ".join(v for v in raw.iloc[:6].values.ravel() if isinstance(v, str)).split())
    head = raw.iloc[:15].astype(str)
    se_col = next((c for c in raw.columns if head[c].str.contains("standard error", case=False).any()), None)
    if se_col is None:
        raise ValueError(f"No 'Standard Error' header in {path.name}")
    est = raw.iloc[:, :se_col].apply(pd.to_numeric, errors="coerce")
    est = est.loc[:, est.notna().sum() >= 3]  # real estimate columns; drops stray page numbers
    se = raw.iloc[:, se_col:].apply(pd.to_numeric, errors="coerce")
    se = se.loc[:, se.notna().sum() >= 3]  # PSA's standard errors, same column order as the estimates
    labels = [next((" ".join(v.split()) for v in raw.iloc[i, :se_col] if isinstance(v, str) and v.strip()), "")
              for i in range(len(raw))]
    numeric = [est.iloc[i].notna().sum() >= max(1, est.shape[1] // 2) for i in range(len(raw))]
    rows = []
    for i, lab in enumerate(labels):
        if numeric[i]:
            # PSA prints "Number (in thousands)" under every level row (some 'Total' rows are blank, e.g. NIR Jan TAB 11)
            captioned = False
            for j in range(i + 1, len(raw)):
                if numeric[j]:
                    break
                if labels[j].startswith("Number (in"):
                    captioned = True
                    break
            rows.append((lab, est.iloc[i].to_numpy(dtype=float), captioned, se.iloc[i].to_numpy(dtype=float)))
    blocks = []
    for k, (lab, vals, captioned, se_vals) in enumerate(rows):
        if lab == "Total":
            continue
        if captioned or (k + 1 < len(rows) and rows[k + 1][0] == "Total"):
            blocks.append({"name": lab, "level": vals, "se": se_vals, "children": []})
        elif blocks:
            blocks[-1]["children"].append((lab, vals))
    return title, blocks


def _is_national(b: dict) -> bool:
    return b["name"] in ("Philippines", "Both Sexes")


def _region(label: str) -> str:
    for _, name, key in REGIONS:
        if re.search(key, label, re.I):
            return name
    raise ValueError(f"Unknown PSA region label: {label!r}")


def _industry(label: str) -> tuple[str, str]:
    for i, (key, name) in enumerate(INDUSTRY_KEYS):
        if key in label.lower():
            return name, SECTOR_ORDER[0 if i < 2 else 1 if i < 7 else 2]
    raise ValueError(f"Unknown PSA industry label: {label!r}")


def _regions(blocks: list[dict]) -> list[dict]:
    assert blocks[0]["name"] == "Philippines" and len(blocks) == 1 + len(REGIONS), [b["name"] for b in blocks]
    return blocks[1:]


def _child_k(b: dict, rows: list[np.ndarray], j: int) -> np.ndarray:
    """Child rows in '000 for column j. Usually % of the block total, but some releases print '000 (Jul Table 2 ages)."""
    v, tot = np.array([r[j] for r in rows]), b["level"][j]
    return v if abs(np.nansum(v) - tot) < abs(np.nansum(v) - 100) else v * tot / 100


def _sexes(b: dict, j: int) -> list[tuple[str, float]]:
    # region blocks: Male, Female rows (unlabeled in Jan/Apr; Jul/Oct add a 100% "Both Sexes" row)
    kids = [(lab, pct) for lab, pct in b["children"] if lab != "Both Sexes"]
    assert len(kids) == 2 and all(lab in ("", s) for (lab, _), s in zip(kids, ("Male", "Female"))), (b["name"], kids)
    return list(zip(("Male", "Female"), _child_k(b, [p for _, p in kids], j)))


def _hours(level: np.ndarray) -> dict[str, float]:
    return {"notwork": level[1], "lt40": level[2] + level[3] + level[4], "ge40": level[5]}


def ex_status_sex_age(blocks):
    for b in blocks:
        sex = None if _is_national(b) else b["name"]
        for m, j in (("employed", 2), ("underemp", 3)):
            yield m, {"sex": sex}, b["level"][j]
            if sex is None:
                labs = [lab.replace(" - ", "-").replace("65 and over", "65 and Over") for lab, _ in b["children"]]
                for lab, v in zip(labs, _child_k(b, [p for _, p in b["children"]], j)):
                    yield m, {"age_group": lab}, v


def ex_status_region_sex(blocks):
    for b in _regions(blocks):
        reg = _region(b["name"])
        for m, j in (("employed", 2), ("underemp", 3)):
            yield m, {"region": reg}, b["level"][j]
            for sex, v in _sexes(b, j):
                yield m, {"region": reg, "sex": sex}, v


def ex_hours_occ(blocks):
    for m, v in _hours(blocks[0]["level"]).items():
        yield m, {}, v


def ex_hours_region_sex(blocks):
    for b in _regions(blocks):
        for m, v in _hours(b["level"]).items():
            yield m, {"region": _region(b["name"])}, v


def ex_class_broad(blocks):
    for sector, v in zip(SECTOR_ORDER, blocks[0]["level"][1:4]):
        yield "employed", {"broad_sector": sector}, v


def ex_sex_major_ind(blocks):
    for b in blocks:
        national, by_sector = b["name"] == "Philippines", {}
        for (lab, _), v in zip(b["children"], _child_k(b, [p for _, p in b["children"]], 0)):
            name, sector = _industry(lab)
            by_sector[sector] = by_sector.get(sector, 0.0) + v
            if national:
                yield "employed", {"major_industry": name}, v
        if not national:
            for sector, v in by_sector.items():
                yield "employed", {"region": _region(b["name"]), "broad_sector": sector}, v


def ex_educ_sex_age(blocks):
    b = next(b for b in blocks if _is_national(b))
    for g, v in zip(EDUC_ORDER, b["level"][1:12], strict=True):
        yield "employed", {"educ_group": g}, v


def ex_educ_region_sex(blocks):
    for b in _regions(blocks):
        for g, v in zip(EDUC_ORDER, b["level"][1:12], strict=True):
            yield "employed", {"region": _region(b["name"]), "educ_group": g}, v


WM_COLS = (("underemp", 0), ("visible", 1), ("invisible", 2))


def ex_wm_hours_sex(blocks):
    for b in blocks:
        for m, j in WM_COLS:
            yield m, {"sex": None if _is_national(b) else b["name"]}, b["level"][j]


def ex_wm_hours_region(blocks):
    for b in _regions(blocks):
        reg = _region(b["name"])
        for m, j in WM_COLS:
            yield m, {"region": reg}, b["level"][j]
            for sex, v in _sexes(b, j):
                yield m, {"region": reg, "sex": sex}, v


def ex_wm_broad(blocks):
    b = blocks[0]
    for lab, sector in zip([lab for lab, _ in b["children"]], SECTOR_ORDER, strict=True):
        assert sector.lower().startswith(lab.lower()[:5]), lab
    for m, j in WM_COLS:
        for sector, v in zip(SECTOR_ORDER, _child_k(b, [p for _, p in b["children"]], j)):
            yield m, {"broad_sector": sector}, v


def ex_wm_major(blocks):
    b, by_sector = blocks[0], {}
    for (lab, _), v in zip(b["children"], _child_k(b, [p for _, p in b["children"]], 0)):
        name, sector = _industry(lab)
        by_sector[sector] = by_sector.get(sector, 0.0) + v
        yield "underemp", {"major_industry": name}, v
    for sector, v in by_sector.items():
        yield "underemp", {"broad_sector": sector}, v


EXTRACTORS = {k: globals()[f"ex_{k}"] for k in PSA_TABLES}


def load_psa_official() -> pd.DataFrame:
    """Long table: month_num, check, table, measure, <DIMS>, psa (levels in '000).
    attrs['se_underemp']: PSA SE of underemployed, keyed by month (national) or (month, region)."""
    recs, found, se_national = [], {}, {}
    for p in sorted(PSA_DIR.glob("*__T*.xls*")):
        prefix = p.name.split("__")[0]
        if "__PR_" in p.name or not prefix[:2].isdigit() or prefix.startswith("00"):
            continue
        month = int(prefix[:2])
        title, blocks = read_psa_blocks(p)
        keys = [k for k, rx in PSA_TABLES.items() if re.search(rx, title, re.I)]
        if not keys:
            continue
        if len(keys) > 1 or (month, keys[0]) in found:
            raise ValueError(f"Ambiguous PSA table {p.name}: {keys} / {found.get((month, keys[0]))}")
        found[(month, keys[0])] = p.name
        tab = re.match(r"(TAB|Table)\s*\d+", p.name.split("__")[1], re.I).group()
        if keys[0] == "status_sex_age":  # national underemployed SE ('000), column 3 as for the estimate
            se_national[month] = next(b for b in blocks if _is_national(b))["se"][3]
        if keys[0] == "status_region_sex":  # same, per region (Jan/Apr/Jul/Oct only)
            se_national.update({(month, _region(b["name"])): b["se"][3] for b in _regions(blocks)})
        for measure, dims, value in EXTRACTORS[keys[0]](blocks):
            recs.append({"month_num": month, "check": keys[0], "table": tab, "measure": measure,
                         **{d: v for d, v in dims.items() if v is not None}, "psa": float(value)})
    missing = [
        f"{MONTHS_ABBR[m - 1]}: {k}"
        for m in range(1, 13)
        for k in sorted(REQUIRED_QUARTERLY if m in (1, 4, 7, 10) else REQUIRED_MONTHLY)
        if (m, k) not in found
    ]
    if missing:
        raise FileNotFoundError(f"PSA Special Release tables not found in {PSA_DIR}:\n  " + "\n  ".join(missing))
    out = pd.DataFrame(recs).reindex(columns=["month_num", "check", "table", "measure", *DIMS, "psa"])
    out.attrs["se_underemp"] = se_national
    return out


def read_annual_employed() -> float:
    """PHILIPPINES employed ('000) from the Annual release, 'Annual 2025p' estimate column."""
    path = next(PSA_DIR.glob("00_Annual__Table 2*.xls*"), None)
    if path is None:
        raise FileNotFoundError(f"Annual release '00_Annual__Table 2 ...' (employed) not found in {PSA_DIR}")
    raw = pd.read_excel(path, header=None)
    col = next(c for c in raw.columns if raw[c].astype(str).str.contains("Annual 2025").any())
    row = raw.index[raw.iloc[:, 1].astype(str).str.strip().str.upper() == "PHILIPPINES"][0]
    return float(raw.at[row, col])


def _with_rates(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Append underemployment-rate rows wherever the same table gives both employed and underemployed."""
    e = df[df["measure"] == "employed"].set_index(keys)
    u = df[df["measure"] == "underemp"].set_index(keys)
    j = e[["psa", "puf"]].join(u[["psa", "puf"]], lsuffix="_e", rsuffix="_u", how="inner")
    rates = pd.DataFrame({"psa": j["psa_u"] / j["psa_e"] * 100, "puf": j["puf_u"] / j["puf_e"] * 100}).reset_index()
    return pd.concat([df, rates.assign(measure="underemp_rate_pct")], ignore_index=True)


def _status(df: pd.DataFrame) -> pd.DataFrame:
    tol = np.where(df["measure"] == "underemp_rate_pct", TOL_RATE_PP, TOL_LEVEL_K)
    df["diff"] = df["puf"] - df["psa"]
    df["status"] = np.where(df["diff"].abs() <= tol, "PASS", "CHECK")
    return df


def verify_against_psa_official(
    con: duckdb.DuckDBPyConnection, overall: pd.DataFrame, by_region: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    print("[4/4] Validating PUF calculations against official PSA Special Release (final) tables...")
    off = load_psa_official()
    # Our underemployed SE (Technical Notes p. 8 with B = 250) vs PSA's published SE: national every month, and each
    # region in Jan/Apr/Jul/Oct. Guards the accuracy claim in the module notes: fails if a change to B, strata or
    # PSUs moves SEs off PSA. National > 5%; region > 15%: each region has ~1/18 of the PSUs, and the worst 2025 cell
    # is CAR in July at 0.875x (July has the largest sample, so the B = 250 guess bites hardest; CAR has small provinces).
    psa_se = pd.Series(off.attrs["se_underemp"])
    nat = psa_se[[k for k in psa_se.index if not isinstance(k, tuple)]]
    reg = psa_se[[k for k in psa_se.index if isinstance(k, tuple)]]
    reg.index = pd.MultiIndex.from_tuples(reg.index)
    for label, mine, psa, n, tol in [
        ("National", overall.set_index("month_num")["se_underemp_k"], nat, 12, 0.05),
        ("Regional", by_region.set_index(["month_num", "region"])["se_underemp_k"], reg, 4 * len(REGIONS), 0.15),
    ]:
        ratio = (mine / psa).dropna()
        print(f"      {label} underemployed SE / PSA SE: median {ratio.median():.4f}, "
              f"range {ratio.min():.3f}-{ratio.max():.3f} ({len(ratio)} cells)")
        assert len(ratio) == n and ratio.between(1 - tol, 1 + tol).all(), ratio[~ratio.between(1 - tol, 1 + tol)].round(3)
    fine = con.execute(
        "SELECT month_num, sex, age_group, educ_group, major_industry, broad_sector, region, "
        "  SUM(wgt) AS employed, "
        "  COALESCE(SUM(wgt) FILTER (WHERE pwmore = '1'), 0) AS underemp, "
        "  COALESCE(SUM(wgt) FILTER (WHERE underemp_type LIKE 'Visibly%'), 0) AS visible, "
        "  COALESCE(SUM(wgt) FILTER (WHERE underemp_type LIKE 'Invisibly%'), 0) AS invisible, "
        "  COALESCE(SUM(wgt) FILTER (WHERE hours_category LIKE 'Did not work%'), 0) AS notwork, "
        "  COALESCE(SUM(wgt) FILTER (WHERE hours_category LIKE 'Worked less than 40%'), 0) AS lt40, "
        "  COALESCE(SUM(wgt) FILTER (WHERE hours_category = 'Worked 40 hours and over'), 0) AS ge40 "
        "FROM lfs_employed_2025 GROUP BY ALL"
    ).df()
    fine[MEASURES] = fine[MEASURES] / 1e3
    assert not (fine["major_industry"] == "Activities of Households as Employers").any(), \
        "PUF now codes households (PSIC T) separately; fold it into 'Other Service Activities' before comparing to PSA"

    off["group"] = off[DIMS].apply(lambda r: "; ".join(f"{d}={v}" for d, v in r.items() if pd.notna(v)) or "Philippines", axis=1)
    off["dimset"] = off[DIMS].notna().apply(lambda r: tuple(d for d, v in r.items() if v), axis=1)
    parts = []
    for dimset, grp in off.groupby("dimset"):
        keys = ["month_num", *dimset]
        puf = fine.groupby(keys, as_index=False)[MEASURES].sum().melt(keys, var_name="measure", value_name="puf")
        parts.append(grp.merge(puf, on=[*keys, "measure"], how="left"))
    # no PUF respondents in a cell = 0; PSA prints "-" (blank) for 0. Must be 0 not NaN, or averages skip months.
    mon = pd.concat(parts, ignore_index=True).fillna({"psa": 0.0, "puf": 0.0})
    mon = _status(_with_rates(mon, ["month_num", "check", "table", "group"]))

    # Period averages: national annual = mean of 12 monthly finals (SUM/12); region = mean of 4 quarterly rounds.
    lv = (mon[mon["measure"] != "underemp_rate_pct"]
          .groupby(["measure", "group", "month_num"], as_index=False)
          .agg(psa=("psa", "mean"), puf=("puf", "mean"), check=("check", lambda s: "+".join(sorted(set(s))))))
    avg = lv.groupby(["measure", "group"], as_index=False).agg(
        psa=("psa", "mean"), puf=("puf", "mean"), months=("month_num", frozenset),
        check=("check", lambda s: "+".join(sorted(set("+".join(s).split("+"))))))
    full = avg["months"] == frozenset(range(1, 13))
    qavg = (avg["months"] == frozenset({1, 4, 7, 10})) & avg["group"].str.contains("region=")
    avg["period"] = np.select([full, qavg], ["2025 Annual Avg (mean of 12 monthly finals)", "Q-avg Jan/Apr/Jul/Oct"], "")
    na = avg[avg["period"] == ""].groupby(["check", "measure"], as_index=False)["months"].first()
    avg = _status(_with_rates(avg[avg["period"] != ""].drop(columns="months"), ["period", "group"]).fillna({"check": "rate = underemp / employed"}))

    # Annual 2025p is preliminary and differs from the mean of PSA's own 12 monthly finals, so report as INFO.
    psa_monthly_mean = avg.loc[(avg["measure"] == "employed") & (avg["group"] == "Philippines"), "psa"].iloc[0]
    annual_psa = read_annual_employed()
    annual_puf_emp = con.execute("SELECT SUM(wgt) / 12e3 FROM lfs_employed_2025").fetchone()[0]
    avg = pd.concat([
        avg,
        pd.DataFrame([{
            "period": "2025 Annual (Annual Special Release 2025p)", "check": "annual_release_table2",
            "measure": "employed", "group": "Philippines", "psa": annual_psa, "puf": annual_puf_emp,
            "diff": annual_puf_emp - annual_psa,
            "status": f"INFO: preliminary; PSA's own monthly finals average {psa_monthly_mean:,.3f}",
        }]),
        pd.DataFrame({
            "period": "N/A (not published every month; no comparable period average)", "check": na["check"],
            "measure": na["measure"], "group": "all groups",
            "status": "N/A months " + na["months"].map(lambda s: ",".join(MONTHS_ABBR[m - 1] for m in sorted(s))),
        }),
    ], ignore_index=True)

    cols = {"check": "Check", "table": "PSA_Table", "measure": "Indicator", "group": "Group", "puf": "PUF_Calculated",
            "psa": "PSA_Official", "diff": "Diff", "status": "Status"}
    df_val_monthly = (mon.assign(Month=mon["month_num"].map(lambda m: MONTHS_ABBR[m - 1]))
                      .sort_values(["month_num", "check", "measure", "group"])
                      .rename(columns=cols)[["Month", *cols.values()]].round(4))
    df_val_annual = avg.rename(columns={**cols, "period": "Period"})[["Period", *[c for c in cols.values() if c != "PSA_Table"]]].round(4)
    df_val_annual.to_csv(TAB_DIR / "0A_PSA_Validation_Annual.csv", index=False)
    df_val_monthly.to_csv(TAB_DIR / "0B_PSA_Validation_Monthly.csv", index=False)

    print("\n=== PSA VALIDATION SUMMARY ===")
    print(pd.concat([df_val_monthly.assign(Period="Monthly"), df_val_annual]).groupby(["Period", "Status"]).size().to_string())
    bad = pd.concat([df_val_monthly[df_val_monthly["Status"].str.startswith("CHECK")],
                     df_val_annual[df_val_annual["Status"].str.startswith("CHECK")]])
    if len(bad):
        print("\n=== ROWS THAT DO NOT MATCH PSA ===\n" + bad.to_string(index=False))
    assert bad.empty, f"{len(bad)} figures do not match the official PSA release (see 0A/0B validation CSVs)"
    return {"0A_Validation_Annual": df_val_annual, "0B_Validation_Monthly": df_val_monthly}


