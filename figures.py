"""All 300-DPI figures: sector overview and breakdowns, research-question figures, and the regional map."""
import json

import duckdb
from matplotlib.collections import PolyCollection
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import seaborn as sns

from tables import EDUC_ORDER, FIG_DIR, GEO_PATH, REGIONS, SECTOR_COLORS, SECTOR_ORDER, SECTOR_SHORT, SEX_COLORS

plt.rcParams.update({"font.sans-serif": "DejaVu Sans", "axes.edgecolor": "#333333", "axes.linewidth": 0.8})
sns.set_theme(style="whitegrid", palette="deep")


# ==============================================================================
# STEP 4: GENERATE 2-PANEL (VOLUME/SHARE + VULNERABILITY RATE) 300-DPI FIGURES
# ==============================================================================
def _flag_suffix(cv: float) -> str:
    if pd.isna(cv) or cv <= 10:
        return ""
    return "**" if cv > 20 else "*"


def _style_bar_cv(bar, cv: float) -> None:
    # shortcut: mutates Matplotlib Patch in-place using PSA/NSCB CV bands (10% and 20%)
    if pd.notna(cv) and cv > 20:
        bar.set_hatch("///")
        bar.set_alpha(0.45)
        bar.set_edgecolor("#333333")
    elif pd.notna(cv) and cv > 10:
        bar.set_hatch("//")
        bar.set_alpha(0.75)
        bar.set_edgecolor("#333333")


def _annotate_hue_bars(
    ax: plt.Axes, df: pd.DataFrame, cat: str, hue: str, metric: str,
    cat_order: list[str], hue_order: list[str], fmt: str, fs: float,
) -> None:
    lookup = df.set_index([cat, hue])[[metric, "cv_underemp_pct"]].to_dict("index")
    for h_val, container in zip(hue_order, ax.containers):
        labels = []
        for c_val, bar in zip(cat_order, container):
            row = lookup.get((c_val, h_val))
            if row is None or pd.isna(row[metric]):
                labels.append("")
                continue
            cv = row["cv_underemp_pct"]
            _style_bar_cv(bar, cv)
            labels.append((fmt % row[metric]) + _flag_suffix(cv))
        ax.bar_label(container, labels=labels, padding=3, fontsize=fs, weight="bold")


def _save_fig(suptitle: str, filename: str, y: float = 1.02) -> None:
    fig = plt.gcf()
    has_cv_flags = any(p.get_hatch() for ax in fig.axes for p in ax.patches)
    plt.suptitle(suptitle, fontsize=12.5, weight="bold", y=y)
    if has_cv_flags:
        plt.tight_layout(rect=(0, 0.025, 1, 1))
        fig.text(
            0.01, 0.004,
            "* CV 10-20% (use with caution)   ** CV > 20% (unreliable)",
            fontsize=8.5, color="#444444", style="italic",
        )
    else:
        plt.tight_layout()
    plt.savefig(FIG_DIR / filename, bbox_inches="tight")
    plt.close()


def _two_panel_bars(
    df: pd.DataFrame, cat: str, hue: str, palette: dict, hue_title: str, cat_label: str,
    title_a: str, title_b: str, suptitle: str, filename: str,
    figsize: tuple[float, float] = (13, 5.4), horizontal: bool = False,
    order: list[str] | None = None, fs: float = 8.5, leg_loc: str = "best",
) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize, dpi=300, sharey=horizontal)
    cat_order = list(order) if order is not None else list(dict.fromkeys(df[cat]))
    hue_order = [k for k in palette if k in set(df[hue])]
    specs = [
        (ax1, "avg_underemp_k", "%.0fk", "Average Monthly Underemployed (in Thousands)", title_a, False),
        (ax2, "underemp_rate_pct", "%.1f%%", "Within-Group Underemployment Rate (%)", title_b, True),
    ]
    for ax, metric, fmt, mlabel, title, is_pct in specs:
        kw = (
            {"y": cat, "x": metric, "order": cat_order, "hue_order": hue_order}
            if horizontal
            else {"x": cat, "y": metric, "order": cat_order, "hue_order": hue_order}
        )
        sns.barplot(data=df, hue=hue, palette=palette, ax=ax, **kw)
        _annotate_hue_bars(ax, df, cat, hue, metric, cat_order, hue_order, fmt, fs)
        lim = df[metric].max() * 1.20
        if horizontal:
            ax.set(xlim=(0, lim), xlabel=mlabel, ylabel=cat_label if ax is ax1 else "")
            if is_pct:
                ax.xaxis.set_major_formatter(mtick.PercentFormatter())
        else:
            ax.set(ylim=(0, lim), xlabel=cat_label, ylabel=mlabel)
            if is_pct:
                ax.yaxis.set_major_formatter(mtick.PercentFormatter())
        ax.set_title(title, fontsize=11, weight="bold")
        ax.legend(title=hue_title, frameon=True, loc=leg_loc)
    _save_fig(suptitle, filename, y=1.01 if horizontal else 1.02)


