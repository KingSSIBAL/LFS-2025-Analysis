-- Analysis table and variance design for the 2025 LFS PUF. Run by tables.create_analytical_view().
-- Placeholders filled in by Python: {parquet} = consolidated PUF Parquet path, {dom} = the 117-domain expression.
-- Source tags ([TN p.X], [DICT]) refer to the SOURCES list in lfs.py.

-- Monthly PUFs have no PUFREG; map each of the 117 work domains to its modal residence region (quarterly rounds).
-- ponytail: workplace region != residence region (NCR +19%, CALABARZON -11%); it can never be checked vs PSA.
CREATE OR REPLACE TABLE work_dom_region AS
SELECT work_dom, arg_max(rcode, w) AS wcode
FROM (
    SELECT {dom} AS work_dom, TRIM(PUFREG) AS rcode, SUM(TRY_CAST(TRIM(PUFPWGTPRV) AS DOUBLE)) AS w
    FROM '{parquet}'
    WHERE NULLIF(TRIM(PUFREG), '') IS NOT NULL AND TRIM(PUFC12A_PROVMUN) <> ''
    GROUP BY 1, 2
)
GROUP BY 1;

-- Variance design [TN p.3-5, p.8]: 117 province/HUC strata, contiguous PSU runs along PUFHHNUM (with tight island
-- reunification when split), residence-region constraint in both quarterly (PUFREG) and monthly (block-smoothed)
-- rounds, full 3-PSU block commuter smoothing, and 2-stage FPC with urban B = 25 / rural B = 15 [TN p.3, p.7].
CREATE OR REPLACE TABLE hh_psu AS
WITH hh AS (
    SELECT TRY_CAST(TRIM(PUFSVYMO) AS INTEGER) AS m, TRY_CAST(TRIM(PUFHHNUM) AS INTEGER) AS hh_num,
           TRIM(PUFHHNUM) AS hh, TRIM(PUFRPL) AS rpl, TRIM(PUFPSU) AS psu,
           NULLIF(TRIM(PUFREG), '') AS reg_code,
           AVG(TRY_CAST(TRIM(PUFPWGTPRV) AS DOUBLE)) AS w_hh,
           mode(TRIM(PUFURB2020) ORDER BY TRIM(PUFURB2020)) FILTER (WHERE TRIM(PUFURB2020) IN ('1', '2')) AS urb,
           mode(d.work_dom ORDER BY d.work_dom) FILTER (WHERE TRIM(PUFC12A_PROVMUN) <> '') AS hh_dom_any,
           mode(wp.wcode ORDER BY wp.wcode) FILTER (WHERE TRIM(PUFC12A_PROVMUN) <> '') AS hh_wreg,
           mode(d.work_dom ORDER BY d.work_dom) FILTER (
               WHERE TRIM(PUFC12A_PROVMUN) <> ''
                 AND (NULLIF(TRIM(PUFREG), '') IS NULL OR wp.wcode = NULLIF(TRIM(PUFREG), ''))
           ) AS hh_dom_qtr
    FROM '{parquet}'
    LEFT JOIN LATERAL (SELECT {dom} AS work_dom) d ON TRUE
    LEFT JOIN work_dom_region wp ON wp.work_dom = d.work_dom
    GROUP BY 1, 2, 3, 4, 5, 6
), lagged AS (
    SELECT *, CASE WHEN rpl = LAG(rpl) OVER (PARTITION BY m ORDER BY hh_num)
                    AND psu = LAG(psu) OVER (PARTITION BY m ORDER BY hh_num)
                    AND reg_code IS NOT DISTINCT FROM LAG(reg_code) OVER (PARTITION BY m ORDER BY hh_num)
                   THEN 0 ELSE 1 END AS is_new
    FROM hh
), runs AS (
    SELECT m, hh_num, hh, rpl, psu, reg_code, urb, w_hh, hh_dom_any, hh_wreg, hh_dom_qtr,
           SUM(is_new) OVER (PARTITION BY m ORDER BY hh_num) AS run_id
    FROM lagged
), run_reg_raw AS (
    SELECT m, run_id, ANY_VALUE(reg_code) AS reg_code,
           mode(hh_wreg ORDER BY hh_wreg) FILTER (WHERE hh_wreg IS NOT NULL) AS r_raw
    FROM runs GROUP BY 1, 2
), run_reg_nb AS (
    SELECT *,
           LAG(r_raw, 1 IGNORE NULLS) OVER w AS rp1, LEAD(r_raw, 1 IGNORE NULLS) OVER w AS rn1,
           LAG(r_raw, 2 IGNORE NULLS) OVER w AS rp2, LEAD(r_raw, 2 IGNORE NULLS) OVER w AS rn2,
           LAG(r_raw, 3 IGNORE NULLS) OVER w AS rp3, LEAD(r_raw, 3 IGNORE NULLS) OVER w AS rn3
    FROM run_reg_raw WINDOW w AS (PARTITION BY m ORDER BY run_id)
), run_eff_reg AS (
    SELECT m, run_id,
           COALESCE(
               reg_code,
               CASE
                   WHEN rp1 = rn1 AND rp1 IS NOT NULL THEN rp1
                   WHEN rp1 = rp2 AND rp1 = rn2 AND rp1 IS NOT NULL THEN rp1
                   WHEN rn1 = rn2 AND rn1 = rp2 AND rn1 IS NOT NULL THEN rn1
                   WHEN rp1 = rp2 AND rp1 = rn3 AND rp1 IS NOT NULL THEN rp1
                   WHEN rn1 = rn2 AND rn1 = rp3 AND rn1 IS NOT NULL THEN rn1
                   WHEN rp2 = rn2 AND rp2 = rp3 AND rp2 = rn3 AND rp2 IS NOT NULL THEN rp2
                   ELSE COALESCE(r_raw, rp1, rn1, rp2, rn2, rp3, rn3)
               END
           ) AS eff_reg
    FROM run_reg_nb
), raw_runs AS (
    SELECT r.m, r.run_id, ANY_VALUE(r.rpl) AS rpl, ANY_VALUE(r.psu) AS psu,
           ANY_VALUE(r.reg_code) AS reg_code, ANY_VALUE(er.eff_reg) AS eff_reg,
           MIN(r.hh_num) AS min_hh, MAX(r.hh_num) AS max_hh,
           mode(r.urb ORDER BY r.urb) AS urb,
           COALESCE(
               mode(r.hh_dom_any ORDER BY r.hh_dom_any) FILTER (WHERE r.hh_dom_any IS NOT NULL AND r.hh_wreg = er.eff_reg),
               mode(r.hh_dom_qtr ORDER BY r.hh_dom_qtr) FILTER (WHERE r.hh_dom_qtr IS NOT NULL)
           ) AS s,
           COUNT(*) AS b, SUM(r.w_hh) AS psu_hh
    FROM runs r
    JOIN run_eff_reg er USING (m, run_id)
    GROUP BY 1, 2
), nb AS (
    SELECT *,
           LAG(s, 1 IGNORE NULLS) OVER w AS p1, LEAD(s, 1 IGNORE NULLS) OVER w AS n1,
           LAG(s, 2 IGNORE NULLS) OVER w AS p2, LEAD(s, 2 IGNORE NULLS) OVER w AS n2,
           LAG(s, 3 IGNORE NULLS) OVER w AS p3, LEAD(s, 3 IGNORE NULLS) OVER w AS n3
    FROM raw_runs WINDOW w AS (PARTITION BY m, eff_reg ORDER BY run_id)
), smoothed_runs AS (
    SELECT m, run_id, rpl, psu, reg_code, eff_reg, min_hh, max_hh, urb, b, psu_hh,
           COALESCE(
               CASE
                   WHEN p1 = n1 AND p1 IS NOT NULL THEN p1
                   WHEN p1 = p2 AND p1 = n2 AND p1 IS NOT NULL THEN p1
                   WHEN n1 = n2 AND n1 = p2 AND n1 IS NOT NULL THEN n1
                   WHEN p1 = p2 AND p1 = n3 AND p1 IS NOT NULL THEN p1
                   WHEN n1 = n2 AND n1 = p3 AND n1 IS NOT NULL THEN n1
                   WHEN p2 = n2 AND p2 = p3 AND p2 = n3 AND p2 IS NOT NULL THEN p2
                   ELSE COALESCE(s, p1, n1, p2, n2, p3, n3)
               END,
               (SELECT work_dom FROM work_dom_region wp WHERE wp.wcode = nb.eff_reg LIMIT 1)
           ) AS strat
    FROM nb
), island_flags AS (
    SELECT *,
           CASE WHEN min_hh - LAG(max_hh) OVER (PARTITION BY m, strat, rpl, psu ORDER BY run_id) < 150
                THEN 0 ELSE 1 END AS is_new_island
    FROM smoothed_runs
), islands AS (
    SELECT *,
           SUM(is_new_island) OVER (PARTITION BY m, strat, rpl, psu ORDER BY run_id) AS island_id
    FROM island_flags
), merged_runs AS (
    SELECT *,
           CASE WHEN SUM(b) OVER (PARTITION BY m, strat, rpl, psu, island_id) <= 30
                THEN MIN(run_id) OVER (PARTITION BY m, strat, rpl, psu, island_id)
                ELSE run_id END AS psu_id
    FROM islands
)
SELECT r.m, r.hh, r.reg_code, r.urb, r.w_hh, r.hh_dom_qtr AS hh_dom, mr.psu_id, mr.strat
FROM runs r
JOIN merged_runs mr USING (m, run_id);

