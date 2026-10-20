"""Compare drafts/data (independent build by Dr. Woo-Sik Son) with data/processed.

Joins on the week start date and prints, per series, how many values agree and
which differ. See docs/sources/kdca_sentinel.md, "Cross-check with an
independent dataset".
"""

import pandas as pd

from common import PROCESSED, ROOT

D = ROOT / "drafts" / "data"
P = PROCESSED


def report(name, merged, a, b, tol):
    both = merged.dropna(subset=[a, b])
    diff = (both[a] - both[b]).abs()
    bad = both[diff > tol]
    only_a = merged[merged[b].isna() & merged[a].notna()]
    only_b = merged[merged[a].isna() & merged[b].notna()]
    print(f"\n=== {name}")
    equal = len(both) - len(bad)
    print(f"overlap {len(both)}; equal (|diff|<={tol}) {equal}; differ {len(bad)}")
    print(f"only theirs {len(only_a)}; only ours {len(only_b)}")
    return both, bad, only_a, only_b


# --- ILI ---
t = pd.read_csv(f"{D}/ili_surveillance_2008w02-2026w41.csv")
o = pd.read_csv(f"{P}/kdca_sentinel_ili.csv", dtype={"region_code": str})
o = o[o.region_code == "00"].rename(columns={"date_start": "week_start_date"})
o = o[["week_start_date", "year", "week", "age_group", "value"]]
m = t.merge(o, on=["week_start_date", "age_group"], how="outer", suffixes=("_t", "_o"))
m = m[m.week_start_date >= "2008-01-06"]
both, bad, only_t, only_o = report("ILI", m, "ili_rate", "value", 0.051)
wk = both[(both.year_t != both.year_o) | (both.week_t != both.week_o)]
print("week label mismatches:", len(wk))
print("differences by age group:", bad.age_group.value_counts().to_dict())
print(
    bad.sort_values("week_start_date")[
        ["week_start_date", "year_t", "week_t", "age_group", "ili_rate", "value"]
    ].to_string(index=False)
)
print("only theirs:")
print(
    only_t.groupby("age_group").week_start_date.agg(["count", "min", "max"]).to_string()
)
print("only ours:")
print(
    only_o.groupby("age_group").week_start_date.agg(["count", "min", "max"]).to_string()
)

# --- Positivity ---
t = pd.read_csv(f"{D}/flu_positivity_2009w22-2026w41.csv")
f = pd.read_csv(f"{P}/kdca_lab_flunet.csv")
f["virus"] = f.category.str.extract(r"virus=([^;]+)")[0]
tested = f[f.indicator == "specimens_tested"].set_index("date_start").value
det = f[f.indicator == "flu_detections"].pivot_table(
    index="date_start", columns="virus", values="value", aggfunc="sum"
)
rows = []
for vt, col in [("total", "influenza"), ("A", "A"), ("B", "B")]:
    r = (100 * det[col] / tested).round(1).rename("ours").reset_index()
    r["virus_type"] = vt
    rows.append(r)
ours = pd.concat(rows).rename(columns={"date_start": "week_start_date"})
k = pd.read_csv(f"{P}/kdca_sentinel_virus.csv")
k = k[k.indicator == "flu_positivity"][["date_start", "value"]].rename(
    columns={"date_start": "week_start_date", "value": "bulletin"}
)
m = t.merge(ours, on=["week_start_date", "virus_type"], how="left").merge(
    k, on="week_start_date", how="left"
)
for src in ["WHO", "KDCA"]:
    s = m[m.source == src]
    both, bad, *_ = report(
        f"Positivity ({src} rows) vs our FluNet", s, "positivity_rate", "ours", 0.11
    )
    print(
        bad[["week_start_date", "virus_type", "positivity_rate", "ours"]]
        .head(20)
        .to_string(index=False)
    )
s = m[(m.source == "KDCA") & (m.virus_type == "total")]
report(
    "Positivity (KDCA rows, total) vs our bulletins",
    s,
    "positivity_rate",
    "bulletin",
    0.11,
)
print(
    s[["week_start_date", "positivity_rate", "ours", "bulletin"]].to_string(index=False)
)
miss = m[m.ours.isna()]
print(
    "their weeks without our FluNet value:",
    len(miss),
    miss.groupby("source").size().to_dict(),
)

# --- SARI ---
t = pd.read_csv(f"{D}/sari_weekly_2020w20-2026w41.csv")
h = pd.read_csv(f"{P}/kdca_sentinel_hospital.csv")
h = h[h.indicator == "sari_new_patients"][["date_start", "value"]].rename(
    columns={"date_start": "week_start_date"}
)
m = t.merge(h, on="week_start_date", how="outer")
m = m[m.week_start_date >= "2020-05-10"]
both, bad, only_t, only_o = report("SARI new patients", m, "count", "value", 0)
print(bad[["week_start_date", "count", "value", "method"]].to_string(index=False))
print(
    "only theirs by year:",
    only_t.week_start_date.str[:4].value_counts().sort_index().to_dict(),
)