def generate_figures(tables: dict[str, pd.DataFrame]) -> None:
    print("[3/3] Generating stratified 300-DPI figures...")
    frames = [tables[k].assign(sector_short=lambda d: d["broad_sector"].map(SECTOR_SHORT))
              for k in ("1A_Sector_Annual", "1B_Sector_Monthly", "2A_Sector_Sex_Annual",
                        "3A_Sector_Age_Annual", "4A_Sector_Age_Sex_Annual", "5A_Sector_Educ_Annual")]
    t1_ann, t1_mon, t2_sex, t3_age, t4_agesex, t5_edu = frames
    palette_short = {SECTOR_SHORT[k]: v for k, v in SECTOR_COLORS.items()}

    # Figure 1: Broad Sector Overview (Stacked Volume/Share + Stacked Rate)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5), dpi=300)
    b1 = ax1.bar(t1_ann["sector_short"], t1_ann["avg_visible_k"], width=0.55, label="Visibly Underemployed (<40 hrs)", color="#2b5c8f")
    b2 = ax1.bar(t1_ann["sector_short"], t1_ann["avg_invisible_k"], width=0.55, bottom=t1_ann["avg_visible_k"], label="Invisibly Underemployed (40+ hrs)", color="#e68a00")
    ax1.bar_label(b1, [f"{v:.1f}%" for v in t1_ann["visible_share_within_group_pct"]], label_type="center", color="white", fontsize=8.5, weight="bold")
    ax1.bar_label(b2, [f"{v:.1f}%" for v in t1_ann["invisible_share_within_group_pct"]], label_type="center", color="white", fontsize=8.5, weight="bold")
    ax1.bar_label(b2, [f"{r.avg_underemp_k:,.0f}k\n({r.share_of_national_underemp_pct:.1f}% of Total)" for r in t1_ann.itertuples()], padding=4, fontsize=8.5, weight="bold")
    ax1.set(ylim=(0, t1_ann["avg_underemp_k"].max() * 1.25), ylabel="Average Monthly Underemployed (in Thousands)")
    ax1.set_title("A. Volume (in Thousands), Share of National Total,\nand Visible vs. Invisible Split", fontsize=11, weight="bold")
    ax1.legend(frameon=True, loc="upper left")

    ax2.bar(t1_ann["sector_short"], t1_ann["visible_rate_pct"], width=0.55, label="Visible Underemployment Rate (<40 hrs)", color="#2b5c8f")
    r2 = ax2.bar(t1_ann["sector_short"], t1_ann["invisible_rate_pct"], width=0.55, bottom=t1_ann["visible_rate_pct"], label="Invisible Underemployment Rate (40+ hrs)", color="#e68a00")
    ax2.bar_label(r2, [f"{v:.1f}%" for v in t1_ann["underemp_rate_pct"]], padding=4, fontsize=9.5, weight="bold")
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax2.set(ylim=(0, t1_ann["underemp_rate_pct"].max() * 1.22), ylabel="Within-Sector Underemployment Rate (%)")
    ax2.set_title("B. Within-Sector Vulnerability Rate (%)\n(Underemployed / Sector Employed)", fontsize=11, weight="bold")
    ax2.legend(frameon=True, loc="upper right")
    _save_fig("Figure 1. Underemployment by Broad Industry Group: Volume vs. Vulnerability Rate (2025 Annual Average)", "fig1_broad_sector_overview_2panel.png")

    # Figure 2: Monthly Trends by Broad Sector
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.4), dpi=300)
    for ax, col, ylab, title, pct in [
        (ax1, "underemp_k", "Underemployed Persons (in Thousands)", "A. Monthly Underemployed Volume (in Thousands)\nby Broad Industry Group", False),
        (ax2, "underemp_rate_pct", "Within-Sector Underemployment Rate (%)", "B. Monthly Within-Sector Underemployment Rate (%)\n(Sector Vulnerability Trend)", True),
    ]:
        sns.lineplot(data=t1_mon, x="month_name", y=col, hue="sector_short", style="sector_short", markers=True, dashes=False, lw=2.3, palette=palette_short, ax=ax)
        ax.set(xlabel="Month (2025)", ylabel=ylab)
        ax.set_title(title, fontsize=11, weight="bold")
        if pct:
            ax.yaxis.set_major_formatter(mtick.PercentFormatter())
        ax.legend(title="Broad Sector", frameon=True)
    _save_fig("Figure 2. Monthly Underemployment Trends by Broad Industry Group (January-December 2025)", "fig2_monthly_sector_trends_2panel.png")

    # Figure 3: Monthly Visible vs. Invisible Split Across Broad Sectors
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.0), dpi=300, sharey=True)
    for idx, (ax, sec) in enumerate(zip(axes, SECTOR_ORDER)):
        sub = t1_mon[t1_mon["broad_sector"] == sec]
        ax.bar(sub["month_name"], sub["visible_k"], label="Visibly (<40 hrs)", color="#2b5c8f")
        ax.bar(sub["month_name"], sub["invisible_k"], bottom=sub["visible_k"], label="Invisibly (40+ hrs)", color="#e68a00")
        ax.set_title(SECTOR_SHORT[sec], fontsize=11, weight="bold")
        ax.set_xlabel("Month (2025)")
        ax.tick_params(axis="x", rotation=45)
        if idx == 0:
            ax.set_ylabel("Underemployed Persons (in Thousands)")
            ax.legend(frameon=True, loc="upper right")
    _save_fig("Figure 3. Monthly Visibly vs. Invisibly Underemployed Workers Stratified by Broad Sector (2025)", "fig3_monthly_visible_invisible_by_sector.png")

    # Figures 4, 5, 6: Paired 2-panel Volume + Rate bar charts
    _two_panel_bars(
        t2_sex, "sector_short", "sex", SEX_COLORS, "Sex", "Broad Industry Group",
        "A. Average Monthly Underemployed (in Thousands)\nby Broad Sector and Sex",
        "B. Within-Group Underemployment Rate (%)\nby Broad Sector and Sex",
        "Figure 4. Underemployment by Broad Industry Group and Sex (2025 Annual Average)",
        "fig4_sector_by_sex_2panel.png",
    )
    _two_panel_bars(
        t3_age, "age_group", "sector_short", palette_short, "Broad Sector", "Age Group (Years)",
        "A. Average Monthly Underemployed (in Thousands)\nby Age Group and Broad Sector",
        "B. Within-Group Underemployment Rate (%)\nby Age Group and Broad Sector",
        "Figure 5. Underemployment by Age Group and Broad Industry Sector (2025 Annual Average)",
        "fig5_sector_by_age_2panel.png", figsize=(15, 5.6), fs=7.5,
    )
    _two_panel_bars(
        t5_edu[t5_edu["educ_group"] != "Not Reported"], "educ_group", "sector_short", palette_short, "Broad Sector",
        "Highest Grade Completed (PUFC07_GRADE)",
        "A. Average Monthly Underemployed (in Thousands)\nby Highest Grade Completed and Broad Sector",
        "B. Within-Group Underemployment Rate (%)\nby Highest Grade Completed and Broad Sector",
        "Figure 6. Underemployment by Highest Grade Completed (1-11) and Broad Industry Sector (2025 Annual Average)",
        "fig6_sector_by_education_2panel.png", figsize=(16, 8.5), horizontal=True, order=EDUC_ORDER, fs=7.2, leg_loc="lower right",
    )

    # Figure 7: 3-Way Stratified Facet (Broad Sector x Age Group x Sex)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), dpi=300, sharey=True)
    sex_order = list(SEX_COLORS)
    for idx, (ax, sec) in enumerate(zip(axes, SECTOR_ORDER)):
        sub = t4_agesex[t4_agesex["broad_sector"] == sec]
        age_order = list(dict.fromkeys(sub["age_group"]))
        sns.barplot(
            data=sub, x="age_group", y="avg_underemp_k", hue="sex",
            order=age_order, hue_order=sex_order, palette=SEX_COLORS, ax=ax,
        )
        _annotate_hue_bars(ax, sub, "age_group", "sex", "avg_underemp_k", age_order, sex_order, "%.0fk", fs=7.5)
        ax.set(xlabel="Age Group (Years)", ylim=(0, t4_agesex["avg_underemp_k"].max() * 1.18))
        ax.set_title(SECTOR_SHORT[sec], fontsize=11, weight="bold")
        if idx == 0:
            ax.set_ylabel("Average Monthly Underemployed (in Thousands)")
            ax.legend(title="Sex", frameon=True)
        else:
            ax.get_legend().remove()
    _save_fig("Figure 7. Underemployed Workers by Broad Sector, Age Group, and Sex (2025 Annual Average)", "fig7_sector_age_sex_3way.png")
    print(f"      Saved 7 multi-panel 300-DPI PNG figures in: {FIG_DIR}")