-- psu_frame: one row per reunited PSU with its smoothed residence stratum and urban/rural frame household size.
CREATE OR REPLACE TABLE psu_frame AS
SELECT m, psu_id, strat,
       COUNT(*) AS b, SUM(w_hh) AS psu_hh,
       CASE WHEN mode(urb ORDER BY urb) = '1' THEN 25.0 ELSE 15.0 END AS b_frame
FROM hh_psu GROUP BY 1, 2, 3;

-- stratum_frame: a_p = sampled PSUs in stratum p; A_p = SUM(psu_hh / b_frame) within (m, strat) so that any
-- month-to-month boundary jitter in a_p cancels between numerator and denominator.
CREATE OR REPLACE TABLE stratum_frame AS
SELECT m, strat, COUNT(*) AS a_p,
       COUNT(*) / GREATEST(COUNT(*)::DOUBLE, SUM(psu_hh / b_frame)) AS f1
FROM psu_frame GROUP BY 1, 2;

-- Materialized TABLE (instead of VIEW) so 80+ downstream table and variance queries do not re-read Parquet and re-join.
-- One row per employed person aged 15+ [TN p.1]. coded: cast raw text once; sector/industry from the PSIC 2-digit
-- division (PUFC16_PKB), education from the 5-digit PUFC07_GRADE code collapsed to PSA's 11 published groups.
CREATE OR REPLACE TABLE lfs_employed_2025 AS
WITH coded AS (
    SELECT
        TRY_CAST(TRIM(PUFSVYMO) AS INTEGER) AS month_num,
        TRIM(PUFHHNUM) AS hh,
        TRY_CAST(TRIM(PUFPWGTPRV) AS DOUBLE) AS wgt,
        NULLIF(TRIM(PUFREG), '') AS reg_code,
        {dom} AS work_dom,
        TRY_CAST(TRIM(PUFC05_AGE) AS INTEGER) AS age,
        TRIM(PUFC04_SEX) AS sex_code,
        TRY_CAST(TRIM(PUFC07_GRADE) AS INTEGER) AS grade_num,
        TRIM(PUFNEWEMPSTAT) AS empstat,
        TRIM(PUFC20_PWMORE) AS pwmore,
        TRY_CAST(TRIM(PUFC19_PHOURS) AS INTEGER) AS phours,
        TRY_CAST(TRIM(PUFC16_PKB) AS INTEGER) AS pkb,
        CASE WHEN pkb BETWEEN 1 AND 3 THEN 1 WHEN pkb BETWEEN 5 AND 43 THEN 2 WHEN pkb BETWEEN 45 AND 99 THEN 3 ELSE 4 END AS sector_order,
        CASE
            WHEN pkb BETWEEN 1 AND 2 THEN 1   WHEN pkb = 3 THEN 2              WHEN pkb BETWEEN 5 AND 9 THEN 3
            WHEN pkb BETWEEN 10 AND 33 THEN 4 WHEN pkb = 35 THEN 5             WHEN pkb BETWEEN 36 AND 39 THEN 6
            WHEN pkb BETWEEN 41 AND 43 THEN 7 WHEN pkb BETWEEN 45 AND 47 THEN 8 WHEN pkb BETWEEN 49 AND 53 THEN 9
            WHEN pkb BETWEEN 55 AND 56 THEN 10 WHEN pkb BETWEEN 58 AND 63 THEN 11 WHEN pkb BETWEEN 64 AND 66 THEN 12
            WHEN pkb = 68 THEN 13             WHEN pkb BETWEEN 69 AND 75 THEN 14 WHEN pkb BETWEEN 77 AND 82 THEN 15
            WHEN pkb = 84 THEN 16             WHEN pkb = 85 THEN 17            WHEN pkb BETWEEN 86 AND 88 THEN 18
            WHEN pkb BETWEEN 90 AND 93 THEN 19 WHEN pkb BETWEEN 94 AND 96 THEN 20 WHEN pkb BETWEEN 97 AND 98 THEN 21
            WHEN pkb = 99 THEN 22 ELSE 99
        END AS major_industry_order,
        CASE
            WHEN age BETWEEN 15 AND 24 THEN 1 WHEN age BETWEEN 25 AND 34 THEN 2 WHEN age BETWEEN 35 AND 44 THEN 3
            WHEN age BETWEEN 45 AND 54 THEN 4 WHEN age BETWEEN 55 AND 64 THEN 5 WHEN age >= 65 THEN 6
        END AS age_order,
        CASE
            WHEN (grade_num BETWEEN 0 AND 1000) OR (grade_num = 2000) THEN 1
            WHEN (grade_num BETWEEN 10011 AND 10015) OR (grade_num BETWEEN 10004 AND 10006) THEN 2
            WHEN grade_num BETWEEN 10016 AND 10018 THEN 3
            WHEN (grade_num BETWEEN 24011 AND 24013) OR (grade_num BETWEEN 24004 AND 24006) THEN 4
            WHEN grade_num BETWEEN 24014 AND 24015 THEN 5
            WHEN grade_num IN (34011, 34021, 34031, 35011) THEN 6
            WHEN grade_num IN (34013, 34023, 34033, 35013) THEN 7
            WHEN (grade_num BETWEEN 40001 AND 40003) OR (grade_num BETWEEN 50001 AND 50003) THEN 8
            WHEN (grade_num BETWEEN 40011 AND 49999) OR (grade_num BETWEEN 50011 AND 59999) THEN 9
            WHEN grade_num BETWEEN 60001 AND 60006 THEN 10
            WHEN (grade_num = 60000) OR (grade_num BETWEEN 60011 AND 89999) THEN 11
            ELSE 99
        END AS educ_code
    FROM '{parquet}'
)
SELECT
    month_num, strftime(make_date(2025, month_num, 1), '%b') AS month_name,
    wgt, age, pwmore, phours, ps.strat, hp.psu_id, coded.hh,
    COALESCE(['Agriculture, Forestry, and Fisheries', 'Industry', 'Services'][sector_order], 'Not Reported') AS broad_sector,
    sector_order,
    COALESCE([
        'Agriculture and Forestry', 'Fishing and Aquaculture', 'Mining and Quarrying',
        'Manufacturing', 'Electricity, Gas, Steam, and Air Conditioning Supply',
        'Water Supply; Sewerage, Waste Management', 'Construction',
        'Wholesale and Retail Trade; Repair of Motor Vehicles', 'Transportation and Storage',
        'Accommodation and Food Service Activities', 'Information and Communication',
        'Financial and Insurance Activities', 'Real Estate Activities',
        'Professional, Scientific and Technical Activities', 'Administrative and Support Service Activities',
        'Public Administration and Defense', 'Education', 'Human Health and Social Work Activities',
        'Arts, Entertainment and Recreation', 'Other Service Activities',
        'Activities of Households as Employers', 'Activities of Extraterritorial Organizations'
    ][major_industry_order], 'Not Reported') AS major_industry,
    major_industry_order,
    CASE sex_code WHEN '1' THEN 'Male' WHEN '2' THEN 'Female' END AS sex,
    ['15-24', '25-34', '35-44', '45-54', '55-64', '65 and Over'][age_order] AS age_group, age_order,
    CASE
        WHEN phours IS NULL OR phours = 0 THEN 'Did not work (With a job, not at work)'
        WHEN phours BETWEEN 1 AND 39 THEN 'Worked less than 40 hours (1-39 hrs)'
        WHEN phours >= 40 THEN 'Worked 40 hours and over'
    END AS hours_category,
    -- [TN p.1-2]: underemployed = wants more hours; visible = under 40 hours (incl. with a job, not at work)
    CASE
        WHEN pwmore = '1' AND (phours IS NULL OR phours < 40) THEN 'Visibly Underemployed (<40 hrs)'
        WHEN pwmore = '1' AND phours >= 40 THEN 'Invisibly Underemployed (40+ hrs)'
        ELSE 'Not Underemployed'
    END AS underemp_type,
    educ_code,
    COALESCE([
        'No grade completed', 'Elementary Undergraduate', 'Elementary Graduate',
        'Junior High Undergraduate', 'Junior High Completed', 'Senior High Undergraduate',
        'Senior High Graduate', 'Post Secondary Undergraduate', 'Post Secondary Graduate',
        'College Undergraduate', 'College Graduate'
    ][educ_code], 'Not Reported') AS educ_group,
    r.rname AS region, r.rord AS region_order, rw.rname AS work_region, rw.rord AS work_region_order
FROM coded
LEFT JOIN region_names r ON r.rcode = coded.reg_code
LEFT JOIN work_dom_region wp ON wp.work_dom = coded.work_dom
LEFT JOIN region_names rw ON rw.rcode = wp.wcode
LEFT JOIN hh_psu hp ON hp.m = coded.month_num AND hp.hh = coded.hh
LEFT JOIN psu_frame ps ON ps.m = hp.m AND ps.psu_id = hp.psu_id
WHERE age >= 15 AND empstat = '1' AND pkb IS NOT NULL;