"""Laboratory surveillance: WHO FluNet data reported by Korea (KDCA).

The Power BI report in `drafts/Korea FLU.md` is the public WHO FluNet dashboard
(model `GIP_PublicOutputs_FluNet_DownloadData`). The same table is published by
the WHO xMart OData API, which this script uses as the primary download. A small
Power BI `querydata` call checks that the API and the dashboard agree.

Run: .venv/bin/python -E -s scripts/kdca_lab.py
"""

import base64
import json
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW, REGIONS, epi_week, season_of, write_tidy  # noqa: E402

OUT = RAW / "kdca_lab"

XMART_URL = "https://xmart-api-public.who.int/FLUMART/VIW_FNT"
REPORT_TOKEN = (
    "eyJrIjoiNjViM2Y4NjktMjJmMC00Y2NjLWFmOWQtODQ0NjZkNWM1YzNmIiwidCI6ImY2MTBjMGI3LWJk"
    "MjQtNGIzOS04MTBiLTNkYzI4MGFmYjU5MCIsImMiOjh9"
)
ROUTERS = [
    "https://api.powerbi.com",
    "https://wabi-north-europe-n-primary-api.analysis.windows.net",
]

# FluNet column -> (indicator, category). Counts of specimens.
COUNT_COLUMNS = {
    "SPEC_RECEIVED_NB": ("specimens_received", "all"),
    "SPEC_PROCESSED_NB": ("specimens_tested", "all"),
    "INF_ALL": ("flu_detections", "virus=influenza"),
    "INF_A": ("flu_detections", "virus=A"),
    "AH1N12009": ("flu_detections", "virus=A(H1N1)pdm09"),
    "AH1": ("flu_detections", "virus=A(H1)"),
    "AH3": ("flu_detections", "virus=A(H3)"),
    "AH5": ("flu_detections", "virus=A(H5)"),
    "AH7N9": ("flu_detections", "virus=A(H7N9)"),
    "AOTHER_SUBTYPE": ("flu_detections", "virus=A(other subtype)"),
    "ANOTSUBTYPED": ("flu_detections", "virus=A(not subtyped)"),
    "INF_B": ("flu_detections", "virus=B"),
    "BVIC_NODEL": ("flu_detections", "virus=B(Victoria)"),
    "BYAM": ("flu_detections", "virus=B(Yamagata)"),
    "BNOTDETERMINED": ("flu_detections", "virus=B(lineage not determined)"),
    "INF_NEGATIVE": ("flu_negative", "all"),
    "RSV": ("rsv_detections", "virus=RSV"),
}

# FluNet ORIGIN_SOURCE -> surveillance system label used in `category`.
SYSTEMS = {
    "SENTINEL": "sentinel",
    "NONSENTINEL": "non_sentinel",
    "NOTDEFINED": "not_defined",
}


def download_xmart() -> Path:
    path = OUT / "flunet_kor.csv"
    resp = requests.get(
        XMART_URL,
        params={"$format": "csv", "$filter": "COUNTRY_CODE eq 'KOR'"},
        timeout=300,
    )
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path


def _powerbi_session() -> tuple[requests.Session, str, str]:
    token = json.loads(base64.b64decode(REPORT_TOKEN + "=="))
    key, tenant = token["k"], token["t"]
    s = requests.Session()
    s.headers.update({"X-PowerBI-ResourceKey": key, "Accept": "application/json"})
    # `api.powerbi.com` often drops the routing call; the default cluster of the
    # public viewer page answers it too.
    route = None
    for router in ROUTERS:
        try:
            route = s.get(
                f"{router}/public/routing/cluster/{tenant}", timeout=60
            ).json()
            break
        except requests.RequestException, ValueError:
            continue
    if route is None:
        raise RuntimeError("Power BI cluster routing failed")
    host = route["FixedClusterUri"].split("//")[1].split(".")[0]
    host = host.replace("-redirect", "").replace("global-", "") + "-api"
    return s, f"https://{host}.analysis.windows.net", key