def generate_region_map(con: duckdb.DuckDBPyConnection, region_tables: dict[str, pd.DataFrame]) -> None:
    """Map of the underemployment rate by region of residence (Jan/Apr/Jul/Oct average) + ranked bars with 95% CIs."""
    df = region_tables["R0A_RReg_Qavg"].set_index("region")
    name_of = {code: name for code, name, _ in REGIONS}
    # Region of each province as the 2025 PUF codes it (e.g. Sulu = BARMM in 2025; the boundary file puts it in IX).
    dom_reg = dict(con.execute("SELECT work_dom, wcode FROM work_dom_region").fetchall())
    polys, vals = [], []
    for f in json.loads(GEO_PATH.read_text())["features"]:
        p, g = f["properties"], f["geometry"]
        code = dom_reg.get(str(p["adm2_psgc"]).zfill(10)[3:5], str(p["adm1_psgc"]).zfill(10)[:2])  # PSGC RR PPP ...
        rings = [poly[0] for poly in g["coordinates"]] if g["type"] == "MultiPolygon" else [g["coordinates"][0]]
        polys += rings
        vals += [df.at[name_of[code], "underemp_rate_pct"]] * len(rings)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 9), dpi=300, gridspec_kw={"width_ratios": [1, 1.15]})
    pc = PolyCollection(polys, array=np.array(vals), cmap="YlOrRd", edgecolor="white", linewidth=0.15)
    pc.autoscale()
    ax1.add_collection(pc)
    ax1.autoscale_view()
    ax1.set_aspect("equal")
    ax1.axis("off")
    fig.colorbar(pc, ax=ax1, shrink=0.55, pad=0.01, format=mtick.PercentFormatter(), label="Underemployment rate (%)")
    ax1.set_title("A. Underemployment Rate by Region of Residence", fontsize=11, weight="bold")

    s = df.sort_values("underemp_rate_pct")
    bars = ax2.barh(s.index, s["underemp_rate_pct"], xerr=1.96 * s["se_underemp_rate_pp"], capsize=2.5,
                    color=pc.cmap(pc.norm(s["underemp_rate_pct"])), edgecolor="#555555", linewidth=0.4)
    ax2.bar_label(bars, [f"{r:.1f}%  ({k:,.0f}k)" for r, k in zip(s["underemp_rate_pct"], s["avg_underemp_k"])],
                  padding=14, fontsize=8, weight="bold")
    ax2.set(xlim=(0, s["underemp_rate_pct"].max() * 1.35), xlabel="Underemployment rate (%), whiskers = 95% CI")
    ax2.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax2.set_title("B. Regions Ranked (rate and number underemployed)", fontsize=11, weight="bold")
    _save_fig("Figure 8. Underemployment by Region of Residence (2025, average of Jan/Apr/Jul/Oct rounds)",
              "fig8_region_map.png", y=1.0)
    print(f"      Saved regional map in: {FIG_DIR}")


