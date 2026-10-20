"""KOSIS table DT_INFLUENZA (Community Health Survey) -> common format.

"시·군·구별 연간 인플루엔자 예방접종률": share of adults who got a flu
vaccine in the last year, by province and si-gun-gu, 2008 onwards.

KOSIS blocks scripted calls to its download endpoint, so the download runs in a
headless browser (playwright): the script opens the table, replaces the
selection with all years, items and regions, and calls the page's own
"large download" (CSV). Writes data/processed/kosis_vaccination.csv.
"""

import io
import json
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from common import RAW, REGIONS, write_tidy

TABLE_URL = (
    "https://kosis.kr/statHtml/statHtml.do"
    "?orgId=177&tblId=DT_INFLUENZA&conn_path=I2&language=ko"
)
RAW_DIR = RAW / "kosis"
RAW_FILE = RAW_DIR / "kosis_DT_INFLUENZA.csv"
META_FILE = RAW_DIR / "kosis_DT_INFLUENZA_info.json"
TREE_FILE = RAW_DIR / "kosis_DT_INFLUENZA_regions.json"
NOTES_FILE = RAW_DIR / "kosis_DT_INFLUENZA_notes.txt"

# KOSIS province item id (level 1) -> Statistics Korea 2-digit code.
PROVINCES = {
    "001": "11",
    "002": "26",
    "003": "27",
    "004": "28",
    "005": "29",
    "006": "30",
    "007": "31",
    "0071": "36",
    "008": "41",
    "009": "51",
    "010": "43",
    "011": "44",
    "012": "52",
    "013": "46",
    "014": "47",
    "015": "48",
    "016": "50",
}

# KOSIS item -> (indicator, unit).
ITEMS = {
    "응답자수": ("respondents", "persons"),
    "조율": ("flu_vaccination_coverage_crude_pct", "percent"),
    "조율표준오차": ("flu_vaccination_coverage_crude_se", "percent"),
    "표준화율": ("flu_vaccination_coverage_standardized_pct", "percent"),
    "표준화율표준오차": ("flu_vaccination_coverage_standardized_se", "percent"),
}


def download() -> Path:
    """Download the whole table as CSV through the KOSIS web page."""
    from playwright.sync_api import sync_playwright

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(accept_downloads=True, locale="ko-KR")
        page.goto(TABLE_URL, wait_until="networkidle", timeout=120_000)
        frame = None
        for _ in range(60):
            frame = next((f for f in page.frames if "statHtmlContent" in f.url), None)
            if frame is not None and "g_jsonStatInfo" in frame.content():
                break
            page.wait_for_timeout(1000)
        if frame is None:
            raise RuntimeError("KOSIS content frame did not load")
        found = re.search(r"var g_jsonStatInfo\s*=\s*'(.*?)';\n", frame.content())
        info = json.loads(found.group(1))
        META_FILE.write_text(json.dumps(info, ensure_ascii=False, indent=1))
        page.wait_for_timeout(5000)
        # Region tree (ids, names, levels, parents): the CSV carries names only.
        tree = frame.evaluate(
            """() => {
                const rows = [];
                $.ui.fancytree.getTree('#fancytree_1').visit(n => {
                    rows.push({level: n.getLevel(), id: n.data.itmId, name: n.title,
                               parent: n.parent && n.parent.data ? n.parent.data.itmId || null : null});
                });
                return rows;
            }"""
        )
        TREE_FILE.write_text(json.dumps(tree, ensure_ascii=False, indent=1))
        notes = frame.evaluate(
            "() => { const e = document.getElementById('pop_cmmtInfoAll');"
            " return e ? e.innerText : ''; }"
        )
        NOTES_FILE.write_text(notes)
        years = info["periodInfo"]["listY"]
        items = info["itemInfo"]["defaultItmList"]
        regions = [x.split("#")[1] for x in info["classInfoList"][0]["defaultItmList"]]
        field_list = [
            {
                "targetId": "PRD",
                "targetValue": "",
                "prdValue": "Y," + ",".join(years) + ",@",
            }
        ]
        field_list += [
            {"targetId": "ITM_ID", "targetValue": i, "prdValue": ""} for i in items
        ]
        field_list += [
            {"targetId": "OV_L1_ID", "targetValue": r, "prdValue": ""} for r in regions
        ]
        fields = {
            "fieldList": json.dumps(field_list),
            "view": "csv",
            "viewSubKind": "2_7_2",
            "viewKind": "2",
            "itemMultiply": str(len(items) * len(regions)),
            "dimCo": str(info["dimCo"]),
        }
        # Same steps as the page's fn_downLargeSubmit, run inside the page.
        with page.expect_download(timeout=300_000) as event:
            frame.evaluate(
                """fields => {
                    const form = document.ParamInfo;
                    for (const [k, v] of Object.entries(fields)) { form[k].value = v; }
                    // "코드포함": add KOSIS region ids; names alone are ambiguous.
                    $('#exprYn').prop('checked', true);
                    if (form.exprYn) { form.exprYn.value = 'Y'; }
                    $(":radio[name='downLargeFileType'][value='csv']").prop('checked', true);
                    $(":radio[name='downLargeExprType'][value='2']").prop('checked', true);
                    $(":radio[name='downLargeSort'][value='asc']").prop('checked', true);
                    $.ajax({
                        dataType: 'json', type: 'POST', url: '/statHtml/makeLarge.do',
                        data: $(form).serialize(),
                        success: r => { form.action = '/statHtml/downLarge.do?file=' + r.file; form.submit(); },
                    });
                }""",
                fields,
            )
        event.value.save_as(RAW_FILE)
        browser.close()
    return RAW_FILE