def download_powerbi_sample() -> pd.DataFrame:
    """Korea rows of the dashboard table, for the cross-check only."""
    s, base, key = _powerbi_session()
    mae = s.get(
        f"{base}/public/reports/{key}/modelsAndExploration",
        params={"preferReadOnlySession": "true"},
        timeout=120,
    ).json()
    (OUT / "models_and_exploration.json").write_text(json.dumps(mae, indent=1))
    model_id = mae["models"][0]["id"]

    cols = ["ISO_SDATE", "ORIS_TYPE_CODE", "SPEC_PROCESSED_NB", "AH3", "INF_ALL"]

    def col(prop: str) -> dict:
        return {
            "Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": prop}
        }

    query = {
        "Version": 2,
        "From": [{"Name": "f", "Entity": "FluNet_Country", "Type": 0}],
        "Select": [{**col(c), "Name": f"f.{c}"} for c in cols],
        "Where": [
            {
                "Condition": {
                    "In": {
                        "Expressions": [col("ISO3")],
                        "Values": [[{"Literal": {"Value": "'KOR'"}}]],
                    }
                }
            }
        ],
    }
    body = {
        "version": "1.0.0",
        "queries": [
            {
                "Query": {
                    "Commands": [
                        {
                            "SemanticQueryDataShapeCommand": {
                                "Query": query,
                                "Binding": {
                                    "Primary": {
                                        "Groupings": [
                                            {"Projections": list(range(len(cols)))}
                                        ]
                                    },
                                    "DataReduction": {
                                        "DataVolume": 4,
                                        "Primary": {"Window": {"Count": 5000}},
                                    },
                                    "Version": 1,
                                },
                            }
                        }
                    ]
                }
            }
        ],
        "cancelQueries": [],
        "modelId": model_id,
    }
    resp = s.post(
        f"{base}/public/reports/querydata",
        params={"synchronous": "true"},
        json=body,
        timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()
    (OUT / "querydata_kor_sample.json").write_text(json.dumps(data))
    return pd.DataFrame(decode_dsr(data), columns=cols)


def decode_dsr(data: dict) -> list[list]:
    """Decode the compressed Power BI DSR rows of the first data shape.

    Each row lists only the values that change. Bit i of `R` means "repeat the
    previous value of column i", bit i of `Ø` means "column i is null". Strings
    may be indexes into `ValueDicts`.
    """
    ds = data["results"][0]["result"]["data"]["dsr"]["DS"][0]
    if ds.get("IC") is False or "RT" in ds:
        raise RuntimeError("querydata result is incomplete (window too small)")
    dicts = ds.get("ValueDicts", {})
    rows_raw = ds["PH"][0]["DM0"]
    schema = rows_raw[0]["S"]
    n = len(schema)
    prev: list = [None] * n
    rows = []
    for r in rows_raw:
        values = iter(r.get("C", []))
        repeat, null = r.get("R", 0), r.get("Ø", 0)
        row = []
        for i in range(n):
            if repeat >> i & 1:
                v = prev[i]
            elif null >> i & 1:
                v = None
            else:
                v = next(values)
                dn = schema[i].get("DN")
                if dn and isinstance(v, int):
                    v = dicts[dn][v]
            row.append(v)
        prev = row
        rows.append(row)
    return rows


def cross_check(api: pd.DataFrame, pbi: pd.DataFrame) -> str:
    pbi = pbi.add_prefix("pbi_")
    pbi["date"] = pd.to_datetime(pbi["pbi_ISO_SDATE"], unit="ms").dt.strftime(
        "%Y-%m-%d"
    )
    merged = api.merge(
        pbi,
        left_on=["ISO_WEEKSTARTDATE", "ORIGIN_SOURCE"],
        right_on=["date", "pbi_ORIS_TYPE_CODE"],
        how="inner",
    )
    lines = [f"API rows: {len(api)}, Power BI rows: {len(pbi)}, matched: {len(merged)}"]
    for column in ["SPEC_PROCESSED_NB", "AH3", "INF_ALL"]:
        a = pd.to_numeric(merged[column]).fillna(0)
        b = pd.to_numeric(merged[f"pbi_{column}"]).fillna(0)
        lines.append(f"{column}: {(a != b).sum()} mismatching weeks")
    return "\n".join(lines)


def clean(api: pd.DataFrame) -> pd.DataFrame:
    """Fix two reporting quirks of the Korea series.

    - A week reported under both NOTDEFINED and SENTINEL (2021-09-05) is kept
      once, as SENTINEL.
    - INF_ALL is empty when no influenza was detected. Where INF_A and INF_B are
      both reported, INF_ALL is their sum.
    """
    sentinel_weeks = set(
        api.loc[api["ORIGIN_SOURCE"] == "SENTINEL", "MMWR_WEEKSTARTDATE"]
    )
    dup = (api["ORIGIN_SOURCE"] == "NOTDEFINED") & api["MMWR_WEEKSTARTDATE"].isin(
        sentinel_weeks
    )
    api = api[~dup].copy()
    fill = api["INF_ALL"].isna() & api["INF_A"].notna() & api["INF_B"].notna()
    api.loc[fill, "INF_ALL"] = api.loc[fill, "INF_A"] + api.loc[fill, "INF_B"]
    return api


def tidy(api: pd.DataFrame) -> pd.DataFrame:
    # FluNet labels weeks with the MMWR rule; relabel them as KDCA epi weeks.
    weeks = [epi_week(d.date()) for d in pd.to_datetime(api["MMWR_WEEKSTARTDATE"])]
    years = [y for y, _ in weeks]
    numbers = [w for _, w in weeks]
    base = pd.DataFrame(
        {
            "source": "who_flunet",
            "period_type": "week",
            "date_start": api["MMWR_WEEKSTARTDATE"],
            "date_end": (
                pd.to_datetime(api["MMWR_WEEKSTARTDATE"]) + pd.Timedelta(days=6)
            ).dt.strftime("%Y-%m-%d"),
            "year": years,
            "week": numbers,
            "season": [season_of(y, w) for y, w in zip(years, numbers)],
            "region_code": "00",
            "region_name": REGIONS["00"],
            "age_group": "all",
            "sex": "all",
            "system": api["ORIGIN_SOURCE"].map(SYSTEMS),
        }
    )
    if base["system"].isna().any():
        raise ValueError(
            f"unknown ORIGIN_SOURCE {set(api['ORIGIN_SOURCE']) - set(SYSTEMS)}"
        )

    parts = []
    for column, (indicator, cat) in COUNT_COLUMNS.items():
        part = base.copy()
        part["indicator"] = indicator
        part["unit"] = "count"
        part["category"] = (
            "system=" + part["system"] + ("" if cat == "all" else ";" + cat)
        )
        part["value"] = pd.to_numeric(api[column])
        parts.append(part[part["value"].notna()])

    # Share of tested specimens positive for influenza, when both are reported.
    pos = base.copy()
    pos["indicator"] = "positivity_pct"
    pos["unit"] = "percent"
    pos["category"] = "system=" + pos["system"] + ";virus=influenza"
    tested = pd.to_numeric(api["SPEC_PROCESSED_NB"])
    pos["value"] = (
        (100 * pd.to_numeric(api["INF_ALL"]) / tested).where(tested > 0).round(2)
    )
    parts.append(pos[pos["value"].notna()])

    out = pd.concat(parts, ignore_index=True).drop(columns="system")
    return out.sort_values(["date_start", "indicator", "category"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    api = pd.read_csv(download_xmart())
    check = cross_check(api, download_powerbi_sample())
    (OUT / "cross_check.txt").write_text(check + "\n")
    print(check)
    path = write_tidy(tidy(clean(api)), "kdca_lab_flunet")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