# ==============================================================================
# RESEARCH QUESTIONS 1, 2, AND 3 DIRECT TABLES & FIGURES
# ==============================================================================
def _draw_rq1(ax: plt.Axes, df: pd.DataFrame, col: str, title: str, label: str, horizontal: bool = False) -> None:
    df_p = df.iloc[::-1] if horizontal else df
    sep = " " if horizontal else "\n"
    bars = (ax.barh(df_p[col], df_p["avg_underemp_k"], height=0.62, color="#2b5c8f") if horizontal
            else ax.bar(df_p[col], df_p["avg_underemp_k"], width=0.45 if len(df_p) <= 3 else 0.52, color="#2b5c8f"))
    labels = []
    for bar, r in zip(bars, df_p.itertuples()):
        _style_bar_cv(bar, r.cv_underemp_pct)
        labels.append(f"{r.avg_underemp_k:,.0f}k{_flag_suffix(r.cv_underemp_pct)}{sep}({r.share_of_national_underemp_pct:.1f}%)")
    ax.bar_label(bars, labels, padding=3, fontsize=8.5, weight="bold")
    lim = df_p["avg_underemp_k"].max() * (1.30 if horizontal else 1.25)
    if horizontal:
        ax.set(xlim=(0, lim), xlabel="Average Monthly Underemployed (in Thousands)", ylabel=label)
    else:
        ax.set(ylim=(0, lim), ylabel="Average Monthly Underemployed (in Thousands)", xlabel=label)
    ax.set_title(title, fontsize=11, weight="bold")