def read(path: Path) -> pd.DataFrame:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp949")
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    return df.loc[:, ~df.columns.str.startswith("Unnamed")]


def tidy(df: pd.DataFrame, tree: list[dict]) -> pd.DataFrame:
    nodes = {n["id"]: n for n in tree}

    def province(kosis_id: str) -> str:
        while nodes[kosis_id]["level"] > 1:
            kosis_id = nodes[kosis_id]["parent"]
        return kosis_id

    def category(kosis_id: str) -> str:
        n = nodes[kosis_id]
        if n["level"] == 1:
            return "all"
        parts = [f"district_code={kosis_id}", f"district_name={n['name'].strip()}"]
        if n["level"] == 3:
            parts.append(f"parent_district_name={nodes[n['parent']]['name'].strip()}")
        return ";".join(parts)

    # Columns: region id ("코드포함" option), region name, period, items.
    df = df.rename(columns={df.columns[0]: "kosis_id"})
    df["kosis_id"] = df["kosis_id"].str.strip()
    missing = set(df["kosis_id"]) - set(nodes)
    if missing:
        raise ValueError(f"region ids not in the KOSIS tree: {missing}")
    time_col = df.columns[2]
    item_cols = {c: re.sub(r"\[.*\]$", "", c).strip() for c in df.columns[3:]}
    long = df.melt(
        id_vars=[time_col, "kosis_id"], value_vars=list(item_cols), var_name="item"
    )
    long["item"] = long["item"].map(item_cols)
    unknown = set(long["item"]) - set(ITEMS)
    if unknown:
        raise ValueError(f"unknown KOSIS items: {unknown}")
    long["value"] = pd.to_numeric(long["value"].str.strip(), errors="coerce")
    long = long.dropna(subset=["value"])
    long["year"] = long[time_col].str.extract(r"(\d{4})")[0].astype(int)
    long["indicator"] = long["item"].map(lambda i: ITEMS[i][0])
    long["unit"] = long["item"].map(lambda i: ITEMS[i][1])
    long["region_code"] = long["kosis_id"].map(lambda i: PROVINCES[province(i)])
    long["region_name"] = long["region_code"].map(REGIONS)
    long["category"] = long["kosis_id"].map(category)
    long["source"] = "kosis_chs"
    long["period_type"] = "year"
    # Fieldwork runs from mid-August to October; "last year" covers the
    # previous season's campaign (October onwards of the year before).
    long["date_start"] = [date(y, 8, 16) for y in long["year"]]
    long["date_end"] = [date(y, 10, 31) for y in long["year"]]
    long["week"] = pd.NA
    long["season"] = [f"{y - 1}-{y}" for y in long["year"]]
    long["age_group"] = "19+"
    long["sex"] = "all"
    return long.sort_values(["indicator", "region_code", "category", "year"])


def main() -> None:
    path = RAW_FILE if RAW_FILE.exists() and "--refresh" not in sys.argv else download()
    tree = json.loads(TREE_FILE.read_text())
    out = tidy(read(path), tree)
    rates = out[
        (out.indicator == "flu_vaccination_coverage_crude_pct")
        & (out.category == "all")
    ]
    print(
        rates.pivot(index="year", columns="region_name", values="value")
        .iloc[:, :6]
        .to_string()
    )
    print(out.groupby("indicator").size().to_string())
    print(write_tidy(out, "kosis_vaccination"))


if __name__ == "__main__":
    main()