def _draw_rq2(ax: plt.Axes, df: pd.DataFrame, col: str, title: str, label: str, horizontal: bool = False) -> None:
    df_p = df.iloc[::-1] if horizontal else df
    pos, w = np.arange(len(df_p)), (0.38 if horizontal else 0.36)
    bar = ax.barh if horizontal else ax.bar
    b_vis = bar(pos + (w / 2 if horizontal else -w / 2), df_p["avg_visible_k"], w, label="Visibly (<40 hrs)", color="#2b5c8f")
    b_inv = bar(pos + (-w / 2 if horizontal else w / 2), df_p["avg_invisible_k"], w, label="Invisibly (40+ hrs)", color="#e68a00")
    sep, fs = (" ", 7.5) if horizontal else ("\n", 8.0)
    vis_labels, inv_labels = [], []
    for bv, bi, r in zip(b_vis, b_inv, df_p.itertuples()):
        _style_bar_cv(bv, r.cv_underemp_pct)
        _style_bar_cv(bi, r.cv_underemp_pct)
        sfx = _flag_suffix(r.cv_underemp_pct)
        vis_labels.append(f"{r.avg_visible_k:,.0f}k{sfx}{sep}({r.visible_share_within_group_pct:.1f}%)")
        inv_labels.append(f"{r.avg_invisible_k:,.0f}k{sfx}{sep}({r.invisible_share_within_group_pct:.1f}%)")
    ax.bar_label(b_vis, vis_labels, padding=3, fontsize=fs, weight="bold", color="#1b3b5c")
    ax.bar_label(b_inv, inv_labels, padding=3, fontsize=fs, weight="bold", color="#995c00")
    lim = max(df_p["avg_visible_k"].max(), df_p["avg_invisible_k"].max()) * (1.34 if horizontal else 1.28)
    if horizontal:
        ax.set(yticks=pos, yticklabels=df_p[col], xlim=(0, lim), xlabel="Average Monthly Underemployed (in Thousands)", ylabel=label)
        ax.legend(frameon=True, loc="lower right")
    else:
        ax.set(xticks=pos, xticklabels=df_p[col], ylim=(0, lim), ylabel="Average Monthly Underemployed (in Thousands)", xlabel=label)
        ax.legend(frameon=True, loc="upper left" if col == "sector_short" else "upper right")
    ax.set_title(title, fontsize=11, weight="bold")


def generate_rq_figures(rq_tables: dict[str, pd.DataFrame]) -> None:
    print("[RQ 1-3] Generating 300-DPI figures for Research Questions 1, 2, and 3...")
    df_d = rq_tables["RQ1_RQ2_d1_Broad_Industry"].assign(sector_short=lambda d: d["broad_sector"].map(SECTOR_SHORT))
    # (table, category column, axis label, horizontal bars?, RQ1 panel title, RQ2 panel title)
    panels = [
        (rq_tables["RQ1_RQ2_a_Age"], "age_group", "Age Group (Years)", False,
         "1a. Total Underemployed Workers by Age Group (2025 Annual Average)",
         "2a. Visibly and Invisibly Underemployed Workers by Age Group (2025 Annual Average)"),
        (rq_tables["RQ1_RQ2_b_Sex"], "sex", "Sex", False,
         "1b. Total Underemployed Workers by Sex (2025 Annual Average)",
         "2b. Visibly and Invisibly Underemployed Workers by Sex (2025 Annual Average)"),
        (rq_tables["RQ1_RQ2_c_Education"], "educ_group", "Highest Grade Completed", True,
         "1c. Total Underemployed Workers by Educational Attainment (2025 Annual Average)",
         "2c. Visibly and Invisibly Underemployed Workers by Educational Attainment (2025 Annual Average)"),
        (df_d, "sector_short", "Broad Industry Sector (AFF, Industry, Services)", False,
         "1d. Total Underemployed Workers by Broad Industry Sector (2025 Annual Average)",
         "2d. Visibly and Invisibly Underemployed Workers by Broad Industry Sector (2025 Annual Average)"),
    ]
    for fn, idx_t, fsize, suptitle, out in [
        (_draw_rq1, 0, (16, 12), "Research Question 1: Number and % Distribution of Total Underemployed Workers (2025 Annual Average)", "fig_RQ1_total_underemployment_4panel.png"),
        (_draw_rq2, 1, (17, 12.5), "Research Question 2: Number and Within-Group % Share of Visibly and Invisibly Underemployed Workers (2025 Annual Average)", "fig_RQ2_visible_invisible_4panel.png"),
    ]:
        fig, axes = plt.subplots(2, 2, figsize=fsize, dpi=300)
        for ax, (df, col, label, horiz, *titles) in zip(axes.flat, panels):
            fn(ax, df, col, titles[idx_t], label, horizontal=horiz)
        _save_fig(suptitle, out, y=1.01)

    # Figure RQ3: Monthly Patterns in Number & Distribution Throughout 2025
    df_m = rq_tables["RQ3_Monthly_Overall"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.5, 5.8), dpi=300)
    b1 = ax1.bar(df_m["month_name"], df_m["visible_k"], label="Visibly Underemployed (<40 hrs)", color="#2b5c8f")
    b2 = ax1.bar(df_m["month_name"], df_m["invisible_k"], bottom=df_m["visible_k"], label="Invisibly Underemployed (40+ hrs)", color="#e68a00")
    ax1.bar_label(b1, [f"{r.visible_k:,.0f}k\n({r.visible_share_pct:.1f}%)" for r in df_m.itertuples()], label_type="center", color="white", fontsize=6.8, weight="bold")
    ax1.bar_label(b2, [f"{r.invisible_k:,.0f}k\n({r.invisible_share_pct:.1f}%)" for r in df_m.itertuples()], label_type="center", color="white", fontsize=6.8, weight="bold")
    ax1.bar_label(b2, [f"{v:,.0f}k" for v in df_m["underemp_k"]], padding=3, fontsize=8.0, weight="bold")
    ax1.set(ylim=(0, df_m["underemp_k"].max() * 1.18), xlabel="Month (2025)", ylabel="Number of Underemployed Persons (in Thousands)")
    ax1.set_title("A. Monthly Number & % Share of Visibly and Invisibly Underemployed (in Thousands)", fontsize=11, weight="bold")
    ax1.legend(frameon=True, loc="upper right")

    ax2_twin = ax2.twinx()
    s1 = ax2.bar(df_m["month_name"], df_m["visible_share_pct"], label="Visible % Share (<40 hrs)", color="#2b5c8f", alpha=0.35)
    s2 = ax2.bar(df_m["month_name"], df_m["invisible_share_pct"], bottom=df_m["visible_share_pct"], label="Invisible % Share (40+ hrs)", color="#e68a00", alpha=0.35)
    l1 = ax2_twin.plot(df_m["month_name"], df_m["underemp_rate_pct"], color="#b30000", marker="o", lw=2.5, label="National Underemployment Rate (%)")
    ax2.bar_label(s1, [f"{v:.1f}%" for v in df_m["visible_share_pct"]], label_type="center", color="#1b3b5c", fontsize=7.2, weight="bold")
    ax2.bar_label(s2, [f"{v:.1f}%" for v in df_m["invisible_share_pct"]], label_type="center", color="#804d00", fontsize=7.2, weight="bold")
    for i, v in enumerate(df_m["underemp_rate_pct"]):
        ax2_twin.annotate(f"{v:.1f}%", (i, v), xytext=(0, 8), textcoords="offset points", ha="center",
                          color="#b30000", fontsize=8.0, weight="bold",
                          bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.8))
    ax2.set(ylim=(0, 100), xlabel="Month (2025)", ylabel="Share of Underemployed (%)")
    ax2.set_title("B. Monthly % Distribution (Visible vs. Invisible) & National Rate (%)", fontsize=11, weight="bold")
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax2_twin.set_ylabel("National Underemployment Rate (%)", color="#b30000")
    ax2_twin.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax2_twin.set_ylim(0, 22)
    ax2_twin.grid(False)
    handles = [s1, s2, l1[0]]
    ax2.legend(handles, [h.get_label() for h in handles], frameon=True, loc="lower left", fontsize=8.5)
    _save_fig("Research Question 3: Monthly Patterns in the Number and Distribution of Underemployed Workers (2025)",
              "fig_RQ3_monthly_number_and_distribution.png", y=1.02)

    print(f"      Saved 3 RQ figures in {FIG_DIR}")